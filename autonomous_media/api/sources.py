import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import ContentSource, Channel

router = APIRouter(prefix="/sources", tags=["Sources"])


class SourceCreate(BaseModel):
    channel_id: str
    type: str  # e.g. "youtube_channel"
    external_ref: str  # YouTube channel ID e.g. "UCxxxxxx"
    config: dict = {}
    active: bool = True


class SourceUpdate(BaseModel):
    active: Optional[bool] = None
    config: Optional[dict] = None


@router.get("/")
def list_sources(channel_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ContentSource)
    if channel_id:
        try:
            channel_uuid = uuid.UUID(channel_id)
            query = query.filter(ContentSource.channel_id == channel_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid channel_id format")

    rows = query.all()
    sources = []
    for s in rows:
        sources.append({
            "id": str(s.id),
            "channel_id": str(s.channel_id),
            "type": s.type,
            "external_ref": s.external_ref,
            "active": s.active,
            "last_polled_at": s.last_polled_at.isoformat() if s.last_polled_at else None,
            "config": s.config,
        })
    return {"sources": sources}


@router.post("/")
def create_source(body: SourceCreate, db: Session = Depends(get_db)):
    try:
        channel_uuid = uuid.UUID(body.channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id format")

    # Check that channel exists
    channel = db.query(Channel).filter(Channel.id == channel_uuid).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    new_source = ContentSource(
        id=uuid.uuid4(),
        channel_id=channel_uuid,
        type=body.type,
        external_ref=body.external_ref,
        config=body.config,
        active=body.active,
    )
    db.add(new_source)
    db.commit()
    db.refresh(new_source)

    return {
        "id": str(new_source.id),
        "channel_id": str(new_source.channel_id),
        "external_ref": new_source.external_ref,
        "type": new_source.type,
    }


@router.get("/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db)):
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source_id format")

    source = db.query(ContentSource).filter(ContentSource.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=404, detail="ContentSource not found")

    return {
        "id": str(source.id),
        "channel_id": str(source.channel_id),
        "type": source.type,
        "external_ref": source.external_ref,
        "active": source.active,
        "last_polled_at": source.last_polled_at.isoformat() if source.last_polled_at else None,
        "config": source.config,
    }


@router.patch("/{source_id}")
def update_source(source_id: str, body: SourceUpdate, db: Session = Depends(get_db)):
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source_id format")

    source = db.query(ContentSource).filter(ContentSource.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=404, detail="ContentSource not found")

    if body.active is not None:
        source.active = body.active
    if body.config is not None:
        # Merge or overwrite config
        source.config = body.config

    db.commit()
    db.refresh(source)

    return {
        "id": str(source.id),
        "active": source.active,
        "config": source.config,
    }


@router.post("/{source_id}/poll-now")
def trigger_source_poll_now(source_id: str, db: Session = Depends(get_db)):
    """Force immediately enqueuing an acquisition job for this content source."""
    from autonomous_media.db.models import Job
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source_id format")

    source = db.query(ContentSource).filter(ContentSource.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=404, detail="ContentSource not found")

    job = Job(
        type="acquisition",
        payload={"source_id": str(source.id)},
        channel_id=source.channel_id,
        priority=1,
        attempts=0,
        max_attempts=3,
        trace_id=f"manual-poll-{source.id}"
    )
    db.add(job)
    # Reset last_polled_at
    source.last_polled_at = None
    db.commit()
    db.refresh(job)

    return {"status": "success", "job_id": str(job.id), "trace_id": job.trace_id}
