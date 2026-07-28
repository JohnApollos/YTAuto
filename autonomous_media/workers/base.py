import threading
import time
from abc import ABC, abstractmethod
from autonomous_media.db.models import Job
from autonomous_media.exceptions import StageUnrecoverableError
from autonomous_media.logging import emit_event
from sqlalchemy.orm import Session

HEARTBEAT_INTERVAL_S = 20

def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

def touch_heartbeat(session: Session, job_id: str):
    from autonomous_media.db.models import Job
    job = session.query(Job).filter(Job.id == job_id).first()
    if job:
        job.last_heartbeat_at = now()
        session.commit()

class JobResult:
    def summary(self):
        return {}

class Worker(ABC):
    job_type: str

    def __init__(self, session_maker):
        self.session_maker = session_maker

    @abstractmethod
    def process(self, session: Session, job: Job) -> JobResult:
        ...

    def run(self, job: Job) -> JobResult:
        with self.session_maker() as session:
            # Re-fetch job in this session to ensure it is bound
            job = session.merge(job)
            job.status = "running"
            job.started_at = now()
            session.commit()
            
            stop_heartbeat = threading.Event()
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, args=(job.id, stop_heartbeat), daemon=True
            )
            heartbeat_thread.start()
            
            try:
                result = self.process(session, job)
                job.status = "succeeded"
                emit_event(f"{job.type}.completed", job.trace_id, result.summary())
                session.commit()
                return result
            except StageUnrecoverableError as e:
                job.status = "dead_letter"
                job.error = str(e)
                session.commit()
                raise
            except Exception as e:
                job.attempts += 1
                job.status = "retrying" if job.attempts < job.max_attempts else "dead_letter"
                job.error = str(e)
                session.commit()
                raise
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=2)
                job.finished_at = now()
                session.commit()

    def _heartbeat_loop(self, job_id, stop: threading.Event):
        while not stop.wait(HEARTBEAT_INTERVAL_S):
            with self.session_maker() as session:
                touch_heartbeat(session, job_id)
