from autonomous_media.workers.base import Worker, JobResult
from sqlalchemy.orm import Session
from autonomous_media.db.models import Job

class TranscriptionWorker(Worker):
    job_type = 'transcription'

    def process(self, session: Session, job: Job) -> JobResult:
        # Stub implementation
        return JobResult()
