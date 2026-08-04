"""
autonomous_media/workers/captions.py

Fixes the production defect reported on the first configured channel:
captions were rendered with FFmpeg's default `drawtext` styling (plain
font, no cap on words shown at once, sometimes a full sentence at a
time). This module replaces that path entirely.

Design, matching spec section 12.6:
  - Whisper's word-level timestamps are re-chunked into small groups
    (2-5 words, configurable per channel) rather than shown as
    whatever span Whisper happened to segment.
  - Captions are emitted as a proper .ass (Advanced SubStation Alpha)
    subtitle file, which natively supports font/size/color/outline,
    and burned in via FFmpeg's `ass` filter -- never `drawtext`.

Usage:
    style = CaptionStyle.from_channel_config(channel.caption_style)
    ass_path = render_captions(transcript.word_timestamps, style, out_dir)
    # Burn-in is now handled by rendering.py during the FFmpeg encode pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Style presets. `caption_style` on a channel (spec section 25.6) selects one
# of these by name; add new presets here rather than hand-editing per-render.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaptionStyle:
    name: str
    font: str = "Montserrat ExtraBold"
    font_size: int = 84
    primary_color: str = "&H00FFFFFF"   # ASS format: &HAABBGGRR, white
    outline_color: str = "&H00000000"   # black
    highlight_color: str = "&H0000FFFF" # yellow, used for the emphasized word if enabled
    outline_width: int = 4
    max_words_per_screen: int = 4
    uppercase: bool = True
    position_margin_v: int = 220        # vertical margin from the bottom, in pixels at 1080x1920

    @staticmethod
    def from_channel_config(preset_name: str) -> "CaptionStyle":
        return CAPTION_PRESETS.get(preset_name, CAPTION_PRESETS["hormozi_bold"])


CAPTION_PRESETS: dict[str, CaptionStyle] = {
    "hormozi_bold": CaptionStyle(
        name="hormozi_bold",
        font="Montserrat ExtraBold",
        font_size=84,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        highlight_color="&H0000FFFF",
        max_words_per_screen=4,
    ),
    "anton_punchy": CaptionStyle(
        name="anton_punchy",
        font="Anton",
        font_size=90,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        highlight_color="&H0000FFFF",
        max_words_per_screen=3,
    ),
    "poppins_soft": CaptionStyle(
        name="poppins_soft",
        font="Poppins Bold",
        font_size=76,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        highlight_color="&H0000FFFF",
        max_words_per_screen=5,
    ),
    # fallback for channels using legacy 'default' preset name
    "default": CaptionStyle(
        name="default",
        font="Montserrat ExtraBold",
        font_size=84,
        primary_color="&H00FFFFFF",
        outline_color="&H00000000",
        highlight_color="&H0000FFFF",
        max_words_per_screen=4,
    ),
}


# ---------------------------------------------------------------------------
# Word timestamp chunking
# ---------------------------------------------------------------------------

@dataclass
class WordTimestamp:
    text: str
    start_s: float
    end_s: float


SENTENCE_ENDERS = (".", "!", "?")


def chunk_words_for_captions(
    word_timestamps: list[WordTimestamp],
    max_words: int = 4,
) -> list[list[WordTimestamp]]:
    """Groups word-level timestamps into small caption chunks.

    Breaks early on sentence-ending punctuation even if under max_words,
    since a caption that stops mid-thought reads worse than one that's
    a word or two short of the cap.
    """
    chunks: list[list[WordTimestamp]] = []
    current: list[WordTimestamp] = []

    for w in word_timestamps:
        current.append(w)
        ends_sentence = w.text.strip().endswith(SENTENCE_ENDERS)
        if len(current) >= max_words or ends_sentence:
            chunks.append(current)
            current = []

    if current:
        chunks.append(current)

    return chunks


def words_from_raw_transcript(
    words: list[dict], start_ms: int, end_ms: int
) -> list[WordTimestamp]:
    """Converts the raw transcript word dicts (with start_ms/end_ms keys)
    stored in MinIO into WordTimestamp objects, filtered to the clip window.
    This is the bridge between the existing transcript format and the new
    caption renderer.
    """
    result = []
    for w in words:
        w_start = w.get("start_ms", 0)
        w_end = w.get("end_ms", 0)
        if w_start >= start_ms and w_end <= end_ms:
            # Convert absolute ms to seconds relative to clip start
            result.append(WordTimestamp(
                text=w.get("word", ""),
                start_s=(w_start - start_ms) / 1000.0,
                end_s=(w_end - start_ms) / 1000.0,
            ))
    return result


# ---------------------------------------------------------------------------
# .ass generation
# ---------------------------------------------------------------------------

_ASS_HEADER_TEMPLATE = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{primary_color},{highlight_color},{outline_color},&H00000000,1,0,0,0,100,100,0,0,1,{outline_width},0,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt_timestamp(seconds: float) -> str:
    """ASS timestamp format: H:MM:SS.CC (centiseconds)."""
    total_cs = round(seconds * 100)
    h, rem = divmod(total_cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def render_captions(
    word_timestamps: list[WordTimestamp],
    style: CaptionStyle,
    output_path: Path,
) -> Path:
    """Writes a complete .ass subtitle file. Returns the path written."""
    chunks = chunk_words_for_captions(word_timestamps, max_words=style.max_words_per_screen)

    header = _ASS_HEADER_TEMPLATE.format(
        font=style.font,
        font_size=style.font_size,
        primary_color=style.primary_color,
        highlight_color=style.highlight_color,
        outline_color=style.outline_color,
        outline_width=style.outline_width,
        margin_v=style.position_margin_v,
    )

    events = []
    for chunk in chunks:
        if not chunk:
            continue
        start = _fmt_timestamp(chunk[0].start_s)
        end = _fmt_timestamp(chunk[-1].end_s)
        words = [w.text.strip() for w in chunk]
        text = " ".join(w.upper() if style.uppercase else w for w in words)
        # Escape ASS special characters that would otherwise break rendering
        text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(events), encoding="utf-8")
    return output_path
