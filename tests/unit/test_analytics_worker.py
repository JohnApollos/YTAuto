from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.analytics import AnalyticsWorker
from autonomous_media.db.models import Job, InventoryItem, Clip, Channel, AnalyticsSnapshot
from autonomous_media.exceptions import StageUnrecoverableError

# Create mock modules
mock_googleapiclient = MagicMock()
mock_google_auth = MagicMock()

@patch.dict("sys.modules", {
    "googleapiclient": mock_googleapiclient,
    "googleapiclient.discovery": mock_googleapiclient.discovery,
    "googleapiclient.errors": mock_googleapiclient.errors,
    "google_auth_oauthlib": mock_google_auth,
    "google.oauth2.credentials": mock_google_auth
})
@patch("autonomous_media.workers.analytics.emit_event")
def test_analytics_worker_success(mock_emit):
    item_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"inventory_item_id": str(item_id)},
        trace_id="test-trace-analytics",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    inventory_item = InventoryItem(
        id=item_id,
        clip_id=clip_id,
        channel_id=channel_id,
        status="published",
        external_video_id="yt_vid_123"
    )
    clip = Clip(
        id=clip_id,
        clip_candidate_id=uuid.uuid4(),
        channel_id=channel_id,
        status="qc_passed"
    )
    channel = Channel(
        id=channel_id,
        name="Test Channel",
        slug="test-channel",
        branding={
            "oauth_credentials": {
                "token": "test_token",
                "refresh_token": "test_refresh",
                "client_id": "client_id",
                "client_secret": "client_secret"
            }
        }
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
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock YouTube videos.list execution
    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = {
        "items": [{
            "statistics": {
                "viewCount": "1000",
                "likeCount": "50",
                "commentCount": "10"
            }
        }]
    }
    mock_youtube.videos().list.return_value = mock_request
    mock_googleapiclient.discovery.build.return_value = mock_youtube
    
    worker = AnalyticsWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_googleapiclient.discovery.build.assert_called_once()
    mock_youtube.videos().list.assert_called_once()
    mock_emit.assert_called_once_with(
        event_type="analytics.updated",
        trace_id="test-trace-analytics",
        payload=ANY
    )
    # Check that AnalyticsSnapshot row and next job were added
    mock_session.add.assert_any_call(ANY)
