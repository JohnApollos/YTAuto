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
HEARTBEAT_TIMEOUT_S = 90  # 90 seconds — workers heartbeat every 20s, so 90s quickly recovers dead workers
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
        # Instantly recover any orphaned 'running' jobs left behind by previous process shutdown
        self._recover_orphaned_running_jobs()
        while self.running:
            try:
                self._seed_poll_jobs()
                self._recover_stuck_jobs()
                self._poll()
            except Exception as e:
                logger.error(f"Scheduler poll error: {e}", extra={"trace_id": "scheduler"})
            time.sleep(POLL_INTERVAL_S)

    def _recover_orphaned_running_jobs(self):
        """
        On scheduler startup, any job left in 'running' state was orphaned when the process shut down.
        Instantly reset them to 'queued' or 'retrying' so the system resumes immediately.
        """
        with self.session_maker() as session:
            orphaned = session.query(Job).filter(Job.status == "running").all()
            if orphaned:
                logger.info(
                    f"Startup Recovery: Re-queuing {len(orphaned)} orphaned jobs left running from previous process run",
                    extra={"trace_id": "scheduler"}
                )
                for job in orphaned:
                    job.attempts += 1
                    job.status = "queued" if job.attempts < job.max_attempts else "dead_letter"
                    job.error = "Process restarted while job was running — automatically requeued on boot"
                session.commit()

    def stop(self):
        self.running = False
        logger.info("Scheduler stopped", extra={"trace_id": "scheduler"})

    def _seed_poll_jobs(self):
        """
        Scan active ContentSource items and enqueue acquisition jobs when they are due.
        """
        from datetime import datetime, timezone, timedelta
        from autonomous_media.db.models import ContentSource, Job
        
        now_utc = datetime.now(timezone.utc)
        
        with self.session_maker() as session:
            active_sources = session.query(ContentSource).filter(
                ContentSource.active == True,
                ContentSource.type.in_(["youtube_channel", "reddit_scraper", "curated_story"])
            ).all()
            if not active_sources:
                return
            
            # Query all pending/running acquisition jobs
            pending_jobs = (
                session.query(Job)
                .filter(
                    Job.type == "acquisition",
                    Job.status.in_(["queued", "running", "retrying"])
                )
                .all()
            )
            # Find the set of content source IDs that already have pending acquisition jobs
            pending_source_ids = set()
            for job in pending_jobs:
                src_id = job.payload.get("source_id")
                if src_id:
                    pending_source_ids.add(str(src_id))
            
            for source in active_sources:
                source_id_str = str(source.id)
                if source_id_str in pending_source_ids:
                    continue
                
                poll_interval_minutes = source.config.get("poll_interval_minutes", 60)
                last_polled = source.last_polled_at
                
                if last_polled is not None:
                    if last_polled.tzinfo is None:
                        last_polled = last_polled.replace(tzinfo=timezone.utc)
                    if now_utc - last_polled < timedelta(minutes=poll_interval_minutes):
                        continue
                
                # Polling is due, seed the acquisition job
                logger.info(
                    f"Seeding acquisition job for content source {source.id}",
                    extra={"trace_id": f"poll-seed-{source.id}"}
                )
                new_job = Job(
                    type="acquisition",
                    payload={"source_id": source_id_str},
                    channel_id=source.channel_id,
                    priority=5,
                    attempts=0,
                    max_attempts=3,
                    trace_id=f"poll-{source.id}"
                )
                session.add(new_job)
            
            session.commit()

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
