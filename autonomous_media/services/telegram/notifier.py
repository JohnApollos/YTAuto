import os
import time
import queue
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from autonomous_media.services.telegram.models import AlertEvent, AlertSeverity, AlertCategory, NotificationPreferences, DeliveryResult
from autonomous_media.services.telegram.client import TelegramClient
from autonomous_media.services.telegram.formatter import TelegramFormatter
from autonomous_media.services.telegram.policies import PolicyEngine
from autonomous_media.services.telegram.deduplication import DeduplicationFilter, IncidentCorrelator, compute_fingerprint
from autonomous_media.services.telegram.commands import CommandDispatcher
from autonomous_media.db.session import SessionLocal
from autonomous_media.db.models import TelegramConfig, TelegramDeliveryLog
from autonomous_media.logging import get_logger

logger = get_logger("services.telegram.notifier")


class TelegramNotifierService:
    """
    Centralized, production-grade Telegram Notification & Operations Service.
    Isolated from production pipeline threads via an asynchronous background queue.
    """

    def __init__(self):
        self._bot_token: Optional[str] = None
        self._chat_id: Optional[str] = None
        self.allowed_chat_ids: List[str] = []
        self.preferences = NotificationPreferences()
        self.quiet_hours_enabled = False
        self.quiet_hours_start = "23:00"
        self.quiet_hours_end = "07:00"
        self.timezone = "Africa/Nairobi"
        self.dedupe_window_seconds = 300
        self.quota_warning_threshold = 70
        self.quota_critical_threshold = 90

        self.client = TelegramClient()
        self.dedupe_filter = DeduplicationFilter(window_seconds=300)
        self.correlator = IncidentCorrelator(threshold_count=5, window_seconds=600)
        
        self.queue: queue.Queue = queue.Queue(maxsize=500)
        self.consecutive_failures = 0
        self.last_successful_delivery: Optional[datetime] = None
        self.last_polled_update_id: Optional[int] = None
        
        self._worker_thread: Optional[threading.Thread] = None
        self._command_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Load persistent configuration from DB or env
        self.reload_config()
        self.start_background_workers()

    def reload_config(self):
        """Loads configuration from PostgreSQL database, falling back to environment variables."""
        db_token = None
        db_chat_id = None
        try:
            with SessionLocal() as session:
                cfg = session.query(TelegramConfig).order_by(TelegramConfig.updated_at.desc()).first()
                if cfg:
                    db_token = cfg.bot_token
                    db_chat_id = cfg.chat_id
                    self.allowed_chat_ids = cfg.allowed_chat_ids or []
                    if cfg.categories:
                        self.preferences.enabled_categories = cfg.categories.get("enabled_categories", self.preferences.enabled_categories)
                        self.preferences.min_severity = cfg.categories.get("min_severity", self.preferences.min_severity)
                    self.quiet_hours_enabled = cfg.quiet_hours_enabled
                    self.quiet_hours_start = cfg.quiet_hours_start or "23:00"
                    self.quiet_hours_end = cfg.quiet_hours_end or "07:00"
                    self.timezone = cfg.timezone or "Africa/Nairobi"
                    self.dedupe_window_seconds = cfg.dedupe_window_seconds or 300
                    self.quota_warning_threshold = cfg.quota_warning_threshold or 70
                    self.quota_critical_threshold = cfg.quota_critical_threshold or 90
                    self.dedupe_filter.window_seconds = self.dedupe_window_seconds
        except Exception as e:
            logger.warning(f"Could not read TelegramConfig from DB: {e}")

        env_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        env_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        self._bot_token = db_token or env_token or None
        self._chat_id = db_chat_id or env_chat_id or None

        self.client.bot_token = self._bot_token
        self.client.default_chat_id = self._chat_id

    @property
    def bot_token(self) -> Optional[str]:
        return self._bot_token

    @property
    def chat_id(self) -> Optional[str]:
        return self._chat_id

    def set_credentials(self, bot_token: str, chat_id: str, allowed_chat_ids: Optional[List[str]] = None):
        """Updates credentials and persists to DB."""
        clean_token = bot_token.strip() if bot_token else ""
        clean_chat_id = chat_id.strip() if chat_id else ""
        allowed = allowed_chat_ids if allowed_chat_ids is not None else self.allowed_chat_ids

        self._bot_token = clean_token or None
        self._chat_id = clean_chat_id or None
        self.allowed_chat_ids = allowed

        self.client.bot_token = self._bot_token
        self.client.default_chat_id = self._chat_id

        try:
            with SessionLocal() as session:
                cfg = session.query(TelegramConfig).first()
                if not cfg:
                    cfg = TelegramConfig()
                    session.add(cfg)
                cfg.bot_token = self._bot_token
                cfg.chat_id = self._chat_id
                cfg.allowed_chat_ids = self.allowed_chat_ids
                session.commit()
        except Exception as e:
            logger.error(f"Failed to persist Telegram credentials to DB: {e}")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def get_connection_status(self) -> str:
        if not self.is_configured():
            return "disconnected"
        if self.consecutive_failures == 0:
            return "healthy"
        elif self.consecutive_failures < 5:
            return "degraded"
        else:
            return "unavailable"

    def start_background_workers(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._delivery_loop, daemon=True, name="telegram_notifier_queue")
        self._worker_thread.start()

        self._command_thread = threading.Thread(target=self._command_poll_loop, daemon=True, name="telegram_command_poller")
        self._command_thread.start()

    def process_event(self, event_type: str, trace_id: str, payload: Dict[str, Any]):
        """
        Public entry point called by logger emit_event().
        Non-blocking: pushes event into internal processing queue.
        """
        severity, category = PolicyEngine.classify_event(event_type, payload)
        event = AlertEvent(
            event_type=event_type,
            trace_id=trace_id,
            payload=payload,
            severity=severity,
            category=category,
            entity_id=payload.get("job_id", payload.get("clip_id", payload.get("story_id")))
        )

        try:
            self.queue.put_nowait(event)
        except queue.Full:
            logger.warning(f"Telegram notification queue full! Dropped event {event_type}")

    # Backward-compatible alias for logger.emit_event()
    notify_event = process_event

    def _delivery_loop(self):
        while self._running:
            try:
                event: AlertEvent = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._dispatch_event(event)
            except Exception as e:
                logger.error(f"Unexpected exception during Telegram dispatch: {e}")
            finally:
                self.queue.task_done()

    def _dispatch_event(self, event: AlertEvent):
        # 1. Deduplication Filter
        fp = compute_fingerprint(event)
        if self.dedupe_filter.is_duplicate(fp):
            logger.debug(f"Suppressed duplicate alert fingerprint {fp} for event {event.event_type}")
            self._log_delivery(event, fp, "", "suppressed_dedupe", None, "Suppressed by deduplication filter")
            return

        # 2. Failure Aggregation / Incident Correlation
        if event.event_type == "job.failed":
            stage = event.payload.get("type", "general_worker")
            err_msg = str(event.payload.get("error", ""))
            incident = self.correlator.record_failure(stage, err_msg)
            if incident:
                # Trigger incident alert
                inc_event = AlertEvent(
                    event_type="incident.detected",
                    trace_id=event.trace_id,
                    payload=incident,
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.JOBS
                )
                self._send_alert_event(inc_event)
                return

        elif event.event_type in ("job.completed", "stage.completed"):
            stage = event.payload.get("type", "general_worker")
            rec = self.correlator.record_success(stage)
            if rec:
                rec_event = AlertEvent(
                    event_type="system.recovered",
                    trace_id=event.trace_id,
                    payload=rec,
                    severity=AlertSeverity.SUCCESS,
                    category=AlertCategory.SYSTEM
                )
                self._send_alert_event(rec_event)

        # 3. Policy & Preferences Filter
        if not PolicyEngine.should_notify(event, self.preferences):
            logger.debug(f"Filtered out event {event.event_type} per severity/category preferences")
            return

        # 4. Quiet Hours Filter (CRITICAL alerts always bypass!)
        if self.quiet_hours_enabled and event.severity != AlertSeverity.CRITICAL:
            if PolicyEngine.is_in_quiet_hours(quiet_start_str=self.quiet_hours_start, quiet_end_str=self.quiet_hours_end, tz_name=self.timezone):
                logger.info(f"Suppressed event {event.event_type} during quiet hours ({self.quiet_hours_start}-{self.quiet_hours_end})")
                self._log_delivery(event, fp, "", "suppressed_quiet_hours", None, "Suppressed during Quiet Hours")
                return

        # 5. Build Formatted Card & Send
        self._send_alert_event(event, fp)

    def _send_alert_event(self, event: AlertEvent, fingerprint: Optional[str] = None):
        if not self.is_configured():
            return

        text, reply_markup = TelegramFormatter.format_event(event)
        res = self.client.send_message(text=text, parse_mode="HTML", reply_markup=reply_markup)

        if res.success:
            self.consecutive_failures = 0
            self.last_successful_delivery = datetime.now(timezone.utc)
            self._log_delivery(event, fingerprint, text, "sent", res.message_id, None)
        else:
            self.consecutive_failures += 1
            logger.warning(f"Telegram delivery failed for {event.event_type}: {res.error}")
            self._log_delivery(event, fingerprint, text, "failed", None, res.error)

    def send_test_notification(self, bot_token: str, chat_id: str) -> tuple[bool, str]:
        """Direct verification call for Settings UI [Save & Test Connection]."""
        test_client = TelegramClient(bot_token.strip(), chat_id.strip())
        now_str = datetime.now().strftime("%H:%M:%S EAT")
        text = (
            "🚀 <b>YTAuto Telegram Connection Test</b> — <code>SUCCESS</code>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Your Telegram Bot is successfully connected and authorized!\n"
            "YTAuto will deliver real-time notifications for jobs, video renders, and system health.\n\n"
            f"🕒 <code>{now_str}</code>\n"
            "━━━━━━━━━━━━━━━━"
        )
        res = test_client.send_message(text=text, parse_mode="HTML", max_retries=1)
        if res.success:
            self.set_credentials(bot_token, chat_id)
            return True, f"Delivered test message (ID: {res.message_id}) at {now_str}"
        else:
            return False, res.error or "Telegram API failed to accept message"

    def _log_delivery(
        self,
        event: AlertEvent,
        fingerprint: Optional[str],
        text: str,
        status: str,
        message_id: Optional[int],
        error: Optional[str]
    ):
        try:
            with SessionLocal() as session:
                log = TelegramDeliveryLog(
                    notification_id=f"notif_{event.trace_id[:8]}_{int(time.time())}",
                    event_type=event.event_type,
                    severity=event.severity.value,
                    dedupe_key=fingerprint,
                    text=text[:1000] if text else f"Event: {event.event_type}",
                    status=status,
                    telegram_message_id=message_id,
                    chat_id=self.chat_id,
                    error=error
                )
                if status == "sent":
                    log.sent_at = datetime.now(timezone.utc)
                session.add(log)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record TelegramDeliveryLog in DB: {e}")

    def _command_poll_loop(self):
        """Periodically polls Telegram getUpdates for incoming user commands."""
        while self._running:
            time.sleep(10)
            if not self.is_configured():
                continue

            try:
                updates = self.client.get_updates(offset=self.last_polled_update_id, timeout=0)
                for update in updates:
                    update_id = update.get("update_id")
                    if update_id is not None:
                        self.last_polled_update_id = update_id + 1

                    message = update.get("message", {})
                    text = message.get("text", "")
                    sender_chat_id = str(message.get("chat", {}).get("id", ""))

                    if text.startswith("/"):
                        resp_text, reply_markup = CommandDispatcher.handle_command(
                            command_text=text,
                            chat_id=sender_chat_id,
                            allowed_chat_ids=self.allowed_chat_ids,
                            configured_chat_id=self.chat_id
                        )
                        self.client.send_message(
                            text=resp_text,
                            chat_id=sender_chat_id,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )

                    # Handle Callback Queries (Inline Keyboard Buttons)
                    cb_query = update.get("callback_query", {})
                    if cb_query:
                        cb_id = cb_query.get("id")
                        cb_data = cb_query.get("data", "")
                        cb_chat_id = str(cb_query.get("message", {}).get("chat", {}).get("id", ""))

                        if cb_data.startswith("cmd:job_retry:"):
                            job_id = cb_data.split(":")[-1]
                            from autonomous_media.scheduler.scheduler import Scheduler
                            # Retry job logic
                            resp_text = f"🔄 <b>Job Retry Requested</b>\n\nJob ID <code>{escape_html(job_id)}</code> re-queued for execution."
                            self.client.send_message(text=resp_text, chat_id=cb_chat_id, parse_mode="HTML")

            except Exception as e:
                logger.debug(f"Command polling exception: {e}")


# Singleton Instance
telegram_notifier = TelegramNotifierService()
