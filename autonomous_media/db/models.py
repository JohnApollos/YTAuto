import uuid
from datetime import datetime
from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey, DateTime, Integer, JSON, Boolean, Float
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
    project_id: Mapped[str] = mapped_column(String)  # spec §5.1 — Google Cloud project's quota pool
    target_duration_min_s: Mapped[int] = mapped_column(Integer)
    target_duration_max_s: Mapped[int] = mapped_column(Integer)
    caption_style: Mapped[str] = mapped_column(String)
    music_profile: Mapped[str] = mapped_column(String)
    voice_profile: Mapped[str | None] = mapped_column(String, nullable=True)  # Piper voice identifier for curated_story channels (spec §30.5)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)
    upload_cadence: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_content_types: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ContentSource(Base):
    __tablename__ = "content_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    type: Mapped[str] = mapped_column(String)  # youtube_channel | rss_feed | ai_story | local_folder
    external_ref: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SourceVideo(Base):
    __tablename__ = "source_videos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_sources.id"))
    external_video_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)  # MinIO key for raw video
    checksum_sha256: Mapped[str | None] = mapped_column(String, nullable=True)


class SourcePost(Base):
    """Spec §30.6: operator-submitted story (Reddit or similar). Manual acquisition
    replaces discover() for the curated_story content type (spec §30.1)."""
    __tablename__ = "source_posts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_sources.id"))
    title: Mapped[str] = mapped_column(String)
    body_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    subreddit: Mapped[str | None] = mapped_column(String, nullable=True)
    narration_audio_key: Mapped[str | None] = mapped_column(String, nullable=True)  # MinIO key for generated WAV
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM formatted narration script
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | scripting | narrating | transcribing | rendering | done | failed
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BackgroundAsset(Base):
    """Spec §30.4: pre-vetted background footage library for curated_story clips.
    The pipeline only ever draws from this library, never searches at render time."""
    __tablename__ = "background_assets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    storage_key: Mapped[str] = mapped_column(String)  # MinIO key
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    license_type: Mapped[str] = mapped_column(String, default="unknown")  # owned | licensed | unknown
    license_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["parkour", "night", "urban"]
    status: Mapped[str] = mapped_column(String, default="active")  # active | retired
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Transcript(Base):
    """Only metadata lives here. Full timestamped transcript JSON lives in MinIO at storage_key (spec §8.3)."""
    __tablename__ = "transcripts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_videos.id"), nullable=True)
    source_post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_posts.id"), nullable=True)
    promo_segments: Mapped[list | None] = mapped_column(JSON, nullable=True)  # cached output of promo_filter.detect_promo_segments (spec §11.8)
    engine: Mapped[str] = mapped_column(String, default="whisper-large-v3-turbo")  # ASR model used
    language: Mapped[str] = mapped_column(String, default="en")
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)  # MinIO pointer to full JSON
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)
    embedding: Mapped[list] = mapped_column(Vector(768))  # dimension must match embedding model output
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ClipCandidate(Base):
    __tablename__ = "clip_candidates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_videos.id"))
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer)  # milliseconds — word-level precision (spec §8.3)
    end_ms: Mapped[int] = mapped_column(Integer)    # milliseconds
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | selected | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Clip(Base):
    __tablename__ = "clips"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clip_candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clip_candidates.id"), nullable=True)
    source_post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_posts.id"), nullable=True)
    background_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("background_assets.id"), nullable=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))  # spec §8.3
    storage_key: Mapped[str] = mapped_column(String)
    thumbnail_key: Mapped[str | None] = mapped_column(String, nullable=True)  # spec §8.3
    duration_s: Mapped[int] = mapped_column(Integer)
    caption_style: Mapped[str | None] = mapped_column(String, nullable=True)  # spec §8.3
    status: Mapped[str] = mapped_column(String, default="rendering")  # rendering | qc_passed | qc_failed | ready
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clips.id"))
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    status: Mapped[str] = mapped_column(String, default="ready")  # ready | scheduled | published | rejected | archived
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # spec §8.3 field name
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_video_id: Mapped[str | None] = mapped_column(String, nullable=True)  # YouTube video ID after upload
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RightsRecord(Base):
    """
    Spec §8.3, §11.4: FK is on content_source_id (not source_video_id).
    Status values: owned | licensed | permission_granted | unknown | denied.
    Deliberately excludes 'fair_use_asserted' — fair use routes only through manual override path.
    """
    __tablename__ = "rights_records"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_sources.id"))
    status: Mapped[str] = mapped_column(
        String, default="unknown"
    )  # owned | licensed | permission_granted | unknown | denied
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # URL or document reference
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)  # operator identity (audit trail)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AnalyticsSnapshot(Base):
    """
    Spec §8.3: time series of pulls per inventory_item — never an overwrite.
    Explicit metric columns rather than a generic JSON blob so they can be queried.
    """
    __tablename__ = "analytics_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_view_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    subscribers_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Job(Base):
    """
    Spec §8.3: flat job table backing the state machine in §7.4.
    last_heartbeat_at backs the liveness mechanism in §12.1.
    """
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String, nullable=False)  # spec uses 'type', not 'job_type'
    status: Mapped[str] = mapped_column(
        String, default="queued"
    )  # queued | running | succeeded | failed | retrying | dead_letter | cancelled
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # spec §12.1
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Model(Base):
    """Spec §8.3: model registry behind the Model Runtime Manager (§12.9)."""
    __tablename__ = "models"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(String)  # e.g. 'scoring', 'transcription', 'vision'
    backend: Mapped[str] = mapped_column(String)  # e.g. 'vulkan', 'faster-whisper', 'cpu'
    version: Mapped[str] = mapped_column(String)
    resource_profile: Mapped[dict] = mapped_column(JSON, default=dict)  # ram_mb, vram_mb, quantization
    status: Mapped[str] = mapped_column(String, default="active")  # active | deprecated


class EvalRun(Base):
    """Spec §8.3: one row per evaluation pass — what the promotion gate (§18.1) checks."""
    __tablename__ = "eval_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    benchmark_set_version: Mapped[str] = mapped_column(String)  # e.g. 'v1'
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # precision_at_5, human_agreement_rate, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SystemEvent(Base):
    """Spec §8.3: append-only event log. Every event carries the job's trace_id (§7.3)."""
    __tablename__ = "system_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String)  # e.g. 'video.discovered', 'clip.candidates.scored'
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    """Spec §8.3, §29.2: backs the JWT auth in Section 14.3.
    role is a closed two-value enum: operator | local_admin.
    """
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="operator")  # operator | local_admin
    channel_scope: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of channel_ids, null = all channels
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
