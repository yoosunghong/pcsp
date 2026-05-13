"""
Analyze aggregate Google Forms A/B ratios for the coarse Korean 2AFC survey.

The form result was recorded as item-level A:B selection ratios from a
30-person Google Forms multiple-choice study, not participant-level rows. This
script scales each ratio to the item participant count and reports pooled
forced-choice accuracy and item difficulty, but intentionally leaves confidence,
response-time, participant variance, and inter-rater reliability unavailable.

Usage:
  conda run -n paper python scripts/analyze_coarse_google_forms_pilot.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


def classify_item(correct: int, n: int) -> str:
    if n == 0:
        return "missing"
    rate = correct / n
    if rate >= 0.8:
        return "strongly_readable"
    if rate >= 0.7:
        return "moderately_readable"
    if rate >= 0.4:
        return "ambiguous"
    return "misleading"


def _scaled_counts(row: dict[str, str]) -> tuple[int, int, int]:
    a_ratio = int(row["a_ratio"])
    b_ratio = int(row["b_ratio"])
    n_participants = int(row["n_participants"])
    ratio_total = a_ratio + b_ratio
    if ratio_total <= 0:
        raise ValueError(f"Invalid ratio total for {row['item_id']}")
    scale = n_participants / ratio_total
    a_count = round(a_ratio * scale)
    b_count = n_participants - a_count
    return a_count, b_count, n_participants


def analyze(counts_path: Path, answer_key_path: Path, output_json: Path, output_csv: Path) -> dict[str, Any]:
    counts_rows = read_csv(counts_path)
    key_rows = read_csv(answer_key_path)
    answer_key = {row["item_id"]: row["correct_option"].strip().upper() for row in key_rows}

    item_rows: list[dict[str, Any]] = []
    total_correct = 0
    total_responses = 0

    for row in counts_rows:
        item_id = row["item_id"]
        a_count, b_count, n_participants = _scaled_counts(row)
        correct_option = answer_key[item_id]
        correct_count = a_count if correct_option == "A" else b_count
        n = a_count + b_count
        lo, hi = wilson_ci(correct_count, n)
        total_correct += correct_count
        total_responses += n
        item_rows.append({
            "item_id": item_id,
            "correct_option": correct_option,
            "a_ratio": int(row["a_ratio"]),
            "b_ratio": int(row["b_ratio"]),
            "n_participants": n_participants,
            "a_count": a_count,
            "b_count": b_count,
            "n": n,
            "correct_count": correct_count,
            "accuracy": correct_count / n if n else 0.0,
            "wilson_ci_95_low": lo,
            "wilson_ci_95_high": hi,
            "difficulty_bucket": classify_item(correct_count, n),
        })

    overall_lo, overall_hi = wilson_ci(total_correct, total_responses)
    bucket_counts: dict[str, int] = {}
    for item in item_rows:
        bucket = item["difficulty_bucket"]
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    n_items = len(item_rows)
    participant_counts = sorted({row["n"] for row in item_rows})
    result = {
        "study_type": "aggregate_2afc_persona_identification",
        "condition": "coarse",
        "source": "Google Forms multiple-choice survey",
        "counts_path": str(counts_path),
        "answer_key_path": str(answer_key_path),
        "n_items": n_items,
        "n_participants_per_item": participant_counts,
        "n_responses": total_responses,
        "correct": total_correct,
        "chance_level": 0.5,
        "accuracy": total_correct / total_responses if total_responses else 0.0,
        "wilson_ci_95": [overall_lo, overall_hi],
        "item_difficulty_counts": bucket_counts,
        "unavailable_metrics": [
            "participant-level variance",
            "confidence",
            "response time",
            "inter-rater reliability",
            "order effects",
        ],
        "notes": (
            "Only item-level A/B selection ratios were retained from Google Forms. "
            "Ratios are scaled to 30 selections per item. The pooled CI treats the "
            "900 selections as aggregate Bernoulli judgments; "
            "participant-level analyses are not available."
        ),
        "items": item_rows,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(item_rows[0].keys()))
        writer.writeheader()
        writer.writerows(item_rows)

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", default="results/human_eval/coarse_google_forms_counts.csv")
    parser.add_argument(
        "--answer_key",
        default="data/human_eval/persona_identification_survey_ko_coarse_answer_key.csv",
    )
    parser.add_argument("--output_json", default="results/human_eval/coarse_google_forms_summary.json")
    parser.add_argument("--output_csv", default="results/human_eval/coarse_google_forms_scored_items.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze(
        ROOT / args.counts,
        ROOT / args.answer_key,
        ROOT / args.output_json,
        ROOT / args.output_csv,
    )
    lo, hi = result["wilson_ci_95"]
    print(
        f"Coarse Google Forms pilot: {result['correct']}/{result['n_responses']} "
        f"= {result['accuracy']:.3f}, Wilson 95% CI [{lo:.3f}, {hi:.3f}]"
    )


if __name__ == "__main__":
    main()
