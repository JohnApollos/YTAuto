import hashlib
import time
from typing import Dict, Optional, Tuple
from autonomous_media.services.telegram.models import AlertEvent, AlertSeverity


def compute_fingerprint(event: AlertEvent) -> str:
    """Generates a stable deduplication fingerprint key for an AlertEvent."""
    if event.dedupe_key:
        return event.dedupe_key

    err_sig = ""
    if "error" in event.payload:
        err_raw = str(event.payload["error"]).split("\n")[0][:60]
        err_sig = hashlib.md5(err_raw.encode("utf-8")).hexdigest()[:8]

    parts = [
        event.event_type,
        event.payload.get("type", event.payload.get("stage", "general")),
        event.entity_id or event.trace_id[:8],
        err_sig
    ]
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class DeduplicationFilter:
    """Suppresses duplicate alert fingerprints within a configurable time window."""

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._history: Dict[str, float] = {}

    def is_duplicate(self, fingerprint: str, now_ts: Optional[float] = None) -> bool:
        if now_ts is None:
            now_ts = time.time()

        # Clean expired entries
        expired = [k for k, v in self._history.items() if now_ts - v > self.window_seconds]
        for k in expired:
            del self._history[k]

        if fingerprint in self._history:
            last_sent = self._history[fingerprint]
            if now_ts - last_sent < self.window_seconds:
                return True

        self._history[fingerprint] = now_ts
        return False


class IncidentCorrelator:
    """Aggregates multiple rapid job failures into correlated pipeline incidents."""

    def __init__(self, threshold_count: int = 5, window_seconds: int = 600):
        self.threshold_count = threshold_count
        self.window_seconds = window_seconds
        self._failures: Dict[str, list[float]] = {}
        self._active_incidents: Dict[str, dict] = {}

    def record_failure(self, stage: str, error_msg: str, now_ts: Optional[float] = None) -> Optional[dict]:
        if now_ts is None:
            now_ts = time.time()

        if stage not in self._failures:
            self._failures[stage] = []

        self._failures[stage].append(now_ts)
        # Keep failures within rolling window
        self._failures[stage] = [t for t in self._failures[stage] if now_ts - t <= self.window_seconds]

        count = len(self._failures[stage])
        if count >= self.threshold_count and stage not in self._active_incidents:
            incident = {
                "subsystem": stage.replace("_", " ").title(),
                "failure_count": count,
                "first_failure_time": time.strftime("%H:%M EAT", time.localtime(self._failures[stage][0])),
                "root_error": error_msg.split("\n")[0][:120],
                "started_at": now_ts
            }
            self._active_incidents[stage] = incident
            return incident

        return None

    def record_success(self, stage: str, now_ts: Optional[float] = None) -> Optional[dict]:
        if now_ts is None:
            now_ts = time.time()

        if stage in self._active_incidents:
            inc = self._active_incidents.pop(stage)
            duration_s = int(now_ts - inc["started_at"])
            mins = duration_s // 60
            secs = duration_s % 60
            dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            
            # Clear failure window
            self._failures[stage] = []
            
            return {
                "subsystem": inc["subsystem"],
                "incident_duration": dur_str,
                "recovered_jobs": inc["failure_count"]
            }

        return None
