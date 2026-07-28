from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/clips", tags=["Clips"])


class ClipPatch(BaseModel):
    status: Optional[str] = None  # 'ready' (approve) or 'qc_failed' (reject)


@router.get("/", summary="List clips — filter by channel, status, score range")
def list_clips(
    channel_id: Optional[str] = None,
    status: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
):
    return {"clips": [], "next_cursor": None}


@router.get("/{clip_id}", summary="Clip detail: scores, preview URL, transcript excerpt")
def get_clip(clip_id: str):
    return {"id": clip_id}


@router.patch("/{clip_id}", summary="Approve or reject a clip (manual review safety net, spec §10.1)")
def patch_clip(clip_id: str, body: ClipPatch):
    # The manual review safety net from spec §10.1 — operator can approve or reject
    return {"id": clip_id, "status": body.status}
