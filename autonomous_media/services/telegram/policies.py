from datetime import datetime, time as dt_time, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from autonomous_media.services.telegram.models import AlertSeverity, AlertCategory, AlertEvent, NotificationPreferences

SEVERITY_HIERARCHY = {
    AlertSeverity.INFO: 1,
    AlertSeverity.SUCCESS: 2,
    AlertSeverity.WARNING: 3,
    AlertSeverity.ERROR: 4,
    AlertSeverity.CRITICAL: 5
}

EVENT_CATEGORY_MAP = {
    # System
    "system.health_degraded": (AlertSeverity.CRITICAL, AlertCategory.SYSTEM),
    "system.health_recovered": (AlertSeverity.SUCCESS, AlertCategory.SYSTEM),
    "system.recovered": (AlertSeverity.SUCCESS, AlertCategory.SYSTEM),
    "model.unavailable": (AlertSeverity.CRITICAL, AlertCategory.SYSTEM),
    "storage.warning": (AlertSeverity.WARNING, AlertCategory.SYSTEM),
    "storage.critical": (AlertSeverity.CRITICAL, AlertCategory.SYSTEM),

    # Jobs
    "job.failed": (AlertSeverity.ERROR, AlertCategory.JOBS),
    "job.dead_letter": (AlertSeverity.ERROR, AlertCategory.JOBS),
    "job.stuck": (AlertSeverity.WARNING, AlertCategory.JOBS),
    "incident.detected": (AlertSeverity.CRITICAL, AlertCategory.JOBS),

    # Content
    "story.submitted": (AlertSeverity.INFO, AlertCategory.CONTENT),
    "narration.completed": (AlertSeverity.INFO, AlertCategory.CONTENT),
    "clip.ready_for_review": (AlertSeverity.SUCCESS, AlertCategory.CONTENT),
    "qc.passed": (AlertSeverity.SUCCESS, AlertCategory.CONTENT),
    "clip.approved": (AlertSeverity.SUCCESS, AlertCategory.CONTENT),
    "clip.rejected": (AlertSeverity.WARNING, AlertCategory.CONTENT),
    "publish.completed": (AlertSeverity.SUCCESS, AlertCategory.CONTENT),

    # Quota
    "quota.warning": (AlertSeverity.WARNING, AlertCategory.QUOTA),
    "quota.critical": (AlertSeverity.CRITICAL, AlertCategory.QUOTA),

    # Security
    "security.unauthorized_command": (AlertSeverity.WARNING, AlertCategory.SECURITY),
    "security.config_changed": (AlertSeverity.INFO, AlertCategory.SECURITY),
}


class PolicyEngine:
    """Evaluates whether an AlertEvent passes notification preferences, severities, and quiet hours."""

    @staticmethod
    def classify_event(event_type: str, payload: Dict[str, Any]) -> tuple[AlertSeverity, AlertCategory]:
        if event_type in EVENT_CATEGORY_MAP:
            return EVENT_CATEGORY_MAP[event_type]
        
        if "fail" in event_type or "error" in event_type:
            return AlertSeverity.ERROR, AlertCategory.JOBS
        if "completed" in event_type or "passed" in event_type or "success" in event_type:
            return AlertSeverity.SUCCESS, AlertCategory.CONTENT
        
        return AlertSeverity.INFO, AlertCategory.SYSTEM

    @staticmethod
    def should_notify(event: AlertEvent, preferences: NotificationPreferences) -> bool:
        category_key = event.category.value
        
        # Check category toggle
        if not preferences.enabled_categories.get(category_key, True):
            return False

        # Check minimum severity threshold
        min_sev_str = preferences.min_severity.get(category_key, "INFO")
        min_sev = AlertSeverity(min_sev_str) if min_sev_str in AlertSeverity.__members__ else AlertSeverity.INFO
        
        event_score = SEVERITY_HIERARCHY.get(event.severity, 1)
        min_score = SEVERITY_HIERARCHY.get(min_sev, 1)
        
        return event_score >= min_score

    @staticmethod
    def is_in_quiet_hours(
        now_utc: Optional[datetime] = None,
        quiet_start_str: str = "23:00",
        quiet_end_str: str = "07:00",
        tz_name: str = "Africa/Nairobi"
    ) -> bool:
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        elif now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        try:
            local_tz = ZoneInfo(tz_name)
            local_dt = now_utc.astimezone(local_tz)
            current_time = local_dt.time()

            sh, sm = map(int, quiet_start_str.split(":"))
            eh, em = map(int, quiet_end_str.split(":"))
            start_time = dt_time(sh, sm)
            end_time = dt_time(eh, em)

            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                # Overnight quiet hours e.g. 23:00 -> 07:00
                return current_time >= start_time or current_time <= end_time
        except Exception:
            return False
