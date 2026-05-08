"""
PCSP v3 full Phase C sweep — runs the spec from PLAN.md:179.

  PCSP variants (4):  full, no_consist, no_diverse, concat
  Baselines     (2):  B1 (no-persona PPO), B3 (SBERT)

  frozen_proj is intentionally skipped (lowest-priority ablation).

All runs use:
  obs_dim = 33,  n_actions = 20
  personas_json = data/personas/personas_300_v3.json
  env_factory   = MiniInzoiV3Env(personas, max_steps=200)
  n_iterations  = PCSPConfig().total_iterations  (300 by default)

Per-mode results land under:
  results/pcsp_v3/{full,no_consist,no_diverse,concat}/
  results/baselines_v3/{b1_no_persona,b3_sbert}/

Usage:
  conda run -n paper python scripts/run_full_sweep_v3.py
  conda run -n paper python scripts/run_full_sweep_v3.py --dry_run    # print plan and exit
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi_v3 import MiniInzoiV3Env
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_BASE
from src.training.pcsp_trainer import PCSPConfig, train_pcsp
from src.training.baselines.no_persona_ppo import train_b1
from src.training.baselines.sbert_policy import train_b3

PCSP_MODES = ["full", "no_consist", "no_diverse", "concat"]
DEFAULT_PERSONAS_V3 = "data/personas/personas_300_v3.json"
DEFAULT_PCSP_OUT = "results/pcsp_v3"
DEFAULT_BASELINE_OUT = "results/baselines_v3"
ALL_RUNS = (
    [("pcsp", m) for m in PCSP_MODES] + [("baseline", "b1"), ("baseline", "b3")]
)


def _v3_env_factory(personas):
    return MiniInzoiV3Env(personas=personas, max_steps=200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry_run", action="store_true",
                        help="Print run plan and exit without training")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--personas_json", default=DEFAULT_PERSONAS_V3,
                        help="v3 personas JSON. Use train_240_v3.json for zero-shot retrain.")
    parser.add_argument("--pcsp_out", default=DEFAULT_PCSP_OUT,
                        help="Output dir for PCSP modes (per-mode subdirs created).")
    parser.add_argument("--baseline_out", default=DEFAULT_BASELINE_OUT,
                        help="Output dir for B1/B3 (per-baseline subdirs created).")
    parser.add_argument("--include", nargs="+", default=None,
                        help="Subset of runs to execute, e.g. "
                             "'pcsp:no_consist pcsp:no_diverse pcsp:concat baseline:b1 baseline:b3'. "
                             "Default: all 6.")
    args = parser.parse_args()

    if args.include:
        wanted = {tuple(s.split(":", 1)) for s in args.include}
        plan = [r for r in ALL_RUNS if r in wanted]
        if not plan:
            raise SystemExit(f"--include {args.include} matched no runs from {ALL_RUNS}")
    else:
        plan = list(ALL_RUNS)

    print("\n" + "=" * 60)
    print("  PCSP v3 Full Phase C Sweep")
    print("=" * 60)
    print(f"  obs_dim={OBS_DIM_V3_BASE}  n_actions={N_ACTIONS_V3}")
    print(f"  personas={args.personas_json}")
    print(f"  pcsp_out={args.pcsp_out}")
    print(f"  baseline_out={args.baseline_out}")
    print(f"  iterations=PCSPConfig.total_iterations (300)")
    print(f"  runs ({len(plan)}):")
    for kind, name in plan:
        print(f"    - {kind:<8} {name}")
    print("=" * 60)

    if args.dry_run:
        return

    summary: dict = {}
    t_total = time.time()

    for kind, name in plan:
        print(f"\n>>> [{kind}] {name}  starting ...")
        t0 = time.time()
        if kind == "pcsp":
            res = train_pcsp(
                mode=name,
                personas_json=args.personas_json,
                config=PCSPConfig(),
                device=args.device,
                output_dir=args.pcsp_out,
                n_iterations=None,
                obs_dim=OBS_DIM_V3_BASE,
                n_actions=N_ACTIONS_V3,
                n_agents=4,
                env_factory=_v3_env_factory,
            )
            summary[f"pcsp_{name}"] = res
        elif kind == "baseline" and name == "b1":
            res = train_b1(
                personas_json=args.personas_json,
                device=args.device,
                output_dir=f"{args.baseline_out}/b1_no_persona",
                obs_dim=OBS_DIM_V3_BASE,
                n_actions=N_ACTIONS_V3,
                n_agents=4,
                env_factory=_v3_env_factory,
            )
            summary["b1_no_persona"] = res
        elif kind == "baseline" and name == "b3":
            res = train_b3(
                personas_json=args.personas_json,
                device=args.device,
                output_dir=f"{args.baseline_out}/b3_sbert",
                obs_dim=OBS_DIM_V3_BASE,
                n_actions=N_ACTIONS_V3,
                n_agents=4,
                env_factory=_v3_env_factory,
            )
            summary["b3_sbert"] = res
        elapsed = time.time() - t0
        print(f"<<< [{kind}] {name}  done in {elapsed:.1f}s")

    total = time.time() - t_total
    print("\n" + "=" * 60)
    print("  Sweep summary")
    print("=" * 60)
    for k, res in summary.items():
        rew = res.get("mean_ep_reward", float("nan"))
        print(f"  {k:<24} reward={rew:7.3f}")
    print(f"\n  Total elapsed: {total:.1f}s ({total/3600:.2f}h)")

    out = ROOT / args.pcsp_out / "sweep_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"runs": summary, "elapsed_sec": total,
                   "obs_dim": OBS_DIM_V3_BASE, "n_actions": N_ACTIONS_V3},
                  f, indent=2)
    print(f"  Saved: {out}")


if __name__ == "__main__":
    main()
