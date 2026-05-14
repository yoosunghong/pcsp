"""Aggregate Phase 4 OOD evaluations + 1M-anchor stability metrics.

Inputs: one or more run directories. The script picks up every JSON in
``<run>/ood_evals/`` (one per (split, assignment, kind) pass) and every
final entry of ``<run>/logs.jsonl`` (for training-time stability).

Output: a table written to stdout and to ``phase4_summary.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as stats
from pathlib import Path


def _last_log(run: Path) -> dict:
    lines = [
        json.loads(l) for l in (run / "logs.jsonl").read_text().splitlines() if l.strip()
    ]
    return lines[-1] if lines else {}


def _ood_passes(run: Path) -> list[dict]:
    out = []
    d = run / "ood_evals"
    if not d.exists():
        return out
    for f in sorted(d.glob("ood_eval__*.json")):
        out.append(json.loads(f.read_text()))
    return out


def _mode(cfg: dict) -> str:
    if cfg.get("infonce_coef", 0) > 0 and cfg.get("kl_diversity_coef", 0) > 0:
        return "full"
    if cfg.get("infonce_coef", 0) > 0:
        return "infonce"
    if cfg.get("kl_diversity_coef", 0) > 0:
        return "kl_div"
    return "baseline"


def fmt_ms(vs: list[float]) -> str:
    vs = [v for v in vs if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))]
    if not vs:
        return "—"
    if len(vs) == 1:
        return f"{vs[0]:.4g}"
    return f"{stats.mean(vs):.4g} ± {stats.stdev(vs):.3g}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dirs", nargs="+")
    p.add_argument("--out", default="phase4_summary.json")
    args = p.parse_args()

    by_mode: dict[str, list[dict]] = {}
    summaries = []
    for r in args.run_dirs:
        run = Path(r)
        if not (run / "config.json").exists():
            continue
        cfg = json.loads((run / "config.json").read_text())
        mode = _mode(cfg)
        last = _last_log(run)
        passes = _ood_passes(run)
        info = {
            "run": run.name,
            "mode": mode,
            "seed": cfg.get("seed"),
            "global_step": last.get("global_step"),
            "episode_return_mean": last.get("env/episode_return_mean"),
            "entropy": last.get("loss/entropy"),
            "approx_kl": last.get("loss/approx_kl"),
            "infonce_top1": last.get("persona/infonce_top1"),
            "traj_top1": last.get("persona/traj_retrieval_top1"),
            "mean_pair_kl": last.get("persona/mean_pairwise_action_kl"),
            "ood": [],
        }
        for pj in passes:
            cfg_p = pj.get("eval_cfg", {})
            retr = pj.get("retrieval", {}) or {}
            beh = pj.get("behavior", {}) or {}
            corr = pj.get("correlation", {}) or {}
            info["ood"].append({
                "tag": f"{cfg_p.get('eval_split')}/{cfg_p.get('eval_assignment')}/{cfg_p.get('eval_population_kind')}",
                "full_top1": retr.get("full", {}).get("top1"),
                "train_top1": retr.get("train_only", {}).get("top1"),
                "heldout_top1": retr.get("heldout_only", {}).get("top1"),
                "mean_pair_kl": beh.get("mean_pairwise_action_kl"),
                "train_vs_heldout_kl": beh.get("train_vs_heldout_action_kl"),
                "rho_emb_vs_kl": corr.get("embed_distance_vs_action_kl_spearman_rho"),
            })
        summaries.append(info)
        by_mode.setdefault(mode, []).append(info)

    # Cross-seed table.
    print("phase4 anchor summary — mean ± std across seeds")
    print(f"{'mode':10} | {'episode_return':18} | {'entropy':12} | {'traj_top1':12} | {'mean_pair_kl':14}")
    print("-" * 80)
    for mode, rs in by_mode.items():
        print(
            f"{mode:10} | "
            f"{fmt_ms([r.get('episode_return_mean') for r in rs]):18} | "
            f"{fmt_ms([r.get('entropy') for r in rs]):12} | "
            f"{fmt_ms([r.get('traj_top1') for r in rs]):12} | "
            f"{fmt_ms([r.get('mean_pair_kl') for r in rs]):14}"
        )

    # OOD aggregate per (mode, ood-pass-tag).
    print()
    print("phase4 OOD — mean ± std across seeds")
    print(f"{'mode':10} | {'pass':40} | {'full_top1':14} | {'heldout_top1':14} | {'tvh_kl':12}")
    print("-" * 100)
    for mode, rs in by_mode.items():
        # Collect by tag.
        tags: dict[str, list[dict]] = {}
        for r in rs:
            for p in r["ood"]:
                tags.setdefault(p["tag"], []).append(p)
        for tag, pl in tags.items():
            print(
                f"{mode:10} | {tag:40} | "
                f"{fmt_ms([p.get('full_top1') for p in pl]):14} | "
                f"{fmt_ms([p.get('heldout_top1') for p in pl]):14} | "
                f"{fmt_ms([p.get('train_vs_heldout_kl') for p in pl]):12}"
            )

    Path(args.out).write_text(json.dumps({"summaries": summaries}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
