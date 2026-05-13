"""
Persona → PersonaConfig via Claude API (Phase 2-2)

Given a natural language persona description, extracts:
  - decay_modifiers: list[float] (8 values, 0.5~2.0 multipliers on BASE_DECAY)
  - preferred_actions: list[int] (2-3 action indices)
  - age: int (inferred if not given)

Used at:
  - Dataset construction time (batch over 300 personas)
  - Inference time for new NPC personas (single call, ~100ms)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# load .env from research root if present
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))

NEED_NAMES = ["hunger", "sleep", "social", "leisure", "hygiene", "fitness", "work", "learning"]
ACTION_NAMES = [
    "work", "eat", "sleep", "socialize", "exercise", "read",
    "clean", "rest", "move_up", "move_down", "move_left", "move_right",
]
# Only task actions (0-7) can be preferred; movement actions are excluded
TASK_ACTIONS = list(range(8))

_SYSTEM_PROMPT = """\
당신은 게임 NPC AI 시스템의 일부입니다.
주어진 NPC 성격 설명(한국어 또는 영어)을 읽고, 아래 JSON 형식으로만 응답하세요.
다른 설명이나 주석은 절대 포함하지 마세요.

필드 설명:
- decay_modifiers: 8개 needs(hunger, sleep, social, leisure, hygiene, fitness, work, learning)의
  감소 속도 배수. 기본값=1.0. 범위: 0.3(매우 느림) ~ 2.5(매우 빠름).
  - 사교적 성격 → social 높게, 내성적 → social 낮게
  - 부지런한 성격 → work 높게
  - 건강 집착 → fitness/hygiene 높게
  - 지식욕 강함 → learning 높게
  - 느긋한 성격 → leisure 낮게
- preferred_actions: 이 NPC가 선호하는 행동 2-3개의 인덱스 (0-7만 허용)
  행동 목록: 0=work, 1=eat, 2=sleep, 3=socialize, 4=exercise, 5=read, 6=clean, 7=rest
- age: 나이 추정값 (정수, 18-70)

응답 예시:
{"decay_modifiers": [1.0, 0.8, 1.5, 0.9, 1.0, 1.2, 0.8, 1.3], "preferred_actions": [3, 0], "age": 25}
"""

_USER_TEMPLATE = "NPC 성격 설명: {text}"


def extract_config(
    text: str,
    client: anthropic.Anthropic | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Extract numeric config from a natural language persona text.

    Returns dict with keys: decay_modifiers, preferred_actions, age
    """
    if client is None:
        client = anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=200,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _USER_TEMPLATE.format(text=text)}],
    )

    raw = message.content[0].text.strip()

    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    result = json.loads(raw)

    # Validate and clamp
    dm = result.get("decay_modifiers", [1.0] * 8)
    if len(dm) != 8:
        dm = (dm + [1.0] * 8)[:8]
    dm = [max(0.3, min(2.5, float(v))) for v in dm]

    pa = result.get("preferred_actions", [0, 3])
    pa = [int(a) for a in pa if 0 <= int(a) <= 7][:3]
    if not pa:
        pa = [0]

    age = int(result.get("age", 30))
    age = max(18, min(70, age))

    return {"decay_modifiers": dm, "preferred_actions": pa, "age": age}


def batch_extract(
    texts: list[str],
    client: anthropic.Anthropic | None = None,
    model: str = "claude-haiku-4-5-20251001",
    verbose: bool = True,
) -> list[dict]:
    """Extract configs for multiple persona texts sequentially."""
    if client is None:
        client = anthropic.Anthropic()

    results = []
    for i, text in enumerate(texts):
        cfg = extract_config(text, client=client, model=model)
        results.append(cfg)
        if verbose and (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(texts)}] processed")
    return results


if __name__ == "__main__":
    sample = "외향적이고 새로운 경험을 즐기는 25세 마케터. 사람들과 어울리기 좋아하고 운동도 자주 한다."
    cfg = extract_config(sample)
    print("Input:", sample)
    print("Output:", json.dumps(cfg, indent=2, ensure_ascii=False))
