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

        # Resolve voice profile (auto-detect male vs female voice based on post story content if neutral)
        from autonomous_media.workers.narration import detect_narrator_voice, normalize_spoken_script

        channel = session.query(Channel).filter(Channel.id == content_source.channel_id).first()
        voice_profile = getattr(channel, "voice_profile", None) if channel else None
        if not voice_profile or voice_profile == "narrator_neutral_v1":
            voice_profile = detect_narrator_voice(post.title, post.body_text)

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

            # Sanitize & normalize text for spoken flow (e.g. 21M -> 21 male, 10km -> 10 kilometers, AITA -> Am I the jerk)
            from autonomous_media.workers.narration import validate_and_clean_narration_script
            validated_text = validate_and_clean_narration_script(post.script_text, post.title, post.body_text)
            text_to_speak = normalize_spoken_script(validated_text)

            try:
                narrate(
                    script_text=text_to_speak,
                    voice_profile=voice_profile,
                    output_path=local_audio_path
                )
            except Exception as e:
                # Fallback 1: gTTS voice synthesis
                logger.warning(f"Piper execution failed: {e}. Falling back to gTTS / pyttsx3 voice synthesis.", extra={"trace_id": job.trace_id})
                success_tts = False
                try:
                    from gtts import gTTS
                    tts = gTTS(text=text_to_speak, lang="en")
                    mp3_temp = Path(temp_dir) / "narration_temp.mp3"
                    tts.save(str(mp3_temp))
                    
                    import subprocess
                    # Convert MP3 to 16kHz mono WAV for Whisper & FFmpeg rendering
                    try:
                        subprocess.run(["ffmpeg", "-i", str(mp3_temp), "-ar", "16000", "-ac", "1", str(local_audio_path), "-y"], check=True, capture_output=True)
                    except Exception:
                        subprocess.run(f'ffmpeg -i "{mp3_temp}" -ar 16000 -ac 1 "{local_audio_path}" -y', shell=True, check=True)
                    success_tts = True
                except Exception as gtts_err:
                    logger.warning(f"gTTS fallback failed: {gtts_err}. Trying offline pyttsx3...", extra={"trace_id": job.trace_id})

                if not success_tts:
                    try:
                        import pyttsx3
                        engine = pyttsx3.init()
                        engine.save_to_file(text_to_speak, str(local_audio_path))
                        engine.runAndWait()
                        success_tts = True
                        logger.info("Successfully synthesized audio via pyttsx3 offline TTS", extra={"trace_id": job.trace_id})
                    except Exception as pyttsx_err:
                        logger.error(f"pyttsx3 fallback failed: {pyttsx_err}.", extra={"trace_id": job.trace_id})

            if not os.path.exists(local_audio_path) or os.path.getsize(local_audio_path) == 0:
                logger.warning(f"Narration audio file missing at {local_audio_path}. Creating emergency audio file.", extra={"trace_id": job.trace_id})
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
