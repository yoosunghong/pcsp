"""
Aggregate T1.3 UE5 scaling-sweep PIE sessions into the scaling curve (Fig 5)
and latency-budget table (Tab from REVISE_PLAN.md T1.3).

Each session dir is expected to contain:
  - run_config.json                   (n_agents, seed)
  - agent_p<id>_*.jsonl               (decision events with "infer_us")
  - frame_stats.jsonl                 (1 Hz: mean_ms / p50 / p95 / p99)
  - zone_occupancy.jsonl              (1 Hz per-zone capacity utilization)

When run_config.json is missing (sessions captured before the spawner was
extended) n_agents falls back to `len(glob("agent_p*.jsonl"))` and seed is
recorded as -1.

The first WARMUP_SECONDS of every session are dropped before computing
latency / frame-time aggregates, removing the PIE cold-start hitch (~400 ms
p99 on the first sample) observed in the 16-agent smoke run.

Usage:
  python research/scripts/analyze_scaling_sweep.py \
      --sessions ue/cnzoi/Saved/PCSP/Logs/20260520_* \
      --out      research/results/ue_sessions/scaling_20260520 \
      --plot

Inputs are *session directories*, not individual files. Glob patterns are
expanded by the shell.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, pstdev

WARMUP_SECONDS = 5.0


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _percentile(sorted_xs, q: float) -> float:
    if not sorted_xs:
        return float("nan")
    idx = max(0, min(len(sorted_xs) - 1, int(len(sorted_xs) * q)))
    return float(sorted_xs[idx])


def _summarize_session(session_dir: Path) -> dict:
    cfg_path = session_dir / "run_config.json"
    agent_files = sorted(session_dir.glob("agent_p*.jsonl"))

    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        n_agents = int(cfg.get("n_agents", len(agent_files)))
        seed = int(cfg.get("seed", -1))
    else:
        n_agents = len(agent_files)
        seed = -1

    # --- Inference latency (µs) + decision / interaction / failure counts ---
    infer_us: list[float] = []
    n_decisions = 0
    n_complete = 0
    n_move_failed = 0
    failure_reasons: Counter[str] = Counter()
    t_first = math.inf
    t_last = 0.0

    for f in agent_files:
        for rec in _iter_jsonl(f):
            ev = rec.get("event")
            t = float(rec.get("t", 0.0))
            if ev in ("decision", "interaction_complete", "interaction_failed", "move_failed"):
                t_first = min(t_first, t)
                t_last = max(t_last, t)
            if ev == "decision":
                n_decisions += 1
                if t >= WARMUP_SECONDS and "infer_us" in rec:
                    infer_us.append(float(rec["infer_us"]))
            elif ev == "interaction_complete":
                n_complete += 1
            elif ev == "move_failed":
                n_move_failed += 1
                reason = str(rec.get("failure_reason", "unspecified"))
                failure_reasons[reason.split(":")[0]] += 1

    duration_s = max(0.0, t_last - t_first) if t_first != math.inf else 0.0
    infer_sorted = sorted(infer_us)

    # --- Frame-time stats (collected at 1 Hz; each row already pre-aggregated) ---
    frame_path = session_dir / "frame_stats.jsonl"
    frame_p95 = []
    frame_p99 = []
    frame_mean = []
    if frame_path.exists():
        for rec in _iter_jsonl(frame_path):
            if float(rec.get("t", 0.0)) < WARMUP_SECONDS:
                continue
            frame_mean.append(float(rec["mean_ms"]))
            frame_p95.append(float(rec["p95_ms"]))
            frame_p99.append(float(rec["p99_ms"]))

    # --- Zone occupancy utilization (mean of occupants/capacity across all samples) ---
    occ_path = session_dir / "zone_occupancy.jsonl"
    util_by_zone: dict[str, list[float]] = {}
    if occ_path.exists():
        for rec in _iter_jsonl(occ_path):
            if float(rec.get("t", 0.0)) < WARMUP_SECONDS:
                continue
            cap = float(rec.get("capacity", 0)) or 1.0
            occ = float(rec.get("occupants", 0))
            util_by_zone.setdefault(rec.get("zone_tag", "?"), []).append(occ / cap)
    mean_util = {z: (sum(v) / len(v) if v else 0.0) for z, v in util_by_zone.items()}

    intents_per_agent_per_min = (
        (n_complete / n_agents) / (duration_s / 60.0)
        if n_agents > 0 and duration_s > 0
        else 0.0
    )
    fail_rate = (
        n_move_failed / (n_move_failed + n_complete)
        if (n_move_failed + n_complete) > 0
        else 0.0
    )

    return {
        "session": session_dir.name,
        "n_agents": n_agents,
        "seed": seed,
        "duration_s": round(duration_s, 1),
        "n_decisions": n_decisions,
        "n_interaction_complete": n_complete,
        "n_move_failed": n_move_failed,
        "fail_rate": round(fail_rate, 4),
        "intents_per_agent_per_min": round(intents_per_agent_per_min, 2),
        "infer_us": {
            "n": len(infer_us),
            "mean": round(mean(infer_us), 1) if infer_us else None,
            "p50": round(_percentile(infer_sorted, 0.50), 1) if infer_us else None,
            "p95": round(_percentile(infer_sorted, 0.95), 1) if infer_us else None,
            "p99": round(_percentile(infer_sorted, 0.99), 1) if infer_us else None,
            "max": round(infer_sorted[-1], 1) if infer_us else None,
        },
        "frame_ms": {
            "n": len(frame_mean),
            "mean": round(mean(frame_mean), 3) if frame_mean else None,
            "p95_of_p95": round(_percentile(sorted(frame_p95), 0.95), 3) if frame_p95 else None,
            "p95_max": round(max(frame_p95), 3) if frame_p95 else None,
            "p99_max": round(max(frame_p99), 3) if frame_p99 else None,
        },
        "failure_reasons": dict(failure_reasons.most_common()),
        "zone_utilization": mean_util,
    }


def _aggregate(sessions: list[dict]) -> list[dict]:
    """Group by n_agents; average across seeds."""
    grouped: dict[int, list[dict]] = {}
    for s in sessions:
        grouped.setdefault(s["n_agents"], []).append(s)

    out = []
    for n, group in sorted(grouped.items()):
        infer_means = [s["infer_us"]["mean"] for s in group if s["infer_us"]["mean"] is not None]
        infer_p95s = [s["infer_us"]["p95"] for s in group if s["infer_us"]["p95"] is not None]
        frame_p95s = [s["frame_ms"]["p95_of_p95"] for s in group if s["frame_ms"]["p95_of_p95"] is not None]
        frame_means = [s["frame_ms"]["mean"] for s in group if s["frame_ms"]["mean"] is not None]
        fail_rates = [s["fail_rate"] for s in group]
        intents = [s["intents_per_agent_per_min"] for s in group]

        def _ms(xs):
            return {
                "mean": round(mean(xs), 3) if xs else None,
                "std": round(pstdev(xs), 3) if len(xs) > 1 else 0.0,
                "n": len(xs),
            }

        out.append({
            "n_agents": n,
            "n_seeds": len(group),
            "seeds": [s["seed"] for s in group],
            "duration_s_mean": round(mean(s["duration_s"] for s in group), 1),
            "infer_us_mean":   _ms(infer_means),
            "infer_us_p95":    _ms(infer_p95s),
            "frame_ms_mean":   _ms(frame_means),
            "frame_ms_p95":    _ms(frame_p95s),
            "fail_rate":       _ms(fail_rates),
            "intents_per_agent_per_min": _ms(intents),
        })
    return out


def _emit_latency_table(agg: list[dict], path: Path) -> None:
    """Tab-separated, ready to paste into the §7 latency-budget table."""
    lines = [
        "n_agents\tseeds\tinfer_us_mean\tinfer_us_p95\tframe_ms_mean\tframe_ms_p95\tfail_rate\tintents_per_agent_min"
    ]
    for r in agg:
        lines.append("\t".join([
            str(r["n_agents"]),
            str(r["n_seeds"]),
            f"{r['infer_us_mean']['mean']:.1f}" if r["infer_us_mean"]["mean"] is not None else "-",
            f"{r['infer_us_p95']['mean']:.1f}" if r["infer_us_p95"]["mean"] is not None else "-",
            f"{r['frame_ms_mean']['mean']:.2f}" if r["frame_ms_mean"]["mean"] is not None else "-",
            f"{r['frame_ms_p95']['mean']:.2f}" if r["frame_ms_p95"]["mean"] is not None else "-",
            f"{r['fail_rate']['mean']:.3f}",
            f"{r['intents_per_agent_per_min']['mean']:.2f}",
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _emit_plot(agg: list[dict], path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"matplotlib not installed; skipping plot ({path})")
        return

    xs = [r["n_agents"] for r in agg]
    infer_mean = [r["infer_us_mean"]["mean"] or 0 for r in agg]
    frame_p95  = [r["frame_ms_p95"]["mean"] or 0 for r in agg]
    fail_pct   = [(r["fail_rate"]["mean"] or 0) * 100 for r in agg]

    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(xs, frame_p95, "o-", color="C0", label="frame p95 (ms)")
    ax1.plot(xs, [v / 1000.0 for v in infer_mean], "s--", color="C2",
             label="inference mean (ms)")
    ax1.set_xlabel("Concurrent agents")
    ax1.set_ylabel("Latency (ms)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(xs, fail_pct, "^-", color="C3", label="BT-abort fail %")
    ax2.set_ylabel("BT-abort failure rate (%)", color="C3")
    ax2.tick_params(axis="y", labelcolor="C3")

    plt.title("PCSP scaling curve (T1.3)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", required=True,
                    help="Session directories (one per PIE run).")
    ap.add_argument("--out", required=True,
                    help="Output directory for scaling_curve.json + latency_budget.tsv.")
    ap.add_argument("--plot", action="store_true",
                    help="Also save scaling_curve.png (requires matplotlib).")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions = []
    for s in args.sessions:
        p = Path(s)
        if not p.is_dir():
            print(f"skip (not a dir): {p}")
            continue
        sessions.append(_summarize_session(p))

    agg = _aggregate(sessions)

    (out_dir / "per_session.json").write_text(
        json.dumps(sessions, indent=2), encoding="utf-8")
    (out_dir / "scaling_curve.json").write_text(
        json.dumps(agg, indent=2), encoding="utf-8")
    _emit_latency_table(agg, out_dir / "latency_budget.tsv")

    if args.plot:
        _emit_plot(agg, out_dir / "scaling_curve.png")

    print(f"wrote {len(sessions)} sessions to {out_dir}")
    print(f"  - per_session.json     ({len(sessions)} rows)")
    print(f"  - scaling_curve.json   ({len(agg)} agent-count buckets)")
    print(f"  - latency_budget.tsv")
    if args.plot:
        print(f"  - scaling_curve.png")


if __name__ == "__main__":
    main()
