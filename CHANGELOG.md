# Changelog

All notable changes to the Autonomous Media system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - Phase 5 Complete
### Added
- Phase 5: Dashboard UI.
- React SPA built with Vite and `lucide-react`, styled with premium Vanilla CSS glassmorphism.
- Hosted statically from the FastAPI monolith in `autonomous_media/main.py`.
- Interactive frontend views for Pipeline Overview, Candidate Review, and Asset Library.
- `autonomous_media/api/routes.py` REST API to expose database state to the frontend.

## [0.5.0] - Phase 4 Complete
### Added
- Phase 4: YouTube API Publisher execution framework.
- `PublishedAsset` database model for tracking successful YouTube uploads and deduplication.
- `YouTubeAPIClient` wrapping Google's API to handle resumable uploads and credentials.
- `PublishWorker` to coordinate the upload flow.
- Added Graceful Deferral strategy for YouTube Quota Exhaustion (429/403 errors).

## [0.4.0] - Phase 3 Complete
### Added
- Phase 3: Automated Video Editing & Rendering Engine execution framework.
- `RenderedAsset` database model for tracking final output files.
- `FFmpegCompositor` to programmatically build complex ffmpeg filtergraphs (crop, boxblur, composite, subtitle burn-in) using `ffmpeg-python` (ADR 0007).
- `RenderWorker` to coordinate fetching raw video, generating `.srt` subs, and invoking the Compositor.
- Local execution test harnesses (`test_rendering_engine.py`) with mock fallbacks for missing binaries.

## [0.3.0] - Phase 2 Complete
### Added
- Phase 2: LLM Evaluation & Selection Engine execution framework.
- `CandidateClip` and `EvaluationScore` database models for scoring persistence.
- `BatchedEvaluationPrompt` to process candidates efficiently with constrained contexts.
- `EvaluateWorker` interacting with `llama-server` via local HTTP endpoints (ADR 0006).
- Evaluation test runner with mock API fallback for local development.

## [0.2.0] - Phase 1 Complete
### Added
- Hierarchical `Workflow`, `WorkflowStage`, and `Task` database models.
- Download, Transcribe, and Topic Extraction execution workers.
- Local execution test harnesses (`test_workflow_execution.py`) with mock fallbacks for missing binaries (`yt-dlp`, `ffmpeg`).
- `ModelRuntimeManager` for VRAM residency management (ADR 0005).

## [0.1.0] - Phase 0 Complete
### Added
- Initial project scaffolding (FastAPI, SQLAlchemy, Docker Compose for Postgres/Redis/MinIO).
- Vite + Tailwind v4 React Dashboard.
- Core documentation matrix (Technical Spec, Developer Guide, Runbook, Changelog, Security, Contributing, ADRs).
