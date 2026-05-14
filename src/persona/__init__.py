"""Persona conditioning subsystem for PCSP.

Phase 2 scope:
- ``registry``: load persona JSON, expose deterministic ids/splits.
- ``encoder``: deterministic random embeddings + cached embedding loading.
- ``projection``: persona-conditioning modules (concat, FiLM).
- ``assignment``: per-(env, slot) assignment strategies.

Phase 3+ will swap the random encoder for real LLM embeddings without
changing the trainer-side interface.
"""

from .registry import PersonaRegistry, load_personas
from .encoder import PersonaEncoder, build_encoder
from .projection import ConditioningHead, build_conditioning_head
from .assignment import PersonaAssigner, build_assigner
from .trajectory_encoder import TrajectoryEncoder, InfoNCEHead
from .splits import (
    build_population_templates,
    check_no_leakage,
    split_indices,
    split_summary,
)

__all__ = [
    "PersonaRegistry",
    "load_personas",
    "PersonaEncoder",
    "build_encoder",
    "ConditioningHead",
    "build_conditioning_head",
    "PersonaAssigner",
    "build_assigner",
    "TrajectoryEncoder",
    "InfoNCEHead",
    "build_population_templates",
    "check_no_leakage",
    "split_indices",
    "split_summary",
]
