"""Phase 5 §5.4 — H5 reward-identity Pareto sweep.

Sweeps the InfoNCE coefficient (lambda) on cH and stag at 1 M env-steps.
Reports per-run (episode_return, identification_top1) — fed into the Pareto
analysis in PHASE5_REPORT §13.

Configuration is matched to ``run_phase5_qwen_anchor.py`` / ``run_phase5_stag_anchor.py``
on every knob except ``--infonce-coef``.

Lambda=0 is the no-consistency ablation arm (PPO + persona conditioning,
no InfoNCE). Non-zero values trace the frontier.
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


CACHE_PATH = "results/embeddings/persona_emb_qwen_emb.pt"

SUBSTRATE_DIR = {
    "commons_harvest__open": "research/meltingpot/runs/phase5_h5_pareto_cH",
    "stag_hunt_in_the_matrix__repeated": "research/meltingpot/runs/phase5_h5_pareto_stag",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--substrate", required=True, choices=list(SUBSTRATE_DIR))
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--infonce-coef", type=float, required=True)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    sub_short = "cH" if args.substrate.startswith("commons") else "stag"
    coef_tag = f"l{args.infonce_coef:g}".replace(".", "p")
    run_name = args.run_name or (
        f"phase5_h5_{sub_short}_{coef_tag}_seed{args.seed}_{args.total_env_steps // 1000}k"
    )

    argv = [
        "--substrate", args.substrate,
        "--num-envs", "8",
        "--num-steps", "128",
        "--num-minibatches", "4",
        "--update-epochs", "4",
        "--total-env-steps", str(args.total_env_steps),
        "--learning-rate", "2.5e-4",
        "--ent-coef", "0.01",
        "--seed", str(args.seed),
        "--persona-conditioning", "concat",
        "--persona-source", "cached",
        "--persona-cache-path", CACHE_PATH,
        "--persona-embedding-dim", "1024",
        "--persona-assignment", "random",
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "25",
        "--checkpoint-interval-updates", "200",
        "--infonce-coef", str(args.infonce_coef),
        "--kl-diversity-coef", "0.0",
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--infonce-candidate-pool", "full",
        "--run-name", run_name,
        "--run-dir", SUBSTRATE_DIR[args.substrate],
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
