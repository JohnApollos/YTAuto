# System Architecture

> **Source of truth:** `docs/technical-specification.md`. This document provides a high-level architectural overview, data flows, and subsystem component specs.

---

## Architectural Style: Modular Monolith

YTAuto is a **modular monolith** — a single Python backend with strict internal module boundaries — plus genuinely separate **stateful services** (PostgreSQL, Redis, MinIO), a **native host process** for the AI model server (`llama-server`), and a **React 19 Single Page Application** control center.

---

## High-Level System Architecture

```mermaid
graph TB
    subgraph Client & Remote Operations
        DASH["Operator Control Center (React 19 SPA)"]
        TG_BOT["Telegram Bot (Remote Command Dispatcher)"]
    end

    subgraph Edge & Gateway
        API["FastAPI Gateway /api/v1"]
        SCHED["Scheduler & Heartbeat Monitor"]
        RIGHTS["Rights Gate"]
        TG_SRV["Telegram Notifier Service"]
    end

    subgraph Workers["Worker Pool (Isolated Pipeline Workers)"]
        ACQ["Acquisition"]
        ASR["Transcription"]
        INT["Intelligence / Scoring"]
        VIS["Vision"]
        EDIT["Editing + Rendering"]
        PUB["Publishing"]
        AN["Analytics"]
        LRN["Learning"]
    end

    subgraph Data["Data Plane"]
        PG[("PostgreSQL + pgvector")]
        RD[("Redis — Queue + Cache")]
        OBJ[("MinIO — Object Storage")]
    end

    subgraph External
        YT["YouTube Data API v3"]
        RUN["llama-server (Vulkan, native host)"]
        TG_API["Telegram Bot API"]
    end

    DASH --> API
    TG_BOT --> API
    API --> PG
    API --> SCHED
    API --> TG_SRV
    SCHED --> RD
    RD --> ACQ & ASR & INT & VIS & EDIT & PUB & AN
    ACQ <--> OBJ & YT
    ASR & INT & VIS --> RUN
    EDIT <--> OBJ
    RIGHTS -.gates.-> PUB
    PUB <--> YT
    AN <--> YT
    TG_SRV --> TG_API
    ACQ & ASR & INT & VIS & EDIT & PUB & AN & LRN --> PG
```

---

## Telegram Alert & Remote Operations Subsystem

The Telegram subsystem functions as the system's **remote command center and observability engine**.

```mermaid
sequenceDiagram
    autonumber
    participant Pipeline as Pipeline Worker / API
    participant Bus as System Event Bus (emit_event)
    participant Notifier as Telegram Notifier Service
    participant Policy as Policy & Severity Engine
    participant Dedupe as Deduplication Filter
    participant Client as Telegram HTTP Client
    participant TG as Telegram Bot API

    Pipeline->>Bus: emit_event("job.failed", trace_id, payload)
    Bus->>Notifier: Enqueues AlertEvent
    Notifier->>Policy: Evaluates Severity (ERROR) & Category (JOBS)
    Policy-->>Notifier: Approved (bypasses Quiet Hours if CRITICAL)
    Notifier->>Dedupe: Checks 300s Fingerprint
    Dedupe-->>Notifier: Unique (Not Duplicate)
    Notifier->>Client: Formats HTML Card & dispatches async
    Client->>TG: POST /sendMessage (Exponential Backoff: 2s, 5s, 15s)
    TG-->>Client: 200 OK (message_id)
    Client->>Notifier: Logs Delivery Audit Row (telegram_delivery_logs)
```

### Key Subsystem Characteristics
1. **5-Level Severity Model**: `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`.
2. **Deduplication Filter**: 300-second fingerprinting window (`event_type:stage:entity_id:error_hash`).
3. **Incident Correlation**: Suppresses individual alerts when 5+ failures occur in 10 minutes, emitting a single `🚨 PIPELINE INCIDENT DETECTED` card, followed by `🟢 SYSTEM RECOVERED` when resolved.
4. **Non-Blocking Execution**: Notifications process asynchronously inside `telegram_notifier_queue`. Network timeouts or Telegram errors **never block video workers**.
5. **Bot Commands**: Remote command dispatcher handling `/status`, `/jobs`, `/failed`, `/review`, `/quota`, `/health`, and `/help` with Chat ID allowlist authorization.

---

## Data Design Summary

All **large content** (raw transcripts as timestamped JSON, rendered MP4s, audio extracts) lives in **MinIO**. PostgreSQL holds metadata and pointers.

### PostgreSQL Core Tables

| Table | Purpose |
|---|---|
| `channels` | One row per channel; all config as data, never as code |
| `content_sources` | Plugin-pattern source registry per channel |
| `source_videos` | Downloaded video metadata + MinIO `storage_key` |
| `source_posts` | Submitted Reddit text narrative stories |
| `transcripts` | ASR metadata — `engine`, `language`, `storage_key` → MinIO |
| `clip_candidates` | Scored candidate windows (`start_ms`/`end_ms`) |
| `clips` | Rendered artifact metadata + `channel_id`, `thumbnail_key` |
| `background_assets` | Footage library metadata (`storage_key`, `license_type`) |
| `inventory_items` | Production/publishing decoupling layer |
| `rights_records` | Per-source rights status — `owned`/`licensed`/`permission_granted`/`unknown`/`denied` |
| `analytics_snapshots` | Time series per `inventory_item_id` |
| `jobs` | State machine rows — `type`, `status`, `last_heartbeat_at` |
| `telegram_configs` | Persistent Telegram bot token, chat_id, category policies, quiet hours |
| `telegram_delivery_logs` | Audit trail of all sent, failed, or suppressed Telegram alerts |
| `system_events` | Append-only audit + event log with `trace_id` |
