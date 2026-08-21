import pytest
from pathlib import Path
from autonomous_media.workers.narration import (
    is_contaminated_script,
    validate_and_clean_narration_script,
    normalize_spoken_script,
)
from autonomous_media.workers.captions import (
    render_captions,
    CaptionStyle,
    WordTimestamp,
)

def test_is_contaminated_script_detects_json_and_scoring_metadata():
    json_payload = '{"hook_strength": 80, "emotional_intensity": 75, "curiosity_gap": 70, "humor": 50}'
    markdown_json = "```json\n{\n  \"humor\": 80\n}\n```"
    stub_result = '{"rationale": "Stub result"}'
    llm_chat = "SYSTEM: You are an AI assistant. Here is the prepared script:"
    clean_prose = "I work at a tech company and my boss asked me to stay late on Friday."

    assert is_contaminated_script(json_payload) is True
    assert is_contaminated_script(markdown_json) is True
    assert is_contaminated_script(stub_result) is True
    assert is_contaminated_script(llm_chat) is True
    assert is_contaminated_script(clean_prose) is False


def test_validate_and_clean_narration_script_fallback():
    contaminated = '{"hook_strength": 80, "emotional_intensity": 75}'
    fallback_title = "AITA for refusing to give up my seat?"
    fallback_body = "I bought a first class ticket for a long flight."

    result = validate_and_clean_narration_script(contaminated, fallback_title, fallback_body)
    assert "hook_strength" not in result
    assert "emotional_intensity" not in result
    assert result == "AITA for refusing to give up my seat?.\n\nI bought a first class ticket for a long flight."


def test_normalize_spoken_script_reddit_slang_and_relationships():
    raw_reddit = "AITA (21M) for telling my MIL and SIL that $50k is WIBTA for my bf and me? OP said idk tbh."
    normalized = normalize_spoken_script(raw_reddit)

    assert "Am I the jerk" in normalized
    assert "21 male" in normalized
    assert "mother-in-law" in normalized
    assert "sister-in-law" in normalized
    assert "50 thousand dollars" in normalized
    assert "Would I be the jerk" in normalized
    assert "boyfriend" in normalized
    assert "original poster" in normalized
    assert "I don't know" in normalized
    assert "to be honest" in normalized


def test_render_captions_produces_valid_ass_tags(tmp_path: Path):
    timestamps = [
        WordTimestamp(text="Hello", start_s=0.0, end_s=0.5),
        WordTimestamp(text="world", start_s=0.5, end_s=1.0),
    ]
    style = CaptionStyle(name="test_style", font="Arial Black", font_size=98)
    out_ass = tmp_path / "captions.ass"

    render_captions(timestamps, style, out_ass)

    assert out_ass.exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Style: Default,Arial Black,98,&H00FFFFFF,&H0000FFFF,&H00000000" in content
    # Assert yellow active word highlight and scale bounce tag is present (\c&H00FFFF&\fscx118\fscy118)
    assert r"{\c&H00FFFF&\fscx118\fscy118}HELLO{\c&HFFFFFF&\fscx100\fscy100}" in content


def test_unknown_voice_profile_raises_proper_exception():
    from autonomous_media.workers.narration import _resolve_voice_model
    from autonomous_media.exceptions import UnknownVoiceProfileError

    with pytest.raises(UnknownVoiceProfileError):
        _resolve_voice_model("non_existent_voice_profile_123")


def test_telegram_cmd_quota_executes_cleanly():
    from autonomous_media.services.telegram.commands import CommandDispatcher

    text, markup = CommandDispatcher.handle_command("/quota", "12345", ["12345"])
    assert "YouTube API Quota Pools" in text
    assert "Remaining:" in text


def test_promo_filter_llm_classify_batch_parses_json():
    from autonomous_media.workers.promo_filter import TranscriptWindow, _llm_classify_batch
    from unittest.mock import MagicMock

    windows = [
        TranscriptWindow(text="Hello and welcome to this video.", start_ms=0, end_ms=5000),
        TranscriptWindow(text="Make sure to check out our sponsor Squarespace.", start_ms=5000, end_ms=10000),
    ]

    mock_mgr = MagicMock()
    mock_res = MagicMock()
    mock_res.text = '{"promotional_ids": [1]}'
    mock_mgr.run_stage.return_value = mock_res

    flagged = _llm_classify_batch(windows, mock_mgr)
    assert len(flagged) == 1
    assert "Squarespace" in flagged[0].text


def test_hardware_telemetry_sampler_returns_valid_metrics():
    from autonomous_media.profiling import HardwareTelemetrySampler

    snapshot = HardwareTelemetrySampler.get_system_snapshot()
    assert "cpu" in snapshot
    assert "ram" in snapshot
    assert "gpu" in snapshot
    assert "storage" in snapshot
    assert "coexistence" in snapshot

    assert snapshot["cpu"]["cores_logical"] >= 1
    assert snapshot["ram"]["total_gb"] > 0
    assert snapshot["ram"]["percent"] >= 0
    assert snapshot["gpu"]["total_vram_gb"] > 0
    assert snapshot["coexistence"]["status"] in ("optimal", "contended", "critical")


def test_stage_profiler_records_stage_execution():
    from autonomous_media.profiling import ProfileStageContext, stage_profiler
    import time

    with ProfileStageContext("test_vision_profiling", job_id="job_abc", trace_id="trace_xyz") as ctx:
        time.sleep(0.01)
        ctx.set_tokens(generated=20, prompt=50)

    recent = stage_profiler.get_recent_profiles(limit=5)
    matched = [p for p in recent if p["stage"] == "test_vision_profiling"]
    assert len(matched) >= 1
    entry = matched[0]
    assert entry["duration_s"] > 0
    assert entry["job_id"] == "job_abc"
    assert entry["trace_id"] == "trace_xyz"
    assert entry["tokens_generated"] == 20


def test_purge_aged_assets_preserves_backgrounds():
    from autonomous_media.storage import purge_aged_assets
    from autonomous_media.db.session import SessionLocal
    from autonomous_media.db.models import BackgroundAsset

    with SessionLocal() as session:
        # Run purge with days_old=365 to verify execution correctness without deleting recent data
        res = purge_aged_assets(session, days_old=365)
        assert "deleted_objects" in res
        assert "freed_mb" in res
        assert "cutoff_date" in res

        # Ensure background assets are not purged
        bg_assets = session.query(BackgroundAsset).all()
        assert len(bg_assets) >= 1


def test_coexistence_governor_decision_endpoint():
    from autonomous_media.api.system import get_coexistence_decision
    from autonomous_media.db.session import SessionLocal

    with SessionLocal() as session:
        decision = get_coexistence_decision(db=session)
        assert "allowed" in decision
        assert decision["mode"] in ("protected", "light", "full")
        assert "reason" in decision
        assert "max_concurrent_agents" in decision
        assert "allow_browser_automation" in decision


def test_caption_presets_all_caps_and_middle_positioning():
    from autonomous_media.workers.captions import CaptionStyle, CAPTION_PRESETS
    
    style = CaptionStyle.from_channel_config("reddit_shorts")
    assert style.uppercase is True
    # Middle of the screen margin should be placed in the upper-middle visual focal zone (>= 800px)
    assert style.position_margin_v >= 800
    assert style.font_size >= 90
    assert "Arial Black" in style.font
    assert style.outline_width >= 6


def test_normalize_spoken_script_smart_punctuation_and_intonation():
    from autonomous_media.workers.narration import normalize_spoken_script

    raw_text = "AITA for leaving my MIL at the airport because she told me to shut up and didnt apologize"
    cleaned = normalize_spoken_script(raw_text)
    
    # Check question mark inflection added
    assert cleaned.endswith("?")
    assert "Am I the jerk" in cleaned
    assert "mother-in-law" in cleaned
    assert "didn't" in cleaned
    assert "because" in cleaned


def test_format_reddit_video_metadata():
    from autonomous_media.workers.publishing import format_reddit_video_metadata
    from autonomous_media.db.models import SourcePost

    post = SourcePost(
        title="[AITA] My wife spent our savings on a luxury handbag without telling me",
        body_text="I was shocked when I opened my bank account and saw a charge for 5000 dollars.",
        subreddit="AmItheAsshole",
        author="confused_husband"
    )

    title, desc = format_reddit_video_metadata(post, clip_dur=45.0)
    assert len(title) <= 100
    assert "#Shorts" in title
    assert "Am I The Jerk" in title or "savings" in title
    assert "#redditstories" in desc
    assert "r/AmItheAsshole" in desc
    assert "u/confused_husband" in desc

    # Test with a massive 300-character Reddit title
    long_post = SourcePost(
        title="AITA for refusing to give my entire life savings of fifty thousand dollars to my estranged stepbrother who never spoke to me for twenty years until he found out I bought a new house in the suburbs and now my whole family is blowing up my phone telling me that I am a selfish monster who ruined Christmas?",
        body_text="Here is the long story...",
        subreddit="AmItheAsshole",
        author="op_poster"
    )
    long_title, long_desc = format_reddit_video_metadata(long_post, clip_dur=55.0)
    assert len(long_title) <= 100
    assert long_title.endswith("#Shorts")






