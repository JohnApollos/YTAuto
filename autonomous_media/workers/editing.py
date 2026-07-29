import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo, Clip
from autonomous_media.storage import get_object_data, put_object_data
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

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

        # 2. Filter words and build SRT
        srt_content = self._generate_srt(words, clip_candidate.start_ms, clip_candidate.end_ms)
        if not srt_content:
            raise StageUnrecoverableError("No words found in the clip window timeline")

        # 3. Upload SRT to MinIO under srt/{clip_candidate_id}.srt
        srt_storage_key = f"srt/{clip_candidate_id}.srt"
        try:
            put_object_data(
                "autonomous-media-raw",
                srt_storage_key,
                srt_content.encode("utf-8"),
                content_type="text/plain"
            )
        except Exception as e:
            raise StageUnrecoverableError(f"Failed to upload SRT to MinIO: {e}")

        # 4. Create Clip row
        clip_id = uuid.uuid4()
        duration_s = int((clip_candidate.end_ms - clip_candidate.start_ms) / 1000.0)
        
        # Determine caption style from channel (fallback to 'default')
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
        session.flush()

        logger.info(
            f"Created Clip {clip_id} with status='rendering'",
            extra={"trace_id": job.trace_id}
        )

        # 5. Enqueue rendering job
        next_job = Job(
            type="rendering",
            payload={"clip_id": str(clip_id)},
            trace_id=job.trace_id,
            channel_id=job.channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        return JobResult()

    def _format_ms_to_srt_time(self, ms: int) -> str:
        sec, msec = divmod(ms, 1000)
        min_val, sec = divmod(sec, 60)
        hr, min_val = divmod(min_val, 60)
        return f"{hr:02d}:{min_val:02d}:{sec:02d},{msec:03d}"

    def _generate_srt(self, words: list[dict], start_ms: int, end_ms: int) -> str:
        clip_words = [w for w in words if w["start_ms"] >= start_ms and w["end_ms"] <= end_ms]
        if not clip_words:
            return ""
            
        srt_blocks = []
        current_block_words = []
        block_index = 1
        
        for w in clip_words:
            current_block_words.append(w)
            text_len = sum(len(x["word"]) for x in current_block_words) + len(current_block_words) - 1
            if len(current_block_words) >= 3 or text_len >= 20:
                rel_start = max(0, current_block_words[0]["start_ms"] - start_ms)
                rel_end = max(rel_start + 100, current_block_words[-1]["end_ms"] - start_ms)
                
                line_text = " ".join(x["word"] for x in current_block_words)
                srt_blocks.append(
                    f"{block_index}\n"
                    f"{self._format_ms_to_srt_time(rel_start)} --> {self._format_ms_to_srt_time(rel_end)}\n"
                    f"{line_text}\n"
                )
                block_index += 1
                current_block_words = []
                
        if current_block_words:
            rel_start = max(0, current_block_words[0]["start_ms"] - start_ms)
            rel_end = max(rel_start + 100, current_block_words[-1]["end_ms"] - start_ms)
            line_text = " ".join(x["word"] for x in current_block_words)
            srt_blocks.append(
                f"{block_index}\n"
                f"{self._format_ms_to_srt_time(rel_start)} --> {self._format_ms_to_srt_time(rel_end)}\n"
                f"{line_text}\n"
            )
            
        return "\n".join(srt_blocks)
