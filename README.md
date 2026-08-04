# Autonomous Media

An autonomous AI content production system. It continuously monitors source YouTube channels, downloads and transcribes long-form podcasts/interviews, scores and selects the best 30–90 second windows using a local LLM, renders them into vertical YouTube Shorts with animated `.ass` captions and branding, and publishes them on a configurable schedule — while requiring minimal ongoing human intervention.

**v1.5 scope:** podcast/interview clipping + operator-submitted curated stories (Reddit narration) · promotional-segment filtering · word-level `.ass` captions (Montserrat ExtraBold) · background asset library · full 7-page operator dashboard · single consumer PC (Windows 11, AMD Ryzen 5 5500, 16 GB RAM, RX 580 8 GB VRAM).

---

## Current Status

| Milestone | Status |
|---|---|
| Phase 0 — Foundation (infra, schema, API skeleton, dashboard) | ✅ Complete |
| Spec v1.2 Compliance Audit (16 schema/code gaps closed) | ✅ Complete — commit `5d21b02` |
| Phase 1 — Podcast Clipping MVP (all 10 pipeline workers implemented) | ✅ Complete — commit `391bfe1` |
| Phase 2 — AI Model Integration, Quota System, E2E Tests | ✅ Complete — commit `391bfe1` |
| **Spec v1.5 Upgrade** — promo filter · ASS captions · curated stories · background assets · 7-page dashboard | ✅ **Complete** — see [CHANGELOG](CHANGELOG.md) |

---

## Quick Start

### Prerequisites

Install on the **host machine** (not in Docker):
- [Python 3.11+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — enable the **WSL2 backend** (Settings → General)
- [FFmpeg](https://ffmpeg.org/download.html) — add to `PATH`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — `pip install yt-dlp`
- A **Vulkan-compiled `llama-server`** binary (see [Deployment Guide](../docs/deployment_guide.md) or the full instructions in the [GitHub repo](https://github.com/JohnApollos/YTAuto))

### One-Click Start (recommended)

Double-click **`Start-Autonomous-Media.bat`** in the project root. It:
1. Starts Docker Desktop if not already running
2. Brings up Postgres, Redis, and MinIO via `docker compose`
3. Launches the Vulkan `llama-server` in a minimised window
4. Polls the health endpoint and opens the dashboard at `http://localhost:3000`

### Manual Setup

```powershell
# 1. Clone
git clone https://github.com/JohnApollos/YTAuto.git
cd YTAuto

# 2. Python environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Copy and fill in environment variables
copy .env.example .env
# Edit .env with your credentials (DATABASE_URL, YOUTUBE_OAUTH_*, JWT_SECRET, etc.)

# 4. Start stateful services (Postgres+pgvector, Redis, MinIO)
docker compose up -d

# 5. Apply all database migrations (includes v1.5 schema)
alembic upgrade head

# 6. Start the AI model server (leave this window open)
llama-server.exe --model C:\dev\YTAuto\models\qwen3-8b-Q4_K_M.gguf --port 8080 --gpu-layers 99

# 7. In a NEW terminal — start the REST API
uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000

# 8. In ANOTHER terminal — start the background scheduler
python -m autonomous_media.main
```

### Starting the Model Server

The LLM inference server runs **natively on the Windows host** (not in Docker) to get direct GPU access:

```powershell
# Start llama-server with Vulkan backend — run ONCE, leave running for the session
llama-server.exe --model path\to\qwen3-8b-Q4_K_M.gguf --port 8080 --gpu-layers 99
```

> **Verify GPU is engaged:** watch Task Manager → GPU during an inference request. If GPU usage stays at 0%, the model is running on CPU — see [ADR 0002](docs/adr/0002-vulkan-over-rocm.md).

Containerised workers reach this host-side server at `http://host.docker.internal:8080` (not `localhost`).

---

## Documentation Map

| Document | Purpose |
|---|---|
| [Technical Specification](docs/technical-specification.md) | The authoritative source of truth: what the system does, why, and every design constraint. **If this disagrees with the code, fix the code.** |
| [Developer Guide](docs/developer-guide.md) | How to build it, in what order, with what conventions. Companion to the spec. |
| [Deployment Guide](docs/deployment-guide.md) | Complete start-to-finish setup on the Windows 11 target machine — prerequisites, models, Docker, OAuth, llama-server, and verification checklist. |
| [Architecture](docs/architecture.md) | Component overview, data flow, and infrastructure decisions. |
| [Runbook](docs/runbook.md) | Incident response — disk full, DB corruption, model crash-loop, OAuth revocation. |
| [ADRs](docs/adr/) | Architectural Decision Records — the reasoning behind each major technical choice. |
| [Changelog](CHANGELOG.md) | Release history and what changed in each version. |
| [Contributing](CONTRIBUTING.md) | Testing conventions and branching strategy. |
| [Security](SECURITY.md) | Vulnerability disclosure policy. |

---

## Repository Layout

```
autonomous-media/
  autonomous_media/
    api/              # FastAPI routers — auth, channels, sources, jobs, clips,
    │                 #   inventory, analytics, rights, system
    db/
    │  models.py      # 13 SQLAlchemy models matching spec §8.3
    │  migrations/    # Alembic versions
    scheduler/        # Job orchestrator + heartbeat-timeout recovery (spec §12.1)
    workers/          # One file per worker type (acquisition, transcription,
    │                 #   intelligence, vision, editing, rendering, quality_gate,
    │                 #   publishing, analytics, learning)
    sources/          # ContentSource protocol + YouTubeClipSource (spec §11.3)
    runtime/          # StageModelManager + ModelRuntime protocol (spec §12.9)
    rights/           # RightsGate + audit log (spec §11.4)
    prompts/          # Versioned prompt files (scoring_v3, title_v1, etc.)
    events.py         # Canonical event type constants (spec §7.3)
    config.py         # Pydantic ChannelConfig schema (spec §25.6)
    quota.py          # Daily YouTube API quota tracker (Pacific timezone, Redis-backed)
    exceptions.py     # Typed exception hierarchy
    logging.py        # JSON structured logger with trace_id
  eval/
  │  run_eval.py           # Precision@5 evaluation harness (spec §18.1)
  │  benchmark_dev_v1.jsonl    # 10-episode dev slice (to be labeled)
  │  benchmark_holdout_v1.jsonl  # 10-episode hold-out (never touched during tuning)
  dashboard/          # React + Tailwind operator console
  docker-compose.yml  # Postgres (pgvector), Redis, MinIO
  docs/               # Full documentation suite
  tests/
    unit/             # Pure functions: scoring math, config validation
    integration/      # Stage-to-stage with mocked ContentSource + ModelRuntime
    e2e/              # Full pipeline against fixture video
```
