# Autonomous Media Runbook

This document outlines the literal steps for incident response in production.

## 1. Disk Full (Storage Exhaustion)
**Symptom:** Workers crash with `No space left on device` during download, render, or MinIO operations.
**Steps:**
1. SSH / log in to the host machine.
2. Run `df -h` to confirm exhaustion on the primary volume.
3. Use the CLI tool to clear dead letter raw assets: `python -m scripts.clear_dead_letter_assets`
4. Empty the MinIO `.trash` directory or rotate old generated inventory that has already been published.
5. If running via Docker, prune unused images: `docker system prune -f`.
6. Restart the worker processes.

## 2. PostgreSQL Corruption / Restore
**Symptom:** Database fails to start, or application throws fatal SQLAlchemy operational errors about table corruption.
**Steps:**
1. Stop the application and scheduler entirely to prevent write conflicts: `docker compose stop api scheduler workers`.
2. Locate the most recent automated pg_dump backup in the secure backup volume.
3. Drop the corrupted database: `docker exec -it autonomous_media_postgres dropdb -U autonomous autonomous_media`
4. Recreate it: `docker exec -it autonomous_media_postgres createdb -U autonomous autonomous_media`
5. Restore the dump: `docker exec -i autonomous_media_postgres psql -U autonomous autonomous_media < backup.sql`
6. Restart the application stack.

## 3. Model Crash-Loop (Vulkan / VRAM Exhaustion)
**Symptom:** `llama.cpp` or `whisper.cpp` processes repeatedly exit with segfaults or out-of-memory Vulkan allocation errors.
**Steps:**
1. Identify the offending model in the logs (`grep "ModelManager" logs.txt`).
2. Verify if another process (e.g., a background desktop application) is eating VRAM on the RX 580.
3. Check `ModelRuntimeManager` logs for lock acquisition deadlocks.
- Ensure only one model is loaded at a time.

## 3. Dashboard UI Fails to Load (404 Not Found)
**Symptom:** Visiting `http://localhost:8000/` returns a 404 error instead of the React Dashboard.
**Action:**
- The frontend assets are not built. Ensure you have run `npm run build` inside the `frontend/` directory so the `dist/` folder is populated for FastAPI to serve.

## 4. OAuth Token Revoked
**Symptom:** Publishing worker fails with HTTP 401 Unauthorized or `invalid_grant` from the YouTube API.
**Steps:**
1. Log into the Dashboard.
2. Navigate to the Channels settings.
3. Identify the Channel with the revoked status.
4. Click "Re-Authenticate" to trigger the Google OAuth flow and mint a new refresh token.
5. The system will automatically pick up the new token on the next publishing attempt.
