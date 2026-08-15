"""
autonomous_media/api/curated_stories.py

POST /curated-stories — operator submits a story for the curated_story
content source (spec section 30, section 9.2).

No automated discover() step exists for this content type (spec section 30.1) --
manual operator submission via this endpoint IS the acquisition step.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from autonomous_media.api.auth import require_auth
from autonomous_media.db.models import ContentSource, SourcePost, Job, Channel
from autonomous_media.db.session import get_db
from autonomous_media.logging import get_logger

router = APIRouter(prefix="/curated-stories", tags=["curated-stories"])
logger = get_logger("api.curated_stories")


class StorySubmission(BaseModel):
    content_source_id: Optional[str] = None
    channel_id: Optional[str] = None
    title: str
    body_text: str
    source_url: Optional[str] = None
    author: Optional[str] = None
    subreddit: Optional[str] = None


class StoryResponse(BaseModel):
    id: str
    status: str
    title: str
    submitted_at: str


@router.options("")
@router.options("/")
def options_stories():
    return {}


@router.post("", response_model=StoryResponse, status_code=201)
@router.post("/", response_model=StoryResponse, status_code=201)
def submit_story(
    body: StorySubmission,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    """Submit a curated story for narration and publication.
    Creates a source_posts row and enqueues a script_preparation job.
    Auto-resolves or creates a curated_story ContentSource for the target channel if needed.
    """
    content_source = None
    if body.content_source_id:
        try:
            cs_id = uuid.UUID(body.content_source_id)
            content_source = session.query(ContentSource).filter(
                ContentSource.id == cs_id,
            ).first()
        except ValueError:
            pass

    if not content_source:
        # Resolve target channel
        target_channel = None
        if body.channel_id:
            try:
                target_channel = session.query(Channel).filter(Channel.id == uuid.UUID(body.channel_id)).first()
            except ValueError:
                pass
        if not target_channel:
            target_channel = session.query(Channel).first()
        
        if not target_channel:
            # Auto-create a default channel if none exists
            target_channel = Channel(
                id=uuid.uuid4(),
                name="Default Story Channel",
                slug=f"default_story_channel_{uuid.uuid4().hex[:6]}",
                niche="Reddit Stories",
                project_id="default_project",
                language="en",
                target_duration_min_s=30,
                target_duration_max_s=90,
                caption_style="classic",
                music_profile="chill",
                allowed_content_types=["curated_story"]
            )
            session.add(target_channel)
            session.flush()

        # Find or auto-create curated_story ContentSource for this channel
        content_source = session.query(ContentSource).filter(
            ContentSource.channel_id == target_channel.id,
            ContentSource.type == "curated_story",
        ).first()

        if not content_source:
            content_source = ContentSource(
                id=uuid.uuid4(),
                channel_id=target_channel.id,
                type="curated_story",
                external_ref="reddit_curated_stories",
                config={"poll_interval_minutes": 60, "max_new_videos_per_poll": 1},
                active=True
            )
            session.add(content_source)
            session.flush()

    # Create the source_post row
    post_id = uuid.uuid4()
    trace_id = f"story-{post_id}"

    post = SourcePost(
        id=post_id,
        content_source_id=content_source.id,
        title=body.title,
        body_text=body.body_text,
        source_url=body.source_url,
        author=body.author,
        subreddit=body.subreddit,
        status="pending",
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(post)

    # Enqueue script_preparation job (spec section 30.2)
    job = Job(
        type="script_preparation",
        payload={"source_post_id": str(post_id)},
        trace_id=trace_id,
        channel_id=content_source.channel_id,
        priority=5,
        attempts=0,
        max_attempts=3,
    )
    session.add(job)
    session.commit()

    logger.info(f"Curated story submitted: {post_id}", extra={"trace_id": trace_id})

    return StoryResponse(
        id=str(post_id),
        status=post.status,
        title=post.title,
        submitted_at=post.submitted_at.isoformat(),
    )


@router.get("", response_model=list[StoryResponse])
@router.get("/", response_model=list[StoryResponse])
def list_stories(
    limit: int = 50,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    """List recent curated story submissions."""
    posts = (
        session.query(SourcePost)
        .order_by(SourcePost.submitted_at.desc())
        .limit(limit)
        .all()
    )
    return [
        StoryResponse(
            id=str(p.id),
            status=p.status,
            title=p.title,
            submitted_at=p.submitted_at.isoformat() if p.submitted_at else "",
        )
        for p in posts
    ]


@router.post("/re-queue-all")
def re_queue_all_stories(session: Session = Depends(get_db)):
    """Re-queues all curated stories from the beginning (script_preparation) for clean voice synthesis & 9:16 portrait rendering."""
    from autonomous_media.db.models import Clip, Transcript

    posts = session.query(SourcePost).all()
    requeued = 0
    for p in posts:
        p.status = "submitted"
        p.script_text = None

        # Clean up stale transcripts & clips linked to this post so they re-render freshly
        try:
            session.query(Transcript).filter(Transcript.source_post_id == p.id).delete(synchronize_session=False)
            session.query(Clip).filter(Clip.source_post_id == p.id).delete(synchronize_session=False)
        except Exception:
            pass

        trace_id = f"story-{p.id}"
        job = Job(
            type="script_preparation",
            payload={"source_post_id": str(p.id)},
            trace_id=trace_id,
            priority=5,
            attempts=0,
            max_attempts=3,
        )
        session.add(job)
        requeued += 1

    session.commit()
    return {"status": "success", "requeued_stories": requeued}
