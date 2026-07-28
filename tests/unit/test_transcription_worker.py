import pytest
from unittest.mock import patch, MagicMock, mock_open, ANY
import uuid
from autonomous_media.workers.transcription import TranscriptionWorker
from autonomous_media.db.models import Job, SourceVideo, Transcript
from autonomous_media.exceptions import StageUnrecoverableError

class DummyWord:
    def __init__(self, word, start, end):
        self.word = word
        self.start = start
        self.end = end

class DummySegment:
    def __init__(self, words):
        self.words = words

class DummyInfo:
    def __init__(self, language="en"):
        self.language = language

# Create mock module and mock class
mock_faster_whisper = MagicMock()
mock_whisper_class = MagicMock()
mock_faster_whisper.WhisperModel = mock_whisper_class

@patch.dict("sys.modules", {"faster_whisper": mock_faster_whisper})
@patch("autonomous_media.workers.transcription.download_file")
@patch("autonomous_media.workers.transcription.put_object_data")
@patch("autonomous_media.workers.transcription.emit_event")
@patch("os.path.exists", return_value=True)
def test_transcription_worker_success(mock_exists, mock_emit, mock_put_object, mock_download):
    source_video_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"source_video_id": str(source_video_id)},
        trace_id="test-trace-transcription",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    source_video = SourceVideo(
        id=source_video_id,
        content_source_id=uuid.uuid4(),
        external_video_id="vid1",
        title="Title 1",
        url="https://youtube.com/watch?v=vid1",
        status="downloaded",
        storage_key="raw/some-uuid/original.mp4"
    )
    mock_session.query().filter().first.return_value = source_video
    
    # Mock WhisperModel transcribe output
    mock_model = MagicMock()
    words = [
        DummyWord("hello", 0.0, 0.5),
        DummyWord("world", 0.5, 1.0)
    ]
    mock_model.transcribe.return_value = ([DummySegment(words)], DummyInfo())
    mock_whisper_class.return_value = mock_model
    
    worker = TranscriptionWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_download.assert_called_once_with("autonomous-media-raw", f"raw/{source_video_id}/audio.wav", ANY)
    mock_model.transcribe.assert_called_once()
    mock_put_object.assert_called_once_with("autonomous-media-raw", ANY, ANY, content_type="application/json")
    mock_emit.assert_called_once_with(
        event_type="transcript.ready",
        trace_id="test-trace-transcription",
        payload=ANY
    )
    # Check that transcript row and next job were added
    mock_session.add.assert_any_call(ANY)
