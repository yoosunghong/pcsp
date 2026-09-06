"""Mini-Inzoi v3-large: 12x12 world with 16 agents and 69-dim state."""
from __future__ import annotations

from .mini_inzoi import DEFAULT_PERSONAS, PersonaConfig
from .mini_inzoi_v3 import MiniInzoiV3Env
from .v3_constants import OBS_DIM_V3_LARGE

GRID_SIZE = 12
N_AGENTS = 16
WORLD_OBJECTS = {
    "bed": (0, 0), "kitchen": (0, 11), "gym": (11, 0), "library": (11, 11),
    "desk": (4, 4), "sofa": (7, 7), "bathroom": (0, 6), "park": (11, 6),
}


def _default_large_personas() -> list[PersonaConfig]:
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


class MiniInzoiV3LargeEnv(MiniInzoiV3Env):
    metadata = {**MiniInzoiV3Env.metadata, "name": "mini_inzoi_v3_large"}
    grid_size = GRID_SIZE
    n_agents = N_AGENTS
    obs_dim = OBS_DIM_V3_LARGE
    world_objects = WORLD_OBJECTS

    def __init__(self, personas=None, max_steps: int = 200, render_mode: str | None = None):
        super().__init__(
            personas=_default_large_personas() if personas is None else personas,
            max_steps=max_steps,
            render_mode=render_mode,
        )


__all__ = ["MiniInzoiV3LargeEnv", "N_AGENTS", "GRID_SIZE", "WORLD_OBJECTS"]
