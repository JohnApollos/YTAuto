from unittest.mock import patch, MagicMock, ANY
import uuid
import json
import pytest
from autonomous_media.workers.editing import EditingWorker
from autonomous_media.db.models import Job, ClipCandidate, SourceVideo, Clip
from autonomous_media.exceptions import StageUnrecoverableError

@patch("autonomous_media.workers.editing.get_object_data")
@patch("autonomous_media.workers.editing.put_object_data")
@patch("autonomous_media.workers.editing.emit_event")
def test_editing_worker_success(mock_emit, mock_put_object, mock_get_object):
    candidate_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"clip_candidate_id": str(candidate_id)},
        trace_id="test-trace-editing",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    clip_candidate = ClipCandidate(
        id=candidate_id,
        source_video_id=uuid.uuid4(),
        start_ms=1000,
        end_ms=4000,
        scores={"crop_region": {"x_min": 0.3, "x_max": 0.6, "y_min": 0.0, "y_max": 1.0}}
    )
    source_video = SourceVideo(
        id=clip_candidate.source_video_id,
        content_source_id=uuid.uuid4()
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
            if isinstance(model, type) and model == ClipCandidate:
                q.filter().first.return_value = clip_candidate
            elif isinstance(model, type) and model == SourceVideo:
                q.filter().first.return_value = source_video
            elif isinstance(model, type) and model == Transcript:
                q.filter().first.return_value = transcript
        return q
    mock_session.query.side_effect = mock_query
    
    # Mock transcript words JSON in MinIO
    words = [
        {"word": "hello", "start_ms": 500, "end_ms": 900},
        {"word": "world", "start_ms": 1000, "end_ms": 1500},
        {"word": "this", "start_ms": 1600, "end_ms": 2000},
        {"word": "is", "start_ms": 2100, "end_ms": 2500},
        {"word": "cool", "start_ms": 3000, "end_ms": 3900},
        {"word": "outside", "start_ms": 4100, "end_ms": 4800}
    ]
    mock_get_object.return_value = json.dumps(words).encode("utf-8")
    
    worker = EditingWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_get_object.assert_called_once()
    # New: editing worker uploads .ass (ASS subtitle) not .srt
    mock_put_object.assert_called_once_with(
        "autonomous-media-raw",
        f"srt/{candidate_id}.ass",
        ANY,
        content_type="text/plain"
    )

    # Verify the rendering job payload carries the ass_storage_key
    added_jobs = [call.args[0] for call in mock_session.add.call_args_list
                  if hasattr(call.args[0], 'type') and getattr(call.args[0], 'type', None) == 'rendering']
    assert len(added_jobs) == 1, "Expected exactly one rendering job to be enqueued"
    assert added_jobs[0].payload.get("ass_storage_key") == f"srt/{candidate_id}.ass"

    # Check that Clip row and next job were added
    mock_session.add.assert_any_call(ANY)
