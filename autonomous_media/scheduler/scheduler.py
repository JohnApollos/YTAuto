import time
from sqlalchemy.orm import Session
from autonomous_media.db.models import Job

class Scheduler:
    def __init__(self, session_maker):
        self.session_maker = session_maker
        self.running = False

    def start(self):
        self.running = True
        while self.running:
            self._poll()
            time.sleep(5)

    def stop(self):
        self.running = False

    def _poll(self):
        with self.session_maker() as session:
            # Poll for queued jobs and dead jobs
            queued = session.query(Job).filter(Job.status == "queued").all()
            for job in queued:
                print(f"Dispatching job {job.id}")
