# Autonomous Media (YTAuto)

An autonomous AI content production system. It continuously monitors source YouTube channels, downloads and transcribes long-form podcasts/interviews, scores and selects the best 30–90 second windows using a local LLM, renders them into vertical YouTube Shorts with animated `.ass` captions and branding, and publishes them on a configurable schedule — while requiring minimal ongoing human intervention.

**v1.8 scope:** podcast/interview clipping + operator-submitted curated stories (Reddit narration) · promotional-segment filtering · word-level `.ass` captions · background asset library · production-grade Telegram remote operations & alert subsystem · real-time hardware telemetry & coexistence governor · non-intrusive runtime stage profiler · 7-day TTL storage lifecycle retention engine · 9-page modular operator control center (React 19 + Vite) · single consumer PC (Windows 11, AMD Ryzen 5 5500, 16 GB RAM, RX 580 8 GB VRAM).

---

## Current Status

| Milestone | Status |
|---|---|
| Phase 0 — Foundation (infra, schema, API skeleton, dashboard) | ✅ Complete |
| Spec v1.2 Compliance Audit (16 schema/code gaps closed) | ✅ Complete — commit `5d21b02` |
| Phase 1 — Podcast Clipping MVP (all 10 pipeline workers implemented) | ✅ Complete — commit `391bfe1` |
| Phase 2 — AI Model Integration, Quota System, E2E Tests | ✅ Complete — commit `391bfe1` |
| Spec v1.5 Upgrade — promo filter · ASS captions · curated stories · background assets | ✅ Complete — see [CHANGELOG](CHANGELOG.md) |
| **Pipeline Remediation & Codebase Ownership Audit** (35/35 unit tests passing) | ✅ **Complete** — see [ENGINEERING_REMEDIATION](docs/ENGINEERING_REMEDIATION.md) |
| **Next-Gen Control Center & Telegram Alert Subsystem Overhaul** | ✅ **Complete** — see [Telegram Alerts](docs/telegram-alerts.md) |
| **Hardware Telemetry, Stage Profiling & 7-Day Storage Lifecycle Retention** (50/50 tests passing) | ✅ **Complete** — see [CHANGELOG](CHANGELOG.md#180) |

---

## Architecture & System Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   OPERATOR INTERFACES & BOT AGENTS                     │
│  ┌──────────────────────────────────┐  ┌────────────────────────────┐  │
│  │ React 19 Control Center (SPA)    │  │ Telegram Bot Remote Ops    │  │
│  │ Hash Router (#/overview, etc.)   │  │ Commands (/status, /jobs)  │  │
│  └──────────────────┬───────────────┘  └─────────────┬──────────────┘  │
└─────────────────────┼────────────────────────────────┼─────────────────┘
                      │                                │
                      ▼                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI GATEWAY SERVER                          │
│  REST API Gateway /api/v1  •  Static Frontend Mount  •  System Events  │
└─────────────────────┬──────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PIPELINE WORKERS & SERVICE LAYER                     │
│  Acquisition → Transcription → Intelligence → Vision → Editing →       │
│  Quality Gate → Publishing → Analytics → Telegram Notifier Service     │
└─────────────────────┬──────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           STATEFUL SERVICES                            │
│  PostgreSQL (pgvector)   •   Redis Queue   •   MinIO Object Storage    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

Install on the **host machine** (not in Docker):
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) & `npm`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — enable the **WSL2 backend** (Settings → General)
- [FFmpeg](https://ffmpeg.org/download.html) — add to `PATH`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — `pip install yt-dlp`
- A **Vulkan-compiled `llama-server`** binary (see [Deployment Guide](docs/deployment-guide.md))

### One-Click Start (recommended)

Double-click **`Start-Autonomous-Media.bat`** in the project root. It:
1. Starts Docker Desktop if not already running
2. Brings up Postgres, Redis, and MinIO via `docker compose`
3. Launches the Vulkan `llama-server` in a minimised window
4. Polls the health endpoint and opens the control center at `http://localhost:8000`

### Manual Setup

```powershell
# 1. Clone
git clone https://github.com/JohnApollos/YTAuto.git
cd YTAuto

# 2. Python environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Frontend compilation
cd frontend
npm install
npm run build
cd ..

# 4. Copy and fill in environment variables
copy .env.example .env
# Edit .env with your credentials (DATABASE_URL, YOUTUBE_OAUTH_*, JWT_SECRET, etc.)

# 5. Start stateful services (Postgres+pgvector, Redis, MinIO)
docker compose up -d

# 6. Apply database migrations
alembic upgrade head

# 7. Start the AI model server (leave this window open)
llama-server.exe --model models/qwen3-8b-Q4_K_M.gguf --port 8080 --gpu-layers 99

# 8. Start the FastAPI application server & React Control Center
uvicorn autonomous_media.main:app --host 0.0.0.0 --port 8000

# 9. In a separate terminal, start the autonomous background worker scheduler
python autonomous_media/main.py
```

---

## Key Features

- **Autonomous Production Engine**: Pipeline stages automatically download, transcribe, score, crop, render, and publish videos.
- **Curated Reddit Story Studio**: Submit text narratives (`r/AskReddit`, `r/AITA`) for automated Piper ONNX neural narration and word-level ASS caption rendering.
- **Telegram Remote Operations & Alerts Subsystem**: Real-time 5-severity alert notifications (`INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`), deduplication filter, incident aggregation, Quiet Hours, and bot remote commands (`/status`, `/jobs`, `/failed`, `/review`, `/quota`, `/health`).
- **Quality Gate Workbench**: Human-in-the-loop video review player with keyboard shortcuts (`Space`, `A`, `R`, `ArrowRight`, `ArrowLeft`).
- **Background Footage Pool**: Upload local `.mp4` video assets or register YouTube CC URLs.
- **YouTube API Quota Management**: Daily Pacific-timezone quota tracker preventing API ban thresholds.

---

## Documentation Map

| Document | Purpose |
|---|---|
| [Technical Specification](docs/technical-specification.md) | Authoritative system design, data models, worker state machine, and Telegram spec. |
| [Telegram Alerts & Remote Ops](docs/telegram-alerts.md) | Dedicated guide to Telegram severity policies, deduplication, commands, and security. |
| [Frontend Architecture](docs/frontend-architecture.md) | Modular React 19 SPA directory structure, state hooks, and API client design. |
| [Frontend Routes](docs/frontend-routes.md) | Inventory of all 9 control center hash URL routes (`#/overview`, `#/stories`, etc.). |
| [Frontend UX Audit](docs/frontend-ux-audit.md) | Product UI/UX audit, accessibility findings, and operator ergonomics specification. |
| [Developer Guide](docs/developer-guide.md) | Step-by-step developer onboarding, module structure, and worker conventions. |
| [Deployment Guide](docs/deployment-guide.md) | Production setup checklist, environment config, and Telegram verification checklist. |
| [Architecture](docs/architecture.md) | High-level component diagrams, job lifecycle state machine, and data flow. |
| [Runbook](docs/runbook.md) | Incident response runbook for worker crashes, DB locks, and Telegram alert failures. |
| [Engineering Remediation](docs/ENGINEERING_REMEDIATION.md) | Audit record of pipeline defects remediated and unit test verification. |
| [Changelog](CHANGELOG.md) | Detailed version release history. |
| [Contributing](CONTRIBUTING.md) | Repository workflow, testing conventions, and security rules. |
| [Security Policy](SECURITY.md) | Security vulnerability reporting and credential management policy. |

---

## Repository Layout

```text
YTAuto/
├── autonomous_media/
│   ├── api/                 # FastAPI endpoints (jobs, clips, stories, system, telegram)
│   ├── db/                  # SQLAlchemy models & Alembic migrations
│   ├── scheduler/           # Job queue dispatcher & heartbeat recovery
│   ├── services/
│   │   └── telegram/        # Telegram alert engine (models, client, policies, commands)
│   ├── workers/             # Production pipeline workers (acquisition, rendering, etc.)
│   ├── runtime/             # StageModelManager AI model server wrapper
│   ├── sources/             # ContentSource implementations (YouTubeClipSource, etc.)
│   └── quota.py             # YouTube API daily quota tracker
├── frontend/                # React 19 + Vite 8 modular SPA control center
│   ├── dist/                # Compiled static production bundle (served at http://localhost:8000)
│   └── src/
│       ├── components/      # UI primitives (Badge, ToastStack)
│       ├── features/        # Modular view components (stories, jobs, settings, etc.)
│       ├── hooks/           # Custom React hooks (useToast)
│       ├── services/        # API client wrapper
│       └── types/           # TypeScript data interfaces
├── docs/                    # Full technical documentation suite
├── tests/
│   └── unit/                # Unit test suite (43 passing tests)
├── docker-compose.yml       # Postgres (pgvector), Redis, MinIO
├── Start-Autonomous-Media.bat # One-click Windows launcher script
└── requirements.txt         # Python dependencies
```

---

## Security & Credential Management

- Bot tokens, API keys, and database passwords must **NEVER be committed to Git**.
- Always use `.env` for local configuration and place token secrets behind masked inputs in the UI (`••••••••••••`).
- Standard placeholders in examples: `<TELEGRAM_BOT_TOKEN>`, `<TELEGRAM_CHAT_ID>`, `<DATABASE_URL>`.
