"""Phase 5 §4 — persona-balanced InfoNCE mini-batches.

PHASE5_REPORT §10.6 confirmed that across three Phase 5 ablations
(embedding, contrast pool, substrate ontology) the full-vocab held-out
top-1 remains 0.000. PHASE5_REPORT §10.8 identified persona-balance in
the InfoNCE batch as the only remaining lever named back in
PHASE4_REPORT §10. PD §3 pool=train produced the first non-zero
held-out top-3 (0.219 ± 0.309) but PD's smaller batch (16 trajectories
vs commons_harvest's 56) destabilised in-distribution retrieval —
exactly the symptom an unbalanced contrast batch would produce.

This script enables ``--infonce-balanced-batch true`` so every InfoNCE
opt step resamples to a uniform persona distribution before forming the
contrastive loss. Trajectories from under-represented personas are
sampled with replacement; over-represented personas are subsampled.

Default ``--infonce-per-persona 0`` → auto = ceil(B / K_present), so
the balanced batch is roughly the same size as the rollout batch.

Runs (2 seeds each, 1M env-steps, InfoNCE-only, qwen_emb, pool=train):
- commons_harvest__open
- prisoners_dilemma_in_the_matrix__repeated
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


CACHE_PATH = "results/embeddings/persona_emb_qwen_emb.pt"

SUBSTRATES = {
    "cH": "commons_harvest__open",
    "PD": "prisoners_dilemma_in_the_matrix__repeated",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--substrate", choices=list(SUBSTRATES), required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--pool", choices=["full", "train"], default="train")
    p.add_argument("--per-persona", type=int, default=0)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    sub_name = SUBSTRATES[args.substrate]
    run_name = args.run_name or (
        f"phase5_balanced_{args.substrate}_pool{args.pool}_seed{args.seed}_{args.total_env_steps // 1000}k"
    )

    argv = [
        "--substrate", sub_name,
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
        "--infonce-balanced-batch", "true",
        "--infonce-per-persona", str(args.per_persona),
        "--run-name", run_name,
        "--run-dir", "research/meltingpot/runs/phase5_balanced",
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
