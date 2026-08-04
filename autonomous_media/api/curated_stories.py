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
from autonomous_media.db.models import ContentSource, SourcePost, Job
from autonomous_media.db.session import get_db
from autonomous_media.logging import get_logger

router = APIRouter(prefix="/curated-stories", tags=["curated-stories"])
logger = get_logger("api.curated_stories")


class StorySubmission(BaseModel):
    content_source_id: str  # must be a curated_story-type ContentSource
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


@router.post("", response_model=StoryResponse, status_code=201)
def submit_story(
    body: StorySubmission,
    session: Session = Depends(get_db),
    _user=Depends(require_auth),
):
    """Submit a curated story for narration and publication.
    Creates a source_posts row and enqueues a script_preparation job.
    """
    # Validate that the content source exists and is the right type
    try:
        cs_id = uuid.UUID(body.content_source_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid content_source_id format")

    content_source = session.query(ContentSource).filter(
        ContentSource.id == cs_id,
        ContentSource.type == "curated_story",
    ).first()
    if not content_source:
        raise HTTPException(
            status_code=404,
            detail="content_source_id not found or is not of type curated_story",
        )

    # Create the source_post row
    post_id = uuid.uuid4()
    trace_id = f"story-{post_id}"

    post = SourcePost(
        id=post_id,
        content_source_id=cs_id,
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
