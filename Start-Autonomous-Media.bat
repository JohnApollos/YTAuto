@echo off
setlocal enabledelayedexpansion
title Autonomous Media - All-in-One Startup
color 0A

echo ===================================================
echo   Autonomous Media System - Automated Startup
echo ===================================================
echo.

cd /d "%~dp0"

:: ---------------------------------------------------------------
:: Step 1: Check for GitHub Updates
:: ---------------------------------------------------------------
echo [1/8] Checking for GitHub code updates...
git pull origin master
echo.

:: ---------------------------------------------------------------
:: Step 2: Install / Update Python Requirements
:: ---------------------------------------------------------------
echo [2/8] Installing / verifying Python requirements...
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    echo       Python dependencies up to date.
) else (
    echo       WARNING: .venv not found! Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo.

:: ---------------------------------------------------------------
:: Step 3: Docker Desktop & Services
:: ---------------------------------------------------------------
echo [3/8] Checking Docker Desktop...
docker info >NUL 2>&1
if errorlevel 1 (
    echo       Docker Desktop daemon not running. Launching Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    set /a WAIT_COUNT=0
    :WAIT_DOCKER
    timeout /t 4 /nobreak >NUL
    docker info >NUL 2>&1
    if errorlevel 1 (
        set /a WAIT_COUNT+=1
        if !WAIT_COUNT! GEQ 30 (
            echo.
            echo       Docker Desktop took longer than 2 minutes to start.
            echo       Please verify Docker Desktop is running and press any key to continue.
            pause
            goto WAIT_DOCKER
        )
        goto WAIT_DOCKER
    )
)
echo       Docker daemon is ready.
echo.

echo [4/8] Starting stateful container services (Postgres, Redis, MinIO)...
docker compose up -d
if errorlevel 1 (
    echo       WARNING: docker compose encountered an issue. Check container logs.
)
echo       Container services are running.
echo.

:: ---------------------------------------------------------------
:: Step 5: Database Migrations
:: ---------------------------------------------------------------
echo [5/8] Running database migrations (alembic)...
.venv\Scripts\python.exe -m alembic upgrade head
echo.

:: ---------------------------------------------------------------
:: Step 6: Native Model Runtime (llama-server.exe)
:: ---------------------------------------------------------------
echo [6/8] Checking llama-server AI model runtime...
tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I /N "llama-server.exe">NUL
if "%ERRORLEVEL%"=="1" (
    where llama-server.exe >NUL 2>&1
    if not errorlevel 1 (
        echo       Launching llama-server...
        start "Autonomous Media - Model Runtime" /MIN llama-server.exe --model "%~dp0models\qwen3-8b-Q4_K_M.gguf" --port 8080 --gpu-layers 99
    ) else if exist "llama-server.exe" (
        echo       Launching local llama-server.exe...
        start "Autonomous Media - Model Runtime" /MIN llama-server.exe --model "%~dp0models\qwen3-8b-Q4_K_M.gguf" --port 8080 --gpu-layers 99
    ) else (
        echo       llama-server.exe not present locally (development mode). Skipping native LLM server.
    )
) else (
    echo       llama-server is already running.
)
echo.

:: ---------------------------------------------------------------
:: Step 7: Build & Start Frontend
:: ---------------------------------------------------------------
echo [7/8] Building and starting Frontend UI...
if exist "frontend" (
    cd frontend
    call npm run build
    start "Autonomous Media - Frontend" /MIN cmd /k "cd /d %~dp0frontend && npm run dev"
    cd ..
)
echo.

:: ---------------------------------------------------------------
:: Step 8: Start API Server + Scheduler
:: ---------------------------------------------------------------
echo [8/8] Starting API Server & Main Scheduler...
start "Autonomous Media - API" /MIN cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000"
start "Autonomous Media - Scheduler" /MIN cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe -m autonomous_media.main"
echo.

echo Waiting for system API health check...
set /a HEALTH_WAIT=0
:WAIT_HEALTH
timeout /t 3 /nobreak >NUL
curl -s -o NUL -w "%%{http_code}" http://localhost:8000/api/v1/system/health 2>NUL | findstr "200" >NUL
if errorlevel 1 (
    set /a HEALTH_WAIT+=1
    if !HEALTH_WAIT! GEQ 30 (
        echo       API is still initializing. You can open http://localhost:5173 once ready.
        goto DONE
    )
    goto WAIT_HEALTH
)

:DONE
echo.
echo ===================================================
echo   AUTONOMOUS MEDIA IS UP AND RUNNING!
echo.
echo   Frontend Dashboard:  http://localhost:5173
echo   API Backend:         http://localhost:8000/docs
echo   MinIO Console:       http://localhost:9001
echo ===================================================
echo.
pause
