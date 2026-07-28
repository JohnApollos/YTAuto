from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.quality_gate import QualityGateWorker
from autonomous_media.db.models import Job, Clip, InventoryItem
from autonomous_media.exceptions import StageUnrecoverableError

# Create mock module
mock_ffmpeg = MagicMock()

@patch.dict("sys.modules", {"ffmpeg": mock_ffmpeg})
@patch("autonomous_media.workers.quality_gate.download_file")
@patch("autonomous_media.workers.quality_gate.emit_event")
@patch("os.path.exists", return_value=True)
def test_quality_gate_worker_success(mock_exists, mock_emit, mock_download):
    clip_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"clip_id": str(clip_id)},
        trace_id="test-trace-qc",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    clip = Clip(
        id=clip_id,
        clip_candidate_id=uuid.uuid4(),
        channel_id=channel_id,
        duration_s=30,
        caption_style="default",
        status="rendering",
        storage_key=f"clips/{clip_id}.mp4"
    )
    
    mock_session.query().filter().first.return_value = clip
    
    # Mock ffmpeg probe output
    mock_ffmpeg.probe.return_value = {
        "streams": [
            {"codec_type": "video", "width": 1080, "height": 1920},
            {"codec_type": "audio"}
        ],
        "format": {"duration": "30.0"}
    }
    
    worker = QualityGateWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", clip.storage_key, ANY)
    mock_ffmpeg.probe.assert_called_once()
    mock_emit.assert_called_once_with(
        event_type="qc.passed",
        trace_id="test-trace-qc",
        payload=ANY
    )
    # Check that Clip status is updated and InventoryItem is created
    assert clip.status == "qc_passed"
    mock_session.add.assert_any_call(ANY)
