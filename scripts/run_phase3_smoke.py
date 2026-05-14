"""Phase 3 trajectory-consistency smoke runs on commons_harvest__open.

Three loss configurations × N seeds. Default budget: 150 k env-steps.

Loss configurations:
    baseline  : PPO with persona conditioning, no consistency, no diversity.
    infonce   : PPO + InfoNCE trajectory-consistency.
    full      : PPO + InfoNCE + KL-diversity.

A fourth combo (PPO + KL-diversity only) is available via
``--mode kl_div``; the spec required 3 combos in the experiment table
but the trainer supports all four loss families.
"""

from __future__ import annotations

import argparse
import sys

from src.training.cleanrl_ppo.launch import main as launch_main


LOSS_PRESETS = {
    "baseline": {"infonce_coef": 0.0, "kl_diversity_coef": 0.0},
    "infonce":  {"infonce_coef": 0.5, "kl_diversity_coef": 0.0},
    "kl_div":   {"infonce_coef": 0.0, "kl_diversity_coef": 0.05},
    "full":     {"infonce_coef": 0.5, "kl_diversity_coef": 0.05},
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=list(LOSS_PRESETS), required=True)
    p.add_argument("--total-env-steps", type=int, default=150_000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--conditioning", default="concat", choices=["concat", "film", "none"])
    p.add_argument("--assignment", default="random", choices=["fixed", "random", "population"])
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    preset = LOSS_PRESETS[args.mode]
    run_name = args.run_name or (
        f"phase3_{args.mode}_{args.conditioning}_seed{args.seed}_{args.total_env_steps // 1000}k"
    )

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
        "--persona-conditioning", args.conditioning,
        "--persona-embedding-dim", "32",
        "--persona-source", "random",
        "--persona-assignment", args.assignment,
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "5",
        "--checkpoint-interval-updates", "200",
        "--infonce-coef", str(preset["infonce_coef"]),
        "--kl-diversity-coef", str(preset["kl_diversity_coef"]),
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--run-name", run_name,
    ] + extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
