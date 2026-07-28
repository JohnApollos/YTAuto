import threading
import time
from abc import ABC, abstractmethod
from autonomous_media.db.models import Task
from autonomous_media.exceptions import StageUnrecoverableError
from autonomous_media.logging import emit_event

HEARTBEAT_INTERVAL_S = 20

def now():
    from datetime import datetime
    return datetime.utcnow()

def touch_heartbeat(task_id):
    # Stub for updating heartbeat in DB
    pass

class TaskResult:
    def summary(self):
        return {}

class Worker(ABC):
    task_type: str

    @abstractmethod
    def process(self, task: Task) -> TaskResult:
        ...

    def run(self, task: Task) -> TaskResult:
        task.status = "running"
        task.started_at = now()
        stop_heartbeat = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, args=(task, stop_heartbeat), daemon=True
        )
        heartbeat_thread.start()
        try:
            result = self.process(task)
            task.status = "succeeded"
            emit_event(f"{self.task_type}.completed", task.trace_id, result.summary())
            return result
        except StageUnrecoverableError as e:
            task.status = "dead_letter"
            task.error = str(e)
            raise
        except Exception as e:
            task.attempts += 1
            task.status = "retrying" if task.attempts < task.max_attempts else "dead_letter"
            task.error = str(e)
            raise
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=2)
            task.finished_at = now()

    def _heartbeat_loop(self, task: Task, stop: threading.Event):
        while not stop.wait(HEARTBEAT_INTERVAL_S):
            touch_heartbeat(task.id)
