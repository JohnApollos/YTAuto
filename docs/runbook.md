# Autonomous Media — Runbook

Literal incident response steps for production. Every section follows the same structure: **Symptom → Diagnosis → Steps → Verification**.

> For architectural context on any component referenced here, see `docs/architecture.md`.
> For configuration values, see `.env` and `autonomous_media/config.py`.

---

## 0. First: Identify What's Wrong

Before any runbook section, locate the broken job:

```powershell
# Jobs that have been stuck in 'running' for > 5 minutes
docker exec -it autonomous_media_postgres psql -U autonomous autonomous_media -c "
SELECT id, type, status, attempts, last_heartbeat_at, error
FROM jobs
WHERE status IN ('running', 'retrying', 'dead_letter')
ORDER BY created_at DESC LIMIT 20;"

# Tail the application log
docker compose logs -f api

# Check Scheduler output
# (If running as native process, check its console window)
```

The `trace_id` column on every job row lets you pull the full event history from `system_events`:

```sql
SELECT event_type, payload, created_at
FROM system_events
WHERE trace_id = '<trace_id_from_job_row>'
ORDER BY created_at;
```

---

## 1. Job Stuck in `running` (Heartbeat Timeout)

**Symptom:** A job row has `status = 'running'` but the process that was running it no longer exists (machine rebooted, OOM kill, power loss).

**Why it resolves itself:** The Scheduler's `_recover_stuck_jobs()` loop wakes every 5 seconds and requeues any `running` job whose `last_heartbeat_at` is older than 120 seconds (consuming one `attempts` count). If the Scheduler is running, you normally don't need to act.

**Manual override (if Scheduler is also down):**
```sql
UPDATE jobs
SET status = 'queued', attempts = attempts + 1, error = 'Manual recovery — heartbeat timeout'
WHERE id = '<job_id>'
  AND status = 'running';
```

**If the job has exhausted retries (`attempts >= max_attempts`):**
```sql
-- Review error, fix root cause, then:
UPDATE jobs SET status = 'queued', attempts = 0, error = NULL WHERE id = '<job_id>';
```

**Verification:** Confirm the job transitions to `running` again within one Scheduler poll cycle (≤ 5 seconds).

---

## 2. Dead-Lettered Jobs

**Symptom:** One or more jobs have `status = 'dead_letter'`. The `error` column explains why.

**Steps:**
1. Query dead-letter queue: `SELECT id, type, error FROM jobs WHERE status = 'dead_letter' ORDER BY finished_at DESC;`
2. Read the `error` column. Common causes and their fixes:

| Error message | Fix |
|---|---|
| `No model registered for stage '...'` | Register the correct worker/runtime; check Scheduler startup logs |
| `StageUnrecoverableError: Stage '...' failed and has no fallback` | Check llama-server is running (`curl http://localhost:8080/health`) |
| `SSRF guard: unexpected URL domain` | Source URL is malformed — inspect `source_videos.url` for the job's `source_video_id` |
| `Heartbeat timeout` | See §1 above |
| `RightsBlockedError` | Update the rights record via the Dashboard or `PATCH /api/v1/rights/{source_id}` |
| `QuotaExceededError` | YouTube quota exhausted — do not retry manually, the Scheduler defers automatically |

3. After fixing root cause, requeue via API: `POST /api/v1/jobs/<job_id>/retry`
   Or directly: `UPDATE jobs SET status = 'queued', attempts = 0 WHERE id = '<job_id>';`

**Verification:** Monitor job status transitions in the Dashboard (Pipeline Overview tab) or via `GET /api/v1/jobs/<job_id>`.

---

## 3. Disk / Storage Exhaustion

**Symptom:** Workers crash with `No space left on device` during download, transcription, or render. MinIO operations return `413 Request Entity Too Large` or similar storage errors.

**Diagnosis:**
```powershell
# Check host disk
Get-PSDrive C

# Check Docker volumes
docker system df -v

# Check MinIO usage
docker exec -it autonomous_media_minio du -sh /data
```

**Steps:**
1. **Rotate published clips:** Clips with `inventory_items.status = 'published'` and `published_at` older than 30 days can have their MinIO renders deleted; the YouTube copy is the permanent record.

   ```sql
   -- Find stale published clips
   SELECT c.storage_key, i.published_at
   FROM clips c JOIN inventory_items i ON i.clip_id = c.id
   WHERE i.status = 'published' AND i.published_at < NOW() - INTERVAL '30 days';
   ```

2. **Clear dead-letter raw downloads:** Source videos in `dead_letter` state whose `storage_key` is populated can be deleted from MinIO.

3. **Docker cleanup:**
   ```powershell
   docker system prune -f
   docker volume prune -f  # CAUTION: will delete non-named volumes
   ```

4. If still critical, pause the Acquisition worker by marking its scheduled jobs `cancelled` until space is recovered.

**Verification:** Re-run `Get-PSDrive C` to confirm space has been reclaimed. Restart any failed workers.

---

## 4. PostgreSQL Issues

### 4a. Database Fails to Start

**Symptom:** `docker compose up -d` leaves `autonomous_media_postgres` in `Exit 1` or `Restarting` state.

**Steps:**
```powershell
# Check container logs
docker logs autonomous_media_postgres --tail=50

# Most common cause: corrupt data volume. Inspect the log for:
# "invalid page in block X of relation..."
```

If corruption is confirmed:
1. Stop all containers: `docker compose down`
2. Restore from the most recent backup (see §4b).
3. Restart: `docker compose up -d`

### 4b. Restore from Backup

```powershell
# Stop application processes first
docker compose stop api
# (stop the Scheduler and any worker processes)

# Drop and recreate the database
docker exec -it autonomous_media_postgres dropdb -U autonomous autonomous_media
docker exec -it autonomous_media_postgres createdb -U autonomous autonomous_media

# Restore pg_dump backup
docker exec -i autonomous_media_postgres psql -U autonomous autonomous_media < path\to\backup.sql

# Restart
docker compose start api
alembic upgrade head  # apply any migrations that post-date the backup
```

### 4c. alembic upgrade head Fails

**Symptom:** `alembic upgrade head` throws an error about a missing type or relation.

**Common causes:**

| Error | Fix |
|---|---|
| `type "vector" does not exist` | `docker exec -it autonomous_media_postgres psql -U autonomous autonomous_media -c "CREATE EXTENSION IF NOT EXISTS vector;"` |
| `relation "X" already exists` | Migration was partially applied — check `alembic_version` table, drop the partial objects manually, re-run |
| `column "X" of relation "Y" already exists` | Same partial-apply scenario |

```powershell
# Check current migration state
alembic current

# Show applied migrations
alembic history --verbose
```

---

## 5. Model Server (llama-server) Crash-Loop

**Symptom:** Workers fail with `ConnectionRefused` to `localhost:8080`. `llama-server` console shows repeated segfaults or OOM errors.

**Diagnosis:**
1. Check VRAM pressure. `Task Manager → Performance → GPU` — if VRAM is at 100%, another application stole VRAM.
2. Check that `--gpu-layers` matches the model's layer count. Setting it too high forces more layers into VRAM than physically available.

**Steps:**
1. Close competing GPU applications (games, any browser using hardware acceleration against the RX 580).
2. Restart `llama-server` with slightly fewer GPU layers: replace `--gpu-layers 99` with `--gpu-layers 28` (reducing the number of layers on GPU; the remainder runs on CPU but at least it's stable).
3. If crash persists with fewer layers, the quantization may be too large for 8GB VRAM. Try a smaller quantization:
   - `Q4_K_M` → `Q3_K_M` (smaller VRAM, slightly lower quality)
4. Verify Vulkan is actually being used: `llama-server.exe --version` should print `vulkan`.

**Verification:** `curl http://localhost:8080/health` returns `{"status": "ok"}`.

---

## 6. YouTube OAuth Token Revoked

**Symptom:** `PublishingWorker` fails with HTTP 401 `invalid_grant` from the YouTube Data API.

**Why this happens:** Google refresh tokens are revoked if the OAuth consent screen is in "Testing" mode (tokens expire after 7 days). The permanent fix is completing the Google Cloud OAuth app verification process and switching the app status to "In production."

**Immediate steps:**
1. Open the Dashboard.
2. Navigate to Channels → select the affected channel → Settings.
3. Click **Re-Authenticate** to trigger the Google OAuth flow in the browser.
4. Complete the consent screen — a new refresh token is minted and stored.
5. The next `PublishingWorker` job will pick it up automatically.

**Permanent fix:** See the Deployment Guide, section "Google Cloud OAuth App Setup." Promote the app to "In production" status in the Google Cloud Console.

---

## 7. Dashboard Not Loading (404)

**Symptom:** `http://localhost:8000/` returns a 404 or blank page instead of the operator dashboard.

**Steps:**
1. Confirm the React build is present:
   ```powershell
   Test-Path c:\dev\YTAuto\dashboard\dist
   ```
2. If the `dist/` folder is missing or stale:
   ```powershell
   cd c:\dev\YTAuto\dashboard
   npm install
   npm run build
   ```
3. Restart the FastAPI server so it picks up the new `dist/`.

---

## 8. MinIO Bucket Missing

**Symptom:** `AcquisitionWorker` fails with `S3Error: NoSuchBucket` on the first run.

**Fix:**
```powershell
# One-time setup — run after first 'docker compose up -d'
docker run --rm --network host \
  minio/mc alias set local http://localhost:9000 minioadmin minioadmin
docker run --rm --network host \
  minio/mc mb local/autonomous-media-raw
docker run --rm --network host \
  minio/mc mb local/autonomous-media-transcripts
docker run --rm --network host \
  minio/mc mb local/autonomous-media-renders
docker run --rm --network host \
  minio/mc mb local/autonomous-media-branding
```

Or via the MinIO Console at `http://localhost:9001` (login: `minioadmin` / `minioadmin`).

---

## 9. YouTube Quota Exhausted

**Symptom:** `PublishingWorker` raises `QuotaExceededError`. Dashboard shows jobs in `deferred` state.

**Expected behaviour:** The Scheduler will NOT retry quota-exhausted jobs as normal retries. They are held in a `deferred` state until midnight Pacific (when quota resets). This is by design — quota exhaustion is not a failure, it is a scheduling constraint.

**Manual verification:**
```sql
SELECT id, type, status, error, created_at
FROM jobs
WHERE error LIKE '%QuotaExceeded%'
ORDER BY created_at DESC;
```

**If quota does not auto-reset:** Verify the Google Cloud Console → APIs & Services → YouTube Data API v3 → Quotas page. Daily quotas reset at midnight US-Pacific (UTC-8 or UTC-7 in DST).

---

## 10. Rights Gate Blocking Publishing

**Symptom:** `PublishingWorker` raises `RightsBlockedError`. The inventory item sits in `ready` status but never advances to `scheduled`.

**Context:** This is correct behaviour. The clip's `content_source` has a `rights_records` row with `status = 'unknown'` or `'denied'`. Publishing is blocked until the status is explicitly set to `owned`, `licensed`, or `permission_granted`.

**Steps:**
1. Review the source in the Dashboard → Sources tab or via `GET /api/v1/rights/{content_source_id}`.
2. If the source is licensed/cleared:
   ```
   PATCH /api/v1/rights/{content_source_id}
   Body: {"status": "licensed", "evidence_ref": "URL or agreement reference", "reviewed_by": "operator-name"}
   ```
3. This writes an audit row to `system_events` — every status change is permanently logged.
4. Re-enqueue the publish job: `POST /api/v1/jobs/{job_id}/retry`.

**Do not** set status to `fair_use_asserted` — it is not a valid status in the system. Fair use is a legal determination, not a software checkbox.
