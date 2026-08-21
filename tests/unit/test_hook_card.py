"""
tests/unit/test_hook_card.py

Unit tests for the visual Reddit hook card PNG generator.
"""

import pytest
import os
from pathlib import Path
from PIL import Image
from autonomous_media.workers.hook_card import (
    generate_reddit_hook_card, _format_count, _wrap_text, _get_font
)


def test_format_count():
    assert _format_count(500) == "500"
    assert _format_count(1500) == "1.5k"
    assert _format_count(14200) == "14.2k"
    assert _format_count(1_200_000) == "1.2M"


def test_wrap_text():
    font = _get_font(24)
    scratch = Image.new("RGBA", (500, 500))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(scratch)

    text = "This is a long story title that needs to be wrapped neatly across multiple lines for readability."
    lines = _wrap_text(text, font, max_width=200, draw=draw)
    assert len(lines) > 1
    assert all(len(line) > 0 for line in lines)


def test_generate_reddit_hook_card_dimensions(tmp_path):
    out_file = tmp_path / "test_card.png"
    result_path = generate_reddit_hook_card(
        title="AITA for refusing to give my sister my wedding dress after she destroyed hers?",
        subreddit="AmItheAsshole",
        author="wedding_bride_2026",
        upvotes=15200,
        comments_count=980,
        out_path=out_file,
        width=960,
    )

    assert Path(result_path).exists()
    img = Image.open(result_path)
    assert img.format == "PNG"
    assert img.size[0] == 960
    assert img.size[1] > 150  # Dynamic height with header, title, footer
    assert img.mode == "RGBA"
