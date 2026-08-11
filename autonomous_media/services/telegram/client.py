import json
import time
import random
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
from autonomous_media.services.telegram.models import DeliveryResult
from autonomous_media.logging import get_logger

logger = get_logger("services.telegram.client")

BACKOFF_DELAYS = [0, 2, 5, 15, 30]


class TelegramClient:
    """Low-level Telegram HTTP API client with exponential backoff and timeout isolation."""

    def __init__(self, bot_token: Optional[str] = None, default_chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.default_chat_id)

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        max_retries: int = 4
    ) -> DeliveryResult:
        """Sends a text message to Telegram with exponential backoff retry handling."""
        token = self.bot_token
        cid = chat_id or self.default_chat_id

        if not token or not cid:
            return DeliveryResult(
                success=False,
                error="Telegram Bot Token or Chat ID not configured",
                retry_count=0
            )

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")
        last_error = None
        last_status = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                base_delay = BACKOFF_DELAYS[min(attempt, len(BACKOFF_DELAYS) - 1)]
                jitter = random.uniform(0.1, 0.5)
                time.sleep(base_delay + jitter)

            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    last_status = resp.status
                    if resp.status == 200:
                        res_body = json.loads(resp.read().decode("utf-8"))
                        msg_id = res_body.get("result", {}).get("message_id")
                        return DeliveryResult(
                            success=True,
                            status_code=200,
                            message_id=msg_id,
                            retry_count=attempt
                        )
            except urllib.error.HTTPError as e:
                last_status = e.code
                try:
                    err_json = json.loads(e.read().decode("utf-8"))
                    last_error = f"HTTP {e.code}: {err_json.get('description', e.reason)}"
                except Exception:
                    last_error = f"HTTP {e.code}: {e.reason}"
                
                # 400 Bad Request (formatting error) or 403 Forbidden shouldn't be endlessly retried
                if e.code in (400, 403):
                    logger.error(f"Telegram permanent client error ({last_error}) on attempt {attempt + 1}")
                    break
            except Exception as e:
                last_error = f"Network exception: {str(e)}"
                logger.warning(f"Telegram delivery attempt {attempt + 1} failed: {last_error}")

        return DeliveryResult(
            success=False,
            status_code=last_status,
            error=last_error or "Delivery failed after max retries",
            retry_count=max_retries
        )

    def get_updates(self, offset: Optional[int] = None, timeout: int = 0) -> List[Dict[str, Any]]:
        """Polls getUpdates endpoint for incoming user messages/commands."""
        token = self.bot_token
        if not token:
            return []

        url = f"https://api.telegram.org/bot{token}/getUpdates?timeout={timeout}"
        if offset is not None:
            url += f"&offset={offset}"

        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
                if resp.status == 200:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    return res_body.get("result", [])
        except Exception as e:
            logger.debug(f"getUpdates poll failed: {e}")
        return []
