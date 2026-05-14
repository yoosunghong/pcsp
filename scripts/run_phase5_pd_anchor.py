"""Phase 5 §3 — second-substrate anchor: prisoners_dilemma_in_the_matrix__repeated.

PHASE5_REPORT §9.6 diagnosed the held-out retrieval failure as an
*action-prior overlap* problem in the (action, reward) GRU input on
`commons_harvest__open`: held-out personas' action priors duplicate train
personas' priors in a small movement-centric action ontology.

PD-in-the-matrix has the same nominal action vocabulary (8 discrete
actions) but with strategically distinct semantics: cooperate/defect
interactions overlay the movement primitives. If the §1 + §2 failure is
substrate-ontology-bound, held-out top-1 should move off 0 here. If the
failure is general (encoder + persona + InfoNCE specification),
PD will also collapse to 0.

The personas are *unchanged*: commons_harvest-tuned descriptions are used
as-is. This is a deliberately stricter test — held-out personas (
`fast_mover`, `spinner`) carry movement language that maps less cleanly to
PD strategic actions, so any non-zero held-out top-1 on PD is strong
evidence that the substrate's behavioural separability — not the
persona corpus — is the load-bearing variable.

Two seeds, 1 M env-steps, InfoNCE-only (`pool=full` to match the §1
baseline). Qwen3-Embedding-0.6B persona table.
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


CACHE_PATH = "results/embeddings/persona_emb_qwen_emb.pt"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--pool", choices=["full", "train"], default="full")
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    run_name = args.run_name or (
        f"phase5_pd_anchor_pool{args.pool}_seed{args.seed}_{args.total_env_steps // 1000}k"
    )

    argv = [
        "--substrate", "prisoners_dilemma_in_the_matrix__repeated",
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
        "--run-dir", "research/meltingpot/runs/phase5_pd_anchor",
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
