import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from autonomous_media.workers.base import Worker, JobResult
from autonomous_media.db.models import Job, SourcePost
from autonomous_media.logging import get_logger
from autonomous_media.exceptions import StageUnrecoverableError
from autonomous_media.runtime.manager import stage_manager
from autonomous_media.workers.narration import prepare_script

logger = get_logger("workers.script_preparation")

class ScriptPreparationWorker(Worker):
    job_type = 'script_preparation'

    def process(self, session: Session, job: Job) -> JobResult:
        source_post_id = job.payload.get("source_post_id")
        if not source_post_id:
            raise StageUnrecoverableError("Missing source_post_id in job payload")

        post = session.query(SourcePost).filter(SourcePost.id == uuid.UUID(source_post_id)).first()
        if not post:
            raise StageUnrecoverableError(f"SourcePost {source_post_id} not found")

        logger.info(
            f"Starting script preparation stage for SourcePost {post.id}",
            extra={"trace_id": job.trace_id}
        )

        post.status = "scripting"
        session.commit()

        # Run LLM script preparation (with raw text fallback)
        try:
            script_text = prepare_script(post.title, post.body_text, stage_manager)
        except Exception as e:
            logger.warning(
                f"LLM script preparation failed ({e}). Using raw title and body text as narration script.",
                extra={"trace_id": job.trace_id}
            )
            script_text = f"{post.title}\n\n{post.body_text}"

        post.script_text = script_text
        post.status = "scripted"
        session.commit()

        # Enqueue narration job
        next_job = Job(
            type="narration",
            payload={"source_post_id": str(post.id)},
            trace_id=job.trace_id,
            channel_id=job.channel_id,
            priority=job.priority,
            attempts=0,
            max_attempts=3
        )
        session.add(next_job)
        session.commit()

        logger.info(
            f"Successfully prepared script for SourcePost {post.id}, enqueued narration job",
            extra={"trace_id": job.trace_id}
        )

        return JobResult()
