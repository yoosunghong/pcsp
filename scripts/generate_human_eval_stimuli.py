"""
Generate human-evaluation stimuli from a survey template.

The generated stimuli show only behavior traces for NPC A/B. Persona text and
Big Five labels are kept out of participant-facing fields to avoid priming.

Usage:
    conda run -n paper python scripts/generate_human_eval_stimuli.py --lang ko
    conda run -n paper python scripts/generate_human_eval_stimuli.py --lang en
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

ACTION_NAMES_EN = [
    "work", "eat", "sleep", "socialize", "exercise", "read",
    "clean", "rest", "move up", "move down", "move left", "move right",
]

ACTION_NAMES_KO = [
    "일하기", "식사하기", "잠자기", "대화하기", "운동하기", "읽기",
    "청소하기", "휴식하기", "위로 이동", "아래로 이동", "왼쪽으로 이동", "오른쪽으로 이동",
]

NEED_NAMES_EN = ["hunger", "sleep", "social", "leisure", "hygiene", "fitness", "work", "learning"]
NEED_NAMES_KO = ["허기", "수면", "사회성", "여가", "위생", "체력", "업무", "학습"]

ACTION_TO_NEED = {
    0: 6,  # work
    1: 0,  # eat
    2: 1,  # sleep
    3: 2,  # socialize
    4: 5,  # exercise
    5: 7,  # read
    6: 4,  # clean
    7: 3,  # rest
}

MOVE_ACTIONS = [8, 9, 10, 11]
TASK_ACTIONS = list(range(8))


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _persona_by_id(personas: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(p["id"]): p for p in personas}


def _weighted_choice(rng: random.Random, weights: list[float]) -> int:
    total = sum(weights)
    point = rng.random() * total
    acc = 0.0
    for idx, weight in enumerate(weights):
        acc += weight
        if point <= acc:
            return idx
    return len(weights) - 1


def _action_label(action: int, lang: str) -> str:
    return (ACTION_NAMES_KO if lang == "ko" else ACTION_NAMES_EN)[action]


def _need_label(need: int, lang: str) -> str:
    return (NEED_NAMES_KO if lang == "ko" else NEED_NAMES_EN)[need]


def _action_reason(action: int, persona: dict[str, Any], lang: str) -> str:
    preferred = set(int(a) for a in persona.get("preferred_actions", []))
    if action in MOVE_ACTIONS:
        return "다음 활동 장소로 이동" if lang == "ko" else "Moves toward the next activity location"

    need_idx = ACTION_TO_NEED[action]
    modifiers = persona.get("decay_modifiers", [1.0] * 8)
    high_need = float(modifiers[need_idx]) >= 1.2
    is_preferred = action in preferred

    if lang == "ko":
        if is_preferred and high_need:
            return f"선호 행동이며 {_need_label(need_idx, lang)} 욕구가 빠르게 변함"
        if is_preferred:
            return "이 NPC가 자주 선택하는 선호 행동"
        if high_need:
            return f"{_need_label(need_idx, lang)} 욕구 관리"
        return "상태 균형 유지"

    if is_preferred and high_need:
        return f"Preferred behavior and fast-changing {_need_label(need_idx, lang)} need"
    if is_preferred:
        return "A preferred behavior for this NPC"
    if high_need:
        return f"Manages the {_need_label(need_idx, lang)} need"
    return "Maintains state balance"


def _generate_trace(
    persona: dict[str, Any],
    trace_len: int,
    seed: int,
    lang: str,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    preferred = set(int(a) for a in persona.get("preferred_actions", []) if 0 <= int(a) <= 7)
    modifiers = [float(v) for v in persona.get("decay_modifiers", [1.0] * 8)]
    if len(modifiers) < 8:
        modifiers = (modifiers + [1.0] * 8)[:8]

    trace: list[dict[str, Any]] = []
    last_action: int | None = None

    for step in range(1, trace_len + 1):
        weights = [0.0] * 12
        for action in TASK_ACTIONS:
            need_idx = ACTION_TO_NEED[action]
            weights[action] = 0.30 + modifiers[need_idx]
            if action in preferred:
                weights[action] += 2.00
            if action == last_action:
                weights[action] *= 0.45

        for action in MOVE_ACTIONS:
            weights[action] = 0.20

        # Insert occasional movement so traces feel like grounded game behavior.
        if step > 1 and step % 4 == 0:
            action = rng.choice(MOVE_ACTIONS)
        else:
            action = _weighted_choice(rng, weights)

        last_action = action
        trace.append({
            "step": step,
            "action_id": action,
            "action": _action_label(action, lang),
            "reason": _action_reason(action, persona, lang),
        })

    return trace


def _trace_text(trace: list[dict[str, Any]], lang: str) -> str:
    if lang == "ko":
        return "\n".join(f"{t['step']:02d}. {t['action']} - {t['reason']}" for t in trace)
    return "\n".join(f"{t['step']:02d}. {t['action']} - {t['reason']}" for t in trace)


def _make_display_block(stimulus: dict[str, Any], lang: str) -> str:
    if lang == "ko":
        return (
            f"[{stimulus['pair_id']}]\n\n"
            f"NPC A 행동 기록\n{stimulus['npc_a_trace_text']}\n\n"
            f"NPC B 행동 기록\n{stimulus['npc_b_trace_text']}\n\n"
            f"질문: {stimulus['question']}"
        )
    return (
        f"[{stimulus['pair_id']}]\n\n"
        f"NPC A behavior trace\n{stimulus['npc_a_trace_text']}\n\n"
        f"NPC B behavior trace\n{stimulus['npc_b_trace_text']}\n\n"
        f"Question: {stimulus['question']}"
    )


def generate_stimuli(
    template_path: Path,
    personas_path: Path,
    output_dir: Path,
    lang: str,
    trace_len: int,
    seed: int,
) -> dict[str, Any]:
    template = _load_json(template_path)
    personas = _persona_by_id(_load_json(personas_path))
    rng = random.Random(seed)

    stimuli: list[dict[str, Any]] = []
    for pair_idx, pair in enumerate(template["pairs"]):
        persona_a = personas[int(pair["persona_a_id"])]
        persona_b = personas[int(pair["persona_b_id"])]

        seed_a = rng.randint(0, 2**31 - 1) + pair_idx * 2
        seed_b = rng.randint(0, 2**31 - 1) + pair_idx * 2 + 1
        trace_a = _generate_trace(persona_a, trace_len=trace_len, seed=seed_a, lang=lang)
        trace_b = _generate_trace(persona_b, trace_len=trace_len, seed=seed_b, lang=lang)

        stimulus = {
            "pair_id": pair["pair_id"],
            "persona_a_id": int(pair["persona_a_id"]),
            "persona_b_id": int(pair["persona_b_id"]),
            "question": pair["question"],
            "scale": template["scale"],
            "npc_a_trace": trace_a,
            "npc_b_trace": trace_b,
            "npc_a_trace_text": _trace_text(trace_a, lang),
            "npc_b_trace_text": _trace_text(trace_b, lang),
        }
        stimulus["display_text"] = _make_display_block(stimulus, lang)
        stimuli.append(stimulus)

    payload = {
        "study_title": template["study_title"],
        "language": lang,
        "n_pairs": len(stimuli),
        "trace_len": trace_len,
        "participant_instruction": (
            "아래의 두 NPC 행동 기록만 보고, 두 NPC가 서로 다른 사람처럼 행동한다고 느껴지는지 평가해 주세요."
            if lang == "ko"
            else "Read only the two NPC behavior traces below and rate whether they feel like distinct people."
        ),
        "scale": template["scale"],
        "stimuli": stimuli,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"survey_stimuli_{lang}"

    json_path = output_dir / f"{stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    csv_path = output_dir / f"{stem}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pair_id", "persona_a_id", "persona_b_id", "question",
                "npc_a_trace", "npc_b_trace", "display_text",
                "scale_1", "scale_3", "scale_5",
            ],
        )
        writer.writeheader()
        for s in stimuli:
            writer.writerow({
                "pair_id": s["pair_id"],
                "persona_a_id": s["persona_a_id"],
                "persona_b_id": s["persona_b_id"],
                "question": s["question"],
                "npc_a_trace": s["npc_a_trace_text"],
                "npc_b_trace": s["npc_b_trace_text"],
                "display_text": s["display_text"],
                "scale_1": template["scale"]["1"],
                "scale_3": template["scale"]["3"],
                "scale_5": template["scale"]["5"],
            })

    md_path = output_dir / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {template['study_title']}\n\n")
        f.write(payload["participant_instruction"] + "\n\n")
        f.write(f"Scale: 1={template['scale']['1']}, 3={template['scale']['3']}, 5={template['scale']['5']}\n\n")
        for s in stimuli:
            f.write(f"## {s['pair_id']}\n\n")
            f.write("```text\n")
            f.write(s["display_text"])
            f.write("\n```\n\n")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
        "n_pairs": len(stimuli),
        "trace_len": trace_len,
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", choices=["en", "ko"], default="ko")
    p.add_argument("--template", default=None)
    p.add_argument("--personas", default="data/personas/train_240.json")
    p.add_argument("--output_dir", default="data/human_eval")
    p.add_argument("--trace_len", type=int, default=12)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    template = args.template
    if template is None:
        template = "data/human_eval/survey_template_ko.json" if args.lang == "ko" else "data/human_eval/survey_template.json"

    result = generate_stimuli(
        template_path=ROOT / template,
        personas_path=ROOT / args.personas,
        output_dir=ROOT / args.output_dir,
        lang=args.lang,
        trace_len=args.trace_len,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
