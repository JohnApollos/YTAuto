import os
import tempfile
import subprocess
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, Clip, ClipCandidate, SourceVideo
from autonomous_media.storage import download_file, upload_file
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError

logger = get_logger("workers.rendering")

class RenderingWorker(Worker):
    job_type = 'rendering'

    def process(self, session: Session, job: Job) -> JobResult:
        clip_id = job.payload.get("clip_id")
        if not clip_id:
            raise StageUnrecoverableError("Missing clip_id in job payload")

        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {clip_id} not found")

        clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
        if not clip_candidate:
            raise StageUnrecoverableError(f"ClipCandidate {clip.clip_candidate_id} not found")

        source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
        if not source_video:
            raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

        logger.info(
            f"Starting rendering for Clip {clip_id} (candidate {clip_candidate.id})",
            extra={"trace_id": job.trace_id}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = "original.mp4"
            srt_filename = "captions.srt"
            output_filename = "output.mp4"

            video_path = os.path.join(temp_dir, video_filename)
            srt_path = os.path.join(temp_dir, srt_filename)
            output_path = os.path.join(temp_dir, output_filename)

            # 1. Fetch raw original video and srt from MinIO
            try:
                download_file("autonomous-media-raw", source_video.storage_key, video_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download video from MinIO: {e}")

            srt_storage_key = f"srt/{clip_candidate.id}.srt"
            try:
                download_file("autonomous-media-raw", srt_storage_key, srt_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download SRT from MinIO: {e}")

            if not os.path.exists(video_path) or not os.path.exists(srt_path):
                raise StageUnrecoverableError("Downloaded input files for rendering not found")

            # 2. Get video dimensions to calculate crop default if needed
            import ffmpeg
            try:
                probe = ffmpeg.probe(video_path)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                width = int(video_info['width'])
                height = int(video_info['height'])
            except Exception as e:
                logger.warning(f"FFmpeg probe failed, defaulting to 1920x1080: {e}", extra={"trace_id": job.trace_id})
                width, height = 1920, 1080

            aspect_ratio = width / height

            # 3. Calculate crop region
            crop_region = clip_candidate.scores.get("crop_region")
            if crop_region:
                crop_w_norm = crop_region["x_max"] - crop_region["x_min"]
                crop_x_norm = crop_region["x_min"]
            else:
                crop_w_norm = (9.0 / 16.0) / aspect_ratio
                crop_x_norm = 0.5 - (crop_w_norm / 2.0)

            start_sec = clip_candidate.start_ms / 1000.0
            end_sec = clip_candidate.end_ms / 1000.0

            # Build the FFmpeg command using ffmpeg-python
            stream = ffmpeg.input(video_filename, ss=start_sec, to=end_sec)
            video = stream.video
            audio = stream.audio

            # Apply filters
            video = video.filter('crop', f"in_w*{crop_w_norm}", "in_h", f"in_w*{crop_x_norm}", 0)
            video = video.filter('scale', 1080, 1920)
            
            # Burn subtitles using relative filename (run in temp_dir to avoid drive letter colon escaping issues)
            # Escaping filename for FFmpeg subtitles filter: replacing single backslashes and single quotes
            escaped_srt_filename = srt_filename.replace('\\', '/').replace(':', '\\:')
            video = video.filter('subtitles', escaped_srt_filename, force_style='FontSize=24,PrimaryColour=&H00FFFFFF')

            # 4. Compile and Run FFmpeg with hardware-encode fallback
            # We compile the graph to get arguments, and then run it with custom cwd=temp_dir
            logger.info("Compiling FFmpeg graph", extra={"trace_id": job.trace_id})

            # Attempt 1: AMD AMF Hardware encode
            args_amf = (
                ffmpeg
                .output(video, audio, output_filename, vcodec='h264_amf', acodec='aac')
                .overwrite_output()
                .compile()
            )
            
            logger.info(f"Running AMF render command: {' '.join(args_amf)}", extra={"trace_id": job.trace_id})
            try:
                res = subprocess.run(args_amf, cwd=temp_dir, check=True, capture_output=True)
                logger.info("Successfully rendered video using h264_amf hardware encoder", extra={"trace_id": job.trace_id})
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                stderr_msg = e.stderr.decode('utf8') if hasattr(e, 'stderr') and e.stderr else str(e)
                logger.warning(
                    f"h264_amf hardware encoder failed: {stderr_msg}. Falling back to libx264 CPU encoder.",
                    extra={"trace_id": job.trace_id}
                )

                # Attempt 2: CPU fallback
                args_cpu = (
                    ffmpeg
                    .output(video, audio, output_filename, vcodec='libx264', acodec='aac', pix_fmt='yuv420p')
                    .overwrite_output()
                    .compile()
                )
                try:
                    subprocess.run(args_cpu, cwd=temp_dir, check=True, capture_output=True)
                    logger.info("Successfully rendered video using libx264 CPU encoder", extra={"trace_id": job.trace_id})
                except subprocess.CalledProcessError as err:
                    err_msg = err.stderr.decode('utf8') if err.stderr else str(err)
                    raise StageUnrecoverableError(f"FFmpeg CPU fallback rendering failed: {err_msg}")

            if not os.path.exists(output_path):
                raise StageUnrecoverableError("Rendered output file not found")

            # 5. Upload rendered video to MinIO
            try:
                upload_file("autonomous-media-raw", clip.storage_key, output_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to upload rendered clip to MinIO: {e}")

            # 6. Update Clip status and save to DB
            clip.status = "qc_pending"
            session.commit()

            # 7. Emit EDIT_RENDER_COMPLETED event
            emit_event(
                event_type="edit.render.completed",
                trace_id=job.trace_id,
                payload={
                    "clip_id": str(clip_id),
                    "storage_key": clip.storage_key,
                    "duration_s": clip.duration_s
                }
            )

            # 8. Enqueue Quality Gate job
            next_job = Job(
                type="quality_gate",
                payload={"clip_id": str(clip_id)},
                trace_id=job.trace_id,
                channel_id=job.channel_id,
                priority=job.priority,
                attempts=0,
                max_attempts=3
            )
            session.add(next_job)
            session.commit()

            logger.info(
                f"Successfully completed rendering stage for Clip {clip_id}. Enqueued quality_gate job.",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()
