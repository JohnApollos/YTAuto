"""
Scheduler & Job Orchestrator — spec §12.1.

The only component that decides 'what runs next'. Polls content_sources
on their configured interval, creates jobs, enforces max_concurrent_jobs,
applies heartbeat-timeout detection, and routes exhausted retries to dead-letter.

The Scheduler itself is stateless relative to job state — all state lives in
jobs/Postgres, so restarting the Scheduler process mid-operation is safe.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from autonomous_media.db.models import Job
from autonomous_media.logging import get_logger

logger = get_logger("scheduler")

# Spec §12.1: jobs stuck 'running' beyond this threshold are presumed dead
HEARTBEAT_TIMEOUT_S = 120  # 2 minutes — tune downward after NFR-3 benchmark run
POLL_INTERVAL_S = 5


class Scheduler:
    """
    Simple polling-loop scheduler for V1 (sequential, spec §19).
    Dispatch is WORKER_REGISTRY[job.type].run(job).
    Worker concurrency is controlled by max_concurrent_jobs (config),
    not hardcoded here — scaling from 1 to N is a config change (spec §19).
    """

    def __init__(self, session_maker, worker_registry: dict | None = None, max_concurrent_jobs: int = 1):
        self.session_maker = session_maker
        self.worker_registry: dict = worker_registry or {}
        self.max_concurrent_jobs = max_concurrent_jobs
        self.running = False

    def start(self):
        logger.info("Scheduler starting", extra={"trace_id": "scheduler"})
        self.running = True
        while self.running:
            try:
                self._recover_stuck_jobs()
                self._poll()
            except Exception as e:
                logger.error(f"Scheduler poll error: {e}", extra={"trace_id": "scheduler"})
            time.sleep(POLL_INTERVAL_S)

    def stop(self):
        self.running = False
        logger.info("Scheduler stopped", extra={"trace_id": "scheduler"})

    def _poll(self):
        """Dispatch queued jobs up to max_concurrent_jobs."""
        from sqlalchemy import or_
        from datetime import datetime, timezone
        
        with self.session_maker() as session:
            running_count = session.query(Job).filter(Job.status == "running").count()
            slots = max(0, self.max_concurrent_jobs - running_count)
            if slots == 0:
                return

            now_utc = datetime.now(timezone.utc)
            queued = (
                session.query(Job)
                .filter(
                    Job.status.in_(["queued", "retrying"]),
                    or_(Job.scheduled_at.is_(None), Job.scheduled_at <= now_utc)
                )
                .order_by(Job.priority.desc(), Job.created_at)
                .limit(slots)
                .all()
            )

            for job in queued:
                self._dispatch(session, job)

    def _dispatch(self, session: Session, job: Job):
        """Hand the job to the appropriate worker. Log unknown types rather than crashing."""
        worker = self.worker_registry.get(job.type)
        if worker is None:
            logger.warning(
                f"No worker registered for job type '{job.type}' — skipping job {job.id}",
                extra={"trace_id": job.trace_id},
            )
            return
        try:
            logger.info(
                f"Dispatching job {job.id} (type={job.type})",
                extra={"trace_id": job.trace_id},
            )
            worker.run(job)
        except Exception as e:
            logger.error(
                f"Job {job.id} failed: {e}",
                extra={"trace_id": job.trace_id},
            )

    def _recover_stuck_jobs(self):
        """
        Spec §12.1 heartbeat mechanism: find 'running' jobs whose
        last_heartbeat_at is older than HEARTBEAT_TIMEOUT_S and requeue
        them (consuming one attempt, same as any other failure).
        This handles Windows Update reboots, power loss, and silent hangs.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT_S)

        with self.session_maker() as session:
            stuck = (
                session.query(Job)
                .filter(
                    Job.status == "running",
                    Job.last_heartbeat_at < cutoff,
                )
                .all()
            )
            for job in stuck:
                logger.warning(
                    f"Heartbeat timeout on job {job.id} — requeuing (attempt {job.attempts + 1}/{job.max_attempts})",
                    extra={"trace_id": job.trace_id},
                )
                job.attempts += 1
                job.status = "retrying" if job.attempts < job.max_attempts else "dead_letter"
                job.error = "Heartbeat timeout — worker presumed dead"
            session.commit()
