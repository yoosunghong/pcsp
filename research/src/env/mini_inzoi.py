"""Reference-compatible Mini-Inzoi v1 environment.

The original source was accidentally excluded by a repository-wide ``env/``
ignore rule.  This implementation restores the public contract and preserves
the dynamics recoverable from committed rollout artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
from gymnasium import spaces
from gymnasium.utils import seeding
from pettingzoo import AECEnv
from pettingzoo.utils import AgentSelector

GRID_SIZE = 6
N_AGENTS = 4
N_NEEDS = 8
N_ACTIONS = 12
OBS_DIM = 20

NEED_NAMES = [
    "hunger", "sleep", "social", "leisure",
    "hygiene", "fitness", "work", "learning",
]
ACTION_NAMES = [
    "work", "eat", "sleep", "socialize", "exercise", "read",
    "clean", "rest", "move_up", "move_down", "move_left", "move_right",
]

# Dict insertion order is part of the v3 affordance observation contract.
WORLD_OBJECTS = {
    "bed": (0, 0),
    "kitchen": (0, 5),
    "gym": (5, 0),
    "library": (4, 5),
    "desk": (2, 2),
    "sofa": (3, 3),
    "bathroom": (0, 3),
    "park": (5, 2),
}

# Recovered exactly from committed zero-shot observation streams.
BASE_DECAY = np.asarray([0.008, 0.005, 0.006, 0.004, 0.003, 0.004, 0.005, 0.003], dtype=np.float32)
ACTION_RESTORE: dict[int, list[tuple[int, float]]] = {
    0: [(6, 0.05)],
    1: [(0, 0.08)],
    2: [(1, 0.10)],
    3: [(2, 0.07)],
    4: [(5, 0.08)],
    5: [(7, 0.06)],
    6: [(4, 0.06)],
    7: [(3, 0.05)],
}

_BF_LEVEL_SIGNED = {"low": -1.0, "mid": 0.0, "high": 1.0}
_BF_LEVEL_COMPAT = {"low": 0.0, "mid": 0.5, "high": 1.0}
_BF_KEYS = ("E", "N", "A", "C", "O")


@dataclass
class PersonaConfig:
    """Numeric environment configuration derived from one persona record."""

    name: str = "persona"
    decay_modifiers: list[float] = field(default_factory=lambda: [1.0] * N_NEEDS)
    preferred_actions: list[int] = field(default_factory=list)
    big_five: dict[str, str] = field(default_factory=lambda: {k: "mid" for k in _BF_KEYS})
    id: int | None = None
    text: str = ""
    occupation: str = ""
    age: int | None = None
    split: str = ""

    def __post_init__(self) -> None:
        values = list(self.decay_modifiers)
        self.decay_modifiers = [float(v) for v in (values + [1.0] * N_NEEDS)[:N_NEEDS]]
        self.preferred_actions = [int(a) for a in self.preferred_actions]
        self.big_five = {k: str(self.big_five.get(k, "mid")) for k in _BF_KEYS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaConfig":
        return cls(
            id=int(data["id"]) if data.get("id") is not None else None,
            name=str(data.get("name") or data.get("occupation") or f"persona_{data.get('id', 'unknown')}"),
            text=str(data.get("text", "")),
            occupation=str(data.get("occupation", "")),
            age=int(data["age"]) if data.get("age") is not None else None,
            split=str(data.get("split", "")),
            decay_modifiers=list(data.get("decay_modifiers", [1.0] * N_NEEDS)),
            preferred_actions=list(data.get("preferred_actions", [])),
            big_five=dict(data.get("big_five", {})),
        )

    @property
    def bf_vec(self) -> np.ndarray:
        """Signed Big-Five vector used by v3 stylistic reward shaping."""
        return np.asarray([_BF_LEVEL_SIGNED.get(self.big_five[k], 0.0) for k in _BF_KEYS], dtype=np.float32)

    @property
    def compatibility_vec(self) -> np.ndarray:
        """Non-negative Big-Five vector used by the v1/v2 social reward."""
        return np.asarray([_BF_LEVEL_COMPAT.get(self.big_five[k], 0.5) for k in _BF_KEYS], dtype=np.float32)


DEFAULT_PERSONAS = [
    PersonaConfig("focused_worker", [1.0, 1.0, 0.8, 1.0, 1.0, 0.8, 1.6, 1.0], [0, 6], {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "mid"}),
    PersonaConfig("social_explorer", [1.0, 1.0, 1.6, 1.2, 1.0, 1.0, 0.8, 1.2], [3, 5], {"E": "high", "N": "low", "A": "high", "C": "mid", "O": "high"}),
    PersonaConfig("active_carer", [1.0, 0.9, 1.2, 0.8, 1.2, 1.5, 1.0, 0.8], [4, 6], {"E": "high", "N": "mid", "A": "high", "C": "high", "O": "mid"}),
    PersonaConfig("quiet_reader", [0.9, 1.0, 0.6, 1.1, 0.8, 0.7, 0.9, 1.6], [5, 7], {"E": "low", "N": "mid", "A": "mid", "C": "high", "O": "high"}),
]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom > 1e-8 else 0.0


class MiniInzoiEnv(AECEnv):
    """Small sequential multi-agent life-simulation environment."""

    metadata = {
        "render_modes": ["ansi", "human"],
        "name": "mini_inzoi_v1",
        "is_parallelizable": False,
    }

    grid_size = GRID_SIZE
    n_agents = N_AGENTS
    n_actions = N_ACTIONS
    obs_dim = OBS_DIM
    world_objects = WORLD_OBJECTS
    action_restore = ACTION_RESTORE

    def __init__(
        self,
        personas: Iterable[PersonaConfig] | None = None,
        max_steps: int = 200,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.render_mode = render_mode
        self.max_steps = int(max_steps)
        supplied = list(personas) if personas is not None else list(DEFAULT_PERSONAS)
        if len(supplied) != self.n_agents:
            raise ValueError(f"Expected {self.n_agents} personas, got {len(supplied)}")
        self.personas = supplied
        self.possible_agents = [f"agent_{i}" for i in range(self.n_agents)]
        self.agent_name_mapping = {agent: i for i, agent in enumerate(self.possible_agents)}
        self._observation_spaces = {
            agent: spaces.Box(0.0, 1.0, shape=(self.obs_dim,), dtype=np.float32)
            for agent in self.possible_agents
        }
        self._action_spaces = {
            agent: spaces.Discrete(self.n_actions) for agent in self.possible_agents
        }
        self.positions = np.zeros((self.n_agents, 2), dtype=np.int64)
        self.needs = np.full((self.n_agents, N_NEEDS), 0.7, dtype=np.float32)
        self.last_actions = np.zeros(self.n_agents, dtype=np.int64)
        self.time_of_day = 8
        self.step_count = 0

    def observation_space(self, agent: str):
        return self._observation_spaces[agent]

    def action_space(self, agent: str):
        return self._action_spaces[agent]

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> None:
        self.np_random, self.np_random_seed = seeding.np_random(seed)
        legacy_seed = int(seed) if seed is not None else int(self.np_random.integers(0, 2**32 - 1))
        legacy_rng = np.random.RandomState(legacy_seed)
        self.agents = self.possible_agents[:]
        self.positions = legacy_rng.randint(0, self.grid_size, size=(self.n_agents, 2)).astype(np.int64)
        self.needs = np.full((self.n_agents, N_NEEDS), 0.7, dtype=np.float32)
        self.last_actions = np.zeros(self.n_agents, dtype=np.int64)
        self.time_of_day = 8
        self.step_count = 0
        self.rewards = {agent: 0.0 for agent in self.agents}
        self._cumulative_rewards = {agent: 0.0 for agent in self.agents}
        self.terminations = {agent: False for agent in self.agents}
        self.truncations = {agent: False for agent in self.agents}
        self.infos = {agent: {} for agent in self.agents}
        self._agent_selector = AgentSelector(self.agents)
        self.agent_selection = self._agent_selector.reset()

    def _make_obs(self, agent_idx: int) -> np.ndarray:
        scale = float(self.grid_size - 1)
        obs: list[float] = [
            float(self.positions[agent_idx, 0]) / scale,
            float(self.positions[agent_idx, 1]) / scale,
            float(self.time_of_day) / 23.0,
        ]
        obs.extend(float(x) for x in self.needs[agent_idx])
        for other_idx in range(self.n_agents):
            if other_idx == agent_idx:
                continue
            obs.extend((
                float(self.positions[other_idx, 0]) / scale,
                float(self.positions[other_idx, 1]) / scale,
                float(self.last_actions[other_idx]) / float(self.n_actions - 1),
            ))
        return np.asarray(obs, dtype=np.float32)

    def observe(self, agent: str) -> np.ndarray:
        return self._make_obs(self.agent_name_mapping[agent])

    def _nearby_agents(self, agent_idx: int) -> list[int]:
        pos = self.positions[agent_idx]
        return [
            j for j in range(self.n_agents)
            if j != agent_idx and np.max(np.abs(pos - self.positions[j])) <= 1
        ]

    def _social_bonus(self, agent_idx: int) -> float:
        nearby = self._nearby_agents(agent_idx)
        if not nearby:
            return 0.0
        # Historical behavior used the first nearby agent in stable index order.
        other_idx = nearby[0]
        similarity = _cosine(
            self.personas[agent_idx].compatibility_vec,
            self.personas[other_idx].compatibility_vec,
        )
        return 0.2 + 0.3 * similarity

    def _apply_action(self, agent_idx: int, action: int) -> float:
        if action == 8:
            self.positions[agent_idx, 0] = max(0, self.positions[agent_idx, 0] - 1)
        elif action == 9:
            self.positions[agent_idx, 0] = min(self.grid_size - 1, self.positions[agent_idx, 0] + 1)
        elif action == 10:
            self.positions[agent_idx, 1] = max(0, self.positions[agent_idx, 1] - 1)
        elif action == 11:
            self.positions[agent_idx, 1] = min(self.grid_size - 1, self.positions[agent_idx, 1] + 1)

        for need_idx, amount in self.action_restore.get(action, []):
            self.needs[agent_idx, need_idx] = min(1.0, float(self.needs[agent_idx, need_idx]) + amount)

        reward = 0.0
        # Preserve the historical post-update reward calculation visible in
        # committed rollouts (near saturation it rewards remaining capacity).
        for need_idx, amount in self.action_restore.get(action, []):
            reward += min(amount, max(0.0, 1.0 - float(self.needs[agent_idx, need_idx])))
        if action in self.personas[agent_idx].preferred_actions:
            reward += 0.5
        if action == 3:
            reward += self._social_bonus(agent_idx)
        return reward

    def _end_cycle(self) -> None:
        modifiers = np.asarray([p.decay_modifiers for p in self.personas], dtype=np.float32)
        self.needs = np.clip(self.needs - BASE_DECAY[None, :] * modifiers, 0.0, 1.0)
        self.time_of_day = (self.time_of_day + 1) % 24
        self.step_count += 1
        if self.step_count >= self.max_steps:
            for agent in self.agents:
                self.truncations[agent] = True

    def step(self, action: int | None) -> None:
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return
        if action is None:
            raise ValueError("Live agents require an integer action")
        if not self.action_space(agent).contains(action):
            raise ValueError(f"Invalid action {action} for {agent}")

        self._cumulative_rewards[agent] = 0.0
        self._clear_rewards()
        idx = self.agent_name_mapping[agent]
        action_id = int(action)
        self.rewards[agent] = float(self._apply_action(idx, action_id))
        self.last_actions[idx] = action_id
        if self._agent_selector.is_last():
            self._end_cycle()
        self.agent_selection = self._agent_selector.next()
        self._accumulate_rewards()

    def render(self) -> str | None:
        lines = [f"Mini-Inzoi | day-hour={self.time_of_day:02d}:00 | cycle={self.step_count}"]
        for agent in self.possible_agents:
            idx = self.agent_name_mapping[agent]
            lines.append(
                f"{agent} ({self.personas[idx].name}) pos={tuple(int(x) for x in self.positions[idx])} "
                f"action={ACTION_NAMES[int(self.last_actions[idx])] if self.last_actions[idx] < len(ACTION_NAMES) else self.last_actions[idx]}"
            )
        output = "\n".join(lines)
        if self.render_mode == "human":
            print(output)
            return None
        return output

    def close(self) -> None:
        """No external resources are owned by the pure-Python environment."""
        return None
