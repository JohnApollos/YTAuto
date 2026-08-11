# Autonomous Media — Developer Guide

**Companion to:** `autonomous-media-technical-specification.md` (v1.1)
**Purpose:** the specification defines *what* the system does and *why*; this document is *how you actually build it*, in what order, with what conventions.
**Audience:** whoever is writing the code — which, for V1, is one person.

---

## How to Use This Document

Every chapter below assumes the Technical Specification is open in the other tab and does not re-explain decisions already made there — it links to the relevant section (§) and tells you what to actually type, create, or run. If a chapter here ever seems to disagree with the spec, the spec wins; file the discrepancy and fix this document, not the other way around.

Chapters, in the order you'll actually use them:

0. [How to Use This Document](#how-to-use-this-document) *(you are here)*
1. [Environment Setup](#1-environment-setup)
2. [Project & Module Structure](#2-project--module-structure)
3. [Database Setup & Migrations](#3-database-setup--migrations)
4. [The Worker Framework](#4-the-worker-framework)
5. [Building Your First Vertical Slice](#5-building-your-first-vertical-slice)
6. [Testing Conventions](#6-testing-conventions)
7. [Coding Standards](#7-coding-standards)
8. [Release Process](#8-release-process)
9. [How-To Recipes](#9-how-to-recipes)
10. [Development Milestones](#10-development-milestones)

---

## 1. Environment Setup

These steps are Windows-specific, matching the operator's actual machine (spec §13.1).

1. **Python 3.11+.** The codebase leans on modern typing (`X | None` unions, `Protocol` classes) used throughout the spec's pseudocode — don't go older.
2. **Docker Desktop, WSL2 backend enabled** (Settings → General → "Use the WSL 2 based engine"). This is materially more efficient than the legacy Hyper-V backend (spec §13.4) and is not the default on every install, so verify it explicitly rather than assuming.
3. **Clone the repo, create a virtual environment, install dependencies:**
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Bring up the stateful services only** (the model runtime stays native on the host — see step 6):
   ```
   docker compose up -d postgres redis minio
   ```
5. **Enable `pgvector` on the fresh Postgres instance** (needed for the `topics.embedding` column, spec §8.3):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
6. **Set up the local model runtime — one persistent process, natively on Windows, not in Docker** (spec §13.3). This is the step most likely to silently go wrong, so verify it explicitly rather than assuming it worked:
   - Obtain or compile a **Vulkan-enabled** `llama.cpp`/`llama-server` build (or, if using Ollama, confirm the specific build in use actually exercises its Vulkan path on this GPU rather than silently falling back to CPU).
   - Start it **once, as a long-lived process**, not something you launch and kill per pipeline stage — `swap`-mode "unload" (spec §12.9) means telling this already-running server to drop the current model, not stopping the process itself.
   - Run one test inference and **watch GPU utilization in Task Manager while it runs.** If GPU usage stays flat at 0% during inference, it's running on CPU — that's the exact failure mode spec §13.3 warns about, and it will not announce itself with an error.
   - Note its port — containerized workers (running in Docker) reach this native host process at `http://host.docker.internal:<port>`, **not** `http://localhost:<port>`, which inside a container resolves to the container itself (spec §13.4).
   - Whisper and FFmpeg are unaffected by any of this (spec §20.1) — verify them separately and don't let a Vulkan problem block getting transcription working.
7. **`.env` file** (never committed — add to `.gitignore` immediately, per spec §14.2):
   ```
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://localhost:6379
   MINIO_ENDPOINT=...
   MINIO_ACCESS_KEY=...
   MINIO_SECRET_KEY=...
   YOUTUBE_OAUTH_CLIENT_ID=...
   YOUTUBE_OAUTH_CLIENT_SECRET=...
   JWT_SECRET=...
   MODEL_RESIDENCY=swap
   ```
8. **First migration and smoke test:**
   ```
   alembic upgrade head
   uvicorn autonomous_media.api.main:app --reload
   curl http://localhost:8000/api/v1/system/health
   ```
   A 200 response here means the database, the API, and your environment variables all agree with each other. If anything above is misconfigured, this is where it surfaces — cheaply, before you've written any pipeline code.

---

## 2. Project & Module Structure

The package layout mirrors the spec's component names directly — if you're looking for the code behind "the Editing Engine," it's in `workers/editing.py`, not buried inside a generically-named `services/` folder.

```
autonomous-media/
  autonomous_media/
    api/                       # FastAPI routers — auth, channels, sources, jobs, clips, system, telegram
    db/
      models.py                # SQLAlchemy models (includes TelegramConfig & TelegramDeliveryLog)
      migrations/               # Alembic environment + versions/
    scheduler/
      scheduler.py              # spec §12.1
      queue.py                  # Redis Streams wrapper, spec §7.3
    services/
      telegram/                # Telegram alert & remote ops subsystem
        models.py              # AlertSeverity, AlertCategory, AlertEvent
        client.py              # Telegram HTTP client with exponential backoff
        formatter.py           # HTML / MarkdownV2 escaping & card templates
        policies.py            # Severity classification & quiet hours engine
        deduplication.py       # 300s fingerprinting & incident correlator
        commands.py            # Bot command dispatcher (/status, /jobs, /review)
        notifier.py            # Singleton async queue service
    workers/
      base.py                  # Worker base class with heartbeat & event emission
      acquisition.py           # spec §12.2
      transcription.py         # spec §12.3
      intelligence.py          # spec §12.4 / §11.1
      vision.py                # spec §12.5
      editing.py               # spec §12.6
      rendering.py             # spec §12.7
      quality_gate.py          # spec §12.8
      publishing.py           # spec §12.10
  frontend/                    # Modular React 19 + Vite 8 control center
    src/
      components/              # UI primitives (Badge, ToastStack)
      features/                # Modular view features (stories, jobs, settings, etc.)
      hooks/                   # Custom React hooks (useToast)
      services/                # API client wrapper (api.ts)
      types/                   # TypeScript interfaces
```
      publishing.py                # spec §12.11
      analytics.py                  # spec §12.12
      learning.py                    # spec §11.6 / §12.9 (residual, not the model runtime)
    sources/
      base.py                    # ContentSource protocol, spec §11.3
      youtube_clip.py             # the only implementation shipped in V1
      ai_story.py                  # stub, V2
    runtime/
      base.py                    # ModelRuntime protocol, spec §12.9
      vulkan_llm.py                # Qwen 3 8B via the Vulkan runtime
      whisper_asr.py
      vision_vlm.py                 # Qwen2.5-VL
      registry.py                    # StageModelManager, spec §12.9
    rights/
      gate.py                    # spec §11.4
    prompts/                     # versioned prompt files, spec §25.8
      scoring_v3.txt
      title_v1.txt
      description_v1.txt
      grounding_v1.txt
    config.py                    # the Pydantic schema from spec §25.6 lives here
    events.py                    # event type constants, spec §7.3
    exceptions.py                 # ModelTimeoutError, MalformedOutputError, StageUnrecoverableError — Chapter 7
  eval/
    benchmark_v1.jsonl            # spec §25.9 — checked in, versioned, never edited in place
    run_eval.py                    # computes spec §18.1's metrics against the benchmark set
  dashboard/                      # React + Tailwind, spec §12.14
  docker/
    docker-compose.yml
  tests/
    unit/
    integration/
    e2e/
  docs/
    technical-specification.md      # the v1.1 spec itself, checked in for reference
    developer-guide.md               # this document
  alembic.ini
  requirements.txt
  .env.example
```

One rule worth stating explicitly: **a new capability gets a new file in the relevant package, not a new top-level folder.** If you're about to create a folder that isn't in the tree above, that's a signal to re-read spec §7.1's modular-monolith reasoning before doing it — the whole point of that decision was avoiding sprawl.

---

## 3. Database Setup & Migrations

### 3.1 Translating the spec's tables into SQLAlchemy

`db/models.py` mirrors spec §8.3 directly. You don't need to translate all twelve tables before writing any code — translate the ones the vertical slice in Chapter 5 actually touches first (`channels`, `content_sources`, `source_videos`, `jobs`), and add the rest as you reach them. Two examples to establish the pattern:

```python
# db/models.py
import uuid
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .base import Base

class Channel(Base):
    __tablename__ = "channels"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True)
    niche: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    language: Mapped[str] = mapped_column(String, default="en")
    project_id: Mapped[str] = mapped_column(String)  # spec §5.1, §8.3 — which Google Cloud project's quota pool this channel uploads through
    target_duration_min_s: Mapped[int] = mapped_column(Integer)
    target_duration_max_s: Mapped[int] = mapped_column(Integer)
    caption_style: Mapped[str] = mapped_column(String)
    music_profile: Mapped[str] = mapped_column(String)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)
    upload_cadence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    content_sources: Mapped[list["ContentSourceRow"]] = relationship(back_populates="channel")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "succeeded", "failed", "retrying", "dead_letter", "cancelled",
             name="job_status"),
        default="queued",
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    last_heartbeat_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)  # spec §12.1 — the worker touches this every 15-30s while `running`
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped["DateTime | None"] = mapped_column(DateTime, nullable=True)
```

The `jobs.status` enum matches the state machine in spec §7.4 exactly — that diagram is the source of truth for which values are valid, not this file.

### 3.2 The `topics.embedding` column

Needs the `pgvector` SQLAlchemy integration (`sqlalchemy-pgvector` or equivalent):

```python
from pgvector.sqlalchemy import Vector

class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))  # dimension must match your embedding model's output
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
```

Add the `ivfflat`/`hnsw` index from spec §8.4 in the Alembic migration, not as a model default — index tuning parameters belong in migrations, where they're versioned and reviewable, not hidden in ORM metadata.

### 3.3 Migration workflow

```
alembic init db/migrations          # once, at project start
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Every schema change from here forward is a new `alembic revision --autogenerate`, reviewed by hand before `upgrade head` — autogenerate is a first draft, not a guarantee, especially for the `pgvector` index and any check constraints on enum-like string columns. Spec §15.3's rule applies from the very first migration, not just once the system is "in production": back up the database before running `upgrade head` against anything that isn't a throwaway dev instance.

---

## 4. The Worker Framework

### 4.1 The `Worker` base class

The spec defines *what* each engine does (§12.1–§12.13) but doesn't hand you an actual base class — here it is. Every job-type worker inherits from this; the retry/error-handling logic lives here once, not copy-pasted into every worker:

```python
# workers/base.py
import threading
from abc import ABC, abstractmethod
from autonomous_media.db.models import Job
from autonomous_media.exceptions import StageUnrecoverableError

HEARTBEAT_INTERVAL_S = 20   # spec §12.1's "every 15-30 seconds" — tune once NFR-3's benchmark exists

class Worker(ABC):
    job_type: str          # e.g. "download", "transcribe", "score_clips" — matches jobs.type

    @abstractmethod
    def process(self, job: Job) -> "JobResult":
        """Do the actual work. Raise a specific exception (Chapter 7) on
        failure — never return a success result for a job that didn't
        actually succeed, and never swallow an exception to avoid a
        retry. The Scheduler, not the worker, decides what retrying
        means (spec §7.4)."""
        ...

    def run(self, job: Job) -> "JobResult":
        """Called by the Scheduler. Handles the parts every worker
        needs identically — including the heartbeat (spec §12.1) — so
        individual workers only implement `process` and never have to
        remember to touch last_heartbeat_at themselves."""
        job.status = "running"
        job.started_at = now()
        stop_heartbeat = threading.Event()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, args=(job, stop_heartbeat), daemon=True
        )
        heartbeat_thread.start()
        try:
            result = self.process(job)
            job.status = "succeeded"
            emit_event(f"{self.job_type}.completed", job.trace_id, result.summary())
            return result
        except StageUnrecoverableError as e:
            job.status = "dead_letter"
            job.error = str(e)
            raise
        except Exception as e:
            job.attempts += 1
            job.status = "retrying" if job.attempts < job.max_attempts else "dead_letter"
            job.error = str(e)
            raise
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=2)
            job.finished_at = now()

    def _heartbeat_loop(self, job: Job, stop: threading.Event):
        """Runs in the background for the lifetime of `process()`. The
        Scheduler's own poll loop (spec §12.1) is what actually acts on
        a stale last_heartbeat_at — this thread only keeps it fresh."""
        while not stop.wait(HEARTBEAT_INTERVAL_S):
            touch_heartbeat(job.id)   # a small, separate DB write — not the same session as the main job update
```

A new worker never needs to think about any of this — `_heartbeat_loop` lives once in the base class, and the Scheduler process that later notices a stale `last_heartbeat_at` (spec §12.1) doesn't care which worker subclass produced it.

### 4.2 Registering a worker against a job type

A simple registry, not a dependency-injection framework — this system doesn't need one at this scale:

```python
# workers/__init__.py
WORKER_REGISTRY: dict[str, Worker] = {}

def register(job_type: str):
    def decorator(cls):
        WORKER_REGISTRY[job_type] = cls()
        return cls
    return decorator

# workers/acquisition.py
@register("download")
class AcquisitionWorker(Worker):
    job_type = "download"
    def process(self, job: Job) -> JobResult:
        ...
```

The Scheduler's dispatch is then `WORKER_REGISTRY[job.type].run(job)` — adding a worker never touches the Scheduler's code, only adds an entry to this dict (see Chapter 9's recipe for the full add-a-worker checklist).

### 4.3 `ContentSource` and `ModelRuntime`, as actual interfaces

These are defined conceptually in spec §11.3 and §12.9; `sources/base.py` and `runtime/base.py` are where they become real, importable `Protocol` classes that `youtube_clip.py`, `vulkan_llm.py`, etc. implement against. Copy the signatures directly from those spec sections — this guide doesn't repeat them here to avoid the two copies drifting apart; if you change one, change the spec, not just the code.

---

## 5. Building Your First Vertical Slice

This is the answer to "which module do I implement first?" The temptation with a system this thoroughly specified is to start building the Intelligence Engine, or the Model Runtime Manager, because that's where the interesting engineering is. Resist it. Build a **walking skeleton** first: the thinnest possible path from "one video URL" to "a row in `clip_candidates`," with every stage as dumb as possible, so you prove the *shape* of the system — job orchestration, state persistence, storage, event flow — before you invest in making any one stage smart.

Concretely, in this order:

**Step 1 — Infra up.** Chapters 1–3. You should be able to `curl` the health endpoint and see an empty `channels` table before writing a single worker.

**Step 2 — A trivial job loop, before Redis Streams.** Literally a `while True: poll for queued jobs, dispatch, sleep(2)` loop against the `jobs` table directly. This is intentionally not the real Scheduler (spec §12.1) yet — you're proving worker dispatch and status transitions work before adding a message broker on top. Swap in Redis Streams once this works, not before.

**Step 3 — One hardcoded content source.** Implement `YouTubeClipSource.discover()` against a single test channel ID you've hardcoded, not a real `content_sources` config row yet. **Use `playlistItems.list` on the channel's uploads playlist, not `search.list`** (spec §5.1) — this is the single easiest mistake to make on a first pass, because `search` is the more obvious-looking endpoint, and it will burn your entire day's quota in a handful of calls if you reach for it here.

**Step 4 — Acquisition worker, for real.** Download the video, extract audio, write both to MinIO, write the `source_videos` row. No error handling beyond "don't crash the loop" yet.

**Step 5 — Transcription worker, CPU is fine.** Wire up Whisper. Don't block this step on getting the Vulkan GPU path working (step 6's model runtime will need it; this step doesn't) — a CPU transcription that takes five minutes instead of thirty seconds still proves the pipeline shape.

**Step 6 — A stub scorer, not the real Intelligence Engine.** Pick the middle 45 seconds of the transcript. Write it to `clip_candidates` as if it were the output of real scoring. This is deliberately fake — the goal of this step is confirming a job can flow all the way from "download requested" to "candidate selected" and land in `succeeded` status with the right rows in the right tables. You are not trying to prove the AI is good yet.

**Step 7 — Confirm the skeleton.** One full run, one hardcoded channel, one video, ends with: a `source_videos` row, a `transcripts` row (with the real transcript in MinIO), a `clip_candidates` row (with fake but plausible start/end times), and the job's row showing `status = succeeded`. If you can see all four of those after running the loop once, the architecture works end to end. Everything from here is making each stage smarter, not proving the shape again.

**Step 8 — Only now, wire in real intelligence.** Replace step 6's stub with the actual Model Runtime Manager (Chapter 4.3, spec §12.9) and the real scoring prompt (`prompts/scoring_v3.txt`, spec §25.8). This is also the point where it's worth setting up the Vulkan model runtime for real (step 5 didn't need it; this step does) and running your first pass against the benchmark set (spec §25.9) to get a baseline Precision@5 before you've tuned anything — you want that baseline number to exist before you start iterating, not after.

Everything past this point — Vision, Editing, Rendering, the Quality Gate, the Rights Gate, Publishing — follows the same discipline: get a dumb version flowing through the pipeline before making it good. The spec's Phase 1 checklist (§27) tells you *what* needs to exist by the end of the phase; this chapter's sequencing tells you the *order* that gets you there without spending three weeks debugging job orchestration and clip scoring at the same time.

---

## 6. Testing Conventions

Matches the pyramid in spec §18; this is the concrete "how," not a restatement of "why."

- **`tests/unit/`** — pure functions: scoring math, config validation, state-machine transition rules. No database, no Docker services running.
- **`tests/integration/`** — pipeline stage-to-stage, with `ContentSource` and `ModelRuntime` mocked (spec §18's table explains why those two interfaces exist partly *for* this). Example:
  ```python
  class FakeModelRuntime(ModelRuntime):
      def infer(self, request, timeout_s):
          return InferenceResult(scores={"hook_strength": 80, ...})  # deterministic, no real inference

  def test_intelligence_worker_selects_top_candidate(fake_transcript):
      worker = IntelligenceWorker(runtime=FakeModelRuntime())
      result = worker.process(job_for(fake_transcript))
      assert result.selected_clips[0].scores.overall > result.selected_clips[1].scores.overall
  ```
- **`tests/e2e/`** — one fixture podcast video through the real pipeline in a test environment (real Docker services, real FFmpeg, still-mocked YouTube API), asserting on output duration, aspect ratio, caption presence, loudness target (spec §18's table).
- **`eval/run_eval.py`** — not a pytest suite; a separate harness that runs the current scoring prompt/model against `benchmark_v1.jsonl` (spec §25.9) and writes an `eval_runs` row (spec §8.3) with the metrics from spec §18.1. Wired into CI as a required check before merging any change that touches a prompt, a scoring weight, or a model version — this is the promotion gate from §18.1, operationalized.

---

## 7. Coding Standards

- **Type hints everywhere.** The architecture leans on `Protocol` and Pydantic throughout (spec §12.9, §25.6) — untyped code fights the design rather than fitting it.
- **A real exception hierarchy**, since the spec's pseudocode already names specific exception types without defining them — define them once, here:
  ```python
  # exceptions.py
  class AutonomousMediaError(Exception): ...
  class ModelTimeoutError(AutonomousMediaError): ...
  class MalformedOutputError(AutonomousMediaError): ...
  class StageUnrecoverableError(AutonomousMediaError): ...
  class QuotaExceededError(AutonomousMediaError): ...
  class RightsBlockedError(AutonomousMediaError): ...
  ```
  Workers raise these specifically, not a bare `Exception` — `Worker.run()` (Chapter 4.1) and the Model Runtime Manager (spec §12.9) both branch on exception type to decide retry vs. fallback vs. dead-letter, so a bare `except Exception: raise RuntimeError(...)` anywhere in a worker silently breaks that logic.
- **Structured logging, every call site.** `trace_id` is not optional (spec §17.1) — a logging wrapper that requires it as a positional argument, rather than a convention you have to remember, catches the omission at write-time instead of at 2am during an incident:
  ```python
  logger.info("clip.scored", trace_id=job.trace_id, clip_id=clip.id, overall_score=score.overall)
  ```
- **Docstrings on anything public**: one-line summary, then `Args`/`Returns` if the signature isn't self-explanatory from type hints alone. Don't document what the type hints already say.

---

## 8. Release Process

1. Version bump (`pyproject.toml` or equivalent) and a changelog entry — this document and the spec both use semantic versioning (spec §15.3); the codebase should too.
2. Run the eval harness (Chapter 6) — no merge to `main` on a scoring/prompt/model change without a passing promotion-gate result (spec §18.1).
3. `alembic upgrade head --sql` (dry-run, prints the SQL without executing) against a copy of the real database before running it for real — catch a destructive migration before it's irreversible, not after.
4. **Back up the database** (spec §21.1) immediately before any real migration runs against the actual operating instance — not "we'll back up regularly," but specifically gated on "right before this migration."
5. Tag the release, deploy (in V1, "deploy" means pulling new images and restarting the local Docker Compose stack — spec §15.1 is explicit that this doesn't need to be more elaborate than that yet).
6. Watch the dashboard's job/error rate for the first few pipeline runs after a release before considering it good — the chaos-testing scenarios in spec §18 describe what to do if something's wrong, but the fastest fix is catching it in the first ten minutes, not the first ten hours.

---

## 9. How-To Recipes

Short, concrete answers to the questions that come up constantly once the system exists and is being extended.

### Add a new worker
1. Pick a `job_type` string (e.g. `"generate_thumbnail"`).
2. Subclass `Worker` (Chapter 4.1) in `workers/<name>.py`, implement `process()`.
3. Decorate it `@register("generate_thumbnail")`.
4. Add `"generate_thumbnail"` to the `jobs.type` check constraint (a small Alembic migration).
5. Have whichever upstream stage should trigger it create a `Job` row with that type and the right `payload`.
6. Add an integration test with a mocked dependency, per Chapter 6.

### Register a new model (e.g., swapping in a newer reasoning model)
1. Add a row to the `models` table (spec §8.3) with its `resource_profile` (RAM/VRAM/quantization).
2. Implement `ModelRuntime` for it in `runtime/<name>.py`.
3. Register it in `runtime/registry.py` against the relevant pipeline `stage`.
4. **Before promoting it over the current model**, run it through `eval/run_eval.py` (Chapter 6, spec §18.1) against the benchmark set — the comparative table in spec §25.7 is your starting hypothesis about whether it's worth trying, not a substitute for actually measuring it on this system's own data.
5. Only flip `StageModelManager`'s registry entry once the eval run shows no regression.

### Add a new job type (distinct from adding a worker — sometimes you need a new job type that an *existing* worker's logic branches on, not a new worker)
1. Define the payload shape (a Pydantic model, alongside the config schema in `config.py`).
2. Decide which existing or new worker handles it, and add the dispatch/branch logic.
3. Add the type string to the `jobs.type` constraint.
4. Add a state-machine test (Chapter 6) confirming it transitions through `queued → running → succeeded/failed` correctly — the state machine in spec §7.4 is generic across job types, but it's worth confirming a genuinely new type doesn't have a stage-specific edge case (e.g., a job type that has no meaningful "retry," only "skip").

### Add a new content source (e.g., an RSS feed, ahead of schedule)
1. Implement `ContentSource` (Chapter 4.3, spec §11.3) in `sources/<name>.py` — `discover()` and `fetch()`.
2. Add the new value to the `SourceType` enum in `config.py` (spec §25.6).
3. A channel adopts it by adding a `content_sources` row with that `type` — no changes anywhere else in the pipeline, which is the entire point of the abstraction (spec §11.3). If you find yourself needing to touch the Scheduler, the Editing Engine, or anything downstream of "raw media in hand" to add a source, something has leaked outside the interface and is worth stopping to fix before continuing.

---

## 10. Development Milestones

More granular than spec §27's checklist, and sequenced — this is the order, not just the list, matching Chapter 5's walking-skeleton philosophy. Rough scope, not committed dates:

| Milestone | Scope | Roughly corresponds to |
|---|---|---|
| M1 | Infra up: Postgres/Redis/MinIO/Alembic/FastAPI health check (Chapters 1–3) | Spec §27 Phase 0 |
| M2 | Walking skeleton: one hardcoded channel, stub scorer, a job reaches `succeeded` end to end (Chapter 5, steps 1–7) | Spec §27 Phase 0 → 1 boundary |
| M3 | Real transcription + real scoring: Model Runtime Manager wired in, batched scoring prompt live (spec §11.1), novelty/dedup working. Label the 50-episode benchmark set (40 dev / 10 hold-out, spec §25.9) and run the ~2-hour-episode benchmark (NFR-3) to get real per-stage timings and a real Precision@5 baseline — both before tuning starts, not after | Spec §27 Phase 1 |
| M4 | Vision (only the selected clip windows, spec §7.5/§12.5) + Editing + Rendering: crop, captions, silence trim, music, branding, automated QC gate | Spec §27 Phase 1 |
| M5 | Rights Gate + Publishing: the quota-aware, rights-gated real YouTube upload — **build the Rights Gate before this milestone's first real upload, not after** (spec §11.4, §27 explicitly calls this out) | Spec §27 Phase 1 completion |
| M6 | Analytics polling + Learning Engine's weighted-average allocation + dashboard clip-review UI (the manual safety net, spec §10.1) | Spec §27 Phase 2 start |
| M7 | Second and third channel configured via data alone, no code changes — this is the milestone that actually proves the "channels submit jobs, they don't own pipelines" claim (spec §7.1), rather than just asserting it | Spec §27 Phase 2 |

Each milestone should end with something *observable* — a real clip in a real channel's inventory, a real dashboard screen, a real eval score — not just "the code for X exists." If a milestone is taking meaningfully longer than the phase estimates in spec §28 suggest, that's useful signal about where this specific project's actual complexity lives, worth feeding back into the spec rather than pushing through silently.

## §26 — Initial Setup After Deployment

After running `alembic upgrade head` and starting both the API server and the scheduler, the database contains no channels or content sources. Complete these steps **once** in the dashboard (http://localhost:8000) before the pipeline will process anything.

### Step 1 — Create a Channel
1. Open the **Setup** tab.
2. In the **Channels** section, fill in: Name (your YouTube channel name), Slug (URL-friendly ID), Niche (e.g. "tech podcasts"), Google Cloud Project ID (from your GCP console — this is the quota pool identifier), and YouTube Data API v3 Key.
3. Click **Add Channel**. The channel appears in the list.

### Step 2 — Add a Content Source
1. In the **Content Sources** section, select your new channel.
2. Enter the **YouTube Channel ID** of the source podcast to clip (e.g. `UCxxxxxxxxxxxxxxxxxxxxxx`). Find this on YouTube: go to the channel → About → Share → Copy channel ID.
3. Set the **Poll Interval** (recommended: 60 minutes).
4. Click **Add Source**.

### Step 3 — Set Rights Status
1. In the **Rights & OAuth** section, select your source from the dropdown.
2. Set status to `owned` (you own the content) or `licensed` (you have a license). Without this, the publishing worker will block all uploads.
3. Optionally fill in an Evidence URL (e.g. a link to your license agreement).
4. Click **Save Rights**.

### Step 4 — Configure YouTube OAuth Credentials
1. In the same section, under **YouTube OAuth**, select your channel.
2. Paste your Access Token, Refresh Token, Client ID, and Client Secret from the Google Cloud OAuth flow.
   - To obtain these: In GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs, download the JSON, then run the one-time OAuth consent flow using `google-auth-oauthlib`.
3. Click **Save Credentials**.

Once these 4 steps are complete, the scheduler will automatically enqueue the first acquisition job within one poll interval. You can monitor progress in the **Pipeline Overview** tab.

---

*End of document. Companion to `autonomous-media-technical-specification.md` v1.1 — keep both in `docs/` and update this guide's cross-references if section numbers in the spec ever shift.*
