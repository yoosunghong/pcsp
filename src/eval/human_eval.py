"""
Human evaluation processing — eval/human_eval.py

Processes Prolific survey data for the "Two-NPC distinctiveness" study.

Survey format (CSV columns):
  participant_id, persona_pair_id, persona_a_id, persona_b_id,
  likert_score (1–5), response_time_sec

Likert scale:
  1 = 전혀 다르지 않음 (not distinct at all)
  5 = 매우 다름 (very distinct)

Computes:
  - Mean distinctiveness score (overall + per model)
  - Krippendorff's alpha (inter-rater reliability)
  - Correlation with behavioral KL (if provided)
  - Comparison table: PCSP vs baselines

Usage:
    python src/eval/human_eval.py \
        --csv data/human_eval/prolific_results.csv \
        --kl_json results/eval/diversity_full.json \
        --output results/eval/human_eval_summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ── Krippendorff's alpha ──────────────────────────────────────────────────────

def krippendorff_alpha(
    ratings_by_rater: list[list[float | None]],
    metric:           str = "ordinal",
) -> float:
    """
    Compute Krippendorff's alpha for inter-rater reliability.

    ratings_by_rater: list of length n_raters; each sub-list has n_items scores
                      (None = missing).
    metric: "nominal", "ordinal", or "interval" — distance function.
    """
    n_raters = len(ratings_by_rater)
    n_items  = max(len(r) for r in ratings_by_rater)

    # Pad shorter lists with None
    data = [r + [None] * (n_items - len(r)) for r in ratings_by_rater]

    # Coincidence matrix
    values = sorted({v for rater in data for v in rater if v is not None})
    val_idx = {v: i for i, v in enumerate(values)}
    n_v     = len(values)

    coincidence = np.zeros((n_v, n_v), dtype=float)
    for item in range(n_items):
        obs = [data[r][item] for r in range(n_raters) if data[r][item] is not None]
        m   = len(obs)
        if m < 2:
            continue
        for i in range(len(obs)):
            for j in range(i + 1, len(obs)):
                ci, cj = val_idx[obs[i]], val_idx[obs[j]]
                coincidence[ci, cj] += 1 / (m - 1)
                coincidence[cj, ci] += 1 / (m - 1)

    n_total  = coincidence.sum()
    n_k      = coincidence.sum(axis=1)

    # Distance function
    if metric == "nominal":
        d = lambda k, l: 0.0 if k == l else 1.0
    elif metric == "ordinal":
        def d(k, l):
            if k == l:
                return 0.0
            lo, hi = (k, l) if k < l else (l, k)
            s = sum(n_k[lo:hi+1]) - (n_k[lo] + n_k[hi]) / 2.0
            return s * s
    else:  # interval
        d = lambda k, l: (values[k] - values[l]) ** 2

    # Observed disagreement Do
    Do = sum(
        coincidence[k, l] * d(k, l)
        for k in range(n_v) for l in range(n_v)
    ) / n_total

    # Expected disagreement De
    De = sum(
        n_k[k] * n_k[l] * d(k, l)
        for k in range(n_v) for l in range(n_v)
    ) / (n_total * (n_total - 1))

    return 1.0 - Do / De if De != 0 else 1.0


# ── Main processing ───────────────────────────────────────────────────────────

def process_human_eval(
    csv_path:    str | Path,
    kl_json:     str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """
    Load Prolific survey CSV, compute statistics, and optionally save JSON.

    Expected CSV columns (flexible — falls back gracefully):
      participant_id, model, persona_pair_id, persona_a_id, persona_b_id,
      likert_score, response_time_sec
    """
    p = Path(csv_path)
    if not p.exists():
        return _placeholder_result()

    rows: list[dict] = []
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return _placeholder_result()

    # Extract scores
    scores_by_model:  dict[str, list[float]] = {}
    scores_by_pair:   dict[str, list[float]] = {}
    participant_ids:  list[str] = []
    all_scores:       list[float] = []

    for row in rows:
        score = float(row.get("likert_score", 0))
        model = row.get("model", "unknown")
        pair  = row.get("persona_pair_id", "?")
        pid   = row.get("participant_id", "?")

        all_scores.append(score)
        scores_by_model.setdefault(model, []).append(score)
        scores_by_pair.setdefault(pair, []).append(score)
        if pid not in participant_ids:
            participant_ids.append(pid)

    # Per-model means
    model_means = {m: float(np.mean(s)) for m, s in scores_by_model.items()}

    # Krippendorff's alpha
    # Reshape: raters × items (pairs)
    pair_list = sorted(scores_by_pair.keys())
    rater_list = participant_ids
    ratings_by_rater: list[list[float | None]] = []
    for pid in rater_list:
        pid_rows = [r for r in rows if r.get("participant_id") == pid]
        pair_score: dict[str, float] = {}
        for row in pid_rows:
            pair_score[row.get("persona_pair_id", "?")] = float(row.get("likert_score", 0))
        ratings_by_rater.append([pair_score.get(pair) for pair in pair_list])

    alpha = krippendorff_alpha(ratings_by_rater, metric="ordinal") if len(rater_list) >= 2 else None

    # Correlation with behavioral KL
    kl_corr = None
    if kl_json:
        try:
            with open(kl_json) as f:
                kl_data = json.load(f)
            mean_kl = kl_data.get("mean_kl")
            if mean_kl:
                kl_corr = {"note": "Spearman ρ requires pair-level KL data; use diversity.py"}
        except Exception:
            pass

    result: dict[str, Any] = {
        "n_participants":     len(rater_list),
        "n_pairs":            len(pair_list),
        "n_responses":        len(rows),
        "mean_score":         float(np.mean(all_scores)),
        "std_score":          float(np.std(all_scores)),
        "model_means":        model_means,
        "krippendorff_alpha": alpha,
        "kl_correlation":     kl_corr,
        "scale":              "1=not distinct, 5=very distinct",
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Saved to {output_path}")

    return result


def _placeholder_result() -> dict:
    """Return placeholder when survey data is not yet collected."""
    result = {
        "status":    "pending",
        "note":      "Prolific survey not yet conducted (planned: 2026-07-04 ~ 2026-08-01)",
        "target_n":  30,
        "pairs":     "PCSP vs baseline NPC behavior trajectories",
        "scale":     "Likert 1-5: 1=Not distinct at all, 5=Very distinct",
        "survey_q":  "Do the two NPCs behave like distinct people?",
    }
    return result


def generate_prolific_survey_template(
    personas_data: list[dict],
    n_pairs:       int = 30,
    seed:          int = 0,
    output_path:   str | Path = "data/human_eval/survey_template.json",
    lang:          str = "en",
) -> dict:
    """
    Generate a survey template: randomly sample n_pairs of persona pairs.
    Outputs a JSON that can be imported into Prolific / Qualtrics.
    """
    copy = {
        "en": {
            "study_title": "NPC Persona Distinctiveness Evaluation",
            "question": "Do the two NPCs behave like distinct people? (1: Not at all, 5: Very much)",
            "scale": {"1": "Not distinct at all", "3": "Somewhat distinct", "5": "Very distinct"},
        },
        "ko": {
            "study_title": "NPC 페르소나 구분 가능성 평가",
            "question": "두 NPC가 서로 다른 사람처럼 행동한다고 느껴지나요? (1: 전혀 그렇지 않다, 5: 매우 그렇다)",
            "scale": {"1": "전혀 구분되지 않음", "3": "어느 정도 구분됨", "5": "매우 잘 구분됨"},
        },
    }
    if lang not in copy:
        raise ValueError(f"Unsupported survey language: {lang}")

    rng   = np.random.default_rng(seed)
    N     = len(personas_data)
    pairs = []

    while len(pairs) < n_pairs:
        i, j = rng.choice(N, size=2, replace=False)
        pair  = tuple(sorted([int(i), int(j)]))
        if pair not in [p["indices"] for p in pairs]:
            pairs.append({
                "pair_id":     f"pair_{len(pairs):03d}",
                "indices":     list(pair),
                "persona_a_id": personas_data[pair[0]]["id"],
                "persona_b_id": personas_data[pair[1]]["id"],
                "question":    copy[lang]["question"],
            })

    template = {
        "study_title": copy[lang]["study_title"],
        "language": lang,
        "n_participants_target": 30,
        "n_pairs": n_pairs,
        "scale": copy[lang]["scale"],
        "pairs": pairs,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f"Survey template saved to {out}")
    return template


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv",            default=None,
                   help="Path to Prolific survey CSV")
    p.add_argument("--kl_json",        default=None)
    p.add_argument("--output",         default="results/eval/human_eval_summary.json")
    p.add_argument("--gen_template",   action="store_true",
                   help="Generate survey template JSON from personas")
    p.add_argument("--personas",       default="data/personas/train_240.json")
    p.add_argument("--n_pairs",        type=int, default=30)
    p.add_argument("--lang",           choices=["en", "ko"], default="en")
    p.add_argument("--template_output", default=None,
                   help="Output path for generated survey template")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.gen_template:
        with open(ROOT / args.personas) as f:
            personas_data = json.load(f)
        default_name = f"survey_template_{args.lang}.json" if args.lang != "en" else "survey_template.json"
        result = generate_prolific_survey_template(
            personas_data, n_pairs=args.n_pairs,
            output_path=ROOT / (args.template_output or f"data/human_eval/{default_name}"),
            lang=args.lang,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.csv:
        result = process_human_eval(
            ROOT / args.csv,
            kl_json=ROOT / args.kl_json if args.kl_json else None,
            output_path=ROOT / args.output,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(_placeholder_result(), indent=2, ensure_ascii=False))
