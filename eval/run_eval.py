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
import json
import sys
from pathlib import Path


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

    precision_scores = []
    for episode in episodes:
        labeled_good = episode.get("labeled_good_clip_ids", [])
        # STUB: replace with real scoring call through StageModelManager
        predicted = episode.get("candidate_ids", [])[:5]
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
