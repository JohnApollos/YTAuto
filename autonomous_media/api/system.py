from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health")
def get_health(db: Session = Depends(get_db)):
    from sqlalchemy import text
    from autonomous_media.storage import get_minio_client
    import redis
    from autonomous_media.config import settings

    db_health = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_health = f"error: {e}"

    redis_health = "ok"
    try:
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=2.0)
        r.ping()
    except Exception as e:
        redis_health = f"error: {e}"

    minio_health = "ok"
    try:
        client = get_minio_client()
        client.list_buckets()
    except Exception as e:
        minio_health = f"error: {e}"

    status = "ok"
    if "error" in db_health or "error" in redis_health or "error" in minio_health:
        status = "degraded"

    return {
        "status": status,
        "db": db_health,
        "redis": redis_health,
        "minio": minio_health
    }


@router.get("/models")
def get_models():
    from autonomous_media.runtime.manager import stage_manager
    health = stage_manager.health_check_all()
    models_res = {}
    for stage, h in health.items():
        models_res[stage] = {
            "healthy": h.healthy,
            "model_name": h.model_name,
            "message": h.message
        }
    return {"models": models_res}


@router.get("/quota")
def get_quota(db: Session = Depends(get_db)):
    from autonomous_media.quota import quota_tracker
    from autonomous_media.db.models import Channel
    
    channels = db.query(Channel).all()
    project_ids = {c.project_id for c in channels if c.project_id}
    
    if not project_ids:
        project_ids.add("default_project")
        
    quotas = []
    for pid in project_ids:
        try:
            remaining = quota_tracker.get_remaining_quota(pid)
            quotas.append({"project_id": pid, "remaining": remaining})
        except Exception as e:
            quotas.append({"project_id": pid, "remaining": 0, "error": str(e)})
            
    return {"quotas": quotas}


from pydantic import BaseModel
from fastapi import HTTPException

class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


@router.get("/telegram")
def get_telegram_config():
    from autonomous_media.services.telegram_bot import telegram_notifier
    return {
        "configured": telegram_notifier.is_configured(),
        "bot_token_set": bool(telegram_notifier.bot_token),
        "chat_id_set": bool(telegram_notifier.chat_id),
        "chat_id": telegram_notifier.chat_id if telegram_notifier.chat_id else None,
    }


@router.post("/telegram")
def save_telegram_config(body: TelegramConfigRequest):
    from autonomous_media.services.telegram_bot import telegram_notifier
    telegram_notifier.set_credentials(body.bot_token, body.chat_id)
    return {
        "status": "success",
        "configured": telegram_notifier.is_configured()
    }


@router.post("/telegram/test")
def test_telegram_notification(body: TelegramConfigRequest):
    from autonomous_media.services.telegram_bot import telegram_notifier
    telegram_notifier.set_credentials(body.bot_token, body.chat_id)
    success = telegram_notifier.send_message(
        "🚀 <b>YTAuto Telegram Notification Test!</b>\n\nYour Telegram Bot is connected and ready to notify you of all system jobs & video renders!"
    )
    return {"status": "sent", "success": success}


@router.post("/re-export")
def re_export_all_published_clips(db: Session = Depends(get_db)):
    """Re-exports all published clips from MinIO to C:\\dev\\YTAuto\\exports with unique clip ID filenames."""
    import os
    import shutil
    import tempfile
    from autonomous_media.db.models import Clip, ClipCandidate, SourceVideo, SourcePost
    from autonomous_media.storage import download_file

    export_root = os.path.join(os.getcwd(), "exports")
    os.makedirs(export_root, exist_ok=True)

    published_clips = db.query(Clip).all()
    exported_count = 0

    for clip in published_clips:
        if not clip.storage_key:
            continue

        clip_short_id = str(clip.id)[:8]
        if clip.source_post_id:
            source_post = db.query(SourcePost).filter(SourcePost.id == clip.source_post_id).first()
            title = source_post.title if source_post else f"Story_{clip_short_id}"
            from autonomous_media.db.models import Transcript
            transcript = db.query(Transcript).filter(Transcript.source_post_id == clip.source_post_id).first()
            word_count = transcript.word_count if transcript else 0
            if word_count > 150:
                export_subdir = os.path.join(export_root, "reddit_videos", "long_form")
            else:
                export_subdir = os.path.join(export_root, "reddit_videos", "shorts")
        else:
            candidate = db.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
            source_video = db.query(SourceVideo).filter(SourceVideo.id == candidate.source_video_id).first() if candidate else None
            title = source_video.title if source_video else "Podcast Clips"
            from autonomous_media.workers.publishing import sanitize_filename
            folder_name = sanitize_filename(title)
            export_subdir = os.path.join(export_root, "youtube_clips", folder_name)

        os.makedirs(export_subdir, exist_ok=True)
        from autonomous_media.workers.publishing import sanitize_filename
        clean_title = sanitize_filename(title)
        filename_base = f"{clean_title}_{clip_short_id}"
        out_video_path = os.path.join(export_subdir, f"{filename_base}.mp4")
        out_txt_path = os.path.join(export_subdir, f"{filename_base}.txt")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_video = os.path.join(tmp_dir, "temp.mp4")
            try:
                download_file("autonomous-media-renders", clip.storage_key, tmp_video)
            except Exception:
                try:
                    download_file("autonomous-media-raw", clip.storage_key, tmp_video)
                except Exception:
                    continue

            if os.path.exists(tmp_video):
                shutil.copy2(tmp_video, out_video_path)
                # Write corresponding metadata .txt file
                description_text = ""
                if clip.source_post_id and source_post:
                    description_text = source_post.body_text or ""
                elif source_video:
                    description_text = f"Clip extracted from {source_video.title or 'Podcast'}\n#shorts #podcast"
                
                with open(out_txt_path, "w", encoding="utf-8") as tf:
                    tf.write(f"Title: {title}\n\nDescription:\n{description_text}\n")
                
                exported_count += 1

    return {"status": "success", "re_exported_clips": exported_count}


@router.post("/jobs/flush-stuck")
def flush_stuck_running_jobs(db: Session = Depends(get_db)):
    """Resets all 'running' or stuck jobs back to 'queued' state so the scheduler resumes processing."""
    from autonomous_media.db.models import Job
    stuck_jobs = db.query(Job).filter(Job.status == "running").all()
    flushed_count = 0
    for j in stuck_jobs:
        j.status = "queued"
        j.error = "Manually flushed from UI"
        flushed_count += 1
    db.commit()
    return {"status": "success", "flushed_jobs": flushed_count}
