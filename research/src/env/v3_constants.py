"""Stable Mini-Inzoi v3 action and observation constants."""
from __future__ import annotations

import numpy as np

N_NEEDS_V3 = 8
N_ACTIONS_V3 = 20

ACTION_NAMES_V3 = [
    "focused_work", "planning_work", "eat_quick", "eat_slow",
    "sleep", "nap", "socialize_initiate", "socialize_respond",
    "exercise_intense", "exercise_light", "read_deep", "read_casual",
    "clean", "rest_alone", "rest_with_others", "explore",
    "move_up", "move_down", "move_left", "move_right",
]

# Axis order: E, N, A, C, O.  Rows are hand-authored as specified in the v3
# design document; only direction matters because reward uses cosine similarity.
ACTION_STYLE_PROFILE = np.asarray([
    [0.0, 0.0, 0.0, 1.0, 0.0],       # focused_work
    [0.0, -0.3, 0.0, 1.0, 0.3],      # planning_work
    [-0.6, 0.6, 0.0, -1.0, 0.0],     # eat_quick
    [0.0, -0.3, 0.3, 0.7, 0.0],      # eat_slow
    [0.0, -1.0, 0.0, 1.0, 0.0],      # sleep
    [0.0, 1.0, 0.0, -1.0, 0.0],      # nap
    [1.0, 0.0, 0.5, 0.0, 0.3],       # socialize_initiate
    [0.0, 0.0, 0.7, 0.3, 0.0],       # socialize_respond
    [0.5, -0.3, 0.0, 0.7, 0.0],      # exercise_intense
    [0.0, 0.0, 0.0, 0.5, 0.0],       # exercise_light
    [-0.3, -0.3, 0.0, 0.7, 1.0],     # read_deep
    [-0.6, 0.0, 0.6, 0.0, 1.0],      # read_casual
    [0.0, -0.5, 0.0, 0.7, -0.3],     # clean
    [-1.0, 0.5, 0.0, 0.0, 0.0],      # rest_alone
    [0.7, 0.0, 0.7, 0.0, 0.3],       # rest_with_others
    [0.5, -0.5, 0.0, 0.0, 1.0],      # explore
    [0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0],
], dtype=np.float32)

# Recovered exactly from committed v3 rollout transitions.
ACTION_RESTORE_V3: dict[int, list[tuple[int, float]]] = {
    0: [(6, 0.05)],
    1: [(6, 0.05)],
    2: [(0, 0.05)],
    3: [(0, 0.08)],
    4: [(1, 0.10)],
    5: [(1, 0.05)],
    6: [(2, 0.07)],
    7: [(2, 0.07)],
    8: [(5, 0.08)],
    9: [(5, 0.04)],
    10: [(7, 0.06)],
    11: [(3, 0.06)],
    12: [(4, 0.06)],
    13: [(3, 0.05)],
    14: [(2, 0.03), (3, 0.03)],
    15: [(3, 0.03)],
}


def obs_dim_v3(n_agents: int) -> int:
    return 2 + 1 + N_NEEDS_V3 + 8 + 3 + 2 + 3 * (int(n_agents) - 1)


OBS_DIM_V3_BASE = obs_dim_v3(4)
OBS_DIM_V3_LARGE = obs_dim_v3(16)

__all__ = [
    "ACTION_NAMES_V3", "ACTION_RESTORE_V3", "ACTION_STYLE_PROFILE",
    "N_ACTIONS_V3", "N_NEEDS_V3", "OBS_DIM_V3_BASE", "OBS_DIM_V3_LARGE",
    "obs_dim_v3",
]
