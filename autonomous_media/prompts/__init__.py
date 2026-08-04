"""
autonomous_media/prompts/__init__.py

Exposes all versioned prompt constants so workers can do:
    from autonomous_media.prompts import PROMO_DETECTION_PROMPT_V1

Prompts are stored as .txt files alongside this file for version control
discipline (spec section 25.8). This module loads them at import time.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """Load a prompt file, stripping trailing whitespace."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


# Versioned prompt constants -- import these, never inline raw strings.
SCORING_PROMPT_V3 = _load("scoring_v3.txt")
TITLE_PROMPT_V1 = _load("title_v1.txt")
DESCRIPTION_PROMPT_V1 = _load("description_v1.txt")
GROUNDING_PROMPT_V1 = _load("grounding_v1.txt")
PROMO_DETECTION_PROMPT_V1 = _load("promo_detection_v1.txt")
SCRIPT_PREP_PROMPT_V1 = _load("script_prep_v1.txt")
