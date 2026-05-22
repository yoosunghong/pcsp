"""Generate fig_ue5_ablation.pdf — Phase 4 runtime ablation bars."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
ABL = ROOT / "results/ue_sessions/ablation_20260518_154827/ablation.json"
OUT = ROOT / "paper/cog2026_main/figures/fig_ue5_ablation.pdf"

data = json.loads(ABL.read_text())
order = ["HybridPCSP", "BTOnly", "HybridNoPersona"]
m = {row["policy_mode"]: row for row in data["modes"]}
modes = [m[k] for k in order]

labels = ["Hybrid\nPCSP", "BT\nOnly", "Hybrid\nNoPersona"]
nint = [r["n_interactions"] for r in modes]
fail = [r["failure_rate"] * 100 for r in modes]
reward = [r["reward_sum"] for r in modes]
rho = [r["inter_persona_rho_mean"] for r in modes]
colors = ["#2ca02c", "#d62728", "#ff7f0e"]

fig, axes = plt.subplots(1, 4, figsize=(8.5, 2.4))
metrics = [
    (nint, "Interactions", None),
    (fail, "Failure rate (%)", None),
    (reward, "Reward sum", None),
    (rho, r"Inter-persona $\rho$", (0, 1.05)),
]
for ax, (vals, title, ylim) in zip(axes, metrics):
    bars = ax.bar(labels, vals, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_title(title, fontsize=10)
    if ylim:
        ax.set_ylim(*ylim)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                f"{v:.2f}" if v < 10 else f"{v:.0f}",
                ha="center", va="bottom", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

fig.tight_layout()
fig.savefig(OUT, bbox_inches="tight")
print(f"wrote {OUT}")
