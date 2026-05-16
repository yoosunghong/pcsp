"""Phase 1 closeout smoke test: 1M-step PPO run on commons_harvest__open.

Thin wrapper around ``src.training.cleanrl_ppo.launch`` that pins the smoke
config and prints a final summary line for the Phase 1 report.
"""

from __future__ import annotations

import sys

from src.training.cleanrl_ppo.launch import main as launch_main


def main() -> int:
    args = [
        "--substrate", "commons_harvest__open",
        "--num-envs", "8",
        "--num-steps", "128",
        "--num-minibatches", "4",
        "--update-epochs", "4",
        "--total-env-steps", "1000000",
        "--learning-rate", "2.5e-4",
        "--ent-coef", "0.01",
        "--seed", "1",
    ] + sys.argv[1:]
    return launch_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
