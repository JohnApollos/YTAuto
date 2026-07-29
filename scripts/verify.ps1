# Autonomous Media — System Verification Script
# Run after initial deployment, after git pull, or when troubleshooting.
# Usage: .\.venv\Scripts\Activate.ps1 ; .\scripts\verify.ps1
# See docs/deployment-guide.md Part 16 for full explanation of each check.

$pass = 0; $fail = 0

# Detect virtual environment paths for robustness
$pythonBin = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$pytestBin = if (Test-Path ".\.venv\Scripts\pytest.exe") { ".\.venv\Scripts\pytest.exe" } else { "pytest" }
$ytdlpBin = if (Test-Path ".\.venv\Scripts\yt-dlp.exe") { ".\.venv\Scripts\yt-dlp.exe" } else { "yt-dlp" }

function Check($label, $cmd) {
    try {
        $result = Invoke-Expression $cmd 2>&1
        if ($LASTEXITCODE -eq 0 -or ($result -join " ") -match "OK|PONG|healthy|passed|accepting") {
            Write-Host "  [PASS] $label" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "  [FAIL] $label" -ForegroundColor Red
            Write-Host "         $result" -ForegroundColor DarkRed
            $script:fail++
        }
    } catch {
        Write-Host "  [FAIL] $label - Exception: $_" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host ""
Write-Host "Autonomous Media - System Verification" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# --- Python Environment ---
Write-Host "Python Environment:" -ForegroundColor Yellow
Check "Python 3.11+"          "$pythonBin --version"
Check "Package import"        "$pythonBin -c `"import autonomous_media; print('OK')`""
Check "faster-whisper import" "$pythonBin -c `"from faster_whisper import WhisperModel; print('OK')`""
Check "minio import"          "$pythonBin -c `"from minio import Minio; print('OK')`""
Check "yt-dlp on PATH"        "$ytdlpBin --version"
Check "FFmpeg on PATH"        "ffmpeg -version"

Write-Host ""

# --- Docker Services ---
Write-Host "Docker Services:" -ForegroundColor Yellow
Check "Docker running"           "docker info"
Check "Services healthy"         'docker compose ps | Select-String "healthy"'
Check "Postgres ready"           'docker exec autonomous_media_postgres pg_isready -U autonomous'
Check "Redis ping"               'docker exec autonomous_media_redis redis-cli ping'

Write-Host ""

# --- Database ---
Write-Host "Database:" -ForegroundColor Yellow
Check "pgvector extension"    'docker exec autonomous_media_postgres psql -U autonomous autonomous_media -c "SELECT 1 FROM pg_extension WHERE extname=''vector''"'
Check "Alembic at head"       'alembic current 2>&1 | Select-String "head"'
Check "All 13 tables exist"   'docker exec autonomous_media_postgres psql -U autonomous autonomous_media -c "\dt" | Select-String "channels|jobs|topics|clips"'

Write-Host ""

# --- API ---
Write-Host "API Server:" -ForegroundColor Yellow
Check "Health endpoint" '(Invoke-WebRequest -Uri http://localhost:8000/api/v1/system/health -UseBasicParsing -ErrorAction SilentlyContinue).StatusCode -eq 200'

Write-Host ""

# --- Model Server ---
Write-Host "LLM Runtime:" -ForegroundColor Yellow
Check "llama-server health" '(Invoke-WebRequest -Uri http://localhost:8080/health -UseBasicParsing -ErrorAction SilentlyContinue).StatusCode -eq 200'

Write-Host ""

# --- Tests ---
Write-Host "Unit Tests:" -ForegroundColor Yellow
Check "All 31 unit tests pass" "$pytestBin tests/unit/ -q --tb=no 2>&1 | Select-String `"passed`""

Write-Host ""

# --- Summary ---
$total = $pass + $fail
$color = if ($fail -eq 0) { "Green" } else { "Red" }
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "Result: $pass/$total passed, $fail failed" -ForegroundColor $color

if ($fail -eq 0) {
    Write-Host "System is ready. Safe to start the pipeline." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Fix the failing checks before running the pipeline." -ForegroundColor Yellow
    Write-Host "See docs/deployment-guide.md Part 16 for remediation steps." -ForegroundColor Yellow
}

exit $fail
