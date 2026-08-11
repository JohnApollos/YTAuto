# Production-Grade Telegram Alert & Remote Operations Subsystem

---

## 1. Overview & Operational Principle

The **YTAuto Telegram Alert Subsystem** transforms Telegram from a simple webhook target into a reliable **remote command center and alerting channel**.

> **Core Operating Principle**: *YTAuto operates fully autonomously. Telegram tells the operator what happened, what matters, whether intervention is required, and what exact action should be taken.*

```text
Pipeline / Worker Event
          ↓
  System Event Bus (emit_event)
          ↓
  Telegram Notification Service (non-blocking)
          ↓
  Severity & Policy Engine (Category Toggles, Thresholds)
          ↓
  Quiet Hours Filter (CRITICAL alerts always bypass)
          ↓
  Deduplication & Incident Correlator (300s window & failure aggregation)
          ↓
  Async Telegram Delivery Queue
          ↓
  Telegram HTTP Client (Exponential Backoff: 2s, 5s, 15s, 30s)
          ↓
  PostgreSQL Audit Trail (telegram_delivery_logs)
```

---

## 2. Alert Severity Model

Notifications are categorized into **5 severity levels**:

| Severity | Color / Emoji | Semantics & Operator Trigger |
| :--- | :--- | :--- |
| **INFO** | ℹ️ / ☀️ | Routine operational milestones (e.g. story submitted, daily summary). |
| **SUCCESS** | ✅ / 🚀 | Important successful events (e.g. clip ready for review, video published). |
| **WARNING** | ⚠️ / 🟡 | Approaching capacity thresholds (e.g. YouTube quota >70%, storage >75%). |
| **ERROR** | 🚨 / ❌ | A background job failed or reached dead-letter state requiring attention. |
| **CRITICAL** | 🔴 / 🚨 | Subsystem failure (e.g. 5+ job failures in 10m, LLM server offline, DB down). |

---

## 3. High-Value Alert Specifications

### 3.1 Job Failure Card (`job.failed`)
```text
🚨 JOB FAILED — ERROR
━━━━━━━━━━━━━━━━
Job:         Piper TTS Narration
Stage:       text_to_speech
Attempt:     2 / 3
Trace ID:    trace_a8f921bc
Next Action: Automatic retry queued in 30s

Details:
Piper TTS binary timeout after 30 seconds

💡 YTAuto autonomous retry logic active.
🕒 08:42 EAT
━━━━━━━━━━━━━━━━
[🔄 Retry Job]   [🌐 Open Job Monitor]
```

### 3.2 Video Ready for Review Card (`clip.ready_for_review`)
```text
🎬 VIDEO READY FOR REVIEW — SUCCESS
━━━━━━━━━━━━━━━━
Title:       AITA for refusing to give up my seat?
Channel:     Reddit Shorts
Duration:    45s
Resolution:  1080 × 1920 (Vertical 9:16)
Pipeline:    Script ✓ | TTS ✓ | Captions ✓ | QA ✓
Status:      READY FOR HUMAN APPROVAL

💡 Press 'A' in Quality Gate to approve or 'R' to reject.
🕒 08:45 EAT
━━━━━━━━━━━━━━━━
[🎬 Open Quality Gate Review]
```

### 3.3 Pipeline Incident Detection (`incident.detected`)
```text
🚨 PIPELINE INCIDENT DETECTED — CRITICAL
━━━━━━━━━━━━━━━━
Affected Subsystem: Text To Speech
Failures (10m):     5
First Incident:     08:32 EAT
System Impact:      HIGH

Details:
Piper TTS process unresponsive / binary timeout

💡 Multiple jobs failed due to common root cause. Check worker service.
🕒 08:42 EAT
━━━━━━━━━━━━━━━━
[🌐 Open System Health]
```

---

## 4. Bot Commands & Remote Operations

Authorized operators can query real-time production stats directly in Telegram:

| Command | Action / Response |
| :--- | :--- |
| `/status` | Returns system health, active jobs, ready QC review clips, and published counts. |
| `/jobs` | Lists the 5 most recent background production jobs with status badges. |
| `/failed` | Lists active failed or dead-lettered jobs with error summaries. |
| `/review` | Displays clips currently waiting in the Quality Gate review queue. |
| `/quota` | Checks YouTube API daily quota pools across all Google Cloud projects. |
| `/health` | Audits PostgreSQL DB, Redis Queue, MinIO Storage, and Vulkan LLM health. |
| `/help` | Returns full command syntax reference. |

### Security & Chat Authorization
Commands check the sender's Telegram `chat_id` against the configured `allowed_chat_ids` list. Unauthorized command attempts return a warning card and emit a `security.unauthorized_command` event to the audit trail.

---

## 5. Deduplication, Failure Aggregation & Quiet Hours

### 5.1 Deduplication Window
- Identical alerts sharing the fingerprint signature (`event_type + stage + entity_id + error_hash`) within `300 seconds` are automatically suppressed.

### 5.2 Failure Aggregation
- If 5+ jobs fail within a rolling 10-minute window, individual failure alerts are suppressed and correlated into a single `🚨 INCIDENT DETECTED` card.
- When the pipeline recovers, a `🟢 SYSTEM RECOVERED` card is delivered.

### 5.3 Quiet Hours (e.g. 23:00 → 07:00 EAT)
- Lower severity alerts (`INFO`, `SUCCESS`, `WARNING`, `ERROR`) are suppressed during Quiet Hours and accumulated for the Morning Summary (`☀️ MORNING SUMMARY`).
- `CRITICAL` alerts **always bypass Quiet Hours** immediately.

---

## 6. HTML & MarkdownV2 Character Escaping

User-submitted Reddit titles, story text, and exception tracebacks are safely escaped using `escape_html()` before rendering Telegram cards:
```python
def escape_html(text: Any) -> str:
    if text is None: return ""
    return html.escape(str(text))
```
This guarantees that titles containing `<`, `>`, or `&` symbols **never break Telegram HTML parsing**.

---

## 7. Delivery Audit Log & Non-Blocking Isolation

All notification dispatches are recorded in the PostgreSQL `telegram_delivery_logs` table:

```sql
SELECT notification_id, event_type, severity, status, error, created_at 
FROM telegram_delivery_logs 
ORDER BY created_at DESC LIMIT 20;
```

**Non-Blocking Guarantee**: All Telegram API calls execute inside an isolated async background queue (`telegram_notifier_queue` thread). Network timeouts or Telegram API failures **NEVER block worker threads or fail video processing jobs**.

---

## 8. Verification & Testing

Unit tests for the Telegram subsystem are located in `tests/unit/test_telegram_subsystem.py`:
```powershell
.venv\Scripts\python -m pytest tests/unit/test_telegram_subsystem.py -v
```
Tests verify:
- `escape_html` & `escape_markdown_v2` special character escaping.
- `PolicyEngine` severity classification & category toggles.
- `DeduplicationFilter` fingerprint suppression.
- `IncidentCorrelator` failure aggregation and recovery notification.
- `CommandDispatcher` command handling & chat ID authorization.
