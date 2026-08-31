"""Small deterministic contract test for the independent behavior features."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval.independent_behavior import extract_features, feature_names


def main() -> None:
    rng = np.random.default_rng(7)
    actions = np.arange(200, dtype=np.int64) % 20
    observations = rng.random((200, 69), dtype=np.float32)
    first = extract_features(actions, observations)
    second = extract_features(actions, observations)
    names = feature_names()
    assert set(first) == {"action_only", "behavior_context"}
    assert len(first["action_only"]) == 445
    assert len(first["behavior_context"]) == 749
    assert len(names["behavior_context"]) == 749
    assert np.array_equal(first["behavior_context"], second["behavior_context"])
    assert np.isclose(first["action_only"][:20].sum(), 1.0)
    assert np.isclose(first["action_only"][20:420].sum(), 1.0)
    print("independent behavior feature contract PASS")


if __name__ == "__main__":
    main()
