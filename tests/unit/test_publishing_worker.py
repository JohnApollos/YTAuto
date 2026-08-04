from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
import os
from autonomous_media.workers.publishing import PublishingWorker
from autonomous_media.db.models import Job, InventoryItem, Clip, Channel, ClipCandidate, SourceVideo, SourcePost, Transcript
from autonomous_media.exceptions import StageUnrecoverableError, RightsBlockedError

# Real os.path.exists to fall back on
_real_exists = os.path.exists

def mock_exists_side_effect(path):
    # If checking for our temporary downloaded video, return True
    if str(path).endswith("rendered.mp4") or "original.mp4" in str(path) or str(path).endswith(".mp4"):
        return True
    return _real_exists(path)

@patch("autonomous_media.workers.publishing.download_file")
@patch("autonomous_media.workers.publishing.emit_event")
@patch("autonomous_media.workers.publishing.RightsGate")
@patch("autonomous_media.storage.get_object_data")
@patch("autonomous_media.workers.publishing.os.path.exists")
@patch("shutil.copy2")
@patch("builtins.open")
def test_publishing_worker_success(mock_open, mock_copy, mock_exists, mock_get_object, mock_rights_gate_class, mock_emit, mock_download):
    mock_exists.side_effect = mock_exists_side_effect
    mock_get_object.return_value = b"[]"
    item_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"inventory_item_id": str(item_id)},
        trace_id="test-trace-publish",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    inventory_item = InventoryItem(
        id=item_id,
        clip_id=clip_id,
        channel_id=channel_id,
        status="ready"
    )
    clip = Clip(
        id=clip_id,
        clip_candidate_id=uuid.uuid4(),
        channel_id=channel_id,
        duration_s=30,
        status="qc_passed",
        storage_key=f"clips/{clip_id}.mp4"
    )
    clip_candidate = ClipCandidate(
        id=clip.clip_candidate_id,
        source_video_id=uuid.uuid4(),
        start_ms=1000,
        end_ms=4000,
        scores={"crop_region": {"x_min": 0.3, "x_max": 0.6, "y_min": 0.0, "y_max": 1.0}}
    )
    source_video = SourceVideo(
        id=clip_candidate.source_video_id,
        storage_key="raw/some-uuid/original.mp4",
        content_source_id=uuid.uuid4(),
        title="Test Source Video"
    )
    channel = Channel(
        id=channel_id,
        name="Test Channel",
        slug="test-channel",
        branding={
            "titles": ["Title 1"],
            "recent_titles": ["Recent 1"]
        }
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        source_video_id=clip_candidate.source_video_id,
        storage_key="transcripts/some-uuid.json"
    )
    
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        if args:
            model = args[0]
            if isinstance(model, type) and model == InventoryItem:
                q.filter().first.return_value = inventory_item
            elif isinstance(model, type) and model == Clip:
                q.filter().first.return_value = clip
            elif isinstance(model, type) and model == Channel:
                q.filter().first.return_value = channel
            elif isinstance(model, type) and model == ClipCandidate:
                q.filter().first.return_value = clip_candidate
            elif isinstance(model, type) and model == SourceVideo:
                q.filter().first.return_value = source_video
            elif isinstance(model, type) and model == Transcript:
                q.filter().first.return_value = transcript
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock RightsGate clearance
    mock_gate = MagicMock()
    mock_gate.is_cleared.return_value = True
    mock_rights_gate_class.return_value = mock_gate
    
    worker = PublishingWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", clip.storage_key, ANY)
    mock_copy.assert_called_once()
    mock_open.assert_called_once()
    mock_emit.assert_called_once_with(
        event_type="publish.completed",
        trace_id="test-trace-publish",
        payload=ANY
    )
    
    assert inventory_item.status == "published"
    assert inventory_item.external_video_id.startswith("local_export_")
    assert clip.status == "published"


@patch("autonomous_media.workers.publishing.download_file")
@patch("autonomous_media.workers.publishing.emit_event")
@patch("autonomous_media.workers.publishing.RightsGate")
@patch("autonomous_media.storage.get_object_data")
@patch("autonomous_media.workers.publishing.os.path.exists")
@patch("shutil.copy2")
@patch("builtins.open")
def test_publishing_worker_story_success(mock_open, mock_copy, mock_exists, mock_get_object, mock_rights_gate_class, mock_emit, mock_download):
    mock_exists.side_effect = mock_exists_side_effect
    mock_get_object.return_value = b"[]"
    item_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    post_id = uuid.uuid4()
    job = Job(
        payload={"inventory_item_id": str(item_id)},
        trace_id="test-trace-publish-story",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    inventory_item = InventoryItem(
        id=item_id,
        clip_id=clip_id,
        channel_id=channel_id,
        status="ready"
    )
    clip = Clip(
        id=clip_id,
        clip_candidate_id=None,
        source_post_id=post_id,
        channel_id=channel_id,
        duration_s=120,
        status="qc_passed",
        storage_key=f"clips/{clip_id}.mp4"
    )
    source_post = SourcePost(
        id=post_id,
        content_source_id=uuid.uuid4(),
        title="Test Reddit Story",
        body_text="Short text here.",
        status="rendering"
    )
    channel = Channel(
        id=channel_id,
        name="Test Channel",
        slug="test-channel",
        branding={}
    )
    # Story word count <= 150 -> goes to shorts folder
    transcript = Transcript(
        id=uuid.uuid4(),
        source_post_id=post_id,
        storage_key="transcripts/some-uuid.json",
        word_count=50
    )
    
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        if args:
            model = args[0]
            if isinstance(model, type) and model == InventoryItem:
                q.filter().first.return_value = inventory_item
            elif isinstance(model, type) and model == Clip:
                q.filter().first.return_value = clip
            elif isinstance(model, type) and model == Channel:
                q.filter().first.return_value = channel
            elif isinstance(model, type) and model == SourcePost:
                q.filter().first.return_value = source_post
            elif isinstance(model, type) and model == Transcript:
                q.filter().first.return_value = transcript
        return q
    mock_session.query.side_effect = mock_query
    
    worker = PublishingWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", clip.storage_key, ANY)
    mock_copy.assert_called_once()
    mock_open.assert_called_once()
    
    # Assert destination folder structure in mock copy call args
    dst_path = mock_copy.call_args[0][1]
    assert "reddit_videos" in dst_path
    assert "shorts" in dst_path
    
    assert inventory_item.status == "published"
    assert clip.status == "published"
    assert source_post.status == "done"
