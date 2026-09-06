"""Synthetic contract checks for the OOD leakage auditor."""
from __future__ import annotations

import numpy as np

from audit_ood_leakage import audit_split


def main() -> None:
    train = [{"id": 1, "text": "Calm and careful planner", "occupation": "a", "big_five": {}, "preferred_actions": []}]
    leaked = [{"id": 1, "text": " calm, and careful planner! ", "occupation": "b", "big_five": {}, "preferred_actions": []}]
    summary, _ = audit_split("synthetic_leak", train, leaked, np.asarray([[1.0, 0.0]]), np.asarray([[1.0, 0.0]]))
    assert summary["gate"] == "fail"
    assert summary["counts"]["id_overlap"] == 1
    assert summary["counts"]["normalized_exact"] == 1

    clean = [{"id": 2, "text": "Energetic explorer", "occupation": "b", "big_five": {}, "preferred_actions": [1]}]
    summary, _ = audit_split("synthetic_clean", train, clean, np.asarray([[1.0, 0.0]]), np.asarray([[0.0, 1.0]]))
    assert summary["gate"] == "pass"
    print("OOD leakage audit contract PASS")


if __name__ == "__main__":
    main()
