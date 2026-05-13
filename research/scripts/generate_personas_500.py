"""
Phase 7: Persona 500개 생성 (Gemini API)
-----------------------------------------
25 Big Five archetypes × 20 occupations = 500 personas
  - train split: 400개 (ID 1-400)
  - test split:  100개 (ID 401-500, zero-shot 평가용)

실행:
  conda run -n paper python scripts/generate_personas_500.py

출력: data/personas/personas_500.json, train_400.json, test_100.json
"""
import sys, json, time, pathlib, os, random
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from google import genai
from google.genai import types

# ── 25 Big Five archetypes ─────────────────────────────────────────────────────
BIG_FIVE_PROFILES: list[dict] = [
    # Extrovert variants (5)
    {"E": "high", "N": "low",  "A": "mid",  "C": "mid",  "O": "high"},  # 0
    {"E": "high", "N": "mid",  "A": "low",  "C": "high", "O": "mid"},   # 1
    {"E": "high", "N": "mid",  "A": "high", "C": "mid",  "O": "mid"},   # 2
    {"E": "high", "N": "high", "A": "mid",  "C": "low",  "O": "high"},  # 3
    {"E": "high", "N": "low",  "A": "mid",  "C": "high", "O": "low"},   # 4
    # Introvert variants (5)
    {"E": "low",  "N": "low",  "A": "mid",  "C": "high", "O": "high"},  # 5
    {"E": "low",  "N": "low",  "A": "mid",  "C": "high", "O": "low"},   # 6
    {"E": "low",  "N": "high", "A": "mid",  "C": "high", "O": "high"},  # 7
    {"E": "low",  "N": "high", "A": "low",  "C": "low",  "O": "mid"},   # 8
    {"E": "low",  "N": "low",  "A": "high", "C": "mid",  "O": "mid"},   # 9
    # Mid-extroversion variants (5)
    {"E": "mid",  "N": "low",  "A": "high", "C": "high", "O": "high"},  # 10
    {"E": "mid",  "N": "mid",  "A": "mid",  "C": "high", "O": "low"},   # 11
    {"E": "mid",  "N": "low",  "A": "low",  "C": "high", "O": "mid"},   # 12
    {"E": "mid",  "N": "high", "A": "high", "C": "mid",  "O": "high"},  # 13
    {"E": "mid",  "N": "mid",  "A": "mid",  "C": "mid",  "O": "mid"},   # 14
    # Additional archetypes (10)
    {"E": "low",  "N": "mid",  "A": "low",  "C": "high", "O": "low"},   # 15 내향+경쟁+현실
    {"E": "high", "N": "low",  "A": "high", "C": "high", "O": "high"},  # 16 외향+친화+성실+개방
    {"E": "mid",  "N": "high", "A": "low",  "C": "high", "O": "mid"},   # 17 균형+신경증+경쟁+성실
    {"E": "low",  "N": "mid",  "A": "high", "C": "low",  "O": "high"},  # 18 내향+친화+개방
    {"E": "high", "N": "high", "A": "low",  "C": "high", "O": "low"},   # 19 외향+신경증+경쟁
    {"E": "mid",  "N": "low",  "A": "mid",  "C": "low",  "O": "high"},  # 20 균형+개방
    {"E": "low",  "N": "high", "A": "high", "C": "mid",  "O": "mid"},   # 21 내향+신경증+친화
    {"E": "high", "N": "mid",  "A": "mid",  "C": "high", "O": "high"},  # 22 외향+성실+개방
    {"E": "mid",  "N": "mid",  "A": "low",  "C": "low",  "O": "low"},   # 23 균형+기본
    {"E": "low",  "N": "low",  "A": "low",  "C": "low",  "O": "mid"},   # 24 내향+기본
]

OCCUPATIONS: list[str] = [
    "마케터", "SW연구원", "회계사", "간호사", "초등교사",
    "영업사원", "기업임원", "공무원", "그래픽디자이너", "작가",
    "창업자", "건설감독", "대학원생", "번역가", "개인트레이너",
    "운동선수", "대학교수", "데이터과학자", "HR매니저", "요리사",
]

AGE_RANGES: dict[str, tuple[int, int]] = {
    "마케터": (24, 38), "SW연구원": (25, 45), "회계사": (28, 55),
    "간호사": (24, 50), "초등교사": (26, 55), "영업사원": (24, 45),
    "기업임원": (35, 60), "공무원": (25, 55), "그래픽디자이너": (22, 42),
    "작가": (28, 65), "창업자": (22, 45), "건설감독": (35, 60),
    "대학원생": (22, 35), "번역가": (25, 50), "개인트레이너": (22, 45),
    "운동선수": (18, 35), "대학교수": (32, 65), "데이터과학자": (24, 45),
    "HR매니저": (28, 55), "요리사": (22, 50),
}

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
    "C_mid":  "보통의 성실성, 상황에 따라 계획/즉흥",
    "C_low":  "즉흥적, 유연하고 자유로운 편",
    "O_high": "상상력 풍부, 새로운 것 선호, 지적 호기심",
    "O_mid":  "보통의 개방성, 친숙한 것과 새것 균형",
    "O_low":  "실용적, 전통 선호, 현실적",
}

NEED_NAMES  = ["hunger", "sleep", "social", "leisure", "hygiene", "fitness", "work", "learning"]
ACTION_NAMES = ["work", "eat", "sleep", "socialize", "exercise", "read", "clean", "rest",
                "move_up", "move_down", "move_left", "move_right"]

DATA_DIR   = ROOT / "data" / "personas"
CKPT_FILE  = DATA_DIR / "checkpoint_500.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def bf_description(bf: dict) -> str:
    parts = [_BF_DESC[f"{k}_{v}"] for k, v in bf.items()]
    return ", ".join(parts)


def build_prompt(bf: dict, occupation: str, age: int) -> str:
    bf_desc = bf_description(bf)
    return f"""당신은 생활 시뮬레이션 게임의 NPC 성격 설계자입니다.
아래 조건에 맞는 NPC persona를 JSON으로 출력하세요.

직업: {occupation}
나이: {age}세
Big Five 특성: {bf_desc}

출력 JSON 형식 (반드시 정확히 이 형식):
{{
  "text": "<한국어로 2-3문장, 성격·직업·생활방식을 구체적으로 묘사>",
  "decay_modifiers": [hunger, sleep, social, leisure, hygiene, fitness, work, learning],
  "preferred_actions": [<0-7 사이 행동 인덱스 2개>]
}}

규칙:
- text: 이름/나이/직업을 포함한 자연스러운 NPC 소개 (2-3문장)
- decay_modifiers: 각 8개 값은 0.3~2.5 범위의 float. 1.0=평균. 높을수록 더 빨리 고갈됨
  (hunger=0, sleep=1, social=2, leisure=3, hygiene=4, fitness=5, work=6, learning=7)
- preferred_actions: 이 persona가 선호하는 행동 2개의 인덱스
  (work=0, eat=1, sleep=2, socialize=3, exercise=4, read=5, clean=6, rest=7)
- Big Five 특성을 decay와 preferred_actions에 반영할 것
  (예: 외향적이면 social decay 높게, 사교 행동 선호)
- JSON만 출력. 설명 없음."""


def parse_response(text: str, bf: dict, occupation: str, age: int) -> dict | None:
    text = text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        d = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

    # Validate
    if "text" not in d or "decay_modifiers" not in d or "preferred_actions" not in d:
        return None
    dm = d["decay_modifiers"]
    if len(dm) != 8 or not all(0.2 <= v <= 3.0 for v in dm):
        return None
    pa = d["preferred_actions"]
    if len(pa) < 1 or not all(0 <= v <= 7 for v in pa):
        return None

    return {
        "big_five":           bf,
        "occupation":         occupation,
        "age":                age,
        "text":               d["text"],
        "decay_modifiers":    [round(float(v), 3) for v in dm],
        "preferred_actions":  [int(v) for v in pa[:2]],
    }


def generate_all(max_retries: int = 3) -> list[dict]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # Load checkpoint
    if CKPT_FILE.exists():
        done_map = json.loads(CKPT_FILE.read_text())
        print(f"Checkpoint loaded: {len(done_map)} personas already done")
    else:
        done_map = {}

    all_personas = []
    pid          = 1

    for arch_idx, bf in enumerate(BIG_FIVE_PROFILES):
        for occ in OCCUPATIONS:
            key = f"{arch_idx}_{occ}"
            if key in done_map:
                p = done_map[key]
                p["id"]    = pid
                p["split"] = "test" if pid > 400 else "train"
                all_personas.append(p)
                pid += 1
                continue

            age    = random.randint(*AGE_RANGES[occ])
            prompt = build_prompt(bf, occ, age)
            result = None

            for attempt in range(max_retries):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.8,
                            max_output_tokens=400,
                        ),
                    )
                    result = parse_response(resp.text, bf, occ, age)
                    if result:
                        break
                    print(f"  Parse failed (attempt {attempt+1}): arch={arch_idx} occ={occ}")
                except Exception as e:
                    print(f"  API error (attempt {attempt+1}): {e}")
                    time.sleep(2 ** attempt)

            if result is None:
                # Fallback: use rule-based defaults
                e_lvl = {"high": 1.5, "mid": 1.0, "low": 0.6}.get(bf.get("E", "mid"), 1.0)
                c_lvl = {"high": 1.3, "mid": 1.0, "low": 0.7}.get(bf.get("C", "mid"), 1.0)
                result = {
                    "big_five":          bf,
                    "occupation":        occ,
                    "age":               age,
                    "text":              f"{age}세 {occ}. {bf_description(bf)}.",
                    "decay_modifiers":   [1.0, 1.0, round(e_lvl, 2), 1.0, 1.0, 1.0,
                                         round(c_lvl, 2), 1.0],
                    "preferred_actions": [3, 0] if bf.get("E") == "high" else [5, 7],
                }
                print(f"  Fallback used: arch={arch_idx} occ={occ}")

            done_map[key] = result
            CKPT_FILE.write_text(json.dumps(done_map, ensure_ascii=False, indent=2))

            result["id"]    = pid
            result["split"] = "test" if pid > 400 else "train"
            all_personas.append(result)
            pid += 1

            print(f"  [{pid-1:3d}/500] {occ} ({bf.get('E','?')}E/{bf.get('N','?')}N)")
            time.sleep(0.3)  # rate limit courtesy

    return all_personas


def main():
    print("Phase 7: Generating 500 personas (25 BF archetypes × 20 occupations)")
    personas = generate_all()

    train = [p for p in personas if p["split"] == "train"]
    test  = [p for p in personas if p["split"] == "test"]

    (DATA_DIR / "personas_500.json").write_text(
        json.dumps(personas, ensure_ascii=False, indent=2)
    )
    (DATA_DIR / "train_400.json").write_text(
        json.dumps(train, ensure_ascii=False, indent=2)
    )
    (DATA_DIR / "test_100.json").write_text(
        json.dumps(test, ensure_ascii=False, indent=2)
    )
    print(f"\nSaved {len(train)} train / {len(test)} test → {DATA_DIR}")


if __name__ == "__main__":
    main()
