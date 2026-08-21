from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum

class ContentType(str, Enum):
    podcast_clip = "podcast_clip"
    ai_story = "ai_story"

class SourceType(str, Enum):
    youtube_channel = "youtube_channel"
    rss_feed = "rss_feed"
    ai_story = "ai_story"
    local_folder = "local_folder"

class ContentSourceConfig(BaseModel):
    type: SourceType
    external_ref: str
    poll_interval_minutes: int = Field(default=60, ge=5)

class UploadCadence(BaseModel):
    target_per_day: int = Field(ge=0, le=20)
    preferred_windows: List[str] = []
    quota_priority: float = Field(default=1.0, ge=0)

class TargetDuration(BaseModel):
    min_seconds: int = Field(ge=5, le=180)
    max_seconds: int = Field(ge=5, le=180)

class BrandingConfig(BaseModel):
    logo_key: Optional[str] = None
    primary_color: Optional[str] = None
    outro_key: Optional[str] = None

class RightsPolicy(BaseModel):
    default_status: str = "unknown"
    require_manual_review: bool = True

class ScoringWeights(BaseModel):
    hook: float = 1.0
    emotion: float = 1.0
    curiosity: float = 1.0
    humor: float = 0.7
    educational: float = 1.0
    story_completeness: float = 0.8
    novelty: float = 1.2

class ChannelConfig(BaseModel):
    name: str
    niche: str
    language: str = "en"
    status: str = "active"
    project_id: str
    content_types: List[ContentType]
    sources: List[ContentSourceConfig]
    upload_cadence: UploadCadence
    target_duration: TargetDuration
    caption_style: str
    music_profile: str
    branding: BrandingConfig = BrandingConfig()
    rights_policy: RightsPolicy = RightsPolicy()
    scoring_weights: ScoringWeights = ScoringWeights()

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    youtube_oauth_client_id: Optional[str] = None
    youtube_oauth_client_secret: Optional[str] = None
    jwt_secret: Optional[str] = None
    model_residency: str = "swap"
    youtube_api_key: Optional[str] = None
    youtube_api_env: str = "production"
    model_env: str = "production"
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
