import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import Clip, ClipCandidate, InventoryItem, Job

router = APIRouter(prefix="/clips", tags=["Clips"])


class ClipPatch(BaseModel):
    status: str  # "ready" (approve) or "qc_failed" (reject)


@router.get("/")
def list_clips(
    channel_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Clip)
    if channel_id:
        try:
            channel_uuid = uuid.UUID(channel_id)
            query = query.filter(Clip.channel_id == channel_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid channel_id format")

    if status:
        query = query.filter(Clip.status == status)

    rows = query.all()
    clips = []
    for c in rows:
        # Fetch associated candidate to get scores
        candidate = db.query(ClipCandidate).filter(ClipCandidate.id == c.clip_candidate_id).first()
        scores = candidate.scores if candidate else {}
        clips.append({
            "id": str(c.id),
            "channel_id": str(c.channel_id),
            "status": c.status,
            "duration_s": c.duration_s,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "scores": scores,
        })
    return {"clips": clips}


@router.get("/{clip_id}")
def get_clip(clip_id: str, db: Session = Depends(get_db)):
    try:
        clip_uuid = uuid.UUID(clip_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid clip_id format")

    clip = db.query(Clip).filter(Clip.id == clip_uuid).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    candidate = db.query(ClipCandidate).filter(ClipCandidate.id == clip.clip_candidate_id).first()
    scores = candidate.scores if candidate else {}

    return {
        "id": str(clip.id),
        "channel_id": str(clip.channel_id),
        "clip_candidate_id": str(clip.clip_candidate_id),
        "storage_key": clip.storage_key,
        "thumbnail_key": clip.thumbnail_key,
        "duration_s": clip.duration_s,
        "caption_style": clip.caption_style,
        "status": clip.status,
        "scores": scores,
        "created_at": clip.created_at.isoformat() if clip.created_at else None,
    }


@router.patch("/{clip_id}")
def patch_clip(clip_id: str, body: ClipPatch, db: Session = Depends(get_db)):
    try:
        clip_uuid = uuid.UUID(clip_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid clip_id format")

    clip = db.query(Clip).filter(Clip.id == clip_uuid).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if body.status not in {"ready", "qc_failed"}:
        raise HTTPException(status_code=400, detail="Invalid status value. Must be 'ready' or 'qc_failed'")

    clip.status = body.status
    db.flush()

    inventory_item = db.query(InventoryItem).filter(InventoryItem.clip_id == clip.id).first()

    if body.status == "ready":
        if inventory_item:
            inventory_item.status = "ready"
            db.flush()

            # Check if a publishing job already exists for this inventory item
            existing_jobs = db.query(Job).filter(
                Job.type == "publishing",
                Job.status.in_(["queued", "running", "retrying"])
            ).all()

            has_publishing_job = False
            for job in existing_jobs:
                if str(job.payload.get("inventory_item_id")) == str(inventory_item.id):
                    has_publishing_job = True
                    break

            if not has_publishing_job:
                new_job = Job(
                    id=uuid.uuid4(),
                    type="publishing",
                    payload={"inventory_item_id": str(inventory_item.id)},
                    trace_id=f"manual-pub-{inventory_item.id}",
                    channel_id=clip.channel_id,
                    priority=5,
                    attempts=0,
                    max_attempts=3
                )
                db.add(new_job)
    else:
        # qc_failed
        if inventory_item:
            inventory_item.status = "rejected"

    db.commit()
    db.refresh(clip)

    return {
        "id": str(clip.id),
        "status": clip.status,
    }
