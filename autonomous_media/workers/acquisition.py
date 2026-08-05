import uuid
import os
import tempfile
import hashlib
import yt_dlp
import ffmpeg
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, ContentSource, SourceVideo
from autonomous_media.sources.youtube_clip import YouTubeClipSource
from autonomous_media.storage import upload_file
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.events import VIDEO_DOWNLOADED
from autonomous_media.exceptions import StageUnrecoverableError, QuotaExceededError

from autonomous_media.config import settings

logger = get_logger("workers.acquisition")

class AcquisitionWorker(Worker):
    job_type = 'acquisition'

    def process(self, session: Session, job: Job) -> JobResult:
        source_id = job.payload.get("source_id")
        if not source_id:
            raise StageUnrecoverableError("Missing source_id in job payload")

        content_source = session.query(ContentSource).filter(ContentSource.id == source_id).first()
        if not content_source:
            raise StageUnrecoverableError(f"ContentSource {source_id} not found")

        # Get existing external_video_ids to avoid duplicates and stop discover paging early
        existing_videos = session.query(SourceVideo.external_video_id).filter(
            SourceVideo.content_source_id == source_id
        ).all()
        existing_ids = {v[0] for v in existing_videos}

        # Resolve api_key
        api_key = content_source.config.get("api_key") or settings.youtube_api_key
        if not api_key:
            raise StageUnrecoverableError("No API key found in ContentSource config or environment")

        since_published_after = content_source.config.get("since_published_after")

        max_new_items = content_source.config.get("max_new_videos_per_poll", 1)

        # Instantiate the clip source
        clip_source = YouTubeClipSource(
            channel_youtube_id=content_source.external_ref,
            api_key=api_key,
            since_published_after=since_published_after,
            max_new_items=max_new_items
        )

        try:
            discovered_items = clip_source.discover(existing_ids=existing_ids)
        except (QuotaExceededError, StageUnrecoverableError) as e:
            raise e
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to discover content items: {e}")

        logger.info(
            f"Discovered {len(discovered_items)} new videos",
            extra={"trace_id": job.trace_id, "source_id": str(source_id)}
        )

        for item in discovered_items:
            # Check double check db
            already_exists = session.query(SourceVideo).filter(
                SourceVideo.content_source_id == source_id,
                SourceVideo.external_video_id == item.external_id
            ).first()
            if already_exists:
                continue

            source_video_id = uuid.uuid4()
            trace_id = f"video-{source_video_id}"

            # Create a unique trace_id for this video pipeline
            logger.info(
                f"Starting acquisition for video {item.external_id}",
                extra={"trace_id": trace_id, "url": item.url}
            )

            # Check SSRF guard
            if "youtube.com" not in item.url and "youtu.be" not in item.url:
                raise StageUnrecoverableError(f"SSRF guard: unexpected URL domain in fetch: {item.url}")

            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            cookies_path = os.path.join(project_root, "cookies.txt")

            with tempfile.TemporaryDirectory() as temp_dir:
                video_filename = f"{item.external_id}.mp4"
                video_path = os.path.join(temp_dir, video_filename)
                audio_path = os.path.join(temp_dir, f"{item.external_id}.wav")

                # Fetch (download with yt-dlp)
                ydl_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': video_path,
                    'quiet': True,
                    'no_warnings': True,
                    'merge_output_format': 'mp4',
                }
                if os.path.exists(cookies_path):
                    ydl_opts['cookiefile'] = cookies_path
                    logger.info("Using cookies.txt file for yt-dlp authentication", extra={"trace_id": trace_id})
                else:
                    logger.warning("No cookies.txt file found. If download fails due to bot detection, place cookies.txt in project root.", extra={"trace_id": trace_id})

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([item.url])
                except Exception as e:
                    logger.error(f"yt-dlp download failed: {e}", extra={"trace_id": trace_id})
                    continue

                if not os.path.exists(video_path):
                    logger.error(f"Downloaded video file not found at {video_path}", extra={"trace_id": trace_id})
                    continue

                # Compute checksum_sha256
                sha256_hash = hashlib.sha256()
                with open(video_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                checksum = sha256_hash.hexdigest()

                # Upload to MinIO
                video_storage_key = f"raw/{source_video_id}/original.mp4"
                try:
                    upload_file("autonomous-media-raw", video_storage_key, video_path)
                except Exception as e:
                    raise StageUnrecoverableError(f"Failed to upload video to MinIO: {e}")

                # Extract audio: 16kHz mono WAV
                try:
                    (
                        ffmpeg
                        .input(video_path)
                        .output(audio_path, ar=16000, ac=1, vn=None)
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                except ffmpeg.Error as e:
                    stderr_msg = e.stderr.decode('utf8') if e.stderr else str(e)
                    logger.error(f"FFmpeg audio extraction failed: {stderr_msg}", extra={"trace_id": trace_id})
                    continue

                if not os.path.exists(audio_path):
                    logger.error(f"Extracted audio file not found at {audio_path}", extra={"trace_id": trace_id})
                    continue

                # Upload audio to MinIO
                audio_storage_key = f"raw/{source_video_id}/audio.wav"
                try:
                    upload_file("autonomous-media-raw", audio_storage_key, audio_path)
                except Exception as e:
                    raise StageUnrecoverableError(f"Failed to upload audio to MinIO: {e}")

                # Get duration
                duration_s = None
                try:
                    probe = ffmpeg.probe(video_path)
                    format_info = probe.get("format", {})
                    duration_s = int(float(format_info.get("duration", 0)))
                except Exception as e:
                    logger.warning(f"Failed to probe video duration: {e}", extra={"trace_id": trace_id})

                # Parse published_at
                pub_date = None
                if item.published_at:
                    try:
                        date_str = item.published_at.replace("Z", "+00:00")
                        pub_date = datetime.fromisoformat(date_str)
                    except Exception as e:
                        logger.warning(f"Failed to parse published_at: {e}", extra={"trace_id": trace_id})

                # Create SourceVideo row
                sv = SourceVideo(
                    id=source_video_id,
                    content_source_id=source_id,
                    external_video_id=item.external_id,
                    title=item.title,
                    url=item.url,
                    published_at=pub_date,
                    downloaded_at=datetime.now(timezone.utc),
                    duration_s=duration_s,
                    status="downloaded",
                    storage_key=video_storage_key,
                    checksum_sha256=checksum
                )
                session.add(sv)
                session.flush()

                # Emit VIDEO_DOWNLOADED event
                emit_event(
                    event_type="video.downloaded",
                    trace_id=trace_id,
                    payload={"source_video_id": str(source_video_id), "external_video_id": item.external_id}
                )

                # Enqueue transcription job
                next_job = Job(
                    type="transcription",
                    payload={"source_video_id": str(source_video_id)},
                    trace_id=trace_id,
                    channel_id=content_source.channel_id,
                    priority=job.priority,
                    attempts=0,
                    max_attempts=3
                )
                session.add(next_job)
                session.commit()

                logger.info(
                    f"Successfully processed video {item.external_id}, enqueued transcription",
                    extra={"trace_id": trace_id}
                )

        # Update ContentSource.last_polled_at
        content_source.last_polled_at = datetime.now(timezone.utc)
        session.commit()

        return JobResult()
