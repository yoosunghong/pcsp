"""Generate the three workshop-paper figures.

Figure 1: cross-substrate seed-level mean_pair_kl (H1, §4)
Figure 2: bimodality histogram of cH and PD per-seed full top-1 (H3, §5.1)
Figure 3: persona-cosine vs per-persona heldout top-1 (embedding-margin, §5.2)

Run:
    python research/paper/neurips2026_workshop_meltingpot/figures/make_figures.py
Outputs:
    fig1_h1_cross_substrate.pdf
    fig2_bimodality.pdf
    fig3_embedding_margin.pdf
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT_DIR = Path(__file__).parent
plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
})

REPO = Path(__file__).resolve().parents[4]


# --------------------------------------------------------------------- F1
def _train_random_mpk_from_summary(path: Path, run_filter=None) -> list[float]:
    data = json.load(path.open())["summaries"]
    out = []
    for s in data:
        if run_filter and not run_filter(s):
            continue
        for r in s["ood"]:
            if r["tag"] == "train/random/None":
                out.append(r["mean_pair_kl"])
    return out


def _train_random_mpk_from_run_dirs(parent_dir: Path) -> list[float]:
    out = []
    for run in sorted(parent_dir.iterdir()):
        s = run / "ood_evals" / "summary.json"
        if not s.exists():
            continue
        for r in json.load(s.open()):
            if r["pass"] == "train/random/None":
                out.append(r["mean_pair_kl"])
    return out


def figure_1():
    cH = _train_random_mpk_from_summary(
        REPO / "research/meltingpot/phase5_qwen_summary.json",
        run_filter=lambda s: s["mode"] == "full",
    )
    pd = _train_random_mpk_from_summary(
        REPO / "research/meltingpot/phase5_pd_summary.json",
        run_filter=lambda s: "poolfull" in s["run"],
    )
    stag = _train_random_mpk_from_run_dirs(
        REPO / "research/meltingpot/runs/phase5_stag_anchor"
    )
    # Restrict stag to the 3 1000k seeds used in the paper
    stag = [v for v in stag if v is not None]

    fig, ax = plt.subplots(figsize=(4.0, 2.6))

    data = [
        ("commons_harvest__open\n(CPR)", cH, "tab:blue"),
        ("prisoners_dilemma_in_the_matrix\n(mixed-motive)", pd, "tab:orange"),
        ("stag_hunt_in_the_matrix\n(coordination)", stag, "tab:green"),
    ]

    rng = np.random.default_rng(0)
    for i, (label, vals, color) in enumerate(data):
        x = i + (rng.random(len(vals)) - 0.5) * 0.15
        ax.scatter(x, vals, color=color, s=42, alpha=0.85, edgecolor="black",
                   linewidth=0.5, zorder=3, label=f"n={len(vals)}")
        m = np.mean(vals)
        ax.hlines(m, i - 0.18, i + 0.18, color=color, linewidth=2.0, zorder=2)

    ax.set_xticks(range(len(data)))
    ax.set_xticklabels([d[0] for d in data])
    ax.set_ylabel("mean pairwise action-KL\n(train/random pass)")
    ax.set_title("H1 — Cross-substrate behavioral divergence")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)

    out = OUT_DIR / "fig1_h1_cross_substrate.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


# --------------------------------------------------------------------- F2
# Source: PHASE5_REPORT.md §12.4 (n=8 raw full top-1 values).
CH_TOP1 = [0.000, 0.000, 0.143, 0.554, 0.554, 0.554, 0.554, 0.554]
PD_TOP1 = [0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.438, 0.438]


def figure_2():
    fig, axes = plt.subplots(1, 2, figsize=(5.5, 2.4), sharey=True)

    bins = np.linspace(-0.05, 0.65, 15)
    for ax, vals, title, color in [
        (axes[0], CH_TOP1, "commons_harvest__open  (n=8)", "tab:blue"),
        (axes[1], PD_TOP1, "prisoners_dilemma  (n=8)", "tab:orange"),
    ]:
        ax.hist(vals, bins=bins, color=color, edgecolor="black", linewidth=0.5)
        ax.axvline(0.083, color="gray", linestyle=":", linewidth=1, label="chance top-1 (0.083)")
        ax.set_xlabel("full top-1 (heldout/random pass)")
        ax.set_title(title)
        ax.set_xlim(-0.05, 0.65)
        ax.legend(loc="upper center", framealpha=0.9)

    axes[0].set_ylabel("seeds")
    fig.suptitle("Bimodal two-attractor distribution (H3, n=8 per substrate)", y=1.02)
    out = OUT_DIR / "fig2_bimodality.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


# --------------------------------------------------------------------- F3
# Source: PHASE5_REPORT.md §12.5 + persona embedding cosine table.
EMB_MARGIN_DATA = [
    # (substrate, persona, cos_to_nearest_train, mean_top1, n_at_1, n_seeds)
    ("commons_harvest__open", "fast_mover", 0.342, 0.653, 5, 8),
    ("commons_harvest__open", "spinner",    0.554, 0.005, 0, 8),
    ("prisoners_dilemma",     "fast_mover", 0.342, 0.250, 2, 8),
    ("prisoners_dilemma",     "spinner",    0.554, 0.000, 0, 8),
]


def figure_3():
    fig, ax = plt.subplots(figsize=(4.2, 2.8))

    markers = {"commons_harvest__open": "o", "prisoners_dilemma": "s"}
    colors = {"fast_mover": "tab:green", "spinner": "tab:red"}

    for sub, persona, cos, mean_top1, n_at_1, n in EMB_MARGIN_DATA:
        ax.scatter(cos, mean_top1, s=180, marker=markers[sub],
                   color=colors[persona], edgecolor="black", linewidth=0.7,
                   alpha=0.9, zorder=3)
        ax.annotate(f"{persona}\n({n_at_1}/{n} seeds at 1.0)",
                    xy=(cos, mean_top1), xytext=(8, 6),
                    textcoords="offset points", fontsize=7)

    # Chance line (12-vocab top-1)
    ax.axhline(0.083, color="gray", linestyle=":", linewidth=1, label="chance top-1 (0.083)")

    ax.set_xlabel("Qwen3 cosine to nearest training persona")
    ax.set_ylabel("mean held-out top-1 (n=8)")
    ax.set_title("Embedding-margin condition")
    ax.set_xlim(0.30, 0.62)
    ax.set_ylim(-0.05, 0.85)
    ax.grid(alpha=0.3)

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
                   markeredgecolor="black", markersize=10, label="commons_harvest"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="white",
                   markeredgecolor="black", markersize=10, label="prisoners_dilemma"),
        plt.Line2D([0], [0], linestyle=":", color="gray", label="chance"),
    ]
    ax.legend(handles=legend_handles, loc="upper right")

    out = OUT_DIR / "fig3_embedding_margin.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


# ---------------------------------------------------------------------
if __name__ == "__main__":
    figure_1()
    figure_2()
    figure_3()
