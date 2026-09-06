"""Audit which persona attributes survive the learned PCSP projection.

The audit stays outside the policy and trajectory encoder. It compares frozen
1024-d Qwen embeddings with the 64-d vectors produced by the trained rank-16
projection using the repository's fixed 240/60 split.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.training.pcsp_trainer import PCSPActorCritic

AXES = ("E", "N", "A", "C", "O")
LEVELS = {"low": 0, "mid": 1, "high": 2}
LAMBDA_GRID = (1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)


def _load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean([np.mean(y_pred[y_true == label] == label) for label in np.unique(y_true)]))


def _macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    scores = []
    for label in np.unique(y_true):
        tp = int(np.sum((y_true == label) & (y_pred == label)))
        fp = int(np.sum((y_true != label) & (y_pred == label)))
        fn = int(np.sum((y_true == label) & (y_pred != label)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(scores))


def _standardize(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0, keepdims=True)
    scale = train.std(axis=0, keepdims=True)
    scale[scale < 1e-8] = 1.0
    return (train - mean) / scale, (test - mean) / scale


def _ridge_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, regularization: float) -> np.ndarray:
    classes = int(train_y.max()) + 1
    x = np.concatenate([train_x, np.ones((len(train_x), 1), dtype=np.float64)], axis=1)
    xt = np.concatenate([test_x, np.ones((len(test_x), 1), dtype=np.float64)], axis=1)
    targets = np.eye(classes, dtype=np.float64)[train_y]
    gram = x @ x.T
    weights = x.T @ np.linalg.solve(gram + regularization * np.eye(len(x)), targets)
    return np.argmax(xt @ weights, axis=1)


def _select_lambda(x: np.ndarray, y: np.ndarray) -> float:
    folds = np.empty(len(y), dtype=np.int64)
    for label in np.unique(y):
        indices = np.flatnonzero(y == label)
        folds[indices] = np.arange(len(indices)) % 5
    best_score, best_lambda = -math.inf, LAMBDA_GRID[0]
    for value in LAMBDA_GRID:
        scores = []
        for fold in range(5):
            fit = folds != fold
            valid = ~fit
            fit_x, valid_x = _standardize(x[fit], x[valid])
            scores.append(_balanced_accuracy(y[valid], _ridge_predict(fit_x, y[fit], valid_x, value)))
        score = float(np.mean(scores))
        if score > best_score:
            best_score, best_lambda = score, value
    return float(best_lambda)


def _probe(representation: str, train_x: np.ndarray, test_x: np.ndarray, train_records: list[dict], test_records: list[dict]) -> list[dict]:
    rows = []
    for axis in AXES:
        train_y = np.asarray([LEVELS[row["big_five"][axis]] for row in train_records])
        test_y = np.asarray([LEVELS[row["big_five"][axis]] for row in test_records])
        regularization = _select_lambda(train_x, train_y)
        fit_x, eval_x = _standardize(train_x, test_x)
        pred = _ridge_predict(fit_x, train_y, eval_x, regularization)
        rows.append({
            "representation": representation,
            "axis": axis,
            "balanced_accuracy": _balanced_accuracy(test_y, pred),
            "macro_f1": _macro_f1(test_y, pred),
            "regularization": regularization,
            "n_train": len(train_y),
            "n_test": len(test_y),
        })
    return rows


def _spectrum(values: np.ndarray) -> dict:
    centered = values.astype(np.float64) - values.mean(axis=0, keepdims=True)
    singular = np.linalg.svd(centered, compute_uv=False)
    energy = singular**2
    probabilities = energy / max(float(energy.sum()), np.finfo(np.float64).eps)
    nonzero = probabilities > 0
    threshold = singular[0] * 1e-6 if len(singular) else 0.0
    return {
        "nominal_rank_1e-6": int(np.sum(singular > threshold)),
        "effective_rank": float(np.exp(-np.sum(probabilities[nonzero] * np.log(probabilities[nonzero])))),
        "stable_rank": float(energy.sum() / max(float(energy[0]), np.finfo(np.float64).eps)),
        "singular_values": singular.tolist(),
        "cumulative_energy": np.cumsum(probabilities).tolist(),
    }


def _rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    ranks[order] = np.arange(len(values), dtype=np.float64)
    return ranks


def _pairwise_cosine_geometry(raw: np.ndarray, projected: np.ndarray) -> dict:
    raw_n = raw / np.maximum(np.linalg.norm(raw, axis=1, keepdims=True), 1e-12)
    proj_n = projected / np.maximum(np.linalg.norm(projected, axis=1, keepdims=True), 1e-12)
    tri = np.triu_indices(len(raw), k=1)
    raw_sim = (raw_n @ raw_n.T)[tri]
    proj_sim = (proj_n @ proj_n.T)[tri]
    return {
        "pair_count": len(raw_sim),
        "pearson_r": float(np.corrcoef(raw_sim, proj_sim)[0, 1]),
        "spearman_rho": float(np.corrcoef(_rankdata(raw_sim), _rankdata(proj_sim))[0, 1]),
    }


def _plot(rows: list[dict], raw_spectrum: dict, projected_spectrum: dict, out_dir: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8))
    x = np.arange(len(AXES))
    width = 0.34
    scores = lambda rep: [next(r["balanced_accuracy"] for r in rows if r["representation"] == rep and r["axis"] == axis) for axis in AXES]
    axes[0].bar(x - width / 2, scores("raw_1024"), width, label="Raw Qwen (1024-d)", color="#667085")
    axes[0].bar(x + width / 2, scores("projected_64"), width, label="Learned projection (64-d)", color="#16A6A1")
    axes[0].axhline(1 / 3, color="#D92D20", linestyle="--", linewidth=1.2, label="Chance")
    axes[0].set_xticks(x, AXES)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Held-out balanced accuracy")
    axes[0].set_title("Big Five information retained")
    axes[0].legend(frameon=False, fontsize=8)

    raw_energy = np.asarray(raw_spectrum["cumulative_energy"])
    projected_energy = np.asarray(projected_spectrum["cumulative_energy"])
    axes[1].plot(np.arange(1, len(raw_energy) + 1), raw_energy, color="#667085", label=f"Raw, erank={raw_spectrum['effective_rank']:.1f}")
    axes[1].plot(np.arange(1, len(projected_energy) + 1), projected_energy, color="#16A6A1", linewidth=2.2, label=f"Projected, erank={projected_spectrum['effective_rank']:.1f}")
    axes[1].axvline(16, color="#7F56D9", linestyle="--", linewidth=1.2, label="LoRA rank ceiling")
    axes[1].set_xlim(1, min(80, len(raw_energy)))
    axes[1].set_ylim(0, 1.02)
    axes[1].set_xlabel("Principal component")
    axes[1].set_ylabel("Cumulative centered energy")
    axes[1].set_title("Projection spectrum")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("PCSP persona projection audit", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_dir / "projection_audit.png", dpi=180, bbox_inches="tight")
    fig.savefig(out_dir / "projection_audit.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "results/pcsp_v3/full/policy.pt")
    parser.add_argument("--embeddings", type=Path, default=ROOT / "results/embeddings/persona_embeddings_300.npy")
    parser.add_argument("--train", type=Path, default=ROOT / "data/personas/train_240_v3.json")
    parser.add_argument("--test", type=Path, default=ROOT / "data/personas/test_60_v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/persona_projection_audit")
    args = parser.parse_args()

    train_records = _load_json(args.train)
    test_records = _load_json(args.test)
    embeddings = np.load(args.embeddings).astype(np.float32)
    ids = [int(row["id"]) for row in train_records + test_records]
    if min(ids) < 1 or max(ids) > len(embeddings):
        raise ValueError(f"Persona ids {min(ids)}..{max(ids)} exceed embedding matrix {embeddings.shape}")

    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    model = PCSPActorCritic(
        obs_dim=int(state["actor_b1.linear.weight"].shape[1]),
        n_actions=int(state["actor_head.weight"].shape[0]),
    )
    model.load_state_dict(state)
    model.eval()

    all_raw = embeddings[np.asarray(ids) - 1]
    with torch.inference_mode():
        all_projected = model.persona_proj(torch.from_numpy(all_raw)).numpy()
    n_train = len(train_records)
    train_raw, test_raw = all_raw[:n_train], all_raw[n_train:]
    train_projected, test_projected = all_projected[:n_train], all_projected[n_train:]

    rows = _probe("raw_1024", train_raw, test_raw, train_records, test_records)
    rows += _probe("projected_64", train_projected, test_projected, train_records, test_records)
    raw_spectrum = _spectrum(all_raw)
    projected_spectrum = _spectrum(all_projected)
    projection_weight = state["persona_proj.lora_B.weight"].numpy() @ state["persona_proj.lora_A.weight"].numpy()
    weight_spectrum = _spectrum(projection_weight.T)

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "axis_probe.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    mean_probe = {
        representation: {
            "balanced_accuracy": float(np.mean([r["balanced_accuracy"] for r in rows if r["representation"] == representation])),
            "macro_f1": float(np.mean([r["macro_f1"] for r in rows if r["representation"] == representation])),
        }
        for representation in ("raw_1024", "projected_64")
    }
    summary = {
        "protocol": {
            "train_file": str(args.train.relative_to(ROOT)),
            "test_file": str(args.test.relative_to(ROOT)),
            "checkpoint": str(args.checkpoint.relative_to(ROOT)),
            "n_train": n_train,
            "n_test": len(test_records),
            "probe": "standardized multiclass ridge; lambda selected by deterministic stratified 5-fold train-only CV",
            "chance_balanced_accuracy": 1 / 3,
        },
        "mean_probe": mean_probe,
        "axis_probe": rows,
        "raw_spectrum": raw_spectrum,
        "projected_spectrum": projected_spectrum,
        "projection_weight_spectrum": weight_spectrum,
        "raw_to_projected_geometry": _pairwise_cosine_geometry(all_raw, all_projected),
    }
    with (args.output / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    _plot(rows, raw_spectrum, projected_spectrum, args.output)
    print(json.dumps({
        "mean_probe": mean_probe,
        "projected_effective_rank": projected_spectrum["effective_rank"],
        "projected_nominal_rank": projected_spectrum["nominal_rank_1e-6"],
        "geometry": summary["raw_to_projected_geometry"],
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
