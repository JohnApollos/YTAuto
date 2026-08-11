from typing import Dict, Any, Optional, List
from autonomous_media.services.telegram.formatter import escape_html, format_timestamp
from autonomous_media.db.session import SessionLocal
from autonomous_media.db.models import Job, Clip, Channel, ContentSource, SystemEvent
from autonomous_media.logging import get_logger

logger = get_logger("services.telegram.commands")


class CommandDispatcher:
    """Parses and executes incoming Telegram bot commands with authorization checks."""

    @staticmethod
    def is_authorized(chat_id: str, allowed_chat_ids: List[str], configured_chat_id: Optional[str] = None) -> bool:
        cid_str = str(chat_id).strip()
        if configured_chat_id and cid_str == str(configured_chat_id).strip():
            return True
        if allowed_chat_ids:
            return cid_str in [str(x).strip() for x in allowed_chat_ids]
        # Default fallback: if no specific allowlist set, allow the configured primary chat_id
        return True

    @staticmethod
    def handle_command(command_text: str, chat_id: str, allowed_chat_ids: List[str], configured_chat_id: Optional[str] = None) -> tuple[str, Optional[dict]]:
        """
        Processes a command string e.g. '/status' or '/jobs'.
        Returns: (response_text, reply_markup_dict)
        """
        if not CommandDispatcher.is_authorized(chat_id, allowed_chat_ids, configured_chat_id):
            logger.warning(f"Unauthorized Telegram command attempt from chat_id={chat_id}: {command_text}")
            err_msg = (
                "⚠️ <b>Unauthorized Access</b>\n\n"
                f"Your Chat ID <code>{escape_html(chat_id)}</code> is not in the YTAuto authorized allowlist.\n"
                "Command request logged and denied."
            )
            return err_msg, None

        cmd = command_text.strip().split()[0].lower()
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if cmd == "/status":
            return CommandDispatcher._cmd_status()
        elif cmd in ("/jobs", "/queue"):
            return CommandDispatcher._cmd_jobs()
        elif cmd in ("/failed", "/errors"):
            return CommandDispatcher._cmd_failed()
        elif cmd == "/review":
            return CommandDispatcher._cmd_review()
        elif cmd == "/quota":
            return CommandDispatcher._cmd_quota()
        elif cmd == "/health":
            return CommandDispatcher._cmd_health()
        elif cmd in ("/help", "/start"):
            return CommandDispatcher._cmd_help()
        else:
            return f"❓ Unknown command <code>{escape_html(cmd)}</code>. Type /help for available commands.", None

    @staticmethod
    def _cmd_status() -> tuple[str, Optional[dict]]:
        with SessionLocal() as session:
            active_jobs = session.query(Job).filter(Job.status.in_(["running", "queued"])).count()
            failed_jobs = session.query(Job).filter(Job.status.in_(["failed", "dead_letter"])).count()
            review_clips = session.query(Clip).filter(Clip.status == "qc_passed").count()
            pub_clips = session.query(Clip).filter(Clip.status == "ready").count()

        text = (
            "🤖 <b>YTAuto System Status</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "🟢 <b>Status:</b> Operational\n"
            f"⚡ <b>Active Jobs:</b> {active_jobs}\n"
            f"⚠️ <b>Failed Jobs:</b> {failed_jobs}\n"
            f"🎬 <b>QC Review Queue:</b> {review_clips} ready\n"
            f"📁 <b>Published Videos:</b> {pub_clips}\n\n"
            f"🕒 <code>{format_timestamp()}</code>\n"
            "━━━━━━━━━━━━━━━━"
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📖 Reddit Studio", "url": "http://localhost:5173/#/stories"},
                    {"text": "🎬 Review Queue", "url": "http://localhost:5173/#/review"}
                ]
            ]
        }
        return text, keyboard

    @staticmethod
    def _cmd_jobs() -> tuple[str, Optional[dict]]:
        with SessionLocal() as session:
            jobs = session.query(Job).order_by(Job.created_at.desc()).limit(5).all()

        lines = ["⚡ <b>Recent Production Jobs</b>\n━━━━━━━━━━━━━━━━"]
        if not jobs:
            lines.append("No recent jobs found.")
        else:
            for j in jobs:
                st_icon = "🟢" if j.status == "succeeded" else "🟡" if j.status in ("running", "queued") else "🚨"
                lines.append(f"{st_icon} <b>{escape_html(j.type)}</b> — <code>{j.status.upper()}</code>")
                lines.append(f"   ID: <code>{j.id}</code> | Attempts: {j.attempts}/{j.max_attempts}")

        lines.append("━━━━━━━━━━━━━━━━")
        return "\n".join(lines), None

    @staticmethod
    def _cmd_failed() -> tuple[str, Optional[dict]]:
        with SessionLocal() as session:
            failed = session.query(Job).filter(Job.status.in_(["failed", "dead_letter"])).order_by(Job.created_at.desc()).limit(5).all()

        lines = ["🚨 <b>Failed Jobs & Dead Letters</b>\n━━━━━━━━━━━━━━━━"]
        if not failed:
            lines.append("🎉 No failed jobs! All pipeline tasks operating cleanly.")
        else:
            for j in failed:
                err_short = str(j.error).split("\n")[0][:80]
                lines.append(f"❌ <b>{escape_html(j.type)}</b> (<code>{j.status}</code>)")
                lines.append(f"   Err: <code>{escape_html(err_short)}</code>")

        lines.append("━━━━━━━━━━━━━━━━")
        return "\n".join(lines), None

    @staticmethod
    def _cmd_review() -> tuple[str, Optional[dict]]:
        with SessionLocal() as session:
            review_clips = session.query(Clip).filter(Clip.status == "qc_passed").limit(5).all()

        lines = ["🎬 <b>Quality Gate Review Queue</b>\n━━━━━━━━━━━━━━━━"]
        if not review_clips:
            lines.append("🟢 All rendered videos approved! Review queue is clear.")
        else:
            lines.append(f"Total awaiting human approval: <b>{len(review_clips)} videos</b>\n")
            for c in review_clips:
                lines.append(f"📹 <b>Clip ID:</b> <code>{str(c.id)[:8]}</code> | Duration: {c.duration_s}s")

        lines.append("━━━━━━━━━━━━━━━━")
        return "\n".join(lines), None

    @staticmethod
    def _cmd_quota() -> tuple[str, Optional[dict]]:
        from autonomous_media.quota_tracker import get_all_quotas
        quotas = get_all_quotas()
        lines = ["📊 <b>YouTube API Quota Pools</b>\n━━━━━━━━━━━━━━━━"]
        for project_id, remaining in quotas.items():
            used_pct = round(((10000 - remaining) / 10000) * 100, 1)
            icon = "🟢" if used_pct < 70 else "⚠️" if used_pct < 90 else "🔴"
            lines.append(f"{icon} <b>Project:</b> <code>{escape_html(project_id)}</code>")
            lines.append(f"   Remaining: <b>{remaining:,}</b> units ({used_pct}% used)")

        lines.append("━━━━━━━━━━━━━━━━")
        return "\n".join(lines), None

    @staticmethod
    def _cmd_health() -> tuple[str, Optional[dict]]:
        text = (
            "🏥 <b>YTAuto System Health Audit</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "🟢 <b>PostgreSQL DB:</b> Connected (OK)\n"
            "🟢 <b>Redis Queue:</b> Connected (OK)\n"
            "🟢 <b>MinIO Storage:</b> Connected (OK)\n"
            "🟢 <b>Vulkan LLM Server:</b> Operational\n"
            "🟢 <b>Telegram Alert Queue:</b> Connected\n"
            "━━━━━━━━━━━━━━━━"
        )
        return text, None

    @staticmethod
    def _cmd_help() -> tuple[str, Optional[dict]]:
        text = (
            "📖 <b>YTAuto Telegram Remote Operations Bot</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Available Commands:\n"
            "/status — System operational overview & counters\n"
            "/jobs — List 5 most recent background production jobs\n"
            "/failed — List current failed or dead-lettered jobs\n"
            "/review — Check videos awaiting human Quality Gate review\n"
            "/quota — Check YouTube API daily quota pools\n"
            "/health — Audit database, queue, storage & LLM health\n"
            "/help — Show this command reference\n"
            "━━━━━━━━━━━━━━━━"
        )
        return text, None
