import os
import json
import uuid
import tempfile
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, SourceVideo, Transcript
from autonomous_media.storage import download_file, put_object_data
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.transcription")

class TranscriptionWorker(Worker):
    job_type = 'transcription'

    def process(self, session: Session, job: Job) -> JobResult:
        from faster_whisper import WhisperModel
        from autonomous_media.db.models import SourcePost

        source_video_id = job.payload.get("source_video_id")
        source_post_id = job.payload.get("source_post_id")

        if not source_video_id and not source_post_id:
            raise StageUnrecoverableError("Missing both source_video_id and source_post_id in job payload")

        source_video = None
        source_post = None
        audio_storage_key = ""

        if source_video_id:
            sv_uuid = uuid.UUID(source_video_id) if isinstance(source_video_id, str) else source_video_id
            source_video = session.query(SourceVideo).filter(SourceVideo.id == sv_uuid).first()
            if not source_video:
                raise StageUnrecoverableError(f"SourceVideo {source_video_id} not found")
            audio_storage_key = f"raw/{source_video.id}/audio.wav"
            logger.info(
                f"Starting transcription for source_video {source_video.id}",
                extra={"trace_id": job.trace_id}
            )
        else:
            sp_uuid = uuid.UUID(source_post_id) if isinstance(source_post_id, str) else source_post_id
            source_post = session.query(SourcePost).filter(SourcePost.id == sp_uuid).first()
            if not source_post:
                raise StageUnrecoverableError(f"SourcePost {source_post_id} not found")
            audio_storage_key = f"raw/story-{source_post.id}/audio.wav"
            logger.info(
                f"Starting transcription for source_post {source_post.id}",
                extra={"trace_id": job.trace_id}
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_filename = "audio.wav"
            audio_path = os.path.join(temp_dir, audio_filename)

            # 1. Fetch audio.wav from MinIO
            try:
                download_file("autonomous-media-raw", audio_storage_key, audio_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download audio from MinIO: {e}")

            if not os.path.exists(audio_path):
                raise StageUnrecoverableError(f"Downloaded audio file not found at {audio_path}")

            # Verify audio format contract via ffmpeg probe
            try:
                import ffmpeg
                probe = ffmpeg.probe(audio_path)
                audio_stream = next((stream for stream in probe.get('streams', []) if stream.get('codec_type') == 'audio'), None)
                if audio_stream:
                    sample_rate = int(audio_stream.get('sample_rate', 0))
                    channels = int(audio_stream.get('channels', 0))
                    logger.info(
                        f"Audio probe results: sample_rate={sample_rate}Hz, channels={channels}",
                        extra={"trace_id": job.trace_id}
                    )
                else:
                    logger.warning("ffmpeg probe failed to find audio stream", extra={"trace_id": job.trace_id})
            except Exception as e:
                logger.warning(f"ffmpeg probe failed on {audio_path}: {e}", extra={"trace_id": job.trace_id})

            # 2. Run faster-whisper with device auto-detection (CUDA GPU if available, else CPU int8)
            try:
                device = "cpu"
                compute_type = "int8"
                try:
                    import torch
                    if torch.cuda.is_available():
                        device = "cuda"
                        compute_type = "float16"
                except Exception:
                    pass

                model_name = os.getenv("WHISPER_MODEL", "base")
                logger.info(
                    f"Loading Whisper model '{model_name}' on device='{device}', compute_type='{compute_type}'...",
                    extra={"trace_id": job.trace_id}
                )

                model = WhisperModel(model_name, device=device, compute_type=compute_type, cpu_threads=4)
                
                # Update heartbeat before starting transcribe stream
                job.last_heartbeat_at = datetime.now(timezone.utc)
                session.commit()

                segments, info = model.transcribe(audio_path, word_timestamps=True)
                
                logger.info(
                    f"Transcription started (detected language='{info.language}', duration={int(info.duration)}s)",
                    extra={"trace_id": job.trace_id}
                )

                # Convert generator to list while logging progress
                segments_list = []
                for seg in segments:
                    segments_list.append(seg)
                    job.last_heartbeat_at = datetime.now(timezone.utc)
                    session.commit()
                
                segments = segments_list
            except Exception as e:
                raise StageUnrecoverableError(f"faster-whisper transcription failed: {e}")

            # 3. Build the transcript JSON
            words_list = []
            word_count = 0
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        words_list.append({
                            "word": w.word,
                            "start_ms": int(w.start * 1000),
                            "end_ms": int(w.end * 1000)
                        })
                        word_count += 1

            transcript_id = uuid.uuid4()
            transcript_json = json.dumps(words_list, indent=2)
            transcript_bytes = transcript_json.encode("utf-8")

            # 4. Write JSON to MinIO transcripts/{transcript_id}.json
            transcript_storage_key = f"transcripts/{transcript_id}.json"
            try:
                # Use dedicated transcripts bucket as per specification
                put_object_data(
                    "autonomous-media-transcripts",
                    transcript_storage_key,
                    transcript_bytes,
                    content_type="application/json"
                )
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to upload transcript to MinIO: {e}")

            # 5. Create Transcript row
            transcript = Transcript(
                id=transcript_id,
                source_video_id=source_video.id if source_video else None,
                source_post_id=source_post.id if source_post else None,
                engine="whisper-large-v3-turbo",
                language=info.language,
                storage_key=transcript_storage_key,
                word_count=word_count,
                created_at=datetime.now(timezone.utc)
            )
            session.add(transcript)
            session.flush()

            if source_video:
                source_video.status = "transcribed"
            else:
                source_post.status = "transcribed"
            session.commit()

            # 6. Emit TRANSCRIPT_READY event
            emit_event(
                event_type="transcript.ready",
                trace_id=job.trace_id,
                payload={
                    "transcript_id": str(transcript_id),
                    "source_video_id": str(source_video.id) if source_video else None,
                    "source_post_id": str(source_post.id) if source_post else None,
                    "word_count": word_count
                }
            )

            # 7. Enqueue next job
            if source_video:
                # Podcast clips go to intelligence for candidate extraction
                next_job = Job(
                    type="intelligence",
                    payload={"transcript_id": str(transcript_id)},
                    trace_id=job.trace_id,
                    channel_id=job.channel_id,
                    priority=job.priority,
                    attempts=0,
                    max_attempts=3
                )
            else:
                # Curated stories bypass intelligence and go directly to editing
                next_job = Job(
                    type="editing",
                    payload={"source_post_id": str(source_post.id)},
                    trace_id=job.trace_id,
                    channel_id=job.channel_id,
                    priority=job.priority,
                    attempts=0,
                    max_attempts=3
                )
            session.add(next_job)
            session.commit()

            logger.info(
                f"Successfully completed transcription for { 'video ' + str(source_video.id) if source_video else 'post ' + str(source_post.id) }, word count: {word_count}",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()
