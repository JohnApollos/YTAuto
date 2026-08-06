import os
import tempfile
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, Clip, InventoryItem
from autonomous_media.storage import download_file
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.quality_gate")

class QualityGateWorker(Worker):
    job_type = 'quality_gate'

    def process(self, session: Session, job: Job) -> JobResult:
        clip_id = job.payload.get("clip_id")
        if not clip_id:
            raise StageUnrecoverableError("Missing clip_id in job payload")

        if isinstance(clip_id, str):
            try:
                clip_id = uuid.UUID(clip_id)
            except ValueError:
                raise StageUnrecoverableError(f"Invalid clip_id format: {clip_id}")

        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {clip_id} not found")

        logger.info(
            f"Starting Quality Gate checks for Clip {clip_id}",
            extra={"trace_id": job.trace_id}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = f"{clip_id}_rendered.mp4"
            video_path = os.path.join(temp_dir, video_filename)

            # 1. Download rendered video from MinIO (autonomous-media-renders)
            try:
                try:
                    download_file("autonomous-media-renders", clip.storage_key, video_path)
                except Exception:
                    download_file("autonomous-media-raw", clip.storage_key, video_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download rendered video from MinIO: {e}")

            if not os.path.exists(video_path):
                raise StageUnrecoverableError(f"Downloaded clip file not found at {video_path}")

            # 2. Run FFmpeg probe checks
            import ffmpeg
            try:
                probe = ffmpeg.probe(video_path)
            except Exception as e:
                raise StageUnrecoverableError(f"FFmpeg probe failed on rendered clip: {e}")

            video_stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'video'), None)
            audio_stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'audio'), None)

            qc_errors = []

            # Check 1: Video stream presence
            if not video_stream:
                qc_errors.append("No video stream found in the rendered clip")
            else:
                # Check 2: Aspect Ratio (9:16 vertical)
                width = int(video_stream.get('width', 0))
                height = int(video_stream.get('height', 0))
                if width <= 0 or height <= 0:
                    qc_errors.append(f"Invalid video dimensions: {width}x{height}")
                else:
                    ratio = width / height
                    expected_ratio = 9.0 / 16.0
                    if abs(ratio - expected_ratio) > 0.05:
                        qc_errors.append(f"Invalid aspect ratio: {width}x{height} (expected 9:16 vertical)")

            # Check 3: Duration check (15s to 90s)
            duration = float(probe.get('format', {}).get('duration', 0))
            if duration <= 0:
                qc_errors.append("Video duration is zero or not found")
            elif not (15.0 <= duration <= 90.0):
                qc_errors.append(f"Video duration is {duration:.2f}s (must be between 15s and 90s)")

            # Check 4: Audio presence
            if not audio_stream:
                qc_errors.append("No audio stream found in the rendered clip")

            # 3. Handle QC Results
            if qc_errors:
                error_msg = "; ".join(qc_errors)
                logger.error(
                    f"Clip {clip_id} failed Quality Gate: {error_msg}",
                    extra={"trace_id": job.trace_id}
                )

                clip.status = "qc_failed"
                session.commit()

                emit_event(
                    event_type="qc.failed",
                    trace_id=job.trace_id,
                    payload={"clip_id": str(clip_id), "reason": error_msg}
                )
                
                # We return job success (since worker successfully evaluated the gate) but clip fails
                return JobResult()

            # QC Passed!
            logger.info(
                f"Clip {clip_id} passed all Quality Gate checks",
                extra={"trace_id": job.trace_id}
            )

            clip.status = "qc_passed"
            
            # Create InventoryItem row with status="ready"
            inventory_item = InventoryItem(
                id=uuid.uuid4(),
                clip_id=clip_id,
                channel_id=clip.channel_id,
                status="ready",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(inventory_item)
            session.flush()

            emit_event(
                event_type="qc.passed",
                trace_id=job.trace_id,
                payload={
                    "clip_id": str(clip_id),
                    "inventory_item_id": str(inventory_item.id),
                    "duration_s": duration
                }
            )

            # Enqueue publishing job
            next_job = Job(
                type="publishing",
                payload={"inventory_item_id": str(inventory_item.id)},
                trace_id=job.trace_id,
                channel_id=job.channel_id,
                priority=job.priority,
                attempts=0,
                max_attempts=3
            )
            session.add(next_job)
            session.commit()

            logger.info(
                f"Created InventoryItem {inventory_item.id} with status='ready', enqueued publishing job",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()
