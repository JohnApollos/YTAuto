import re
import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional, List
from autonomous_media.services.telegram.models import AlertSeverity, AlertEvent


def escape_html(text: Any) -> str:
    """Safely escapes HTML special characters (<, >, &, \") so user content doesn't break parse_mode='HTML'."""
    if text is None:
        return ""
    return html.escape(str(text))


def escape_markdown_v2(text: Any) -> str:
    """Safely escapes Telegram MarkdownV2 special characters."""
    if text is None:
        return ""
    s = str(text)
    pattern = r'([_\*\[\]\(\)~`>#\+\-=\|{}!\.])'
    return re.sub(pattern, r'\\\1', s)


def format_timestamp(dt: Optional[datetime] = None, tz_name: str = "Africa/Nairobi") -> str:
    """Formats datetime into human-readable local time e.g., '08:42 EAT'."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    try:
        local_tz = ZoneInfo(tz_name)
        local_dt = dt.astimezone(local_tz)
        tz_abbr = "EAT" if tz_name == "Africa/Nairobi" else local_dt.strftime("%Z")
        return f"{local_dt.strftime('%H:%M')} {tz_abbr}"
    except Exception:
        return dt.strftime("%H:%M UTC")


class TelegramFormatter:
    """Constructs Telegram HTML cards and inline keyboard markup for pipeline events."""

    @staticmethod
    def build_card(
        emoji: str,
        title: str,
        severity: AlertSeverity,
        fields: List[tuple[str, str]],
        description: Optional[str] = None,
        footer: Optional[str] = None,
        timestamp_str: Optional[str] = None
    ) -> str:
        ts = timestamp_str or format_timestamp()
        sev_label = severity.value
        
        lines = [f"{emoji} <b>{escape_html(title)}</b> — <code>{sev_label}</code>\n"]
        lines.append("━━━━━━━━━━━━━━━━")
        
        for k, v in fields:
            lines.append(f"<b>{escape_html(k)}:</b> {escape_html(v)}")
        
        if description:
            lines.append(f"\n<b>Details:</b>\n<code>{escape_html(description[:600])}</code>")
            
        if footer:
            lines.append(f"\n💡 <i>{escape_html(footer)}</i>")
            
        lines.append(f"\n🕒 <code>{ts}</code>")
        lines.append("━━━━━━━━━━━━━━━━")
        
        return "\n".join(lines)

    @staticmethod
    def format_event(event: AlertEvent, dashboard_url: str = "http://localhost:5173") -> tuple[str, Optional[dict]]:
        """
        Formats an AlertEvent into a Telegram message text and optional inline keyboard.
        Returns: (message_text, reply_markup_dict)
        """
        event_type = event.event_type
        payload = event.payload
        trace_id = event.trace_id
        
        # 1. Job Failed
        if event_type == "job.failed":
            job_name = payload.get("type", payload.get("job_type", "Pipeline Task")).replace("_", " ").title()
            stage = payload.get("stage", payload.get("type", "processing"))
            attempt = f"{payload.get('attempts', 1)} / {payload.get('max_attempts', 3)}"
            error_raw = payload.get("error", "Execution exception")
            error_short = error_raw.split("\n")[0][:120]
            next_act = "Automatic retry queued" if payload.get('will_retry', True) else "Manual inspection required"
            
            fields = [
                ("Job", job_name),
                ("Stage", stage),
                ("Attempt", attempt),
                ("Trace ID", trace_id[:12]),
                ("Next Action", next_act)
            ]
            if "channel_name" in payload:
                fields.insert(2, ("Channel", payload["channel_name"]))
            if "story_title" in payload:
                fields.insert(3, ("Story", payload["story_title"]))

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Retry Job", "callback_data": f"cmd:job_retry:{payload.get('job_id', trace_id)}"},
                        {"text": "🌐 Open Job Monitor", "url": f"{dashboard_url}/#/jobs"}
                    ]
                ]
            }
            
            text = TelegramFormatter.build_card(
                emoji="🚨",
                title="JOB FAILED",
                severity=event.severity,
                fields=fields,
                description=error_short,
                footer="YTAuto autonomous retry logic active."
            )
            return text, keyboard

        # 2. Job Dead-Lettered
        elif event_type == "job.dead_letter":
            job_name = payload.get("type", "Pipeline Task").replace("_", " ").title()
            attempts = f"{payload.get('attempts', 3)} / {payload.get('max_attempts', 3)}"
            error_short = str(payload.get("error", "Exhausted all retries")).split("\n")[0][:120]
            
            fields = [
                ("Job", job_name),
                ("Attempts", attempts),
                ("Trace ID", trace_id[:12]),
                ("Status", "DEAD-LETTERED")
            ]
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "⚡ Re-queue Job", "callback_data": f"cmd:job_retry:{payload.get('job_id', trace_id)}"},
                        {"text": "🌐 Open Dashboard", "url": f"{dashboard_url}/#/jobs"}
                    ]
                ]
            }
            text = TelegramFormatter.build_card(
                emoji="🔴",
                title="JOB DEAD-LETTERED",
                severity=AlertSeverity.ERROR,
                fields=fields,
                description=error_short,
                footer="System will NOT retry automatically. Operator review required."
            )
            return text, keyboard

        # 3. QC Ready / Video Review Required
        elif event_type in ("clip.ready_for_review", "qc.passed"):
            title = payload.get("title", payload.get("source_title", "Reddit Story Video"))
            duration = f"{payload.get('duration_s', 45)}s"
            channel = payload.get("channel_name", "Reddit Shorts")
            
            fields = [
                ("Title", title[:60]),
                ("Channel", channel),
                ("Duration", duration),
                ("Resolution", "1080 × 1920 (Vertical 9:16)"),
                ("Pipeline", "Script ✓ | TTS ✓ | Captions ✓ | QA ✓"),
                ("Status", "READY FOR HUMAN APPROVAL")
            ]
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🎬 Open Quality Gate", "url": f"{dashboard_url}/#/review"}
                    ]
                ]
            }
            text = TelegramFormatter.build_card(
                emoji="🎬",
                title="VIDEO READY FOR REVIEW",
                severity=AlertSeverity.SUCCESS,
                fields=fields,
                footer="Press 'A' in Quality Gate to approve or 'R' to reject."
            )
            return text, keyboard

        # 4. Video Approved / Published
        elif event_type in ("clip.approved", "publish.completed"):
            yt_id = payload.get("external_video_id", "")
            title = payload.get("title", "Video Clip")
            fields = [
                ("Title", title[:60]),
                ("Status", "PUBLISHED TO YOUTUBE")
            ]
            if yt_id:
                fields.append(("YouTube URL", f"https://youtu.be/{yt_id}"))
                
            keyboard = None
            if yt_id:
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "▶️ Watch on YouTube", "url": f"https://youtu.be/{yt_id}"}]
                    ]
                }
            text = TelegramFormatter.build_card(
                emoji="🚀",
                title="VIDEO PUBLISHED",
                severity=AlertSeverity.SUCCESS,
                fields=fields
            )
            return text, keyboard

        # 5. Incident Aggregation
        elif event_type == "incident.detected":
            count = payload.get("failure_count", 5)
            subsystem = payload.get("subsystem", "Pipeline Worker")
            first_fail = payload.get("first_failure_time", format_timestamp())
            root_err = payload.get("root_error", "Service unresponsive")
            
            fields = [
                ("Affected Subsystem", subsystem),
                ("Failures (10m)", str(count)),
                ("First Incident", first_fail),
                ("System Impact", "HIGH")
            ]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🌐 Open System Health", "url": f"{dashboard_url}/#/overview"}]
                ]
            }
            text = TelegramFormatter.build_card(
                emoji="🚨",
                title="PIPELINE INCIDENT DETECTED",
                severity=AlertSeverity.CRITICAL,
                fields=fields,
                description=root_err,
                footer="Multiple jobs failed due to common root cause. Check worker service."
            )
            return text, keyboard

        # 6. Recovery Alert
        elif event_type == "system.recovered":
            subsystem = payload.get("subsystem", "Piper TTS / Workers")
            duration = payload.get("incident_duration", "3m 45s")
            recovered_jobs = payload.get("recovered_jobs", 0)
            
            fields = [
                ("Subsystem", subsystem),
                ("Downtime Duration", duration),
                ("Auto-Resumed Jobs", str(recovered_jobs)),
                ("Status", "OPERATIONAL")
            ]
            text = TelegramFormatter.build_card(
                emoji="🟢",
                title="SYSTEM RECOVERED",
                severity=AlertSeverity.SUCCESS,
                fields=fields,
                footer="All automated workers have resumed normal processing."
            )
            return text, None

        # 7. Quota Alert
        elif event_type.startswith("quota."):
            rem = payload.get("remaining", 0)
            proj = payload.get("project_id", "default_project")
            pct = payload.get("used_percent", 80)
            is_crit = event_type == "quota.critical" or pct >= 90
            
            fields = [
                ("Project Pool", proj),
                ("Used Capacity", f"{pct}%"),
                ("Remaining Units", f"{rem:,}"),
                ("Reset Time", "Midnight Pacific (00:00 PST)")
            ]
            text = TelegramFormatter.build_card(
                emoji="🔴" if is_crit else "⚠️",
                title="YOUTUBE QUOTA CRITICAL" if is_crit else "YOUTUBE QUOTA WARNING",
                severity=AlertSeverity.CRITICAL if is_crit else AlertSeverity.WARNING,
                fields=fields,
                footer="Non-essential acquisitions deferred automatically."
            )
            return text, None

        # 8. Daily Summary
        elif event_type == "daily.summary":
            created = payload.get("videos_created", 0)
            approved = payload.get("videos_approved", 0)
            qc_ready = payload.get("videos_awaiting_qc", 0)
            failed = payload.get("jobs_failed", 0)
            quota_used = payload.get("quota_used", 0)
            
            fields = [
                ("Videos Rendered", str(created)),
                ("Approved & Published", str(approved)),
                ("Awaiting QC Review", str(qc_ready)),
                ("Jobs Failed", str(failed)),
                ("YouTube Quota Used", f"{quota_used:,} units")
            ]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "☀️ Open Command Center", "url": f"{dashboard_url}/#/overview"}]
                ]
            }
            text = TelegramFormatter.build_card(
                emoji="☀️",
                title="YTAUTO DAILY SUMMARY",
                severity=AlertSeverity.INFO,
                fields=fields,
                footer="YTAuto autonomous production engine daily operational status."
            )
            return text, keyboard

        # Fallback generic format
        fields = [
            ("Event", event_type),
            ("Trace ID", trace_id[:12])
        ]
        if "title" in payload:
            fields.append(("Subject", str(payload["title"])))
            
        text = TelegramFormatter.build_card(
            emoji="ℹ️",
            title=event_type.replace(".", " ").upper(),
            severity=event.severity,
            fields=fields
        )
        return text, None
