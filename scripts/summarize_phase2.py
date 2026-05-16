"""Summarize Phase 2 persona-conditioned PPO smoke runs.

Reads ``logs.jsonl`` and ``persona_diagnostics.json`` from each run and
prints a one-block summary for the PHASE2_REPORT.md table.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean


def summarize(run_dir: Path) -> dict:
    log_path = run_dir / "logs.jsonl"
    diag_path = run_dir / "persona_diagnostics.json"
    cfg_path = run_dir / "config.json"
    logs = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    cfg = json.loads(cfg_path.read_text())
    diag = json.loads(diag_path.read_text()) if diag_path.exists() else None
    last = logs[-1]
    final_ep_return = last.get("env/episode_return_mean", float("nan"))
    summary = {
        "run": run_dir.name,
        "mode": cfg.get("persona_conditioning"),
        "assignment": cfg.get("persona_assignment"),
        "embedding_dim": cfg.get("persona_embedding_dim"),
        "total_env_steps": last.get("global_step"),
        "wallclock_s": last.get("wallclock_s"),
        "sps_mean": mean(l["rollout/sps"] for l in logs if "rollout/sps" in l),
        "final_loss_policy": last.get("loss/policy"),
        "final_loss_value": last.get("loss/value"),
        "final_loss_entropy": last.get("loss/entropy"),
        "final_approx_kl": last.get("loss/approx_kl"),
        "final_episode_return_mean": final_ep_return,
        "explained_var": last.get("loss/explained_var"),
    }
    if diag is not None:
        summary["personas_seen"] = len(diag.get("personas_seen", []))
        summary["mean_pairwise_action_kl"] = diag.get("mean_pairwise_action_kl")
        # Range of per-persona mean returns (skips NaN).
        rets = [
            v for v in diag.get("mean_episode_return", {}).values()
            if isinstance(v, (int, float)) and not math.isnan(v)
        ]
        if rets:
            summary["per_persona_return_min"] = min(rets)
            summary["per_persona_return_max"] = max(rets)
            summary["per_persona_return_spread"] = max(rets) - min(rets)
        # FORWARD/FIRE_ZAP action shares per persona.
        action_dist = diag.get("action_distribution", {})
        if action_dist:
            zap_shares = {pid: probs[7] for pid, probs in action_dist.items()}
            fwd_shares = {pid: probs[1] for pid, probs in action_dist.items()}
            summary["zap_share_range"] = (min(zap_shares.values()), max(zap_shares.values()))
            summary["forward_share_range"] = (min(fwd_shares.values()), max(fwd_shares.values()))
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dirs", nargs="+")
    args = p.parse_args()
    for d in args.run_dirs:
        s = summarize(Path(d))
        print(json.dumps(s, indent=2, default=str))
        print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
