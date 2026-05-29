"""
Coarse trace renderer for UE5 PIE-session JSONL.

Reads `ue/cnzoi/Saved/PCSP/Logs/<stamp>/agent_p*.jsonl` and emits one
human-readable line per event. Useful for portfolio walkthroughs and
sanity-checking a session without booting the editor.

Two output modes:

  --mode full        every decision / interaction / failure event
                     (default; chronological merge across agents)
  --mode schedule    one line per `interaction_complete` only; a
                     compressed per-persona daily schedule

A persona filter (`--persona 7`) limits output to a single agent.
A time window (`--from 30 --until 90`) clips to [from, until] seconds.

Output is plain text on stdout; pipe to a file or `less` as needed.

Example:
  python research/scripts/render_session_trace.py \\
      --session ue/cnzoi/Saved/PCSP/Logs/20260518_140432 \\
      --persona 7 --mode full --from 0 --until 120

  python research/scripts/render_session_trace.py \\
      --session ue/cnzoi/Saved/PCSP/Logs/20260518_140432 \\
      --mode schedule > schedule.txt
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


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


def _fmt_full(rec: dict) -> str | None:
    t = float(rec.get("t", 0.0))
    pid = rec.get("persona_id", "?")
    event = rec.get("event", "")
    if event == "decision":
        action = rec.get("action", "?")
        cat = rec.get("category", "?")
        urg = float(rec.get("urgency", 0.0))
        marker = "!" if urg >= 0.85 else " "
        return f"[t={t:7.2f}] p={pid:>3} {marker} DECIDE   {action:<20} ({cat:<8}) urg={urg:.2f}"
    if event == "interaction_complete":
        action = rec.get("action", "?")
        zone = rec.get("affordance") or rec.get("intended_zone") or "?"
        cat = rec.get("category", "?")
        reward = float(rec.get("reward", 0.0))
        dur = rec.get("duration_s")
        dur_s = f" [{float(dur):.1f}s]" if dur is not None else ""
        return f"[t={t:7.2f}] p={pid:>3}   INTERACT {action:<20} @{zone:<16} ({cat:<8}) reward={reward:+.2f}{dur_s}"
    if event == "interaction_failed":
        action = rec.get("action", "?")
        reason = rec.get("failure_reason", "unknown")
        return f"[t={t:7.2f}] p={pid:>3}   IFAIL    {action:<20} reason={reason}"
    if event == "move_failed":
        action = rec.get("action", "?")
        zone = rec.get("intended_zone") or "-"
        reason = rec.get("failure_reason", "unknown")
        dist = rec.get("distance_to_target")
        d_s = f" dist={float(dist):.0f}cm" if dist is not None else ""
        return f"[t={t:7.2f}] p={pid:>3}   MFAIL    {action:<20} →{zone:<16} {reason}{d_s}"
    if event == "session_start":
        mode = rec.get("policy_mode", "?")
        abl = rec.get("active_ablation") or "-"
        return f"[t={t:7.2f}] p={pid:>3}   START    policy_mode={mode} active_ablation={abl}"
    return None


def _fmt_schedule(rec: dict) -> str | None:
    if rec.get("event") != "interaction_complete":
        return None
    t = float(rec.get("t", 0.0))
    pid = rec.get("persona_id", "?")
    action = rec.get("action", "?")
    zone = rec.get("affordance") or rec.get("intended_zone") or "?"
    cat = rec.get("category", "?")
    reward = float(rec.get("reward", 0.0))
    return f"[t={t:7.2f}] p={pid:>3} {action:<20} @{zone:<16} ({cat:<8}) reward={reward:+.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=Path,
                    help="Saved/PCSP/Logs/<stamp> directory")
    ap.add_argument("--mode", choices=("full", "schedule"), default="full")
    ap.add_argument("--persona", type=int, default=None,
                    help="If set, only render this persona_id")
    ap.add_argument("--from", dest="t_from", type=float, default=None,
                    help="Earliest t (seconds) to include")
    ap.add_argument("--until", dest="t_until", type=float, default=None,
                    help="Latest t (seconds) to include")
    ap.add_argument("--group-by", choices=("time", "persona"), default="time",
                    help="time: chronological merge across agents (default). "
                         "persona: group all events of each persona together.")
    args = ap.parse_args()

    files = sorted(args.session.glob("agent_p*.jsonl"))
    if not files:
        raise SystemExit(f"No agent_p*.jsonl found in {args.session}")

    fmt = _fmt_full if args.mode == "full" else _fmt_schedule

    # Collect (t, pid, line) records first so we can sort or bucket.
    rows: list[tuple[float, int, str]] = []
    for f in files:
        for rec in _iter_jsonl(f):
            pid = rec.get("persona_id")
            if args.persona is not None and pid != args.persona:
                continue
            t = float(rec.get("t", 0.0))
            if args.t_from is not None and t < args.t_from:
                continue
            if args.t_until is not None and t > args.t_until:
                continue
            line = fmt(rec)
            if line is None:
                continue
            rows.append((t, int(pid) if pid is not None else -1, line))

    if not rows:
        print(f"# no events matched filters in {args.session}")
        return

    if args.group_by == "persona":
        by_pid: dict[int, list[tuple[float, str]]] = defaultdict(list)
        for t, pid, line in rows:
            by_pid[pid].append((t, line))
        for pid in sorted(by_pid):
            print(f"## persona {pid}  ({len(by_pid[pid])} events)")
            for _, line in sorted(by_pid[pid], key=lambda r: r[0]):
                print(line)
            print()
    else:
        for _, _, line in sorted(rows, key=lambda r: (r[0], r[1])):
            print(line)


if __name__ == "__main__":
    main()
