import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo, Clip, SourcePost, Transcript, ContentSource, Channel
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
        source_post_id = job.payload.get("source_post_id")

        if not clip_candidate_id and not source_post_id:
            raise StageUnrecoverableError("Missing both clip_candidate_id and source_post_id in job payload")

        clip_candidate = None
        source_video = None
        source_post = None
        transcript = None
        caption_style = "default"

        if clip_candidate_id:
            cc_uuid = uuid.UUID(clip_candidate_id) if isinstance(clip_candidate_id, str) else clip_candidate_id
            clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == cc_uuid).first()
            if not clip_candidate:
                raise StageUnrecoverableError(f"ClipCandidate {clip_candidate_id} not found")

            source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
            if not source_video:
                raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

            transcript = session.query(Transcript).filter(Transcript.source_video_id == source_video.id).first()
            if not transcript:
                raise StageUnrecoverableError(f"Transcript for SourceVideo {source_video.id} not found")

            # Resolve caption style from channel
            content_source = session.query(ContentSource).filter(ContentSource.id == source_video.content_source_id).first()
            if content_source:
                channel = session.query(Channel).filter(Channel.id == content_source.channel_id).first()
                if channel:
                    caption_style = channel.caption_style or "default"
        else:
            sp_uuid = uuid.UUID(source_post_id) if isinstance(source_post_id, str) else source_post_id
            source_post = session.query(SourcePost).filter(SourcePost.id == sp_uuid).first()
            if not source_post:
                raise StageUnrecoverableError(f"SourcePost {source_post_id} not found")

            transcript = session.query(Transcript).filter(Transcript.source_post_id == source_post.id).first()
            if not transcript:
                raise StageUnrecoverableError(f"Transcript for SourcePost {source_post.id} not found")

            # Resolve caption style from channel
            content_source = session.query(ContentSource).filter(ContentSource.id == source_post.content_source_id).first()
            if content_source:
                channel = session.query(Channel).filter(Channel.id == content_source.channel_id).first()
                if channel:
                    caption_style = channel.caption_style or "default"

        logger.info(
            f"Starting editing stage for { 'clip_candidate ' + str(clip_candidate_id) if clip_candidate else 'source_post ' + str(source_post_id) }",
            extra={"trace_id": job.trace_id}
        )

        # 1. Fetch transcript JSON from MinIO
        try:
            transcript_bytes = get_object_data("autonomous-media-transcripts", transcript.storage_key)
            words = json.loads(transcript_bytes.decode("utf-8"))
        except Exception as e:
            # Fallback check raw bucket if legacy key exists
            try:
                transcript_bytes = get_object_data("autonomous-media-raw", transcript.storage_key)
                words = json.loads(transcript_bytes.decode("utf-8"))
            except Exception:
                raise StageUnrecoverableError(f"Failed to fetch or parse transcript JSON: {e}")

        # 2. Build word timestamps for the clip window
        if clip_candidate:
            word_ts = words_from_raw_transcript(words, clip_candidate.start_ms, clip_candidate.end_ms)
            duration_s = int((clip_candidate.end_ms - clip_candidate.start_ms) / 1000.0)
            ass_storage_key = f"subtitles/{clip_candidate_id}.ass"
        else:
            # Full post duration
            word_ts = words_from_raw_transcript(words, 0, 1000000000)
            duration_s = 0
            if word_ts:
                duration_s = int(word_ts[-1].end_ms / 1000.0)
            ass_storage_key = f"subtitles/story-{source_post.id}.ass"

        if not word_ts:
            raise StageUnrecoverableError("No words found in the clip window timeline")

        # 3. Generate .ass subtitle file and upload to MinIO
        style = CaptionStyle.from_channel_config(caption_style)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ass_path = render_captions(word_ts, style, Path(tmp) / "captions.ass")
                put_object_data(
                    "autonomous-media-transcripts",
                    ass_storage_key,
                    ass_path.read_bytes(),
                    content_type="text/plain"
                )
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to generate or upload .ass captions: {e}")

        # 4. Resolve non-null channel_id
        resolved_channel_id = job.channel_id
        if not resolved_channel_id:
            if content_source:
                resolved_channel_id = content_source.channel_id
            if not resolved_channel_id:
                ch = session.query(Channel).first()
                if ch:
                    resolved_channel_id = ch.id

        if not resolved_channel_id:
            raise StageUnrecoverableError("No channel_id found to associate with rendered Clip")

        # 5. Create Clip row
        clip_id = uuid.uuid4()
        final_video_key = f"renders/{clip_id}.mp4"

        clip = Clip(
            id=clip_id,
            clip_candidate_id=clip_candidate.id if clip_candidate else None,
            source_post_id=source_post.id if source_post else None,
            channel_id=resolved_channel_id,
            storage_key=final_video_key,
            thumbnail_key=f"thumbnails/{clip_id}.jpg",
            duration_s=duration_s,
            caption_style=caption_style,
            status="rendering",
            created_at=datetime.now(timezone.utc)
        )
        session.add(clip)
        
        next_job_payload = {
            "clip_id": str(clip_id), 
            "ass_storage_key": ass_storage_key,
            "source_post_id": str(source_post.id) if source_post else None
        }
        
        session.flush()

        logger.info(
            f"Created Clip {clip_id} with status='rendering'",
            extra={"trace_id": job.trace_id}
        )

        # 6. Enqueue rendering job
        next_job = Job(
            type="rendering",
            payload=next_job_payload,
            trace_id=job.trace_id,
            channel_id=resolved_channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        return JobResult()
