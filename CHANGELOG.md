# Changelog

All notable changes to Autonomous Media will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased] — Phase 1: Podcast Clipping MVP

Next milestone. All workers have correct structural contracts and are wired into the Scheduler. Phase 1 replaces all `process()` method stubs with real implementations, end-to-end.

### Planned
- `YouTubeClipSource.discover()` — real `channels.list` → `playlistItems.list` chain (spec §5.1 quota guard)
- `AcquisitionWorker.process()` — yt-dlp download, SHA-256 checksum, MinIO write
- `TranscriptionWorker.process()` — faster-whisper Large-v3-Turbo with word-level timestamps; result JSON to MinIO
- `IntelligenceWorker.process()` — sliding-window candidate generation, heuristic first-pass, batched LLM scoring (`scoring_v3.txt`), pgvector novelty/dedup
- `VisionWorker.process()` — MediaPipe speaker tracking + Qwen2.5-VL OCR on selected clip windows
- `EditingWorker.process()` + `RenderingWorker.process()` — FFmpeg AMF/VCE hardware encode, caption burn-in, branding, silence-trim
- `QualityGateWorker.process()` — QC checks per spec §12.8
- `RightsGate` wired into publish path before first real upload
- `PublishingWorker.process()` — YouTube `videos.insert`, quota-aware with `QuotaExceededError` deferral
- `AnalyticsWorker.process()` — YouTube Analytics API poll → `analytics_snapshots` rows
- MinIO bucket auto-creation on startup
- Eval benchmark labeling — 40-episode dev slice per §25.9 protocol

---

## [0.7.0] — Spec v1.2 Compliance Audit — 2026-07-28

**Commit:** `5d21b02` — 20 files changed, 1,098 insertions, 12 new files

This release closes all 16 compliance gaps found during a systematic audit of the codebase against the Technical Specification v1.2. The project is now architecturally complete and structurally correct — all data models, interfaces, and contracts match the spec. Pipeline logic remains to be implemented (Phase 1).

### Changed — Database Models (`db/models.py`)
- `Transcript`: replaced `text + segments` columns with `engine`, `language`, `storage_key` (MinIO pointer), `word_count`. Full timestamped JSON now lives in MinIO, not Postgres (spec §8.3).
- `ClipCandidate`: renamed `start_time_s`/`end_time_s` → `start_ms`/`end_ms` (millisecond precision for word-level timestamps); removed `transcript_text` (stored in MinIO via transcript).
- `Clip`: added `channel_id (FK)`, `thumbnail_key`, `caption_style`; fixed `status` default to `rendering`.
- `InventoryItem`: renamed `scheduled_for` → `scheduled_at`, `platform_ref` → `external_video_id`; fixed `status` default to `ready`; added `updated_at`.
- `RightsRecord`: changed FK from `source_video_id` → `content_source_id` (spec §8.3, §11.4); replaced status values (`pending`/`cleared`/`flagged` → `owned`/`licensed`/`permission_granted`/`unknown`/`denied`); added `evidence_ref`, `reviewed_by`, `reviewed_at`, `expires_at`.
- `AnalyticsSnapshot`: replaced generic polymorphic `entity_id`/`entity_type` with `inventory_item_id (FK)` and explicit metric columns (`views`, `likes`, `comments`, `shares`, `avg_view_duration_s`, `ctr`, `subscribers_delta`).
- `Job`: renamed `job_type` → `type` (spec field name); added `channel_id (FK)`; removed `target_id` polymorphic field.
- `workers/base.py`: fixed `emit_event` call to use `job.type` instead of `self.job_type`.

### Added — New Database Tables
- `Model` — model registry backing the Runtime Manager (spec §12.9).
- `EvalRun` — one row per evaluation pass; what the §18.1 promotion gate reads.
- `SystemEvent` — append-only audit/event log; every row carries `trace_id` for lifecycle reconstruction (spec §7.3).

### Added — New Alembic Migration
- `a1b2c3d4e5f6_fix_schema_v12_gaps.py` — covers all schema changes above plus all §8.4 performance indexes (`jobs`, `source_videos`, `inventory_items`, `clip_candidates`, `analytics_snapshots`, `system_events`).

### Rewritten — `rights/gate.py`
- `CLEARED_STATUSES = {"owned", "licensed", "permission_granted"}` — correct status set.
- FK lookup now uses `content_source_id`, not `source_video_id`.
- Every `set_status()` call writes a `SystemEvent` audit row (spec §14.6).
- `fair_use_asserted` deliberately excluded — it is not a valid status.

### Rewritten — `sources/base.py`
- Replaced `poll()` method with spec §11.3 `ContentSource` Protocol: `discover() → list[SourceItem]` + `fetch(item) → RawMedia`.
- Added `SourceItem` and `RawMedia` dataclasses.

### Added — `sources/youtube_clip.py` (new file)
- `YouTubeClipSource` — V1's first `ContentSource` implementation.
- Quota guard: resolves uploads playlist via `channels.list` (1 unit), polls `playlistItems.list` (1 unit/page) — never `search.list` (100 units).
- SSRF guard: `fetch()` rejects non-YouTube URLs (spec §14.5).
- `AIStorySource` V2 stub included.

### Rewritten — `runtime/manager.py`
- `ModelRuntime` Protocol with `load()`, `unload()`, `infer()`, `health_check()`.
- `StageModelManager`: swap/eager residency modes, per-model timeout, retry-at-lower-temperature (up to 2 attempts), two-tier fallback (primary → fallback → `dead_letter`).
- `StubModelRuntime`: deterministic JSON responses for tests.
- `health_check_all()` backs the `GET /api/v1/system/models` endpoint.

### Rewritten — `scheduler/scheduler.py`
- Priority-ordered dispatch from `queued`/`retrying` jobs.
- `max_concurrent_jobs` config parameter (scaling knob, spec §19).
- `_recover_stuck_jobs()` — heartbeat-timeout detection for stuck `running` jobs (spec §12.1). Makes Windows reboots self-healing.

### Added — `events.py` (new file)
- 17 canonical event type string constants per spec §7.3.

### Added — `prompts/` (4 new files)
- `scoring_v3.txt`, `title_v1.txt`, `description_v1.txt`, `grounding_v1.txt` — verbatim from spec §25.8.

### Added — `eval/` (3 new files)
- `run_eval.py` — Precision@5 harness; writes `eval_runs` rows for the §18.1 promotion gate.
- `benchmark_dev_v1.jsonl` — 40-episode dev slice (to be labeled per §25.9).
- `benchmark_holdout_v1.jsonl` — 10-episode hold-out (never touched during tuning).

### Added — API Routers
- `api/jobs.py` — `GET/POST /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/retry`, `POST /jobs/{id}/cancel` (spec §9.2).
- `api/clips.py` — `GET/PATCH /clips`, `GET /clips/{id}` approve/reject (spec §9.2, §10.1).
- `api/main.py` — now mounts all 9 routers.

### Changed — `requirements.txt`
- Added Phase 1 AI/media dependencies: `yt-dlp`, `ffmpeg-python`, `faster-whisper`, `mediapipe`, `paddlepaddle`, `paddleocr`, `pyannote.audio`, `silero-vad`.

---

## [0.6.0] — Phase 0: Documentation & Dashboard — 2026-07-28

### Added
- Full documentation suite: Technical Specification v1.2, Developer Guide, Architecture, Runbook, ADRs 0001–0007, Security, Contributing, Changelog.
- React + Tailwind v4 operator dashboard with glassmorphism design.
- Dashboard views: Pipeline Overview, Candidate Review, Asset Library.
- `autonomous_media/api/routes.py` — REST API exposing database state to the frontend.

---

## [0.5.0] — Infrastructure Foundation — 2026-07-28

### Added
- `docker-compose.yml` — Postgres (pgvector via `ankane/pgvector`), Redis 7, MinIO with healthchecks and named volumes.
- `autonomous_media/` package scaffold: `api/`, `db/`, `workers/`, `sources/`, `runtime/`, `rights/`, `scheduler/`, `prompts/`, `rendering/`, `youtube/`, `evaluation/`.
- `db/models.py` — initial schema (later corrected in 0.7.0 compliance audit).
- `db/migrations/versions/d081f2fc0740` — first Alembic baseline migration.
- `autonomous_media/config.py` — Pydantic `Settings` + `ChannelConfig` schema.
- `autonomous_media/exceptions.py` — typed exception hierarchy.
- `autonomous_media/logging.py` — JSON structured logger with `trace_id` propagation.
- `workers/base.py` — `Worker` ABC with heartbeat thread + retry/dead-letter routing.
- `runtime/manager.py` — initial `ModelRuntimeManager` (later rewritten in 0.7.0).
- `scheduler/scheduler.py` — initial scheduler (later rewritten in 0.7.0).
- `alembic.ini` — configured to use `autonomous_media/db/migrations/`.
- `requirements.txt` — core dependencies.
- `.env.example` — environment variable template.
- `.gitignore`, `CONTRIBUTING.md`, `SECURITY.md`.
