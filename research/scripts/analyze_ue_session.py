"""
Aggregate UE5 PIE-session JSONL trajectory logs into per-persona metrics.

Inputs:  ue/cnzoi/Saved/PCSP/Logs/<stamp>/agent_p<id>_*.jsonl
Outputs: results/ue_sessions/<stamp>/summary.json (+ per-persona table)

Phase 4 metrics covered:
  - Action histogram (20 v3 actions) per persona
  - Category coverage (10 affordance categories) per persona
  - interaction_complete count + reward sum
  - move_failed count + failure-reason breakdown
  - Decision latency (consecutive `t` deltas on `decision` events)
  - Congestion proxy: fraction of move_failed labeled FindBestZone:AllOverCapacity
  - Per-persona mean softmax(logits) (when decision logs include "logits") —
    used by --compare to compute symmetric KL between paired sessions.

Usage:
  python research/scripts/analyze_ue_session.py \
      --session ue/cnzoi/Saved/PCSP/Logs/20260518_104056 \
      --out research/results/ue_sessions/20260518_104056

  # Compare two sessions (e.g. seen vs zero-shot personas):
  python research/scripts/analyze_ue_session.py \
      --session ue/cnzoi/Saved/PCSP/Logs/<train_stamp> \
      --compare ue/cnzoi/Saved/PCSP/Logs/<heldout_stamp> \
      --out research/results/ue_sessions/zeroshot_<heldout_stamp>
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

V3_ACTIONS = [
    "EatQuick", "EatSlow", "RestAlone", "RestWithOthers",
    "FocusedWork", "PlanningWork", "DeepStudy", "CasualLearning",
    "ExerciseSolo", "ExerciseSocial", "HygieneQuick", "HygieneCareful",
    "SocializeInitiate", "SocializeRespond", "LeisureIndoor", "LeisureOutdoor",
    "ShopEssentials", "BrowseArea", "ObserveCrowd", "IdleReflect",
]
V3_CATEGORIES = [
    "Eat", "Rest", "Work", "Study", "Exercise", "Hygiene",
    "Social", "Leisure", "Shop", "Observe", "Idle",
]


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


def _softmax(xs: list[float]) -> list[float]:
    if not xs:
        return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def _analyze_agent(path: Path) -> dict:
    actions = Counter()
    categories_done = Counter()
    failure_reasons = Counter()
    intended_zone_on_fail = Counter()
    decision_times: list[float] = []
    reward_sum = 0.0
    n_decisions = n_interact = n_failed = 0
    persona_id = None
    policy_mode = None
    duration = 0.0
    # Running mean of per-decision softmax(logits) — preserves policy KL signal
    # without holding every decision in memory.
    prob_sum: list[float] = []
    n_logit_decisions = 0

    for rec in _iter_jsonl(path):
        ev = rec.get("event")
        if persona_id is None and "persona_id" in rec:
            persona_id = rec["persona_id"]
        if policy_mode is None and "policy_mode" in rec:
            policy_mode = rec["policy_mode"]
        if "t" in rec:
            duration = max(duration, float(rec["t"]))

        if ev == "decision":
            n_decisions += 1
            actions[rec.get("action", "Unknown")] += 1
            decision_times.append(float(rec.get("t", 0.0)))
            logits = rec.get("logits")
            if isinstance(logits, list) and logits:
                probs = _softmax([float(x) for x in logits])
                if not prob_sum:
                    prob_sum = [0.0] * len(probs)
                if len(probs) == len(prob_sum):
                    for i, p in enumerate(probs):
                        prob_sum[i] += p
                    n_logit_decisions += 1
        elif ev == "interaction_complete":
            n_interact += 1
            categories_done[rec.get("category", "Unknown")] += 1
            reward_sum += float(rec.get("reward", 0.0))
        elif ev == "move_failed":
            n_failed += 1
            reason = rec.get("failure_reason", "unknown")
            failure_reasons[reason.split(":", 1)[0]] += 1
            intended_zone_on_fail[rec.get("intended_zone", "")] += 1

    # Latency from consecutive decision timestamps
    deltas = [b - a for a, b in zip(decision_times[:-1], decision_times[1:]) if b > a]
    latency = {}
    if deltas:
        latency = {
            "mean_s": float(mean(deltas)),
            "median_s": float(median(deltas)),
            "p95_s": float(sorted(deltas)[int(0.95 * (len(deltas) - 1))]),
            "n_samples": len(deltas),
        }

    failure_rate = n_failed / max(1, n_failed + n_interact)
    congestion = failure_reasons.get("FindBestZone", 0) / max(1, n_failed)

    mean_probs = [p / n_logit_decisions for p in prob_sum] if n_logit_decisions else []

    return {
        "file": path.name,
        "persona_id": persona_id,
        "policy_mode": policy_mode,
        "duration_s": duration,
        "n_decisions": n_decisions,
        "n_interactions": n_interact,
        "n_failed": n_failed,
        "failure_rate": failure_rate,
        "congestion_fraction": congestion,
        "reward_sum": reward_sum,
        "action_hist": dict(actions),
        "category_hist": dict(categories_done),
        "failure_reasons": dict(failure_reasons),
        "intended_zone_on_fail": dict(intended_zone_on_fail),
        "latency": latency,
        "mean_policy_probs": mean_probs,
        "n_logit_decisions": n_logit_decisions,
    }


def _normalize_hist(hist: dict, keys: list[str]) -> list[float]:
    total = sum(hist.get(k, 0) for k in keys) or 1
    return [hist.get(k, 0) / total for k in keys]


def _spearman(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        return float("nan")

    def rank(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((rb[i] - mb) ** 2 for i in range(n)))
    return num / (da * db) if da > 0 and db > 0 else float("nan")


def analyze_session(session_dir: Path) -> dict:
    files = sorted(session_dir.glob("agent_p*.jsonl"))
    if not files:
        raise SystemExit(f"No agent_p*.jsonl files under {session_dir}")

    per_agent = [_analyze_agent(p) for p in files]
    per_persona: dict[int, dict] = {}
    for a in per_agent:
        pid = a["persona_id"]
        if pid is None:
            continue
        per_persona.setdefault(pid, []).append(a)

    # Aggregate across replicate agents per persona (if any)
    persona_rows = []
    for pid, rows in sorted(per_persona.items()):
        act = Counter()
        cat = Counter()
        fr = Counter()
        for r in rows:
            act.update(r["action_hist"])
            cat.update(r["category_hist"])
            fr.update(r["failure_reasons"])
        n_dec = sum(r["n_decisions"] for r in rows)
        n_int = sum(r["n_interactions"] for r in rows)
        n_fail = sum(r["n_failed"] for r in rows)
        # Decision-count-weighted mean of per-agent mean softmax(logits).
        n_logits_total = sum(r.get("n_logit_decisions", 0) for r in rows)
        policy_probs: list[float] = []
        if n_logits_total > 0:
            dim = max(len(r["mean_policy_probs"]) for r in rows)
            acc = [0.0] * dim
            for r in rows:
                n = r.get("n_logit_decisions", 0)
                mp = r.get("mean_policy_probs") or []
                if n > 0 and len(mp) == dim:
                    for i, p in enumerate(mp):
                        acc[i] += p * n
            policy_probs = [v / n_logits_total for v in acc]
        persona_rows.append({
            "persona_id": pid,
            "n_agents": len(rows),
            "n_decisions": n_dec,
            "n_interactions": n_int,
            "n_failed": n_fail,
            "failure_rate": n_fail / max(1, n_fail + n_int),
            "reward_sum": sum(r["reward_sum"] for r in rows),
            "action_hist": dict(act),
            "category_hist": dict(cat),
            "failure_reasons": dict(fr),
            "action_distribution": _normalize_hist(act, V3_ACTIONS),
            "category_distribution": _normalize_hist(cat, V3_CATEGORIES),
            "policy_probs": policy_probs,
            "n_logit_decisions": n_logits_total,
        })

    # Session totals
    tot_dec = sum(r["n_decisions"] for r in persona_rows)
    tot_int = sum(r["n_interactions"] for r in persona_rows)
    tot_fail = sum(r["n_failed"] for r in persona_rows)
    tot_reward = sum(r["reward_sum"] for r in persona_rows)
    duration_s = max((a["duration_s"] for a in per_agent), default=0.0)

    all_latency = [a["latency"]["mean_s"] for a in per_agent if a["latency"]]
    overall_latency = {
        "mean_s": float(mean(all_latency)) if all_latency else None,
        "std_s": float(pstdev(all_latency)) if len(all_latency) > 1 else 0.0,
        "n_agents_with_samples": len(all_latency),
    }

    # Inter-persona action-distribution dispersion (mean pairwise Spearman ρ).
    # Low value = personas behave differently (= the policy is conditioning).
    dists = [r["action_distribution"] for r in persona_rows]
    rhos = []
    for i in range(len(dists)):
        for j in range(i + 1, len(dists)):
            rho = _spearman(dists[i], dists[j])
            if not math.isnan(rho):
                rhos.append(rho)
    persona_dispersion = {
        "pairwise_action_rho_mean": float(mean(rhos)) if rhos else None,
        "pairwise_action_rho_median": float(median(rhos)) if rhos else None,
        "n_pairs": len(rhos),
    }

    modes = Counter(a["policy_mode"] for a in per_agent if a.get("policy_mode"))
    policy_mode = modes.most_common(1)[0][0] if modes else None

    return {
        "session_dir": str(session_dir),
        "policy_mode": policy_mode,
        "policy_mode_counts": dict(modes),
        "n_agents": len(per_agent),
        "n_personas": len(persona_rows),
        "duration_s": duration_s,
        "totals": {
            "decisions": tot_dec,
            "interactions": tot_int,
            "failed_moves": tot_fail,
            "failure_rate": tot_fail / max(1, tot_fail + tot_int),
            "reward_sum": tot_reward,
            "interactions_per_agent": tot_int / max(1, len(per_agent)),
        },
        "category_coverage": dict(
            Counter(c for r in persona_rows for c in r["category_hist"])
        ),
        "failure_reason_totals": dict(
            sum((Counter(r["failure_reasons"]) for r in persona_rows), Counter())
        ),
        "latency": overall_latency,
        "persona_dispersion": persona_dispersion,
        "per_persona": persona_rows,
    }


def _kl_divergence(p: list[float], q: list[float], eps: float = 1e-8) -> float:
    if len(p) != len(q) or not p:
        return float("nan")
    s = 0.0
    for pi, qi in zip(p, q):
        if pi <= 0.0:
            continue
        s += pi * math.log((pi + eps) / (qi + eps))
    return s


def compare_sessions(a: dict, b: dict) -> dict:
    """Per-persona Spearman ρ (action histogram) + symmetric policy KL (mean softmax)."""
    a_by_pid = {r["persona_id"]: r for r in a["per_persona"]}
    b_by_pid = {r["persona_id"]: r for r in b["per_persona"]}
    common = sorted(set(a_by_pid) & set(b_by_pid))
    rows = []
    for pid in common:
        ra, rb = a_by_pid[pid], b_by_pid[pid]
        rho = _spearman(ra["action_distribution"], rb["action_distribution"])
        kl_ab = kl_ba = sym_kl = float("nan")
        pa, pb = ra.get("policy_probs") or [], rb.get("policy_probs") or []
        if pa and pb and len(pa) == len(pb):
            kl_ab = _kl_divergence(pa, pb)
            kl_ba = _kl_divergence(pb, pa)
            sym_kl = 0.5 * (kl_ab + kl_ba)
        rows.append({
            "persona_id": pid, "rho": rho,
            "kl_ab": kl_ab, "kl_ba": kl_ba, "kl_symmetric": sym_kl,
        })
    rhos = [r["rho"] for r in rows if not math.isnan(r["rho"])]
    kls = [r["kl_symmetric"] for r in rows if not math.isnan(r["kl_symmetric"])]
    return {
        "n_common_personas": len(common),
        "per_persona_rho_mean": float(mean(rhos)) if rhos else None,
        "per_persona_rho_median": float(median(rhos)) if rhos else None,
        "per_persona_kl_mean": float(mean(kls)) if kls else None,
        "per_persona_kl_median": float(median(kls)) if kls else None,
        "n_personas_with_kl": len(kls),
        "per_persona": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=Path)
    ap.add_argument("--compare", type=Path, default=None,
                    help="Optional second session dir to compare action distributions against.")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    summary = analyze_session(args.session)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[ok] wrote {args.out / 'summary.json'}")
    print(f"     mode={summary['policy_mode']} "
          f"personas={summary['n_personas']} agents={summary['n_agents']} "
          f"duration={summary['duration_s']:.1f}s "
          f"interactions={summary['totals']['interactions']} "
          f"failure_rate={summary['totals']['failure_rate']:.3f}")
    if summary["persona_dispersion"]["pairwise_action_rho_mean"] is not None:
        print(f"     inter-persona action rho (lower = more persona-distinct): "
              f"mean={summary['persona_dispersion']['pairwise_action_rho_mean']:.3f}")

    if args.compare:
        other = analyze_session(args.compare)
        cmp = compare_sessions(summary, other)
        (args.out / "compare.json").write_text(json.dumps({
            "session_a": str(args.session),
            "session_b": str(args.compare),
            **cmp,
        }, indent=2))
        print(f"[ok] wrote {args.out / 'compare.json'} "
              f"(matched personas={cmp['n_common_personas']}, "
              f"mean rho={cmp['per_persona_rho_mean']}, "
              f"mean KL={cmp['per_persona_kl_mean']} "
              f"over {cmp['n_personas_with_kl']} personas)")


if __name__ == "__main__":
    main()
