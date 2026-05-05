"""
Generate a Korean 2AFC persona-identification survey.

Each item shows one compact behavior trace and two persona candidates. The
participant chooses which persona better matches the behavior. This evaluates
whether persona-conditioned behavior is identifiable from action patterns.

Usage:
    conda run -n paper python scripts/generate_persona_identification_survey_ko.py
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_human_eval_stimuli import (  # noqa: E402
    MOVE_ACTIONS,
    _generate_trace,
)

STUDY_TITLE = "NPC 페르소나 식별 평가"
INSTRUCTION = (
    "아래 행동 기록은 한 NPC의 짧은 행동 패턴입니다. "
    "두 후보 중 이 행동 기록과 더 잘 어울리는 페르소나를 선택해 주세요."
)
QUESTION = "이 행동 기록은 어느 페르소나의 NPC에 더 가까워 보이나요?"
BIG_FIVE_LEVEL = {"low": 0, "mid": 1, "high": 2}


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _persona_by_id(personas: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in personas}


def _persona_label(persona: dict[str, Any]) -> str:
    occupation = persona.get("occupation")
    age = persona.get("age")
    prefix = ""
    if occupation and age:
        prefix = f"{age}세 {occupation}. "
    elif occupation:
        prefix = f"{occupation}. "
    return prefix + str(persona["text"])


def _preferred_actions(persona: dict[str, Any]) -> set[int]:
    return {int(a) for a in persona.get("preferred_actions", []) if 0 <= int(a) <= 7}


def _contrast_score(persona_a: dict[str, Any], persona_b: dict[str, Any]) -> float:
    pref_a = _preferred_actions(persona_a)
    pref_b = _preferred_actions(persona_b)
    preferred_distance = len(pref_a.symmetric_difference(pref_b)) / 6.0

    big_five_a = persona_a.get("big_five", {})
    big_five_b = persona_b.get("big_five", {})
    trait_distance = 0.0
    for trait in ["E", "N", "A", "C", "O"]:
        level_a = BIG_FIVE_LEVEL.get(str(big_five_a.get(trait, "mid")), 1)
        level_b = BIG_FIVE_LEVEL.get(str(big_five_b.get(trait, "mid")), 1)
        trait_distance += abs(level_a - level_b) / 2.0
    trait_distance /= 5.0

    occupation_bonus = 0.15 if persona_a.get("occupation") != persona_b.get("occupation") else 0.0
    return preferred_distance * 0.65 + trait_distance * 0.35 + occupation_bonus


def _select_contrasting_distractor(
    target: dict[str, Any],
    personas: list[dict[str, Any]],
    rng: random.Random,
    top_k: int = 20,
) -> tuple[dict[str, Any], float]:
    scored = [
        (_contrast_score(target, candidate), candidate)
        for candidate in personas
        if int(candidate["id"]) != int(target["id"])
    ]
    scored.sort(key=lambda row: row[0], reverse=True)
    score, candidate = rng.choice(scored[:top_k])
    return candidate, score


def _compact_trace_text(trace: list[dict[str, Any]], max_actions: int) -> str:
    rows = [t for t in trace if int(t["action_id"]) not in MOVE_ACTIONS][:max_actions]
    lines = []
    for t in rows:
        suffix = " - 선호 행동" if t.get("is_preferred") else ""
        lines.append(f"{t['action']}{suffix}")
    return "\n".join(lines)


def _make_display_text(item: dict[str, Any]) -> str:
    return (
        f"[{item['item_id']}]\n\n"
        f"행동 기록\n{item['trace_text']}\n\n"
        f"후보 A\n{item['candidate_a_text']}\n\n"
        f"후보 B\n{item['candidate_b_text']}\n\n"
        f"질문: {QUESTION}\n"
        f"응답: A / B"
    )


def generate_survey(
    template_path: Path,
    personas_path: Path,
    output_dir: Path,
    trace_len: int = 16,
    display_trace_len: int = 8,
    seed: int = 42,
) -> dict[str, Any]:
    template = _load_json(template_path)
    persona_list = _load_json(personas_path)
    personas = _persona_by_id(persona_list)
    rng = random.Random(seed)

    items: list[dict[str, Any]] = []
    for idx, pair in enumerate(template["pairs"]):
        persona_a = personas[int(pair["persona_a_id"])]
        persona_b = personas[int(pair["persona_b_id"])]

        target_is_a = rng.random() < 0.5
        target_persona = persona_a if target_is_a else persona_b
        distractor_persona, contrast_score = _select_contrasting_distractor(
            target_persona,
            persona_list,
            rng,
        )

        trace_seed = rng.randint(0, 2**31 - 1) + idx
        trace = _generate_trace(target_persona, trace_len=trace_len, seed=trace_seed, lang="ko")
        trace_text = _compact_trace_text(trace, display_trace_len)

        correct_option = "A"
        candidate_a = target_persona
        candidate_b = distractor_persona
        if rng.random() < 0.5:
            correct_option = "B"
            candidate_a = distractor_persona
            candidate_b = target_persona

        item = {
            "item_id": f"item_{idx:03d}",
            "source_pair_id": pair["pair_id"],
            "target_persona_id": int(target_persona["id"]),
            "distractor_persona_id": int(distractor_persona["id"]),
            "distractor_contrast_score": round(contrast_score, 4),
            "candidate_a_id": int(candidate_a["id"]),
            "candidate_b_id": int(candidate_b["id"]),
            "correct_option": correct_option,
            "question": QUESTION,
            "trace": trace,
            "trace_text": trace_text,
            "candidate_a_text": _persona_label(candidate_a),
            "candidate_b_text": _persona_label(candidate_b),
        }
        item["display_text"] = _make_display_text(item)
        items.append(item)

    payload = {
        "study_title": STUDY_TITLE,
        "language": "ko",
        "task_type": "two_alternative_forced_choice_persona_identification",
        "n_items": len(items),
        "trace_len": trace_len,
        "display_trace_len": display_trace_len,
        "participant_instruction": INSTRUCTION,
        "question": QUESTION,
        "chance_level": 0.5,
        "items": items,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "persona_identification_survey_ko"

    json_path = output_dir / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    csv_path = output_dir / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "item_id",
                "source_pair_id",
                "target_persona_id",
                "distractor_persona_id",
                "distractor_contrast_score",
                "candidate_a_id",
                "candidate_b_id",
                "correct_option",
                "trace_text",
                "candidate_a_text",
                "candidate_b_text",
                "display_text",
            ],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({
                "item_id": item["item_id"],
                "source_pair_id": item["source_pair_id"],
                "target_persona_id": item["target_persona_id"],
                "distractor_persona_id": item["distractor_persona_id"],
                "distractor_contrast_score": item["distractor_contrast_score"],
                "candidate_a_id": item["candidate_a_id"],
                "candidate_b_id": item["candidate_b_id"],
                "correct_option": item["correct_option"],
                "trace_text": item["trace_text"],
                "candidate_a_text": item["candidate_a_text"],
                "candidate_b_text": item["candidate_b_text"],
                "display_text": item["display_text"],
            })

    md_path = output_dir / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {STUDY_TITLE}\n\n")
        f.write(INSTRUCTION + "\n\n")
        f.write("각 문항은 후보 A 또는 후보 B 중 하나만 선택합니다.\n\n")
        for item in items:
            f.write(f"## {item['item_id']}\n\n")
            f.write("```text\n")
            f.write(item["display_text"])
            f.write("\n```\n\n")

    answer_key_path = output_dir / f"{stem}_answer_key.csv"
    with open(answer_key_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["item_id", "target_persona_id", "correct_option"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({
                "item_id": item["item_id"],
                "target_persona_id": item["target_persona_id"],
                "correct_option": item["correct_option"],
            })

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
        "answer_key": str(answer_key_path),
        "n_items": len(items),
        "display_trace_len": display_trace_len,
    }


def main() -> None:
    result = generate_survey(
        template_path=ROOT / "data/human_eval/survey_template.json",
        personas_path=ROOT / "data/personas/train_240.json",
        output_dir=ROOT / "data/human_eval",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
