# Autonomous Media

## Technical Specification & System Design

**Version:** 1.2
**Status:** Foundation Complete — Phase 1 Implementation In Progress
**Classification:** Internal — Single-Operator System
**Last Updated:** 2026-07-28
**Document Owner:** Project Operator

> **Note:** The authoritative text of this specification was provided to the implementation team as a structured prompt document and is the source of truth for all design decisions. This file is the in-repository index and revision register for that specification. Any discrepancy between code and the specification text resolves in favour of the specification.

---

## Revision History

| Version | Date | Summary |
|---|---|---|
| 0.1–0.9 | (informal) | Iterative discovery: feasibility, architecture sketches, hardware assessment, scope narrowing, vision document, draft SRS |
| 1.0 | 2026-07-25 | First consolidated technical specification. Formalises project name as **Autonomous Media**. Resolves contradictions from discovery phase. Closes gaps in quota planning, rights/compliance, data model, API design, and hardware-specific AI runtime strategy. |
| 1.1 | 2026-07-25 | Review pass closed six remaining gaps: AI evaluation framework with promotion gate (§18.1), fully specified Model Runtime Manager (§12.9) covering fallback/quantization/timeout, rights/compliance matrix (§11.4), analytics feedback loop (§23), CONTRIBUTING guide, Security policy. |
| 1.2 | 2026-07-28 | Implementation phase adjustments. Formalized flat `Job` architecture (replacing `Workflow→Stage→Task`). Introduced `ContentSource` Protocol (§11.3). Expanded `AnalyticsSnapshot` schema (§8.3). Closed all open questions from v1.1 with explicit decisions recorded in ADRs 0004–0009. |

---

## Status at Spec v1.2

### Completed (Foundation)

| Component | Status | Notes |
|---|---|---|
| Project scaffold & repo structure | ✅ Complete | |
| Docker Compose services (Postgres, Redis, MinIO) | ✅ Complete | |
| PostgreSQL schema — all 13 tables | ✅ Complete | Audit commit `5d21b02` |
| Alembic migrations (two versions) | ✅ Complete | `d081f2fc0740` + `a1b2c3d4e5f6` |
| FastAPI skeleton — 9 routers at `/api/v1` | ✅ Complete | |
| JWT authentication | ✅ Complete | |
| `ContentSource` Protocol (§11.3) | ✅ Complete | `sources/base.py` |
| `YouTubeClipSource` (V1 only source) | ✅ Scaffolded | `discover()`/`fetch()` are stubs |
| `StageModelManager` + `ModelRuntime` Protocol (§12.9) | ✅ Complete | `runtime/manager.py` |
| Scheduler with heartbeat-timeout recovery (§12.1) | ✅ Complete | `scheduler/scheduler.py` |
| Worker base class with retry/dead-letter routing | ✅ Complete | `workers/base.py` |
| All 10 worker type scaffolds | ✅ Scaffolded | `process()` stubs only |
| `RightsGate` with audit logging (§11.4, §14.6) | ✅ Complete | `rights/gate.py` |
| `events.py` — canonical event type constants (§7.3) | ✅ Complete | |
| Versioned prompt files (§25.8) | ✅ Complete | `prompts/scoring_v3.txt`, etc. |
| Evaluation harness + benchmark files (§18.1, §25.9) | ✅ Scaffolded | Benchmarks unlabeled |
| Structured JSON logging with `trace_id` (§14.1) | ✅ Complete | `logging.py` |
| Prometheus metrics scaffold (§16.1) | ✅ Complete | via `prometheus-fastapi-instrumentator` |
| Operator dashboard (React) | ✅ Complete | `dashboard/` |
| All documentation (spec, guide, runbook, ADRs) | ✅ Complete | `docs/` |

### In Progress / Not Yet Started (Phase 1)

| Component | Status | Spec Reference |
|---|---|---|
| `YouTubeClipSource.discover()` — real API call | 🔜 Not started | §11.3, §5.1 |
| `AcquisitionWorker.process()` — real implementation | 🔜 Not started | §12.2 |
| `TranscriptionWorker.process()` — real implementation | 🔜 Not started | §12.3 |
| `IntelligenceWorker.process()` — real implementation | 🔜 Not started | §11.1, §20.3 |
| `VisionWorker.process()` — real implementation | 🔜 Not started | §12.5, §7.5 |
| `EditingWorker.process()` — real implementation | 🔜 Not started | §12.7 |
| `RenderingWorker.process()` — real implementation | 🔜 Not started | §12.7, §20.1 |
| `QualityGateWorker.process()` — real implementation | 🔜 Not started | §12.8 |
| `PublishingWorker.process()` — real implementation | 🔜 Not started | §5.1, §9.2 |
| `AnalyticsWorker.process()` — real implementation | 🔜 Not started | §23 |
| `LearningWorker.process()` — real implementation | 🔜 Not started | §23 |
| Eval benchmark labeling (dev slice) | 🔜 Not started | §25.9 |
| MinIO bucket auto-creation on startup | 🔜 Not started | §12.2 |
| pgvector ANN index on `topics.embedding` | 🔜 Not started | §11.2, §8.4 |
| NFR-3 benchmark run (wall-clock timings per stage) | 🔜 Not started | §25.5 |

---

## V2 — Deferred Features

The following are explicitly deferred to V2 and must not influence V1 implementation decisions:

| Feature | Spec Reference | Notes |
|---|---|---|
| Multi-platform syndication (TikTok, Instagram) | §26 | V1 is YouTube Shorts only |
| Automated thumbnail generation (Stable Diffusion) | §26.2 | V1: static branded frame from video |
| A/B testing (title/thumbnail rotation) | §26.3 | Requires analytics baseline first |
| AI Story Generation source (`AIStorySource`) | §27 | V1: podcast clipping only |
| Horizontal scaling beyond `sequential` mode | §19 | V1: `max_concurrent_jobs = 1` |

---

## Key Design Decisions Index

For the reasoning behind each major architectural choice, see the corresponding ADR:

| Decision | ADR |
|---|---|
| Modular monolith over microservices | [ADR 0001](adr/0001-modular-monolith-over-microservices.md) |
| Vulkan over ROCm for AMD RX 580 | [ADR 0002](adr/0002-vulkan-over-rocm.md) |
| Batched LLM scoring over per-candidate scoring | [ADR 0003](adr/0003-batched-over-per-candidate-scoring.md) |
| Flat `Job` table over `Workflow→Stage→Task` hierarchy | [ADR 0004](adr/0004-flat-job-table-over-workflow-hierarchy.md) |
| `StageModelManager` swap mode for VRAM constraint | [ADR 0005](adr/0005-model-runtime-manager.md) |
| `llama-server` HTTP interface over subprocess stdout | [ADR 0006](adr/0006-http-llama-server.md) |
| `ffmpeg-python` for filtergraph construction | [ADR 0007](adr/0007-ffmpeg-python.md) |
| `content_source_id` as the rights FK target | [ADR 0008](adr/0008-rights-fk-on-content-source.md) |
| Transcript content in MinIO, metadata-only in Postgres | [ADR 0009](adr/0009-transcript-content-in-minio.md) |
