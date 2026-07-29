import pytest
from unittest.mock import patch, MagicMock
import uuid
import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autonomous_media.db.base import Base
from autonomous_media.db.models import (
    Job, Channel, ContentSource, SourceVideo, Transcript, ClipCandidate, Clip, InventoryItem, RightsRecord
)
from autonomous_media.quota import QuotaTracker
from autonomous_media.workers.publishing import PublishingWorker
from autonomous_media.exceptions import QuotaExceededError

@pytest.fixture(scope="module")
def db_engine():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=True
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()

def test_quota_tracker_basic_logic():
    tracker = QuotaTracker()
    project_id = "test-project-123"
    
    # Defaults to 10000 units
    assert tracker.get_remaining_quota(project_id) == 10000
    assert tracker.has_quota(project_id, 1600) is True
    assert tracker.has_quota(project_id, 11000) is False
    
    # Consumes correctly
    tracker.consume_quota(project_id, 1600)
    assert tracker.get_remaining_quota(project_id) == 8400
    assert tracker.has_quota(project_id, 8400) is True
    assert tracker.has_quota(project_id, 8500) is False

@patch("autonomous_media.quota.quota_tracker")
@patch("autonomous_media.workers.publishing.download_file")
@patch("autonomous_media.workers.publishing.get_object_data_helper")
@patch("autonomous_media.workers.publishing.stage_manager")
@patch("autonomous_media.db.session.SessionLocal")
@patch("os.path.exists", return_value=True)
def test_publishing_worker_quota_enforcement(
    mock_exists, mock_session_local, mock_stage_manager, mock_get_object, mock_download, mock_quota_tracker, db_session
):
    # Set environments
    os.environ["MODEL_ENV"] = "test"
    os.environ["YOUTUBE_API_ENV"] = "test"

    session_maker = sessionmaker(bind=db_session.bind, expire_on_commit=False)
    mock_session_local.side_effect = lambda: session_maker()

    # Configure stage_manager and get_object_data mocks consistently
    def mock_run_stage(stage, request):
        if stage == "title":
            return MagicMock(text="Amazing Title")
        elif stage == "description":
            return MagicMock(text='{"description": "Amazing video", "hashtags": ["#cool"]}')
        return MagicMock(text="{}")
    mock_stage_manager.run_stage.side_effect = mock_run_stage
    mock_get_object.return_value = b"[]"

    # Mock quota tracker responses: first check fails, second succeeds
    mock_quota_tracker.has_quota.side_effect = [False, True]
    
    channel = Channel(
        name="Test Quota Channel",
        slug="test-quota-channel",
        niche="education",
        project_id="test-quota-proj",
        target_duration_min_s=15,
        target_duration_max_s=45,
        caption_style="default",
        music_profile="default",
        branding={"recent_titles": ["Test Title"]},
        allowed_content_types=["podcast_clip"],
        upload_cadence={"target_per_day": 1}
    )
    db_session.add(channel)
    db_session.commit()

    source_id = uuid.uuid4()
    # Add a mock cleared rights record so rights gate succeeds
    rights = RightsRecord(
        content_source_id=source_id,
        status="owned",
        reviewed_by="admin"
    )
    db_session.add(rights)

    video = SourceVideo(
        content_source_id=source_id,
        external_video_id="video_quota",
        title="Video Quota",
        url="https://youtube.com/watch?v=video_quota",
        status="downloaded"
    )
    db_session.add(video)
    db_session.commit()

    transcript_id = uuid.uuid4()
    tr = Transcript(
        id=transcript_id,
        source_video_id=video.id,
        engine="whisper-large-v3-turbo",
        language="en",
        storage_key="transcripts/dummy.json",
        word_count=100
    )
    db_session.add(tr)
    
    candidate = ClipCandidate(
        source_video_id=video.id,
        start_ms=1000,
        end_ms=20000,
        status="selected"
    )
    db_session.add(candidate)
    db_session.commit()

    clip = Clip(
        clip_candidate_id=candidate.id,
        channel_id=channel.id,
        storage_key="clips/dummy.mp4",
        duration_s=19,
        status="qc_passed"
    )
    db_session.add(clip)
    db_session.commit()

    inventory_item = InventoryItem(
        clip_id=clip.id,
        channel_id=channel.id,
        status="ready"
    )
    db_session.add(inventory_item)
    db_session.commit()

    job = Job(
        type="publishing",
        trace_id="trace-quota-test",
        channel_id=channel.id,
        payload={"inventory_item_id": str(inventory_item.id)}
    )
    db_session.add(job)
    db_session.commit()

    # Create worker
    worker = PublishingWorker(session_maker)

    # 1. Run worker: first call has_quota returns False -> raises QuotaExceededError
    with pytest.raises(QuotaExceededError):
        worker.run(job)
        
    mock_quota_tracker.has_quota.assert_called_with("test-quota-proj", 1600)

    # Run worker: second call has_quota returns True -> succeeds and calls consume_quota
    worker.run(job)
    
    mock_quota_tracker.consume_quota.assert_called_with("test-quota-proj", 1600)
    
    # Re-query inside a fresh session to verify the status
    with session_maker() as fresh_session:
        fresh_item = fresh_session.query(InventoryItem).filter(InventoryItem.id == inventory_item.id).first()
        assert fresh_item.status == "published"
