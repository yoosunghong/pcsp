"""Phase 4 — long-horizon 1M-step anchor runs on commons_harvest__open.

Mirrors ``run_phase3_smoke.py`` but at 1 M env-steps and writes runs
into ``research/meltingpot/runs/phase4_anchor/<mode>_seed<S>_1M``.

Loss configurations (same presets as Phase 3):

    baseline : PPO + persona conditioning, no consistency, no diversity.
    infonce  : PPO + InfoNCE trajectory-consistency.
    full     : PPO + InfoNCE + KL-diversity.
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


LOSS_PRESETS = {
    "baseline": {"infonce_coef": 0.0, "kl_diversity_coef": 0.0},
    "infonce":  {"infonce_coef": 0.5, "kl_diversity_coef": 0.0},
    "full":     {"infonce_coef": 0.5, "kl_diversity_coef": 0.05},
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=list(LOSS_PRESETS), required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--conditioning", default="concat", choices=["concat", "film", "none"])
    p.add_argument("--persona-source", default="random", choices=["random", "cached"])
    p.add_argument("--persona-cache-path", default=None)
    p.add_argument("--persona-embedding-dim", type=int, default=32)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    preset = LOSS_PRESETS[args.mode]
    run_name = args.run_name or (
        f"phase4_anchor_{args.mode}_seed{args.seed}_{args.total_env_steps // 1000}k"
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
        "--persona-embedding-dim", str(args.persona_embedding_dim),
        "--persona-source", args.persona_source,
        "--persona-assignment", "random",
        "--persona-split", "train",       # leakage prevention: train pool only
        "--persona-diagnostics-interval-updates", "25",
        "--checkpoint-interval-updates", "200",
        "--infonce-coef", str(preset["infonce_coef"]),
        "--kl-diversity-coef", str(preset["kl_diversity_coef"]),
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--run-name", run_name,
        "--run-dir", "research/meltingpot/runs/phase4_anchor",
    ]
    if args.persona_cache_path is not None:
        argv += ["--persona-cache-path", args.persona_cache_path]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
