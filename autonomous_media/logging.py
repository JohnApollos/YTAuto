import logging
import json
import traceback
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id # type: ignore
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_data)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def emit_event(event_type: str, trace_id: str, payload: dict):
    from autonomous_media.db.session import SessionLocal
    from autonomous_media.db.models import SystemEvent
    
    logger = get_logger("event_bus")
    logger.info(f"Event {event_type} emitted", extra={"trace_id": trace_id, "payload": payload})
    
    try:
        with SessionLocal() as session:
            evt = SystemEvent(
                event_type=event_type,
                trace_id=trace_id,
                payload=payload
            )
            session.add(evt)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to write SystemEvent to DB: {e}", extra={"trace_id": trace_id})

    # Dispatch to Telegram Bot (non-blocking, only if configured)
    try:
        from autonomous_media.services.telegram.notifier import telegram_notifier
        if telegram_notifier.is_configured():
            telegram_notifier.notify_event(event_type, trace_id, payload)
    except Exception:
        pass
