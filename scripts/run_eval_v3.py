"""
PCSP v3 in-distribution persona-classification eval.

Runs `zero_shot_consistency` on the 4 PCSP-v3 checkpoints
(full, no_consist, no_diverse, concat).

  IMPORTANT — protocol caveat
  -----------------------------------------------------------------
  The v3 sweep trained on `personas_300_v3.json` (all 300 personas),
  not on a 240-train / 60-test split. So the 60 IDs we evaluate
  here (taken from v1's `test_60.json` for ID continuity) WERE seen
  during v3 training. This is therefore *in-distribution persona
  separability*, not zero-shot generalization.

  Useful for: ablation ranking — does the consistency loss make
  trajectories more persona-recoverable on the same metric?
  NOT useful for: zero-shot / compositional-generalization claims —
  those require retraining on a held-out v3 split first.
  -----------------------------------------------------------------

B1 (no-persona PPO) is excluded — there is no persona conditioning
to recover. B3 (SBERT) is excluded — it has no trained
TrajectoryEncoder of its own, so persona-classification with PCSP's
encoder would be apples-to-oranges.

Usage:
  conda run -n paper python scripts/run_eval_v3.py
"""
from __future__ import annotations

import json
import sys
import time
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

PCSP_V3 = ROOT / "results/pcsp_v3"
EMBEDDINGS = ROOT / "results/embeddings/persona_embeddings_300.npy"
TEST_60_V1 = ROOT / "data/personas/test_60.json"
PERSONAS_V3 = ROOT / "data/personas/personas_300_v3.json"

VARIANTS = [
    ("full",       PCSPActorCritic),
    ("no_consist", PCSPActorCritic),
    ("no_diverse", PCSPActorCritic),
    ("concat",     ConcatActorCritic),
]


def _v3_env_factory(personas):
    return MiniInzoiV3Env(personas=personas, max_steps=200)


def main():
    test_60 = json.load(open(TEST_60_V1))
    test_ids = {p["id"] for p in test_60}
    v3_all = json.load(open(PERSONAS_V3))
    test_v3 = [p for p in v3_all if p["id"] in test_ids]
    assert len(test_v3) == 60, f"Expected 60 v3 test personas, got {len(test_v3)}"

    embeddings = np.load(EMBEDDINGS)
    print(f"Loaded {len(test_v3)} v3 personas; embeddings shape={embeddings.shape}")

    results: dict[str, dict] = {}
    t_total = time.time()

    for mode, ModelClass in VARIANTS:
        ckpt_dir = PCSP_V3 / mode
        policy_path = ckpt_dir / "policy.pt"
        encoder_path = ckpt_dir / "traj_encoder.pt"
        if not (policy_path.exists() and encoder_path.exists()):
            print(f"[skip] {mode}: missing checkpoint")
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
        res["elapsed_sec"] = elapsed
        results[mode] = res

        out = ckpt_dir / "eval_persona_classification_indist60.json"
        with open(out, "w") as f:
            json.dump(res, f, indent=2)
        print(f"  acc={res.get('accuracy', float('nan')):.3f}  "
              f"coherence={res.get('coherence_ratio', float('nan')):.2f}  "
              f"intra={res.get('intra_cos_mean', float('nan')):.3f}  "
              f"inter={res.get('inter_cos_mean', float('nan')):.3f}  "
              f"elapsed={elapsed:.1f}s")

    total = time.time() - t_total

    print("\n" + "=" * 78)
    print("  PCSP-v3 in-distribution persona classification (60 personas, n_ep=5)")
    print("=" * 78)
    print(f"  {'mode':<12} | {'acc':>6} | {'coherence':>9} | {'intra':>6} | {'inter':>6}")
    print(f"  {'-'*12} | {'-'*6} | {'-'*9} | {'-'*6} | {'-'*6}")
    for k, r in results.items():
        print(f"  {k:<12} | "
              f"{r.get('accuracy', float('nan')):.3f}  | "
              f"{r.get('coherence_ratio', float('nan')):8.2f}  | "
              f"{r.get('intra_cos_mean', float('nan')):.3f}  | "
              f"{r.get('inter_cos_mean', float('nan')):.3f}")
    print(f"\n  Total elapsed: {total:.1f}s")

    summary = ROOT / "results/pcsp_v3/eval_indist60_summary.json"
    with open(summary, "w") as f:
        json.dump({
            "metric": "in_distribution_persona_classification",
            "n_personas": len(test_v3),
            "n_episodes_per_persona": 5,
            "personas_seen_during_training": True,
            "results": results,
            "elapsed_sec": total,
        }, f, indent=2)
    print(f"  Saved: {summary}")


if __name__ == "__main__":
    main()
