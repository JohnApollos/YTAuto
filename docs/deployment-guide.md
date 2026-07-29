# Autonomous Media — Deployment Guide

**Target:** Windows 11 machine with an AMD GPU (RX 580 or equivalent)
**Source:** This codebase lives at https://github.com/JohnApollos/YTAuto
**Scope:** Complete start-to-finish setup on a machine that has never run this system before. This guide covers every piece of software, every command, and every credential required.

> **Development vs Target Device**
> The codebase is authored on a separate development machine. You are reading this to set up the *target* machine — the machine that will run the system continuously. The only transfer mechanism needed is `git clone` from GitHub; no files are copied manually.

---

## Part 1 — System Prerequisites

Install each item in this order. All are one-time installs.

### 1.1 Git for Windows

Download: https://git-scm.com/download/win

During setup, select:
- ✅ "Git from the command line and also from 3rd-party software"
- ✅ "Use Windows' default console window"

Verify:
```powershell
git --version
# git version 2.x.x.windows.x
```

---

### 1.2 Python 3.11+

Download: https://www.python.org/downloads/windows/ — select **Python 3.11.x** or newer.

During setup:
- ✅ **"Add Python to PATH"** (the checkbox at the very bottom of the first screen — do not miss this)
- ✅ "Install for all users" (recommended)

Verify:
```powershell
python --version
# Python 3.11.x
pip --version
```

---

### 1.3 Docker Desktop

Download: https://docs.docker.com/desktop/install/windows-install/

During setup:
- ✅ Enable the **WSL 2 backend** (Docker Settings → General → "Use the WSL 2 based engine")

After install, start Docker Desktop and wait until the whale icon in the system tray shows "Docker Desktop is running." Do not proceed until Docker is fully up.

Verify:
```powershell
docker --version
docker compose version
```

---

### 1.4 FFmpeg

FFmpeg handles all video encode/decode. It must be on the system `PATH` — the Python `ffmpeg-python` library is a wrapper that calls the `ffmpeg.exe` binary.

1. Download the latest full build: https://www.gyan.dev/ffmpeg/builds/ → **"ffmpeg-release-full.7z"**
2. Extract to `C:\ffmpeg\`
3. Add to PATH: System Properties → Advanced → Environment Variables → Path → New → `C:\ffmpeg\bin`

Verify (open a **new** PowerShell window after editing PATH):
```powershell
ffmpeg -version
# ffmpeg version 7.x
```

---

### 1.5 AMD Vulkan Runtime

The AMD Adrenalin driver installer includes the Vulkan runtime automatically. If you have Adrenalin 24.x or later installed, Vulkan is already present.

Verify:
```powershell
# Install the Vulkan SDK for the vulkaninfo tool
winget install KhronosGroup.VulkanSDK

vulkaninfo --summary
# Should list: GPU 0: AMD Radeon RX 580
```

If `vulkaninfo` reports no Vulkan-capable devices, reinstall the AMD Adrenalin driver (24.x or later) from https://www.amd.com/en/support.

---

### 1.6 Visual C++ Redistributable

Some Python packages with C extensions require the MSVC runtime. Download and install if not already present:

https://aka.ms/vs/17/release/vc_redist.x64.exe

---

## Part 2 — Get the Codebase

Open **PowerShell** (run as Administrator for the `mkdir C:\dev` step):

```powershell
# Create a project root
mkdir C:\dev
cd C:\dev

# Clone from GitHub
git clone https://github.com/JohnApollos/YTAuto.git
cd YTAuto
```

Verify:
```powershell
# You should see the project structure
ls
# autonomous_media  dashboard  docs  docker-compose.yml  requirements.txt  ...
```

---

## Part 3 — Python Environment

```powershell
# Create a virtual environment inside the project folder
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1
```

> [!NOTE]
> If you get "running scripts is disabled on this system", run this first:
> ```powershell
> Set-ExecutionPolicy Unrestricted -Scope CurrentUser
> ```
> Then re-run the activate command.

```powershell
# Upgrade pip and install all dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This installs: FastAPI, SQLAlchemy, Alembic, psycopg2, pgvector, Redis, MinIO, yt-dlp, faster-whisper, ffmpeg-python, mediapipe, paddleocr, pyannote.audio, Prometheus, and all other project dependencies.

> [!NOTE]
> `paddlepaddle` and `pyannote.audio` are large packages (~2 GB total download). Allow 10–20 minutes on a typical connection.

Verify:
```powershell
python -c "import fastapi, sqlalchemy, faster_whisper, yt_dlp; print('OK')"
# OK
```

---

## Part 4 — AI Models

The system uses local AI inference. Models must be downloaded onto the target machine. Create the models directory inside the project:

```powershell
mkdir C:\dev\YTAuto\models
```

### 4.1 Qwen 3 8B Instruct — LLM (clip scoring, title/description generation)

Download: https://huggingface.co/Qwen/Qwen3-8B-GGUF

File to download: **`Qwen3-8B-Q4_K_M.gguf`** (~5.2 GB)

```powershell
# Using huggingface-cli (pip install huggingface_hub)
pip install huggingface_hub
huggingface-cli download Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf --local-dir C:\dev\YTAuto\models
```

### 4.2 Qwen2.5-VL 7B — Vision LLM (speaker tracking context, OCR)

Download: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct-GGUF

File to download: **`Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf`** (~4.8 GB)

```powershell
huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct-GGUF Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf --local-dir C:\dev\YTAuto\models
```

### 4.3 Whisper Large-v3 Turbo — Speech Recognition

`faster-whisper` downloads the model automatically on first use. However, to avoid a delay on first run and to enable offline operation, pre-download it now:

```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')"
# This downloads ~1.6 GB to %USERPROFILE%\.cache\huggingface
```

### 4.4 llama-server Binary (Vulkan-compiled)

`llama-server` is the local HTTP inference server for the LLMs. It must be compiled with Vulkan support for the RX 580. Pre-built Vulkan binaries are available from the `llama.cpp` release page:

1. Go to: https://github.com/ggerganov/llama.cpp/releases/latest
2. Download: **`llama-<version>-bin-win-vulkan-x64.zip`**
3. Extract to `C:\dev\llama\`
4. Add to PATH: Environment Variables → Path → New → `C:\dev\llama`

Verify (in a **new** PowerShell window):
```powershell
llama-server --version
# version: xxxx (xxxxxxxx)
# built with ...
# Vulkan  ... ← must appear in the output
```

If Vulkan does not appear, you downloaded the wrong binary variant. Re-download the `vulkan` build specifically.

---

## Part 5 — Environment Configuration

```powershell
cd C:\dev\YTAuto
copy .env.example .env
notepad .env
```

Fill in every value. The file should look like this (replace the placeholder values):

```env
# Database — maps to the Postgres container started in Part 6
DATABASE_URL=postgresql+psycopg2://autonomous:autonomous@localhost:5432/autonomous_media

# Cache — maps to the Redis container
REDIS_URL=redis://localhost:6379/0

# Object storage — maps to the MinIO container
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# YouTube API — from Google Cloud Console (see Part 9)
YOUTUBE_OAUTH_CLIENT_ID=your_client_id_here
YOUTUBE_OAUTH_CLIENT_SECRET=your_client_secret_here

# Auth — generate a long random string (min 32 chars)
JWT_SECRET=replace_with_a_long_random_secret_string_minimum_32_chars

# AI model residency — 'swap' is correct for 16 GB RAM (see ADR 0005)
MODEL_RESIDENCY=swap
```

> [!IMPORTANT]
> Never commit `.env` to Git. It is already listed in `.gitignore`.

---

## Part 6 — Start Stateful Services (Docker)

PostgreSQL (with the pgvector extension), Redis, and MinIO all run in Docker. The `llama-server` runs natively — see Part 10.

```powershell
cd C:\dev\YTAuto

# Start Postgres, Redis, and MinIO as background services
docker compose up -d postgres redis minio
```

Wait 15 seconds, then verify all three are healthy:

```powershell
docker compose ps
# NAME                          STATUS
# autonomous_media_postgres     Up (healthy)
# autonomous_media_redis        Up (healthy)
# autonomous_media_minio        Up (healthy)
```

If any service shows `Up (starting)` wait another 10 seconds and check again. Do not proceed until all three are `(healthy)`.

---

## Part 7 — Database Migrations

Apply the schema to the freshly started Postgres instance:

```powershell
cd C:\dev\YTAuto
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Expected output (last lines):
```
INFO  [alembic.runtime.migration] Running upgrade  -> d081f2fc0740, Align_schema_with_V1_2_Spec
INFO  [alembic.runtime.migration] Running upgrade d081f2fc0740 -> a1b2c3d4e5f6, Fix schema gaps to fully match V1.2 spec §8.3
```

Verify the pgvector extension was created:
```powershell
docker exec -it autonomous_media_postgres psql -U autonomous autonomous_media -c "\dx"
# Should list: vector | ... | pgvector ...
```

---

## Part 8 — Create MinIO Buckets
 
The object storage buckets must exist before the first worker run. 

> [!NOTE]
> In Phase 2+, the system automatically checks and creates these four buckets on startup inside the scheduler (`ensure_all_buckets()`). If you start the scheduler first, this step is handled for you.

However, if you want to create them manually or verify their existence beforehand, you can run the following commands:

```powershell
# Using Docker to run the MinIO Client (mc) — no extra install needed
docker run --rm --network host minio/mc alias set local http://localhost:9000 minioadmin minioadmin
docker run --rm --network host minio/mc mb local/autonomous-media-raw
docker run --rm --network host minio/mc mb local/autonomous-media-transcripts
docker run --rm --network host minio/mc mb local/autonomous-media-renders
docker run --rm --network host minio/mc mb local/autonomous-media-branding
```

Verify at the MinIO console: http://localhost:9001 (login: `minioadmin` / `minioadmin`). You should see 4 buckets.

---

## Part 9 — Google Cloud OAuth Setup

Each YouTube channel the system publishes to requires its own OAuth credential pair. Do this once per channel.

1. Go to https://console.cloud.google.com/
2. Create a new project (or use an existing one). **Use one project per channel** — this isolates each channel's 10,000 units/day quota from the others (spec §5.1).
3. Enable the **YouTube Data API v3** for the project (APIs & Services → Library → search "YouTube Data API v3" → Enable).
4. Create credentials:
   - APIs & Services → Credentials → Create Credentials → **OAuth 2.0 Client IDs**
   - Application type: **Desktop app**
   - Download the JSON file
5. Copy `client_id` and `client_secret` from the JSON into `.env`.
6. In the OAuth consent screen, add the Google account that owns the YouTube channel as a **Test User**. The system will not be able to authenticate to a channel whose account is not listed here (while the app is in "Testing" status).

> [!IMPORTANT]
> Google refresh tokens issued for apps in "Testing" status expire after **7 days**. To avoid weekly re-authentication, submit the app for verification via OAuth consent screen → "Publish App." Verification can take 2–4 weeks but grants indefinite refresh tokens.

---

## Part 10 — Start the AI Model Server

The `llama-server` process runs natively on Windows — not in Docker — to get direct access to the RX 580 via Vulkan. Open a dedicated PowerShell window and keep it running:

**Terminal A — LLM Server (Qwen 3 8B):**
```powershell
llama-server.exe `
  --model C:\dev\YTAuto\models\Qwen3-8B-Q4_K_M.gguf `
  --port 8080 `
  --gpu-layers 99 `
  --ctx-size 32768 `
  --threads 6
```

Wait for:
```
llama_new_context_with_model: n_ctx      = 32768
...
main: server is listening on 127.0.0.1:8080
```

Verify GPU is engaged:
```powershell
# In a separate window
Invoke-RestMethod -Uri http://localhost:8080/health
# {"status":"ok"}
```

Then open **Task Manager → Performance → GPU** and watch GPU usage spike during a test inference. If GPU stays at 0%, the Vulkan backend is not active — review §1.5.

> [!NOTE]
> The VLM (Qwen2.5-VL) runs on the **same port** via the `StageModelManager` swap mechanism — it starts `llama-server` with a different `--model` path when a Vision stage job is dispatched. You do not need to start a separate server for it.

---

## Part 11 — Start the Application

Open two more PowerShell windows:

**Terminal B — FastAPI (REST API + Dashboard):**
```powershell
cd C:\dev\YTAuto
.\.venv\Scripts\Activate.ps1
uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Wait for:
```
INFO:     Application startup complete.
```

Verify:
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/system/health
# {"status":"ok"}
```

**Terminal C — Scheduler + Workers:**
```powershell
cd C:\dev\YTAuto
.\.venv\Scripts\Activate.ps1
python autonomous_media/main.py
```

The Scheduler will log `Scheduler starting` and begin its 5-second poll loop.

---

## Part 12 — Verification Checklist

Run through this checklist to confirm the system is fully operational:

```powershell
# 1. All Docker services healthy
docker compose ps

# 2. API responds
Invoke-RestMethod http://localhost:8000/api/v1/system/health

# 3. Swagger UI accessible
Start-Process "http://localhost:8000/docs"

# 4. Dashboard accessible
Start-Process "http://localhost:8000/"

# 5. MinIO console accessible
Start-Process "http://localhost:9001"

# 6. llama-server healthy
Invoke-RestMethod http://localhost:8080/health

# 7. Database has all 13 tables
docker exec -it autonomous_media_postgres psql -U autonomous autonomous_media -c "\dt"
# Should list: analytics_snapshots, channels, clip_candidates, clips,
#              content_sources, eval_runs, inventory_items, jobs, models,
#              rights_records, source_videos, system_events, topics, transcripts
```

All checks should pass before adding any channels or sources.

---

## Part 13 — Keeping the System Updated

When a new version is pushed to GitHub:

```powershell
cd C:\dev\YTAuto

# 1. Stop the Scheduler (Ctrl+C in Terminal C)
# 2. Pull latest code
git pull origin master

# 3. Install any new dependencies
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Apply any new migrations
alembic upgrade head

# 5. Restart Terminal B and Terminal C
```

Docker services (Postgres, Redis, MinIO) do **not** need to be restarted for code updates. Only restart them if `docker-compose.yml` itself changed.

---

## Part 14 — Troubleshooting

For incident response during operation, see [`docs/runbook.md`](runbook.md). The most common setup-time issues are:

| Problem | Fix |
|---|---|
| `Activate.ps1 cannot be loaded, scripts disabled` | `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` |
| `alembic: command not found` | Virtual environment is not activated. Run `.\.venv\Scripts\Activate.ps1` first. |
| `type "vector" does not exist` during migration | `docker exec -it autonomous_media_postgres psql -U autonomous autonomous_media -c "CREATE EXTENSION IF NOT EXISTS vector;"` then re-run `alembic upgrade head` |
| `docker compose ps` shows `(unhealthy)` for Postgres | Wait 30 seconds after `docker compose up -d` — Postgres init takes longer than the healthcheck interval on slow disks |
| `llama-server` exits immediately | Check that the `.gguf` file path is correct and the file downloaded completely (verify file size matches HuggingFace) |
| GPU stays at 0% during inference | Download the `vulkan` variant of llama-server specifically; confirm AMD Adrenalin 24.x is installed |
| `NoSuchBucket` on first worker run | Run the MinIO bucket creation commands from Part 8 |
| YouTube API `403 accessNotConfigured` | YouTube Data API v3 is not enabled in the Google Cloud project — enable it in APIs & Services → Library |
| YouTube API `401 invalid_grant` | OAuth refresh token expired (Testing app, 7-day limit) — re-authenticate via the Dashboard or promote the app to "In production" |

---

## Part 15 — Keeping the Codebase Synced (git pull Workflow)

The dev machine and the target (production) machine share the same repository on GitHub. All code changes are authored on the dev machine and pushed to GitHub; the production machine pulls them down. Never edit code directly on the production machine.

### 15.1 Standard Update Procedure

Run this sequence on the **production machine** whenever deploying a new version:

```powershell
# 1. Activate the virtual environment (if not already active)
.\.venv\Scripts\Activate.ps1

# 2. Pull the latest changes from GitHub
git fetch origin
git status          # check for any unexpected local modifications — there should be none

git pull origin master   # or main, whichever is the default branch

# 3. Install any new Python dependencies
pip install -r requirements.txt

# 4. Check if there are new Alembic migrations
#    If new migration files appear under autonomous_media/db/migrations/versions/, run:
alembic upgrade head

# 5. Rebuild Docker images if docker-compose.yml or any Dockerfile changed
#    (git diff HEAD~1 docker-compose.yml to check)
docker compose build

# 6. Restart all services to pick up the new code
docker compose down
docker compose up -d

# 7. Verify the system came back healthy (see Part 16 for full verification)
curl http://localhost:8000/api/v1/system/health
```

### 15.2 Before Running `alembic upgrade head` on Real Data

Per spec §15.3 and developer guide §8 — this is mandatory, not optional:

```powershell
# Backup the database before EVERY migration against real data
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
docker exec autonomous_media_postgres pg_dump -U autonomous autonomous_media `
  > "backups\db_backup_pre_migration_$timestamp.sql"

# Preview what the migration will execute (dry run — no changes made)
alembic upgrade head --sql

# Only after reviewing the SQL output and creating the backup:
alembic upgrade head
```

### 15.3 Checking What Changed Before Pulling

```powershell
# See what commits are incoming without applying them
git fetch origin
git log HEAD..origin/master --oneline

# See which files changed in those commits
git diff HEAD origin/master --name-only

# If migrations/ or requirements.txt appear in the diff, those steps are required
```

### 15.4 Rolling Back a Bad Update

```powershell
# Revert to the previous commit (keeps changes staged, easy to undo)
git revert HEAD

# Or hard reset to a specific commit (destructive — local uncommitted changes lost)
git reset --hard <commit-hash>

# Roll back the Alembic migration (each migration has a downgrade() function)
alembic downgrade -1

# Restore database from backup if needed
docker exec -i autonomous_media_postgres psql -U autonomous autonomous_media `
  < "backups\db_backup_pre_migration_<timestamp>.sql"

# Restart services
docker compose down
docker compose up -d
```

### 15.5 Checking the Currently Deployed Version

```powershell
# Show the current git commit and tag on the production machine
git log -1 --format="%H %s %ci"
git describe --tags --always

# Show the current Alembic migration state
alembic current

# Show running container image digests
docker compose ps
```

---

## Part 16 — System Verification Checklist

Run this after initial deployment, after every `git pull` update, or any time the system is not behaving as expected. Each check is a single command — if it passes, move on; if it fails, the inline note tells you which Part to revisit.

### 16.1 Python Environment

```powershell
# Verify Python version is 3.11+
python --version
# Expected: Python 3.11.x or higher

# Verify virtual environment is active and packages installed
pip show faster-whisper yt-dlp minio sqlalchemy alembic | Select-String "Name|Version"
# Expected: all five packages listed with version numbers

# Verify the autonomous_media package itself imports cleanly
python -c "import autonomous_media; print('Package import: OK')"
# Expected: "Package import: OK"  — any ImportError means a broken dependency or missing file
```

**If fails:** re-run `pip install -r requirements.txt`. If errors persist, check Python version and virtual environment activation.

### 16.2 Docker Services

```powershell
# All three core services must be running and healthy
docker compose ps
# Expected: postgres, redis, minio all show "running (healthy)"

# Quick connectivity test for each service
docker exec autonomous_media_postgres pg_isready -U autonomous
# Expected: "localhost:5432 - accepting connections"

docker exec autonomous_media_redis redis-cli ping
# Expected: "PONG"

# MinIO web console should respond
Invoke-WebRequest -Uri "http://localhost:9001" -UseBasicParsing | Select-Object StatusCode
# Expected: StatusCode 200
```

**If fails:** `docker compose up -d`. If still unhealthy after 60 seconds, check `docker compose logs <service>`.

### 16.3 Database & Migrations

```powershell
# Verify pgvector extension is present
docker exec autonomous_media_postgres psql -U autonomous autonomous_media `
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
# Expected: one row showing "vector | <version>"

# Verify Alembic is at the latest migration head
alembic current
# Expected: last revision hash with "(head)" suffix — no "heads" mismatch

# Verify all 13 core tables exist
docker exec autonomous_media_postgres psql -U autonomous autonomous_media `
  -c "\dt"
# Expected: channels, clip_candidates, clips, content_sources, eval_runs, 
#           inventory_items, jobs, models, rights_records, source_videos,
#           system_events, topics, transcripts  — all 13 listed
```

**If fails:**
- Missing `vector` extension: see Part 4
- Migration mismatch: run `alembic upgrade head` (after backup — see Part 15.2)
- Missing tables: run `alembic upgrade head` from scratch

### 16.4 MinIO Buckets

```powershell
# All four required buckets must exist
python -c "
from minio import Minio
import os
from dotenv import load_dotenv
load_dotenv()
client = Minio(
    os.environ['MINIO_ENDPOINT'],
    access_key=os.environ['MINIO_ACCESS_KEY'],
    secret_key=os.environ['MINIO_SECRET_KEY'],
    secure=False
)
required = ['autonomous-media-raw','autonomous-media-transcripts','autonomous-media-renders','autonomous-media-branding']
found = [b.name for b in client.list_buckets()]
missing = [b for b in required if b not in found]
print('Buckets OK:', required) if not missing else print('MISSING:', missing)
"
# Expected: "Buckets OK: ['autonomous-media-raw', ...]"
```

**If fails:** run the bucket creation commands from Part 8, or restart the system — `ensure_all_buckets()` runs automatically on startup (Phase 2+).

### 16.5 API Server

```powershell
# Health endpoint must return HTTP 200
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/system/health" -UseBasicParsing
$response.StatusCode
# Expected: 200

$response.Content
# Expected: JSON with status "healthy" and all services listed as up
```

**If fails:** check `docker compose logs api` for the startup error. Most common causes: bad `DATABASE_URL` in `.env`, Postgres not yet healthy, missing migration.

### 16.6 FFmpeg

```powershell
# FFmpeg must be on PATH and the AMF hardware encoder must be available
ffmpeg -version 2>&1 | Select-String "^ffmpeg version"
# Expected: "ffmpeg version N.xxx ..."

ffmpeg -hide_banner -encoders 2>&1 | Select-String "h264_amf"
# Expected: "V..... h264_amf" — if blank, AMF is unavailable (fall back to libx264; rendering works but is CPU-only)

# Test that ffmpeg can probe a media file (basic sanity check)
ffprobe -v quiet -print_format json -show_streams "$(python -c "import shutil; print(shutil.which('ffprobe'))")" 2>&1
# Just checking ffprobe runs without error
```

**If fails:** add FFmpeg `bin\` directory to `PATH`. See Part 6 of this guide.

### 16.7 Whisper / faster-whisper

```powershell
# faster-whisper must load without error
python -c "
from faster_whisper import WhisperModel
model = WhisperModel('tiny', device='cpu', compute_type='int8')
segs, info = model.transcribe('nul', language='en')
print('faster-whisper: OK')
" 2>&1 | Select-String "OK|Error|CUDA"
# Expected: "faster-whisper: OK"
# Note: 'nul' is the Windows null device — this just checks the library loads
```

**If fails:** `pip install faster-whisper`. If CUDA errors appear even though you're using CPU, add `CUDA_VISIBLE_DEVICES=` (blank) to `.env` to suppress GPU detection.

### 16.8 llama-server (Vulkan LLM Runtime)

```powershell
# llama-server must be running and responding on port 8080
Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing | Select-Object StatusCode, Content
# Expected: StatusCode 200, Content includes "{"status":"ok"}"

# Confirm GPU is being used — send a small inference request while watching Task Manager GPU
# In a second terminal: watch GPU utilization in Task Manager > Performance > GPU
$body = '{"model":"qwen3","messages":[{"role":"user","content":"Say: test"}],"max_tokens":5}'
Invoke-WebRequest -Uri "http://localhost:8080/v1/chat/completions" `
  -Method Post -ContentType "application/json" -Body $body -UseBasicParsing | `
  Select-Object StatusCode
# Expected: StatusCode 200
# In Task Manager: GPU utilization should spike during this call (non-zero %)
# If GPU stays at 0%: llama-server is running on CPU — re-download the Vulkan binary (Part 7)
```

**If fails — server not running:** start `llama-server` manually per Part 7 of this guide. It must be started before any AI-dependent pipeline stage runs.

**If fails — GPU at 0%:** confirm you downloaded the `vulkan` build variant, not the CPU build. Confirm AMD Adrenalin 24.x drivers are installed. Confirm the `.gguf` model file path in your `llama-server` start command is correct.

### 16.9 yt-dlp

```powershell
# yt-dlp must be on PATH and able to reach YouTube
yt-dlp --version
# Expected: a version string like "2025.xx.xx"

# Quick live test — just get video info, no download
yt-dlp --dump-json "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | `
  python -c "import sys,json; d=json.load(sys.stdin); print('yt-dlp live test OK, title:', d['title'])"
# Expected: "yt-dlp live test OK, title: ..."
```

**If fails:** `pip install -U yt-dlp`. If network errors: check firewall / proxy settings.

### 16.10 Unit Test Suite

```powershell
# All 17 unit tests must pass — any failure before you've changed anything means a broken installation
pytest tests/unit/ -v --tb=short
# Expected: 17 passed, 0 failed, 0 errors
```

**If fails:** check the error output for which module is failing to import. Usually indicates a missing dependency (`pip install -r requirements.txt`) or a wrong `DATABASE_URL` (unit tests should not need a live database — if they do, something is importing a DB-dependent module at test collection time).

### 16.11 End-to-End Summary Check

Run all of the above in sequence and get a pass/fail summary:

```powershell
# Save as scripts/verify.ps1 and run it after every deployment
$pass = 0; $fail = 0

function Check($label, $cmd) {
    try {
        $result = Invoke-Expression $cmd 2>&1
        if ($LASTEXITCODE -eq 0 -or $result -match "OK|PONG|healthy|passed") {
            Write-Host "  [PASS] $label" -ForegroundColor Green; $script:pass++
        } else {
            Write-Host "  [FAIL] $label" -ForegroundColor Red; Write-Host "         $result" -ForegroundColor DarkRed; $script:fail++
        }
    } catch {
        Write-Host "  [FAIL] $label - Exception: $_" -ForegroundColor Red; $script:fail++
    }
}

Write-Host "`nAutonomous Media - System Verification" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

Check "Python 3.11+"              'python --version'
Check "Package import"            'python -c "import autonomous_media; print(\"OK\")"'
Check "Docker services healthy"   'docker compose ps | Select-String "healthy"'
Check "Postgres ready"            'docker exec autonomous_media_postgres pg_isready -U autonomous'
Check "Redis ping"                'docker exec autonomous_media_redis redis-cli ping'
Check "pgvector extension"        'docker exec autonomous_media_postgres psql -U autonomous autonomous_media -c "SELECT 1 FROM pg_extension WHERE extname=''vector''"'
Check "Alembic at head"           'alembic current 2>&1 | Select-String "head"'
Check "API health"                '(Invoke-WebRequest -Uri http://localhost:8000/api/v1/system/health -UseBasicParsing).StatusCode -eq 200'
Check "FFmpeg on PATH"            'ffmpeg -version'
Check "faster-whisper import"     'python -c "from faster_whisper import WhisperModel; print(\"OK\")"'
Check "llama-server health"       '(Invoke-WebRequest -Uri http://localhost:8080/health -UseBasicParsing).StatusCode -eq 200'
Check "yt-dlp on PATH"            'yt-dlp --version'
Check "Unit tests (17)"           'pytest tests/unit/ -q --tb=no 2>&1 | Select-String "passed"'

Write-Host "`nResult: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) {"Green"} else {"Red"})
if ($fail -eq 0) { Write-Host "System is ready." -ForegroundColor Green }
else { Write-Host "Fix the failing checks before running the pipeline." -ForegroundColor Yellow }
```

Run it with:
```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\verify.ps1
```

**Expected output when everything is healthy:**
```
Autonomous Media - System Verification
=======================================
  [PASS] Python 3.11+
  [PASS] Package import
  [PASS] Docker services healthy
  [PASS] Postgres ready
  [PASS] Redis ping
  [PASS] pgvector extension
  [PASS] Alembic at head
  [PASS] API health
  [PASS] FFmpeg on PATH
  [PASS] faster-whisper import
  [PASS] llama-server health
  [PASS] yt-dlp on PATH
  [PASS] Unit tests (17)

Result: 13 passed, 0 failed
System is ready.
```
