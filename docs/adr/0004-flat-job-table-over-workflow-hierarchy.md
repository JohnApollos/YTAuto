# ADR 0004 — Flat Job Table Over Workflow-Stage-Task Hierarchy

**Date:** 2026-07-28
**Status:** Accepted
**Supersedes:** The `Workflow → WorkflowStage → Task` hierarchical model used in the pre-v1.2 codebase.

## Context

The original implementation modelled the processing pipeline as a three-level hierarchy: a `Workflow` (one per source video), containing `WorkflowStage` objects (acquisition, transcription, scoring, etc.), each containing one or more `Task` rows. This was carried over from an enterprise pattern where hierarchical state is useful for aggregating status across distributed workers.

For a single-operator system running on one machine with sequential processing, this hierarchy introduced complexity without benefit:

- Adding a new pipeline stage required adding a new `WorkflowStage` type and wiring it into the hierarchy.
- Querying "what needs to run next" required joining three tables.
- The hierarchy implied a fixed, pre-defined pipeline shape — but the actual pipeline (what stages run, in what order, conditioned on what) is better expressed as a job enqueuing chain.
- Dead-letter handling, retry logic, and heartbeat tracking all had to be implemented three times (once at each level).

## Decision

Replace the three-level hierarchy with a **flat `Job` table**. Every unit of work is one row in `jobs` with:

- `type` — the worker that should handle it (e.g. `"acquisition"`, `"transcription"`, `"scoring"`)
- `status` — the state machine value (`queued`, `running`, `succeeded`, `retrying`, `dead_letter`, `cancelled`)
- `payload` — a JSON blob with the arguments the worker needs
- `channel_id` — FK for channel-scoped jobs
- `trace_id` — a propagated correlation ID linking all jobs that originated from the same source video
- `last_heartbeat_at` — supports the liveness mechanism (spec §12.1)
- `attempts` / `max_attempts` — retry control

The pipeline shape is encoded in the workers themselves: a successful `AcquisitionWorker` enqueues a `TranscriptionWorker` job; a successful `TranscriptionWorker` enqueues a `ScoringWorker` job; etc.

## Consequences

**Positive:**
- "What needs to run next?" is a single `SELECT` with a `WHERE status IN ('queued', 'retrying') ORDER BY priority, created_at` — no joins.
- Adding a new pipeline stage is adding a new `Worker` class and one `session.add(Job(...))` call in the triggering stage. No schema migration for the new stage type.
- Retry, dead-letter, and heartbeat logic live in exactly one place: `workers/base.py`.
- A `trace_id` on every job row makes the full lifecycle of any clip reconstructable with one `system_events` query.

**Negative:**
- The pipeline shape is implicit (embedded in worker logic) rather than explicit (queryable from the database). To understand the full pipeline, you read the worker code, not the schema.
- Aggregating progress across all jobs for a single source video requires filtering `jobs` by `trace_id`, not traversing a `Workflow` parent row.

Both negatives are acceptable for a single-operator, single-machine system. The `system_events` table provides the audit trail that partially compensates for the lack of an explicit pipeline graph.
