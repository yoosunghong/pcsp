"""
PCSP v3 zero-shot persona-classification eval.

Sister script to scripts/run_eval_v3.py — but evaluates checkpoints trained on
a 240-train split against a 60-persona held-out test split, so this is true
zero-shot, not in-distribution.

Modes evaluated (PCSPActorCritic | ConcatActorCritic):
  full, no_consist, no_diverse, concat
B1 (no-persona PPO) and B3 (SBERT) are excluded for the same reasons as
run_eval_v3.py: B1 has no persona to recover, B3 has no own TrajectoryEncoder.

Default outputs (unseen_occupation_v3 split):
  results/pcsp_v3_zeroshot/{mode}/eval_persona_classification_zs60.json
  results/pcsp_v3_zeroshot/eval_zs60_summary.json

Usage:
  conda run -n paper python scripts/run_eval_v3_zeroshot.py
  # Or, for compositional split families:
  conda run -n paper python scripts/run_eval_v3_zeroshot.py \\
      --checkpoints_root results/pcsp_v3_archetype_zs \\
      --test_personas data/personas/splits/unseen_archetype_v3_test.json \\
      --out_filename eval_persona_classification_archetype.json \\
      --summary_filename eval_archetype_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from math import sqrt
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi_v3 import MiniInzoiV3Env
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_BASE
from src.eval.zeroshot import zero_shot_consistency
from src.training.pcsp_trainer import (
    ConcatActorCritic,
    PCSPActorCritic,
    TrajectoryEncoder,
)

EMBEDDINGS = ROOT / "results/embeddings/persona_embeddings_300.npy"

VARIANTS = [
    ("full",       PCSPActorCritic),
    ("no_consist", PCSPActorCritic),
    ("no_diverse", PCSPActorCritic),
    ("concat",     ConcatActorCritic),
]


def _v3_env_factory(personas):
    return MiniInzoiV3Env(personas=personas, max_steps=200)


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - margin) / den), min(1.0, (centre + margin) / den))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoints_root", default="results/pcsp_v3_zeroshot",
                        help="Per-mode checkpoint dir root (expects {root}/{mode}/{policy,traj_encoder}.pt).")
    parser.add_argument("--test_personas", default="data/personas/test_60_v3.json",
                        help="JSON file with the held-out test personas.")
    parser.add_argument("--out_filename", default="eval_persona_classification_zs60.json",
                        help="Per-mode output filename inside each ckpt dir.")
    parser.add_argument("--summary_filename", default="eval_zs60_summary.json",
                        help="Combined summary filename inside checkpoints_root.")
    args = parser.parse_args()

    ckpts_root = ROOT / args.checkpoints_root
    test_path  = ROOT / args.test_personas

    test_v3 = json.load(open(test_path))
    assert len(test_v3) == 60, f"Expected 60 v3 test personas, got {len(test_v3)}"

    embeddings = np.load(EMBEDDINGS)
    print(f"Loaded {len(test_v3)} v3 test personas from {test_path}; "
          f"embeddings shape={embeddings.shape}")
    print(f"Reading checkpoints from {ckpts_root}")

    results: dict[str, dict] = {}
    t_total = time.time()

    for mode, ModelClass in VARIANTS:
        ckpt_dir = ckpts_root / mode
        policy_path = ckpt_dir / "policy.pt"
        encoder_path = ckpt_dir / "traj_encoder.pt"
        if not (policy_path.exists() and encoder_path.exists()):
            print(f"[skip] {mode}: missing checkpoint at {ckpt_dir}")
            continue

        print(f"\n=== {mode} ({ModelClass.__name__}) ===")
        policy = ModelClass(OBS_DIM_V3_BASE, N_ACTIONS_V3)
        policy.load_state_dict(torch.load(policy_path, map_location="cpu"))

        traj_enc = TrajectoryEncoder(OBS_DIM_V3_BASE, N_ACTIONS_V3)
        traj_enc.load_state_dict(torch.load(encoder_path, map_location="cpu"))

        t0 = time.time()
        res = zero_shot_consistency(
            policy, traj_enc, test_v3, embeddings,
            n_episodes=5, device="cuda", n_agents=4,
            env_factory=_v3_env_factory,
        )
        elapsed = time.time() - t0

        n_traj = int(res.get("n_trajectories", 0))
        accuracy = float(res.get("accuracy", 0.0))
        k = int(round(accuracy * n_traj))
        lo, hi = _wilson_ci(k, n_traj)
        res["wilson_ci_95"] = [lo, hi]
        res["random_chance"] = 1.0 / max(1, len(test_v3))
        res["speedup_over_chance"] = accuracy / res["random_chance"] if res["random_chance"] else 0.0
        res["elapsed_sec"] = elapsed
        results[mode] = res

        out = ckpt_dir / args.out_filename
        with open(out, "w") as f:
            json.dump(res, f, indent=2)
        print(f"  acc={accuracy:.3f}  CI=[{lo:.3f},{hi:.3f}]  "
              f"coherence={res.get('coherence_ratio', float('nan')):.2f}  "
              f"intra={res.get('intra_cos_mean', float('nan')):.3f}  "
              f"inter={res.get('inter_cos_mean', float('nan')):.3f}  "
              f"elapsed={elapsed:.1f}s")

    total = time.time() - t_total

    print("\n" + "=" * 90)
    print("  PCSP-v3 zero-shot persona classification (60 unseen personas, n_ep=5)")
    print("=" * 90)
    print(f"  {'mode':<12} | {'acc':>6} | {'CI95':>20} | {'coherence':>9} | {'intra':>6} | {'inter':>6}")
    print(f"  {'-'*12} | {'-'*6} | {'-'*20} | {'-'*9} | {'-'*6} | {'-'*6}")
    for k, r in results.items():
        ci = r.get("wilson_ci_95", [0, 0])
        print(f"  {k:<12} | "
              f"{r.get('accuracy', float('nan')):.3f}  | "
              f"[{ci[0]:.3f},{ci[1]:.3f}]    | "
              f"{r.get('coherence_ratio', float('nan')):8.2f}  | "
              f"{r.get('intra_cos_mean', float('nan')):.3f}  | "
              f"{r.get('inter_cos_mean', float('nan')):.3f}")
    print(f"\n  Total elapsed: {total:.1f}s")

    summary = ckpts_root / args.summary_filename
    with open(summary, "w") as f:
        json.dump({
            "metric": "zero_shot_persona_classification",
            "n_personas": len(test_v3),
            "n_episodes_per_persona": 5,
            "personas_seen_during_training": False,
            "split_source": str(test_path.relative_to(ROOT)),
            "checkpoints_root": str(ckpts_root.relative_to(ROOT)),
            "results": results,
            "elapsed_sec": total,
        }, f, indent=2)
    print(f"  Saved: {summary}")


if __name__ == "__main__":
    main()
