from typing import Optional
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


@router.get("/resources")
def get_system_resources():
    from autonomous_media.profiling import HardwareTelemetrySampler, stage_profiler
    snapshot = HardwareTelemetrySampler.get_system_snapshot()
    snapshot["recent_profiles"] = stage_profiler.get_recent_profiles(limit=10)
    snapshot["stage_averages"] = stage_profiler.get_stage_averages()
    return snapshot


@router.get("/coexistence/decision")
def get_coexistence_decision(db: Session = Depends(get_db)):
    """
    Direct actionable governor endpoint for OpenWorker and external agent systems.
    Evaluates live hardware headroom (RAM, VRAM, CPU) and YTAuto pipeline execution state
    to return a definitive operating mode and concurrency limits.
    """
    from autonomous_media.profiling import HardwareTelemetrySampler
    from autonomous_media.db.models import Job

    snapshot = HardwareTelemetrySampler.get_system_snapshot()
    ram = snapshot["ram"]
    gpu = snapshot["gpu"]

    # Check active YTAuto jobs
    active_jobs = db.query(Job).filter(Job.status.in_(["running"])).all()
    running_types = {j.type for j in active_jobs}

    is_rendering = "rendering" in running_types
    is_scoring = "intelligence" in running_types or "transcription" in running_types

    # 1. Critical Contention / High Memory Pressure: Protect YTAuto
    if ram["free_gb"] < 1.5 or is_rendering or gpu["free_vram_gb"] < 1.8:
        return {
            "allowed": False,
            "mode": "protected",
            "reason": f"YTAuto active workload: {'rendering' if is_rendering else 'high memory pressure'} (RAM free: {ram['free_gb']} GB, VRAM free: {gpu['free_vram_gb']} GB)",
            "retry_after_s": 30,
            "recommended_model": None,
            "max_concurrent_agents": 0,
            "allow_browser_automation": False
        }

    # 2. Light Load (e.g. scoring or moderate headroom)
    if is_scoring or ram["free_gb"] < 4.0 or gpu["free_vram_gb"] < 3.5:
        return {
            "allowed": True,
            "mode": "light",
            "reason": f"YTAuto active in light stage or moderate headroom (RAM free: {ram['free_gb']} GB)",
            "retry_after_s": 15,
            "recommended_model": "qwen2.5:3b-instruct",
            "max_concurrent_agents": 1,
            "allow_browser_automation": False
        }

    # 3. Optimal Headroom: YTAuto idle / polling
    return {
        "allowed": True,
        "mode": "full",
        "reason": f"System resources optimal; YTAuto idle (RAM free: {ram['free_gb']} GB, VRAM free: {gpu['free_vram_gb']} GB)",
        "retry_after_s": 10,
        "recommended_model": "qwen2.5:7b-instruct",
        "max_concurrent_agents": 4,
        "allow_browser_automation": True
    }



@router.post("/storage/flush-raw")
def flush_raw_storage(db: Session = Depends(get_db)):
    from autonomous_media.storage import flush_used_raw_sources
    result = flush_used_raw_sources(db)
    return result


@router.post("/storage/purge-aged")
def purge_aged_storage(days: int = 7, db: Session = Depends(get_db)):
    from autonomous_media.storage import purge_aged_assets
    result = purge_aged_assets(db, days_old=days)
    return result




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
    allowed_chat_ids: Optional[list[str]] = None


class TelegramPreferencesRequest(BaseModel):
    enabled_categories: Optional[dict[str, bool]] = None
    min_severity: Optional[dict[str, str]] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    dedupe_window_seconds: Optional[int] = None
    quota_warning_threshold: Optional[int] = None
    quota_critical_threshold: Optional[int] = None


@router.get("/telegram")
def get_telegram_config(db: Session = Depends(get_db)):
    from autonomous_media.services.telegram import telegram_notifier
    token = telegram_notifier.bot_token
    masked_token = f"{token[:6]}...{token[-4:]}" if token and len(token) > 10 else None
    
    return {
        "configured": telegram_notifier.is_configured(),
        "connection_status": telegram_notifier.get_connection_status(),
        "bot_token_masked": masked_token,
        "chat_id": telegram_notifier.chat_id,
        "allowed_chat_ids": telegram_notifier.allowed_chat_ids,
        "preferences": {
            "enabled_categories": telegram_notifier.preferences.enabled_categories,
            "min_severity": telegram_notifier.preferences.min_severity
        },
        "quiet_hours": {
            "enabled": telegram_notifier.quiet_hours_enabled,
            "start": telegram_notifier.quiet_hours_start,
            "end": telegram_notifier.quiet_hours_end,
            "timezone": telegram_notifier.timezone
        },
        "thresholds": {
            "dedupe_window_seconds": telegram_notifier.dedupe_window_seconds,
            "quota_warning_threshold": telegram_notifier.quota_warning_threshold,
            "quota_critical_threshold": telegram_notifier.quota_critical_threshold
        },
        "last_successful_delivery": telegram_notifier.last_successful_delivery.isoformat() if telegram_notifier.last_successful_delivery else None
    }


@router.post("/telegram")
def save_telegram_config(body: TelegramConfigRequest):
    from autonomous_media.services.telegram import telegram_notifier
    telegram_notifier.set_credentials(body.bot_token, body.chat_id, body.allowed_chat_ids)
    return {
        "status": "success",
        "configured": telegram_notifier.is_configured(),
        "connection_status": telegram_notifier.get_connection_status()
    }


@router.post("/telegram/preferences")
def save_telegram_preferences(body: TelegramPreferencesRequest, db: Session = Depends(get_db)):
    from autonomous_media.services.telegram import telegram_notifier
    from autonomous_media.db.models import TelegramConfig
    
    if body.enabled_categories is not None:
        telegram_notifier.preferences.enabled_categories.update(body.enabled_categories)
    if body.min_severity is not None:
        telegram_notifier.preferences.min_severity.update(body.min_severity)
    if body.quiet_hours_enabled is not None:
        telegram_notifier.quiet_hours_enabled = body.quiet_hours_enabled
    if body.quiet_hours_start is not None:
        telegram_notifier.quiet_hours_start = body.quiet_hours_start
    if body.quiet_hours_end is not None:
        telegram_notifier.quiet_hours_end = body.quiet_hours_end
    if body.timezone is not None:
        telegram_notifier.timezone = body.timezone
    if body.dedupe_window_seconds is not None:
        telegram_notifier.dedupe_window_seconds = body.dedupe_window_seconds
        telegram_notifier.dedupe_filter.window_seconds = body.dedupe_window_seconds
    if body.quota_warning_threshold is not None:
        telegram_notifier.quota_warning_threshold = body.quota_warning_threshold
    if body.quota_critical_threshold is not None:
        telegram_notifier.quota_critical_threshold = body.quota_critical_threshold

    # Persist to DB
    cfg = db.query(TelegramConfig).first()
    if not cfg:
        cfg = TelegramConfig()
        db.add(cfg)
    cfg.categories = {
        "enabled_categories": telegram_notifier.preferences.enabled_categories,
        "min_severity": telegram_notifier.preferences.min_severity
    }
    cfg.quiet_hours_enabled = telegram_notifier.quiet_hours_enabled
    cfg.quiet_hours_start = telegram_notifier.quiet_hours_start
    cfg.quiet_hours_end = telegram_notifier.quiet_hours_end
    cfg.timezone = telegram_notifier.timezone
    cfg.dedupe_window_seconds = telegram_notifier.dedupe_window_seconds
    cfg.quota_warning_threshold = telegram_notifier.quota_warning_threshold
    cfg.quota_critical_threshold = telegram_notifier.quota_critical_threshold
    db.commit()

    return {"status": "success", "message": "Telegram preferences saved"}


@router.post("/telegram/test")
def test_telegram_notification(body: TelegramConfigRequest):
    from autonomous_media.services.telegram import telegram_notifier
    success, message = telegram_notifier.send_test_notification(body.bot_token, body.chat_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Telegram test failed: {message}")
    return {"status": "sent", "success": True, "message": message}


@router.get("/telegram/logs")
def get_telegram_delivery_logs(limit: int = 20, db: Session = Depends(get_db)):
    from autonomous_media.db.models import TelegramDeliveryLog
    logs = db.query(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(limit).all()
    return {
        "logs": [
            {
                "id": str(l.id),
                "notification_id": l.notification_id,
                "event_type": l.event_type,
                "severity": l.severity,
                "status": l.status,
                "error": l.error,
                "sent_at": l.sent_at.isoformat() if l.sent_at else None,
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in logs
        ]
    }


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
