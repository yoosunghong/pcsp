"""Phase 4 — embedding A/B sweep (random vs cached vs frozen-LLM-surrogate).

Runs short InfoNCE-on PPO jobs at 60 k env-steps for each embedding
source so the comparison is on a fixed budget. All other knobs are
matched to ``run_phase4_anchor.py`` so the A/B is genuinely about the
embedding source, not about LR/buffer/etc.

Embedding conditions:

- ``random32``   : default ``--persona-source random`` (32-d Gaussian, salt=0).
- ``charhash64`` : cached, character-3gram feature hash, 64-d.
- ``descbow128`` : cached, token feature hash with IDF dampening, 128-d.

Requires ``scripts/build_persona_embeddings.py`` to have produced the
``.pt`` cache files beforehand.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.training.cleanrl_ppo.launch import main as launch_main


CONDITIONS = {
    "random32":   {"source": "random", "dim": 32, "path": None},
    "charhash64": {"source": "cached", "dim": 64,  "path": "results/embeddings/persona_emb_charhash64.pt"},
    "descbow128": {"source": "cached", "dim": 128, "path": "results/embeddings/persona_emb_descbow128.pt"},
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
        f"phase4_emb_{args.condition}_seed{args.seed}_{args.total_env_steps // 1000}k"
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
        "--run-dir", "research/meltingpot/runs/phase4_emb_ab",
    ]
    if cond["path"] is not None:
        if not Path(cond["path"]).exists():
            raise SystemExit(
                f"Missing cache file {cond['path']}. Run scripts/build_persona_embeddings.py first."
            )
        argv += ["--persona-cache-path", cond["path"]]
    argv += extra
    return launch_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
