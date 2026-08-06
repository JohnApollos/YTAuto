import os
import json
import urllib.request
import urllib.parse
import threading
from autonomous_media.logging import get_logger

logger = get_logger("services.telegram")

class TelegramNotifier:
    """
    Sends rich, real-time event notifications to a Telegram Chat/Group/Channel.
    Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment variables.
    """

    def __init__(self):
        self._bot_token = None
        self._chat_id = None

    @property
    def bot_token(self) -> str:
        return self._bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    @property
    def chat_id(self) -> str:
        return self._chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def set_credentials(self, bot_token: str, chat_id: str):
        self._bot_token = bot_token.strip()
        self._chat_id = chat_id.strip()

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str) -> bool:
        token = self.bot_token
        cid = self.chat_id
        if not token or not cid:
            return False

        def _send():
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {
                    "chat_id": cid,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }
                data = json.dumps(payload).encode("utf-8")

                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("Telegram notification sent successfully")
                        return True
            except Exception as e:
                logger.warning(f"Failed to send Telegram notification: {e}")
                return False

        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
        return True

    def notify_event(self, event_type: str, trace_id: str, payload: dict):
        if not self.is_configured():
            return

        msg = ""
        if event_type == "video.discovered":
            title = payload.get("title", "New Video")
            msg = f"🎬 <b>New Video Discovered</b>\n\n📌 <b>Title:</b> {title}\n🆔 <code>{trace_id}</code>"

        elif event_type == "video.downloaded":
            title = payload.get("title", "Video")
            msg = f"📥 <b>Video Downloaded & Audio Extracted</b>\n\n📌 <b>Video:</b> {title}\n🆔 <code>{trace_id}</code>"

        elif event_type == "transcript.ready":
            words = payload.get("word_count", "N/A")
            msg = f"🎙️ <b>Whisper Speech-to-Text Completed</b>\n\n🗣️ <b>Words Transcribed:</b> {words}\n🆔 <code>{trace_id}</code>"

        elif event_type == "clip.candidates.scored":
            count = payload.get("candidate_count", payload.get("selected_count", "N/A"))
            msg = f"🔥 <b>Viral Moments Analyzed</b>\n\n📊 <b>Clips Selected:</b> {count}\n🆔 <code>{trace_id}</code>"

        elif event_type == "story.submitted":
            title = payload.get("title", "Reddit Story")
            msg = f"📖 <b>New Reddit Story Submitted</b>\n\n📌 <b>Title:</b> {title}\n🆔 <code>{trace_id}</code>"

        elif event_type == "narration.completed":
            msg = f"🗣️ <b>Voice Narration Synthesized</b>\n\n✅ Voice track generated successfully.\n🆔 <code>{trace_id}</code>"

        elif event_type == "edit.render.completed":
            filename = payload.get("output_file", "render.mp4")
            msg = f"🎥 <b>Video Rendering Completed!</b>\n\n📁 <b>File:</b> <code>{filename}</code>\n🆔 <code>{trace_id}</code>"

        elif event_type == "qc.passed":
            msg = f"✅ <b>Quality Gate Review PASSED</b>\n\nReady for export & publishing.\n🆔 <code>{trace_id}</code>"

        elif event_type in ("job.failed", "qc.failed"):
            error = payload.get("error", "Unknown error")
            msg = f"🚨 <b>Pipeline Job Failure</b>\n\n❌ <b>Error:</b> <code>{error}</code>\n🆔 <code>{trace_id}</code>"

        elif event_type == "publish.completed":
            yt_id = payload.get("external_video_id", "")
            msg = f"🚀 <b>YouTube Upload Completed!</b>\n\n🔗 <b>URL:</b> https://youtu.be/{yt_id}\n🆔 <code>{trace_id}</code>"

        if msg:
            self.send_message(msg)


telegram_notifier = TelegramNotifier()
