"""Recompute persona-identification accuracy after excluding preflagged OOD test records."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "v3_standard": ("data/personas/test_60_v3.json", "results/pcsp_v3/eval_indist60_summary.json", "results"),
    "unseen_occupation_v3": ("data/personas/splits/unseen_occupation_v3_test.json", "results/pcsp_v3_zeroshot/eval_zs60_summary.json", "results"),
    "unseen_combo_v3": ("data/personas/splits/unseen_combo_v3_test.json", "results/pcsp_v3_combo_zs/eval_combo_summary.json", "results"),
    "v3_large": ("data/personas/test_100_v3.json", "results/pcsp_v3_large/eval_zs100_summary.json", "per_seed"),
}


def flagged_ids(audit_csv: Path, threshold: float) -> tuple[dict[str, set[int]], list[dict]]:
    by_split: dict[str, set[int]] = defaultdict(set)
    pairs = []
    with audit_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cosine = float(row["embedding_max_cosine"])
            if cosine < threshold:
                continue
            split = row["split"]
            test_id = int(row["test_id"])
            train_id = int(row["embedding_train_id"])
            by_split[split].add(test_id)
            pairs.append({"split": split, "test_id": test_id, "train_id": train_id, "cosine": cosine})
    return by_split, pairs


def sensitivity_row(split: str, label: str, result: dict, persona_ids: list[int], excluded_ids: set[int]) -> dict:
    scores = np.asarray(result["per_persona_acc"], dtype=np.float64)
    if len(scores) != len(persona_ids):
        raise ValueError(f"{split}/{label}: {len(scores)} scores for {len(persona_ids)} personas")
    reported = float(result["accuracy"])
    original = float(scores.mean())
    if not np.isclose(reported, original, atol=1e-12):
        raise ValueError(f"{split}/{label}: reported accuracy {reported} != per-persona mean {original}")
    mask = np.asarray([persona_id not in excluded_ids for persona_id in persona_ids])
    if mask.all():
        raise ValueError(f"{split}/{label}: no flagged IDs found in persona list")
    kept = scores[mask]
    removed = scores[~mask]
    mode, _, seed = label.partition("@")
    return {
        "split": split,
        "mode": mode,
        "seed": int(seed) if seed else "",
        "n_original": len(scores),
        "n_excluded": int((~mask).sum()),
        "excluded_ids": ";".join(map(str, np.asarray(persona_ids)[~mask].tolist())),
        "excluded_accuracy_mean": float(removed.mean()),
        "original_accuracy": original,
        "filtered_accuracy": float(kept.mean()),
        "delta": float(kept.mean() - original),
    }


def run(audit_csv: Path, threshold: float) -> tuple[dict, list[dict]]:
    by_split, pairs = flagged_ids(audit_csv, threshold)
    rows = []
    for split, (personas_rel, results_rel, container) in SPECS.items():
        excluded = by_split.get(split, set())
        if not excluded:
            continue
        personas = json.loads((ROOT / personas_rel).read_text(encoding="utf-8"))
        persona_ids = [int(row["id"]) for row in personas]
        payload = json.loads((ROOT / results_rel).read_text(encoding="utf-8"))
        for label, result in payload[container].items():
            rows.append(sensitivity_row(split, label, result, persona_ids, excluded))

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["split"], row["mode"])].append(row)
    aggregates = []
    for (split, mode), values in sorted(grouped.items()):
        original = np.asarray([row["original_accuracy"] for row in values])
        filtered = np.asarray([row["filtered_accuracy"] for row in values])
        delta = filtered - original
        aggregates.append({
            "split": split,
            "mode": mode,
            "n_runs": len(values),
            "original_mean": float(original.mean()),
            "filtered_mean": float(filtered.mean()),
            "delta_mean": float(delta.mean()),
            "delta_max_abs": float(np.abs(delta).max()),
            "delta_sample_std": float(delta.std(ddof=1)) if len(delta) > 1 else 0.0,
        })
    payload = {
        "protocol": {
            "embedding_cosine_threshold": threshold,
            "threshold_source": "results/ood_leakage_audit/summary.json predeclared alert",
            "operation": "exclude flagged test personas from the existing per-persona accuracy mean",
            "not_recomputed": ["candidate-set predictions", "trajectory embeddings", "coherence ratio", "training"],
            "split_level_flag_count": len(pairs),
            "unique_test_id_count": len({pair["test_id"] for pair in pairs}),
            "unique_train_test_pair_count": len({(pair["test_id"], pair["train_id"]) for pair in pairs}),
        },
        "flagged_pairs": pairs,
        "aggregate_by_split_mode": aggregates,
        "max_absolute_accuracy_delta": max(abs(row["delta"]) for row in rows),
    }
    return payload, rows


def plot(payload: dict, output: Path) -> None:
    rows = payload["aggregate_by_split_mode"]
    labels = [f'{row["split"]} / {row["mode"]}' for row in rows]
    values = [row["delta_mean"] * 100 for row in rows]
    colors = ["#16A6A1" if value >= 0 else "#D92D20" for value in values]
    fig, axis = plt.subplots(figsize=(9.5, max(5.5, len(rows) * 0.38)))
    y = np.arange(len(rows))
    axis.barh(y, values, color=colors)
    axis.axvline(0, color="#344054", linewidth=1)
    axis.set_yticks(y, labels, fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("Accuracy change after exclusion (percentage points)")
    axis.set_title("OOD semantic-neighbor exclusion sensitivity", fontweight="bold")
    axis.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "ood_near_neighbor_sensitivity.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "ood_near_neighbor_sensitivity.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-csv", type=Path, default=ROOT / "results/ood_leakage_audit/nearest_pairs.csv")
    parser.add_argument("--threshold", type=float, default=0.95)
    parser.add_argument("--output", type=Path, default=ROOT / "results/ood_leakage_sensitivity")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    payload, rows = run(args.audit_csv, args.threshold)
    (args.output / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (args.output / "per_run.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(payload, args.output)
    print(json.dumps({
        "flagged_pairs": payload["protocol"]["unique_train_test_pair_count"],
        "evaluations": len(rows),
        "max_absolute_accuracy_delta": payload["max_absolute_accuracy_delta"],
    }, indent=2))


if __name__ == "__main__":
    main()
