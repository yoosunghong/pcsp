"""PCSP v3-large training entry — 12x12 / 16-agent variant.

Mirrors scripts/run_pcsp_v3.py but threads MiniInzoiV3LargeEnv +
OBS_DIM_V3_LARGE through the shared train_pcsp hooks. Uses the 500-persona
v3 file (or train_400_v3.json for held-out evaluation) and the precomputed
500-persona Qwen3 embeddings under results/embeddings/.

Usage examples:
  # smoke (20 iter, full mode)
  conda run -n paper python scripts/run_pcsp_v3_large.py --smoke
  # full PCSP, 300 iter, seed 42
  conda run -n paper python scripts/run_pcsp_v3_large.py --mode full --seed 42
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

from src.env.mini_inzoi_v3_large import MiniInzoiV3LargeEnv, N_AGENTS as N_AGENTS_LARGE
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_LARGE
from src.training.pcsp_trainer import PCSPConfig, train_pcsp

ALL_MODES = ["full", "no_consist", "no_diverse", "concat", "frozen_proj"]
DEFAULT_PERSONAS_V3L = "data/personas/train_400_v3.json"
DEFAULT_EMBED_NPY    = "../results/embeddings/persona_embeddings_500.npy"
DEFAULT_OUTPUT_DIR   = "results/pcsp_v3_large"


def _v3_large_env_factory(personas):
    return MiniInzoiV3LargeEnv(personas=personas, max_steps=200)


def main():
    parser = argparse.ArgumentParser(description="Run PCSP v3-large training / ablation")
    parser.add_argument("--mode", choices=ALL_MODES, default="full")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test: 20 iterations only")
    parser.add_argument("--all", action="store_true",
                        help="Run all modes sequentially")
    parser.add_argument("--n_iterations", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--personas_json", default=DEFAULT_PERSONAS_V3L)
    parser.add_argument("--embed_npy", default=DEFAULT_EMBED_NPY)
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    n_iter = 20 if args.smoke else args.n_iterations
    modes  = ALL_MODES if args.all else [args.mode]

    summary: dict = {}
    t_total = time.time()
    for mode in modes:
        print(f"\n{'='*60}")
        print(f"  Mode: {mode}  |  iters: {n_iter or 300}  |  seed: {args.seed}  "
              f"|  v3-large (obs={OBS_DIM_V3_LARGE}, n_act={N_ACTIONS_V3}, n_ag={N_AGENTS_LARGE})")
        print(f"{'='*60}")
        cfg = PCSPConfig()
        cfg.seed = args.seed
        result = train_pcsp(
            mode=mode,
            personas_json=args.personas_json,
            embed_npy=args.embed_npy,
            config=cfg,
            device=args.device,
            output_dir=f"{args.output_dir}/{mode}_seed{args.seed}",
            n_iterations=n_iter,
            obs_dim=OBS_DIM_V3_LARGE,
            n_actions=N_ACTIONS_V3,
            n_agents=N_AGENTS_LARGE,
            env_factory=_v3_large_env_factory,
        )
        summary[mode] = result

    elapsed = time.time() - t_total
    print(f"\n[v3-large] sweep done in {elapsed/60:.1f} min")
    out = Path(args.output_dir) / f"summary_seed{args.seed}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(f"summary → {out}")


if __name__ == "__main__":
    main()
