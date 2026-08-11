import pytest
import time
from datetime import datetime, timezone
from autonomous_media.services.telegram.models import AlertSeverity, AlertCategory, AlertEvent, NotificationPreferences
from autonomous_media.services.telegram.formatter import escape_html, escape_markdown_v2, TelegramFormatter
from autonomous_media.services.telegram.policies import PolicyEngine
from autonomous_media.services.telegram.deduplication import DeduplicationFilter, IncidentCorrelator, compute_fingerprint
from autonomous_media.services.telegram.commands import CommandDispatcher
from autonomous_media.services.telegram.notifier import telegram_notifier


def test_escape_html_special_characters():
    raw_input = "<script>alert('xss')</script> & AITA for r/AskReddit titles with <tags>"
    escaped = escape_html(raw_input)
    assert "&lt;script&gt;" in escaped
    assert "&amp;" in escaped
    assert "<" not in escaped
    assert ">" not in escaped


def test_escape_markdown_v2_characters():
    raw_input = "Hello *world* [link](http://test.com) _test_! #"
    escaped = escape_markdown_v2(raw_input)
    assert r"\*" in escaped
    assert r"\[" in escaped
    assert r"\]" in escaped
    assert r"\!" in escaped


def test_policy_engine_classification():
    sev, cat = PolicyEngine.classify_event("job.failed", {"error": "Pipeline failure"})
    assert sev == AlertSeverity.ERROR
    assert cat == AlertCategory.JOBS

    sev, cat = PolicyEngine.classify_event("clip.ready_for_review", {})
    assert sev == AlertSeverity.SUCCESS
    assert cat == AlertCategory.CONTENT

    sev, cat = PolicyEngine.classify_event("system.health_degraded", {})
    assert sev == AlertSeverity.CRITICAL
    assert cat == AlertCategory.SYSTEM


def test_policy_engine_preference_filtering():
    prefs = NotificationPreferences()
    prefs.enabled_categories["JOBS"] = True
    prefs.min_severity["JOBS"] = "ERROR"

    event_info = AlertEvent("job.failed", "trace_1", {}, severity=AlertSeverity.INFO, category=AlertCategory.JOBS)
    assert PolicyEngine.should_notify(event_info, prefs) is False

    event_error = AlertEvent("job.failed", "trace_2", {}, severity=AlertSeverity.ERROR, category=AlertCategory.JOBS)
    assert PolicyEngine.should_notify(event_error, prefs) is True


def test_deduplication_filter():
    dedupe = DeduplicationFilter(window_seconds=10)
    event1 = AlertEvent("job.failed", "trace_1", {"error": "Piper TTS timeout"}, severity=AlertSeverity.ERROR)
    fp = compute_fingerprint(event1)

    now = time.time()
    assert dedupe.is_duplicate(fp, now_ts=now) is False
    assert dedupe.is_duplicate(fp, now_ts=now + 2) is True
    assert dedupe.is_duplicate(fp, now_ts=now + 12) is False


def test_incident_correlator_aggregation_and_recovery():
    correlator = IncidentCorrelator(threshold_count=3, window_seconds=60)
    now = time.time()

    # Record 2 failures -> No incident yet
    assert correlator.record_failure("piper_tts", "Timeout 1", now_ts=now) is None
    assert correlator.record_failure("piper_tts", "Timeout 2", now_ts=now + 1) is None

    # Record 3rd failure -> Triggers incident
    inc = correlator.record_failure("piper_tts", "Timeout 3", now_ts=now + 2)
    assert inc is not None
    assert inc["subsystem"] == "Piper Tts"
    assert inc["failure_count"] == 3

    # Record success -> Emits recovery
    rec = correlator.record_success("piper_tts", now_ts=now + 10)
    assert rec is not None
    assert rec["subsystem"] == "Piper Tts"
    assert rec["recovered_jobs"] == 3


from unittest.mock import patch, MagicMock

@patch("autonomous_media.services.telegram.commands.SessionLocal")
def test_command_dispatcher_authorization(mock_session_local):
    mock_session = MagicMock()
    mock_session.query().filter().count.return_value = 0
    mock_session_local.return_value.__enter__.return_value = mock_session

    allowed_ids = ["12345", "67890"]
    assert CommandDispatcher.is_authorized("12345", allowed_ids) is True
    assert CommandDispatcher.is_authorized("99999", allowed_ids) is False

    # Command execution
    resp, keyboard = CommandDispatcher.handle_command("/status", "12345", allowed_ids)
    assert "YTAuto System Status" in resp
    assert keyboard is not None

    resp, _ = CommandDispatcher.handle_command("/status", "99999", allowed_ids)
    assert "Unauthorized Access" in resp


def test_telegram_formatter_job_failed():
    event = AlertEvent(
        event_type="job.failed",
        trace_id="trace_xyz12345",
        payload={
            "type": "script_preparation",
            "stage": "text_to_speech",
            "error": "Piper TTS binary timeout after 30s",
            "attempts": 2,
            "max_attempts": 3,
            "will_retry": True
        },
        severity=AlertSeverity.ERROR,
        category=AlertCategory.JOBS
    )
    text, keyboard = TelegramFormatter.format_event(event)
    assert "🚨 <b>JOB FAILED</b>" in text
    assert "Script Preparation" in text
    assert "Piper TTS binary timeout" in text
    assert keyboard is not None
