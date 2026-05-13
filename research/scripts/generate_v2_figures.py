"""
Phase 7 — 결과 그림 생성

그림 1 (fig_v2_comparison.pdf):
  v1 (6×6, 4 agents) vs v2 (12×12, 16 agents) 핵심 지표 비교
  (PCSP full 기준, 4개 메트릭)

그림 2 (fig_v2_ablation.pdf):
  v2 환경에서의 ablation (full / no_consist / no_diverse / concat)

Usage:
  conda run -n paper python scripts/generate_v2_figures.py
"""
from __future__ import annotations

import json
import sys
import pathlib

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT     = pathlib.Path(__file__).resolve().parents[1]
V1_EVAL  = ROOT / "results" / "eval"  / "comparison.json"
V2_EVAL  = ROOT / "results" / "v2" / "eval" / "comparison_v2.json"
FIG_DIR  = ROOT / "results" / "v2" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Use same style as existing figures (no Korean font needed for English labels)
plt.rcParams.update({
    "figure.dpi":   150,
    "font.size":    10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
})


def load_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return None
    with open(path) as f:
        return json.load(f)


# ── Figure 1: v1 vs v2 scale comparison ───────────────────────────────────────

def fig_scale_comparison(v1_data: dict, v2_data: dict) -> None:
    """4-panel bar chart: v1 PCSP full vs v2 PCSP full on key metrics."""

    metrics = [
        ("reward_mean",   "Episode Reward",        False),
        ("zeroshot_acc",  "Zero-shot Acc",          False),
        ("mean_kl",       "Behavioral KL",          False),
        ("spearman_rho",  r"Spearman $\rho$",       False),
    ]

    # Extract v1 full values (from Phase 5 comparison.json — list of dicts)
    def get_v1(key: str) -> float:
        if isinstance(v1_data, list):
            entry = next((d for d in v1_data if d.get("model") in ("PCSP (full)", "full")), {})
        else:
            entry = v1_data.get("PCSP (full)", v1_data.get("full", {}))
        # v1 uses nested sub-dicts; extract scalar values
        nested = {
            "reward_mean":  lambda e: e.get("reward", {}).get("mean", float("nan")),
            "zeroshot_acc": lambda e: e.get("zeroshot", {}).get("accuracy", float("nan")),
            "mean_kl":      lambda e: e.get("diversity", {}).get("mean_kl", float("nan")),
            "spearman_rho": lambda e: e.get("diversity", {}).get("spearman_rho", float("nan")),
        }
        if key in nested:
            return float(nested[key](entry))
        return float(entry.get(key, float("nan")))

    def get_v2(key: str) -> float:
        entry = v2_data.get("full", {})
        return float(entry.get(key, float("nan")))

    fig, axes = plt.subplots(1, 4, figsize=(12, 3.5))
    colors = ["#4878CF", "#D65F5F"]
    labels = ["v1 (6×6, 4 agents)", "v2 (12×12, 16 agents)"]

    for ax, (key, title, _) in zip(axes, metrics):
        v1_val = get_v1(key)
        v2_val = get_v2(key)
        bars   = ax.bar([0, 1], [v1_val, v2_val], color=colors, width=0.5,
                        edgecolor="black", linewidth=0.7)
        ax.set_title(title, fontweight="bold")
        ax.set_xticks([])
        ax.set_xlim(-0.5, 1.5)
        # Value labels on bars
        for bar, val in zip(bars, [v1_val, v2_val]):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01 * ax.get_ylim()[1],
                        f"{val:.2f}", ha="center", va="bottom", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    legend_patches = [mpatches.Patch(color=c, label=l) for c, l in zip(colors, labels)]
    fig.legend(handles=legend_patches, loc="lower center", ncol=2, fontsize=9,
               bbox_to_anchor=(0.5, -0.05))
    fig.suptitle("PCSP Scale-Up: v1 → v2 (full model)", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])

    out = FIG_DIR / "fig_v2_comparison.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Figure 2: v2 ablation bar chart ───────────────────────────────────────────

def fig_v2_ablation(v2_data: dict) -> None:
    """Grouped bar chart: 4 metrics × 4 models."""

    modes   = ["full", "no_consist", "no_diverse", "concat"]
    metrics = [
        ("reward_mean",  "Reward"),
        ("zeroshot_acc", "Zero-shot Acc"),
        ("mean_kl",      "Behavioral KL"),
        ("spearman_rho", r"Spearman $\rho$"),
    ]

    present = [m for m in modes if m in v2_data]
    if not present:
        print("  [SKIP] No v2 ablation data found")
        return

    x      = np.arange(len(metrics))
    width  = 0.18
    cmap   = ["#4878CF", "#F0A500", "#E87722", "#6BAA75"]
    fig, ax = plt.subplots(figsize=(10, 4))

    for k, mode in enumerate(present):
        vals = [float(v2_data[mode].get(mkey, float("nan"))) for mkey, _ in metrics]
        offset = (k - len(present) / 2 + 0.5) * width
        bars   = ax.bar(x + offset, vals, width, label=mode,
                        color=cmap[k], edgecolor="black", linewidth=0.5)
        for bar, val in zip(bars, vals):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.005,
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=7, rotation=45)

    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in metrics])
    ax.set_title("PCSP v2 Ablation Study (12×12, 16 agents, 500 personas)",
                 fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    out = FIG_DIR / "fig_v2_ablation.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ── Figure 3: learning curves from training metrics ───────────────────────────

def fig_v2_learning_curves() -> None:
    """Reward + consistency_loss curves for v2 training."""
    metrics_dir = ROOT / "results" / "v2" / "pcsp"
    modes_colors = {
        "full":       "#4878CF",
        "no_consist": "#F0A500",
        "no_diverse": "#E87722",
        "concat":     "#6BAA75",
    }

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    any_plotted = False

    for mode, color in modes_colors.items():
        metrics_path = metrics_dir / mode / "metrics.json"
        if not metrics_path.exists():
            continue
        with open(metrics_path) as f:
            data = json.load(f)
        ms = data.get("metrics", [])
        if not ms:
            continue

        iters   = [m["iteration"]      for m in ms]
        rewards = [m["mean_ep_reward"] for m in ms]
        conloss = [m["consistency_loss"] for m in ms]

        axes[0].plot(iters, rewards, color=color, label=mode, linewidth=1.5)
        axes[1].plot(iters, conloss, color=color, label=mode, linewidth=1.5)
        any_plotted = True

    if not any_plotted:
        print("  [SKIP] No v2 training metrics found")
        plt.close(fig)
        return

    axes[0].set_title("Episode Reward",     fontweight="bold")
    axes[1].set_title("Consistency Loss",   fontweight="bold")
    for ax in axes:
        ax.set_xlabel("Iteration")
        ax.legend(fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("PCSP v2 Learning Curves (12×12, 16 agents)", fontweight="bold")
    fig.tight_layout()
    out = FIG_DIR / "fig_v2_learning_curves.pdf"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


def main():
    print("Generating Phase 7 figures ...")

    v1_data = load_json(V1_EVAL)
    v2_data = load_json(V2_EVAL)

    if v1_data and v2_data:
        print("  Figure 1: v1 vs v2 scale comparison")
        fig_scale_comparison(v1_data, v2_data)
    else:
        print("  [SKIP] Figure 1: need both v1 and v2 eval results")

    if v2_data:
        print("  Figure 2: v2 ablation")
        fig_v2_ablation(v2_data)
    else:
        print("  [SKIP] Figure 2: need v2 eval results")

    print("  Figure 3: v2 learning curves")
    fig_v2_learning_curves()

    print("Done.")


if __name__ == "__main__":
    main()
