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
