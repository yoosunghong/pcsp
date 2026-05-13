"""Re-render the designer-persona t-SNE in the *projected* persona space.

Loads the trained PCSP-v3 full policy, projects both the 240 Korean training
personas and the 50 English designer personas through the learned LoRA
projection, then runs t-SNE on the combined 64-dim embeddings. Saves both the
projection-space plot and (for reference) the raw-embedding plot side-by-side.

Usage:
    conda run -n paper python scripts/visualize_designer_tsne_projected.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.manifold import TSNE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.training.pcsp_trainer import PCSPActorCritic

OBS_DIM_V3_BASE = 33
N_ACTIONS_V3 = 20

SOURCE_STYLES: dict[str, dict] = {
    "The Sims 3":              {"color": "#D62728", "marker": "*", "size": 110, "label": "The Sims 3"},
    "Animal Crossing":         {"color": "#2CA02C", "marker": "o", "size": 70,  "label": "Animal Crossing"},
    "Stardew Valley":          {"color": "#1F77B4", "marker": "s", "size": 70,  "label": "Stardew Valley"},
    "Persona Series":          {"color": "#9467BD", "marker": "^", "size": 80,  "label": "Persona Series"},
    "Original Designer Brief": {"color": "#FF7F0E", "marker": "D", "size": 65,  "label": "Original brief"},
}


def run_tsne(matrix: np.ndarray, perplexity: int = 30) -> np.ndarray:
    try:
        tsne = TSNE(
            n_components=2,
            perplexity=perplexity,
            init="pca",
            learning_rate="auto",
            max_iter=1500,
            random_state=42,
        )
    except TypeError:
        tsne = TSNE(
            n_components=2,
            perplexity=perplexity,
            init="pca",
            learning_rate="auto",
            n_iter=1500,
            random_state=42,
        )
    return tsne.fit_transform(matrix.astype(np.float32))


def plot_tsne(
    ax,
    coords: np.ndarray,
    n_train: int,
    designer_records: list[dict],
    title: str,
) -> None:
    train_xy = coords[:n_train]
    designer_xy = coords[n_train:]

    ax.scatter(
        train_xy[:, 0], train_xy[:, 1],
        s=26, c="#B7B7B7", alpha=0.55, edgecolors="none", label="train_240_v3",
    )
    by_source: dict[str, list[int]] = {}
    for idx, rec in enumerate(designer_records):
        by_source.setdefault(rec["source"], []).append(idx)
    for source, idxs in by_source.items():
        style = SOURCE_STYLES.get(source, {"color": "#000", "marker": "x", "size": 60, "label": source})
        pts = designer_xy[idxs]
        ax.scatter(
            pts[:, 0], pts[:, 1],
            s=style["size"], c=style["color"], marker=style["marker"],
            edgecolors="black", linewidths=0.5,
            label=f"{style['label']} (n={len(idxs)})", zorder=4, alpha=0.92,
        )
    x_pad = (float(coords[:, 0].max()) - float(coords[:, 0].min())) * 0.06
    y_pad = (float(coords[:, 1].max()) - float(coords[:, 1].min())) * 0.08
    ax.set_xlim(float(coords[:, 0].min()) - x_pad, float(coords[:, 0].max()) + x_pad * 1.6)
    ax.set_ylim(float(coords[:, 1].min()) - y_pad, float(coords[:, 1].max()) + y_pad)
    ax.set_title(title)
    ax.set_xlabel("t-SNE dim 1")
    ax.set_ylabel("t-SNE dim 2")
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.85)


def coverage_stats(coords: np.ndarray, n_train: int) -> dict:
    """Quick numeric summary of how much designer points sit inside train hull."""
    train_xy = coords[:n_train]
    designer_xy = coords[n_train:]
    nn_dists = []
    for d in designer_xy:
        dists = np.linalg.norm(train_xy - d, axis=1)
        nn_dists.append(float(dists.min()))
    pairwise_train = []
    for i in range(min(n_train, 200)):
        dists = np.linalg.norm(train_xy - train_xy[i], axis=1)
        dists = dists[dists > 0]
        if dists.size:
            pairwise_train.append(float(dists.min()))
    return {
        "designer_nn_to_train_mean": float(np.mean(nn_dists)),
        "designer_nn_to_train_median": float(np.median(nn_dists)),
        "train_pairwise_nn_mean": float(np.mean(pairwise_train)),
        "ratio": float(np.mean(nn_dists) / np.mean(pairwise_train)),
    }


def main() -> None:
    case_dir = ROOT / "results" / "designer_persona_case_study"
    train_personas = json.loads((ROOT / "data/personas/train_240_v3.json").read_text(encoding="utf-8"))
    all_train_raw = np.load(ROOT / "results/embeddings/persona_embeddings_300.npy").astype(np.float32)
    train_indices = [int(p["id"]) - 1 for p in train_personas]
    train_raw = all_train_raw[train_indices]
    train_raw = train_raw / np.linalg.norm(train_raw, axis=1, keepdims=True)

    designer_records = json.loads((case_dir / "designer_personas.json").read_text(encoding="utf-8"))
    designer_raw = np.load(case_dir / "designer_persona_embeddings.npy").astype(np.float32)

    # ------------------------------------------------------------------
    # Project both sets through the trained PCSP-v3 full LoRA projection.
    # ------------------------------------------------------------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy = PCSPActorCritic(OBS_DIM_V3_BASE, N_ACTIONS_V3)
    policy.load_state_dict(
        torch.load(ROOT / "results/pcsp_v3/full/policy.pt", map_location="cpu", weights_only=True)
    )
    policy = policy.to(device).eval()

    with torch.no_grad():
        train_proj = policy.persona_proj(
            torch.tensor(train_raw, dtype=torch.float32, device=device)
        ).cpu().numpy()
        designer_proj = policy.persona_proj(
            torch.tensor(designer_raw, dtype=torch.float32, device=device)
        ).cpu().numpy()

    # ------------------------------------------------------------------
    # t-SNE in raw 1024-dim vs projected 64-dim space.
    # ------------------------------------------------------------------
    raw_matrix = np.vstack([train_raw, designer_raw])
    proj_matrix = np.vstack([train_proj, designer_proj])
    print("Running t-SNE on raw (1024-dim)...")
    raw_coords = run_tsne(raw_matrix)
    print("Running t-SNE on projected (64-dim)...")
    proj_coords = run_tsne(proj_matrix)

    n_train = len(train_personas)
    raw_stats = coverage_stats(raw_coords, n_train)
    proj_stats = coverage_stats(proj_coords, n_train)
    print("Raw-embedding coverage stats:", raw_stats)
    print("Projected coverage stats:   ", proj_stats)

    np.save(case_dir / "tsne_coords_train240_plus_designer_projected.npy", proj_coords.astype(np.float32))

    # ------------------------------------------------------------------
    # Side-by-side figure for the paper.
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    plot_tsne(
        axes[0], raw_coords, n_train, designer_records,
        title="(a) Raw Qwen3 embeddings (1024-dim)",
    )
    plot_tsne(
        axes[1], proj_coords, n_train, designer_records,
        title="(b) Learned LoRA projection (64-dim)",
    )
    fig.suptitle(
        "Persona embedding space: train_240 (Korean) + 50 designer-authored (English)",
        fontsize=12,
    )
    fig.tight_layout()
    side_path = ROOT / "paper/figures/fig5_designer_personas_tsne.png"
    fig.savefig(side_path, dpi=170, bbox_inches="tight")
    fig.savefig(case_dir / "designer_personas_tsne_sidebyside.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved side-by-side figure to: {side_path}")

    # Also save the projected-only plot in the case-study dir for inspection.
    fig2, ax2 = plt.subplots(figsize=(10, 8))
    plot_tsne(
        ax2, proj_coords, n_train, designer_records,
        title="LoRA-projected (64-dim) persona embeddings: train_240_v3 + designer-authored",
    )
    fig2.tight_layout()
    fig2.savefig(case_dir / "designer_personas_tsne_projected.png", dpi=170, bbox_inches="tight")
    plt.close(fig2)

    summary = {
        "raw": raw_stats,
        "projected": proj_stats,
        "n_train": n_train,
        "n_designer": len(designer_records),
    }
    (case_dir / "tsne_coverage_stats.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
