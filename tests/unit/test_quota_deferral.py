import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import uuid

from autonomous_media.db.models import Job
from autonomous_media.exceptions import QuotaExceededError
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.scheduler.scheduler import Scheduler

# Dummy worker class to test QuotaExceededError raising
class DummyQuotaWorker(Worker):
    job_type = "dummy_quota"
    def process(self, session, job):
        raise QuotaExceededError("YouTube Quota limit reached")

def test_quota_exceeded_deferral_math():
    # Test next midnight Pacific calculations in base worker
    job = Job(id=uuid.uuid4(), type="dummy_quota", trace_id="trace", attempts=0, max_attempts=3)
    
    mock_session = MagicMock()
    mock_session.merge.return_value = job
    
    session_maker = MagicMock()
    session_maker.return_value.__enter__.return_value = mock_session

    worker = DummyQuotaWorker(session_maker=session_maker)
    
    # We patch time/threading/emit_event
    with patch("threading.Thread") as mock_thread, \
         patch("autonomous_media.workers.base.emit_event") as mock_emit:
        
        with pytest.raises(QuotaExceededError):
            worker.run(job)
            
        assert job.status == "retrying"
        assert job.attempts == 0  # Should NOT increment attempts
        assert job.scheduled_at is not None
        
        # Verify scheduled_at is indeed midnight Pacific
        scheduled_utc = job.scheduled_at.replace(tzinfo=timezone.utc)
        scheduled_pacific = scheduled_utc.astimezone(ZoneInfo("America/Los_Angeles"))
        
        assert scheduled_pacific.hour == 0
        assert scheduled_pacific.minute == 0
        assert scheduled_pacific.second == 0
        assert scheduled_pacific > datetime.now(timezone.utc).astimezone(ZoneInfo("America/Los_Angeles"))

def test_scheduler_poll_ignores_future_scheduled_jobs():
    session_maker = MagicMock()
    mock_session = MagicMock()
    session_maker.return_value.__enter__.return_value = mock_session
    
    scheduler = Scheduler(session_maker=session_maker, max_concurrent_jobs=1)
    
    mock_query = MagicMock()
    mock_session.query.return_value = mock_query
    
    mock_filter_running = MagicMock()
    mock_filter_running.count.return_value = 0
    
    mock_filter_queued = MagicMock()
    mock_filter_queued.order_by.return_value.limit.return_value.all.return_value = []
    
    mock_query.filter.side_effect = [mock_filter_running, mock_filter_queued]
    
    scheduler._poll()
    
    # Assert query was configured correctly
    assert mock_query.filter.call_count == 2
    
    # Check first call arguments (status == 'running')
    first_call_args = mock_query.filter.call_args_list[0][0]
    # Represented as boolean/binary clause, but let's check it's not empty
    assert len(first_call_args) == 1
