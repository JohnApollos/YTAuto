from unittest.mock import patch, MagicMock, ANY
import uuid
import pytest
from autonomous_media.workers.learning import LearningWorker
from autonomous_media.db.models import Job, AnalyticsSnapshot, InventoryItem, Clip, ClipCandidate, Channel

@patch("autonomous_media.workers.learning.emit_event")
def test_learning_worker_success(mock_emit):
    snapshot_id = uuid.uuid4()
    item_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    job = Job(
        payload={"analytics_snapshot_id": str(snapshot_id)},
        trace_id="test-trace-learning",
        channel_id=channel_id,
        priority=5
    )
    
    mock_session = MagicMock()
    snapshot = AnalyticsSnapshot(
        id=snapshot_id,
        inventory_item_id=item_id,
        views=1500, # High views to trigger positive reinforcement
        likes=100
    )
    inventory_item = InventoryItem(
        id=item_id,
        clip_id=clip_id,
        channel_id=channel_id
    )
    clip = Clip(
        id=clip_id,
        clip_candidate_id=candidate_id,
        channel_id=channel_id
    )
    clip_candidate = ClipCandidate(
        id=candidate_id,
        scores={
            "hook_strength": 90,
            "emotional_intensity": 50,
            "curiosity_gap": 40,
            "humor": 30,
            "educational_value": 30,
            "story_completeness": 30
        }
    )
    channel = Channel(
        id=channel_id,
        name="Test Channel",
        slug="test-channel",
        branding={
            "scoring_weights": {
                "hook": 1.0,
                "emotion": 1.0,
                "curiosity": 1.0,
                "humor": 0.7,
                "educational": 1.0,
                "story_completeness": 0.8
            }
        }
    )
    
    def mock_query(*args):
        q = MagicMock()
        q.filter().first.return_value = None
        if args:
            model = args[0]
            if isinstance(model, type) and model == AnalyticsSnapshot:
                q.filter().first.return_value = snapshot
            elif isinstance(model, type) and model == InventoryItem:
                q.filter().first.return_value = inventory_item
            elif isinstance(model, type) and model == Clip:
                q.filter().first.return_value = clip
            elif isinstance(model, type) and model == ClipCandidate:
                q.filter().first.return_value = clip_candidate
            elif isinstance(model, type) and model == Channel:
                q.filter().first.return_value = channel
        return q
    mock_session.query.side_effect = mock_query
    
    worker = LearningWorker(MagicMock())
    from autonomous_media.workers.base import JobResult
    result = worker.process(mock_session, job)
    
    assert isinstance(result, JobResult)
    mock_emit.assert_called_once_with(
        event_type="learning.weights.updated",
        trace_id="test-trace-learning",
        payload=ANY
    )
    # Check that hook weight was increased (hook_strength was highest score of 90)
    weights = channel.branding["scoring_weights"]
    assert weights["hook"] > 1.0
