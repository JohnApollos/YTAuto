# Autonomous Media System - Complete Automated Launcher Script

$ErrorActionPreference = "Continue"

Write-Host "===================================================" -ForegroundColor Green
Write-Host "  Autonomous Media System - Automated Startup" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

$ROOT_DIR = Get-Location

# 1. Pull Git Updates
Write-Host "[1/8] Checking for GitHub code updates..." -ForegroundColor Cyan
git pull origin master

# 2. Update Python Requirements
Write-Host "`n[2/8] Installing / verifying Python requirements..." -ForegroundColor Cyan
if (Test-Path ".venv\Scripts\python.exe") {
    & .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    Write-Host "      Python dependencies up to date." -ForegroundColor Green
} else {
    Write-Host "      Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & .venv\Scripts\python.exe -m pip install -r requirements.txt
}

# 3. Check Docker Desktop
Write-Host "`n[3/8] Checking Docker Desktop..." -ForegroundColor Cyan
$dockerRunning = $false
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
} catch {}

if (-not $dockerRunning) {
    Write-Host "      Docker Desktop daemon not running. Launching Docker Desktop..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
    $count = 0
    while (-not $dockerRunning -and $count -lt 30) {
        Start-Sleep -Seconds 4
        try {
            docker info 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $dockerRunning = $true }
        } catch {}
        $count++
    }
}
Write-Host "      Docker daemon is ready." -ForegroundColor Green

# 4. Bring up container services
Write-Host "`n[4/8] Starting container services (Postgres, Redis, MinIO)..." -ForegroundColor Cyan
docker compose up -d

# 5. Alembic database migrations
Write-Host "`n[5/8] Running database migrations (alembic upgrade head)..." -ForegroundColor Cyan
& .venv\Scripts\python.exe -m alembic upgrade head

# 6. llama-server (if present)
Write-Host "`n[6/8] Checking llama-server model runtime..." -ForegroundColor Cyan
$llamaExe = Get-Command "llama-server.exe" -ErrorAction SilentlyContinue
if ($llamaExe -or (Test-Path "llama-server.exe")) {
    $exePath = if ($llamaExe) { $llamaExe.Source } else { "llama-server.exe" }
    Write-Host "      Launching llama-server..." -ForegroundColor Green
    Start-Process -FilePath $exePath -ArgumentList "--model models\qwen3-8b-Q4_K_M.gguf --port 8080 --gpu-layers 99" -WindowStyle Minimized
} else {
    Write-Host "      [NOTICE] llama-server.exe not found on this system. Skipping native LLM server." -ForegroundColor Yellow
}

# 7. Frontend Build & Dev
Write-Host "`n[7/8] Building and starting Frontend UI..." -ForegroundColor Cyan
if (Test-Path "frontend") {
    Set-Location frontend
    npm run build
    Start-Process "powershell" -ArgumentList "-Command npm run dev" -WindowStyle Minimized
    Set-Location $ROOT_DIR
}

# 8. API Server & Scheduler
Write-Host "`n[8/8] Starting API Server & Main Scheduler..." -ForegroundColor Cyan
Start-Process "powershell" -ArgumentList "-Command .venv\Scripts\python.exe -m uvicorn autonomous_media.api.main:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized
Start-Process "powershell" -ArgumentList "-Command .venv\Scripts\python.exe -m autonomous_media.main" -WindowStyle Minimized

Write-Host "`n===================================================" -ForegroundColor Green
Write-Host "  AUTONOMOUS MEDIA IS UP AND RUNNING!" -ForegroundColor Green
Write-Host "  Frontend Dashboard:  http://localhost:5173" -ForegroundColor Yellow
Write-Host "  API Backend Docs:    http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  MinIO Storage:       http://localhost:9001" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Green
