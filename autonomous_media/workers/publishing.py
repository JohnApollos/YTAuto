import os
import json
import tempfile
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, InventoryItem, Clip, ClipCandidate, SourceVideo, Channel
from autonomous_media.storage import download_file
from autonomous_media.rights.gate import RightsGate
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.runtime.manager import stage_manager, InferenceRequest
from autonomous_media.exceptions import StageUnrecoverableError, RightsBlockedError, QuotaExceededError

logger = get_logger("workers.publishing")

class PublishingWorker(Worker):
    job_type = 'publishing'

    def process(self, session: Session, job: Job) -> JobResult:
        inventory_item_id = job.payload.get("inventory_item_id")
        if not inventory_item_id:
            raise StageUnrecoverableError("Missing inventory_item_id in job payload")

        if isinstance(inventory_item_id, str):
            try:
                inventory_item_id = uuid.UUID(inventory_item_id)
            except ValueError:
                raise StageUnrecoverableError(f"Invalid inventory_item_id format: {inventory_item_id}")

        inventory_item = session.query(InventoryItem).filter(InventoryItem.id == inventory_item_id).first()
        if not inventory_item:
            raise StageUnrecoverableError(f"InventoryItem {inventory_item_id} not found")

        clip = session.query(Clip).filter(Clip.id == inventory_item.clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {inventory_item.clip_id} not found")

        clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
        if not clip_candidate:
            raise StageUnrecoverableError(f"ClipCandidate {clip.clip_candidate_id} not found")

        source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
        if not source_video:
            raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

        channel = session.query(Channel).filter(Channel.id == clip.channel_id).first()
        if not channel:
            raise StageUnrecoverableError(f"Channel {clip.channel_id} not found")

        # 1. Rights check via RightsGate (spec §11.4)
        rights_gate = RightsGate(self.session_maker)
        if not rights_gate.is_cleared(source_video.content_source_id):
            raise RightsBlockedError(
                f"Publishing blocked: Content source {source_video.content_source_id} rights status is not cleared"
            )

        logger.info(
            f"Starting publishing stage for InventoryItem {inventory_item_id} (Clip {clip.id})",
            extra={"trace_id": job.trace_id}
        )

        # 2. Get the transcript text for the clip window
        from autonomous_media.db.models import Transcript
        transcript = session.query(Transcript).filter(Transcript.source_video_id == source_video.id).first()
        if not transcript:
            raise StageUnrecoverableError(f"Transcript not found for video {source_video.id}")

        try:
            transcript_bytes = get_object_data_helper(transcript.storage_key)
            words = json.loads(transcript_bytes.decode("utf-8"))
        except Exception as e:
            # Fallback to clip candidate title or description if transcript fetch fails
            logger.warning(f"Could not load transcript for metadata generation: {e}", extra={"trace_id": job.trace_id})
            words = []

        clip_words = [w for w in words if w["start_ms"] >= clip_candidate.start_ms and w["end_ms"] <= clip_candidate.end_ms]
        source_video_title = source_video.title or "Podcast Clip"
        candidate_text = " ".join(w["word"] for w in clip_words) if clip_words else source_video_title

        # 3. Generate Title and Description dynamically using StageModelManager
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        
        # A. Title generation
        title_prompt_path = os.path.join(prompts_dir, "title_v1.txt")
        try:
            with open(title_prompt_path, "r", encoding="utf-8") as f:
                title_template = f.read()
            recent_titles_str = ", ".join(channel.branding.get("recent_titles", ["Awesome short clip"]))
            title_prompt = (
                title_template
                .replace("{recent_titles}", recent_titles_str)
                .replace("{candidate_text}", candidate_text)
            )
            title_res = stage_manager.run_stage("title", InferenceRequest(prompt=title_prompt))
            video_title = title_res.text.strip().replace('"', '')[:95] # YouTube max title is 100 chars
        except Exception as e:
            logger.warning(f"Title generation failed: {e}. Using fallback title.", extra={"trace_id": job.trace_id})
            video_title = f"Clip from: {source_video_title[:60]}"

        # B. Description generation
        desc_prompt_path = os.path.join(prompts_dir, "description_v1.txt")
        try:
            with open(desc_prompt_path, "r", encoding="utf-8") as f:
                desc_template = f.read()
            desc_prompt = desc_template.replace("{candidate_text}", candidate_text)
            desc_res = stage_manager.run_stage("description", InferenceRequest(prompt=desc_prompt))
            desc_data = json.loads(desc_res.text)
            
            desc_text = desc_data.get("description", "An amazing short clip.")
            hashtags = " ".join(desc_data.get("hashtags", ["#shorts", "#podcast"]))
            video_description = f"{desc_text}\n\n{hashtags}"
        except Exception as e:
            logger.warning(f"Description generation failed: {e}. Using fallback description.", extra={"trace_id": job.trace_id})
            video_description = f"Clip extracted from {source_video.url}\n#shorts #podcast"

        # 4. Fetch the rendered video clip file from MinIO
        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = f"{clip.id}.mp4"
            video_path = os.path.join(temp_dir, video_filename)

            try:
                download_file("autonomous-media-raw", clip.storage_key, video_path)
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to download rendered clip from MinIO: {e}")

            if not os.path.exists(video_path):
                raise StageUnrecoverableError(f"Rendered clip file not found at {video_path}")

            # 5. Check remaining quota before upload (spec §5.1)
            project_id = channel.project_id or "default_project"
            from autonomous_media.quota import quota_tracker
            if not quota_tracker.has_quota(project_id, 1600):
                raise QuotaExceededError(
                    f"Project {project_id} has insufficient quota remaining for upload (requires 1600)"
                )

            # 6. Retrieve OAuth credentials from Channel branding or environment
            oauth_data = channel.branding.get("oauth_credentials") or {}
            if not oauth_data and os.environ.get("YOUTUBE_OAUTH_TOKEN"):
                oauth_data = {"token": os.environ.get("YOUTUBE_OAUTH_TOKEN")}

            if not oauth_data:
                # Only allow mock flow explicitly in test environments.
                # In all other cases, raise an unrecoverable error so misconfigured
                # channels fail loudly rather than generating phantom mock uploads.
                logger.info("No credentials found, checking for mock flow", extra={"trace_id": job.trace_id})
                if os.environ.get("YOUTUBE_API_ENV") == "test":
                    youtube_video_id = f"mock_{uuid.uuid4().hex[:10]}"
                    logger.info(f"Mock publishing successful. Video ID: {youtube_video_id}", extra={"trace_id": job.trace_id})
                else:
                    raise StageUnrecoverableError("OAuth credentials not configured for channel")
            else:
                # Run real YouTube upload
                from googleapiclient.errors import HttpError
                try:
                    from google.oauth2.credentials import Credentials
                    from googleapiclient.discovery import build
                    from googleapiclient.http import MediaFileUpload

                    creds = Credentials(
                        token=oauth_data.get("token"),
                        refresh_token=oauth_data.get("refresh_token"),
                        token_uri=oauth_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                        client_id=oauth_data.get("client_id"),
                        client_secret=oauth_data.get("client_secret")
                    )
                    youtube = build("youtube", "v3", credentials=creds)

                    body = {
                        'snippet': {
                            'title': video_title,
                            'description': video_description,
                            'categoryId': '22' # People & Blogs default
                        },
                        'status': {
                            'privacyStatus': 'public',
                            'selfDeclaredMadeForKids': False
                        }
                    }

                    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
                    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
                    
                    response = request.execute()
                    youtube_video_id = response.get("id")
                    if not youtube_video_id:
                        raise StageUnrecoverableError("YouTube upload succeeded but no video ID was returned")
                except HttpError as err:
                    # Check for quota errors
                    if err.resp.status in [403, 429] and "quota" in str(err).lower():
                        raise QuotaExceededError(f"YouTube upload failed due to quota limit: {err}")
                    raise StageUnrecoverableError(f"YouTube API upload failed: {err}")
                except Exception as e:
                    raise StageUnrecoverableError(f"Failed to execute YouTube upload: {e}")

            # Consume quota
            quota_tracker.consume_quota(project_id, 1600)

            # 7. Save publishing status to database
            inventory_item.status = "published"
            inventory_item.published_at = datetime.now(timezone.utc)
            inventory_item.external_video_id = youtube_video_id
            clip.status = "published"
            session.commit()
            


            # 7. Emit PUBLISH_COMPLETED event
            emit_event(
                event_type="publish.completed",
                trace_id=job.trace_id,
                payload={
                    "inventory_item_id": str(inventory_item_id),
                    "external_video_id": youtube_video_id,
                    "title": video_title
                }
            )

            # 8. Enqueue analytics job (scheduled in 24 hours / 86400 seconds)
            next_job = Job(
                type="analytics",
                payload={"inventory_item_id": str(inventory_item_id)},
                trace_id=job.trace_id,
                channel_id=job.channel_id,
                priority=job.priority,
                attempts=0,
                max_attempts=3
            )
            # In production scheduler, this would be picked up when datetime.now() >= scheduled_at
            # We can save it as scheduled job by setting started_at/created_at or metadata if needed.
            session.add(next_job)
            session.commit()

            logger.info(
                f"Successfully published Clip {clip.id} to YouTube as video {youtube_video_id}",
                extra={"trace_id": job.trace_id}
            )

        return JobResult()

def get_object_data_helper(key: str) -> bytes:
    # Helper to support mock fetching of object data
    from autonomous_media.storage import get_object_data
    return get_object_data("autonomous-media-raw", key)
