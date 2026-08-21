import os
import json
import tempfile
import uuid
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, InventoryItem, Clip, ClipCandidate, SourceVideo, Channel, SourcePost, Transcript
from autonomous_media.storage import download_file
from autonomous_media.rights.gate import RightsGate
from autonomous_media.logging import get_logger, emit_event
from autonomous_media.runtime.manager import stage_manager, InferenceRequest
from autonomous_media.exceptions import StageUnrecoverableError, RightsBlockedError

logger = get_logger("workers.publishing")

def sanitize_filename(name: str, max_length: int = 45) -> str:
    """Sanitize string for Windows and Unix file/directory name compatibility and cap length to avoid MAX_PATH crashes."""
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return sanitized[:max_length].strip()


def format_reddit_video_metadata(source_post, clip_dur: float) -> tuple[str, str]:
    """Generates an engaging, high-CTR YouTube title (strictly < 100 chars) and rich description with viral hashtags for Reddit Stories."""
    raw_title = (source_post.title or "Unbelievable Reddit Story").strip()
    
    # 1. Clean Reddit prefixes e.g. [AITA], (UPDATE), r/AITA -
    clean_title = re.sub(r'\[.*?\]|\(.*?\)|^r/\w+\s*[-:]\s*', '', raw_title).strip()
    clean_title = re.sub(r'\bAITA\b', 'Am I The Jerk', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\bWIBTA\b', 'Would I Be The Jerk', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'\bTIFU\b', 'Today I Messed Up', clean_title, flags=re.IGNORECASE)
    
    is_short = clip_dur <= 60
    tag = "#Shorts" if is_short else "#RedditStories"
    emoji = "🤔" if "?" in clean_title else "😳"
    
    # YouTube has a strict 100-character ceiling for video titles.
    # Allocate budget for title + emoji + hashtag
    max_body_len = 100 - len(tag) - len(emoji) - 3  # ~83 chars
    if len(clean_title) > max_body_len:
        clean_title = clean_title[:max_body_len - 3].rsplit(' ', 1)[0] + "..."

    video_title = f"{clean_title} {emoji} {tag}".strip()
    
    # Hard clamp to guarantee len <= 100
    if len(video_title) > 100:
        video_title = video_title[:95] + "..."

    # 2. Format description with hook preview, attribution, call to action, and viral hashtags
    subreddit = getattr(source_post, "subreddit", None) or "RedditStories"
    author = getattr(source_post, "author", None) or "Anonymous"
    body = (source_post.body_text or "").strip()
    preview = body[:280].rsplit(' ', 1)[0] + "..." if len(body) > 280 else body
    hashtags = "#redditstories #reddit #storytime #askreddit #aita #redditreadings #shorts #viral #story" if is_short else "#redditstories #reddit #storytime #askreddit #aita #redditreadings #viral #story"
    
    video_description = (
        f"{raw_title}\n\n"
        f"📖 Story Preview:\n{preview}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Subreddit: r/{subreddit}\n"
        f"👤 Original Poster: u/{author}\n\n"
        f"👉 Subscribe for daily Reddit stories, relationship drama, and AITA confessions!\n\n"
        f"{hashtags}"
    )
    return video_title, video_description


class PublishingWorker(Worker):
    job_type = 'publishing'

    def process(self, session: Session, job: Job) -> JobResult:
        inventory_item_id = job.payload.get("inventory_item_id")
        if not inventory_item_id:
            raise StageUnrecoverableError("Missing inventory_item_id in job payload")

        inventory_item = session.query(InventoryItem).filter(InventoryItem.id == uuid.UUID(inventory_item_id) if isinstance(inventory_item_id, str) else inventory_item_id).first()
        if not inventory_item:
            raise StageUnrecoverableError(f"InventoryItem {inventory_item_id} not found")

        # Idempotency check: prevent duplicate publishing / re-exporting
        if inventory_item.status == "published":
            logger.info(
                f"InventoryItem {inventory_item_id} is already published — skipping duplicate export/upload",
                extra={"trace_id": job.trace_id}
            )
            return JobResult()

        clip = session.query(Clip).filter(Clip.id == inventory_item.clip_id).first()
        if not clip:
            raise StageUnrecoverableError(f"Clip {inventory_item.clip_id} not found")

        channel = session.query(Channel).filter(Channel.id == clip.channel_id).first()
        if not channel:
            raise StageUnrecoverableError(f"Channel {clip.channel_id} not found")

        is_story = clip.source_post_id is not None
        source_post = None
        source_video = None
        video_title = ""
        video_description = ""
        export_subdir = ""

        # Make sure target export folder exists deterministically relative to repository root
        project_root = Path(__file__).resolve().parents[2]
        export_root = os.path.join(project_root, "exports")
        os.makedirs(export_root, exist_ok=True)

        if not is_story:
            # YouTube/Podcast Clip Workflow
            clip_candidate = session.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
            if not clip_candidate:
                raise StageUnrecoverableError(f"ClipCandidate {clip.clip_candidate_id} not found")

            source_video = session.query(SourceVideo).filter(SourceVideo.id == clip_candidate.source_video_id).first()
            if not source_video:
                raise StageUnrecoverableError(f"SourceVideo {clip_candidate.source_video_id} not found")

            # Rights check via RightsGate
            rights_gate = RightsGate(self.session_maker)
            if not rights_gate.is_cleared(source_video.content_source_id):
                raise RightsBlockedError(
                    f"Publishing blocked: Content source {source_video.content_source_id} rights status is not cleared"
                )

            # Generate metadata
            transcript = session.query(Transcript).filter(Transcript.source_video_id == source_video.id).first()
            words = []
            if transcript:
                try:
                    from autonomous_media.storage import get_object_data
                    try:
                        transcript_bytes = get_object_data("autonomous-media-transcripts", transcript.storage_key)
                    except Exception:
                        transcript_bytes = get_object_data("autonomous-media-raw", transcript.storage_key)
                    words = json.loads(transcript_bytes.decode("utf-8"))
                except Exception as e:
                    logger.warning(f"Could not load transcript for metadata: {e}")

            clip_words = [w for w in words if w["start_ms"] >= clip_candidate.start_ms and w["end_ms"] <= clip_candidate.end_ms]
            candidate_text = " ".join(w["word"] for w in clip_words) if clip_words else (source_video.title or "Clip")

            # A. Title generation
            prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
            title_prompt_path = os.path.join(prompts_dir, "title_v1.txt")
            try:
                with open(title_prompt_path, "r", encoding="utf-8") as f:
                    title_template = f.read()
                recent_titles_str = ", ".join(channel.branding.get("recent_titles", ["Awesome short clip"]))
                title_prompt = title_template.replace("{recent_titles}", recent_titles_str).replace("{candidate_text}", candidate_text)
                title_res = stage_manager.run_stage("title", InferenceRequest(prompt=title_prompt))
                raw_t = title_res.text.strip().replace('"', '')
                if raw_t.startswith("{") or "hook_strength" in raw_t:
                    video_title = f"Clip from: {source_video.title or 'Podcast'}"
                else:
                    video_title = raw_t[:95]
            except Exception as e:
                video_title = f"Clip from: {source_video.title or 'Podcast'}"

            # B. Description generation
            desc_prompt_path = os.path.join(prompts_dir, "description_v1.txt")
            try:
                with open(desc_prompt_path, "r", encoding="utf-8") as f:
                    desc_template = f.read()
                desc_prompt = desc_template.replace("{candidate_text}", candidate_text)
                desc_res = stage_manager.run_stage("description", InferenceRequest(prompt=desc_prompt))
                desc_data = json.loads(desc_res.text) if desc_res.text.strip().startswith("{") else {}
                desc_text = desc_data.get("description", "An amazing short clip.") if isinstance(desc_data, dict) else "An amazing short clip."
                hashtags = " ".join(desc_data.get("hashtags", ["#shorts", "#podcast"])) if isinstance(desc_data, dict) else "#shorts #podcast"
                video_description = f"{desc_text}\n\n{hashtags}"
            except Exception as e:
                video_description = f"Clip extracted from {source_video.url or 'original video'}\n#shorts #podcast"

            # Directory: exports/youtube_clips/<source_video_title>/
            folder_name = sanitize_filename(source_video.title or "Podcast Clips")
            export_subdir = os.path.join(export_root, "youtube_clips", folder_name)
        else:
            # Reddit Stories Workflow
            source_post = session.query(SourcePost).filter(SourcePost.id == clip.source_post_id).first()
            if not source_post:
                raise StageUnrecoverableError(f"SourcePost {clip.source_post_id} not found")

            clip_dur = clip.duration_s if clip.duration_s else 0
            video_title, video_description = format_reddit_video_metadata(source_post, clip_dur)

            # Classification by actual clip duration in seconds (<=60s is Short, >60s is Long-Form)
            if clip_dur > 60:
                export_subdir = os.path.join(export_root, "reddit_videos", "long_form")
            else:
                export_subdir = os.path.join(export_root, "reddit_videos", "shorts")

        os.makedirs(export_subdir, exist_ok=True)
        clip_short_id = str(clip.id)[:8]
        sanitized_title = sanitize_filename(video_title or f"clip_{clip_short_id}")
        export_filename = f"{sanitized_title}_{clip_short_id}"
        export_video_path = os.path.join(export_subdir, f"{export_filename}.mp4")
        export_txt_path = os.path.join(export_subdir, f"{export_filename}.txt")

        # 4. Fetch the rendered video clip file from MinIO
        with tempfile.TemporaryDirectory() as temp_dir:
            video_filename = "rendered.mp4"
            temp_video_path = os.path.join(temp_dir, video_filename)

            try:
                download_file("autonomous-media-renders", clip.storage_key, temp_video_path)
            except Exception as e:
                try:
                    download_file("autonomous-media-raw", clip.storage_key, temp_video_path)
                except Exception:
                    raise StageUnrecoverableError(f"Failed to download rendered clip from MinIO: {e}")

            if not os.path.exists(temp_video_path):
                raise StageUnrecoverableError(f"Rendered clip file not found at {temp_video_path}")

            # Copy clip video and write metadata txt file
            try:
                shutil.copy2(temp_video_path, export_video_path)
                with open(export_txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Title: {video_title}\n\nDescription:\n{video_description}\n")
            except Exception as e:
                raise StageUnrecoverableError(f"Failed to write exported files to {export_subdir}: {e}")

        # 5. Save publishing status to database
        inventory_item.status = "published"
        inventory_item.published_at = datetime.now(timezone.utc)
        inventory_item.external_video_id = f"local_export_{uuid.uuid4().hex[:10]}"
        clip.status = "published"
        
        if source_post:
            source_post.status = "done"
        session.commit()

        # 6. Emit PUBLISH_COMPLETED event
        emit_event(
            event_type="publish.completed",
            trace_id=job.trace_id,
            payload={
                "inventory_item_id": str(inventory_item.id),
                "export_path": export_video_path,
                "title": video_title
            }
        )

        logger.info(
            f"Successfully exported clip locally to {export_video_path}",
            extra={"trace_id": job.trace_id}
        )

        return JobResult()
