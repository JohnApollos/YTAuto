from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

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


@router.get("/", summary="List jobs — filter by status, type, channel, date range")
def list_jobs(
    status: Optional[str] = None,
    type: Optional[str] = None,
    channel_id: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
):
    # Stub: replace with real DB query with cursor-based pagination (spec §9.1)
    return {"jobs": [], "next_cursor": None}


@router.get("/{job_id}", summary="Job detail including full event trace")
def get_job(job_id: str):
    return {"id": job_id, "status": "queued"}


@router.post("/{job_id}/retry", summary="Manually retry a dead-lettered job")
def retry_job(job_id: str):
    # Stub: set job.status = 'queued', reset attempts if appropriate
    return {"id": job_id, "status": "queued"}


@router.post("/{job_id}/cancel", summary="Cancel a queued or running job")
def cancel_job(job_id: str):
    # Stub: set job.status = 'cancelled'
    return {"id": job_id, "status": "cancelled"}
