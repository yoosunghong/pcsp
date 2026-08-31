"""Contract test for fixed-threshold OOD exclusion sensitivity."""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from run_ood_near_neighbor_sensitivity import flagged_ids, sensitivity_row


with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "pairs.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["split", "test_id", "embedding_train_id", "embedding_max_cosine"])
        writer.writeheader()
        writer.writerow({"split": "toy", "test_id": 3, "embedding_train_id": 8, "embedding_max_cosine": 0.95})
        writer.writerow({"split": "toy", "test_id": 4, "embedding_train_id": 9, "embedding_max_cosine": 0.949})
    by_split, pairs = flagged_ids(path, 0.95)
    assert by_split == {"toy": {3}}
    assert len(pairs) == 1 and pairs[0]["train_id"] == 8

result = {"accuracy": 0.5, "per_persona_acc": [0.0, 0.5, 1.0]}
row = sensitivity_row("toy", "full@42", result, [1, 2, 3], {3})
assert row["n_excluded"] == 1
assert row["filtered_accuracy"] == 0.25
assert row["delta"] == -0.25
print("OOD near-neighbor sensitivity contract PASS")
