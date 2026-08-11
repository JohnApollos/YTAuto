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
    assert "mother in law" in normalized
    assert "sister in law" in normalized
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
    style = CaptionStyle(name="test_style", font="Arial Black")
    out_ass = tmp_path / "captions.ass"

    render_captions(timestamps, style, out_ass)

    assert out_ass.exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Style: Default,Arial Black,84,&H00FFFFFF,&H0000FFFF,&H00000000" in content
    # Assert 6-hex-digit yellow active word highlight tag is present (\c&H00FFFF&)
    assert r"{\c&H00FFFF&}HELLO{\c&HFFFFFF&}" in content
