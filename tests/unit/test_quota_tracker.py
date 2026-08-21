import uuid
import pytest
from autonomous_media.quota import QuotaTracker

def test_quota_tracker_basic_logic():
    tracker = QuotaTracker()
    project_id = f"test-project-{uuid.uuid4().hex[:8]}"
    
    # Defaults to 10000 units
    assert tracker.get_remaining_quota(project_id) == 10000
    assert tracker.has_quota(project_id, 1600) is True
    assert tracker.has_quota(project_id, 11000) is False
    
    # Consumes correctly
    tracker.consume_quota(project_id, 1600)
    assert tracker.get_remaining_quota(project_id) == 8400
    assert tracker.has_quota(project_id, 8400) is True
    assert tracker.has_quota(project_id, 8500) is False
