"""
Evaluation harness — spec §18.1.

Runs the current scoring prompt/model against the development or hold-out
benchmark set and writes an eval_runs row with the computed metrics.

Promotion gate: a change to the scoring prompt, the reasoning model, or
the scoring weights is promoted to production only if Precision@5 and
human agreement rate on the 10-episode HOLD-OUT slice do not regress
relative to the current production version.

The development slice (40 episodes) is used during iteration.
The hold-out slice (10 episodes) is ONLY touched immediately before a
promotion decision — never during tuning.
"""
import os
import json
import sys
from pathlib import Path
from autonomous_media.runtime.manager import stage_manager, InferenceRequest


DEV_BENCHMARK = Path(__file__).parent / "benchmark_dev_v1.jsonl"
HOLDOUT_BENCHMARK = Path(__file__).parent / "benchmark_holdout_v1.jsonl"


def load_benchmark(path: Path) -> list[dict]:
    if not path.exists():
        print(f"[WARN] Benchmark file not found: {path}")
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_precision_at_k(predicted_ids: list[str], labeled_good_ids: list[str], k: int = 5) -> float:
    """Of the top-k predicted clips, what fraction appears in the human-labeled good set?"""
    if not predicted_ids:
        return 0.0
    top_k = predicted_ids[:k]
    hits = sum(1 for p in top_k if p in labeled_good_ids)
    return hits / min(k, len(top_k))


def run_eval(benchmark_path: Path, model_version: str = "stub") -> dict:
    """
    Run scoring against every episode in the benchmark set.
    Returns a metrics dict suitable for writing to the eval_runs table.
    """
    episodes = load_benchmark(benchmark_path)
    if not episodes:
        print("No benchmark episodes loaded. Label some episodes first (spec §25.9).")
        return {}

    # Load scoring prompt template
    prompt_path = Path(__file__).parent.parent / "autonomous_media" / "prompts" / "scoring_v3.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    except Exception as e:
        print(f"[ERROR] Failed to load scoring prompt template: {e}")
        return {}

    precision_scores = []
    for episode in episodes:
        labeled_good = episode.get("labeled_good_clip_ids", [])
        candidates = episode.get("candidates", [])
        
        scored_candidates = []
        for cand in candidates:
            # Format prompt template
            prompt = (
                prompt_template
                .replace("{channel_profile_summary}", "Niche: Tech and Startups podcast")
                .replace("{start_ms}", "0")
                .replace("{end_ms}", "0")
                .replace("{candidate_text}", cand["text"])
            )
            
            # Call real StageModelManager scoring
            try:
                res = stage_manager.run_stage("scoring", InferenceRequest(prompt=prompt))
                scores = json.loads(res.text)
            except Exception as e:
                print(f"[WARN] Failed to score candidate {cand['id']}: {e}")
                scores = {}
                
            # Compute composite score using the same formula
            weighted_score = (
                scores.get("hook_strength", 0) * 1.0 +
                scores.get("emotional_intensity", 0) * 1.0 +
                scores.get("curiosity_gap", 0) * 1.0 +
                scores.get("humor", 0) * 0.7 +
                scores.get("educational_value", 0) * 1.0 +
                scores.get("story_completeness", 0) * 0.8
            )
            scored_candidates.append((cand["id"], weighted_score))
            
        # Sort candidates descending by score and pick top 5
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        predicted = [cand_id for cand_id, _ in scored_candidates][:5]
        
        p_at_5 = compute_precision_at_k(predicted, labeled_good, k=5)
        precision_scores.append(p_at_5)

    mean_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0

    metrics = {
        "precision_at_5": round(mean_precision, 4),
        "episode_count": len(episodes),
        "model_version": model_version,
        "benchmark_path": str(benchmark_path.name),
    }
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    slice_arg = sys.argv[1] if len(sys.argv) > 1 else "dev"
    path = HOLDOUT_BENCHMARK if slice_arg == "holdout" else DEV_BENCHMARK
    run_eval(path)
