# Autonomous Media — Developer Guide

**Companion to:** `docs/technical-specification.md` (v1.2)
**Purpose:** The specification defines *what* the system does and *why*. This guide is *how you build it* — in what order, with what conventions, and with what tools.
**Audience:** Whoever is writing the code. For V1, that is one person.
**Rule:** If anything in this guide conflicts with the Technical Specification, the spec wins.

---

## 1. Orientation

### Where We Are

Phase 0 (infrastructure, schema, API skeleton, dashboard) is **complete**. A full spec v1.2 compliance audit has been completed — 16 schema/code gaps were found and closed in commit `5d21b02`. All structural contracts are in place. What is **not yet implemented** is the actual pipeline logic inside each worker's `process()` method.

Phase 1 is the next task: make one end-to-end clip, from source poll to `inventory_items` row, work completely with no stubs.

### Development Philosophy

- **One file, one job, one audience.** Every module has a clearly bounded responsibility. Look at the filename, know exactly what lives there.
- **Stubs are temporary scaffolding, not acceptable architecture.** Every worker's `process()` method currently returns `JobResult()` immediately. Phase 1 replaces them with real logic.
- **The spec is the arbiter.** If you're unsure what a piece of code should do, open `docs/technical-specification.md` and read the relevant section. Cross-section references in the spec (e.g. §11.3, §12.9) are trustworthy.

---

## 2. Project Structure

```
autonomous_media/
  api/
    auth.py          # JWT login/token endpoint
    channels.py      # Channel CRUD
    sources.py       # ContentSource management
    jobs.py          # Job list/get/retry/cancel — spec §9.2
    clips.py         # Clip list/get/patch (approve/reject) — spec §9.2, §10.1
    inventory.py     # Inventory item management
    analytics.py     # Analytics snapshot reads
    rights.py        # Rights status read/update
    system.py        # /health, /models (health_check_all), /quota
    main.py          # FastAPI app: mounts all 9 routers at /api/v1
  db/
    base.py          # DeclarativeBase
    session.py       # SessionMaker factory
    models.py        # 13 SQLAlchemy models — canonical schema
    migrations/      # Alembic versions (one migration per spec change)
  workers/
    base.py          # Worker ABC, JobResult, heartbeat thread
    acquisition.py   # Download source video + checksum + MinIO write
    transcription.py # faster-whisper → timestamped JSON → MinIO
    intelligence.py  # Candidate window gen + heuristics + LLM scoring + pgvector dedup
    vision.py        # MediaPipe speaker tracking + Qwen2.5-VL OCR
    editing.py       # FFmpeg filtergraph construction + caption burn-in
    rendering.py     # FFmpeg hardware encode (AMF/VCE) + thumbnail
    quality_gate.py  # QC: black-frame, silence, aspect ratio, duration (spec §12.8)
    publishing.py    # YouTube videos.insert (quota-aware) — spec §5.1
    analytics.py     # YouTube Analytics API poll → analytics_snapshots rows
    learning.py      # Scoring weight update from analytics feedback (spec §23)
  sources/
    base.py          # ContentSource Protocol: discover() + fetch()
    youtube_clip.py  # YouTubeClipSource — the only V1 source implementation
  runtime/
    manager.py       # StageModelManager + ModelRuntime Protocol + StubModelRuntime
  rights/
    gate.py          # RightsGate: is_cleared, get_status, set_status (audit-logged)
  scheduler/
    scheduler.py     # Job poll loop + heartbeat-timeout recovery + dispatch
  prompts/
    scoring_v3.txt   # Versioned LLM prompt for clip scoring (spec §25.8)
    title_v1.txt     # Title generation prompt
    description_v1.txt
    grounding_v1.txt # Hallucination-check prompt (spec §12.6)
  config.py          # Pydantic Settings + ChannelConfig schema
  exceptions.py      # Typed exception hierarchy
  events.py          # Canonical event type string constants (spec §7.3)
  logging.py         # JSON structured logger + emit_event
  main.py            # Top-level entrypoint for uvicorn
eval/
  run_eval.py        # Precision@5 evaluation harness (spec §18.1)
  benchmark_dev_v1.jsonl    # 40-episode dev slice — label before Phase 2
  benchmark_holdout_v1.jsonl  # 10-episode hold-out — never touched during tuning
```

---

## 3. Conventions

### Exception Hierarchy

Always use typed exceptions from `autonomous_media/exceptions.py`:

| Exception | When to raise |
|---|---|
| `StageUnrecoverableError` | Permanent failure — job goes straight to `dead_letter` (no retry) |
| `ModelTimeoutError` | Inference took longer than `StageModelManager.timeout_for(model)` |
| `MalformedOutputError` | LLM returned unparseable JSON |
| `QuotaExceededError` | YouTube quota exhausted — job should be deferred, not dead-lettered |
| `RightsBlockedError` | Clip fails rights gate — dead-letter immediately, no retry |

### Structured Logging

Every log call must include `extra={"trace_id": job.trace_id}`. This is how the full lifecycle of one clip is reconstructable from logs alone.

```python
from autonomous_media.logging import get_logger
logger = get_logger("workers.acquisition")
logger.info("Video downloaded", extra={"trace_id": job.trace_id, "storage_key": key})
```

### Event Bus

Emit a `SystemEvent` row via `emit_event()` at every major pipeline transition. Use the constants in `events.py`, never bare strings.

```python
from autonomous_media.events import VIDEO_DOWNLOADED
emit_event(VIDEO_DOWNLOADED, job.trace_id, {"source_video_id": str(video_id)})
```

### Worker Pattern

Every worker inherits `Worker` from `workers/base.py`, declares a `job_type` class attribute matching what the Scheduler enqueues, and implements `process(session, job) -> JobResult`. The base class owns: heartbeat thread, status transitions, retry/dead-letter routing on exception.

```python
class AcquisitionWorker(Worker):
    job_type = "acquisition"

    def process(self, session: Session, job: Job) -> JobResult:
        source_video_id = job.payload["source_video_id"]
        # ... real implementation ...
        return JobResult()
```

### Model Inference

Never call `llama-server` directly from a worker. Always go through `StageModelManager`:

```python
from autonomous_media.runtime.manager import stage_manager, InferenceRequest
result = stage_manager.run_stage("scoring", InferenceRequest(prompt=rendered_prompt))
scores = json.loads(result.text)
```

### Timestamps

All `clip_candidates.start_ms` / `end_ms` values are **milliseconds**. Whisper word-level segment timestamps are also milliseconds in `faster-whisper`. Do not use seconds anywhere in the clip boundary logic.

### Rights Gate

Always check rights clearance before enqueuing a publish job:

```python
from autonomous_media.rights.gate import RightsGate
gate = RightsGate(session_maker)
if not gate.is_cleared(source.id):
    raise RightsBlockedError(f"Source {source.id} has status={gate.get_status(source.id)}")
```

---

## 4. Adding a New Worker

1. Create `autonomous_media/workers/<name>.py` implementing `Worker`.
2. Register it in `autonomous_media/main.py` (or wherever `Scheduler` is initialised) in the `worker_registry` dict.
3. Add the job type string to `events.py` as a constant.
4. Write unit tests in `tests/unit/test_<name>_worker.py`.
5. If the worker calls a model, register a `StubModelRuntime` for its stage in `tests/conftest.py`.

---

## 5. Phase 1 Build Sequence (Walking Skeleton)

The correct order for implementing Phase 1 is:

```
Step 1: YouTubeClipSource.discover()
  ├─ Real channels.list → playlistItems.list call (never search.list)
  ├─ Persist SourceVideo rows
  └─ Update ContentSource.last_polled_at

Step 2: AcquisitionWorker.process()
  ├─ Call source.fetch(item) → yt-dlp download
  ├─ Verify checksum (SHA-256)
  ├─ Upload to MinIO raw/{source_video_id}/original.mp4
  └─ Emit VIDEO_DOWNLOADED event

Step 3: TranscriptionWorker.process()
  ├─ Pull raw audio from MinIO
  ├─ Run faster-whisper (large-v3-turbo) with word-level timestamps
  ├─ Write {word, start_ms, end_ms}[] JSON to MinIO transcripts/{id}.json
  ├─ Create Transcript row (engine, language, word_count, storage_key)
  └─ Emit TRANSCRIPT_READY event

Step 4: Walking skeleton verified
  └─ Confirm one InventoryItem row exists with status='ready'
     (Intelligence/Vision/Editing can remain stubs here —
     just validate the data contracts are correct end-to-end)

Step 5: IntelligenceWorker.process() — full implementation
  ├─ Load transcript from MinIO
  ├─ Sliding-window candidate generation (§11.1 parameters)
  ├─ Heuristic first-pass filter (§20.3 cascade)
  ├─ Batched LLM scoring via StageModelManager (scoring_v3.txt prompt)
  ├─ pgvector novelty check (§11.2)
  ├─ Create ClipCandidate rows (start_ms, end_ms, scores, rank)
  └─ Emit CLIP_CANDIDATES_SCORED event

Step 6: EditingWorker + RenderingWorker (no AI, pure FFmpeg)
  ├─ Crop/reframe speaker window
  ├─ Burn captions (start_ms/end_ms → SRT)
  ├─ Apply branding / music / silence-trim
  ├─ Hardware encode (AMF/VCE via FFmpeg)
  └─ Write Clip row + MinIO storage_key

Step 7: QualityGateWorker
  └─ Spec §12.8 checks (duration, black frames, silence, aspect ratio)

Step 8: RightsGate wired into publish path (BEFORE first real upload)

Step 9: PublishingWorker
  ├─ OAuth credential retrieval
  ├─ Resumable upload via YouTube videos.insert
  ├─ Quota tracking — backoff on 429/403
  └─ Emit PUBLISH_COMPLETED event
```

---

## 6. Testing Strategy

### Test Levels

| Level | Location | Rule |
|---|---|---|
| Unit | `tests/unit/` | Pure functions only. No DB, no network, no filesystem. Mock everything. |
| Integration | `tests/integration/` | Real DB (test Postgres), real MinIO. Mock `ContentSource` and `ModelRuntime`. |
| E2E | `tests/e2e/` | Full pipeline from a fixture `.mp4` through to an `InventoryItem` row. Run manually before releases. |

### Running Tests

```powershell
# Unit tests — fast, no services required
pytest tests/unit/ -v

# Integration tests — requires docker compose up -d
pytest tests/integration/ -v

# All tests
pytest tests/ -v
```

### Mocking Models

Use `StubModelRuntime` (already registered as default in `runtime/manager.py`) in all tests. It returns deterministic JSON so tests don't depend on a live `llama-server`. When writing a new integration test:

```python
# conftest.py
from autonomous_media.runtime.manager import stage_manager, StubModelRuntime
stage_manager.register("scoring", StubModelRuntime())
```

---

## 7. Evaluation & Promotion Gate (spec §18.1)

Before promoting any change to the scoring prompt, scoring weights, or inference model to production:

1. Run `eval/run_eval.py dev` against the development benchmark slice.
2. Tune until `precision_at_5` is stable.
3. Run `eval/run_eval.py holdout` **once** (this is the only time the hold-out slice is touched).
4. Write the resulting `metrics` dict to an `eval_runs` row.
5. Promotion is allowed only if hold-out metrics do not regress vs. the previous production version.

The 40-episode dev slice (`eval/benchmark_dev_v1.jsonl`) needs to be labeled before Phase 2 begins. Labeling protocol: for each episode in the dev set, a human identifies the top-5 clips they would have published. Those clip IDs go in the `labeled_good_clip_ids` field.

---

## 8. Quota Management (spec §5.1)

YouTube Data API v3 has a hard 10,000-unit daily quota (shared per Google Cloud project).

| Operation | Cost |
|---|---|
| `videos.insert` (upload) | 1,600 units |
| `playlistItems.list` (poll) | 1 unit/page |
| `channels.list` | 1 unit |
| `search.list` | **100 units** ← **NEVER USE THIS** |

**Rule:** All source polling uses `playlistItems.list`. The uploads playlist ID is resolved **once** via `channels.list` and cached in `ContentSource.config`. Never call `search.list` anywhere.

At 1,600 units per upload and 10,000 units/day, that is ~6 uploads/day across all channels. The `PublishingWorker` must check quota before calling `videos.insert`. On quota exhaustion, raise `QuotaExceededError` — the Scheduler defers the job rather than dead-lettering it.

---

## 9. Troubleshooting Known Constraints

### Vulkan / GPU Not Engaged

**Symptom:** GPU usage stays at 0% in Task Manager during inference; wall-clock time is 10–50× slower.

**Steps:**
1. Confirm `llama-server.exe` was compiled with Vulkan support: `llama-server.exe --version` should include `vulkan`.
2. Check AMD driver version. Required: Adrenalin 24.x or later (Polaris/GCN4 support was retained in the Adrenalin driver path even as ROCm dropped it).
3. Verify the `--gpu-layers` argument is set to `99` (or any value ≥ the number of model layers).
4. Check logs for `Vulkan device not found` — if seen, the Vulkan runtime is not installed: `winget install KhronosGroup.VulkanRT`.

### Heartbeat-Stuck Jobs

**Symptom:** Job sits in `running` status indefinitely after the process was killed.

**Fix:** The Scheduler's `_recover_stuck_jobs()` loop will requeue it within `HEARTBEAT_TIMEOUT_S = 120` seconds automatically. If this does not happen, check that the Scheduler process itself is running.

Manually reset if urgent:
```sql
UPDATE jobs SET status = 'queued', attempts = attempts + 1 WHERE id = '<job_id>';
```

### Transcript JSON Truncated

**Symptom:** `faster-whisper` produces a valid transcript but the MinIO write silently truncates it.

**Root cause:** Most likely a `word_timestamps=True` output that was serialised to `str()` rather than `json.dumps()`. Always serialise with `json.dumps(segments, ensure_ascii=False)`.

### PostgreSQL pgvector Extension Missing

**Symptom:** `alembic upgrade head` fails with `type "vector" does not exist`.

**Fix:** The `docker-compose.yml` uses `ankane/pgvector:latest` which ships with the extension. If using an external Postgres:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### MinIO Bucket Not Found

**Symptom:** `minio.error.S3Error: NoSuchBucket` on first acquisition worker run.

**Fix:** Create the buckets on first start (this will be automated in a startup script):
```powershell
# Using the MinIO Client (mc)
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/autonomous-media-raw
mc mb local/autonomous-media-transcripts
mc mb local/autonomous-media-renders
mc mb local/autonomous-media-branding
```

---

## 10. Phase 2 & Beyond — Open Questions

The following design questions should be resolved **by reference to the Technical Specification v1.2** before implementation of Phase 2 begins. They are recorded here to flag the decision points, not to pre-answer them.

1. **Vision Stage Trigger (spec §7.5):** The spec states Vision runs on selected clip windows, not on the entire source video. Confirm: does the `VisionWorker` receive a `clip_candidate_id` (with start/end timestamps) or a `source_video_id`? The current job payload schema in `workers/vision.py` uses `source_video_id` — this may need updating. Refer to spec §7.5 for the authoritative answer.

2. **Scoring Cascade Thresholds (spec §20.3):** The heuristic first-pass thresholds in the `IntelligenceWorker` (e.g. minimum segment energy, minimum hook phrase density) are set to placeholder values. The NFR-3 benchmark run (timing 10 real episodes end-to-end) is what produces the data to tune these. Do **not** tune them from intuition — run the benchmark first.

3. **Pgvector Index Type (spec §11.2):** The `topics.embedding` column uses `Vector(768)`. The migration does not yet create a vector index. Before the first production run at scale, decide between `ivfflat` (faster build, lower recall) and `hnsw` (better recall, slower build). Refer to spec §11.2 for the guidance on which to prefer. Create the index in a new migration **after** the first realistic data load.

4. **Audio Format Contract (spec §12.3):** `faster-whisper` works best on 16kHz mono WAV. Confirm that the `AcquisitionWorker` writes `audio.wav` in this exact format (using `ffmpeg -ar 16000 -ac 1`) before the `TranscriptionWorker` reads it. Both workers need to agree on this contract.

5. **Quota Deferral Duration (spec §5.1):** The spec requires deferred publish jobs to be retried "when quota resets." YouTube quota resets at midnight Pacific. The Scheduler's deferral logic needs a time-zone-aware next-reset calculation, not a naive `+ 24 hours`. Refer to spec §5.1 for the exact required behaviour.

6. **Evaluation Benchmark Labeling (spec §25.9):** The `eval/benchmark_dev_v1.jsonl` and `benchmark_holdout_v1.jsonl` files are currently empty. The labeling protocol (40 dev episodes, 10 hold-out) must be completed before Phase 2's scoring improvements can be validated against the promotion gate. The protocol is specified in §25.9.

7. **TikTok/Instagram Syndication (V2 — spec §26):** Multi-platform distribution is explicitly deferred to V2. Do not design any V1 code to accommodate it — that introduces premature abstraction. V1's `PublishingWorker` is explicitly YouTube-only. When V2 begins, the correct path is implementing a second concrete `PublisherProtocol` for TikTok/Instagram, not parameterising the existing one.
