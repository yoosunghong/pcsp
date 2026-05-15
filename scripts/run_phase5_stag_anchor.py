"""Phase 5 §5.2 — third-substrate anchor: stag_hunt_in_the_matrix__repeated.

PHASE5_REPORT §12.9 names third-substrate H1 confirmation as the highest-leverage
remaining experiment: closing MELTINGPOT_PROPOSAL §6's "H1 holds on >=3 substrates
with separated CIs" criterion. cH (CPR) and PD (mixed-motive matrix) are already
confirmed; stag_hunt adds a coordination/risk-vs-payoff axis from category B.

Single-seed Phase 5 §1 anchor configuration: qwen_emb persona table,
``pool=full`` (default), balanced=False (default), InfoNCE-only. Matched to
``run_phase5_pd_anchor.py`` so cross-substrate comparison is on the substrate
alone.
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
        f"phase5_stag_anchor_pool{args.pool}_seed{args.seed}_{args.total_env_steps // 1000}k"
    )

    argv = [
        "--substrate", "stag_hunt_in_the_matrix__repeated",
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
        "--run-dir", "research/meltingpot/runs/phase5_stag_anchor",
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
