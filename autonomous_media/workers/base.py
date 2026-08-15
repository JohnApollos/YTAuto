import threading
import time
from abc import ABC, abstractmethod
from autonomous_media.db.models import Job
from autonomous_media.exceptions import StageUnrecoverableError, QuotaExceededError
from autonomous_media.logging import emit_event
from sqlalchemy.orm import Session

HEARTBEAT_INTERVAL_S = 20

def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

def touch_heartbeat(session: Session, job_id: str):
    from autonomous_media.db.models import Job
    try:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.last_heartbeat_at = now()
            session.commit()
    except Exception:
        pass

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
            
            from autonomous_media.profiling import ProfileStageContext

            try:
                with ProfileStageContext(stage_name=job.type, job_id=str(job.id), trace_id=job.trace_id):
                    result = self.process(session, job)
                job.status = "succeeded"
                emit_event(f"{job.type}.completed", job.trace_id, result.summary())
                session.commit()
                return result
            except StageUnrecoverableError as e:
                job.status = "dead_letter"
                job.error = str(e)
                session.commit()
                emit_event("job.dead_letter", job.trace_id, {"type": job.type, "job_id": str(job.id), "error": str(e), "attempts": job.attempts, "max_attempts": job.max_attempts})
                raise
            except QuotaExceededError as e:
                from zoneinfo import ZoneInfo
                from datetime import datetime, time as dt_time, timedelta, timezone
                
                # Compute next midnight Pacific
                pacific = ZoneInfo("America/Los_Angeles")
                now_pacific = datetime.now(pacific)
                tomorrow_pacific = now_pacific + timedelta(days=1)
                midnight_pacific = datetime.combine(tomorrow_pacific.date(), dt_time.min, tzinfo=pacific)
                next_midnight_utc = midnight_pacific.astimezone(timezone.utc)
                
                job.scheduled_at = next_midnight_utc
                job.status = "retrying"
                job.error = f"QuotaExceededError: deferred until midnight Pacific. Details: {e}"
                session.commit()
                emit_event("quota.warning", job.trace_id, {"type": job.type, "job_id": str(job.id), "error": str(e)})
                raise
            except Exception as e:
                job.attempts += 1
                is_dead = job.attempts >= job.max_attempts
                job.status = "dead_letter" if is_dead else "retrying"
                job.error = str(e)
                session.commit()
                evt_name = "job.dead_letter" if is_dead else "job.failed"
                emit_event(evt_name, job.trace_id, {"type": job.type, "job_id": str(job.id), "error": str(e), "attempts": job.attempts, "max_attempts": job.max_attempts, "will_retry": not is_dead})
                raise
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=2)
                job.finished_at = now()
                session.commit()
                import gc
                gc.collect()

    def _heartbeat_loop(self, job_id, stop: threading.Event):
        while not stop.wait(HEARTBEAT_INTERVAL_S):
            with self.session_maker() as session:
                touch_heartbeat(session, job_id)
