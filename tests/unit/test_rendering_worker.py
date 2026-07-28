from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.rendering import RenderingWorker
from autonomous_media.db.models import Job, Clip, ClipCandidate, SourceVideo
from autonomous_media.exceptions import StageUnrecoverableError

# Create mock module
mock_ffmpeg = MagicMock()

@patch.dict("sys.modules", {"ffmpeg": mock_ffmpeg})
@patch("autonomous_media.workers.rendering.download_file")
@patch("autonomous_media.workers.rendering.upload_file")
@patch("autonomous_media.workers.rendering.emit_event")
@patch("autonomous_media.workers.rendering.subprocess.run")
@patch("os.path.exists", return_value=True)
def test_rendering_worker_success(mock_exists, mock_run, mock_emit, mock_upload, mock_download):
    clip_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"clip_id": str(clip_id)},
        trace_id="test-trace-rendering",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    clip = Clip(
        id=clip_id,
        clip_candidate_id=candidate_id,
        channel_id=channel_id,
        duration_s=3,
        caption_style="default",
        status="rendering",
        storage_key=f"clips/{clip_id}.mp4"
    )
    clip_candidate = ClipCandidate(
        id=candidate_id,
        source_video_id=uuid.uuid4(),
        start_ms=1000,
        end_ms=4000,
        scores={"crop_region": {"x_min": 0.3, "x_max": 0.6, "y_min": 0.0, "y_max": 1.0}}
    )
    source_video = SourceVideo(
        id=clip_candidate.source_video_id,
        storage_key="raw/some-uuid/original.mp4"
    )
    
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        if args:
            model = args[0]
            if isinstance(model, type) and model == Clip:
                q.filter().first.return_value = clip
            elif isinstance(model, type) and model == ClipCandidate:
                q.filter().first.return_value = clip_candidate
            elif isinstance(model, type) and model == SourceVideo:
                q.filter().first.return_value = source_video
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock ffmpeg chain
    mock_ffmpeg.input.return_value = mock_ffmpeg
    mock_ffmpeg.crop.return_value = mock_ffmpeg
    mock_ffmpeg.filter.return_value = mock_ffmpeg
    mock_ffmpeg.output.return_value = mock_ffmpeg
    mock_ffmpeg.overwrite_output.return_value = mock_ffmpeg
    mock_ffmpeg.compile.return_value = ["ffmpeg", "-i", "in.mp4", "out.mp4"]
    
    # Mock subprocess.run success
    mock_run.return_value = MagicMock()
    
    worker = RenderingWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    # Check download of both video and srt
    assert mock_download.call_count == 2
    mock_ffmpeg.input.assert_called()
    mock_ffmpeg.output.assert_called()
    mock_run.assert_called()
    mock_upload.assert_called_once_with("autonomous-media-raw", f"clips/{clip_id}.mp4", ANY)
    
    # Check database updates and next job enqueuing
    mock_session.add.assert_any_call(ANY)
