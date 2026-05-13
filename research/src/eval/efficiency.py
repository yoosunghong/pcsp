"""
Sample efficiency — eval/efficiency.py

Computes reward-per-env-step curves from saved training metrics JSON files.
Also reports the step count at which each model first exceeds a reward threshold,
and area-under-curve (AUC) as a summary efficiency statistic.

Usage (standalone):
    python src/eval/efficiency.py \
        --metrics_dirs results/pcsp/full results/baselines/b1_no_persona results/baselines/b3_sbert \
        --threshold 80.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def compute_efficiency(
    metrics_list:    list[dict],
    n_transitions_key: str = "n_transitions",
    reward_key:      str = "mean_ep_reward",
    threshold:       float = 80.0,
) -> dict:
    """
    Compute sample efficiency metrics from a list of per-iteration metric dicts.

    Returns:
        total_steps:        cumulative env steps at end of training
        auc_per_1k_steps:   area under reward curve per 1000 env steps
        steps_to_threshold: env steps to first exceed `threshold` reward (-1 if never)
        final_reward:       last reward
        reward_per_1k:      reward / 1000 total env steps (simple ratio)
    """
    cum_steps = 0
    cum_steps_list: list[float] = []
    rewards: list[float] = []

    for m in metrics_list:
        cum_steps += m.get(n_transitions_key, 0)
        cum_steps_list.append(float(cum_steps))
        rewards.append(float(m.get(reward_key, 0.0)))

    rewards_arr = np.array(rewards)
    steps_arr   = np.array(cum_steps_list)

    # AUC using trapezoidal rule, normalised by total steps
    if len(steps_arr) > 1:
        auc = float(np.trapz(rewards_arr, steps_arr) / (steps_arr[-1] + 1e-8) * 1000)
    else:
        auc = 0.0

    # Steps to threshold
    above = np.where(rewards_arr >= threshold)[0]
    steps_to_threshold = int(steps_arr[above[0]]) if len(above) > 0 else -1

    final_reward = float(rewards_arr[-1]) if len(rewards_arr) > 0 else 0.0
    total_steps  = int(cum_steps)
    reward_per_1k = float(final_reward / (total_steps / 1000)) if total_steps > 0 else 0.0

    return {
        "total_steps":        total_steps,
        "auc_per_1k_steps":   auc,
        "steps_to_threshold": steps_to_threshold,
        "threshold":          threshold,
        "final_reward":       final_reward,
        "reward_per_1k":      reward_per_1k,
    }


def load_metrics_from_dir(metrics_dir: Path | str) -> list[dict]:
    """Load per-iteration metrics from a results directory (metrics.json)."""
    p = Path(metrics_dir) / "metrics.json"
    if not p.exists():
        raise FileNotFoundError(f"metrics.json not found in {metrics_dir}")
    with open(p) as f:
        data = json.load(f)
    # Support both {metrics: [...]} and {results: {key: last_dict}} formats
    if "metrics" in data:
        return data["metrics"]
    raise ValueError(f"Unsupported metrics.json format in {metrics_dir}")


def compare_efficiency(
    named_dirs:  dict[str, str | Path],  # {label: metrics_dir}
    threshold:   float = 80.0,
) -> dict[str, dict]:
    """
    Compare sample efficiency across multiple models.
    Returns a dict mapping label → efficiency stats.
    """
    results = {}
    for label, d in named_dirs.items():
        try:
            metrics = load_metrics_from_dir(d)
            results[label] = compute_efficiency(metrics, threshold=threshold)
        except Exception as e:
            results[label] = {"error": str(e)}
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--metrics_dirs", nargs="+", required=True,
                   help="Paths to results dirs containing metrics.json")
    p.add_argument("--labels",       nargs="+", default=None,
                   help="Labels for each dir (defaults to dir name)")
    p.add_argument("--threshold",    type=float, default=80.0,
                   help="Reward threshold for steps_to_threshold metric")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    labels = args.labels or [Path(d).name for d in args.metrics_dirs]
    named  = dict(zip(labels, args.metrics_dirs))
    result = compare_efficiency(named, threshold=args.threshold)
    print(json.dumps(result, indent=2))
