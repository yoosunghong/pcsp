"""Apply the frozen independent action evaluator to UE Actor and Mass logs."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval.independent_behavior import classification_metrics, extract_features

AXES = ("E", "N", "A", "C", "O")
LEVELS = {"low": 0, "mid": 1, "high": 2}


def _jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: {exc}") from exc


def _action_index(row: dict) -> int | None:
    value = row.get("policy_action_index")
    if value is not None and 0 <= int(value) < 20:
        return int(value)
    logits = row.get("logits")
    if isinstance(logits, list) and len(logits) == 20 and any(float(x) != 0.0 for x in logits):
        return int(np.argmax(np.asarray(logits, dtype=np.float64)))
    return None


def _pseudo_observation(row: dict) -> np.ndarray:
    observation = np.zeros(24, dtype=np.float64)
    position = row.get("pos", [0.0, 0.0])
    observation[0] = np.clip((float(position[0]) / 3000.0 + 1.0) * 0.5, 0.0, 1.0)
    observation[1] = np.clip((float(position[1]) / 3000.0 + 1.0) * 0.5, 0.0, 1.0)
    observation[2] = float(row.get("t", 0.0)) % 600.0 / 600.0
    needs = row.get("needs", [])
    for index, value in enumerate(needs[:8]):
        observation[3 + index] = float(value)
    return observation


def load_tier_sequences(session: Path) -> tuple[dict[str, dict[int, list[dict]]], dict]:
    sequences: dict[str, dict[int, list[dict]]] = {"actor": defaultdict(list), "mass": defaultdict(list)}
    session_meta = {"active_ablation": "unknown", "policy_mode": "unknown"}
    for path in sorted(session.glob("agent_p*.jsonl")):
        for row in _jsonl(path):
            if row.get("event") == "session_start":
                session_meta["active_ablation"] = row.get("active_ablation", session_meta["active_ablation"])
                session_meta["policy_mode"] = row.get("policy_mode", session_meta["policy_mode"])
            if row.get("event") == "decision" and _action_index(row) is not None:
                sequences["actor"][int(row["persona_id"])].append(row)
    mass_path = session / "mass_trajectories.jsonl"
    if mass_path.exists():
        for row in _jsonl(mass_path):
            if _action_index(row) is not None:
                sequences["mass"][int(row["persona_id"])].append(row)
    return sequences, session_meta


def _probabilities(weights, axis: str, features: np.ndarray) -> np.ndarray:
    prefix = f"action_only_{axis}"
    mean = weights[f"{prefix}_mean"]
    scale = weights[f"{prefix}_scale"]
    z = (features - mean) / scale
    z = np.concatenate((z, np.ones((len(z), 1))), axis=1)
    logits = z @ weights[f"{prefix}_weight"] / float(weights[f"{prefix}_temperature"][0])
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def _js_divergence(left: np.ndarray, right: np.ndarray) -> float:
    midpoint = 0.5 * (left + right)
    left_mask = left > 0
    right_mask = right > 0
    left_term = np.sum(left[left_mask] * np.log(left[left_mask] / midpoint[left_mask]))
    right_term = np.sum(right[right_mask] * np.log(right[right_mask] / midpoint[right_mask]))
    return float(0.5 * (left_term + right_term))


def evaluate(session: Path, personas_path: Path, weights_path: Path, min_decisions: int) -> tuple[dict, list[dict]]:
    sequences, session_meta = load_tier_sequences(session)
    personas = {int(row["id"]): row for row in json.loads(personas_path.read_text(encoding="utf-8"))}
    weights = np.load(weights_path)
    tier_rows: dict[str, list[dict]] = {"actor": [], "mass": []}
    for tier, by_persona in sequences.items():
        for persona_id, rows in sorted(by_persona.items()):
            if len(rows) < min_decisions or persona_id not in personas:
                continue
            actions = np.asarray([_action_index(row) for row in rows], dtype=np.int64)
            observations = np.stack([_pseudo_observation(row) for row in rows])
            features = extract_features(actions, observations)["action_only"]
            tier_rows[tier].append({
                "persona_id": persona_id,
                "n_decisions": len(actions),
                "features": features,
                "action_hist": features[:20],
                "labels": np.asarray([LEVELS[personas[persona_id]["big_five"][axis]] for axis in AXES]),
            })

    results = {
        "protocol": {
            "session": str(session.resolve()),
            "feature_contract": "independent_behavior.action_only.v1",
            "policy_action_source": "explicit policy_action_index; legacy Actor fallback is argmax of logged logits",
            "min_decisions": min_decisions,
            **session_meta,
        },
        "tiers": {},
        "paired": {},
    }
    prediction_rows = []
    for tier, rows in tier_rows.items():
        if not rows:
            results["tiers"][tier] = {"n_personas": 0, "error": "no eligible trajectories"}
            continue
        features = np.stack([row["features"] for row in rows])
        labels = np.stack([row["labels"] for row in rows])
        axis_metrics = {}
        for axis_index, axis in enumerate(AXES):
            probs = _probabilities(weights, axis, features)
            axis_metrics[axis] = classification_metrics(labels[:, axis_index], probs)
            for row, truth, probability in zip(rows, labels[:, axis_index], probs):
                prediction_rows.append({
                    "tier": tier, "persona_id": row["persona_id"], "n_decisions": row["n_decisions"],
                    "axis": axis, "truth": int(truth), "predicted": int(probability.argmax()),
                    "confidence": float(probability.max()),
                })
        results["tiers"][tier] = {
            "n_personas": len(rows),
            "decision_count": {"min": min(row["n_decisions"] for row in rows), "max": max(row["n_decisions"] for row in rows), "mean": float(np.mean([row["n_decisions"] for row in rows]))},
            "mean_balanced_accuracy": float(np.mean([metric["balanced_accuracy"] for metric in axis_metrics.values()])),
            "axes": axis_metrics,
        }

    actor = {row["persona_id"]: row for row in tier_rows["actor"]}
    mass = {row["persona_id"]: row for row in tier_rows["mass"]}
    paired_ids = sorted(set(actor) & set(mass))
    if paired_ids:
        divergences = [_js_divergence(actor[pid]["action_hist"], mass[pid]["action_hist"]) for pid in paired_ids]
        prediction_lookup = {(row["tier"], row["persona_id"], row["axis"]): row["predicted"] for row in prediction_rows}
        agreement = [
            prediction_lookup[("actor", pid, axis)] == prediction_lookup[("mass", pid, axis)]
            for pid in paired_ids for axis in AXES
        ]
        results["paired"] = {
            "n_personas": len(paired_ids),
            "mean_action_js_divergence": float(np.mean(divergences)),
            "median_action_js_divergence": float(np.median(divergences)),
            "trait_prediction_agreement": float(np.mean(agreement)),
            "per_persona_action_js": dict(zip(map(str, paired_ids), map(float, divergences))),
        }

        rng = np.random.default_rng(91_017)
        bootstrap_delta = []
        randomization_delta = []

        def tier_score(tier: str, ids: list[int], swap: dict[int, bool] | None = None) -> float:
            scores = []
            for axis in AXES:
                truth, predicted = [], []
                for pid in ids:
                    source_tier = tier
                    if swap and swap[pid]:
                        source_tier = "mass" if tier == "actor" else "actor"
                    row = next(item for item in tier_rows[source_tier] if item["persona_id"] == pid)
                    truth.append(int(row["labels"][AXES.index(axis)]))
                    predicted.append(prediction_lookup[(source_tier, pid, axis)])
                y = np.asarray(truth)
                pred = np.asarray(predicted)
                recalls = [np.mean(pred[y == label] == label) for label in np.unique(y)]
                scores.append(float(np.mean(recalls)))
            return float(np.mean(scores))

        observed_delta = tier_score("mass", paired_ids) - tier_score("actor", paired_ids)
        for _ in range(2000):
            sampled = rng.choice(paired_ids, len(paired_ids), replace=True).tolist()
            bootstrap_delta.append(tier_score("mass", sampled) - tier_score("actor", sampled))
            swap = {pid: bool(value) for pid, value in zip(paired_ids, rng.integers(0, 2, len(paired_ids)))}
            randomization_delta.append(tier_score("mass", paired_ids, swap) - tier_score("actor", paired_ids, swap))
        results["paired"]["mass_minus_actor_balanced_accuracy"] = {
            "observed": observed_delta,
            "cluster_bootstrap_95": [float(np.quantile(bootstrap_delta, 0.025)), float(np.quantile(bootstrap_delta, 0.975))],
            "paired_randomization_p_two_sided": float((1 + np.sum(np.abs(randomization_delta) >= abs(observed_delta))) / 2001),
            "resamples": 2000,
        }
    return results, prediction_rows


def _plot(results: dict, output: Path) -> None:
    if any(results["tiers"].get(tier, {}).get("n_personas", 0) == 0 for tier in ("actor", "mass")):
        return
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6))
    x = np.arange(len(AXES))
    actor = [results["tiers"]["actor"]["axes"][axis]["balanced_accuracy"] for axis in AXES]
    mass = [results["tiers"]["mass"]["axes"][axis]["balanced_accuracy"] for axis in AXES]
    axes[0].bar(x - 0.18, actor, 0.36, label="Actor / BT", color="#16A6A1")
    axes[0].bar(x + 0.18, mass, 0.36, label="Mass background", color="#7F56D9")
    axes[0].axhline(1 / 3, color="#D92D20", linestyle="--", linewidth=1.1, label="Chance")
    axes[0].set_xticks(x, AXES)
    axes[0].set_ylim(0, 1.02)
    axes[0].set_ylabel("Balanced accuracy")
    axes[0].set_title("Frozen action-only trait probe")
    axes[0].legend(frameon=False, fontsize=8)
    paired = results["paired"].get("per_persona_action_js", {})
    paired_x = np.arange(len(paired))
    axes[1].bar(paired_x, list(paired.values()), color="#F79009")
    axes[1].set_xticks(paired_x, list(paired.keys()), fontsize=8)
    axes[1].set_xlabel("Paired persona")
    axes[1].set_ylabel("Jensen–Shannon divergence")
    axes[1].set_title("Actor vs Mass action distribution")
    fig.suptitle("UE simulation-tier behavior audit", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "ue_behavior_tier_eval.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "ue_behavior_tier_eval.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--personas", type=Path, default=ROOT / "data/personas/personas_300_v3.json")
    parser.add_argument("--weights", type=Path, default=ROOT / "results/independent_behavior_v3_large/evaluator_weights.npz")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-decisions", type=int, default=5)
    args = parser.parse_args()
    output = args.output or args.session
    output.mkdir(parents=True, exist_ok=True)
    results, predictions = evaluate(args.session, args.personas, args.weights, args.min_decisions)
    (output / "ue_behavior_eval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (output / "ue_behavior_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["tier", "persona_id", "n_decisions", "axis", "truth", "predicted", "confidence"])
        writer.writeheader()
        writer.writerows(predictions)
    sequences, _ = load_tier_sequences(args.session)
    with (output / "source_trajectories.jsonl").open("w", encoding="utf-8") as handle:
        for tier, by_persona in sequences.items():
            for persona_id, rows in sorted(by_persona.items()):
                for row in rows:
                    canonical = {
                        "tier": tier,
                        "persona_id": persona_id,
                        "t": float(row.get("t", 0.0)),
                        "policy_action_index": _action_index(row),
                        "pos": row.get("pos", []),
                        "needs": row.get("needs", []),
                    }
                    handle.write(json.dumps(canonical, separators=(",", ":")) + "\n")
    _plot(results, output)
    print(json.dumps({
        "actor": results["tiers"].get("actor", {}),
        "mass": results["tiers"].get("mass", {}),
        "paired": results["paired"],
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
