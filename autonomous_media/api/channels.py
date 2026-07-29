import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from autonomous_media.db.session import get_db
from autonomous_media.db.models import Channel

router = APIRouter(prefix="/channels", tags=["Channels"])


class ChannelCreate(BaseModel):
    name: str
    slug: str
    niche: str
    project_id: str
    language: str = "en"
    target_duration_min_s: int = 30
    target_duration_max_s: int = 90
    caption_style: str = "default"
    music_profile: str = "none"


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[str] = None


class OAuthCredentials(BaseModel):
    token: str
    refresh_token: str
    client_id: str
    client_secret: str
    token_uri: str = "https://oauth2.googleapis.com/token"


@router.get("/")
def list_channels(db: Session = Depends(get_db)):
    rows = db.query(Channel).all()
    channels = []
    for c in rows:
        channels.append({
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "niche": c.niche,
            "status": c.status,
            "project_id": c.project_id,
            "language": c.language,
        })
    return {"channels": channels}


@router.post("/")
def create_channel(body: ChannelCreate, db: Session = Depends(get_db)):
    # Check if slug is unique
    existing = db.query(Channel).filter(Channel.slug == body.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Channel slug '{body.slug}' already exists")

    new_channel = Channel(
        id=uuid.uuid4(),
        name=body.name,
        slug=body.slug,
        niche=body.niche,
        status="active",
        language=body.language,
        project_id=body.project_id,
        target_duration_min_s=body.target_duration_min_s,
        target_duration_max_s=body.target_duration_max_s,
        caption_style=body.caption_style,
        music_profile=body.music_profile,
        branding={},
        upload_cadence={},
        allowed_content_types=["podcast_clip"],
    )
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)

    return {
        "id": str(new_channel.id),
        "name": new_channel.name,
        "slug": new_channel.slug,
    }


@router.get("/{channel_id}")
def get_channel(channel_id: str, db: Session = Depends(get_db)):
    try:
        channel_uuid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel ID format")

    channel = db.query(Channel).filter(Channel.id == channel_uuid).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Strip oauth_credentials from branding response for security
    branding_clean = dict(channel.branding) if channel.branding else {}
    if "oauth_credentials" in branding_clean:
        branding_clean.pop("oauth_credentials")

    return {
        "id": str(channel.id),
        "name": channel.name,
        "slug": channel.slug,
        "niche": channel.niche,
        "status": channel.status,
        "project_id": channel.project_id,
        "language": channel.language,
        "target_duration_min_s": channel.target_duration_min_s,
        "target_duration_max_s": channel.target_duration_max_s,
        "caption_style": channel.caption_style,
        "music_profile": channel.music_profile,
        "branding": branding_clean,
        "upload_cadence": channel.upload_cadence,
        "allowed_content_types": channel.allowed_content_types,
        "created_at": channel.created_at.isoformat() if channel.created_at else None,
    }


@router.patch("/{channel_id}")
def update_channel(channel_id: str, body: ChannelUpdate, db: Session = Depends(get_db)):
    try:
        channel_uuid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel ID format")

    channel = db.query(Channel).filter(Channel.id == channel_uuid).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if body.name is not None:
        channel.name = body.name
    if body.niche is not None:
        channel.niche = body.niche
    if body.status is not None:
        channel.status = body.status
    if body.project_id is not None:
        channel.project_id = body.project_id

    db.commit()
    db.refresh(channel)

    return {
        "id": str(channel.id),
        "name": channel.name,
        "slug": channel.slug,
        "niche": channel.niche,
        "status": channel.status,
        "project_id": channel.project_id,
    }


@router.post("/{channel_id}/oauth")
def save_oauth(channel_id: str, body: OAuthCredentials, db: Session = Depends(get_db)):
    try:
        channel_uuid = uuid.UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel ID format")

    channel = db.query(Channel).filter(Channel.id == channel_uuid).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    branding = dict(channel.branding) if channel.branding else {}
    branding["oauth_credentials"] = {
        "token": body.token,
        "refresh_token": body.refresh_token,
        "client_id": body.client_id,
        "client_secret": body.client_secret,
        "token_uri": body.token_uri,
    }
    # Explicitly assign branding back to mark it as modified for SQLAlchemy
    channel.branding = branding
    db.commit()

    return {"status": "saved"}
