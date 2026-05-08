"""
PCSP v3 학습 실행 스크립트 — Phase C

Thin wrapper around the threaded `train_pcsp` (post §7 refactor) that supplies:
  - obs_dim = 33  (v3 base scale, 4 agents)
  - n_actions = 20
  - env_factory → MiniInzoiV3Env
  - personas_json → data/personas/personas_300_v3.json (v3 preferred_actions)

The Qwen3 embeddings file is reused unchanged: persona IDs are preserved
between personas_300.json and personas_300_v3.json (only `preferred_actions`
was rewritten by scripts/build_personas_v3.py).

Usage:
  # smoke (20 iter, full mode)
  conda run -n paper python scripts/run_pcsp_v3.py --smoke

  # full PCSP, 300 iter
  conda run -n paper python scripts/run_pcsp_v3.py --mode full

  # all ablations
  conda run -n paper python scripts/run_pcsp_v3.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi_v3 import MiniInzoiV3Env
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_BASE
from src.training.pcsp_trainer import PCSPConfig, train_pcsp

ALL_MODES = ["full", "no_consist", "no_diverse", "concat", "frozen_proj"]
DEFAULT_PERSONAS_V3 = "data/personas/personas_300_v3.json"
DEFAULT_OUTPUT_DIR  = "results/pcsp_v3"


def _v3_env_factory(personas):
    return MiniInzoiV3Env(personas=personas, max_steps=200)


def main():
    parser = argparse.ArgumentParser(description="Run PCSP v3 training / ablation")
    parser.add_argument("--mode", choices=ALL_MODES, default="full")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test: 20 iterations only")
    parser.add_argument("--all", action="store_true",
                        help="Run all modes sequentially (full + 4 ablations)")
    parser.add_argument("--n_iterations", type=int, default=None,
                        help="Override iteration count")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--personas_json", default=DEFAULT_PERSONAS_V3,
                        help=f"v3 personas file (default: {DEFAULT_PERSONAS_V3})")
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    n_iter = 20 if args.smoke else args.n_iterations
    modes  = ALL_MODES if args.all else [args.mode]

    summary: dict = {}
    t_total = time.time()

    for mode in modes:
        print(f"\n{'='*60}")
        print(f"  Mode: {mode}  |  iterations: {n_iter or 300}  |  v3 (obs={OBS_DIM_V3_BASE}, n_actions={N_ACTIONS_V3})")
        print(f"{'='*60}")

        cfg = PCSPConfig()
        result = train_pcsp(
            mode=mode,
            personas_json=args.personas_json,
            config=cfg,
            device=args.device,
            output_dir=args.output_dir,
            n_iterations=n_iter,
            obs_dim=OBS_DIM_V3_BASE,
            n_actions=N_ACTIONS_V3,
            n_agents=4,
            env_factory=_v3_env_factory,
        )
        summary[mode] = result

    elapsed = time.time() - t_total

    print(f"\n{'='*60}")
    print("  PCSP v3 Summary")
    print(f"{'='*60}")
    for mode, res in summary.items():
        rew = res.get("mean_ep_reward", float("nan"))
        con = res.get("consistency_loss", float("nan"))
        div = res.get("diversity_loss", float("nan"))
        print(f"  {mode:<14} reward={rew:7.3f}  con={con:.4f}  div={div:.4f}")
    print(f"\n  Total elapsed: {elapsed:.1f}s")

    out = ROOT / args.output_dir / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"modes": summary, "elapsed_sec": elapsed,
                   "obs_dim": OBS_DIM_V3_BASE, "n_actions": N_ACTIONS_V3}, f, indent=2)
    print(f"  Summary saved: {out}")


if __name__ == "__main__":
    main()
