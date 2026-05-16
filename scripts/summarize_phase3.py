"""Summarize Phase 3 trajectory-consistency runs (3 seeds × 3 modes).

Aggregates final-update metrics from ``logs.jsonl`` and the latest
``persona_diagnostics.json`` for every run dir, computes per-mode mean ±
std across seeds, and prints a compact table.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as stats
from pathlib import Path


def load_run(run_dir: Path) -> dict:
    cfg = json.loads((run_dir / "config.json").read_text())
    logs = [json.loads(l) for l in (run_dir / "logs.jsonl").read_text().splitlines() if l.strip()]
    last = logs[-1]
    diag = None
    diag_path = run_dir / "persona_diagnostics.json"
    if diag_path.exists():
        diag = json.loads(diag_path.read_text())
    return {"cfg": cfg, "last": last, "diag": diag, "logs": logs}


def mode_of(cfg: dict) -> str:
    if cfg.get("infonce_coef", 0) > 0 and cfg.get("kl_diversity_coef", 0) > 0:
        return "full"
    if cfg.get("infonce_coef", 0) > 0:
        return "infonce"
    if cfg.get("kl_diversity_coef", 0) > 0:
        return "kl_div"
    return "baseline"


def fmt_mean_std(vs: list[float]) -> str:
    if not vs:
        return "—"
    if len(vs) == 1:
        return f"{vs[0]:.4g}"
    return f"{stats.mean(vs):.4g} ± {stats.stdev(vs):.3g}"


def collect(metric_path: str, runs: list[dict]) -> list[float]:
    out = []
    for r in runs:
        cur: object = r
        try:
            for k in metric_path.split("."):
                cur = cur[k]
            if isinstance(cur, (int, float)) and not math.isnan(cur):
                out.append(float(cur))
        except (KeyError, TypeError):
            pass
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dirs", nargs="+")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    runs = [load_run(Path(d)) for d in args.run_dirs]
    by_mode: dict[str, list[dict]] = {}
    for r in runs:
        by_mode.setdefault(mode_of(r["cfg"]), []).append(r)

    METRICS = [
        ("episode_return_mean",     "last.env/episode_return_mean"),
        ("entropy",                 "last.loss/entropy"),
        ("approx_kl",               "last.loss/approx_kl"),
        ("explained_var",           "last.loss/explained_var"),
        ("sps_final",               "last.rollout/sps"),
        ("infonce_loss_final",      "last.loss/infonce"),
        ("infonce_top1_final",      "last.persona/infonce_top1"),
        ("infonce_top3_final",      "last.persona/infonce_top3"),
        ("kl_diversity_final",      "last.loss/kl_diversity"),
        ("mean_pairwise_action_kl", "diag.mean_pairwise_action_kl"),
        ("traj_retrieval_top1",     "diag.trajectory_retrieval.top1"),
        ("traj_retrieval_top3",     "diag.trajectory_retrieval.top3"),
        ("social.harvest_freq_spread",  "last.social/harvest_freq_spread"),
        ("social.aggression_spread",    "last.social/aggression_spread"),
        ("social.cooperation_spread",   "last.social/cooperation_ratio_spread"),
        ("social.stationarity_spread",  "last.social/stationarity_spread"),
        ("social.exploration_spread",   "last.social/exploration_spread"),
    ]

    out_table: dict[str, dict[str, str]] = {}
    out_raw: dict[str, dict[str, list[float]]] = {}
    for mode, rs in by_mode.items():
        row: dict[str, str] = {"n_seeds": str(len(rs))}
        raw: dict[str, list[float]] = {"n_seeds": [len(rs)]}
        for label, path in METRICS:
            vs = collect(path, rs)
            row[label] = fmt_mean_std(vs)
            raw[label] = vs
        out_table[mode] = row
        out_raw[mode] = raw

    if args.json:
        print(json.dumps({"summary": out_table, "raw": out_raw}, indent=2, default=str))
        return 0

    # Print as table.
    modes = list(out_table.keys())
    print("phase3 summary — mean ± std across seeds")
    header = ["metric"] + modes
    print(" | ".join(header))
    print("-+-".join(["-" * 30] + ["-" * 18 for _ in modes]))
    print(" | ".join([f"{'n_seeds':30}"] + [f"{out_table[m]['n_seeds']:18}" for m in modes]))
    for label, _ in METRICS:
        cells = [f"{out_table[m].get(label, '—'):18}" for m in modes]
        print(" | ".join([f"{label:30}"] + cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
