"""Phase 5 — 1 M-step anchor runs with Qwen3-Embedding-0.6B persona embeddings.

This is the headline experiment of Phase 5 §1: re-run the Phase 4 anchor
protocol with the random32 embedding source replaced by the real-LLM
``qwen_emb`` artifact. All other knobs (substrate, loss presets, vec env
shape, seed budget, diagnostics cadence, checkpointing) are matched to
``scripts/run_phase4_anchor.py`` so the comparison is on the embedding
source alone.

Loss configurations match Phase 4:

    baseline : PPO + persona conditioning, no consistency, no diversity.
    infonce  : PPO + InfoNCE trajectory-consistency.
    full     : PPO + InfoNCE + KL-diversity.

Phase 4 §9 reported the central failure: random32 yielded held-out top-1
retrieval of 0.000 ± 0.000 (full 12-vocab) and ~0 Spearman ρ between
embedding cosine and behaviour KL. The qwen_emb arm tests whether those
numbers move when the persona table carries semantic structure.
"""

from __future__ import annotations

import argparse

from src.training.cleanrl_ppo.launch import main as launch_main


LOSS_PRESETS = {
    "baseline": {"infonce_coef": 0.0, "kl_diversity_coef": 0.0},
    "infonce":  {"infonce_coef": 0.5, "kl_diversity_coef": 0.0},
    "full":     {"infonce_coef": 0.5, "kl_diversity_coef": 0.05},
}

CACHE_PATH = "results/embeddings/persona_emb_qwen_emb.pt"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=list(LOSS_PRESETS), required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=1_000_000)
    p.add_argument("--run-name", default=None)
    args, extra = p.parse_known_args()

    preset = LOSS_PRESETS[args.mode]
    run_name = args.run_name or (
        f"phase5_qwen_anchor_{args.mode}_seed{args.seed}_{args.total_env_steps // 1000}k"
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
        "--persona-embedding-dim", "1024",  # informational only for cached
        "--persona-assignment", "random",
        "--persona-split", "train",
        "--persona-diagnostics-interval-updates", "25",
        "--checkpoint-interval-updates", "200",
        "--infonce-coef", str(preset["infonce_coef"]),
        "--kl-diversity-coef", str(preset["kl_diversity_coef"]),
        "--infonce-traj-dim", "64",
        "--infonce-traj-hidden", "128",
        "--infonce-temperature", "0.1",
        "--run-name", run_name,
        "--run-dir", "research/meltingpot/runs/phase5_qwen_anchor",
    ]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
