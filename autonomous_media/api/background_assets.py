"""
autonomous_media/api/background_assets.py

CRUD for the background asset library (spec section 30.4).
The pipeline only draws from this pre-vetted pool, never searches at render time.
"""

from __future__ import annotations

import uuid
import os
import tempfile
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from autonomous_media.api.auth import require_auth
from autonomous_media.db.models import BackgroundAsset
from autonomous_media.db.session import get_db
from autonomous_media.storage import upload_file

router = APIRouter(prefix="/background-assets", tags=["background-assets"])


class AssetCreate(BaseModel):
    storage_key: str
    source_url: Optional[str] = None
    license_type: str = "unknown"  # owned | licensed | unknown
    license_evidence_ref: Optional[str] = None
    duration_s: Optional[float] = None
    tags: list[str] = []


class AssetPatch(BaseModel):
    license_type: Optional[str] = None
    license_evidence_ref: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None  # active | retired


class AssetResponse(BaseModel):
    id: str
    storage_key: str
    source_url: Optional[str] = None
    license_type: str
    license_evidence_ref: Optional[str] = None
    duration_s: Optional[float] = None
    tags: list[str] = []
    status: str


AssetCreate.model_rebuild()
AssetPatch.model_rebuild()
AssetResponse.model_rebuild()


@router.get("", response_model=list[AssetResponse])
@router.get("/", response_model=list[AssetResponse])
def list_assets(
    status: str = "active",
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    assets = (
        session.query(BackgroundAsset)
        .filter(BackgroundAsset.status == status)
        .order_by(BackgroundAsset.created_at.desc())
        .all()
    )
    return [_to_response(a) for a in assets]


@router.post("", response_model=AssetResponse, status_code=201)
def create_asset(
    body: AssetCreate,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    asset = BackgroundAsset(
        id=uuid.uuid4(),
        storage_key=body.storage_key,
        source_url=body.source_url,
        license_type=body.license_type,
        license_evidence_ref=body.license_evidence_ref,
        duration_s=body.duration_s,
        tags=body.tags,
        status="active",
    )
    session.add(asset)
    session.commit()
    return _to_response(asset)


@router.post("/upload", response_model=AssetResponse, status_code=201)
def upload_local_background_asset(
    file: UploadFile = File(...),
    license_type: str = Form("owned"),
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    """Upload a local video file (.mp4) directly into MinIO and register it as an active background asset."""
    asset_id = uuid.uuid4()
    storage_key = f"backgrounds/{asset_id}.mp4"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        contents = file.file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        upload_file("autonomous-media-renders", storage_key, tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    asset = BackgroundAsset(
        id=asset_id,
        storage_key=storage_key,
        source_url=f"local://{file.filename}",
        license_type=license_type,
        status="active",
    )
    session.add(asset)
    session.commit()
    return _to_response(asset)


@router.patch("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    body: AssetPatch,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    try:
        aid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid asset_id")

    asset = session.query(BackgroundAsset).filter(BackgroundAsset.id == aid).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if body.license_type is not None:
        asset.license_type = body.license_type
    if body.license_evidence_ref is not None:
        asset.license_evidence_ref = body.license_evidence_ref
    if body.tags is not None:
        asset.tags = body.tags
    if body.status is not None:
        asset.status = body.status

    session.commit()
    return _to_response(asset)


@router.delete("/{asset_id}", status_code=204)
def retire_asset(
    asset_id: str,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    """Soft-delete: sets status to 'retired', does not remove from MinIO."""
    try:
        aid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid asset_id")

    asset = session.query(BackgroundAsset).filter(BackgroundAsset.id == aid).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.status = "retired"
    session.commit()


def _to_response(asset: BackgroundAsset) -> AssetResponse:
    return AssetResponse(
        id=str(asset.id),
        storage_key=asset.storage_key,
        source_url=asset.source_url,
        license_type=asset.license_type,
        license_evidence_ref=asset.license_evidence_ref,
        duration_s=asset.duration_s,
        tags=asset.tags or [],
        status=asset.status,
    )
