"""Print a one-line + multi-line summary of a CleanRL PPO run from its logs.jsonl.

Usage:
    python scripts/summarize_run.py research/meltingpot/runs/phase1_smoke_1M
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean


def main() -> int:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("research/meltingpot/runs/phase1_smoke_1M")
    log = run_dir / "logs.jsonl"
    if not log.is_file():
        print(f"missing: {log}", file=sys.stderr)
        return 1
    rows = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    if not rows:
        print("no rows in log", file=sys.stderr)
        return 1
    last = rows[-1]
    first = rows[0]
    sps = [r.get("rollout/sps", 0.0) for r in rows]
    eps = [r.get("env/episode_return_mean") for r in rows if "env/episode_return_mean" in r]
    klg = [r.get("loss/approx_kl", 0.0) for r in rows]

    print(f"run_dir: {run_dir}")
    print(f"num_log_rows: {len(rows)}")
    print(f"global_step_final: {last.get('global_step')}")
    print(f"wallclock_s: {last.get('wallclock_s', 0):.1f}")
    print(f"sps_mean: {mean(sps):.1f}")
    print(f"sps_last: {last.get('rollout/sps', 0):.1f}")
    print(f"approx_kl_mean: {mean(klg):.5f}")
    print(f"approx_kl_last: {last.get('loss/approx_kl', 0):.5f}")
    print(f"loss_value_last: {last.get('loss/value', 0):.3f}")
    print(f"loss_policy_last: {last.get('loss/policy', 0):.5f}")
    print(f"entropy_last: {last.get('loss/entropy', 0):.3f}")
    print(f"explained_var_last: {last.get('loss/explained_var', 0):.4f}")
    print(f"reset_count_last: {last.get('env/reset_count', 0)}")
    if eps:
        print(f"ep_return_first_logged: {eps[0]:.3f}")
        print(f"ep_return_last_logged:  {eps[-1]:.3f}")
        print(f"ep_return_max:          {max(eps):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
