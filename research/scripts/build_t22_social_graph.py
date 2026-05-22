"""
T2.2 — Social-graph emergence in UE5 (Layer-3, §7.7, Fig 7).

Builds a co-interaction graph across the 64 persona-conditioned agents of a
single HybridPCSP PIE session. There is no explicit "partner" field in the
logs, so co-presence is reconstructed from per-agent zone-occupancy intervals:
each (decision -> interaction_complete) pair places an agent in one zone
category for the interval [t_decision, t_complete], with the realised
interaction point recorded as the completion position. Two agents are
co-present when their intervals overlap in the same zone category *and* their
interaction points are within --radius world units of each other (same/adjacent
seat, not merely the same large zone). Same-zone-category alone yields a
near-complete graph because a single zone holds up to ~36 agents; the proximity
gate isolates genuine co-location. The edge weight is the total overlap in
seconds summed over all such co-located pairs across the run.

Nodes are coloured by behavioural archetype (each agent's modal expressed
category). The scientific question is whether persona-conditioned routine
choice produces non-random social structure — e.g. archetype assortativity —
rather than a uniform mixing graph. Even weak structure is reportable; the
analysis itself is the Layer-3 maturity signal called for in the revision plan.

Inputs:
  ue/cnzoi/Saved/PCSP/Logs/<stamp>/agent_p*.jsonl   (decision + interaction_complete)

Outputs:
  research/paper/figures/fig_ue5_social_graph.{pdf,png}
  research/results/ue_sessions/<stamp>/social_graph_t22.json

Usage:
  python research/scripts/build_t22_social_graph.py \
      --session ue/cnzoi/Saved/PCSP/Logs/20260520_013551
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

V3_CATEGORIES = [
    "Eat", "Rest", "Work", "Study", "Exercise", "Hygiene",
    "Social", "Leisure", "Shop", "Observe", "Idle",
]

# Stable per-archetype colours (matches the §7.6 figure palette family).
ARCHETYPE_COLORS = {
    "Eat": "#8C613C", "Rest": "#4C72B0", "Work": "#55A868",
    "Study": "#C44E52", "Exercise": "#DD8452", "Hygiene": "#64B5CD",
    "Social": "#CC79A7", "Leisure": "#937860", "Shop": "#DA8BC3",
    "Observe": "#8172B3", "Idle": "#999999",
}

_PERSONA_RE = re.compile(r"agent_p(\d+)_")


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


def collect_intervals(session: Path):
    """Return (intervals, archetype, decisions, completions) per persona.

    intervals[pid] = list of (t_start, t_end, zone_category, (x, y)).
    A decision marks departure toward a zone; the next interaction_complete in
    the same agent file resolves the realised zone, finish time, and the
    interaction-point position.
    """
    intervals: dict[str, list[tuple[float, float, str, tuple[float, float]]]] = {}
    archetype: dict[str, str] = {}
    n_completions: dict[str, int] = {}

    for fp in sorted(session.glob("agent_p*.jsonl")):
        m = _PERSONA_RE.search(fp.name)
        if not m:
            continue
        pid = f"p{int(m.group(1)):03d}"
        ivs: list[tuple[float, float, str, tuple[float, float]]] = []
        expr = Counter()
        pending_decision_t: float | None = None
        for rec in _iter_jsonl(fp):
            ev = rec.get("event")
            if ev == "decision":
                # Keep the earliest un-resolved decision time as interval start.
                if pending_decision_t is None:
                    pending_decision_t = float(rec.get("t", 0.0))
            elif ev == "interaction_complete":
                cat = rec.get("category")
                t_end = float(rec.get("t", 0.0))
                t_start = pending_decision_t if pending_decision_t is not None else t_end
                pending_decision_t = None
                pos = rec.get("pos")
                if (cat in V3_CATEGORIES and t_end >= t_start
                        and isinstance(pos, list) and len(pos) >= 2):
                    ivs.append((t_start, t_end, cat, (float(pos[0]), float(pos[1]))))
                    expr[cat] += 1
        intervals[pid] = ivs
        n_completions[pid] = sum(expr.values())
        archetype[pid] = expr.most_common(1)[0][0] if expr else "Idle"
    return intervals, archetype, n_completions


def build_edges(intervals, radius: float):
    """Co-located co-presence edges.

    Two intervals form (a fraction of) an edge when they share a zone category,
    their time windows overlap, AND their interaction points lie within `radius`
    world units. Edge weight is summed overlap seconds. Returns
    dict[(pid_a, pid_b)] -> {"overlap_s": float, "events": int}.
    Per-category sweep keeps the cost near-linear in interval count.
    """
    by_cat = defaultdict(list)
    for pid, ivs in intervals.items():
        for (s, e, c, p) in ivs:
            by_cat[c].append((s, e, pid, p))

    r2 = radius * radius
    edges: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"overlap_s": 0.0, "events": 0}
    )
    for cat, ivs in by_cat.items():
        ivs.sort(key=lambda x: x[0])
        active: list[tuple[float, float, str, tuple[float, float]]] = []
        for (s, e, pid, p) in ivs:
            active = [a for a in active if a[1] > s]
            for (s2, e2, pid2, p2) in active:
                if pid2 == pid:
                    continue
                if (p[0] - p2[0]) ** 2 + (p[1] - p2[1]) ** 2 > r2:
                    continue
                ov = min(e, e2) - max(s, s2)
                if ov > 0:
                    key = tuple(sorted((pid, pid2)))
                    edges[key]["overlap_s"] += ov
                    edges[key]["events"] += 1
            active.append((s, e, pid, p))
    return edges


def graph_stats(nodes, edges, archetype):
    import networkx as nx

    g = nx.Graph()
    for n in nodes:
        g.add_node(n, archetype=archetype.get(n, "Idle"))
    for (a, b), w in edges.items():
        g.add_edge(a, b, weight=w["overlap_s"], events=w["events"])

    stats = {
        "n_nodes": g.number_of_nodes(),
        "n_edges": g.number_of_edges(),
        "density": nx.density(g),
        "mean_degree": (2 * g.number_of_edges() / g.number_of_nodes())
        if g.number_of_nodes() else 0.0,
    }
    try:
        stats["archetype_assortativity"] = nx.attribute_assortativity_coefficient(
            g, "archetype"
        )
    except Exception:
        stats["archetype_assortativity"] = None
    try:
        comms = nx.community.greedy_modularity_communities(g, weight="weight")
        stats["modularity"] = nx.community.modularity(g, comms, weight="weight")
        stats["n_communities"] = len(comms)
    except Exception:
        stats["modularity"] = None
        stats["n_communities"] = None
    return g, stats


def render_graph(g, archetype, out_path: Path):
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import networkx as nx

    weights = [g[u][v]["weight"] for u, v in g.edges()]
    wmax = max(weights) if weights else 1.0
    pos = nx.spring_layout(g, weight="weight", seed=0, k=0.9, iterations=200)

    present = [a for a in V3_CATEGORIES
               if any(archetype.get(n) == a for n in g.nodes())]
    node_colors = [ARCHETYPE_COLORS.get(archetype.get(n, "Idle"), "#999999")
                   for n in g.nodes()]
    degrees = dict(g.degree(weight="weight"))
    dmax = max(degrees.values()) if degrees else 1.0
    node_sizes = [60 + 340 * (degrees[n] / dmax) for n in g.nodes()]

    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    for (u, v) in g.edges():
        w = g[u][v]["weight"]
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color="#555555", alpha=0.06 + 0.5 * (w / wmax),
                linewidth=0.3 + 2.2 * (w / wmax), zorder=1)
    nx.draw_networkx_nodes(g, pos, node_color=node_colors, node_size=node_sizes,
                           linewidths=0.4, edgecolors="white", ax=ax)
    ax.set_title("Co-interaction graph (64 agents, HybridPCSP)\n"
                 "edge = shared-zone overlap, node colour = behavioural archetype",
                 fontsize=10)
    handles = [mpatches.Patch(color=ARCHETYPE_COLORS[a], label=a) for a in present]
    ax.legend(handles=handles, frameon=False, fontsize=7, ncol=2,
              loc="lower left", bbox_to_anchor=(0.0, -0.02))
    ax.axis("off")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=Path)
    ap.add_argument("--radius", type=float, default=250.0,
                    help="co-location radius (world units); 250 ~ same seat")
    ap.add_argument("--radius-sweep", type=float, nargs="*",
                    default=[250.0, 400.0, 600.0],
                    help="radii reported in the robustness sweep")
    ap.add_argument("--fig-dir", type=Path, default=Path("research/paper/figures"))
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    intervals, archetype, n_completions = collect_intervals(args.session)
    edges = build_edges(intervals, args.radius)
    nodes = sorted(intervals.keys())
    g, stats = graph_stats(nodes, edges, archetype)

    fig_path = args.fig_dir / "fig_ue5_social_graph.pdf"
    render_graph(g, archetype, fig_path)

    arch_counts = Counter(archetype[n] for n in nodes)
    top_pairs = sorted(
        ({"pair": list(k), "overlap_s": round(v["overlap_s"], 1),
          "events": v["events"],
          "same_archetype": archetype[k[0]] == archetype[k[1]]}
         for k, v in edges.items()),
        key=lambda d: d["overlap_s"], reverse=True,
    )[:10]
    same_arch_edges = sum(1 for k in edges if archetype[k[0]] == archetype[k[1]])

    # Robustness: assortativity / same-archetype fraction vs co-location radius.
    radius_sweep = []
    for r in args.radius_sweep:
        e_r = build_edges(intervals, r)
        _, s_r = graph_stats(nodes, e_r, archetype)
        sa = sum(1 for k in e_r if archetype[k[0]] == archetype[k[1]])
        radius_sweep.append({
            "radius": r,
            "n_edges": s_r["n_edges"],
            "density": round(s_r["density"], 4),
            "archetype_assortativity": s_r["archetype_assortativity"],
            "same_archetype_edge_fraction": (sa / len(e_r)) if e_r else 0.0,
        })

    payload = {
        "session_dir": str(args.session),
        "colocation_radius": args.radius,
        "n_agents": len(nodes),
        "total_completions": sum(n_completions.values()),
        "graph": stats,
        "archetype_counts": dict(arch_counts),
        "same_archetype_edge_fraction": (same_arch_edges / len(edges)) if edges else 0.0,
        "radius_sweep": radius_sweep,
        "node_archetype": archetype,
        "top_co_interaction_pairs": top_pairs,
    }
    out_json = args.out_json or (Path("research/results/ue_sessions")
                                 / args.session.name / "social_graph_t22.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("wrote", fig_path)
    print("wrote", out_json)
    print(f"nodes={stats['n_nodes']} edges={stats['n_edges']} "
          f"density={stats['density']:.3f} mean_deg={stats['mean_degree']:.2f}")
    print(f"archetype assortativity = {stats['archetype_assortativity']}")
    print(f"modularity = {stats['modularity']} "
          f"communities = {stats['n_communities']}")
    print(f"same-archetype edge fraction = "
          f"{payload['same_archetype_edge_fraction']:.3f}")


if __name__ == "__main__":
    main()
