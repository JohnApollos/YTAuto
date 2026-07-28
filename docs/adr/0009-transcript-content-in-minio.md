# ADR 0009 — Transcript Content in MinIO, Metadata Only in PostgreSQL

**Date:** 2026-07-28
**Status:** Accepted

## Context

During the spec v1.2 compliance audit, the `transcripts` table had two columns — `text` (plain text) and `segments` (a JSON blob) — storing the full transcript content inside PostgreSQL.

A `faster-whisper` word-level transcript for a 2-hour podcast with `word_timestamps=True` produces approximately 80,000–120,000 words as a JSON array of `{word, start, end}` objects. At ~40 bytes per word, that is 3–5 MB of JSON per episode stored as a Postgres JSON column.

### Problems with storing transcript content in Postgres

1. **Column size:** PostgreSQL JSON columns have no hard size limit, but rows this large degrade index performance, bloat WAL logs, and create excessive I/O during backup/restore.
2. **Query patterns:** The application never queries transcript content via SQL. It loads the full JSON into memory in the Python worker, processes it, and writes clip candidates. There is no `WHERE transcript LIKE '%...'` query pattern — full-text search of transcripts is not a V1 feature.
3. **Object storage is the right tool:** MinIO (S3-compatible) is already part of the infrastructure for video files. Transcripts are logically the same kind of large, write-once, read-few-times blob.

## Decision

The `transcripts` table stores **metadata only**: `engine`, `language`, `word_count`, `storage_key`, `source_video_id`, `created_at`. The full timestamped transcript JSON lives in MinIO at the path `transcripts/{transcript_id}.json`.

Workers that need transcript content retrieve it from MinIO using the `storage_key`. Workers that only need to know whether transcription is complete query the `transcripts` table.

## Consequences

**Positive:**
- Postgres stays lean: `transcripts` rows are < 200 bytes each.
- MinIO is the right medium: object storage with a content-addressed key is idempotent, survives retries without duplication, and can be deleted/replaced without a database migration.
- Adding a new transcript format (speaker-diarized, translated) is adding a new MinIO object at a predictable key, not a schema migration.
- Word count is stored in the metadata row for quick heuristics (e.g., skip transcription if already complete) without fetching the full JSON.

**Negative:**
- Accessing transcript content requires two calls: one to Postgres (get `storage_key`) and one to MinIO (fetch JSON). This is a minor latency trade-off with no practical impact on a background processing system.
- Local development without MinIO requires a running MinIO container (already provided by `docker-compose.yml`). Pure-Postgres-only development of transcript-reading code is not supported.
