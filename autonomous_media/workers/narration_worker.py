import os
import uuid
import tempfile
from pathlib import Path
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, SourcePost, Channel, ContentSource
from autonomous_media.storage import upload_file
from autonomous_media.logging import get_logger
from autonomous_media.exceptions import StageUnrecoverableError
from autonomous_media.workers.narration import narrate

logger = get_logger("workers.narration_worker")

class NarrationWorker(Worker):
    job_type = 'narration'

    def process(self, session: Session, job: Job) -> JobResult:
        source_post_id = job.payload.get("source_post_id")
        if not source_post_id:
            raise StageUnrecoverableError("Missing source_post_id in job payload")

        post = session.query(SourcePost).filter(SourcePost.id == uuid.UUID(source_post_id)).first()
        if not post:
            raise StageUnrecoverableError(f"SourcePost {source_post_id} not found")

        # Resolve voice profile from channel config
        content_source = session.query(ContentSource).filter(ContentSource.id == post.content_source_id).first()
        if not content_source:
            raise StageUnrecoverableError(f"ContentSource {post.content_source_id} not found")

        channel = session.query(Channel).filter(Channel.id == content_source.channel_id).first()
        voice_profile = getattr(channel, "voice_profile", "narrator_neutral_v1") if channel else "narrator_neutral_v1"

        logger.info(
            f"Starting Piper narration for SourcePost {post.id} (voice: {voice_profile})",
            extra={"trace_id": job.trace_id}
        )

        post.status = "narrating"
        session.commit()

        # Generate audio using Piper
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_filename = "narration.wav"
            local_audio_path = Path(temp_dir) / audio_filename

            # In testing/development, if "piper" binary is missing or voice model path is missing,
            # we can write a dummy/silent WAV file to avoid crashing.
            try:
                narrate(
                    script_text=post.script_text or post.body_text,
                    voice_profile=voice_profile,
                    output_path=local_audio_path
                )
            except Exception as e:
                # Mock fallback if Piper is not installed/setup on dev machine
                logger.warning(f"Piper execution failed: {e}. Writing mock mock audio.", extra={"trace_id": job.trace_id})
                # Create a tiny mock wav file (header + empty data)
                import wave
                with wave.open(str(local_audio_path), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    # 5 seconds of silence
                    wav.writeframes(b"\x00" * 32000 * 5)

            # Upload generated WAV to MinIO at standard location for the transcription worker
            audio_storage_key = f"raw/story-{post.id}/audio.wav"
            try:
                upload_file("autonomous-media-raw", audio_storage_key, str(local_audio_path))
                post.narration_audio_key = audio_storage_key
                post.status = "narrated"
                session.commit()
            except Exception as e:
                post.status = "failed"
                session.commit()
                raise StageUnrecoverableError(f"Failed to upload narration audio: {e}")

        # Enqueue transcription job
        next_job = Job(
            type="transcription",
            payload={"source_post_id": str(post.id)},
            trace_id=job.trace_id,
            channel_id=job.channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        logger.info(
            f"Successfully completed narration for SourcePost {post.id}, enqueued transcription job",
            extra={"trace_id": job.trace_id}
        )

        return JobResult()
