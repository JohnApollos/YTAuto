import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import Job

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    channel_id: Optional[str] = None
    trace_id: str
    attempts: int
    max_attempts: int
    error: Optional[str] = None
    created_at: str


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
        jobs_list.append({
            "id": str(j.id),
            "type": j.type,
            "status": j.status,
            "channel_id": str(j.channel_id) if j.channel_id else None,
            "trace_id": j.trace_id,
            "attempts": j.attempts,
            "max_attempts": j.max_attempts,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else "",
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
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
