"""Phase 5 §2 — InfoNCE contrast-pool intervention with Qwen embeddings.

PHASE5_REPORT §5 identified the trained head's failure mode as a
*candidate-pool* problem rather than an embedding problem: held-out slots
appear only as negatives during training, so the head learns "no observed
trajectory belongs in a held-out slot" — a signal that is robust to the
embedding source.

This script runs the contrast-pool intervention. With
``--pool train`` the trainer restricts the InfoNCE candidate set to the
``persona_split`` indices, so held-out slots receive zero gradient signal
during training and the head's test-time behaviour on held-out candidates
is governed entirely by embedding geometry.

Two arms, both with the qwen_emb artifact:

- ``full``  : Phase 4/5 §1 baseline (full 12-vocab as candidate pool).
- ``train`` : Phase 5 §2 intervention (10-vocab train-only pool).

Two seeds, 1 M env-steps, InfoNCE-only (KL-diversity off — Phase 4 §4
showed the KL term destabilises the value function and is orthogonal to
this question).
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


CACHE_PATH = "results/embeddings/persona_emb_qwen_emb.pt"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pool", choices=["full", "train"], required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    run_name = args.run_name or (
        f"phase5_contrast_pool_{args.pool}_seed{args.seed}_{args.total_env_steps // 1000}k"
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
        "--persona-conditioning", "concat",
        "--persona-source", "cached",
        "--persona-cache-path", CACHE_PATH,
        "--persona-embedding-dim", "1024",
        "--persona-assignment", "random",
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "25",
        "--checkpoint-interval-updates", "200",
        "--infonce-coef", "0.5",
        "--kl-diversity-coef", "0.0",
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--infonce-candidate-pool", args.pool,
        "--run-name", run_name,
        "--run-dir", "research/meltingpot/runs/phase5_contrast_pool",
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
