from unittest.mock import patch, MagicMock, ANY
import uuid
import json
import pytest
from autonomous_media.workers.intelligence import IntelligenceWorker
from autonomous_media.db.models import Job, Transcript, ClipCandidate, Topic
from autonomous_media.exceptions import StageUnrecoverableError

# Create mock module and mock class
mock_sentence_transformers = MagicMock()
mock_transformer_class = MagicMock()
mock_sentence_transformers.SentenceTransformer = mock_transformer_class

@patch.dict("sys.modules", {"sentence_transformers": mock_sentence_transformers})
@patch("autonomous_media.workers.intelligence.get_object_data")
@patch("autonomous_media.workers.intelligence.emit_event")
@patch("autonomous_media.workers.intelligence.stage_manager")
def test_intelligence_worker_success(mock_stage_manager, mock_emit, mock_get_object):
    transcript_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"transcript_id": str(transcript_id)},
        trace_id="test-trace-intelligence",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    transcript = Transcript(
        id=transcript_id,
        source_video_id=uuid.uuid4(),
        storage_key="transcripts/some-uuid.json"
    )
    
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        q.filter().all.return_value = []
        if args:
            model = args[0]
            if isinstance(model, type) and model == Transcript:
                q.filter().first.return_value = transcript
        return q
    mock_session.query.side_effect = mock_query
    mock_session.scalar.return_value = 0.5
    
    # Mock transcript words JSON in MinIO (around 45 seconds of words to trigger candidate generation)
    words = []
    initial_text = ["Start?", "Build", "a", "name."]
    for idx, word in enumerate(initial_text):
        words.append({
            "word": word,
            "start_ms": idx * 300,
            "end_ms": (idx + 1) * 300
        })
    for i in range(4, 150):
        words.append({
            "word": f"word{i}",
            "start_ms": i * 300,
            "end_ms": (i + 1) * 300 - 50
        })
    mock_get_object.return_value = json.dumps(words).encode("utf-8")
    
    # Mock SentenceTransformer embed output (768 dimensions)
    mock_transformer = MagicMock()
    mock_transformer.encode.return_value = [0.1] * 768
    mock_transformer_class.return_value = mock_transformer
    
    # Mock stage_manager run_stage output
    mock_inference_result = MagicMock()
    mock_inference_result.text = json.dumps({
        "hook_strength": 85,
        "emotional_intensity": 70,
        "curiosity_gap": 80,
        "humor": 40,
        "educational_value": 90,
        "story_completeness": 85,
        "rationale": "Great candidate clip."
    })
    mock_stage_manager.run_stage.return_value = mock_inference_result
    
    worker = IntelligenceWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_get_object.assert_called_once_with("autonomous-media-transcripts", "transcripts/some-uuid.json")
    mock_transformer.encode.assert_called()
    mock_stage_manager.run_stage.assert_called()
    mock_emit.assert_called_once_with(
        event_type="clip.candidates.scored",
        trace_id="test-trace-intelligence",
        payload=ANY
    )
    # Check that ClipCandidate and Topic were added to DB
    mock_session.add.assert_any_call(ANY)
