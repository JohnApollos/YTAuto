import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import RightsRecord, ContentSource, SystemEvent
from autonomous_media.events import RIGHTS_STATUS_UPDATED

router = APIRouter(prefix="/rights", tags=["Rights"])


class RightsUpdate(BaseModel):
    status: str  # "owned" | "licensed" | "permission_granted" | "unknown" | "denied"
    evidence_ref: Optional[str] = None
    reviewed_by: Optional[str] = None


@router.get("/{source_id}")
def get_rights_status(source_id: str, db: Session = Depends(get_db)):
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source_id format")

    record = db.query(RightsRecord).filter(RightsRecord.content_source_id == source_uuid).first()
    if not record:
        return {
            "status": "unknown",
            "content_source_id": source_id,
            "evidence_ref": None,
            "reviewed_by": None,
            "reviewed_at": None,
        }

    return {
        "id": str(record.id),
        "content_source_id": str(record.content_source_id),
        "status": record.status,
        "evidence_ref": record.evidence_ref,
        "reviewed_by": record.reviewed_by,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
    }


@router.put("/{source_id}")
def update_rights_status(source_id: str, body: RightsUpdate, db: Session = Depends(get_db)):
    try:
        source_uuid = uuid.UUID(source_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid source_id format")

    valid_statuses = {"owned", "licensed", "permission_granted", "unknown", "denied"}
    if body.status not in valid_statuses:
        # FastAPI handles validation errors using 422 Unprocessable Entity
        raise HTTPException(
            status_code=422,
            detail=f"Invalid rights status '{body.status}'. Must be one of: {valid_statuses}"
        )

    # Check that ContentSource exists
    source = db.query(ContentSource).filter(ContentSource.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=404, detail="ContentSource not found")

    record = db.query(RightsRecord).filter(RightsRecord.content_source_id == source_uuid).first()
    now = datetime.now(timezone.utc)
    if record:
        record.status = body.status
        record.evidence_ref = body.evidence_ref
        record.reviewed_by = body.reviewed_by or "operator"
        record.reviewed_at = now
    else:
        record = RightsRecord(
            id=uuid.uuid4(),
            content_source_id=source_uuid,
            status=body.status,
            evidence_ref=body.evidence_ref,
            reviewed_by=body.reviewed_by or "operator",
            reviewed_at=now,
        )
        db.add(record)

    # Create audit event SystemEvent matching RightsGate
    event = SystemEvent(
        id=uuid.uuid4(),
        event_type=RIGHTS_STATUS_UPDATED,
        payload={
            "content_source_id": source_id,
            "new_status": body.status,
            "reviewed_by": body.reviewed_by or "operator",
            "evidence_ref": body.evidence_ref,
        },
        trace_id=f"rights-{source_id}",
        created_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(record)

    return {
        "id": str(record.id),
        "content_source_id": str(record.content_source_id),
        "status": record.status,
        "evidence_ref": record.evidence_ref,
    }
