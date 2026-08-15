import os
import io
from minio import Minio
from autonomous_media.config import settings

def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False
    )

def ensure_bucket(bucket_name: str) -> None:
    client = get_minio_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

def upload_file(bucket_name: str, object_name: str, file_path: str, max_retries: int = 3) -> None:
    client = get_minio_client()
    ensure_bucket(bucket_name)
    last_err = None
    for attempt in range(max_retries):
        try:
            client.fput_object(bucket_name, object_name, file_path)
            return
        except Exception as e:
            last_err = e
            import time
            time.sleep(1.0 * (attempt + 1))
    raise last_err

def download_file(bucket_name: str, object_name: str, file_path: str, max_retries: int = 3) -> None:
    client = get_minio_client()
    last_err = None
    for attempt in range(max_retries):
        try:
            client.fget_object(bucket_name, object_name, file_path)
            return
        except Exception as e:
            last_err = e
            import time
            time.sleep(1.0 * (attempt + 1))
    raise last_err

def put_object_data(bucket_name: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    client = get_minio_client()
    ensure_bucket(bucket_name)
    data_stream = io.BytesIO(data)
    client.put_object(bucket_name, object_name, data_stream, len(data), content_type=content_type)

def get_object_data(bucket_name: str, object_name: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(bucket_name, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

def delete_object(bucket_name: str, object_name: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(bucket_name, object_name)
    except Exception:
        pass

def flush_used_raw_sources(session) -> dict:
    """
    Safely purges downloaded full-length raw source video files and raw WAV files
    from MinIO bucket 'autonomous-media-raw' once all derived clip rendering jobs
    have completed. Preserves all transcripts, candidate metadata, and rendered clips.
    """
    from autonomous_media.db.models import SourceVideo, ClipCandidate, Clip, Job
    from minio.deleteobjects import DeleteObject

    client = get_minio_client()
    bucket = "autonomous-media-raw"

    if not client.bucket_exists(bucket):
        return {"deleted_objects": 0, "freed_bytes": 0, "purged_videos": 0}

    # Find active rendering jobs
    active_jobs = session.query(Job).filter(Job.status.in_(["queued", "running"])).all()
    active_clip_ids = {j.payload.get("clip_id") for j in active_jobs if j.payload and j.payload.get("clip_id")}

    source_videos = session.query(SourceVideo).all()
    purged_videos = 0
    safe_prefixes = set()

    for sv in source_videos:
        cands = session.query(ClipCandidate).filter(ClipCandidate.source_video_id == sv.id).all()
        cand_ids = [c.id for c in cands]
        clips = session.query(Clip).filter(Clip.clip_candidate_id.in_(cand_ids)).all() if cand_ids else []
        clip_ids_str = {str(c.id) for c in clips}

        # If any clip derived from this video is actively in the rendering/queue pipeline, do not purge
        if clip_ids_str.intersection(active_clip_ids):
            continue

        safe_prefixes.add(str(sv.id))
        if sv.storage_key:
            sv.storage_key = None
            purged_videos += 1

    session.commit()

    # Gather objects to delete from MinIO
    raw_objs = list(client.list_objects(bucket, recursive=True))
    to_delete = []
    freed_bytes = 0

    for o in raw_objs:
        # Match either safe source video ID or orphaned raw files
        is_safe = any(vid_id in o.object_name for vid_id in safe_prefixes)
        # Also clean up unreferenced orphan files in raw/
        is_orphan = not any(str(sv.id) in o.object_name for sv in source_videos)
        
        if is_safe or is_orphan:
            to_delete.append(DeleteObject(o.object_name))
            freed_bytes += (o.size or 0)

    if to_delete:
        errors = list(client.remove_objects(bucket, to_delete))
        if errors:
            import logging
            logger = logging.getLogger("storage")
            for err in errors:
                logger.warning(f"Error removing raw object {err.name}: {err.message}")

    return {
        "deleted_objects": len(to_delete),
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "purged_videos": purged_videos
    }

def purge_aged_assets(session, days_old: int = 7) -> dict:
    """
    Safely purges videos, clips, transcripts, and job history older than `days_old`
    across MinIO buckets ('autonomous-media-renders', 'autonomous-media-transcripts',
    'autonomous-media-raw') and local exports, EXCLUDING all background video assets
    ('background_assets' / backgrounds/*) used for Reddit story video backdrops.
    """
    from datetime import datetime, timezone, timedelta
    from autonomous_media.db.models import Clip, InventoryItem, AnalyticsSnapshot, Job, SourcePost, BackgroundAsset, Transcript, SourceVideo
    from minio.deleteobjects import DeleteObject
    import os

    client = get_minio_client()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_old)

    # 1. Resolve protected background assets
    bg_assets = session.query(BackgroundAsset).all()
    protected_keys = {b.storage_key for b in bg_assets if b.storage_key}
    protected_keys.add("Minecraft Parkour")

    def is_protected(obj_name: str) -> bool:
        if obj_name in protected_keys:
            return True
        if obj_name.startswith("backgrounds/"):
            return True
        return False

    total_deleted_objects = 0
    total_freed_bytes = 0

    # 2. Purge from MinIO buckets
    buckets_to_clean = ["autonomous-media-renders", "autonomous-media-transcripts", "autonomous-media-raw"]
    for b in buckets_to_clean:
        if not client.bucket_exists(b):
            continue
        objs = list(client.list_objects(b, recursive=True))
        to_delete = []
        for o in objs:
            if is_protected(o.object_name):
                continue
            if o.last_modified and o.last_modified < cutoff:
                to_delete.append(DeleteObject(o.object_name))
                total_freed_bytes += (o.size or 0)
        
        if to_delete:
            errors = list(client.remove_objects(b, to_delete))
            total_deleted_objects += len(to_delete)

    # 3. Purge from local exports directory
    export_dir = os.path.join(os.getcwd(), "exports")
    local_files_deleted = 0
    if os.path.exists(export_dir):
        for f in os.listdir(export_dir):
            fp = os.path.join(export_dir, f)
            if os.path.isfile(fp):
                mtime = datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc)
                if mtime < cutoff:
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        local_files_deleted += 1
                        total_freed_bytes += sz
                    except Exception:
                        pass

    # 4. Clean database rows older than cutoff
    # A. Old Clips and their dependents
    old_clips = session.query(Clip).filter(Clip.created_at < cutoff).all()
    old_clip_ids = [c.id for c in old_clips]
    purged_clips_count = len(old_clip_ids)

    if old_clip_ids:
        # Delete dependent AnalyticsSnapshots and InventoryItems
        inv_items = session.query(InventoryItem).filter(InventoryItem.clip_id.in_(old_clip_ids)).all()
        inv_ids = [inv.id for inv in inv_items]
        if inv_ids:
            session.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.inventory_item_id.in_(inv_ids)).delete(synchronize_session=False)
            session.query(InventoryItem).filter(InventoryItem.id.in_(inv_ids)).delete(synchronize_session=False)

        session.query(Clip).filter(Clip.id.in_(old_clip_ids)).delete(synchronize_session=False)

    # B. Old Jobs
    old_jobs_count = session.query(Job).filter(Job.created_at < cutoff).delete(synchronize_session=False)

    # C. Old Transcripts
    session.query(Transcript).filter(Transcript.created_at < cutoff).delete(synchronize_session=False)

    session.commit()

    return {
        "deleted_objects": total_deleted_objects,
        "local_files_deleted": local_files_deleted,
        "freed_bytes": total_freed_bytes,
        "freed_mb": round(total_freed_bytes / (1024 * 1024), 2),
        "freed_gb": round(total_freed_bytes / (1024 * 1024 * 1024), 2),
        "purged_clips": purged_clips_count,
        "purged_jobs": old_jobs_count,
        "cutoff_date": cutoff.isoformat()
    }

def ensure_all_buckets() -> None:
    buckets = [
        "autonomous-media-raw",
        "autonomous-media-transcripts",
        "autonomous-media-renders",
        "autonomous-media-branding"
    ]
    for bucket in buckets:
        ensure_bucket(bucket)

