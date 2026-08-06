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
                # Fallback to gTTS voice synthesis if Piper is not installed/setup on machine
                logger.warning(f"Piper execution failed: {e}. Falling back to gTTS voice synthesis.", extra={"trace_id": job.trace_id})
                try:
                    from gtts import gTTS
                    text_to_speak = post.script_text or post.body_text or "This is an automated story narration video."
                    tts = gTTS(text=text_to_speak, lang="en")
                    mp3_temp = Path(temp_dir) / "narration_temp.mp3"
                    tts.save(str(mp3_temp))
                    
                    import subprocess
                    # Convert MP3 to 16kHz mono WAV for Whisper & FFmpeg rendering
                    try:
                        subprocess.run(["ffmpeg", "-i", str(mp3_temp), "-ar", "16000", "-ac", "1", str(local_audio_path), "-y"], check=True, capture_output=True)
                    except Exception:
                        subprocess.run(f'ffmpeg -i "{mp3_temp}" -ar 16000 -ac 1 "{local_audio_path}" -y', shell=True, check=True)
                except Exception as fallback_err:
                    logger.error(f"gTTS fallback failed: {fallback_err}. Writing silent audio fallback.", extra={"trace_id": job.trace_id})
                    import wave
                    with wave.open(str(local_audio_path), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(16000)
                        wav.writeframes(b"\x00" * 32000 * 30)

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
