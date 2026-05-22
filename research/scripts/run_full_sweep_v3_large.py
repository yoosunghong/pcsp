"""PCSP v3-large full sweep — 4 PCSP modes + B1 + B3, across multiple seeds.

Per spec from REVISE_PLAN.md T2.4: v3 20-action ontology at v2 scale
(12x12, 16 agents, 500 personas) — train_400_v3.json for training,
test_100_v3.json reserved for zero-shot eval.

Per-mode results land under:
  results/pcsp_v3_large/{full,no_consist,no_diverse,concat}_seed{S}/
  results/baselines_v3_large/{b1_no_persona,b3_sbert}_seed{S}/
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
from src.training.baselines.no_persona_ppo import train_b1, PPOConfig as B1Config
from src.training.baselines.sbert_policy import train_b3

PCSP_MODES = ["full", "no_consist", "no_diverse", "concat"]
DEFAULT_PERSONAS_V3L = "data/personas/train_400_v3.json"
DEFAULT_EMBED_NPY = "../results/embeddings/persona_embeddings_500.npy"
DEFAULT_PCSP_OUT = "results/pcsp_v3_large"
DEFAULT_BASELINE_OUT = "results/baselines_v3_large"


def _v3l_env_factory(personas):
    return MiniInzoiV3LargeEnv(personas=personas, max_steps=200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44],
                        help="Seeds (default: 42 43 44)")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--include", nargs="+", default=None,
                        help="Subset of runs, e.g. 'pcsp:full pcsp:no_consist'. "
                             "Choices: pcsp:{full,no_consist,no_diverse,concat}, baseline:{b1,b3}.")
    parser.add_argument("--n_iterations", type=int, default=None,
                        help="Override iterations (default 300 from PCSPConfig).")
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    all_runs = [("pcsp", m) for m in PCSP_MODES] + [("baseline", "b1"), ("baseline", "b3")]
    if args.include:
        wanted = {tuple(s.split(":", 1)) for s in args.include}
        plan = [r for r in all_runs if r in wanted]
        if not plan:
            raise SystemExit(f"--include matched no runs from {all_runs}")
    else:
        plan = list(all_runs)

    print("\n" + "=" * 64)
    print("  PCSP v3-LARGE Full Sweep (12x12, 16 agents, 400 train personas)")
    print(f"  seeds: {args.seeds}  |  plan: {len(plan)} kinds x {len(args.seeds)} seeds "
          f"= {len(plan) * len(args.seeds)} runs")
    print("=" * 64)
    for kind, mode in plan:
        print(f"   {kind}:{mode}")
    if args.dry_run:
        return

    summary: dict = {}
    t_total = time.time()
    run_idx = 0
    total_runs = len(plan) * len(args.seeds)

    for seed in args.seeds:
        for kind, mode in plan:
            run_idx += 1
            tag = f"{kind}:{mode}@{seed}"
            print(f"\n{'─' * 64}\n[{run_idx}/{total_runs}] {tag}\n{'─' * 64}")
            t0 = time.time()

            if kind == "pcsp":
                cfg = PCSPConfig()
                cfg.seed = seed
                result = train_pcsp(
                    mode=mode,
                    personas_json=DEFAULT_PERSONAS_V3L,
                    embed_npy=DEFAULT_EMBED_NPY,
                    config=cfg,
                    device=args.device,
                    output_dir=f"{DEFAULT_PCSP_OUT}/{mode}_seed{seed}",
                    n_iterations=args.n_iterations,
                    obs_dim=OBS_DIM_V3_LARGE,
                    n_actions=N_ACTIONS_V3,
                    n_agents=N_AGENTS_LARGE,
                    env_factory=_v3l_env_factory,
                )
            elif kind == "baseline" and mode == "b1":
                cfg = B1Config()
                cfg.seed = seed
                result = train_b1(
                    personas_json=DEFAULT_PERSONAS_V3L,
                    config=cfg,
                    device=args.device,
                    output_dir=f"{DEFAULT_BASELINE_OUT}/b1_no_persona_seed{seed}",
                    n_iterations=args.n_iterations,
                    obs_dim=OBS_DIM_V3_LARGE,
                    n_actions=N_ACTIONS_V3,
                    n_agents=N_AGENTS_LARGE,
                    env_factory=_v3l_env_factory,
                )
            elif kind == "baseline" and mode == "b3":
                # train_b3 follows the same signature pattern as train_b1
                # (see scripts/run_full_sweep_v3.py).
                cfg = PCSPConfig()
                cfg.seed = seed
                result = train_b3(
                    personas_json=DEFAULT_PERSONAS_V3L,
                    config=cfg,
                    device=args.device,
                    output_dir=f"{DEFAULT_BASELINE_OUT}/b3_sbert_seed{seed}",
                    n_iterations=args.n_iterations,
                    obs_dim=OBS_DIM_V3_LARGE,
                    n_actions=N_ACTIONS_V3,
                    n_agents=N_AGENTS_LARGE,
                    env_factory=_v3l_env_factory,
                )
            else:
                raise SystemExit(f"unknown run: {kind}:{mode}")

            summary[tag] = result
            print(f"[{tag}] elapsed {(time.time() - t0)/60:.1f} min")

    total_min = (time.time() - t_total) / 60
    print(f"\n[v3-large sweep] all {total_runs} runs done in {total_min:.1f} min")

    out = Path(DEFAULT_PCSP_OUT) / "sweep_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(f"summary → {out}")


if __name__ == "__main__":
    main()
