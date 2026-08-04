@echo off
setlocal enabledelayedexpansion
title Autonomous Media - Starting
color 0A

echo ============================================
echo   Autonomous Media - Startup
echo ============================================
echo.

:: ---------------------------------------------------------------
:: Step 1: Docker Desktop
:: ---------------------------------------------------------------
echo [1/4] Checking Docker Desktop...
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>NUL | find /I /N "Docker Desktop.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo       Not running yet - starting it now. This can take a minute.
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

    set /a WAIT_COUNT=0
    :WAIT_DOCKER
    timeout /t 5 /nobreak >NUL
    docker info >NUL 2>&1
    if errorlevel 1 (
        set /a WAIT_COUNT+=1
        if !WAIT_COUNT! GEQ 24 (
            echo.
            echo       Docker Desktop is taking longer than expected ^(2+ minutes^).
            echo       Please check if it needs attention, then re-run this file.
            pause
            exit /b 1
        )
        goto WAIT_DOCKER
    )
) else (
    echo       Already running.
)
echo       Docker is ready.
echo.

:: ---------------------------------------------------------------
:: Step 2: Bring up the stateful services
:: ---------------------------------------------------------------
echo [2/5] Starting services (Postgres, Redis, MinIO)...
cd /d "%~dp0"
docker compose up -d
if errorlevel 1 (
    echo       Something went wrong bringing up services - see the message above.
    pause
    exit /b 1
)
echo       Services starting in the background.
echo.

:: ---------------------------------------------------------------
:: Step 3: Native model runtime
:: ---------------------------------------------------------------
echo [3/5] Checking the AI model runtime...
tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I /N "llama-server.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo       Starting it now...
    start "Autonomous Media - Model Runtime" /MIN llama-server.exe ^
        --model "%~dp0models\qwen3-8b-Q4_K_M.gguf" ^
        --port 8080 --gpu-layers 99
) else (
    echo       Already running.
)
echo.

:: ---------------------------------------------------------------
:: Step 4: Wait for health
:: ---------------------------------------------------------------
echo [4/5] Starting API server + Scheduler...
tasklist /FI "WINDOWTITLE eq Autonomous Media - Scheduler" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="1" (
    start "Autonomous Media - Scheduler" /MIN cmd /k "cd /d %~dp0 && .venv\Scripts\activate && python -m autonomous_media.main"
    start "Autonomous Media - API" /MIN cmd /k "cd /d %~dp0 && .venv\Scripts\activate && uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000"
) else (
    echo       Already running.
)
echo.
echo [5/5] Waiting for the system to be ready...
set /a HEALTH_WAIT=0
:WAIT_HEALTH
timeout /t 3 /nobreak >NUL
curl -s -o NUL -w "%%{http_code}" http://localhost:8000/api/v1/system/health 2>NUL | findstr "200" >NUL
if errorlevel 1 (
    set /a HEALTH_WAIT+=1
    if !HEALTH_WAIT! GEQ 40 (
        echo.
        echo       Still not responding after 2 minutes.
        echo       Something may need attention - please contact support
        echo       rather than continuing to wait.
        pause
        exit /b 1
    )
    goto WAIT_HEALTH
)

echo.
echo ============================================
echo   AUTONOMOUS MEDIA IS RUNNING
echo.
echo   Dashboard:  http://localhost:3000
echo.
echo   You can close this window now.
echo ============================================
echo.
pause
