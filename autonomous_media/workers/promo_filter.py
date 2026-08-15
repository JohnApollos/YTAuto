"""
autonomous_media/workers/promo_filter.py

Fixes the production defect: the scorer selected a mid-episode sponsor
read as a clip. Ad copy is written to be persuasive and engaging --
exactly what the hook/curiosity heuristics in the Intelligence Engine
reward -- so this needs an explicit exclusion pass, not a scoring
adjustment. See spec section 11.8 for the full design rationale.

This runs once per transcript, before candidate generation (spec
section 11.1), and its output is cached on transcripts.promo_segments
(spec section 8.3) so it's never recomputed for the same transcript.

Two-stage cascade, matching the pattern already established for
clip scoring itself (spec section 20.3): cheap heuristics first,
a batched LLM call only on what survives.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Stage 1: cheap heuristic pre-filter
# ---------------------------------------------------------------------------

PROMO_MARKERS = [
    "sponsored by",
    "this episode is brought to you by",
    "brought to you by",
    "use code",
    "promo code",
    "discount code",
    "% off",
    "percent off",
    "check out the link",
    "link in the description",
    "link in the show notes",
    "our sponsor",
    "today's sponsor",
    "use my code",
    "head to",  # common ad-read lead-in ("head to squarespace.com/...")
]


@dataclass
class TimeRange:
    start_ms: int
    end_ms: int


@dataclass
class TranscriptWindow:
    text: str
    start_ms: int
    end_ms: int


def heuristic_promo_flag(window_text: str) -> bool:
    lowered = window_text.lower()
    return any(marker in lowered for marker in PROMO_MARKERS)


def build_sliding_windows(
    words: list[dict], window_length_s: float = 30.0, step_s: float = 15.0
) -> list[TranscriptWindow]:
    """Build overlapping windows over the full transcript for promo detection.
    Uses the same raw word-dict format stored in MinIO.
    """
    if not words:
        return []

    window_ms = int(window_length_s * 1000)
    step_ms = int(step_s * 1000)
    first_start = words[0].get("start_ms", 0)
    last_end = words[-1].get("end_ms", 0)

    windows = []
    pos = first_start
    while pos < last_end:
        end_pos = pos + window_ms
        window_words = [
            w for w in words
            if w.get("start_ms", 0) >= pos and w.get("end_ms", 0) <= end_pos
        ]
        if window_words:
            text = " ".join(w.get("word", "") for w in window_words)
            windows.append(TranscriptWindow(
                text=text,
                start_ms=window_words[0]["start_ms"],
                end_ms=window_words[-1]["end_ms"],
            ))
        pos += step_ms

    return windows


# ---------------------------------------------------------------------------
# Stage 2: batched LLM classification for borderline windows
# ---------------------------------------------------------------------------

def _llm_classify_batch(
    windows: list[TranscriptWindow],
    model_manager,
    batch_size: int = 15,
) -> list[TranscriptWindow]:
    """Classifies windows that didn't trip the heuristic filter. Batched
    for the same reason clip scoring is batched (spec section 11.1) --
    one call per group amortizes the shared prompt tokens instead of
    repeating them per window."""
    try:
        from autonomous_media.prompts import PROMO_DETECTION_PROMPT_V1
    except ImportError:
        # Prompt not available yet - skip LLM classification gracefully
        return []

    import json
    flagged: list[TranscriptWindow] = []

    for batch_start in range(0, len(windows), batch_size):
        batch = windows[batch_start: batch_start + batch_size]
        if not batch:
            continue

        try:
            from autonomous_media.runtime.manager import InferenceRequest
            windows_json = json.dumps([
                {"id": i, "text": w.text}
                for i, w in enumerate(batch)
            ])
            formatted_prompt = PROMO_DETECTION_PROMPT_V1.replace("{windows}", windows_json)
            request = InferenceRequest(prompt=formatted_prompt)
            result = model_manager.run_stage(
                stage="promo_detection",
                request=request,
            )
            # Expected result text: {"promotional_ids": [0, 3, 7, ...]}
            data = json.loads(result.text) if result.text else {}
            promotional_ids = set(data.get("promotional_ids", []))
            flagged.extend(batch[i] for i in range(len(batch)) if i in promotional_ids)
        except Exception:
            # LLM classification is best-effort; heuristics already caught the
            # obvious cases. Don't let a model failure abort promo detection.
            pass

    return flagged


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_promo_segments(
    words: list[dict],
    model_manager=None,
) -> list[TimeRange]:
    """Full two-stage detection. Call once per transcript; cache the
    result on transcripts.promo_segments (spec section 8.3).
    `model_manager` is optional -- if None, only the heuristic stage runs.
    """
    windows = build_sliding_windows(words)
    heuristic_hits = [w for w in windows if heuristic_promo_flag(w.text)]
    heuristic_hit_ids = {id(w) for w in heuristic_hits}
    borderline = [w for w in windows if id(w) not in heuristic_hit_ids]

    llm_hits = []
    if model_manager is not None and borderline:
        llm_hits = _llm_classify_batch(borderline, model_manager)

    all_hits = heuristic_hits + llm_hits
    ranges = [TimeRange(w.start_ms, w.end_ms) for w in all_hits]
    return _merge_adjacent_ranges(ranges)


def _merge_adjacent_ranges(
    ranges: list[TimeRange], gap_tolerance_ms: int = 2000
) -> list[TimeRange]:
    """Merges overlapping/near-adjacent flagged windows into contiguous
    promo blocks -- an ad read is rarely exactly one window long."""
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda r: r.start_ms)
    merged = [TimeRange(ranges[0].start_ms, ranges[0].end_ms)]
    for r in ranges[1:]:
        last = merged[-1]
        if r.start_ms <= last.end_ms + gap_tolerance_ms:
            merged[-1] = TimeRange(last.start_ms, max(last.end_ms, r.end_ms))
        else:
            merged.append(TimeRange(r.start_ms, r.end_ms))
    return merged


def overlap_fraction(
    candidate_start_ms: int,
    candidate_end_ms: int,
    promo_ranges: list[TimeRange],
) -> float:
    """Fraction of a candidate clip's duration that overlaps any promo range."""
    candidate_len = candidate_end_ms - candidate_start_ms
    if candidate_len <= 0:
        return 0.0

    overlap_ms = 0
    for r in promo_ranges:
        lo = max(candidate_start_ms, r.start_ms)
        hi = min(candidate_end_ms, r.end_ms)
        if hi > lo:
            overlap_ms += hi - lo

    return overlap_ms / candidate_len


def filter_promo_overlap(
    candidates: list,
    promo_ranges: list[TimeRange],
    max_overlap: float = 0.20,
) -> list:
    """Hard exclusion, not a scoring penalty -- a candidate that's mostly
    ad copy shouldn't be rankable at all, regardless of how well the
    remaining portion would otherwise score. `candidates` is expected to
    have .start_ms / .end_ms attributes OR be dicts with those keys."""
    def get_start(c):
        return c["start_ms"] if isinstance(c, dict) else c.start_ms

    def get_end(c):
        return c["end_ms"] if isinstance(c, dict) else c.end_ms

    return [
        c for c in candidates
        if overlap_fraction(get_start(c), get_end(c), promo_ranges) < max_overlap
    ]
