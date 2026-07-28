import os
import tempfile
import statistics
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo
from autonomous_media.storage import download_file
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.vision")

class VisionWorker(Worker):
    job_type = 'vision'

    def process(self, session: Session, job: Job) -> JobResult:
        import cv2
        import mediapipe as mp
        clip_candidate_id = job.payload.get("clip_candidate_id")
        if not clip_candidate_id:
            raise StageUnrecoverableError("Missing clip_candidate_id in job payload")

        clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip_candidate_id).first()
        if not clip_candidate:
            raise StageUnrecoverableError(f"ClipCandidate {clip_candidate_id} not found")

        source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
        if not source_video:
            raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

        logger.info(
            f"Starting vision analysis (face detection) for clip_candidate {clip_candidate_id}",
            extra={"trace_id": job.trace_id}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = f"{source_video.id}_original.mp4"
            video_path = os.path.join(temp_dir, video_filename)

            # 1. Fetch raw video from MinIO
            try:
                download_file("autonomous-media-raw", source_video.storage_key, video_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download raw video from MinIO: {e}")

            if not os.path.exists(video_path):
                raise StageUnrecoverableError(f"Downloaded video file not found at {video_path}")

            # 2. Run face detection on key frames (every 0.5s)
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise StageUnrecoverableError(f"Failed to open video file {video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0 # Default fallback
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            if width <= 0 or height <= 0:
                cap.release()
                raise StageUnrecoverableError(f"Invalid video dimensions: {width}x{height}")

            # Aspect ratio of the original video
            aspect_ratio = width / height

            # We want to crop to vertical 9:16 aspect ratio
            # crop_w / crop_h = 9/16
            # In normalized coordinates, if crop_h_norm = 1.0 (full height),
            # then crop_w_pixels = height * (9/16)
            # crop_w_norm = crop_w_pixels / width = (height * 9/16) / width = (9/16) / aspect_ratio
            crop_width_norm = (9.0 / 16.0) / aspect_ratio

            # Seek to start of clip candidate (start_ms)
            start_sec = clip_candidate.start_ms / 1000.0
            end_sec = clip_candidate.end_ms / 1000.0
            
            start_frame = int(start_sec * fps)
            end_frame = int(end_sec * fps)

            # Sample key frames every 0.5 seconds
            frame_step = int(fps * 0.5)
            if frame_step <= 0:
                frame_step = 1

            x_centers = []

            # Initialize MediaPipe Face Detection
            mp_face_detection = mp.solutions.face_detection
            with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
                for frame_idx in range(start_frame, end_frame, frame_step):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # Convert BGR to RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = face_detection.process(rgb_frame)

                    if results.detections:
                        # Take the first detected face (usually speaker)
                        detection = results.detections[0]
                        bbox = detection.location_data.relative_bounding_box
                        # Bounding box center x
                        x_center = bbox.xmin + (bbox.width / 2.0)
                        x_centers.append(x_center)

            cap.release()

            # 3. Compute crop region (median bounding box center)
            if x_centers:
                x_center = statistics.median(x_centers)
            else:
                x_center = 0.5 # Default to center of screen if no face is detected

            x_min = x_center - (crop_width_norm / 2.0)
            x_max = x_center + (crop_width_norm / 2.0)

            # Clamping to [0.0, 1.0] while preserving the exact crop width
            if x_min < 0.0:
                diff = 0.0 - x_min
                x_min = 0.0
                x_max = min(1.0, x_max + diff)
            elif x_max > 1.0:
                diff = x_max - 1.0
                x_max = 1.0
                x_min = max(0.0, x_min - diff)

            crop_region = {
                "x_min": round(float(x_min), 4),
                "x_max": round(float(x_max), 4),
                "y_min": 0.0,
                "y_max": 1.0
            }

            # 4. Store crop region in ClipCandidate.scores
            scores = dict(clip_candidate.scores or {})
            scores["crop_region"] = crop_region
            clip_candidate.scores = scores
            session.commit()

            # 5. Emit VIDEO_ANALYZED event
            emit_event(
                event_type="video.analyzed",
                trace_id=job.trace_id,
                payload={
                    "clip_candidate_id": str(clip_candidate_id),
                    "crop_region": crop_region,
                    "faces_detected_count": len(x_centers)
                }
            )

            # Enqueue editing job
            next_job = Job(
                type="editing",
                payload={"clip_candidate_id": str(clip_candidate_id)},
                trace_id=job.trace_id,
                channel_id=job.channel_id,
                priority=job.priority,
                attempts=0,
                max_attempts=3
            )
            session.add(next_job)
            session.commit()

            logger.info(
                f"Successfully completed vision analysis for candidate {clip_candidate_id}. Crop center x: {x_center:.4f}. Enqueued editing job.",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()
