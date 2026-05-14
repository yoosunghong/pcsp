"""Evaluation utilities for the Melting Pot PCSP stack (Phase 4)."""

from .ood import OODEvalConfig, run_ood_eval
from .analysis import (
    AnalysisHook,
    persona_arithmetic,
    trajectory_clustering_stub,
    convention_emergence_stub,
    latent_trajectory_projection_stub,
)

__all__ = [
    "OODEvalConfig",
    "run_ood_eval",
    "AnalysisHook",
    "persona_arithmetic",
    "trajectory_clustering_stub",
    "convention_emergence_stub",
    "latent_trajectory_projection_stub",
]
