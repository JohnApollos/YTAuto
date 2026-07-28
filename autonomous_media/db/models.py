import uuid
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, Integer, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
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
    allowed_content_types: Mapped[list[str]] = mapped_column(JSON, default=list) # Array equivalent in SQLite/JSON
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    content_sources: Mapped[list["ContentSource"]] = relationship(back_populates="channel")


class ContentSource(Base):
    __tablename__ = "content_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    type: Mapped[str] = mapped_column(String)
    external_ref: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)

    channel: Mapped["Channel"] = relationship(back_populates="content_sources")
    source_videos: Mapped[list["SourceVideo"]] = relationship(back_populates="content_source")


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

    content_source: Mapped["ContentSource"] = relationship(back_populates="source_videos")


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

class CandidateClip(Base):
    __tablename__ = "candidate_clips"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    start_time_s: Mapped[int] = mapped_column(Integer)
    end_time_s: Mapped[int] = mapped_column(Integer)
    transcript_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

    source_video: Mapped["SourceVideo"] = relationship()
    topic: Mapped["Topic"] = relationship()
    evaluation_score: Mapped["EvaluationScore"] = relationship(back_populates="candidate_clip", uselist=False)

class EvaluationScore(Base):
    __tablename__ = "evaluation_scores"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_clips.id"), unique=True)
    hook_score: Mapped[int] = mapped_column(Integer) # 1-10
    virality_score: Mapped[int] = mapped_column(Integer) # 1-10
    coherence_score: Mapped[int] = mapped_column(Integer) # 1-10
    total_score: Mapped[int] = mapped_column(Integer) # Sum or weighted average
    llm_reasoning: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

    candidate_clip: Mapped["CandidateClip"] = relationship(back_populates="evaluation_score")

class RenderedAsset(Base):
    __tablename__ = "rendered_assets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidate_clips.id"), unique=True)
    storage_key: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        Enum("pending", "rendering", "completed", "failed", name="render_status"),
        default="pending",
    )
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

    candidate_clip: Mapped["CandidateClip"] = relationship()
    published_asset: Mapped["PublishedAsset"] = relationship(back_populates="rendered_asset", uselist=False)

class PublishedAsset(Base):
    __tablename__ = "published_assets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rendered_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rendered_assets.id"), unique=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "uploading", "published", "failed", "deferred", name="publish_status"),
        default="pending",
    )
    published_at: Mapped["DateTime"] = mapped_column(DateTime, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

    rendered_asset: Mapped["RenderedAsset"] = relationship(back_populates="published_asset")


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Podcast #391"
    target_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_videos.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", "cancelled", name="workflow_status"),
        default="pending",
    )
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    stages: Mapped[list["WorkflowStage"]] = relationship(back_populates="workflow")

class WorkflowStage(Base):
    __tablename__ = "workflow_stages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id"))
    name: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Download", "Transcribe"
    order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", "skipped", name="stage_status"),
        default="pending",
    )
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    workflow: Mapped["Workflow"] = relationship(back_populates="stages")
    tasks: Mapped[list["Task"]] = relationship(back_populates="stage")

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_stages.id"))
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "succeeded", "failed", "retrying", "dead_letter", "cancelled",
             name="task_status"),
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

    stage: Mapped["WorkflowStage"] = relationship(back_populates="tasks")
