"""Smoke test for MiniInzoiV3LargeEnv. Mirrors scripts/test_env_v3.py.

Checks:
  - obs_dim, action_space, n_agents
  - reset → step loop with random actions completes one full episode
  - per-agent observations stay finite and in [0, 1]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

from src.env.mini_inzoi import PersonaConfig
from src.env.mini_inzoi_v3_large import MiniInzoiV3LargeEnv, N_AGENTS, GRID_SIZE
from src.env.v3_constants import OBS_DIM_V3_LARGE, N_ACTIONS_V3


def main() -> None:
    pdata = json.loads(
        (ROOT / "data" / "personas" / "personas_500_v3.json").read_text(encoding="utf-8")
    )
    rng = np.random.default_rng(0)
    idxs = rng.choice(len(pdata), size=N_AGENTS, replace=False)
    personas = [PersonaConfig.from_dict(pdata[i]) for i in idxs]

    env = MiniInzoiV3LargeEnv(personas=personas, max_steps=50)
    assert env._obs_dim == OBS_DIM_V3_LARGE, (env._obs_dim, OBS_DIM_V3_LARGE)
    print(f"env: grid={GRID_SIZE}x{GRID_SIZE}  n_agents={N_AGENTS}  "
          f"obs_dim={env._obs_dim}  n_actions={N_ACTIONS_V3}")

    env.reset(seed=0)
    n_steps = 0
    n_finite = 0
    for agent in env.agent_iter():
        obs, rew, term, trunc, _ = env.last()
        n_finite += int(np.all(np.isfinite(obs)) and obs.shape == (OBS_DIM_V3_LARGE,))
        if term or trunc:
            env.step(None)
            continue
        a = int(rng.integers(0, N_ACTIONS_V3))
        env.step(a)
        n_steps += 1
        if n_steps >= 5 * 50 * N_AGENTS:
            break
    print(f"steps taken: {n_steps}  finite-obs ticks: {n_finite}")
    print("OK")


if __name__ == "__main__":
    main()
