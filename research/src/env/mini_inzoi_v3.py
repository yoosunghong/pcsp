"""Mini-Inzoi v3: richer action semantics and persona-observable state."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from .mini_inzoi import (
    BASE_DECAY,
    DEFAULT_PERSONAS,
    MiniInzoiEnv,
    PersonaConfig,
    WORLD_OBJECTS,
    _cosine,
)
from .v3_constants import (
    ACTION_NAMES_V3,
    ACTION_RESTORE_V3,
    ACTION_STYLE_PROFILE,
    N_ACTIONS_V3,
    OBS_DIM_V3_BASE,
)

GRID_SIZE = 6
N_AGENTS = 4
MAX_REPEAT = 6
MAX_NOVEL_STEPS = 20


def _default_v3_personas() -> list[PersonaConfig]:
    mapping = {
        0: [0, 1], 1: [2, 3], 2: [4, 5], 3: [6, 7],
        4: [8, 9], 5: [10, 11], 6: [12], 7: [13, 14],
    }
    result: list[PersonaConfig] = []
    for base in DEFAULT_PERSONAS:
        preferred = sorted({v for old in base.preferred_actions for v in mapping.get(old, [])})
        result.append(PersonaConfig(
            name=base.name,
            decay_modifiers=list(base.decay_modifiers),
            preferred_actions=preferred,
            big_five=dict(base.big_five),
        ))
    return result


class MiniInzoiV3Env(MiniInzoiEnv):
    metadata = {**MiniInzoiEnv.metadata, "name": "mini_inzoi_v3"}
    grid_size = GRID_SIZE
    n_agents = N_AGENTS
    n_actions = N_ACTIONS_V3
    obs_dim = OBS_DIM_V3_BASE
    action_restore = ACTION_RESTORE_V3
    world_objects = WORLD_OBJECTS

    def __init__(
        self,
        personas: Iterable[PersonaConfig] | None = None,
        max_steps: int = 200,
        render_mode: str | None = None,
    ) -> None:
        super().__init__(
            personas=_default_v3_personas() if personas is None else personas,
            max_steps=max_steps,
            render_mode=render_mode,
        )
        self._obs_dim = self.obs_dim
        self._bf_vecs = np.asarray([p.bf_vec for p in self.personas], dtype=np.float32)
        self.repeat_counts = np.zeros(self.n_agents, dtype=np.int64)
        self.novelty_steps = np.zeros(self.n_agents, dtype=np.int64)

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> None:
        super().reset(seed=seed, options=options)
        self._bf_vecs = np.asarray([p.bf_vec for p in self.personas], dtype=np.float32)
        self.repeat_counts = np.zeros(self.n_agents, dtype=np.int64)
        self.novelty_steps = np.zeros(self.n_agents, dtype=np.int64)

    def _nearest_affordance_index(self, agent_idx: int) -> int:
        position = self.positions[agent_idx].astype(np.float32)
        coords = np.asarray(list(self.world_objects.values()), dtype=np.float32)
        return int(np.argmin(np.abs(coords - position[None, :]).sum(axis=1)))

    def _make_obs(self, agent_idx: int) -> np.ndarray:
        scale = float(self.grid_size - 1)
        obs: list[float] = [
            float(self.positions[agent_idx, 0]) / scale,
            float(self.positions[agent_idx, 1]) / scale,
            float(self.time_of_day) / 23.0,
        ]
        obs.extend(float(x) for x in self.needs[agent_idx])

        affordance = [0.0] * len(self.world_objects)
        affordance[self._nearest_affordance_index(agent_idx)] = 1.0
        obs.extend(affordance)

        nearby = self._nearby_agents(agent_idx)
        last_action = int(self.last_actions[agent_idx])
        obs.extend((
            float(len(nearby)) / float(self.n_agents),
            float(last_action in (6, 7, 14)),
            float(last_action == 7),
            float(self.repeat_counts[agent_idx]) / float(MAX_REPEAT),
            float(self.novelty_steps[agent_idx]) / float(MAX_NOVEL_STEPS),
        ))

        for other_idx in range(self.n_agents):
            if other_idx == agent_idx:
                continue
            obs.extend((
                float(self.positions[other_idx, 0]) / scale,
                float(self.positions[other_idx, 1]) / scale,
                float(self.last_actions[other_idx]) / float(self.n_actions - 1),
            ))
        return np.asarray(obs, dtype=np.float32)

    def _style_reward(self, agent_idx: int, action: int) -> float:
        style = ACTION_STYLE_PROFILE[action]
        return 0.3 * _cosine(self._bf_vecs[agent_idx], style)

    def _apply_action(self, agent_idx: int, action: int) -> float:
        if action == 16:
            self.positions[agent_idx, 0] = max(0, self.positions[agent_idx, 0] - 1)
        elif action == 17:
            self.positions[agent_idx, 0] = min(self.grid_size - 1, self.positions[agent_idx, 0] + 1)
        elif action == 18:
            self.positions[agent_idx, 1] = max(0, self.positions[agent_idx, 1] - 1)
        elif action == 19:
            self.positions[agent_idx, 1] = min(self.grid_size - 1, self.positions[agent_idx, 1] + 1)

        for need_idx, amount in self.action_restore.get(action, []):
            self.needs[agent_idx, need_idx] = min(1.0, float(self.needs[agent_idx, need_idx]) + amount)

        reward = 0.0
        for need_idx, amount in self.action_restore.get(action, []):
            reward += min(amount, max(0.0, 1.0 - float(self.needs[agent_idx, need_idx])))
        # The v3 need term adds a small penalty for every critically depleted
        # need.  The 0.2 threshold and 0.1 weight are exactly recoverable from
        # long repeated-action rollouts as neglected needs cross the boundary.
        reward -= 0.1 * int(np.count_nonzero(self.needs[agent_idx] < 0.2))
        if action in self.personas[agent_idx].preferred_actions:
            reward += 0.5
        reward += self._style_reward(agent_idx, action)
        if action in (6, 7, 14):
            reward += self._social_bonus(agent_idx)

        if action == int(self.last_actions[agent_idx]):
            self.repeat_counts[agent_idx] = min(MAX_REPEAT, self.repeat_counts[agent_idx] + 1)
            self.novelty_steps[agent_idx] = min(MAX_NOVEL_STEPS, self.novelty_steps[agent_idx] + 1)
        else:
            self.repeat_counts[agent_idx] = 0
            self.novelty_steps[agent_idx] = 0
        return reward

    def render(self) -> str | None:
        lines = [f"Mini-Inzoi v3 | day-hour={self.time_of_day:02d}:00 | cycle={self.step_count}"]
        for agent in self.possible_agents:
            idx = self.agent_name_mapping[agent]
            lines.append(
                f"{agent} ({self.personas[idx].name}) pos={tuple(int(x) for x in self.positions[idx])} "
                f"action={ACTION_NAMES_V3[int(self.last_actions[idx])]}"
            )
        output = "\n".join(lines)
        if self.render_mode == "human":
            print(output)
            return None
        return output


__all__ = [
    "MiniInzoiV3Env", "PersonaConfig", "WORLD_OBJECTS", "GRID_SIZE", "N_AGENTS",
    "MAX_REPEAT", "MAX_NOVEL_STEPS", "BASE_DECAY",
]
