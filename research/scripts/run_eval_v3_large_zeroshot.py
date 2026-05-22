"""PCSP v3-large zero-shot persona-classification eval.

Mirrors scripts/run_eval_v3_zeroshot.py for the 12x12 / 16-agent v3-large
sweep. Loads per-seed checkpoints from results/pcsp_v3_large/{mode}_seed{S}/
and aggregates accuracy / CI / coherence across seeds (mean +/- std).

Outputs:
  results/pcsp_v3_large/{mode}_seed{S}/eval_persona_classification_zs100.json
  results/pcsp_v3_large/eval_zs100_summary.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from math import sqrt
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi_v3_large import MiniInzoiV3LargeEnv, N_AGENTS as N_AGENTS_LARGE
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_LARGE
from src.eval.zeroshot import zero_shot_consistency
from src.training.pcsp_trainer import (
    ConcatActorCritic,
    PCSPActorCritic,
    TrajectoryEncoder,
)

EMBEDDINGS = REPO / "results" / "embeddings" / "persona_embeddings_500.npy"

VARIANTS = [
    ("full",       PCSPActorCritic),
    ("no_consist", PCSPActorCritic),
    ("no_diverse", PCSPActorCritic),
    ("concat",     ConcatActorCritic),
]


def _v3l_env_factory(personas):
    return MiniInzoiV3LargeEnv(personas=personas, max_steps=200)


def _wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - margin) / den), min(1.0, (centre + margin) / den))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoints_root", default="results/pcsp_v3_large")
    parser.add_argument("--test_personas", default="data/personas/test_100_v3.json")
    parser.add_argument("--out_filename", default="eval_persona_classification_zs100.json")
    parser.add_argument("--summary_filename", default="eval_zs100_summary.json")
    parser.add_argument("--n_episodes", type=int, default=5)
    args = parser.parse_args()

    ckpts_root = ROOT / args.checkpoints_root
    test_path  = ROOT / args.test_personas

    test_v3 = json.load(open(test_path))
    print(f"Loaded {len(test_v3)} v3 test personas from {test_path}")
    embeddings = np.load(EMBEDDINGS)
    print(f"embeddings shape={embeddings.shape}")
    print(f"Reading checkpoints from {ckpts_root}")

    # Discover per-mode per-seed dirs: {mode}_seed{S}
    pattern = re.compile(r"^(?P<mode>[a-z_]+)_seed(?P<seed>\d+)$")
    per_mode: dict[str, list[tuple[int, Path]]] = {m: [] for m, _ in VARIANTS}
    for child in sorted(ckpts_root.glob("*_seed*")):
        if not child.is_dir():
            continue
        m = pattern.match(child.name)
        if not m:
            continue
        mode = m.group("mode")
        seed = int(m.group("seed"))
        if mode in per_mode:
            per_mode[mode].append((seed, child))

    results_per_seed: dict[str, dict] = {}
    aggregated: dict[str, dict] = {}
    t_total = time.time()

    for mode, ModelClass in VARIANTS:
        seed_dirs = per_mode.get(mode, [])
        if not seed_dirs:
            print(f"[skip] {mode}: no seed dirs under {ckpts_root}")
            continue
        accs = []
        coherences = []
        intras = []
        inters = []
        for seed, ckpt_dir in seed_dirs:
            inner = ckpt_dir / mode
            policy_path = inner / "policy.pt"
            encoder_path = inner / "traj_encoder.pt"
            if not (policy_path.exists() and encoder_path.exists()):
                print(f"  [skip] {mode}@{seed}: missing files in {ckpt_dir}")
                continue
            print(f"\n=== {mode} seed={seed} ({ModelClass.__name__}) ===")
            policy = ModelClass(OBS_DIM_V3_LARGE, N_ACTIONS_V3)
            policy.load_state_dict(torch.load(policy_path, map_location="cpu"))
            traj_enc = TrajectoryEncoder(OBS_DIM_V3_LARGE, N_ACTIONS_V3)
            traj_enc.load_state_dict(torch.load(encoder_path, map_location="cpu"))

            t0 = time.time()
            res = zero_shot_consistency(
                policy, traj_enc, test_v3, embeddings,
                n_episodes=args.n_episodes, device="cuda",
                n_agents=N_AGENTS_LARGE,
                env_factory=_v3l_env_factory,
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
            res["seed"] = seed

            out = inner / args.out_filename
            out.write_text(json.dumps(res, indent=2), encoding="utf-8")
            results_per_seed[f"{mode}@{seed}"] = res
            print(f"  acc={accuracy:.3f}  CI=[{lo:.3f},{hi:.3f}]  "
                  f"coh={res.get('coherence_ratio', float('nan')):.2f}  elapsed={elapsed:.1f}s")
            accs.append(accuracy)
            coherences.append(float(res.get("coherence_ratio", float("nan"))))
            intras.append(float(res.get("intra_cos_mean", float("nan"))))
            inters.append(float(res.get("inter_cos_mean", float("nan"))))

        if accs:
            aggregated[mode] = {
                "n_seeds": len(accs),
                "seeds": [s for s, _ in seed_dirs[:len(accs)]],
                "accuracy_mean": float(np.mean(accs)),
                "accuracy_std":  float(np.std(accs, ddof=0)),
                "coherence_mean": float(np.nanmean(coherences)),
                "coherence_std":  float(np.nanstd(coherences, ddof=0)),
                "intra_mean":    float(np.nanmean(intras)),
                "inter_mean":    float(np.nanmean(inters)),
                "random_chance": 1.0 / max(1, len(test_v3)),
            }

    total = time.time() - t_total
    print("\n" + "=" * 90)
    print(f"  PCSP-v3-LARGE zero-shot persona classification (n={len(test_v3)}, n_ep={args.n_episodes})")
    print("=" * 90)
    print(f"  {'mode':<12} | {'acc mean':>9} | {'acc std':>7} | {'coh mean':>8} | n_seeds")
    for mode, agg in aggregated.items():
        print(f"  {mode:<12} | {agg['accuracy_mean']:>9.3f} | {agg['accuracy_std']:>7.3f} | "
              f"{agg['coherence_mean']:>8.2f} | {agg['n_seeds']}")

    summary = ckpts_root / args.summary_filename
    summary.write_text(json.dumps({
        "metric": "zero_shot_persona_classification",
        "n_personas": len(test_v3),
        "n_episodes_per_persona": args.n_episodes,
        "n_agents_per_env": N_AGENTS_LARGE,
        "split_source": str(test_path.relative_to(ROOT)),
        "checkpoints_root": str(ckpts_root.relative_to(ROOT)),
        "per_seed": results_per_seed,
        "aggregated": aggregated,
        "elapsed_sec": total,
    }, indent=2, default=float), encoding="utf-8")
    print(f"  Saved: {summary}")


if __name__ == "__main__":
    main()
