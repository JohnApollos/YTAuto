"""
autonomous_media/workers/narration.py

The Narration Engine for the curated_story content source (spec
section 30.5). Wraps Piper -- a local, CPU-only neural TTS engine.

Piper is treated the same way FFmpeg is -- a direct subprocess call,
not a managed ModelRuntime -- because it runs entirely on CPU and
doesn't contend with the VRAM the scoring/vision models need.

After narration, the generated audio is fed into the existing Whisper
Transcription worker (spec section 12.3), exactly like a podcast
recording, so caption timing needs zero new code.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NarrationResult:
    audio_path: Path
    duration_s: float


# ---------------------------------------------------------------------------
# Voice configuration -- maps channel voice_profile name → Piper model file.
# Add new entries here as new voices are adopted.
# ---------------------------------------------------------------------------

VOICE_MODEL_PATHS: dict[str, str] = {
    "motivational_male_v1": "models/piper/en_US-ryan-high.onnx",
    "warm_female_v1": "models/piper/en_US-amy-medium.onnx",
    "narrator_neutral_v1": "models/piper/en_US-lessac-high.onnx",
}

DEFAULT_VOICE = "narrator_neutral_v1"


class UnknownVoiceProfileError(Exception):
    pass


def _resolve_voice_model(voice_profile: str | None) -> str:
    profile = voice_profile or DEFAULT_VOICE
    if profile not in VOICE_MODEL_PATHS:
        raise UnknownVoiceProfileError(
            f"voice_profile '{profile}' has no entry in VOICE_MODEL_PATHS -- "
            f"add it before assigning it to a channel."
        )
    return VOICE_MODEL_PATHS[profile]


import shutil
import os

def _find_piper_binary(default: str = "piper") -> str:
    """Resolve piper binary path across Windows/Linux environments."""
    if shutil.which(default):
        return default
    if shutil.which("piper.exe"):
        return "piper.exe"
    
    candidates = [
        os.path.join("models", "piper", "piper.exe"),
        os.path.join("models", "piper", "piper"),
        "C:\\piper\\piper.exe",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return default

def narrate(
    script_text: str,
    voice_profile: str | None,
    output_path: Path,
    piper_binary: str | None = None,
) -> NarrationResult:
    """Generates narration audio for already-prepared script text.

    Runs Piper as a subprocess rather than importing it as a library.
    The generated audio is a WAV file suitable for feeding directly into
    the Whisper Transcription worker.
    """
    voice_model = _resolve_voice_model(voice_profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_binary = os.path.abspath(piper_binary or _find_piper_binary())
    resolved_model = os.path.abspath(voice_model)
    resolved_output = os.path.abspath(output_path)

    cmd = [
        resolved_binary,
        "--model", resolved_model,
        "--output_file", resolved_output,
    ]

    piper_dir = os.path.dirname(resolved_binary)
    result = subprocess.run(
        cmd,
        input=script_text,
        capture_output=True,
        text=True,
        cwd=piper_dir if os.path.exists(piper_dir) else None
    )
    if result.returncode != 0:
        raise RuntimeError(f"Piper narration failed using binary '{resolved_binary}' and model '{voice_model}':\n{result.stderr}")

    duration_s = _probe_duration(output_path)
    return NarrationResult(audio_path=output_path, duration_s=duration_s)


def _probe_duration(audio_path: Path) -> float:
    """Uses ffprobe (ships alongside FFmpeg) to read the audio duration."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Could not read narration duration:\n{result.stderr}")
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# Script preparation prompt (spec section 30.2)
# Kept here alongside its only caller for now; promote to prompts/ as a
# versioned file (spec section 25.8) once it's stable.
# ---------------------------------------------------------------------------

SCRIPT_PREP_PROMPT_V1 = """SYSTEM:
You are preparing a Reddit post for spoken narration. Rewrite the text
below for natural spoken pacing: remove markdown formatting, expand
abbreviations a listener wouldn't parse aloud (e.g. "AITA" -> "Am I
the jerk"), and break it into short paragraphs at natural pause
points. Do not add any fact, event, or detail not present in the
original text -- this is a pacing and formatting pass only, not a
rewrite of the story itself. Return only the prepared script text.

USER:
Title: {title}
Body:
{body_text}
"""


def prepare_script(title: str, body_text: str, model_manager) -> str:
    """Thin wrapper around the Model Runtime Manager (spec section 12.9)."""
    from autonomous_media.runtime.manager import InferenceRequest

    try:
        prompt_text = SCRIPT_PREP_PROMPT_V1.format(title=title, body_text=body_text)
        request = InferenceRequest(prompt=prompt_text)
        result = model_manager.run_stage(stage="script_preparation", request=request)
        res_text = result.text.strip()
        if "hook_strength" in res_text or "Stub result" in res_text or res_text.startswith("{"):
            return f"{title}\n\n{body_text}"
        return res_text
    except Exception:
        return f"{title}\n\n{body_text}"
