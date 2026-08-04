import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo, Clip
from autonomous_media.storage import get_object_data, put_object_data
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError
from pathlib import Path
import tempfile
from autonomous_media.workers.captions import (
    CaptionStyle, render_captions, words_from_raw_transcript
)

logger = get_logger("workers.editing")

class EditingWorker(Worker):
    job_type = 'editing'

    def process(self, session: Session, job: Job) -> JobResult:
        clip_candidate_id = job.payload.get("clip_candidate_id")
        if not clip_candidate_id:
            raise StageUnrecoverableError("Missing clip_candidate_id in job payload")

        if isinstance(clip_candidate_id, str):
            try:
                clip_candidate_id = uuid.UUID(clip_candidate_id)
            except ValueError:
                raise StageUnrecoverableError(f"Invalid clip_candidate_id format: {clip_candidate_id}")

        clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip_candidate_id).first()
        if not clip_candidate:
            raise StageUnrecoverableError(f"ClipCandidate {clip_candidate_id} not found")

        source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
        if not source_video:
            raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

        # Load transcript using source_video_id
        # We query the Transcript table first to get the storage_key
        from autonomous_media.db.models import Transcript
        transcript = session.query(Transcript).filter(Transcript.source_video_id == source_video.id).first()
        if not transcript:
            raise StageUnrecoverableError(f"Transcript for SourceVideo {source_video.id} not found")

        logger.info(
            f"Starting editing stage for clip_candidate {clip_candidate_id}",
            extra={"trace_id": job.trace_id}
        )

        # 1. Fetch transcript JSON from MinIO
        try:
            transcript_bytes = get_object_data("autonomous-media-raw", transcript.storage_key)
            words = json.loads(transcript_bytes.decode("utf-8"))
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to fetch or parse transcript JSON: {e}")

        # 1.5 Determine caption style from channel (fallback to 'default')
        caption_style = 'default'
        from autonomous_media.db.models import Channel
        content_source = session.query(SourceVideo.content_source_id).filter(SourceVideo.id == source_video.id).first()
        if content_source:
            from autonomous_media.db.models import ContentSource
            channel_id_row = session.query(ContentSource.channel_id).filter(ContentSource.id == content_source[0]).first()
            if channel_id_row:
                channel = session.query(Channel).filter(Channel.id == channel_id_row[0]).first()
                if channel:
                    caption_style = channel.caption_style

        # 2. Build word timestamps for the clip window
        word_ts = words_from_raw_transcript(words, clip_candidate.start_ms, clip_candidate.end_ms)
        if not word_ts:
            raise StageUnrecoverableError("No words found in the clip window timeline")

        # 3. Generate .ass subtitle file and upload to MinIO
        #    Rendering worker will apply it during the FFmpeg encode pass.
        ass_storage_key = f"srt/{clip_candidate_id}.ass"
        style = CaptionStyle.from_channel_config(caption_style)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ass_path = render_captions(word_ts, style, Path(tmp) / "captions.ass")
                put_object_data(
                    "autonomous-media-raw",
                    ass_storage_key,
                    ass_path.read_bytes(),
                    content_type="text/plain"
                )
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to generate or upload .ass captions: {e}")

        # 4. Create Clip row
        clip_id = uuid.uuid4()
        duration_s = int((clip_candidate.end_ms - clip_candidate.start_ms) / 1000.0)

        # We set storage_key to the final video path
        final_video_key = f"clips/{clip_id}.mp4"

        clip = Clip(
            id=clip_id,
            clip_candidate_id=clip_candidate_id,
            channel_id=job.channel_id,
            storage_key=final_video_key,
            thumbnail_key=f"thumbnails/{clip_id}.jpg",
            duration_s=duration_s,
            caption_style=caption_style,
            status="rendering",
            created_at=datetime.now(timezone.utc)
        )
        session.add(clip)
        
        # Store the ASS file key in the job payload so rendering.py can fetch it
        next_job_payload = {"clip_id": str(clip_id), "ass_storage_key": ass_storage_key}
        
        session.flush()

        logger.info(
            f"Created Clip {clip_id} with status='rendering'",
            extra={"trace_id": job.trace_id}
        )

        # 5. Enqueue rendering job
        next_job = Job(
            type="rendering",
            payload=next_job_payload,
            trace_id=job.trace_id,
            channel_id=job.channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        return JobResult()
