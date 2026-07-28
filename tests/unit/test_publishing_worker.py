from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.publishing import PublishingWorker
from autonomous_media.db.models import Job, InventoryItem, Clip, Channel, ContentSource, ClipCandidate, SourceVideo
from autonomous_media.exceptions import StageUnrecoverableError, RightsBlockedError

# Create mock module
mock_googleapiclient = MagicMock()
mock_google_auth = MagicMock()

class MockHttpError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resp = MagicMock()
        self.resp.status = 403

mock_googleapiclient.errors.HttpError = MockHttpError

@patch.dict("sys.modules", {
    "googleapiclient": mock_googleapiclient,
    "googleapiclient.discovery": mock_googleapiclient.discovery,
    "googleapiclient.http": mock_googleapiclient.http,
    "googleapiclient.errors": mock_googleapiclient.errors,
    "google_auth_oauthlib": mock_google_auth,
    "google.oauth2.credentials": mock_google_auth
})
@patch("autonomous_media.workers.publishing.download_file")
@patch("autonomous_media.workers.publishing.emit_event")
@patch("autonomous_media.workers.publishing.RightsGate")
@patch("autonomous_media.workers.publishing.get_object_data_helper")
@patch("os.path.exists", return_value=True)
def test_publishing_worker_success(mock_exists, mock_get_object, mock_rights_gate_class, mock_emit, mock_download):
    mock_get_object.return_value = b"[]"
    item_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    source_id = uuid.uuid4()
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
            "oauth_credentials": {
                "token": "test_token",
                "refresh_token": "test_refresh_token",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret"
            }
        }
    )
    from autonomous_media.db.models import Transcript
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
    
    # Mock Google API Client upload
    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = {"id": "yt_vid_123"}
    mock_youtube.videos().insert.return_value = mock_request
    mock_googleapiclient.discovery.build.return_value = mock_youtube
    
    worker = PublishingWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", clip.storage_key, ANY)
    mock_googleapiclient.discovery.build.assert_called_once()
    mock_youtube.videos().insert.assert_called_once()
    mock_emit.assert_called_once_with(
        event_type="publish.completed",
        trace_id="test-trace-publish",
        payload=ANY
    )
    
    assert inventory_item.status == "published"
    assert inventory_item.external_video_id == "yt_vid_123"
    mock_session.add.assert_any_call(ANY)
