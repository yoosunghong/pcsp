"""Display-only Korean action semantics for rollout and survey rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ActionSemantics:
    intent: str
    default_place: str
    variants_ko: tuple[str, ...]


V1_ACTION_SEMANTICS: dict[int, ActionSemantics] = {
    0: ActionSemantics("work", "desk", ("집중해서 업무 처리", "꼼꼼하게 할 일 점검", "업무 계획 정리")),
    1: ActionSemantics("eat", "kitchen", ("간단히 식사", "천천히 식사", "허기를 달래기")),
    2: ActionSemantics("sleep", "bed", ("잠자기", "충분히 수면", "잠시 눈을 붙이기")),
    3: ActionSemantics("social", "sofa", ("먼저 말을 걸어 대화", "가볍게 안부 묻기", "함께 이야기 나누기")),
    4: ActionSemantics("fitness", "gym", ("운동하기", "몸을 활발히 움직이기", "가볍게 스트레칭")),
    5: ActionSemantics("learning", "library", ("집중해서 책 읽기", "관심 분야 살펴보기", "조용히 독서")),
    6: ActionSemantics("hygiene", "bathroom", ("주변 정리와 청소", "깔끔하게 정돈", "위생 관리")),
    7: ActionSemantics("leisure", "sofa", ("혼자 편히 쉬기", "느긋하게 휴식", "잠시 여유 보내기")),
    8: ActionSemantics("move", "", ("위쪽으로 이동",)),
    9: ActionSemantics("move", "", ("아래쪽으로 이동",)),
    10: ActionSemantics("move", "", ("왼쪽으로 이동",)),
    11: ActionSemantics("move", "", ("오른쪽으로 이동",)),
}

V3_ACTION_SEMANTICS: dict[int, ActionSemantics] = {
    0: ActionSemantics("work", "desk", ("깊이 집중해 업무 처리", "방해 없이 몰입해 일하기")),
    1: ActionSemantics("work", "desk", ("차분하게 업무 계획 세우기", "할 일을 구조적으로 정리")),
    2: ActionSemantics("self_care", "kitchen", ("빠르게 끼니 해결", "간단한 음식으로 허기 달래기")),
    3: ActionSemantics("self_care", "kitchen", ("천천히 식사를 음미", "여유 있게 식사")),
    4: ActionSemantics("self_care", "bed", ("충분히 잠자기", "푹 자며 회복")),
    5: ActionSemantics("self_care", "bed", ("잠깐 낮잠 자기", "짧게 눈을 붙이기")),
    6: ActionSemantics("social", "sofa", ("먼저 말을 걸어 대화", "적극적으로 대화 시작")),
    7: ActionSemantics("social", "sofa", ("상대의 말에 다정하게 응답", "대화에 맞장구치기")),
    8: ActionSemantics("fitness", "gym", ("강도 높게 운동", "힘차게 체력 훈련")),
    9: ActionSemantics("fitness", "gym", ("가볍게 운동", "부담 없이 스트레칭")),
    10: ActionSemantics("learning", "library", ("깊이 집중해 공부", "어려운 책을 꼼꼼히 읽기")),
    11: ActionSemantics("leisure", "library", ("가볍게 책 읽기", "편안하게 독서")),
    12: ActionSemantics("self_care", "bathroom", ("주변을 깔끔하게 청소", "차분히 정리 정돈")),
    13: ActionSemantics("leisure", "sofa", ("혼자 조용히 휴식", "사람들과 떨어져 쉬기")),
    14: ActionSemantics("social", "sofa", ("다른 사람들과 함께 휴식", "여럿이 편하게 시간 보내기")),
    15: ActionSemantics("leisure", "park", ("새로운 곳을 탐색", "주변을 호기심 있게 둘러보기")),
    16: ActionSemantics("move", "", ("위쪽으로 이동",)),
    17: ActionSemantics("move", "", ("아래쪽으로 이동",)),
    18: ActionSemantics("move", "", ("왼쪽으로 이동",)),
    19: ActionSemantics("move", "", ("오른쪽으로 이동",)),
}


def nearest_place_name(position: Sequence[int | float], world_objects: Mapping[str, Sequence[int | float]]) -> str:
    row, col = float(position[0]), float(position[1])
    return min(
        world_objects,
        key=lambda name: abs(row - float(world_objects[name][0])) + abs(col - float(world_objects[name][1])),
    )


def action_label_ko(action_id: int) -> str:
    sem = V1_ACTION_SEMANTICS.get(int(action_id))
    return sem.variants_ko[0] if sem else f"행동 {action_id}"


def v3_action_label_ko(action_id: int) -> str:
    sem = V3_ACTION_SEMANTICS.get(int(action_id))
    return sem.variants_ko[0] if sem else f"행동 {action_id}"


def _describe(step: dict, world_objects, semantics: dict[int, ActionSemantics]) -> str:
    action_id = int(step.get("action_id", -1))
    sem = semantics.get(action_id)
    if sem is None:
        phrase = f"행동 {action_id}"
    else:
        variant_idx = max(0, int(step.get("step", 1)) - 1) % len(sem.variants_ko)
        phrase = sem.variants_ko[variant_idx]
    hour = int(step.get("time_of_day", 0))
    position = step.get("position", (0, 0))
    place = str(step.get("place") or nearest_place_name(position, world_objects))
    return f"{hour:02d}:00 {place}에서 {phrase}"


def describe_action_ko(step: dict, world_objects) -> str:
    return _describe(step, world_objects, V1_ACTION_SEMANTICS)


def describe_v3_action_ko(step: dict, world_objects) -> str:
    return _describe(step, world_objects, V3_ACTION_SEMANTICS)


__all__ = [
    "ActionSemantics", "V1_ACTION_SEMANTICS", "V3_ACTION_SEMANTICS",
    "action_label_ko", "v3_action_label_ko", "describe_action_ko",
    "describe_v3_action_ko", "nearest_place_name",
]
