"""Phase 4 — OOD evaluation runner.

Loads a trained PCSP checkpoint and runs four eval passes:

    1. train-random         — in-distribution sanity check.
    2. heldout-random       — zero-shot OOD on the held-out personas.
    3. mixed-population     — population template with half train,
                              half held-out.
    4. heldout-population   — population template with only held-out.

Each pass writes a JSON to ``<run_dir>/ood_evals/`` and the script
prints a compact summary table at the end. The evaluator never touches
the optimizer / training state — checkpoints are loaded read-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.eval import OODEvalConfig, run_ood_eval


PASSES = [
    {"split": "train",   "assignment": "random",     "kind": None},
    {"split": "heldout", "assignment": "random",     "kind": None},
    {"split": "all",     "assignment": "population", "kind": "mixed"},
    {"split": "all",     "assignment": "population", "kind": "heldout_only"},
]


def _latest_ckpt(run_dir: Path) -> Path:
    ckpts = sorted((run_dir / "checkpoints").glob("ckpt_*.pt"))
    if not ckpts:
        raise FileNotFoundError(f"No checkpoints in {run_dir}/checkpoints")
    return ckpts[-1]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dirs", nargs="+")
    p.add_argument("--eval-steps", type=int, default=1024)
    p.add_argument("--num-envs", type=int, default=8)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--device", default="auto")
    args = p.parse_args()

    rows = []
    for run_str in args.run_dirs:
        run_dir = Path(run_str)
        ckpt = _latest_ckpt(run_dir)
        for pass_cfg in PASSES:
            ev = OODEvalConfig(
                checkpoint_path=str(ckpt),
                eval_split=pass_cfg["split"],
                eval_assignment=pass_cfg["assignment"],
                eval_population_kind=pass_cfg["kind"],
                eval_steps=args.eval_steps,
                num_envs=args.num_envs,
                seed=args.seed,
                device=args.device,
            )
            result = run_ood_eval(ev)
            retr = result.get("retrieval", {}) or {}
            beh = result.get("behavior", {}) or {}
            corr = result.get("correlation", {}) or {}
            nn = result.get("nearest_neighbours", {}) or {}
            rows.append({
                "run": run_dir.name,
                "pass": f"{pass_cfg['split']}/{pass_cfg['assignment']}/{pass_cfg['kind']}",
                "full_top1": retr.get("full", {}).get("top1"),
                "full_top3": retr.get("full", {}).get("top3"),
                "train_top1": retr.get("train_only", {}).get("top1"),
                "heldout_top1": retr.get("heldout_only", {}).get("top1"),
                "mean_pair_kl": beh.get("mean_pairwise_action_kl"),
                "train_vs_heldout_kl": beh.get("train_vs_heldout_action_kl"),
                "rho_emb_vs_kl": corr.get("embed_distance_vs_action_kl_spearman_rho"),
                "nn_right_split_frac": nn.get("mean_right_split_frac"),
                "out": result.get("_output_path"),
            })

    print(json.dumps(rows, indent=2, default=str))
    # Also write a CSV-like summary next to each run.
    for run_str in args.run_dirs:
        run_dir = Path(run_str)
        out_path = run_dir / "ood_evals" / "summary.json"
        sub = [r for r in rows if r["run"] == run_dir.name]
        out_path.write_text(json.dumps(sub, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
