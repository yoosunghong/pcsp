"""
T1.5 — Failure-analysis figures for the Layer-3 rho-drop reframe (§7.6).

Produces two figures from a single 64-agent HybridPCSP PIE session:

  1. Zone-capacity utilisation heatmap (per-zone occupancy / capacity over the
     episode) — the engine-side contention signal behind the rho-drop.
  2. Per-category expressed-vs-preferred intent distribution — the policy's
     preferred intent (mean softmax over the 20-d logits, folded to 11
     categories) against what actually executed (completed-affordance
     categories). The gap visualises contention pushing agents "toward what is
     reachable, not what their embedding most prefers".

Inputs:
  ue/cnzoi/Saved/PCSP/Logs/<stamp>/zone_occupancy.jsonl
  ue/cnzoi/Saved/PCSP/Logs/<stamp>/agent_p*.jsonl   (decision + interaction_complete)

Outputs:
  research/paper/figures/fig_ue5_contention_heatmap.{pdf,png}
  research/paper/figures/fig_ue5_expressed_vs_preferred.{pdf,png}
  research/results/ue_sessions/<stamp>/contention_t15.json

Usage:
  python research/scripts/build_t15_contention.py \
      --session ue/cnzoi/Saved/PCSP/Logs/20260520_013551
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

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
CAT_INDEX = {c: i for i, c in enumerate(V3_CATEGORIES)}
ACTION_TO_CATEGORY = {
    "EatQuick": "Eat", "EatSlow": "Eat",
    "RestAlone": "Rest", "RestWithOthers": "Rest",
    "FocusedWork": "Work", "PlanningWork": "Work",
    "DeepStudy": "Study", "CasualLearning": "Study",
    "ExerciseSolo": "Exercise", "ExerciseSocial": "Exercise",
    "HygieneQuick": "Hygiene", "HygieneCareful": "Hygiene",
    "SocializeInitiate": "Social", "SocializeRespond": "Social",
    "LeisureIndoor": "Leisure", "LeisureOutdoor": "Leisure",
    "ShopEssentials": "Shop", "BrowseArea": "Shop",
    "ObserveCrowd": "Observe", "IdleReflect": "Idle",
}
# 20-d logit index -> 11-category index, for folding softmax onto categories.
ACTION_IDX_TO_CAT_IDX = [CAT_INDEX[ACTION_TO_CATEGORY[a]] for a in V3_ACTIONS]

# zone_tag suffix -> display category. "Higiene" is the in-engine tag spelling.
ZONE_TAG_TO_CAT = {
    "PCSP.Zone.Eat": "Eat",
    "PCSP.Zone.Rest": "Rest",
    "PCSP.Zone.Work": "Work",
    "PCSP.Zone.Study": "Study",
    "PCSP.Zone.Exercise": "Exercise",
    "PCSP.Zone.Higiene": "Hygiene",
    "PCSP.Zone.Social": "Social",
    "PCSP.Zone.Leisure": "Leisure",
    "PCSP.Zone.Shop": "Shop",
    "PCSP.Zone.Observe": "Observe",
}


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
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def collect_occupancy(session: Path, n_bins: int):
    """Return (zone_cats, util[zone][bin]) mean utilisation per zone/time-bin."""
    path = session / "zone_occupancy.jsonl"
    times = [float(r["t"]) for r in _iter_jsonl(path) if "t" in r]
    if not times:
        raise SystemExit(f"No timestamps in {path}")
    t_max = max(times)
    bin_w = t_max / n_bins

    zone_cats = [ZONE_TAG_TO_CAT[t] for t in ZONE_TAG_TO_CAT]
    sums = {c: [0.0] * n_bins for c in zone_cats}
    cnts = {c: [0] * n_bins for c in zone_cats}
    for r in _iter_jsonl(path):
        tag = r.get("zone_tag")
        cat = ZONE_TAG_TO_CAT.get(tag)
        if cat is None:
            continue
        cap = float(r.get("capacity", 0)) or 1.0
        util = float(r.get("occupants", 0)) / cap
        b = min(int(float(r["t"]) / bin_w), n_bins - 1)
        sums[cat][b] += util
        cnts[cat][b] += 1

    util = {c: [sums[c][b] / cnts[c][b] if cnts[c][b] else 0.0
                for b in range(n_bins)] for c in zone_cats}
    return zone_cats, util, bin_w, t_max


def collect_intents(session: Path):
    """Aggregate preferred (mean softmax) and expressed (completed) category dists."""
    pref = [0.0] * len(V3_CATEGORIES)
    n_dec = 0
    expr = Counter()
    n_done = 0
    n_agents = 0
    for fp in sorted(session.glob("agent_p*.jsonl")):
        n_agents += 1
        for rec in _iter_jsonl(fp):
            ev = rec.get("event")
            if ev == "decision":
                logits = rec.get("logits")
                if isinstance(logits, list) and len(logits) == len(V3_ACTIONS):
                    probs = _softmax([float(x) for x in logits])
                    for ai, p in enumerate(probs):
                        pref[ACTION_IDX_TO_CAT_IDX[ai]] += p
                    n_dec += 1
            elif ev == "interaction_complete":
                cat = rec.get("category")
                if cat in CAT_INDEX:
                    expr[cat] += 1
                    n_done += 1
    pref = [p / n_dec for p in pref] if n_dec else pref
    expr_dist = [expr[c] / n_done if n_done else 0.0 for c in V3_CATEGORIES]
    return pref, expr_dist, n_dec, n_done, n_agents


def _sym_kl(p: list[float], q: list[float], eps: float = 1e-9) -> float:
    def kl(a, b):
        return sum(ai * math.log((ai + eps) / (bi + eps)) for ai, bi in zip(a, b) if ai > 0)
    return kl(p, q) + kl(q, p)


def render_heatmap(zone_cats, util, bin_w, out_path: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    order = ["Social", "Work", "Study", "Leisure", "Eat",
             "Rest", "Exercise", "Shop", "Hygiene", "Observe"]
    order = [c for c in order if c in util]
    arr = np.array([util[c] for c in order])
    n_bins = arr.shape[1]
    total_min = (n_bins * bin_w) / 60.0

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    im = ax.imshow(arr, aspect="auto", cmap="magma", vmin=0.0, vmax=1.0,
                   extent=[0, total_min, len(order), 0], interpolation="nearest")
    ax.set_yticks([i + 0.5 for i in range(len(order))])
    ax.set_yticklabels(order, fontsize=8)
    ax.set_xlabel("In-game time (min)")
    ax.set_title("Zone-capacity utilisation (64 agents, HybridPCSP)", fontsize=10)
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label("occupants / capacity", fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_expressed_vs_preferred(pref, expr, out_path: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    idx = [i for i in range(len(V3_CATEGORIES)) if pref[i] > 0.005 or expr[i] > 0.005]
    cats = [V3_CATEGORIES[i] for i in idx]
    p = [pref[i] for i in idx]
    e = [expr[i] for i in idx]
    x = np.arange(len(cats))
    w = 0.38

    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.bar(x - w / 2, p, w, label="Preferred (policy softmax)", color="#4C72B0")
    ax.bar(x + w / 2, e, w, label="Expressed (completed)", color="#C44E52")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Category probability")
    ax.set_title("Expressed vs. preferred intent under engine contention (64 agents)",
                 fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=Path)
    ap.add_argument("--n-bins", type=int, default=30)
    ap.add_argument("--fig-dir", type=Path,
                    default=Path("research/paper/figures"))
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    zone_cats, util, bin_w, t_max = collect_occupancy(args.session, args.n_bins)
    pref, expr, n_dec, n_done, n_agents = collect_intents(args.session)

    heat_path = args.fig_dir / "fig_ue5_contention_heatmap.pdf"
    evp_path = args.fig_dir / "fig_ue5_expressed_vs_preferred.pdf"
    render_heatmap(zone_cats, util, bin_w, heat_path)
    render_expressed_vs_preferred(pref, expr, evp_path)

    peak_util = {c: max(util[c]) for c in util}
    mean_util = {c: sum(util[c]) / len(util[c]) for c in util}
    gap = {V3_CATEGORIES[i]: expr[i] - pref[i] for i in range(len(V3_CATEGORIES))}
    payload = {
        "session_dir": str(args.session),
        "n_agents": n_agents,
        "n_decisions": n_dec,
        "n_interactions_completed": n_done,
        "episode_seconds": t_max,
        "n_bins": args.n_bins,
        "categories": V3_CATEGORIES,
        "preferred_dist": {V3_CATEGORIES[i]: pref[i] for i in range(len(V3_CATEGORIES))},
        "expressed_dist": {V3_CATEGORIES[i]: expr[i] for i in range(len(V3_CATEGORIES))},
        "expressed_minus_preferred": gap,
        "preferred_expressed_sym_kl": _sym_kl(pref, expr),
        "zone_peak_utilisation": peak_util,
        "zone_mean_utilisation": mean_util,
    }
    out_json = args.out_json or (Path("research/results/ue_sessions")
                                 / args.session.name / "contention_t15.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("wrote", heat_path)
    print("wrote", evp_path)
    print("wrote", out_json)
    print(f"sym-KL(preferred||expressed) = {payload['preferred_expressed_sym_kl']:.3f}")
    top_gap = sorted(gap.items(), key=lambda kv: kv[1])[:3]
    print("most-suppressed (expressed-preferred):", top_gap)


if __name__ == "__main__":
    main()
