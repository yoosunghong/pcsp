"""Trajectory-analysis hooks for future Phase 5 research.

These are intentionally *lightweight* interfaces — Phase 4's spec calls
for "clean hooks/interfaces, no large analysis system yet." Each entry
point takes plain torch / numpy tensors and returns a small dict so it
can be invoked from any future analysis script without dragging in the
trainer.

The implementations marked ``_stub`` document the input/output contract
and return a minimal placeholder result. They are wired into the OOD
evaluator's ``analysis_hooks`` list so a Phase 5 researcher can replace
the stub with a real implementation without touching the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
import torch.nn.functional as F


@dataclass
class AnalysisHook:
    """Named callable invoked on a (z_traj, persona_ids, persona_table) triple.

    Hooks are pure functions of their inputs; they return a JSON-serialisable
    dict that the evaluator merges into the eval report under
    ``analysis.<hook_name>``.
    """
    name: str
    fn: Callable[[torch.Tensor, torch.Tensor, torch.Tensor], dict]


# ---- persona arithmetic ---------------------------------------------------


def persona_arithmetic(
    persona_table: torch.Tensor,
    *,
    pairs: list[tuple[int, int]] | None = None,
    ids: list[str] | None = None,
) -> dict:
    """Compute (a+b)/2 mixtures and report nearest persona ids.

    Returns: ``{pair_id: {midpoint_top1_id, midpoint_top1_cos, ...}}``.
    Pure linear algebra on the frozen persona table; no training data
    required. Phase 5 should extend this with policy-level rollouts of
    the resulting mixture embedding.
    """
    if pairs is None:
        K = persona_table.shape[0]
        pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    table_n = F.normalize(persona_table, dim=-1)
    out: dict = {}
    for i, j in pairs:
        mid = 0.5 * (persona_table[i] + persona_table[j])
        mid_n = F.normalize(mid, dim=-1)
        cos = (table_n @ mid_n).cpu().numpy()
        topk = int(np.argmax(cos))
        key = f"{i}+{j}" if ids is None else f"{ids[i]}+{ids[j]}"
        out[key] = {
            "top1_idx": topk,
            "top1_id": None if ids is None else ids[topk],
            "top1_cos": float(cos[topk]),
        }
    return out


# ---- trajectory clustering (stub) -----------------------------------------


def trajectory_clustering_stub(
    z_traj: torch.Tensor,
    persona_ids: torch.Tensor,
    persona_table: torch.Tensor,
    *,
    k: int = 4,
) -> dict:
    """Placeholder for Phase 5 KMeans / spectral clustering on z_traj.

    Returns the cluster-purity-vs-persona Rand-index-style summary using
    a single greedy-assignment baseline so a downstream researcher can
    sanity-check the interface before swapping in a real algorithm.
    """
    z = F.normalize(z_traj, dim=-1)
    # Persona centroids in z_traj's own space (avoids cross-space dim mismatch
    # between z_traj and the persona table, which can differ in dim under the
    # cached path). A real Phase 5 implementation should KMeans on z_traj.
    K = int(persona_table.shape[0])
    centroids = torch.zeros(K, z.shape[1], device=z.device, dtype=z.dtype)
    counts = torch.zeros(K, device=z.device, dtype=z.dtype)
    for i in range(z.shape[0]):
        pid = int(persona_ids[i].item())
        centroids[pid] += z[i]
        counts[pid] += 1
    nz = counts > 0
    centroids[nz] = centroids[nz] / counts[nz].unsqueeze(-1)
    centroids = F.normalize(centroids, dim=-1)
    nearest = (z @ centroids.t()).argmax(dim=-1)
    purity = (nearest == persona_ids).float().mean().item()
    return {
        "method": "nearest-centroid-in-z_traj-space (stub)",
        "k": K,
        "purity": purity,
        "note": "Replace with KMeans(z_traj, k=k) in Phase 5.",
    }


# ---- convention emergence (stub) ------------------------------------------


def convention_emergence_stub(
    z_traj: torch.Tensor,
    persona_ids: torch.Tensor,
    persona_table: torch.Tensor,
) -> dict:
    """Placeholder for cross-time analysis of group-level conventions.

    A real implementation would consume a series of ``z_traj`` snapshots
    across training and report drift of group-level centroids. Here we
    report only a one-shot population centroid + dispersion to nail down
    the interface.
    """
    z = F.normalize(z_traj, dim=-1)
    centroid = z.mean(dim=0)
    centroid = F.normalize(centroid, dim=-1)
    cos = (z @ centroid).cpu().numpy()
    return {
        "centroid_cos_mean": float(cos.mean()),
        "centroid_cos_std": float(cos.std()),
        "n_trajectories": int(z.shape[0]),
        "note": "Phase 5 should track centroid drift across training checkpoints.",
    }


# ---- latent trajectory projection (stub) ----------------------------------


def latent_trajectory_projection_stub(
    z_traj: torch.Tensor,
    persona_ids: torch.Tensor,
    persona_table: torch.Tensor,
) -> dict:
    """Placeholder for PCA / UMAP projection of z_traj for plotting.

    Returns the first 2 PCs (via torch.pca_lowrank) so a downstream
    notebook can build a scatter without re-implementing the projection
    in three places.
    """
    n = z_traj.shape[0]
    q = min(2, max(1, z_traj.shape[1]))
    if n < 2:
        return {"method": "pca_lowrank", "components": [], "n": n}
    try:
        _, _, V = torch.pca_lowrank(z_traj, q=q)
        proj = (z_traj @ V).cpu().numpy().tolist()
    except RuntimeError:
        proj = []
    return {
        "method": "pca_lowrank",
        "q": q,
        "projection": proj[:256],          # cap dump size
        "persona_ids": persona_ids.cpu().tolist()[:256],
        "note": "Cap of 256 trajectories per dump. Phase 5 should swap in UMAP.",
    }


DEFAULT_ANALYSIS_HOOKS: list[AnalysisHook] = [
    AnalysisHook("trajectory_clustering", trajectory_clustering_stub),
    AnalysisHook("convention_emergence", convention_emergence_stub),
    AnalysisHook("latent_projection", latent_trajectory_projection_stub),
]
