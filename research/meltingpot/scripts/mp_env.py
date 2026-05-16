"""Minimal Melting Pot wrapper exposing a parallel-step API.

Returns RGB (H,W,3) uint8 observations per agent. Episodes are not auto-reset;
the trainer truncates with fixed-length rollouts.
"""
from __future__ import annotations

import numpy as np
from meltingpot import substrate


class MeltingPotEnv:
    def __init__(self, substrate_name: str = "commons_harvest__open", seed: int | None = None):
        cfg = substrate.get_config(substrate_name)
        self.roles = cfg.default_player_roles
        self.n_agents = len(self.roles)
        self._env = substrate.build(substrate_name, roles=self.roles)
        spec = self._env.action_spec()
        self.n_actions = int(spec[0].num_values)
        self.obs_shape = self._env.observation_spec()[0]["RGB"].shape  # (H,W,3)
        self._last_obs = None
        self._done = True

    def reset(self) -> np.ndarray:
        ts = self._env.reset()
        self._last_obs = self._stack_rgb(ts.observation)
        self._done = False
        return self._last_obs  # (n_agents, H, W, 3) uint8

    def step(self, actions):
        ts = self._env.step([int(a) for a in actions])
        rgb = self._stack_rgb(ts.observation)
        rewards = np.asarray(ts.reward, dtype=np.float32)  # (n_agents,)
        done = bool(ts.last())
        self._last_obs = rgb
        self._done = done
        return rgb, rewards, done

    @staticmethod
    def _stack_rgb(obs_list) -> np.ndarray:
        return np.stack([o["RGB"] for o in obs_list], axis=0)

    def close(self):
        try:
            self._env.close()
        except Exception:
            pass
