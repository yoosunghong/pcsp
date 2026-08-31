"""Evaluate v3-large policies from behavior traces without learned evaluators.

The rollout side imports the policy only to generate actions.  All feature
extraction and linear probing lives in ``src.eval.independent_behavior``, which
has no dependency on PCSP, its projection, logits, or trajectory encoder.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import PersonaConfig
from src.env.mini_inzoi_v3_large import MiniInzoiV3LargeEnv, N_AGENTS
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_LARGE
from src.eval.independent_behavior import (
    balanced_accuracy,
    classification_metrics,
    extract_features,
    feature_names,
    fit_ridge_probe,
)
from src.training.pcsp_trainer import PCSPActorCritic

AXES = ("E", "N", "A", "C", "O")
LEVELS = {"low": 0, "mid": 1, "high": 2}
MODES = ("full", "no_consist")
SEEDS = (42, 43, 44)


def _load(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _collect_batch(
    policy: PCSPActorCritic,
    records: list[dict],
    embeddings: np.ndarray,
    device: torch.device,
    rollout_seed: int,
    steps: int,
) -> list[dict]:
    actual = len(records)
    padded = list(records)
    while len(padded) < N_AGENTS:
        padded.append(records[len(padded) % actual])
    configs = [PersonaConfig.from_dict(row) for row in padded]
    env = MiniInzoiV3LargeEnv(personas=configs, max_steps=steps)
    env.reset(seed=rollout_seed)
    e_llm = torch.from_numpy(embeddings[[int(row["id"]) - 1 for row in padded]].astype(np.float32)).to(device)
    obs_sequences = [[] for _ in padded]
    action_sequences = [[] for _ in padded]
    torch.manual_seed(rollout_seed + 1_000_003)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(rollout_seed + 1_000_003)

    for _ in range(steps):
        observations = np.stack([env.observe(agent) for agent in env.possible_agents])
        with torch.inference_mode():
            logits = policy.action_logits(torch.from_numpy(observations).to(device), e_llm)
            actions = torch.distributions.Categorical(logits=logits).sample().cpu().numpy()
        for index, (agent, action) in enumerate(zip(env.possible_agents, actions)):
            if env.agent_selection != agent:
                raise RuntimeError("unexpected AEC agent order")
            obs_sequences[index].append(observations[index])
            action_sequences[index].append(int(action))
            env.step(int(action))
    env.close()
    return [extract_features(np.asarray(action_sequences[i]), np.asarray(obs_sequences[i])) for i in range(actual)]


def _generate_cache(args: argparse.Namespace, device: torch.device) -> dict[str, np.ndarray]:
    train_records = _load(args.train_personas)
    test_records = _load(args.test_personas)
    if len(train_records) != 400 or len(test_records) != 100:
        raise ValueError("frozen v3-large protocol expects 400 train and 100 test personas")
    split_records = (
        [(row, "evaluator_train") for row in train_records[:320]]
        + [(row, "evaluator_calibration") for row in train_records[320:]]
        + [(row, "evaluator_test") for row in test_records]
    )
    embeddings = np.load(args.embeddings).astype(np.float32)
    rows: list[dict] = []
    started = time.time()
    for mode_index, mode in enumerate(MODES):
        for policy_seed in SEEDS:
            checkpoint = args.checkpoints_root / f"{mode}_seed{policy_seed}" / mode / "policy.pt"
            state = torch.load(checkpoint, map_location="cpu", weights_only=True)
            policy = PCSPActorCritic(OBS_DIM_V3_LARGE, N_ACTIONS_V3)
            policy.load_state_dict(state)
            policy.to(device).eval()
            completed = 0
            for split_name in ("evaluator_train", "evaluator_calibration", "evaluator_test"):
                group = [record for record, split in split_records if split == split_name]
                for batch_start in range(0, len(group), N_AGENTS):
                    batch = group[batch_start:batch_start + N_AGENTS]
                    rollout_seed = 90_000 + mode_index * 10_000 + policy_seed * 101 + batch_start
                    features = _collect_batch(policy, batch, embeddings, device, rollout_seed, args.steps)
                    for record, values in zip(batch, features):
                        rows.append({
                            "mode": mode,
                            "policy_seed": policy_seed,
                            "persona_id": int(record["id"]),
                            "split": split_name,
                            "labels": [LEVELS[record["big_five"][axis]] for axis in AXES],
                            "action_only": values["action_only"].astype(np.float32),
                            "behavior_context": values["behavior_context"].astype(np.float32),
                        })
                    completed += len(batch)
                    print(f"[{mode}@{policy_seed}] {completed:3d}/500", flush=True)
            del policy
            if device.type == "cuda":
                torch.cuda.empty_cache()

    cache = {
        "mode": np.asarray([row["mode"] for row in rows]),
        "policy_seed": np.asarray([row["policy_seed"] for row in rows], dtype=np.int16),
        "persona_id": np.asarray([row["persona_id"] for row in rows], dtype=np.int16),
        "split": np.asarray([row["split"] for row in rows]),
        "labels": np.asarray([row["labels"] for row in rows], dtype=np.int8),
        "action_only": np.stack([row["action_only"] for row in rows]),
        "behavior_context": np.stack([row["behavior_context"] for row in rows]),
        "generation_seconds": np.asarray([time.time() - started]),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output / "behavior_features.npz", **cache)
    return cache


def _load_cache(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _mean_axis_score(labels: np.ndarray, probabilities: list[np.ndarray], indices: np.ndarray) -> float:
    return float(np.mean([
        balanced_accuracy(labels[indices, axis], probabilities[axis][indices].argmax(axis=1))
        for axis in range(len(AXES))
    ]))


def _resampling(cache: dict[str, np.ndarray], probabilities: list[np.ndarray], replicates: int, seed: int) -> dict:
    test = cache["split"] == "evaluator_test"
    persona_ids = np.unique(cache["persona_id"][test])
    rng = np.random.default_rng(seed)
    bootstrap = {mode: [] for mode in MODES}
    bootstrap["full_minus_no_consist"] = []
    for _ in range(replicates):
        sampled = rng.choice(persona_ids, len(persona_ids), replace=True)
        sampled_indices = {
            mode: np.concatenate([np.flatnonzero(test & (cache["mode"] == mode) & (cache["persona_id"] == pid)) for pid in sampled])
            for mode in MODES
        }
        scores = {mode: _mean_axis_score(cache["labels"], probabilities, indices) for mode, indices in sampled_indices.items()}
        for mode in MODES:
            bootstrap[mode].append(scores[mode])
        bootstrap["full_minus_no_consist"].append(scores["full"] - scores["no_consist"])

    return {
        "replicates": replicates,
        "bootstrap_95": {key: [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))] for key, values in bootstrap.items()},
    }


def _evaluate_representation(cache: dict[str, np.ndarray], representation: str, replicates: int) -> tuple[dict, list[np.ndarray], list]:
    train = cache["split"] == "evaluator_train"
    calibration = cache["split"] == "evaluator_calibration"
    test = cache["split"] == "evaluator_test"
    x = cache[representation].astype(np.float64)
    probabilities: list[np.ndarray] = []
    probes = []
    probe_config = {}
    for axis_index, axis in enumerate(AXES):
        probe = fit_ridge_probe(x[train], cache["labels"][train, axis_index], x[calibration], cache["labels"][calibration, axis_index])
        probes.append(probe)
        probabilities.append(probe.probabilities(x))
        probe_config[axis] = {"regularization": probe.regularization, "temperature": probe.temperature}

    by_variant = {}
    by_variant_seed = {}
    for mode in MODES:
        mode_indices = np.flatnonzero(test & (cache["mode"] == mode))
        axis_metrics = {
            axis: classification_metrics(cache["labels"][mode_indices, i], probabilities[i][mode_indices])
            for i, axis in enumerate(AXES)
        }
        by_variant[mode] = {
            "mean_balanced_accuracy": float(np.mean([value["balanced_accuracy"] for value in axis_metrics.values()])),
            "mean_macro_f1": float(np.mean([value["macro_f1"] for value in axis_metrics.values()])),
            "axes": axis_metrics,
        }
        for policy_seed in SEEDS:
            indices = np.flatnonzero(test & (cache["mode"] == mode) & (cache["policy_seed"] == policy_seed))
            by_variant_seed[f"{mode}@{policy_seed}"] = {
                "mean_balanced_accuracy": _mean_axis_score(cache["labels"], probabilities, indices),
                "n": len(indices),
            }
    resampling = _resampling(cache, probabilities, replicates, seed=71_003 + len(representation))
    observed_delta = by_variant["full"]["mean_balanced_accuracy"] - by_variant["no_consist"]["mean_balanced_accuracy"]
    # Paired randomization: exchange full/no-consistency predictions for every
    # seed of a sampled persona, then recompute the exact balanced-accuracy
    # statistic.  This preserves labels, persona clusters, and seed pairing.
    rng = np.random.default_rng(83_011 + len(representation))
    persona_ids = np.unique(cache["persona_id"][test])
    keys = [(seed, int(pid)) for seed in SEEDS for pid in persona_ids]
    full_indices = np.asarray([
        np.flatnonzero(test & (cache["mode"] == "full") & (cache["policy_seed"] == seed) & (cache["persona_id"] == pid))[0]
        for seed, pid in keys
    ])
    no_indices = np.asarray([
        np.flatnonzero(test & (cache["mode"] == "no_consist") & (cache["policy_seed"] == seed) & (cache["persona_id"] == pid))[0]
        for seed, pid in keys
    ])
    null_values = []
    for _ in range(replicates):
        swap_persona = dict(zip(persona_ids.tolist(), rng.integers(0, 2, len(persona_ids)).astype(bool).tolist()))
        swap = np.asarray([swap_persona[pid] for _, pid in keys])
        perm_full = np.where(swap, no_indices, full_indices)
        perm_no = np.where(swap, full_indices, no_indices)
        full_score = _mean_axis_score(cache["labels"], probabilities, perm_full)
        no_score = _mean_axis_score(cache["labels"], probabilities, perm_no)
        null_values.append(full_score - no_score)
    null = np.asarray(null_values)
    resampling["permutation_delta"] = {
        "observed": observed_delta,
        "null_mean": float(null.mean()),
        "p_two_sided": float((1 + np.sum(np.abs(null) >= abs(observed_delta))) / (1 + replicates)),
    }
    return {"probe": probe_config, "by_variant": by_variant, "by_variant_seed": by_variant_seed, "resampling": resampling}, probabilities, probes


def _plot(results: dict, output: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.7), sharey=True)
    x = np.arange(len(AXES))
    for panel, representation in enumerate(("action_only", "behavior_context")):
        axis = axes[panel]
        values = results["representations"][representation]["by_variant"]
        full = [values["full"]["axes"][name]["balanced_accuracy"] for name in AXES]
        no_consist = [values["no_consist"]["axes"][name]["balanced_accuracy"] for name in AXES]
        axis.bar(x - 0.18, full, 0.36, label="PCSP full", color="#16A6A1")
        axis.bar(x + 0.18, no_consist, 0.36, label="No consistency", color="#F79009")
        axis.axhline(1 / 3, color="#D92D20", linestyle="--", linewidth=1.1, label="Chance")
        axis.set_xticks(x, AXES)
        axis.set_ylim(0, 1.02)
        axis.set_title("Action-only" if panel == 0 else "Action + state-response")
        axis.set_ylabel("Held-out balanced accuracy" if panel == 0 else "")
        axis.legend(frameon=False, fontsize=8)
    fig.suptitle("Independent v3-large behavioral trait evaluation", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "independent_behavior_eval.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "independent_behavior_eval.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints-root", type=Path, default=ROOT / "results/pcsp_v3_large")
    parser.add_argument("--embeddings", type=Path, default=REPO / "results/embeddings/persona_embeddings_500.npy")
    parser.add_argument("--train-personas", type=Path, default=ROOT / "data/personas/train_400_v3.json")
    parser.add_argument("--test-personas", type=Path, default=ROOT / "data/personas/test_100_v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/independent_behavior_v3_large")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--reuse-cache", action="store_true")
    args = parser.parse_args()
    device = torch.device(args.device if args.device == "cpu" or torch.cuda.is_available() else "cpu")
    cache_path = args.output / "behavior_features.npz"
    cache = _load_cache(cache_path) if args.reuse_cache and cache_path.exists() else _generate_cache(args, device)
    expected_rows = len(MODES) * len(SEEDS) * 500
    if len(cache["mode"]) != expected_rows:
        raise RuntimeError(f"feature cache has {len(cache['mode'])} rows; expected {expected_rows}")

    results = {
        "protocol": {
            "independence": "evaluator uses frozen environment trajectory statistics only; no PCSP projection, logits, or learned trajectory encoder",
            "evaluator_train_personas": 320,
            "evaluator_calibration_personas": 80,
            "evaluator_test_personas": 100,
            "policy_variants": list(MODES),
            "policy_seeds": list(SEEDS),
            "steps_per_trajectory": args.steps,
            "rollout_semantics": "one synchronously observed action per agent per environment cycle",
            "primary_representation": "action_only",
        },
        "feature_counts": {key: len(value) for key, value in feature_names().items()},
        "representations": {},
    }
    all_probabilities = {}
    all_probes = {}
    for representation in ("action_only", "behavior_context"):
        evaluated, probabilities, probes = _evaluate_representation(cache, representation, args.resamples)
        results["representations"][representation] = evaluated
        all_probabilities[representation] = probabilities
        all_probes[representation] = probes
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (args.output / "feature_schema.json").write_text(json.dumps(feature_names(), indent=2), encoding="utf-8")
    weight_payload = {}
    for representation, probes in all_probes.items():
        for axis, probe in zip(AXES, probes):
            prefix = f"{representation}_{axis}"
            weight_payload[f"{prefix}_weight"] = probe.weight
            weight_payload[f"{prefix}_mean"] = probe.mean
            weight_payload[f"{prefix}_scale"] = probe.scale
            weight_payload[f"{prefix}_regularization"] = np.asarray([probe.regularization])
            weight_payload[f"{prefix}_temperature"] = np.asarray([probe.temperature])
    np.savez_compressed(args.output / "evaluator_weights.npz", **weight_payload)
    with (args.output / "test_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["mode", "policy_seed", "persona_id", "axis", "truth", "representation", "predicted", "confidence"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        test_indices = np.flatnonzero(cache["split"] == "evaluator_test")
        for representation, probabilities in all_probabilities.items():
            for index in test_indices:
                for axis_index, axis in enumerate(AXES):
                    prob = probabilities[axis_index][index]
                    writer.writerow({
                        "mode": cache["mode"][index], "policy_seed": int(cache["policy_seed"][index]),
                        "persona_id": int(cache["persona_id"][index]), "axis": axis,
                        "truth": int(cache["labels"][index, axis_index]), "representation": representation,
                        "predicted": int(prob.argmax()), "confidence": float(prob.max()),
                    })
    _plot(results, args.output)
    print(json.dumps({
        representation: {
            mode: results["representations"][representation]["by_variant"][mode]["mean_balanced_accuracy"]
            for mode in MODES
        }
        for representation in ("action_only", "behavior_context")
    }, indent=2))


if __name__ == "__main__":
    main()
