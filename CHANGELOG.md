# Changelog

All notable changes to Autonomous Media will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [1.7.0] — Telegram Remote Operations & Next-Gen Frontend Control Center — 2026-08-11

Delivers a production-grade Telegram remote operations and alerting subsystem, refactors the frontend into a modular React 19 SPA with URL hash routing, adds Quality Gate keyboard shortcuts, and achieves 100% test suite verification (43/43 unit tests passing).

### Added — Production-Grade Telegram Alert & Remote Operations Subsystem
- **Centralized Notification Engine (`autonomous_media/services/telegram/`)**: Modular subpackage containing `models.py`, `client.py`, `formatter.py`, `policies.py`, `deduplication.py`, `commands.py`, and `notifier.py`.
- **5-Level Severity Model**: Categorizes alerts into `INFO`, `SUCCESS`, `WARNING`, `ERROR`, and `CRITICAL`.
- **Deduplication & Failure Aggregation**: 300-second fingerprint window (`event_type:stage:entity_id:error_hash`) suppresses identical alerts. Aggregates 5+ failures within 10 minutes into a correlated `🚨 PIPELINE INCIDENT DETECTED` card, and emits `🟢 SYSTEM RECOVERED` upon resolution.
- **Telegram Bot Remote Commands**: Dispatcher supporting `/status`, `/jobs`, `/failed`, `/review`, `/quota`, `/health`, and `/help` with Chat ID allowlist authorization (`allowed_chat_ids`).
- **HTML & MarkdownV2 Escaping**: Robust `escape_html()` and `escape_markdown_v2()` functions preventing broken markup when processing raw user input or stack traces.
- **Non-Blocking Delivery Queue**: Async background queue (`telegram_notifier_queue`) ensuring Telegram API timeouts or failures never block pipeline workers.
- **Database Persistence**: Added `TelegramConfig` and `TelegramDeliveryLog` models to `autonomous_media/db/models.py`.

### Added — Next-Gen Modular Control Center Frontend (`frontend/src/`)
- **Modular Directory Architecture**: Refactored monolithic `App.tsx` into modular feature directories (`types/`, `services/`, `hooks/`, `components/`, `features/`).
- **URL Hash Client Router**: Implemented hash-based navigation (`#/overview`, `#/stories`, `#/jobs`, `#/review`, `#/assets`, `#/backgrounds`, `#/sources`, `#/rights`, `#/settings`) preserving view state across browser refreshes.
- **Quality Gate Workbench**: Keyboard-driven reviewer (`Space` for play/pause, `A` for approve, `R` for reject, `ArrowRight`/`ArrowLeft` for card navigation).
- **Settings & Telegram Control View (`SettingsView.tsx`)**: Real-time Telegram connection audit badge, masked token display, category toggles, Quiet Hours time picker (`23:00` - `07:00 EAT`), and delivery audit log table.

### Added — Comprehensive Unit Test Suite & Documentation
- **Telegram Unit Test Suite (`tests/unit/test_telegram_subsystem.py`)**: 8 dedicated tests covering HTML/Markdown escaping, severity classification, deduplication, incident correlation, command authorization, and card formatting. All 43 backend unit tests passing cleanly.
- **Subsystem Specification Document (`docs/telegram-alerts.md`)**: Comprehensive guide detailing subsystem architecture, severity policies, message templates, bot commands, security rules, and troubleshooting procedures.

---

## [1.6.0] — Automated Story Synthesis, Voice Engines & UX Overhaul — 2026-08-07

Delivers major reliability fixes, multi-tier voice synthesis, 9:16 vertical portrait mode for Reddit Shorts, automatic orphan job recovery on boot, and comprehensive operator dashboard UX enhancements.

### Added — Multi-Tier Voice Synthesis & Automated Piper Installer
- **Piper ONNX Neural Voice Engine**: `autonomous_media/workers/narration.py` updated to run Piper local ONNX neural voice models (`en_US-lessac-high`, `en_US-ryan-high`, `en_US-amy-medium`). Added absolute path resolution and process working directory configuration.
- **Automated Piper Installer**: `scripts/download_piper.py` — automated Python script that downloads `piper.exe` binary and high-fidelity ONNX neural voice models into `models/piper/`.
- **Multi-Tier Voice Fallbacks**: `autonomous_media/workers/narration_worker.py` updated with fallback hierarchy (`Piper ONNX` $\rightarrow$ `gTTS` Google DeepMind Neural TTS $\rightarrow$ `pyttsx3` Windows SAPI5 offline). Added emergency audio file existence guarantee before MinIO upload.

### Added — Startup Orphan Recovery & Scheduler Stability
- **`_recover_orphaned_running_jobs()`**: `autonomous_media/scheduler/scheduler.py` automatically detects and resets orphaned `running` jobs from previous process crashes/shutdowns back to `queued` on boot in 0 seconds flat.
- **Reduced Heartbeat Timeout**: Reduced `HEARTBEAT_TIMEOUT_S` from 15 minutes (900s) to 90s for rapid dead-worker recovery.
- **Flush Endpoint & UI**: Added `POST /system/jobs/flush-stuck` endpoint to `autonomous_media/api/system.py` and a **"Flush Stuck Jobs"** UI button to the Job Queue dashboard.

### Fixed — 9:16 Vertical Portrait Mode & Rendering Logic
- **Vertical Shorts Enforcement**: Updated `RenderingWorker` in `autonomous_media/workers/rendering.py` so all Reddit Shorts ($\le 60\text{s}$ or queued as `shorts`) are strictly center-cropped and rendered in **9:16 Vertical Portrait format (1080x1920)** instead of 16:9 landscape.
- **Random Inner Segment Probing**: `RenderingWorker` probes background video duration and calculates random start timestamps (`ss=bg_ss`), ensuring different story clips utilize different inner segments of long background assets.
- **Subtitles Alignment**: Aligned `.ass` caption positioning with vertical 1080x1920 portrait canvas.

### Fixed — Script Text Sanitization & Database Constraints
- **Script Text Guard**: Fixed LLM fallback issue where `prepare_script()` in `narration.py` and `NarrationWorker` in `narration_worker.py` fell back to `StubModelRuntime` rationale text (`hook_strength`, `stub result`). Added sanitization guards so voice synthesis always reads actual Reddit story title and body text word-for-word.
- **Story Re-Queue Reset**: Updated `POST /curated-stories/re-queue-all` in `autonomous_media/api/curated_stories.py` to reset stale `script_text` to `None` on story re-generation.
- **Clip `channel_id` Resolution**: Fixed `EditingWorker` (`editing.py`) channel resolution when creating `Clip` database rows, preventing PostgreSQL NOT NULL constraint violations.

### Added — Frontend Dashboard UX Enhancements (`frontend/src/App.tsx`)
- **Quality Gate Review Video Player**: Embedded interactive `<video>` players on Quality Gate Review cards (`http://localhost:5173`), allowing operators to preview rendered video, listen to narration audio, and verify subtitles before approving/rejecting clips.
- **Exported Assets Library Controls**: Added real-time clip search bar, sorting selector by date (newest/oldest first) and duration (longest/shortest first), category filter (Podcast Clips vs Reddit Stories), and export date timestamps.
- **Re-Export Sync Button**: Added **"Sync / Re-export All Files to Folder"** button with unique filename generation (`_<clip_id[:8]>`).
- **1-Click Story Re-Generation**: Added **"Re-generate & Render All Stories (gTTS Voice)"** button in Curated Stories tab.

### Changed — Dependencies & Repository Optimization
- `requirements.txt`: Added `gTTS>=2.5.0`, `pyttsx3>=2.99`, and `pypiwin32>=223`.
- `.gitignore`: Excluded `models/piper/` large binary models and `exports/` directory from git tracking to comply with GitHub repository size limits.

---

## [1.5.0] — Spec v1.5 Upgrade — 2026-08-04

Implements all new features from Technical Specification v1.5 excluding §29 (licensing/trust model, deferred). Zero breaking changes to the existing podcast-clipping pipeline.

### Added — Promotional Segment Filter (spec §11.8)
- `autonomous_media/workers/promo_filter.py` — two-stage cascade: cheap keyword heuristics first (`PROMO_MARKERS` list), then batched LLM classification on borderline windows only. Output is merged into contiguous promo blocks.
- `autonomous_media/prompts/promo_detection_v1.txt` — versioned LLM prompt for borderline classification.
- `autonomous_media/prompts/__init__.py` — new module exposing all prompt constants as importable names; replaces reading raw `.txt` files inline across workers.
- **Integrated into `IntelligenceWorker`**: promo detection runs once per transcript before candidate generation. Result is cached on `transcripts.promo_segments` so retries are free. Candidates with >20% promo overlap are hard-excluded before scoring.

### Added — Word-Level `.ass` Caption Renderer (spec §12.6)
- `autonomous_media/workers/captions.py` — full Advanced SubStation Alpha (`.ass`) subtitle generator. Replaces the previous SRT/`drawtext` approach.
  - Three named presets: `hormozi_bold` (Montserrat ExtraBold 84pt), `anton_punchy` (Anton 90pt), `poppins_soft` (Poppins Bold 76pt). Fallback: `default`.
  - Chunks word timestamps into 2–5 word groups; breaks early on sentence-ending punctuation.
  - Uppercase, white text, black 4px outline, 220px bottom margin at 1080×1920 — optimised for Shorts.
- **`EditingWorker` updated**: generates the `.ass` file, uploads it to MinIO at `srt/{clip_candidate_id}.ass`, and passes `ass_storage_key` to the rendering job payload.
- **`RenderingWorker` updated**: downloads the `.ass` file and applies `ass=<path>` video filter in the single FFmpeg encode pass (no second FFmpeg call).

### Added — Curated Story Pipeline (spec §30)
- `autonomous_media/workers/narration.py` — Piper TTS wrapper. Runs Piper as a subprocess (CPU-only, no VRAM contention). Includes `prepare_script()` for Reddit-style story cleaning and `narrate()` for WAV generation.
- `autonomous_media/prompts/script_prep_v1.txt` — LLM prompt that reformats Reddit posts for natural spoken pacing (expands AITA/NTA/YTA abbreviations, removes markdown).
- `autonomous_media/api/curated_stories.py` — `POST /curated-stories` (submit story, enqueues `script_preparation` job) + `GET /curated-stories` (list submissions).
- `autonomous_media/api/background_assets.py` — Full CRUD for the pre-vetted background footage library (`GET`, `POST`, `PATCH /{id}`, `DELETE /{id}` with soft-delete).

### Changed — Database Schema (spec §8.3, §30.6)
- `autonomous_media/db/models.py`:
  - **New table `source_posts`**: operator-submitted stories; `status` tracks `pending → scripting → narrating → transcribing → rendering → done`.
  - **New table `background_assets`**: footage library with `storage_key`, `license_type`, `tags`, soft-delete via `status`.
  - **New table `users`**: backs JWT auth (§14.3); `role` is `operator | local_admin`; `channel_scope` list restricts per-channel access.
  - `Channel`: added `voice_profile` (Piper voice identifier for curated_story channels).
  - `Transcript`: `source_video_id` made nullable; added `source_post_id` FK; added `promo_segments` JSON cache column.
  - `Clip`: `clip_candidate_id` made nullable; added `source_post_id` and `background_asset_id` FKs.
- `autonomous_media/db/migrations/versions/002_v1_5_schema.py` — new Alembic migration covering all of the above. Run `alembic upgrade head` after pulling.

### Added — Operator Dashboard (spec §31)
- `frontend/src/App.tsx` — four new sidebar pages:
  - **Curated Stories**: story submission form + live status list; filters sources to `curated_story` type automatically.
  - **Background Assets**: register/tag/retire footage; license badge colours (green=owned, blue=licensed, amber=unknown).
  - **Rights & Compliance**: per-source rights override with evidence ref; full source list with inline Review buttons.
  - *(System Health and Pipeline Overview already existed; now clearly separated in the nav)*.

### Added — Startup Launcher (spec §13.6)
- `Start-Autonomous-Media.bat` (project root) — double-click launcher; handles Docker startup, `docker compose`, `llama-server`, and health polling. Times out with a clear error if the system doesn't respond in 2 minutes.

### Changed — API Routes
- `autonomous_media/api/routes.py`: registered `curated_stories_router` and `background_assets_router`.

---

## [0.8.0] — Phase 1 & 2 Implementation: Pipeline & AI Backend MVP — 2026-07-29

This release completes Phase 1 and Phase 2, delivering a fully operational pipeline from YouTube channel polling to AI clipping, auto-editing, and publication.

### Added — Quota Tracking & Deferral
- Implemented daily Pacific timezone-based `QuotaTracker` supporting Redis storage with a thread-safe in-memory fallback.
- Added pre-upload quota capacity checking and consumption hook inside `PublishingWorker` to prevent exceeding the YouTube daily upload limit (1600 units/upload).
- Added automatic job deferral to Pacific midnight when quota is exhausted, rescheduling publishing jobs into the queue.

### Added — Evaluation & Benchmarking
- Populated `eval/benchmark_dev_v1.jsonl` with 10 labeled episodes containing candidate segments and target clip IDs.
- Completed evaluation harness in `eval/run_eval.py` using the stage manager's real scoring flow.
- Added and verified NFR-3 wall-clock latency benchmark script (`eval/nfr3_benchmark.py`).

### Changed — Workers & Startup Gaps Fixed
- Added UUID string-to-object parsing in `IntelligenceWorker`, `EditingWorker`, `QualityGateWorker`, and `PublishingWorker` to resolve SQLite data type compatibility.
- Handled SQLite dialect compatibility inside `IntelligenceWorker` by dynamically skipping pgvector cosine distance queries.
- Refactored `RightsGate` instantiation to use the worker's session maker factory instead of the active worker session, preventing premature session closure.
- Implemented subtitle auto-generation and FFmpeg relative-path commands to resolve Windows absolute path drive letter limitations.

### Added — Testing
- Created `tests/integration/test_pipeline_e2e.py` verifying the full worker pipeline flow (`Intelligence` -> `Editing` -> `QualityGate`) sequentially.
- Created `tests/unit/test_quota_tracker.py` covering fallback capacity logic and `PublishingWorker` quota enforcement.



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
