"""
T1.4 — Long-horizon persona-persistence figure (Fig 6).

Aggregates per-minute intent-category activity from a UE5 standalone session
JSONL log and renders a 4-row activity strip for the chosen personas.

Input:  ue/cnzoi/Saved/PCSP/Logs/<stamp>/agent_p<id>_*.jsonl
Output: research/paper/cog2026_vision/figures/persona_persistence.pdf
        research/results/ue_sessions/<stamp>/persona_persistence.json

Usage:
  python research/scripts/build_persona_persistence.py \
      --session ue/cnzoi/Saved/PCSP/Logs/20260520_PERSISTENCE \
      --personas 1 9 41 58 \
      --bin-seconds 60 \
      --out-fig research/paper/cog2026_vision/figures/persona_persistence.pdf \
      --out-json research/results/ue_sessions/20260520_PERSISTENCE/persona_persistence.json

Persona selection (max-pairwise sym-KL on category distributions from the
clean training-side session research/results/ue_sessions/20260518_114841/):
  p001  Social-heavy
  p009  Rest-heavy
  p041  Observe / Study spread
  p058  Work-heavy
Min pairwise sym-KL among the four = 2.68.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

V3_CATEGORIES = [
    "Eat", "Rest", "Work", "Study", "Exercise", "Hygiene",
    "Social", "Leisure", "Shop", "Observe", "Idle",
]
CAT_INDEX = {c: i for i, c in enumerate(V3_CATEGORIES)}

# Fallback: derive intent category from the chosen action when the
# decision event predates an interaction_complete (category is "None"
# until the affordance fires; useful for high-contention agents that
# rarely complete interactions).
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

PERSONA_LABEL = {
    1:  "p001  (Social)",
    2:  "p002  (Rest/Social)",
    5:  "p005  (Social/Rest)",
    6:  "p006  (Work/Study)",
    9:  "p009  (Rest)",
    13: "p013  (Rest/Work)",
    41: "p041  (high-entropy)",
    58: "p058  (Work)",
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


def collect_persona_files(session_dir: Path, persona_ids: list[int]) -> dict[int, list[Path]]:
    out: dict[int, list[Path]] = {pid: [] for pid in persona_ids}
    for p in sorted(session_dir.glob("agent_p*.jsonl")):
        # agent_p<id>_BP_PCAPAgent_C_<n>.jsonl
        stem = p.stem
        try:
            pid = int(stem.split("_")[1][1:])
        except (IndexError, ValueError):
            continue
        if pid in out:
            out[pid].append(p)
    return out


def activity_strip_for_persona(files: list[Path], bin_seconds: float, n_bins: int) -> list[int]:
    """Per-bin dominant category index. -1 if no decisions in bin."""
    per_bin = [Counter() for _ in range(n_bins)]
    for fp in files:
        for rec in _iter_jsonl(fp):
            ev = rec.get("event")
            if ev not in ("decision", "interaction_complete"):
                continue
            cat = rec.get("category", "None")
            if cat is None or cat == "None":
                cat = ACTION_TO_CATEGORY.get(rec.get("action"))
                if cat is None:
                    continue
            ci = CAT_INDEX.get(cat)
            if ci is None:
                continue
            t = rec.get("t")
            if t is None:
                continue
            b = int(t // bin_seconds)
            if 0 <= b < n_bins:
                per_bin[b][ci] += 1
    out: list[int] = []
    for c in per_bin:
        if not c:
            out.append(-1)
        else:
            out.append(max(c.items(), key=lambda kv: kv[1])[0])
    return out


def render_figure(strips: dict[int, list[int]], persona_order: list[int],
                  bin_seconds: float, out_path: Path) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import numpy as np

    n_bins = len(next(iter(strips.values())))
    minutes = bin_seconds / 60.0
    total_min = n_bins * minutes

    # Distinct color per category (qualitative); -1 (no activity) -> light grey.
    palette = list(plt.cm.tab20.colors)[: len(V3_CATEGORIES)]
    cmap = mcolors.ListedColormap([(0.92, 0.92, 0.92)] + palette)
    bounds = list(range(-1, len(V3_CATEGORIES) + 1))
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, axes = plt.subplots(len(persona_order), 1,
                             figsize=(7.5, 0.55 * len(persona_order) + 1.4),
                             sharex=True)
    if len(persona_order) == 1:
        axes = [axes]
    for ax, pid in zip(axes, persona_order):
        arr = np.array(strips[pid])[None, :]
        ax.imshow(arr, aspect="auto", cmap=cmap, norm=norm,
                  extent=[0, total_min, 0, 1], interpolation="nearest")
        ax.set_yticks([])
        ax.set_ylabel(PERSONA_LABEL.get(pid, f"p{pid:03d}"),
                      rotation=0, ha="right", va="center", fontsize=9)
    axes[-1].set_xlabel("In-game time (min)")
    # Legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[i]) for i in range(len(V3_CATEGORIES))]
    handles.append(plt.Rectangle((0, 0), 1, 1, color=(0.92, 0.92, 0.92)))
    labels = list(V3_CATEGORIES) + ["(none)"]
    fig.legend(handles, labels, loc="lower center", ncol=6,
               bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=8)
    fig.suptitle("Long-horizon persona persistence (30-min standalone window)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True, type=Path,
                    help="UE5 PCSP log dir (contains agent_p*.jsonl)")
    ap.add_argument("--personas", type=int, nargs="+", default=[1, 9, 41, 58])
    ap.add_argument("--bin-seconds", type=float, default=60.0)
    ap.add_argument("--duration-seconds", type=float, default=1800.0)
    ap.add_argument("--out-fig", type=Path,
                    default=Path("research/paper/figures/persona_persistence.pdf"))
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    n_bins = int(args.duration_seconds // args.bin_seconds)
    files_by_pid = collect_persona_files(args.session, args.personas)
    strips: dict[int, list[int]] = {}
    for pid in args.personas:
        fs = files_by_pid.get(pid, [])
        if not fs:
            raise SystemExit(f"No JSONL found for persona {pid} in {args.session}")
        strips[pid] = activity_strip_for_persona(fs, args.bin_seconds, n_bins)

    # Persistence statistics
    stats: dict[int, dict] = {}
    for pid, strip in strips.items():
        active = [c for c in strip if c >= 0]
        cnt = Counter(active)
        total = sum(cnt.values()) or 1
        top_cat_idx, top_cat_n = cnt.most_common(1)[0] if cnt else (-1, 0)
        runs = 0
        prev = None
        for c in active:
            if c != prev:
                runs += 1
            prev = c
        stats[pid] = {
            "n_bins_active": len(active),
            "top_category": V3_CATEGORIES[top_cat_idx] if top_cat_idx >= 0 else None,
            "top_category_share": top_cat_n / total,
            "category_run_count": runs,
            "category_histogram": {V3_CATEGORIES[i]: n for i, n in cnt.items()},
        }

    render_figure(strips, args.personas, args.bin_seconds, args.out_fig)

    payload = {
        "session_dir": str(args.session),
        "personas": args.personas,
        "bin_seconds": args.bin_seconds,
        "duration_seconds": args.duration_seconds,
        "categories": V3_CATEGORIES,
        "strips": {str(pid): strips[pid] for pid in args.personas},
        "persistence_stats": {str(pid): stats[pid] for pid in args.personas},
    }
    out_json = args.out_json or (Path("research/results/ue_sessions") / args.session.name
                                 / "persona_persistence.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("wrote", args.out_fig)
    print("wrote", out_json)


if __name__ == "__main__":
    main()
