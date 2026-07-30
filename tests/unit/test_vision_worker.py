from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.vision import VisionWorker
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo
from autonomous_media.exceptions import StageUnrecoverableError

# Create mock modules
mock_cv2 = MagicMock()
mock_mp = MagicMock()

@patch.dict("sys.modules", {"cv2": mock_cv2, "mediapipe": mock_mp})
@patch("autonomous_media.workers.vision.download_file")
@patch("autonomous_media.workers.vision.emit_event")
@patch("os.path.exists", return_value=True)
def test_vision_worker_success(mock_exists, mock_emit, mock_download):
    candidate_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"clip_candidate_id": str(candidate_id)},
        trace_id="test-trace-vision",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    clip_candidate = ClipCandidate(
        id=candidate_id,
        source_video_id=uuid.uuid4(),
        start_ms=30000,
        end_ms=60000,
        scores={}
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
            if isinstance(model, type) and model == ClipCandidate:
                q.filter().first.return_value = clip_candidate
            elif isinstance(model, type) and model == SourceVideo:
                q.filter().first.return_value = source_video
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock cv2 VideoCapture and properties
    mock_cv2.CAP_PROP_FPS = 5
    mock_cv2.CAP_PROP_FRAME_WIDTH = 3
    mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
    mock_cv2.CAP_PROP_FRAME_COUNT = 7
    mock_cap = MagicMock()
    mock_cap.get.side_effect = lambda prop: {
        5: 30.0, # CAP_PROP_FPS
        3: 1920.0, # CAP_PROP_FRAME_WIDTH
        4: 1080.0, # CAP_PROP_FRAME_HEIGHT
        7: 1800.0, # CAP_PROP_FRAME_COUNT
    }.get(prop, 0)
    mock_cap.read.return_value = (True, MagicMock())
    mock_cap.isOpened.return_value = True
    mock_cv2.VideoCapture.return_value = mock_cap
    
    # Mock OpenCV CascadeClassifier
    mock_cascade = MagicMock()
    mock_cascade.empty.return_value = False
    mock_cascade.detectMultiScale.return_value = [(400, 300, 200, 200)]
    mock_cv2.CascadeClassifier.return_value = mock_cascade
    
    worker = VisionWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", "raw/some-uuid/original.mp4", ANY)
    mock_cv2.VideoCapture.assert_called_once()
    mock_cascade.detectMultiScale.assert_called()
    mock_emit.assert_called_once_with(
        event_type="video.analyzed",
        trace_id="test-trace-vision",
        payload=ANY
    )
    # Check that next job is enqueued and clip_candidate updated
    mock_session.add.assert_any_call(ANY)
