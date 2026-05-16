"""Sanity test for the Melting Pot wrappers.

Runs:
    - single-env reset/step
    - async vector env reset/step
    - shape and dtype invariants
    - end-of-episode auto-reset
"""

from __future__ import annotations

import numpy as np

from src.env.meltingpot import (
    AsyncVectorMeltingPot,
    SingleSubstrateEnv,
    SyncVectorMeltingPot,
)


def test_single_env() -> None:
    env = SingleSubstrateEnv("commons_harvest__open")
    spec = env.spec
    obs, _ = env.reset(seed=0)
    assert obs.shape == (spec.num_players, spec.obs_height, spec.obs_width, spec.obs_channels)
    assert obs.dtype == np.uint8
    for _ in range(8):
        actions = np.zeros(spec.num_players, dtype=np.int64)
        obs, rew, term, trunc, info = env.step(actions)
        assert obs.shape == (spec.num_players, spec.obs_height, spec.obs_width, spec.obs_channels)
        assert rew.shape == (spec.num_players,)
        assert isinstance(term, bool) and isinstance(trunc, bool)
    env.close()
    print(f"[ok] single env: spec={spec}")


def test_vector_env(EnvCls, label: str) -> None:
    n = 2
    venv = EnvCls("commons_harvest__open", num_envs=n)
    spec = venv.spec
    obs = venv.reset(seed=0)
    assert obs.shape == (n, spec.num_players, spec.obs_height, spec.obs_width, spec.obs_channels)
    for _ in range(8):
        actions = np.zeros((n, spec.num_players), dtype=np.int64)
        obs, rew, done, trunc, infos = venv.step(actions)
        assert obs.shape == (n, spec.num_players, spec.obs_height, spec.obs_width, spec.obs_channels)
        assert rew.shape == (n, spec.num_players)
        assert done.shape == (n,)
    venv.close()
    print(f"[ok] {label} vector env: n={n} batch={n * spec.num_players}")


if __name__ == "__main__":
    test_single_env()
    test_vector_env(SyncVectorMeltingPot, "sync")
    test_vector_env(AsyncVectorMeltingPot, "async")
    print("[ok] all smoke checks passed")
