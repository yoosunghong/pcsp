"""Frozen-feature behavioral evaluator with no PCSP model dependencies.

This module accepts observation/action trajectories and exposes only ordinary
behavioral statistics plus a linear ridge probe.  It intentionally does not
import the policy, persona projection, or learned trajectory encoder.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ACTION_GROUPS = {
    "work": (0, 1),
    "recovery": (2, 3, 4, 5, 8, 9, 10, 11, 12, 13),
    "social": (6, 7, 14),
    "explore": (15,),
    "movement": (16, 17, 18, 19),
}


def _lag1(values: np.ndarray) -> float:
    if len(values) < 3 or values[:-1].std() < 1e-12 or values[1:].std() < 1e-12:
        return 0.0
    return float(np.corrcoef(values[:-1], values[1:])[0, 1])


def feature_names(n_actions: int = 20, observation_indices: tuple[int, ...] = tuple(range(24))) -> dict[str, list[str]]:
    action = [f"action_hist[{a}]" for a in range(n_actions)]
    action += [f"transition[{a}->{b}]" for a in range(n_actions) for b in range(n_actions)]
    action += [f"mean_run_length[{a}]" for a in range(n_actions)]
    action += [f"lag1_group[{name}]" for name in ACTION_GROUPS]
    contextual = list(action)
    for index in observation_indices:
        contextual += [f"obs_{stat}[{index}]" for stat in ("mean", "std", "p10", "p50", "p90", "lag1")]
    contextual += [f"chosen_need_delta[action={a},need={need}]" for a in range(n_actions) for need in range(8)]
    return {"action_only": action, "behavior_context": contextual}


def extract_features(
    actions: np.ndarray,
    observations: np.ndarray,
    n_actions: int = 20,
    observation_indices: tuple[int, ...] = tuple(range(24)),
) -> dict[str, np.ndarray]:
    actions = np.asarray(actions, dtype=np.int64)
    observations = np.asarray(observations, dtype=np.float64)
    if len(actions) < 2 or len(observations) != len(actions):
        raise ValueError("actions and observations must have the same length >= 2")
    if actions.min() < 0 or actions.max() >= n_actions:
        raise ValueError("action outside configured ontology")
    if observations.ndim != 2 or observations.shape[1] <= max(observation_indices):
        raise ValueError("observation matrix does not cover frozen summary indices")

    hist = np.bincount(actions, minlength=n_actions).astype(np.float64) / len(actions)
    transitions = np.zeros((n_actions, n_actions), dtype=np.float64)
    np.add.at(transitions, (actions[:-1], actions[1:]), 1.0)
    transitions /= len(actions) - 1
    run_sum = np.zeros(n_actions, dtype=np.float64)
    run_count = np.zeros(n_actions, dtype=np.float64)
    start = 0
    for index in range(1, len(actions) + 1):
        if index == len(actions) or actions[index] != actions[start]:
            action = int(actions[start])
            run_sum[action] += index - start
            run_count[action] += 1
            start = index
    runs = np.divide(run_sum, run_count, out=np.zeros_like(run_sum), where=run_count > 0)
    group_lag = np.asarray([_lag1(np.isin(actions, members).astype(np.float64)) for members in ACTION_GROUPS.values()])
    action_only = np.concatenate((hist, transitions.ravel(), runs, group_lag))

    selected = observations[:, observation_indices]
    obs_stats = []
    for column in selected.T:
        obs_stats.extend((column.mean(), column.std(), *np.quantile(column, (0.1, 0.5, 0.9)), _lag1(column)))
    needs = observations[:, 3:11]
    need_delta = np.zeros((n_actions, 8), dtype=np.float64)
    baseline = needs.mean(axis=0)
    for action in range(n_actions):
        mask = actions == action
        if mask.any():
            need_delta[action] = needs[mask].mean(axis=0) - baseline
    contextual = np.concatenate((action_only, np.asarray(obs_stats), need_delta.ravel()))
    result = {"action_only": action_only, "behavior_context": contextual}
    expected = feature_names(n_actions, observation_indices)
    for key, values in result.items():
        if len(values) != len(expected[key]) or not np.isfinite(values).all():
            raise RuntimeError(f"invalid {key} feature vector")
    return result


def balanced_accuracy(y: np.ndarray, pred: np.ndarray, n_classes: int = 3) -> float:
    recalls = [float(np.mean(pred[y == label] == label)) for label in range(n_classes) if np.any(y == label)]
    return float(np.mean(recalls))


def macro_f1(y: np.ndarray, pred: np.ndarray, n_classes: int = 3) -> float:
    scores = []
    for label in range(n_classes):
        tp = int(np.sum((y == label) & (pred == label)))
        fp = int(np.sum((y != label) & (pred == label)))
        fn = int(np.sum((y == label) & (pred != label)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(scores))


def classification_metrics(y: np.ndarray, probabilities: np.ndarray) -> dict:
    pred = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    correct = (pred == y).astype(np.float64)
    order = np.argsort(confidence)
    ece = 0.0
    for indices in np.array_split(order, 10):
        if len(indices):
            ece += len(indices) / len(y) * abs(correct[indices].mean() - confidence[indices].mean())
    return {
        "n": int(len(y)),
        "accuracy": float(correct.mean()),
        "balanced_accuracy": balanced_accuracy(y, pred),
        "macro_f1": macro_f1(y, pred),
        "ece_equal_frequency_10": float(ece),
    }


@dataclass
class RidgeProbe:
    regularization: float
    temperature: float
    mean: np.ndarray
    scale: np.ndarray
    weight: np.ndarray

    def probabilities(self, values: np.ndarray) -> np.ndarray:
        z = (values - self.mean) / self.scale
        z = np.concatenate((z, np.ones((len(z), 1))), axis=1)
        logits = z @ self.weight / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        return exp / exp.sum(axis=1, keepdims=True)


def fit_ridge_probe(
    train_x: np.ndarray,
    train_y: np.ndarray,
    calibration_x: np.ndarray,
    calibration_y: np.ndarray,
    regularizations: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0),
) -> RidgeProbe:
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    x = (train_x - mean) / scale
    cal = (calibration_x - mean) / scale
    x = np.concatenate((x, np.ones((len(x), 1))), axis=1)
    cal = np.concatenate((cal, np.ones((len(cal), 1))), axis=1)
    targets = np.eye(3)[train_y]
    # Target balancing avoids majority-class dominance without changing the
    # shared feature transform.
    counts = np.bincount(train_y, minlength=3).astype(np.float64)
    targets *= len(train_y) / (3 * np.maximum(counts, 1.0))[None, :]
    gram = x.T @ x
    cross = x.T @ targets
    best: tuple[float, float, float, np.ndarray] | None = None
    penalty = np.eye(x.shape[1])
    penalty[-1, -1] = 0.0
    for value in regularizations:
        weight = np.linalg.solve(gram + value * penalty, cross)
        logits = cal @ weight
        for temperature in (0.25, 0.5, 1.0, 2.0, 4.0):
            scaled = logits / temperature
            scaled -= scaled.max(axis=1, keepdims=True)
            probabilities = np.exp(scaled)
            probabilities /= probabilities.sum(axis=1, keepdims=True)
            score = balanced_accuracy(calibration_y, probabilities.argmax(axis=1))
            nll = -float(np.mean(np.log(np.maximum(probabilities[np.arange(len(calibration_y)), calibration_y], 1e-12))))
            candidate = (score, -nll, -value)
            if best is None or candidate > best[:3]:
                best = (score, -nll, -value, weight.copy())
                best_temperature = temperature
    assert best is not None
    return RidgeProbe(-best[2], float(best_temperature), mean, scale, best[3])
