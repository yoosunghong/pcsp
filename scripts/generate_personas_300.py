"""
Phase 2-1: Persona 300개 생성 (Gemini API 사용)
-----------------------------------------------
15 Big Five archetypes × 20 occupations = 300 personas
  - train split: 240개 (ID 1-240)
  - test split:  60개  (ID 241-300, zero-shot 평가용)

실행 방법:
  export GEMINI_API_KEY=AIza...
  conda run -n paper python scripts/generate_personas_300.py

재실행 시 기존에 생성된 persona는 건너뜀 (체크포인트).
출력: data/personas/personas_300.json, train_240.json, test_60.json
"""
import sys, json, time, pathlib, os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")
load_dotenv(Path(__file__).parent.parent / ".env")

from google import genai
from google.genai import types

# ── Spec matrix ────────────────────────────────────────────────────────────────

# 15 Big Five archetypes covering all major combinations
BIG_FIVE_PROFILES: list[dict] = [
    # Extrovert variants (5)
    {"E": "high", "N": "low",  "A": "mid",  "C": "mid",  "O": "high"},  # 0: 외향+개방
    {"E": "high", "N": "mid",  "A": "low",  "C": "high", "O": "mid"},   # 1: 외향+성실+경쟁
    {"E": "high", "N": "mid",  "A": "high", "C": "mid",  "O": "mid"},   # 2: 외향+친화
    {"E": "high", "N": "high", "A": "mid",  "C": "low",  "O": "high"},  # 3: 외향+신경증+창의
    {"E": "high", "N": "low",  "A": "mid",  "C": "high", "O": "low"},   # 4: 외향+성실+현실
    # Introvert variants (5)
    {"E": "low",  "N": "low",  "A": "mid",  "C": "high", "O": "high"},  # 5: 내향+성실+개방
    {"E": "low",  "N": "low",  "A": "mid",  "C": "high", "O": "low"},   # 6: 내향+성실+현실
    {"E": "low",  "N": "high", "A": "mid",  "C": "high", "O": "high"},  # 7: 내향+신경증+개방
    {"E": "low",  "N": "high", "A": "low",  "C": "low",  "O": "mid"},   # 8: 내향+신경증+비친화
    {"E": "low",  "N": "low",  "A": "high", "C": "mid",  "O": "mid"},   # 9: 내향+친화
    # Mid-extroversion variants (5)
    {"E": "mid",  "N": "low",  "A": "high", "C": "high", "O": "high"},  # 10: 균형+친화+성실+개방
    {"E": "mid",  "N": "mid",  "A": "mid",  "C": "high", "O": "low"},   # 11: 균형+성실+현실
    {"E": "mid",  "N": "low",  "A": "low",  "C": "high", "O": "mid"},   # 12: 균형+성실+경쟁
    {"E": "mid",  "N": "high", "A": "high", "C": "mid",  "O": "high"},  # 13: 균형+신경증+친화+개방
    {"E": "mid",  "N": "mid",  "A": "mid",  "C": "mid",  "O": "mid"},   # 14: 완전 균형
]

# 20 occupations (diverse domains)
OCCUPATIONS: list[str] = [
    "마케터", "SW연구원", "회계사", "간호사", "초등교사",
    "영업사원", "기업임원", "공무원", "그래픽디자이너", "작가",
    "창업자", "건설감독", "대학원생", "번역가", "개인트레이너",
    "운동선수", "대학교수", "데이터과학자", "HR매니저", "요리사",
]

# Age range per occupation (min, max)
AGE_RANGES: dict[str, tuple[int, int]] = {
    "마케터": (24, 38), "SW연구원": (25, 45), "회계사": (28, 55),
    "간호사": (24, 50), "초등교사": (26, 55), "영업사원": (24, 45),
    "기업임원": (35, 60), "공무원": (25, 55), "그래픽디자이너": (22, 42),
    "작가": (28, 65), "창업자": (22, 45), "건설감독": (35, 60),
    "대학원생": (22, 35), "번역가": (25, 50), "개인트레이너": (22, 45),
    "운동선수": (18, 35), "대학교수": (32, 65), "데이터과학자": (24, 45),
    "HR매니저": (28, 55), "요리사": (22, 50),
}

# ── Big Five description helpers ───────────────────────────────────────────────

_BF_DESC = {
    "E_high": "외향적, 사교적, 활동적",
    "E_mid":  "보통의 사교성, 상황에 따라 외향/내향",
    "E_low":  "내향적, 혼자 시간 선호, 말이 적음",
    "N_high": "감정 기복 있음, 스트레스에 민감, 걱정 많음",
    "N_mid":  "대체로 안정적, 가끔 감정 기복",
    "N_low":  "정서적으로 안정, 느긋하고 차분함",
    "A_high": "친절, 협조적, 타인 배려 우선",
    "A_mid":  "보통의 친화성, 상황에 따라 협조적",
    "A_low":  "독립적, 경쟁적, 자기주장 강함",
    "C_high": "성실, 계획적, 꼼꼼하고 목표 지향적",
    "C_mid":  "보통의 성실성, 유연한 일정 관리",
    "C_low":  "즉흥적, 자유분방, 계획보다 흐름을 따름",
    "O_high": "개방적, 창의적, 새로운 경험 추구",
    "O_mid":  "보통의 개방성, 익숙한 것과 새로운 것 균형",
    "O_low":  "현실적, 전통 중시, 익숙한 방식 선호",
}


def bf_description(bf: dict) -> str:
    parts = [_BF_DESC[f"{k}_{v}"] for k, v in bf.items()]
    return "; ".join(parts)


# ── Prompt builder ─────────────────────────────────────────────────────────────

_BATCH_SYSTEM = """\
당신은 게임 NPC 성격 데이터 생성 전문가입니다.
아래 형식의 JSON 배열만 출력하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요.

각 항목 형식:
{
  "text": "한국어 자연어 성격 설명 (2-3문장, 100자 내외)",
  "age": 30,
  "decay_modifiers": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
  "preferred_actions": [0, 3]
}

주의사항:
- "age": 주어진 나이 범위 내의 정수
- "decay_modifiers": 길이가 8인 실수 배열 (순서: 0=hunger, 1=sleep, 2=social, 3=leisure, 4=hygiene, 5=fitness, 6=work, 7=learning) 범위 0.3~2.5
- "preferred_actions": 선호 행동 인덱스 2~3개의 정수 배열 (0=work, 1=eat, 2=sleep, 3=socialize, 4=exercise, 5=read, 6=clean, 7=rest)

성격 특성을 decay_modifiers에 반영:
- 사교적 → social(index 2) 높게, 내향적 → social 낮게
- 업무 집중 → work(index 6) 높게
- 운동 지향 → fitness(index 5) 높게
- 지식 추구 → learning(index 7) 높게
- 청결 중시 → hygiene(index 4) 높게
- 여유로운 성격 → leisure(index 3) 낮게 (느리게 감소)
"""


def build_batch_prompt(specs: list[dict]) -> str:
    lines = [f"다음 {len(specs)}개 NPC의 성격 JSON을 생성하세요:\n"]
    for i, s in enumerate(specs):
        bf_desc = bf_description(s["big_five"])
        age_range = AGE_RANGES[s["occupation"]]
        lines.append(
            f"{i+1}. 직업={s['occupation']}, "
            f"나이 범위={age_range[0]}-{age_range[1]}세, "
            f"Big Five=[{bf_desc}]"
        )
    return "\n".join(lines)


# ── Main generation loop ───────────────────────────────────────────────────────

BATCH_SIZE = 10
CHECKPOINT_PATH = pathlib.Path(
    "/home/swim/Documents/Projects/co-spec/data/personas/checkpoint_300.json"
)
OUT_DIR = pathlib.Path("/home/swim/Documents/Projects/co-spec/data/personas")


def load_checkpoint() -> dict[int, dict]:
    """Load already-generated personas (keyed by persona_id)."""
    if CHECKPOINT_PATH.exists():
        return {r["id"]: r for r in json.loads(CHECKPOINT_PATH.read_text())}
    return {}


def save_checkpoint(records: dict[int, dict]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
        json.dumps(sorted(records.values(), key=lambda r: r["id"]), indent=2, ensure_ascii=False)
    )


def generate_batch(
    specs: list[dict],
    client: genai.Client,
    model: str = "gemini-2.5-flash",
    retries: int = 3,
) -> list[dict]:
    prompt = build_batch_prompt(specs)
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_BATCH_SYSTEM,
                    max_output_tokens=8000,
                ),
            )
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            items = json.loads(raw)
            assert len(items) == len(specs), f"Expected {len(specs)}, got {len(items)}"
            return items
        except Exception as e:
            print(f"  Attempt {attempt+1}/{retries} failed: {e}")
            if 'raw' in locals():
                print(f"  [RAW OUTPUT DEBUB]:\n{raw}\n  [END RAW OUTPUT]")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to generate batch after {retries} attempts")


def build_persona_record(pid: int, spec: dict, gen: dict) -> dict:
    dm = gen.get("decay_modifiers", [1.0] * 8)
    if len(dm) != 8:
        dm = (dm + [1.0] * 8)[:8]
    dm = [max(0.3, min(2.5, float(v))) for v in dm]

    pa = [int(a) for a in gen.get("preferred_actions", [0]) if 0 <= int(a) <= 7][:3]
    if not pa:
        pa = [0]

    age = int(gen.get("age", 30))
    age_range = AGE_RANGES[spec["occupation"]]
    age = max(age_range[0], min(age_range[1], age))

    split = "test" if pid > 240 else "train"

    return {
        "id": pid,
        "text": gen.get("text", ""),
        "big_five": spec["big_five"],
        "occupation": spec["occupation"],
        "age": age,
        "decay_modifiers": dm,
        "preferred_actions": pa,
        "split": split,
    }


def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        print("Run: export GEMINI_API_KEY=AIza...")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash"

    # Build full spec list (300 items, ordered by persona_id)
    all_specs: list[dict] = []
    for occ_idx, occupation in enumerate(OCCUPATIONS):
        for bf_idx, big_five in enumerate(BIG_FIVE_PROFILES):
            pid = occ_idx * 15 + bf_idx + 1  # 1-indexed
            all_specs.append({"id": pid, "occupation": occupation, "big_five": big_five})
    all_specs.sort(key=lambda s: s["id"])

    records = load_checkpoint()
    missing = [s for s in all_specs if s["id"] not in records]
    print(f"Total: 300 | Already done: {len(records)} | Remaining: {len(missing)}")

    if not missing:
        print("All personas already generated. Skipping to export.")
    else:
        batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        print(f"Generating {len(missing)} personas in {len(batches)} batches (model={model})\n")

        for b_idx, batch_specs in enumerate(batches):
            print(f"Batch {b_idx+1}/{len(batches)} (IDs {batch_specs[0]['id']}-{batch_specs[-1]['id']})...")
            t0 = time.time()
            generated = generate_batch(batch_specs, client=client, model=model)
            elapsed = time.time() - t0

            for spec, gen in zip(batch_specs, generated):
                rec = build_persona_record(spec["id"], spec, gen)
                records[rec["id"]] = rec

            save_checkpoint(records)
            print(f"  Done in {elapsed:.1f}s | checkpoint saved ({len(records)}/300)")
            time.sleep(0.3)  # brief pause between batches

    # Export final JSON files
    all_records = sorted(records.values(), key=lambda r: r["id"])
    train = [r for r in all_records if r["split"] == "train"]
    test  = [r for r in all_records if r["split"] == "test"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "personas_300.json").write_text(
        json.dumps(all_records, indent=2, ensure_ascii=False)
    )
    (OUT_DIR / "train_240.json").write_text(
        json.dumps(train, indent=2, ensure_ascii=False)
    )
    (OUT_DIR / "test_60.json").write_text(
        json.dumps(test, indent=2, ensure_ascii=False)
    )

    print(f"\nSaved {len(train)} train + {len(test)} test → {OUT_DIR}")
    print("Files: personas_300.json, train_240.json, test_60.json")

    # Quick stats
    import collections
    occ_counts = collections.Counter(r["occupation"] for r in all_records)
    bf_e_counts = collections.Counter(r["big_five"]["E"] for r in all_records)
    print(f"\nBig Five E distribution: {dict(bf_e_counts)}")
    print(f"Occupation sample: {list(occ_counts.items())[:5]}")


if __name__ == "__main__":
    main()
