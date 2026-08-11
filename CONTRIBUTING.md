# Contributing to Autonomous Media (YTAuto)

Thank you for contributing to YTAuto. These guidelines serve as the authoritative standard for code quality, testing conventions, architecture patterns, security rules, and documentation standards.

---

## 1. Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ & `npm`
- Docker Desktop (WSL2 backend enabled)
- FFmpeg (added to system `PATH`)

### Backend Setup
```powershell
# 1. Virtual Environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment Variables
copy .env.example .env

# 3. Stateful Infrastructure (Postgres, Redis, MinIO)
docker compose up -d

# 4. Database Migrations
alembic upgrade head
```

### Frontend Setup
```powershell
cd frontend
npm install
npm run dev     # Starts Vite development server at http://localhost:5173
npm run build   # Compiles production bundle to frontend/dist
```

---

## 2. Directory Architecture

```text
YTAuto/
├── autonomous_media/
│   ├── api/                 # FastAPI REST routers
│   ├── db/                  # SQLAlchemy models & Alembic migrations
│   ├── scheduler/           # Job queue orchestrator & heartbeat monitor
│   ├── services/
│   │   └── telegram/        # Telegram alert engine & bot command dispatcher
│   ├── workers/             # Pipeline worker processes
│   ├── runtime/             # StageModelManager AI model server bridge
│   ├── sources/             # ContentSource implementations
│   └── quota.py             # YouTube API daily quota tracker
├── frontend/                # React 19 + Vite 8 control center SPA
│   └── src/
│       ├── components/      # UI primitives (Badge, ToastStack)
│       ├── features/        # Modular view features (stories, jobs, settings, etc.)
│       ├── hooks/           # Custom React hooks (useToast)
│       ├── services/        # API client wrapper
│       └── types/           # TypeScript interfaces
├── docs/                    # Architecture, API, and subsystem specs
└── tests/                   # Automated unit and integration tests
```

---

## 3. Development & Testing Workflow

### Running Unit Tests
All tests are executed using `pytest`:
```powershell
.venv\Scripts\python -m pytest tests/unit/ -v
```
Ensure all **43 unit tests pass** before creating a pull request.

### Testing Telegram Integration Safely
- **NEVER hardcode real Telegram bot tokens or Chat IDs in code or tests.**
- Use mock credentials or test via the Settings UI (`#/settings`).
- Unit tests use `unittest.mock.patch` to mock `TelegramClient` and DB sessions:
```powershell
.venv\Scripts\python -m pytest tests/unit/test_telegram_subsystem.py -v
```

---

## 4. Coding & Security Rules

1. **No Hardcoded Credentials**: Bot tokens, API keys, and database URIs must be loaded from `.env` or database settings tables.
2. **Masked Secrets**: API endpoints returning bot configuration must mask tokens (`bot_token_masked`).
3. **Non-Blocking Observability**: Telegram notifications must run asynchronously in background queues; external API failures must **never block video workers**.
4. **HTML/Markdown Escaping**: All user-provided strings (Reddit titles, errors) must pass through `escape_html()` or `escape_markdown_v2()` before Telegram card rendering.
5. **Git Discipline**:
   - Feature branches: `feature/name` or `fix/name`.
   - Target branch: `master`.
   - Never commit `.env` or binary model files (`models/piper/`).
