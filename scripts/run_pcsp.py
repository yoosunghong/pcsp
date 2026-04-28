"""
PCSP 학습 실행 스크립트 — Phase 4

Usage:
  # smoke test (20 iter, 모든 mode)
  conda run -n paper python scripts/run_pcsp.py --smoke

  # 특정 mode smoke test
  conda run -n paper python scripts/run_pcsp.py --smoke --mode full

  # 전체 학습 (300 iter)
  conda run -n paper python scripts/run_pcsp.py --mode full
  conda run -n paper python scripts/run_pcsp.py --mode no_consist
  conda run -n paper python scripts/run_pcsp.py --mode no_diverse
  conda run -n paper python scripts/run_pcsp.py --mode concat
  conda run -n paper python scripts/run_pcsp.py --mode frozen_proj

  # 전체 ablation 일괄 실행
  conda run -n paper python scripts/run_pcsp.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.training.pcsp_trainer import PCSPConfig, train_pcsp

ALL_MODES = ["full", "no_consist", "no_diverse", "concat", "frozen_proj"]


def main():
    parser = argparse.ArgumentParser(description="Run PCSP training / ablation")
    parser.add_argument(
        "--mode", choices=ALL_MODES, default="full",
        help="Training mode (default: full)"
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Smoke test: 20 iterations only"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all modes sequentially (full + 4 ablations)"
    )
    parser.add_argument(
        "--n_iterations", type=int, default=None,
        help="Override iteration count"
    )
    parser.add_argument(
        "--device", default="cuda",
        help="Compute device (default: cuda)"
    )
    args = parser.parse_args()

    n_iter = 20 if args.smoke else args.n_iterations

    modes = ALL_MODES if args.all else [args.mode]

    summary = {}
    t_total = time.time()

    for mode in modes:
        print(f"\n{'='*60}")
        print(f"  Mode: {mode}  |  iterations: {n_iter or 300}")
        print(f"{'='*60}")

        cfg = PCSPConfig()
        result = train_pcsp(
            mode=mode,
            config=cfg,
            device=args.device,
            n_iterations=n_iter,
        )
        summary[mode] = result

    elapsed = time.time() - t_total

    print(f"\n{'='*60}")
    print("  PCSP Summary")
    print(f"{'='*60}")
    for mode, res in summary.items():
        rew = res.get("mean_ep_reward", float("nan"))
        con = res.get("consistency_loss", float("nan"))
        div = res.get("diversity_loss", float("nan"))
        print(f"  {mode:<14} reward={rew:7.3f}  con={con:.4f}  div={div:.4f}")
    print(f"\n  Total elapsed: {elapsed:.1f}s")

    # Save aggregated summary
    root = Path(__file__).resolve().parents[1]
    out  = root / "results/pcsp/summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"modes": summary, "elapsed_sec": elapsed}, f, indent=2)
    print(f"  Summary saved: {out}")


if __name__ == "__main__":
    main()
