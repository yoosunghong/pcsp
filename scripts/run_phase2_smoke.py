"""Phase 2 persona-conditioning smoke runs.

Launches one PPO run per conditioning mode (none, concat, film) on
commons_harvest__open with deterministic-random persona embeddings and
random per-episode persona assignment. The smaller per-mode budget is
documented in PHASE2_REPORT.md; rerun with ``--total-env-steps 1000000``
to get a 1M run for the best-stabilized mode.
"""

from __future__ import annotations

import argparse
import sys

from src.training.cleanrl_ppo.launch import main as launch_main


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["none", "concat", "film"], required=True)
    p.add_argument("--total-env-steps", type=int, default=150_000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--assignment", default="random",
                   choices=["fixed", "random", "population"])
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    run_name = args.run_name or f"phase2_{args.mode}_smoke_{args.total_env_steps // 1000}k"

    argv = [
        "--substrate", "commons_harvest__open",
        "--num-envs", "8",
        "--num-steps", "128",
        "--num-minibatches", "4",
        "--update-epochs", "4",
        "--total-env-steps", str(args.total_env_steps),
        "--learning-rate", "2.5e-4",
        "--ent-coef", "0.01",
        "--seed", str(args.seed),
        "--persona-conditioning", args.mode,
        "--persona-embedding-dim", "32",
        "--persona-source", "random",
        "--persona-assignment", args.assignment,
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "10",
        "--checkpoint-interval-updates", "200",
        "--run-name", run_name,
    ] + extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
