"""Phase 5 — embedding-source A/B sanity for the real Qwen3-Embedding-0.6B artifact.

Mirrors ``run_phase4_embedding_ab.py`` exactly (same budget, same loss
config, same trainer knobs) but swaps the cached cache path to the
``qwen_emb`` artifact built by ``scripts/build_persona_embeddings_qwen.py``.

The 60 k-step sanity exists to (1) confirm the 1024-d cached path is
end-to-end stable through the cleanrl-ppo trainer and (2) get a first
read on whether the embedding's richer cosine geometry already moves
the InfoNCE retrieval needle at small budgets. The headline 1 M-step
anchor is ``scripts/run_phase5_qwen_anchor.py``.

Conditions exposed here:

- ``random32``     : Phase 4 baseline, included so a single Phase 5 sweep
                     can re-emit the random reference without re-reading
                     the Phase 4 aggregate.
- ``qwen_emb``     : Qwen3-Embedding-0.6B, 1024-d, L2-normalised. The
                     headline arm.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.training.cleanrl_ppo.launch import main as launch_main


CONDITIONS = {
    "random32": {"source": "random", "dim": 32, "path": None},
    "qwen_emb": {"source": "cached", "dim": 1024, "path": "results/embeddings/persona_emb_qwen_emb.pt"},
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--condition", choices=list(CONDITIONS), required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=60_000)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    cond = CONDITIONS[args.condition]
    run_name = args.run_name or (
        f"phase5_qwen_ab_{args.condition}_seed{args.seed}_{args.total_env_steps // 1000}k"
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
        "--persona-source", cond["source"],
        "--persona-embedding-dim", str(cond["dim"]),
        "--persona-assignment", "random",
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "5",
        "--checkpoint-interval-updates", "100",
        "--infonce-coef", "0.5",
        "--kl-diversity-coef", "0.0",
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--run-name", run_name,
        "--run-dir", "research/meltingpot/runs/phase5_qwen_ab",
    ]
    if cond["path"] is not None:
        if not Path(cond["path"]).exists():
            raise SystemExit(
                f"Missing cache file {cond['path']}. "
                "Run scripts/build_persona_embeddings_qwen.py first."
            )
        argv += ["--persona-cache-path", cond["path"]]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
