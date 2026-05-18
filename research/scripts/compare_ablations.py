"""
Aggregate multiple PIE-session JSONL log dirs (one per Phase 4 ablation mode)
into a single ablation comparison table.

Each input session is analyzed via analyze_ue_session.analyze_session, then
compared against a reference session (--ref, default = first --session).

Output (printed + written to <out>/ablation.json):
  per mode: policy_mode, n_personas, n_interactions, failure_rate, reward,
            mean_pairwise_action_rho (inter-persona dispersion — lower = more
            persona-distinct), mean_rho_vs_ref, mean_symmetric_kl_vs_ref

Usage:
  python research/scripts/compare_ablations.py \
      --session ue/cnzoi/Saved/PCSP/Logs/<hybrid_pcsp> \
      --session ue/cnzoi/Saved/PCSP/Logs/<bt_only> \
      --session ue/cnzoi/Saved/PCSP/Logs/<hybrid_no_persona> \
      --out research/results/ue_sessions/ablation_<stamp>

Notes:
  - BTOnly rows have zeroed logits by design, so policy KL vs reference is
    not meaningful for that mode and is reported as None.
  - Inter-persona dispersion ρ uses the action histogram, which is populated
    for every mode regardless of logit availability.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_ue_session import analyze_session, compare_sessions


def _mode_label(summary: dict) -> str:
    return summary.get("policy_mode") or "Unknown"


def _has_logits(summary: dict) -> bool:
    # BTOnly skips ONNX and emits a zero logit vector to keep the JSONL
    # schema uniform. Softmax of zeros is uniform, so any KL we'd compute
    # against it just measures distance from uniform — not a policy KL.
    # Treat that as "no logits available" for comparison purposes.
    if summary.get("policy_mode") == "BTOnly":
        return False
    return any(r.get("policy_probs") for r in summary["per_persona"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", action="append", required=True, type=Path,
                    help="Session dir; pass once per ablation mode.")
    ap.add_argument("--ref", type=Path, default=None,
                    help="Reference session for ρ/KL comparison (default = first --session).")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    sessions = [analyze_session(p) for p in args.session]
    ref_path = args.ref or args.session[0]
    ref_summary = next((s for s in sessions if Path(s["session_dir"]) == ref_path), None)
    if ref_summary is None:
        ref_summary = analyze_session(ref_path)

    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in sessions:
        is_ref = Path(s["session_dir"]) == Path(ref_summary["session_dir"])
        cmp = None if is_ref else compare_sessions(ref_summary, s)
        kl_ok = _has_logits(s) and _has_logits(ref_summary)
        rows.append({
            "session_dir": s["session_dir"],
            "policy_mode": _mode_label(s),
            "is_reference": is_ref,
            "n_personas": s["n_personas"],
            "n_interactions": s["totals"]["interactions"],
            "failure_rate": s["totals"]["failure_rate"],
            "reward_sum": s["totals"]["reward_sum"],
            "interactions_per_agent": s["totals"]["interactions_per_agent"],
            "inter_persona_rho_mean": s["persona_dispersion"]["pairwise_action_rho_mean"],
            "vs_ref_action_rho_mean": cmp["per_persona_rho_mean"] if cmp else None,
            "vs_ref_kl_symmetric_mean": (cmp["per_persona_kl_mean"] if cmp and kl_ok else None),
            "n_personas_with_kl": (cmp["n_personas_with_kl"] if cmp and kl_ok else 0),
        })

    table = {
        "reference": ref_summary["session_dir"],
        "reference_mode": _mode_label(ref_summary),
        "modes": rows,
    }
    out_path = args.out / "ablation.json"
    out_path.write_text(json.dumps(table, indent=2))
    print(f"[ok] wrote {out_path}")
    print(f"     reference: {table['reference_mode']}  "
          f"({Path(table['reference']).name})")
    print()
    header = f"{'mode':<18} {'n_int':>6} {'fail%':>6} {'reward':>8} {'rho_ref':>7} {'KL_ref':>7} {'rho_intra':>9}"
    print(header)
    print("-" * len(header))
    for r in rows:
        rho_ref = f"{r['vs_ref_action_rho_mean']:.3f}" if r['vs_ref_action_rho_mean'] is not None else "  ref"
        kl_ref  = f"{r['vs_ref_kl_symmetric_mean']:.3f}" if r['vs_ref_kl_symmetric_mean'] is not None else "   - "
        rho_in  = f"{r['inter_persona_rho_mean']:.3f}" if r['inter_persona_rho_mean'] is not None else "   - "
        print(f"{r['policy_mode']:<18} {r['n_interactions']:>6d} "
              f"{r['failure_rate']*100:>5.1f}% {r['reward_sum']:>8.1f} "
              f"{rho_ref:>7} {kl_ref:>7} {rho_in:>8}")


if __name__ == "__main__":
    main()
