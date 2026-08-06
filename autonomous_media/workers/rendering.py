import os
import uuid
import tempfile
import subprocess
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, Clip, ClipCandidate, SourceVideo, BackgroundAsset, ContentSource, SourcePost
from autonomous_media.storage import download_file, upload_file
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.exceptions import StageUnrecoverableError
from pathlib import Path

logger = get_logger("workers.rendering")

def download_youtube_background(url: str, temp_dir: str) -> str:
    """Download a YouTube background video using yt-dlp."""
    import yt_dlp
    output_tmpl = os.path.join(temp_dir, "downloaded_bg.%(ext)s")
    
    # We restrict to mp4 video around 720p/1080p to keep it fast
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]/best[ext=mp4]/best',
        'outtmpl': output_tmpl,
        'quiet': True,
        'no_warnings': True,
    }
    
    logger.info(f"Downloading background video from URL: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

class RenderingWorker(Worker):
    job_type = 'rendering'

    def process(self, session: Session, job: Job) -> JobResult:
        clip_id = job.payload.get("clip_id")
        ass_storage_key = job.payload.get("ass_storage_key")
        source_post_id = job.payload.get("source_post_id")

        if not clip_id:
            raise StageUnrecoverableError("Missing clip_id in job payload")

        clip = session.query(Clip).filter(Clip.id == uuid.UUID(clip_id) if isinstance(clip_id, str) else clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {clip_id} not found")

        logger.info(
            f"Starting rendering for Clip {clip_id}",
            extra={"trace_id": job.trace_id}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = "original.mp4"
            ass_filename = "captions.ass"
            output_filename = "output.mp4"
            audio_filename = "narration.wav"

            video_path = os.path.join(temp_dir, video_filename)
            ass_path = os.path.join(temp_dir, ass_filename)
            output_path = os.path.join(temp_dir, output_filename)
            audio_path = os.path.join(temp_dir, audio_filename)

            is_story = source_post_id is not None
            bg_asset_used = None

            if not is_story:
                # Podcast clipping workflow
                clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
                if not clip_candidate:
                    raise StageUnrecoverableError(f"ClipCandidate {clip.clip_candidate_id} not found")

                source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
                if not source_video:
                    raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

                # Fetch raw original video from MinIO
                try:
                    download_file("autonomous-media-raw", source_video.storage_key, video_path)
                except Exception as e:
                    raise StageUnrecoverableError(f"Failed to download video from MinIO: {e}")
            else:
                # Reddit stories workflow: Resolve background asset & source_post
                sp_uuid = uuid.UUID(source_post_id) if isinstance(source_post_id, str) else source_post_id
                source_post = session.query(SourcePost).filter(SourcePost.id == sp_uuid).first()
                if not source_post:
                    raise StageUnrecoverableError(f"SourcePost {source_post_id} not found")

                content_source = session.query(ContentSource).filter(ContentSource.id == source_post.content_source_id).first()
                bg_urls = []
                if content_source and content_source.config:
                    bg_urls = content_source.config.get("background_urls", [])

                downloaded_path = None
                for url in bg_urls:
                    # Check if already downloaded/registered
                    existing = session.query(BackgroundAsset).filter(BackgroundAsset.source_url == url).first()
                    if existing:
                        bg_asset_used = existing
                        break
                    
                    # Try downloading it
                    try:
                        downloaded_path = download_youtube_background(url, temp_dir)
                        if downloaded_path and os.path.exists(downloaded_path):
                            # Save to MinIO & register in DB
                            asset_id = uuid.uuid4()
                            storage_key = f"backgrounds/{asset_id}.mp4"
                            upload_file("autonomous-media-renders", storage_key, downloaded_path)
                            
                            bg_asset_used = BackgroundAsset(
                                id=asset_id,
                                storage_key=storage_key,
                                source_url=url,
                                license_type="licensed",
                                status="active",
                                created_at=datetime.now(timezone.utc)
                            )
                            session.add(bg_asset_used)
                            session.commit()
                            break
                    except Exception as e:
                        logger.warning(f"Failed to download background YouTube URL {url}: {e}")

                if not bg_asset_used:
                    # Fallback to choosing a random BackgroundAsset from DB (using dialect-agnostic func.random())
                    from sqlalchemy import func
                    bg_asset_used = session.query(BackgroundAsset).filter(BackgroundAsset.status == "active").order_by(func.random()).first()

                if not bg_asset_used:
                    raise StageUnrecoverableError("No background assets found. Provide background YouTube URLs or register background footage first.")

                clip.background_asset_id = bg_asset_used.id
                session.commit()

                # Download background video asset
                try:
                    download_file("autonomous-media-renders", bg_asset_used.storage_key, video_path)
                except Exception:
                    try:
                        download_file("autonomous-media-raw", bg_asset_used.storage_key, video_path)
                    except Exception as e:
                        # If storage key in MinIO missing (e.g. seed data), attempt auto-downloading from YouTube source_url
                        if bg_asset_used.source_url:
                            logger.info(f"Background MinIO key {bg_asset_used.storage_key} missing. Downloading from YouTube {bg_asset_used.source_url}...", extra={"trace_id": job.trace_id})
                            dl_path = download_youtube_background(bg_asset_used.source_url, temp_dir)
                            if dl_path and os.path.exists(dl_path):
                                upload_file("autonomous-media-renders", bg_asset_used.storage_key, dl_path)
                                video_path = dl_path
                            else:
                                raise StageUnrecoverableError(f"Failed to download background asset: {e}")
                        else:
                            raise StageUnrecoverableError(f"Failed to download background asset: {e}")

                # Download narration audio
                try:
                    download_file("autonomous-media-raw", f"raw/story-{source_post_id}/audio.wav", audio_path)
                except Exception as e:
                    raise StageUnrecoverableError(f"Failed to download narration audio: {e}")

            # Download subtitles (.ass or fallback .srt)
            use_ass = True
            if ass_storage_key:
                try:
                    download_file("autonomous-media-transcripts", ass_storage_key, ass_path)
                except Exception as e:
                    try:
                        download_file("autonomous-media-raw", ass_storage_key, ass_path)
                    except Exception:
                        raise StageUnrecoverableError(f"Failed to download ASS from MinIO: {e}")
            else:
                use_ass = False
                clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
                srt_storage_key = f"srt/{clip_candidate.id}.srt" if clip_candidate else f"srt/{clip.id}.srt"
                try:
                    download_file("autonomous-media-transcripts", srt_storage_key, srt_path := os.path.join(temp_dir, "captions.srt"))
                except Exception as e:
                    try:
                        download_file("autonomous-media-raw", srt_storage_key, srt_path := os.path.join(temp_dir, "captions.srt"))
                    except Exception:
                        raise StageUnrecoverableError(f"Failed to download SRT from MinIO: {e}")

            if not os.path.exists(video_path) or (use_ass and not os.path.exists(ass_path)) or (not use_ass and not os.path.exists(srt_path)):
                raise StageUnrecoverableError("Downloaded input files for rendering not found")

            # Get video dimensions to calculate crop
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

            is_long_form = False
            if is_story and source_post:
                word_count = len((source_post.body_text or "").split())
                if word_count > 150:
                    is_long_form = True

            if not is_story:
                clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
                crop_region = clip_candidate.scores.get("crop_region") if clip_candidate else None
                if crop_region:
                    crop_w_norm = crop_region["x_max"] - crop_region["x_min"]
                    crop_x_norm = crop_region["x_min"]
                else:
                    crop_w_norm = (9.0 / 16.0) / aspect_ratio
                    crop_x_norm = 0.5 - (crop_w_norm / 2.0)

                start_sec = clip_candidate.start_ms / 1000.0 if clip_candidate else 0.0
                end_sec = clip_candidate.end_ms / 1000.0 if clip_candidate else 10.0
                
                # Build FFmpeg graph
                stream = ffmpeg.input(video_path, ss=start_sec, to=end_sec)
                video = stream.video
                audio = stream.audio

                # Crop and scale to 9:16 vertical (1080x1920)
                video = video.filter('crop', f"in_w*{crop_w_norm}", "in_h", f"in_w*{crop_x_norm}", 0)
                video = video.filter('scale', 1080, 1920)
            elif is_long_form:
                # Long-Form Stories (>150 words): 16:9 Landscape (1920x1080)
                # Random inner segment from long background asset
                import random
                bg_ss = 0.0
                try:
                    probe_bg = ffmpeg.probe(video_path)
                    probe_aud = ffmpeg.probe(audio_path)
                    bg_dur = float(probe_bg.get('format', {}).get('duration', 0))
                    aud_dur = float(probe_aud.get('format', {}).get('duration', 10.0))
                    if bg_dur > aud_dur + 10.0:
                        bg_ss = random.uniform(5.0, bg_dur - aud_dur - 5.0)
                except Exception:
                    pass

                stream_v = ffmpeg.input(video_path, ss=bg_ss)
                stream_a = ffmpeg.input(audio_path)
                video = stream_v.video
                audio = stream_a.audio
                video = video.filter('scale', 1920, 1080)
            else:
                # Shorts Stories (<=150 words): Center crop to 9:16 Vertical (1080x1920)
                # Random inner segment from long background asset
                import random
                bg_ss = 0.0
                try:
                    probe_bg = ffmpeg.probe(video_path)
                    probe_aud = ffmpeg.probe(audio_path)
                    bg_dur = float(probe_bg.get('format', {}).get('duration', 0))
                    aud_dur = float(probe_aud.get('format', {}).get('duration', 10.0))
                    if bg_dur > aud_dur + 10.0:
                        bg_ss = random.uniform(5.0, bg_dur - aud_dur - 5.0)
                except Exception:
                    pass

                crop_w_norm = (9.0 / 16.0) / aspect_ratio
                crop_x_norm = 0.5 - (crop_w_norm / 2.0)

                stream_v = ffmpeg.input(video_path, ss=bg_ss)
                stream_a = ffmpeg.input(audio_path)
                video = stream_v.video
                audio = stream_a.audio
                video = video.filter('crop', f"in_w*{crop_w_norm}", "in_h", f"in_w*{crop_x_norm}", 0)
                video = video.filter('scale', 1080, 1920)
            
            # Burn in subtitles
            if use_ass:
                escaped_ass_filename = ass_filename.replace('\\', '/').replace(':', '\\:')
                video = video.filter('ass', escaped_ass_filename)
            else:
                escaped_srt_filename = "captions.srt".replace('\\', '/').replace(':', '\\:')
                video = video.filter('subtitles', escaped_srt_filename, force_style='FontSize=24,PrimaryColour=&H00FFFFFF')

            # Compile output command
            # For stories, we specify shortest=None to truncate background video to narration audio length
            output_opts = {}
            if is_story:
                output_opts["shortest"] = None

            args_amf = (
                ffmpeg
                .output(video, audio, output_filename, vcodec='h264_amf', acodec='aac', **output_opts)
                .overwrite_output()
                .compile()
            )
            
            logger.info(f"Running AMF render command: {' '.join(args_amf)}", extra={"trace_id": job.trace_id})
            try:
                subprocess.run(args_amf, cwd=temp_dir, check=True, capture_output=True)
                logger.info("Successfully rendered video using h264_amf hardware encoder", extra={"trace_id": job.trace_id})
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                stderr_msg = e.stderr.decode('utf8') if hasattr(e, 'stderr') and e.stderr else str(e)
                logger.warning(
                    f"h264_amf hardware encoder failed: {stderr_msg}. Falling back to libx264 CPU encoder.",
                    extra={"trace_id": job.trace_id}
                )

                # CPU fallback
                args_cpu = (
                    ffmpeg
                    .output(video, audio, output_filename, vcodec='libx264', acodec='aac', pix_fmt='yuv420p', **output_opts)
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
                upload_file("autonomous-media-renders", clip.storage_key, output_path)
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
