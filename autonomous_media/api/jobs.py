import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import Job, SourceVideo, SourcePost, Clip, ClipCandidate, InventoryItem, ContentSource

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def resolve_job_target_title(db: Session, payload: Optional[dict], trace_id: Optional[str]) -> Optional[str]:
    """Resolves a human-friendly video/story title from job payload or trace_id."""
    if not payload:
        payload = {}

    # 1. Payload ID lookups
    for k in ["source_video_id", "clip_candidate_id", "clip_id", "source_post_id", "inventory_item_id"]:
        if k in payload and payload[k]:
            try:
                uid = uuid.UUID(str(payload[k]))
                if k == "source_video_id":
                    sv = db.query(SourceVideo).filter(SourceVideo.id == uid).first()
                    if sv and sv.title:
                        return sv.title
                elif k == "clip_candidate_id":
                    cc = db.query(ClipCandidate).filter(ClipCandidate.id == uid).first()
                    if cc:
                        sv = db.query(SourceVideo).filter(SourceVideo.id == cc.source_video_id).first()
                        if sv and sv.title:
                            return sv.title
                elif k == "clip_id":
                    c = db.query(Clip).filter(Clip.id == uid).first()
                    if c:
                        if c.source_post_id:
                            sp = db.query(SourcePost).filter(SourcePost.id == c.source_post_id).first()
                            if sp and sp.title:
                                return sp.title
                        elif c.clip_candidate_id:
                            cc = db.query(ClipCandidate).filter(ClipCandidate.id == c.clip_candidate_id).first()
                            if cc:
                                sv = db.query(SourceVideo).filter(SourceVideo.id == cc.source_video_id).first()
                                if sv and sv.title:
                                    return sv.title
                elif k == "source_post_id":
                    sp = db.query(SourcePost).filter(SourcePost.id == uid).first()
                    if sp and sp.title:
                        return sp.title
                elif k == "inventory_item_id":
                    inv = db.query(InventoryItem).filter(InventoryItem.id == uid).first()
                    if inv and inv.clip_id:
                        c = db.query(Clip).filter(Clip.id == inv.clip_id).first()
                        if c:
                            if c.source_post_id:
                                sp = db.query(SourcePost).filter(SourcePost.id == c.source_post_id).first()
                                if sp and sp.title:
                                    return sp.title
                            elif c.clip_candidate_id:
                                cc = db.query(ClipCandidate).filter(ClipCandidate.id == c.clip_candidate_id).first()
                                if cc:
                                    sv = db.query(SourceVideo).filter(SourceVideo.id == cc.source_video_id).first()
                                    if sv and sv.title:
                                        return sv.title
            except Exception:
                pass

    # 2. Trace ID Regex extraction
    if trace_id:
        match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', trace_id, re.I)
        if match:
            try:
                uid = uuid.UUID(match.group(0))
                sv = db.query(SourceVideo).filter(SourceVideo.id == uid).first()
                if sv and sv.title:
                    return sv.title
                cc = db.query(ClipCandidate).filter(ClipCandidate.id == uid).first()
                if cc:
                    sv = db.query(SourceVideo).filter(SourceVideo.id == cc.source_video_id).first()
                    if sv and sv.title:
                        return sv.title
                sp = db.query(SourcePost).filter(SourcePost.id == uid).first()
                if sp and sp.title:
                    return sp.title
                cs = db.query(ContentSource).filter(ContentSource.id == uid).first()
                if cs and cs.external_ref:
                    return f"Channel: {cs.external_ref}"
            except Exception:
                pass

    return None


@router.get("", response_model=dict)
@router.get("/", response_model=dict)
def list_jobs(
    status: Optional[str] = None,
    type: Optional[str] = None,
    channel_id: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status and status != "all":
        query = query.filter(Job.status == status)
    if type:
        query = query.filter(Job.type == type)
    if channel_id:
        try:
            query = query.filter(Job.channel_id == uuid.UUID(channel_id))
        except ValueError:
            pass

    query = query.order_by(Job.created_at.desc()).limit(limit)
    rows = query.all()

    jobs_list = []
    for j in rows:
        title = resolve_job_target_title(db, j.payload, j.trace_id)
        jobs_list.append({
            "id": str(j.id),
            "type": j.type,
            "status": j.status,
            "channel_id": str(j.channel_id) if j.channel_id else None,
            "trace_id": j.trace_id,
            "display_title": title,
            "attempts": j.attempts,
            "max_attempts": j.max_attempts,
            "error": j.error,
            "payload": j.payload,
            "created_at": (j.created_at.isoformat() + "Z") if j.created_at and not j.created_at.isoformat().endswith("Z") else (j.created_at.isoformat() if j.created_at else ""),
            "started_at": (j.started_at.isoformat() + "Z") if j.started_at and not j.started_at.isoformat().endswith("Z") else (j.started_at.isoformat() if j.started_at else None),
            "finished_at": (j.finished_at.isoformat() + "Z") if j.finished_at and not j.finished_at.isoformat().endswith("Z") else (j.finished_at.isoformat() if j.finished_at else None),
        })

    return {"jobs": jobs_list}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": str(job.id),
        "type": job.type,
        "status": job.status,
        "channel_id": str(job.channel_id) if job.channel_id else None,
        "trace_id": job.trace_id,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else "",
    }


@router.post("/{job_id}/retry")
def retry_job(job_id: str, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "queued"
    job.attempts = 0
    job.error = None
    db.commit()
    return {"id": str(job.id), "status": "queued"}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.status = "cancelled"
    db.commit()
    return {"id": str(job.id), "status": "cancelled"}
