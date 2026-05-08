"""
Generate a Korean 2AFC human-evaluation survey for PCSP persona identification.

This script is intentionally tied to real model rollouts. For paper results,
provide a rollout JSON exported from the evaluated policy, preferably on held-out
zero-shot personas. Synthetic traces are useful only for pilot UI testing and are
not accepted by this generator.

Expected rollout JSON:
{
  "rollouts": [
    {
      "model": "PCSP-full",
      "trajectory_id": "pcsp_full_p241_ep000",
      "persona_id": 241,
      "split": "test",
      "actions": [
        {"step": 1, "action_id": 3},
        {"step": 2, "action_id": 5}
      ]
    }
  ]
}

Usage:
    conda run -n paper python scripts/generate_persona_identification_survey_ko.py \
        --rollouts results/human_eval/pcsp_zero_shot_rollouts.json \
        --personas data/personas/test_60.json \
        --output_dir data/human_eval
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.action_semantics import action_label_ko, describe_action_ko
from src.env.mini_inzoi import WORLD_OBJECTS

STUDY_TITLE = "NPC 페르소나 식별 평가"
INSTRUCTION = (
    "아래에는 한 NPC의 실제 행동 기록과 두 개의 후보 페르소나가 제시됩니다. "
    "행동의 시간, 장소, 주변 상황을 함께 보고 어느 후보 페르소나에 더 가까운 NPC인지 선택해 주세요. "
    "정답을 맞히는 과제이므로, 두 후보 중 더 그럴듯한 쪽을 골라 주세요."
)
QUESTION = "이 행동 기록은 어느 후보 페르소나의 NPC에 더 가까워 보이나요?"

BIG_FIVE_LEVEL = {"low": 0, "mid": 1, "high": 2}
TRAIT_ORDER = ["E", "N", "A", "C", "O"]


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _persona_by_id(personas: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in personas}


def _persona_label(persona: dict[str, Any]) -> str:
    occupation = str(persona.get("occupation", "")).strip()
    age = persona.get("age")
    prefix = ""
    if age and occupation:
        prefix = f"{age}세 {occupation}. "
    elif occupation:
        prefix = f"{occupation}. "
    return prefix + str(persona["text"]).strip()


def _trait_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    bf_a = a.get("big_five", {})
    bf_b = b.get("big_five", {})
    total = 0.0
    for trait in TRAIT_ORDER:
        va = BIG_FIVE_LEVEL.get(str(bf_a.get(trait, "mid")), 1)
        vb = BIG_FIVE_LEVEL.get(str(bf_b.get(trait, "mid")), 1)
        total += abs(va - vb) / 2.0
    return total / len(TRAIT_ORDER)


def _preferred_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    pa = {int(x) for x in a.get("preferred_actions", []) if 0 <= int(x) <= 7}
    pb = {int(x) for x in b.get("preferred_actions", []) if 0 <= int(x) <= 7}
    return len(pa.symmetric_difference(pb)) / 8.0


def _distractor_score(target: dict[str, Any], candidate: dict[str, Any]) -> float:
    same_occupation_penalty = 0.15 if target.get("occupation") == candidate.get("occupation") else 0.0
    return 0.60 * _trait_distance(target, candidate) + 0.40 * _preferred_distance(target, candidate) - same_occupation_penalty


def _select_distractor(
    target: dict[str, Any],
    personas: list[dict[str, Any]],
    rng: random.Random,
    top_k: int,
) -> tuple[dict[str, Any], float]:
    scored = [
        (_distractor_score(target, p), p)
        for p in personas
        if int(p["id"]) != int(target["id"])
    ]
    if not scored:
        raise ValueError("Need at least two personas to create a 2AFC item.")
    scored.sort(key=lambda x: x[0], reverse=True)
    score, distractor = rng.choice(scored[: max(1, min(top_k, len(scored)))])
    return distractor, round(float(score), 4)


def _normalise_rollouts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rollouts = payload
    elif isinstance(payload, dict) and isinstance(payload.get("rollouts"), list):
        rollouts = payload["rollouts"]
    else:
        raise ValueError("Rollout JSON must be a list or an object with a 'rollouts' list.")

    clean = []
    for idx, row in enumerate(rollouts):
        if "persona_id" not in row:
            raise ValueError(f"rollouts[{idx}] is missing persona_id.")
        if "actions" not in row and "action_ids" not in row:
            raise ValueError(f"rollouts[{idx}] must include actions or action_ids.")
        clean.append(dict(row))
    return clean


def _action_id_from_step(step: Any) -> int:
    if isinstance(step, dict):
        return int(step["action_id"])
    return int(step)


def _trace_text(
    rollout: dict[str, Any],
    display_trace_len: int,
    include_movement: bool,
    coarse_mode: bool = False,
) -> str:
    raw_actions = rollout.get("actions", rollout.get("action_ids", []))
    rows: list[str] = []
    for step in raw_actions:
        action_id = _action_id_from_step(step)
        if not include_movement and action_id >= 8:
            continue
        if coarse_mode or not isinstance(step, dict):
            rows.append(action_label_ko(action_id))
        else:
            rows.append(describe_action_ko(step, WORLD_OBJECTS))
        if len(rows) >= display_trace_len:
            break
    if not rows:
        raise ValueError(f"Rollout {rollout.get('trajectory_id', '<unknown>')} has no displayable actions.")
    return "\n".join(rows)


def _make_display_text(item: dict[str, Any]) -> str:
    return (
        f"[{item['item_id']}]\n\n"
        f"행동 기록\n{item['trace_text']}\n\n"
        f"후보 A\n{item['candidate_a_text']}\n\n"
        f"후보 B\n{item['candidate_b_text']}\n\n"
        f"질문: {QUESTION}\n"
        f"응답: A / B\n"
        f"확신도: 1 / 2 / 3 / 4 / 5"
    )


def generate_survey(
    rollouts_path: Path,
    personas_path: Path,
    output_dir: Path,
    output_stem: str,
    n_items: int,
    display_trace_len: int,
    include_movement: bool,
    seed: int,
    distractor_top_k: int,
    coarse_mode: bool = False,
) -> dict[str, Any]:
    rollouts_payload = _load_json(rollouts_path)
    rollouts = _normalise_rollouts(rollouts_payload)
    personas_list = _load_json(personas_path)
    personas = _persona_by_id(personas_list)
    rng = random.Random(seed)

    eligible = [r for r in rollouts if int(r["persona_id"]) in personas]
    if not eligible:
        raise ValueError("No rollouts match persona ids in the selected personas file.")
    rng.shuffle(eligible)
    selected = eligible[: min(n_items, len(eligible))]

    items: list[dict[str, Any]] = []
    for idx, rollout in enumerate(selected):
        target = personas[int(rollout["persona_id"])]
        distractor, distractor_score = _select_distractor(target, personas_list, rng, distractor_top_k)

        correct_option = "A"
        candidate_a = target
        candidate_b = distractor
        if rng.random() < 0.5:
            correct_option = "B"
            candidate_a = distractor
            candidate_b = target

        item = {
            "item_id": f"item_{idx:03d}",
            "trajectory_id": rollout.get("trajectory_id", f"rollout_{idx:03d}"),
            "model": rollout.get("model", "unknown"),
            "split": rollout.get("split", "unknown"),
            "target_persona_id": int(target["id"]),
            "distractor_persona_id": int(distractor["id"]),
            "distractor_score": distractor_score,
            "candidate_a_id": int(candidate_a["id"]),
            "candidate_b_id": int(candidate_b["id"]),
            "correct_option": correct_option,
            "question": QUESTION,
            "trace_text": _trace_text(rollout, display_trace_len, include_movement, coarse_mode),
            "candidate_a_text": _persona_label(candidate_a),
            "candidate_b_text": _persona_label(candidate_b),
        }
        item["display_text"] = _make_display_text(item)
        items.append(item)

    payload = {
        "study_title": STUDY_TITLE,
        "language": "ko",
        "task_type": "human_two_alternative_forced_choice_persona_identification",
        "source_rollouts": str(rollouts_path),
        "source_personas": str(personas_path),
        "n_items": len(items),
        "display_trace_len": display_trace_len,
        "include_movement": include_movement,
        "coarse_mode": coarse_mode,
        "participant_instruction": INSTRUCTION,
        "question": QUESTION,
        "response_columns": ["participant_id", "item_id", "response", "confidence", "response_time_sec"],
        "chance_level": 0.5,
        "analysis": "Report human top-1 accuracy against correct_option with Wilson 95% CI; aggregate by model and split.",
        "items": items,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_stem}.json"
    csv_path = output_dir / f"{output_stem}.csv"
    md_path = output_dir / f"{output_stem}.md"
    answer_key_path = output_dir / f"{output_stem}_answer_key.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_id", "trajectory_id", "model", "split",
                "target_persona_id", "distractor_persona_id", "distractor_score",
                "candidate_a_id", "candidate_b_id", "correct_option",
                "trace_text", "candidate_a_text", "candidate_b_text", "display_text",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for item in items:
            writer.writerow(item)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {STUDY_TITLE}\n\n")
        f.write(INSTRUCTION + "\n\n")
        f.write("각 문항에서 후보 A 또는 후보 B를 고르고, 확신도를 1~5로 표시합니다.\n\n")
        for item in items:
            f.write(f"## {item['item_id']}\n\n")
            f.write("```text\n")
            f.write(item["display_text"])
            f.write("\n```\n\n")

    with open(answer_key_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_id", "trajectory_id", "model", "split",
                "target_persona_id", "correct_option",
            ],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({
                "item_id": item["item_id"],
                "trajectory_id": item["trajectory_id"],
                "model": item["model"],
                "split": item["split"],
                "target_persona_id": item["target_persona_id"],
                "correct_option": item["correct_option"],
            })

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
        "answer_key": str(answer_key_path),
        "n_items": len(items),
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--rollouts", required=True, help="JSON containing real model rollouts.")
    p.add_argument("--personas", default="data/personas/test_60.json")
    p.add_argument("--output_dir", default="data/human_eval")
    p.add_argument("--output_stem", default="persona_identification_survey_ko")
    p.add_argument("--n_items", type=int, default=30)
    p.add_argument("--display_trace_len", type=int, default=12)
    p.add_argument("--include_movement", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--distractor_top_k", type=int, default=12)
    p.add_argument(
        "--coarse_mode",
        action="store_true",
        help="Render bare action labels only (no time/place/style/social context). "
        "Used for the rich-vs-coarse observability ablation.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    result = generate_survey(
        rollouts_path=ROOT / args.rollouts,
        personas_path=ROOT / args.personas,
        output_dir=ROOT / args.output_dir,
        output_stem=args.output_stem,
        n_items=args.n_items,
        display_trace_len=args.display_trace_len,
        include_movement=args.include_movement,
        seed=args.seed,
        distractor_top_k=args.distractor_top_k,
        coarse_mode=args.coarse_mode,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
