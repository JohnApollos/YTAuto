# Autonomous Media - Windows 11 Deployment Guide

This guide provides a comprehensive, start-to-finish walkthrough for installing, configuring, and running the Autonomous Media V1.2 system on a brand-new Windows 11 target device equipped with an AMD GPU (e.g., RX 580).

## 1. Prerequisites Installation

You must install the following core software on the Windows 11 machine before proceeding:

1. **Git for Windows**:
   - Download and install from [git-scm.com](https://git-scm.com/download/win).
   - *Ensure "Git from the command line and also from 3rd-party software" is selected during setup.*
2. **Python 3.11+**:
   - Download from [python.org](https://www.python.org/downloads/windows/).
   - **Crucial:** Check the box that says **"Add Python to PATH"** at the very bottom of the installer window before clicking Install.
3. **Docker Desktop**:
   - Download and install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/).
   - Ensure the WSL 2 (Windows Subsystem for Linux) backend is enabled in Docker settings.
   - Start Docker Desktop and ensure the engine is running.
4. **Vulkan SDK** (For AMD GPU Inference):
   - Download and install the [Vulkan SDK](https://vulkan.lunarg.com/sdk/home).

## 2. Clone the Repository

Open **PowerShell** as Administrator and run:

```powershell
# Create a dedicated development directory
mkdir C:\dev
cd C:\dev

# Clone the codebase
git clone https://github.com/JohnApollos/YTAuto.git
cd YTAuto
```

## 3. Python Environment Setup

Create a virtual environment and install the required dependencies:

```powershell
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install the dependencies
pip install -r requirements.txt
```

> [!NOTE]
> If you receive an error about running scripts being disabled on this system when activating the virtual environment, run: `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` and try again.

## 4. Environment Configuration (.env)

The system requires environment variables to connect to databases and services. We have provided an example file.

```powershell
# Copy the example environment file
copy .env.example .env
```

Open `.env` in Notepad and ensure the following keys are set. For local development, the defaults map to the Docker containers we will start in the next step:

```env
DATABASE_URL=postgresql+psycopg2://autonomous:autonomous@localhost/autonomous_media
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
YOUTUBE_OAUTH_CLIENT_ID=your_client_id
YOUTUBE_OAUTH_CLIENT_SECRET=your_client_secret
JWT_SECRET=super_secret_key
MODEL_RESIDENCY=swap
```

## 5. Start Stateful Services (Docker)

The system relies on PostgreSQL (with pgvector), Redis, and MinIO. These are managed via Docker Compose.

```powershell
# Start the services in the background
docker compose up -d postgres redis minio
```

Wait 10-15 seconds for the database to fully initialize.

## 6. Database Migration

Now that PostgreSQL is running, apply the database schema. This creates the 13 tables required by the V1.2 Technical Specification (including `jobs`, `channels`, `transcripts`, `inventory_items`, and `pgvector` extensions).

```powershell
# Run the Alembic migrations
alembic upgrade head
```

## 7. Download AI Models

Because ROCm is not supported on the RX 580, inference is handled by a Vulkan-compiled `llama.cpp` server (`ModelRuntimeManager`). You need to download the `.gguf` weights to the `models/` directory.

```powershell
# Create the models directory
mkdir models
```

Download the following files into the `models/` directory:
1. **LLM**: [Qwen 3 8B Instruct (Q4_K_M)](https://huggingface.co/Qwen/Qwen-7B-Chat-GGUF)
2. **VLM**: [Qwen2.5-VL 7B (Q4_K_M)](https://huggingface.co/Qwen/Qwen-VL-Chat-GGUF)
3. **ASR**: [Whisper Large-v3 Turbo (ggml-large-v3-turbo.bin)](https://huggingface.co/ggerganov/whisper.cpp)

## 8. Start the System

You must start the API server and the Background Worker Fleet. Open two separate PowerShell windows.

**Terminal 1: Start the FastAPI Server**
```powershell
cd C:\dev\YTAuto
.\.venv\Scripts\Activate.ps1
uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2: Start the Worker Fleet & Scheduler**
```powershell
cd C:\dev\YTAuto
.\.venv\Scripts\Activate.ps1
python autonomous_media/main.py
```

The system is now fully configured and running! You can access the API Swagger UI at `http://localhost:8000/docs` and the Dashboard (if served) at `http://localhost:8000/`.
