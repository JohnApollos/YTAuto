import pytest
from unittest.mock import patch, MagicMock, mock_open, ANY
from datetime import datetime, timezone
import uuid
from autonomous_media.workers.acquisition import AcquisitionWorker
from autonomous_media.db.models import Job, ContentSource, SourceVideo
from autonomous_media.sources.base import SourceItem
from autonomous_media.exceptions import StageUnrecoverableError

def test_acquisition_worker_missing_source_id():
    worker = AcquisitionWorker(MagicMock())
    job = Job(payload={})
    
    with pytest.raises(StageUnrecoverableError) as exc_info:
        worker.process(MagicMock(), job)
    assert "Missing source_id" in str(exc_info.value)

def test_acquisition_worker_source_not_found():
    worker = AcquisitionWorker(MagicMock())
    job = Job(payload={"source_id": str(uuid.uuid4())})
    
    mock_session = MagicMock()
    mock_session.query().filter().first.return_value = None
    
    with pytest.raises(StageUnrecoverableError) as exc_info:
        worker.process(mock_session, job)
    assert "ContentSource" in str(exc_info.value)

@patch("autonomous_media.workers.acquisition.YouTubeClipSource")
@patch("autonomous_media.workers.acquisition.yt_dlp.YoutubeDL")
@patch("autonomous_media.workers.acquisition.ffmpeg")
@patch("autonomous_media.workers.acquisition.upload_file")
@patch("autonomous_media.workers.acquisition.emit_event")
@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data=b"test_data")
def test_acquisition_worker_success(mock_file, mock_exists, mock_emit, mock_upload, mock_ffmpeg, mock_ytdl, mock_clip_source):
    source_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"source_id": str(source_id)},
        trace_id="test-trace",
        priority=5
    )
    
    # Mock database session
    mock_session = MagicMock()
    content_source = ContentSource(
        id=source_id,
        channel_id=channel_id,
        external_ref="UC12345",
        config={"api_key": "test_key", "since_published_after": "2026-01-01T00:00:00Z"}
    )
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        q.filter().all.return_value = []
        if args:
            model = args[0]
            if isinstance(model, type) and model == ContentSource:
                q.filter().first.return_value = content_source
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock YouTubeClipSource discover
    mock_clip_instance = MagicMock()
    mock_clip_instance.discover.return_value = [
        SourceItem(external_id="vid1", title="Title 1", url="https://youtube.com/watch?v=vid1", published_at="2026-01-02T12:00:00Z")
    ]
    mock_clip_source.return_value = mock_clip_instance
    
    # Mock ffmpeg probe
    mock_ffmpeg.probe.return_value = {"format": {"duration": "120.0"}}
    
    worker = AcquisitionWorker(MagicMock())
    result = worker.process(mock_session, job)
    
    # Assertions
    from autonomous_media.workers.base import JobResult
    assert isinstance(result, JobResult)
    mock_clip_instance.discover.assert_called_once_with(existing_ids=set())
    mock_ytdl.return_value.__enter__.return_value.download.assert_called_once_with(["https://youtube.com/watch?v=vid1"])
    mock_ffmpeg.input.assert_called_once()
    mock_upload.assert_any_call("autonomous-media-raw", ANY, ANY)
    mock_emit.assert_called_once_with(
        event_type="video.downloaded",
        trace_id=ANY,
        payload=ANY
    )
    # Check that next job is added
    mock_session.add.assert_any_call(ANY)
