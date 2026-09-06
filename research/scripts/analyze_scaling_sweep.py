"""
Aggregate T1.3 UE5 scaling-sweep PIE sessions into the scaling curve (Fig 5)
and latency-budget table (Tab from REVISE_PLAN.md T1.3).

Each session dir is expected to contain:
  - run_config.json                   (hero_agents, mass_entities, total_npcs, seed)
  - agent_p<id>_*.jsonl               (decision events with "infer_us")
  - frame_stats.jsonl                 (1 Hz: mean_ms / p50 / p95 / p99)
  - zone_occupancy.jsonl              (1 Hz per-zone capacity utilization)
  - path_scheduler.jsonl              (Actor-tier request queue/wait telemetry)
  - mass_stats.jsonl                  (Mass update/decision/arrival telemetry)

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
        hero_agents = int(cfg.get("hero_agents", len(agent_files)))
        mass_entities = int(cfg.get("mass_entities", 0))
        n_agents = int(cfg.get("total_npcs", cfg.get("n_agents", hero_agents + mass_entities)))
        seed = int(cfg.get("seed", -1))
    else:
        hero_agents = len(agent_files)
        mass_entities = 0
        n_agents = hero_agents
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
    frame_last_t = 0.0
    if frame_path.exists():
        for rec in _iter_jsonl(frame_path):
            t = float(rec.get("t", 0.0))
            frame_last_t = max(frame_last_t, t)
            if t < WARMUP_SECONDS:
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

    # --- Actor path-request scheduler telemetry ---
    scheduler_path = session_dir / "path_scheduler.jsonl"
    scheduler_rows = []
    if scheduler_path.exists():
        scheduler_rows = [
            rec for rec in _iter_jsonl(scheduler_path)
            if float(rec.get("t", 0.0)) >= WARMUP_SECONDS
        ]

    # --- Mass background-tier telemetry ---
    mass_path = session_dir / "mass_stats.jsonl"
    mass_rows = []
    mass_last_t = 0.0
    if mass_path.exists():
        for rec in _iter_jsonl(mass_path):
            t = float(rec.get("t", 0.0))
            mass_last_t = max(mass_last_t, t)
            if t >= WARMUP_SECONDS:
                mass_rows.append(rec)

    # All-Mass sessions intentionally have no per-Actor trajectory files. Use
    # the sampled telemetry timeline so their duration and per-NPC throughput
    # do not collapse to zero in the aggregate table.
    if duration_s <= 0.0:
        duration_s = max(0.0, max(frame_last_t, mass_last_t) - WARMUP_SECONDS)
    mass_decisions = sum(int(rec.get("decisions", 0)) for rec in mass_rows)
    mass_arrivals = sum(int(rec.get("arrivals", 0)) for rec in mass_rows)
    mass_policy_samples = [
        float(rec.get("policy_us_mean", 0.0))
        for rec in mass_rows if int(rec.get("decisions", 0)) > 0
    ]

    intents_per_agent_per_min = (
        ((n_complete + mass_arrivals) / n_agents) / (duration_s / 60.0)
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
        "hero_agents": hero_agents,
        "mass_entities": mass_entities,
        "architecture": (
            "all_mass" if mass_entities > 0 and hero_agents == 0
            else "mass_hybrid" if mass_entities > 0
            else "actor_bt"
        ),
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
        "path_scheduler": {
            "n": len(scheduler_rows),
            "queue_peak": max((int(r.get("peak_depth", 0)) for r in scheduler_rows), default=0),
            "wait_ms_mean": round(mean(float(r.get("wait_ms_mean", 0.0)) for r in scheduler_rows), 3)
                if scheduler_rows else None,
            "wait_ms_p95_mean": round(mean(float(r.get("wait_ms_p95", 0.0)) for r in scheduler_rows), 3)
                if scheduler_rows else None,
            "submitted": sum(int(r.get("submitted", 0)) for r in scheduler_rows),
        },
        "mass": {
            "n": len(mass_rows),
            "decisions": mass_decisions,
            "arrivals": mass_arrivals,
            "policy_us_mean": round(mean(mass_policy_samples), 3) if mass_policy_samples else None,
            "arrivals_per_entity_min": round(
                (mass_arrivals / mass_entities) / (duration_s / 60.0)
                if mass_entities > 0 and duration_s > 0 else 0.0,
                3,
            ),
        },
    }


def _aggregate(sessions: list[dict]) -> list[dict]:
    """Group by architecture and total NPC count; average across seeds."""
    grouped: dict[tuple[str, int], list[dict]] = {}
    for s in sessions:
        grouped.setdefault((s["architecture"], s["n_agents"]), []).append(s)

    out = []
    for (architecture, n), group in sorted(grouped.items()):
        infer_means = [s["infer_us"]["mean"] for s in group if s["infer_us"]["mean"] is not None]
        infer_p95s = [s["infer_us"]["p95"] for s in group if s["infer_us"]["p95"] is not None]
        frame_p95s = [s["frame_ms"]["p95_of_p95"] for s in group if s["frame_ms"]["p95_of_p95"] is not None]
        frame_means = [s["frame_ms"]["mean"] for s in group if s["frame_ms"]["mean"] is not None]
        fail_rates = [s["fail_rate"] for s in group]
        intents = [s["intents_per_agent_per_min"] for s in group]
        queue_peaks = [s["path_scheduler"]["queue_peak"] for s in group]
        scheduler_waits = [
            s["path_scheduler"]["wait_ms_p95_mean"] for s in group
            if s["path_scheduler"]["wait_ms_p95_mean"] is not None
        ]
        mass_policy = [
            s["mass"]["policy_us_mean"] for s in group
            if s["mass"]["policy_us_mean"] is not None
        ]

        def _ms(xs):
            return {
                "mean": round(mean(xs), 3) if xs else None,
                "std": round(pstdev(xs), 3) if len(xs) > 1 else 0.0,
                "n": len(xs),
            }

        out.append({
            "n_agents": n,
            "architecture": architecture,
            "hero_agents": group[0]["hero_agents"],
            "mass_entities": group[0]["mass_entities"],
            "n_seeds": len(group),
            "seeds": [s["seed"] for s in group],
            "duration_s_mean": round(mean(s["duration_s"] for s in group), 1),
            "infer_us_mean":   _ms(infer_means),
            "infer_us_p95":    _ms(infer_p95s),
            "frame_ms_mean":   _ms(frame_means),
            "frame_ms_p95":    _ms(frame_p95s),
            "fail_rate":       _ms(fail_rates),
            "intents_per_agent_per_min": _ms(intents),
            "path_queue_peak": _ms(queue_peaks),
            "path_wait_ms_p95": _ms(scheduler_waits),
            "mass_policy_us_mean": _ms(mass_policy),
        })
    return out


def _emit_latency_table(agg: list[dict], path: Path) -> None:
    """Tab-separated, ready to paste into the §7 latency-budget table."""
    lines = [
        "architecture\ttotal_npcs\thero_agents\tmass_entities\tseeds\tinfer_us_mean\tinfer_us_p95\tframe_ms_mean\tframe_ms_p95\tfail_rate\tintents_per_agent_min\tpath_queue_peak\tpath_wait_ms_p95\tmass_policy_us_mean"
    ]
    for r in agg:
        lines.append("\t".join([
            str(r["architecture"]),
            str(r["n_agents"]),
            str(r["hero_agents"]),
            str(r["mass_entities"]),
            str(r["n_seeds"]),
            f"{r['infer_us_mean']['mean']:.1f}" if r["infer_us_mean"]["mean"] is not None else "-",
            f"{r['infer_us_p95']['mean']:.1f}" if r["infer_us_p95"]["mean"] is not None else "-",
            f"{r['frame_ms_mean']['mean']:.2f}" if r["frame_ms_mean"]["mean"] is not None else "-",
            f"{r['frame_ms_p95']['mean']:.2f}" if r["frame_ms_p95"]["mean"] is not None else "-",
            f"{r['fail_rate']['mean']:.3f}",
            f"{r['intents_per_agent_per_min']['mean']:.2f}",
            f"{r['path_queue_peak']['mean']:.1f}" if r["path_queue_peak"]["mean"] is not None else "-",
            f"{r['path_wait_ms_p95']['mean']:.1f}" if r["path_wait_ms_p95"]["mean"] is not None else "-",
            f"{r['mass_policy_us_mean']['mean']:.1f}" if r["mass_policy_us_mean"]["mean"] is not None else "-",
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

    fig, ax1 = plt.subplots(figsize=(7, 4))
    colors = {"actor_bt": "C0", "mass_hybrid": "C2"}
    markers = {"actor_bt": "o", "mass_hybrid": "s"}
    architectures = sorted({r["architecture"] for r in agg})
    for architecture in architectures:
        rows = [r for r in agg if r["architecture"] == architecture]
        xs = [r["n_agents"] for r in rows]
        frame_p95 = [r["frame_ms_p95"]["mean"] or 0 for r in rows]
        ax1.plot(xs, frame_p95, marker=markers.get(architecture, "o"),
                 color=colors.get(architecture), label=f"{architecture} frame p95")
    ax1.set_xlabel("Concurrent agents")
    ax1.set_ylabel("Frame p95 (ms)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left")

    plt.title(
        "PCSP All-Mass Portfolio Scaling"
        if architectures == ["all_mass"]
        else "PCSP Actor/BT debug baseline vs all-Mass scaling"
    )
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
