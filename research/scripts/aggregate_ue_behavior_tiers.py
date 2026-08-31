"""Aggregate independent Actor/Mass behavior audits across UE sessions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


METRICS = (
    "actor_balanced_accuracy",
    "mass_balanced_accuracy",
    "mass_minus_actor_balanced_accuracy",
    "mean_action_js_divergence",
    "trait_prediction_agreement",
)


def load_row(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    protocol = payload["protocol"]
    return {
        "session": Path(protocol["session"]).name,
        "active_ablation": protocol["active_ablation"],
        "policy_mode": protocol["policy_mode"],
        "actor_personas": payload["tiers"]["actor"]["n_personas"],
        "mass_personas": payload["tiers"]["mass"]["n_personas"],
        "actor_mean_decisions": payload["tiers"]["actor"]["decision_count"]["mean"],
        "mass_mean_decisions": payload["tiers"]["mass"]["decision_count"]["mean"],
        "actor_balanced_accuracy": payload["tiers"]["actor"]["mean_balanced_accuracy"],
        "mass_balanced_accuracy": payload["tiers"]["mass"]["mean_balanced_accuracy"],
        "mass_minus_actor_balanced_accuracy": payload["paired"]["mass_minus_actor_balanced_accuracy"]["observed"],
        "mean_action_js_divergence": payload["paired"]["mean_action_js_divergence"],
        "trait_prediction_agreement": payload["paired"]["trait_prediction_agreement"],
    }


def aggregate(rows: list[dict], inputs: list[Path]) -> dict:
    if len(rows) < 2:
        raise ValueError("At least two session audits are required")
    ablations = {row["active_ablation"] for row in rows}
    policies = {row["policy_mode"] for row in rows}
    if len(ablations) != 1 or len(policies) != 1:
        raise ValueError(f"Mixed protocols: ablations={ablations}, policies={policies}")
    summary = {}
    for metric in METRICS:
        values = np.asarray([row[metric] for row in rows], dtype=np.float64)
        summary[metric] = {
            "mean": float(values.mean()),
            "sample_std": float(values.std(ddof=1)),
            "min": float(values.min()),
            "max": float(values.max()),
        }
    return {
        "protocol": {
            "active_ablation": next(iter(ablations)),
            "policy_mode": next(iter(policies)),
            "aggregation_unit": "UE standalone run / spawn seed",
            "n_runs": len(rows),
            "input_audits": [path.as_posix() for path in inputs],
            "uncertainty": "sample standard deviation across three spawn seeds; descriptive, not a confidence interval",
        },
        "runs": rows,
        "aggregate": summary,
    }


def plot(payload: dict, output: Path) -> None:
    rows = payload["runs"]
    x = np.arange(len(rows))
    actor = np.asarray([row["actor_balanced_accuracy"] for row in rows])
    mass = np.asarray([row["mass_balanced_accuracy"] for row in rows])
    js = np.asarray([row["mean_action_js_divergence"] for row in rows])
    agreement = np.asarray([row["trait_prediction_agreement"] for row in rows])
    labels = [row["session"][-6:] for row in rows]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6))
    axes[0].plot(x, actor, "o-", color="#16A6A1", label="Actor / BT")
    axes[0].plot(x, mass, "o-", color="#7F56D9", label="Mass background")
    axes[0].axhline(1 / 3, color="#D92D20", linestyle="--", linewidth=1.1, label="Chance")
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 0.7)
    axes[0].set_ylabel("Mean Big Five balanced accuracy")
    axes[0].set_xlabel("Session suffix (seeds 0, 1, 2)")
    axes[0].set_title("Frozen action-only trait probe")
    axes[0].legend(frameon=False, fontsize=8)

    axes[1].plot(x, agreement, "o-", color="#F79009", label="Trait agreement")
    axes[1].plot(x, js, "o-", color="#2E90FA", label="Action JS divergence")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylim(0, 0.85)
    axes[1].set_xlabel("Session suffix (seeds 0, 1, 2)")
    axes[1].set_title("Actor/Mass preservation diagnostics")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Full-PCSP UE simulation-tier audit — three spawn seeds", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "full_pcsp_ue_tier_multiseed.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "full_pcsp_ue_tier_multiseed.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = [load_row(path) for path in args.inputs]
    payload = aggregate(rows, args.inputs)
    (args.output / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (args.output / "per_seed.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(payload, args.output)
    print(json.dumps(payload["aggregate"], indent=2))


if __name__ == "__main__":
    main()
