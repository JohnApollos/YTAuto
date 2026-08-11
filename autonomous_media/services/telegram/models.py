from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


class AlertSeverity(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertCategory(str, Enum):
    SYSTEM = "SYSTEM"
    JOBS = "JOBS"
    CONTENT = "CONTENT"
    QUOTA = "QUOTA"
    SECURITY = "SECURITY"


from datetime import datetime, timezone

@dataclass
class AlertEvent:
    event_type: str
    trace_id: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: AlertSeverity = AlertSeverity.INFO
    category: AlertCategory = AlertCategory.SYSTEM
    dedupe_key: Optional[str] = None
    entity_id: Optional[str] = None


@dataclass
class NotificationPreferences:
    enabled_categories: Dict[str, bool] = field(default_factory=lambda: {
        "SYSTEM": True,
        "JOBS": True,
        "CONTENT": True,
        "QUOTA": True,
        "SECURITY": True
    })
    min_severity: Dict[str, str] = field(default_factory=lambda: {
        "SYSTEM": "WARNING",
        "JOBS": "INFO",
        "CONTENT": "INFO",
        "QUOTA": "WARNING",
        "SECURITY": "INFO"
    })


@dataclass
class DeliveryResult:
    success: bool
    status_code: Optional[int] = None
    message_id: Optional[int] = None
    error: Optional[str] = None
    retry_count: int = 0
