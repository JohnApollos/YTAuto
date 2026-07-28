import uuid
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, Integer, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from autonomous_media.db.base import Base

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True)
    niche: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    language: Mapped[str] = mapped_column(String, default="en")
    project_id: Mapped[str] = mapped_column(String)
    target_duration_min_s: Mapped[int] = mapped_column(Integer)
    target_duration_max_s: Mapped[int] = mapped_column(Integer)
    caption_style: Mapped[str] = mapped_column(String)
    music_profile: Mapped[str] = mapped_column(String)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)
    upload_cadence: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_content_types: Mapped[list[str]] = mapped_column(JSON, default=list) # SQLite fallback for array
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class ContentSource(Base):
    __tablename__ = "content_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    type: Mapped[str] = mapped_column(String)
    external_ref: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)

class SourceVideo(Base):
    __tablename__ = "source_videos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_sources.id"))
    external_video_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    published_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    downloaded_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String, nullable=True)

class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id"))
    text: Mapped[str] = mapped_column(Text)
    segments: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class CandidateClip(Base):
    __tablename__ = "clip_candidates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    start_time_s: Mapped[int] = mapped_column(Integer)
    end_time_s: Mapped[int] = mapped_column(Integer)
    transcript_text: Mapped[str] = mapped_column(Text)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class Clip(Base):
    __tablename__ = "clips"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clip_candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clip_candidates.id"))
    storage_key: Mapped[str] = mapped_column(String)
    duration_s: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_id: Mapped[str] = mapped_column(String) # polymorphic ID
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String,
        default="queued",
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    last_heartbeat_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id"))
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    status: Mapped[str] = mapped_column(String, default="available") # available, published, rejected
    scheduled_for: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    published_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    platform_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class RightsRecord(Base):
    __tablename__ = "rights_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id"))
    status: Mapped[str] = mapped_column(String, default="pending") # pending, cleared, flagged
    flag_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cleared_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[str] = mapped_column(String) # Channel or InventoryItem (polymorphic)
    entity_type: Mapped[str] = mapped_column(String) # 'channel', 'clip'
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
