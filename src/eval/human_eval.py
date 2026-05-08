"""
Human evaluation analysis for PCSP.

Supported study types:
  1. 2AFC persona identification
     Columns: participant_id, item_id, response, confidence, response_time_sec.
     Join with an answer-key CSV containing item_id and correct_option.

  2. Legacy Likert distinctiveness
     Columns: participant_id, persona_pair_id, likert_score.

Usage:
    conda run -n paper python src/eval/human_eval.py \
        --csv data/human_eval/prolific_results.csv \
        --answer_key data/human_eval/persona_identification_survey_ko_answer_key.csv \
        --output results/eval/human_eval_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _std(values: list[float]) -> float | None:
    return float(np.std(values)) if values else None


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


def krippendorff_alpha_nominal(ratings_by_rater: list[list[str | None]]) -> float | None:
    """Krippendorff alpha for nominal labels such as A/B responses."""
    if len(ratings_by_rater) < 2:
        return None
    n_items = max(len(r) for r in ratings_by_rater)
    data = [r + [None] * (n_items - len(r)) for r in ratings_by_rater]

    values = sorted({v for row in data for v in row if v is not None})
    if len(values) <= 1:
        return 1.0
    idx = {v: i for i, v in enumerate(values)}
    coincidence = np.zeros((len(values), len(values)), dtype=float)

    for item_idx in range(n_items):
        obs = [row[item_idx] for row in data if row[item_idx] is not None]
        m = len(obs)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                coincidence[idx[obs[i]], idx[obs[j]]] += 1 / (m - 1)

    total = float(coincidence.sum())
    if total == 0:
        return None
    observed = float(coincidence.sum() - np.trace(coincidence)) / total
    marginals = coincidence.sum(axis=1)
    expected = 1.0 - float(np.sum(marginals * (marginals - 1))) / (total * (total - 1))
    if expected <= 0:
        return 1.0
    return float(1.0 - observed / expected)


def _group_accuracy(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "unknown")), []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for group, group_rows in groups.items():
        n = len(group_rows)
        k = sum(1 for r in group_rows if r["is_correct"])
        lo, hi = wilson_ci(k, n)
        out[group] = {
            "n": n,
            "correct": k,
            "accuracy": k / n if n else 0.0,
            "wilson_ci_95": [lo, hi],
            "mean_confidence": _mean([r["confidence"] for r in group_rows if r["confidence"] is not None]),
            "mean_response_time_sec": _mean([
                r["response_time_sec"] for r in group_rows if r["response_time_sec"] is not None
            ]),
        }
    return out


def process_2afc_identification(
    csv_path: str | Path,
    answer_key_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    responses = _read_csv(Path(csv_path))
    key_rows = _read_csv(Path(answer_key_path))
    key = {row["item_id"]: row for row in key_rows}

    scored: list[dict[str, Any]] = []
    for row in responses:
        item_id = row.get("item_id", "").strip()
        if item_id not in key:
            continue
        response = row.get("response", "").strip().upper()
        if response not in {"A", "B"}:
            continue
        correct_option = key[item_id]["correct_option"].strip().upper()
        confidence = row.get("confidence", "").strip()
        response_time = row.get("response_time_sec", "").strip()
        scored.append({
            "participant_id": row.get("participant_id", "unknown"),
            "item_id": item_id,
            "response": response,
            "correct_option": correct_option,
            "is_correct": response == correct_option,
            "model": key[item_id].get("model", row.get("model", "unknown")),
            "split": key[item_id].get("split", row.get("split", "unknown")),
            "confidence": float(confidence) if confidence else None,
            "response_time_sec": float(response_time) if response_time else None,
        })

    n = len(scored)
    k = sum(1 for row in scored if row["is_correct"])
    lo, hi = wilson_ci(k, n)

    participant_ids = sorted({row["participant_id"] for row in scored})
    item_ids = sorted({row["item_id"] for row in scored})
    ratings_by_rater: list[list[str | None]] = []
    for pid in participant_ids:
        by_item = {row["item_id"]: row["response"] for row in scored if row["participant_id"] == pid}
        ratings_by_rater.append([by_item.get(item_id) for item_id in item_ids])

    result: dict[str, Any] = {
        "study_type": "2afc_persona_identification",
        "n_participants": len(participant_ids),
        "n_items": len(item_ids),
        "n_responses": n,
        "correct": k,
        "chance_level": 0.5,
        "accuracy": k / n if n else 0.0,
        "wilson_ci_95": [lo, hi],
        "krippendorff_alpha_nominal": krippendorff_alpha_nominal(ratings_by_rater),
        "mean_confidence": _mean([r["confidence"] for r in scored if r["confidence"] is not None]),
        "mean_response_time_sec": _mean([r["response_time_sec"] for r in scored if r["response_time_sec"] is not None]),
        "by_model": _group_accuracy(scored, "model"),
        "by_split": _group_accuracy(scored, "split"),
    }

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def process_likert_distinctiveness(
    csv_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    rows = _read_csv(Path(csv_path))
    scores = [float(r["likert_score"]) for r in rows if r.get("likert_score")]
    by_model: dict[str, list[float]] = {}
    for row in rows:
        if not row.get("likert_score"):
            continue
        by_model.setdefault(row.get("model", "unknown"), []).append(float(row["likert_score"]))

    result: dict[str, Any] = {
        "study_type": "likert_distinctiveness",
        "n_responses": len(scores),
        "mean_score": _mean(scores),
        "std_score": _std(scores),
        "by_model": {
            model: {"n": len(vals), "mean": _mean(vals), "std": _std(vals)}
            for model, vals in by_model.items()
        },
        "scale": "1=not distinct, 5=very distinct",
    }
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def _placeholder_result() -> dict[str, Any]:
    return {
        "status": "pending",
        "note": "Human evaluation has not been collected yet.",
        "recommended_study": "2AFC persona identification on real held-out PCSP rollouts.",
        "minimum_response_columns": ["participant_id", "item_id", "response", "confidence", "response_time_sec"],
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="Participant response CSV.")
    p.add_argument("--answer_key", default=None, help="2AFC answer-key CSV.")
    p.add_argument("--output", default="results/eval/human_eval_summary.json")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.csv:
        result = _placeholder_result()
    elif args.answer_key:
        result = process_2afc_identification(
            ROOT / args.csv,
            ROOT / args.answer_key,
            ROOT / args.output,
        )
    else:
        result = process_likert_distinctiveness(ROOT / args.csv, ROOT / args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
