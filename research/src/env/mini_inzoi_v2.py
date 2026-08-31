"""Mini-Inzoi v2: 12x12 world with 16 agents."""
from __future__ import annotations

from .mini_inzoi import (
    ACTION_NAMES,
    N_ACTIONS,
    N_NEEDS,
    PersonaConfig,
    MiniInzoiEnv,
)

GRID_SIZE = 12
N_AGENTS = 16
OBS_DIM = 2 + 1 + N_NEEDS + 3 * (N_AGENTS - 1)
WORLD_OBJECTS = {
    "bed": (0, 0), "kitchen": (0, 11), "gym": (11, 0), "library": (11, 11),
    "desk": (4, 4), "sofa": (7, 7), "bathroom": (0, 6), "park": (11, 6),
}


def _default_16_personas() -> list[PersonaConfig]:
    from .mini_inzoi import DEFAULT_PERSONAS
    return [
        PersonaConfig(
            name=f"{base.name}_{i}",
            decay_modifiers=list(base.decay_modifiers),
            preferred_actions=list(base.preferred_actions),
            big_five=dict(base.big_five),
        )
        for i in range(N_AGENTS)
        for base in [DEFAULT_PERSONAS[i % len(DEFAULT_PERSONAS)]]
    ]


class MiniInzoiEnvV2(MiniInzoiEnv):
    metadata = {**MiniInzoiEnv.metadata, "name": "mini_inzoi_v2"}
    grid_size = GRID_SIZE
    n_agents = N_AGENTS
    obs_dim = OBS_DIM
    world_objects = WORLD_OBJECTS

    def __init__(self, personas=None, max_steps: int = 200, render_mode: str | None = None):
        super().__init__(
            personas=_default_16_personas() if personas is None else personas,
            max_steps=max_steps,
            render_mode=render_mode,
        )


__all__ = [
    "MiniInzoiEnvV2", "PersonaConfig", "_default_16_personas",
    "N_AGENTS", "N_ACTIONS", "N_NEEDS", "OBS_DIM", "GRID_SIZE", "ACTION_NAMES",
]
