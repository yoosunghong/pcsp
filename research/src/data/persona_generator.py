"""
Persona dataset: Big Five × occupation → 30 seed personas
각 persona의 decay_modifiers와 preferred_actions를 함께 정의해 환경과 바로 연동 가능.
"""
from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass, asdict

# Big Five 축 (E/I, N/S, A/D, C/U, O/C)
# E=Extroversion, N=Neuroticism, A=Agreeableness, C=Conscientiousness, O=Openness

NEED_IDX = {
    "hunger": 0, "sleep": 1, "social": 2, "leisure": 3,
    "hygiene": 4, "fitness": 5, "work": 6, "learning": 7,
}
ACTION_IDX = {
    "work": 0, "eat": 1, "sleep": 2, "socialize": 3,
    "exercise": 4, "read": 5, "clean": 6, "rest": 7,
    "move_up": 8, "move_down": 9,
}


@dataclass
class Persona:
    id: int
    text: str          # 자연어 설명
    big_five: dict     # E, N, A, C, O: "high"/"mid"/"low"
    occupation: str
    age: int
    # decay_modifiers: shape (8,), multiplier on BASE_DECAY
    decay_modifiers: list[float]
    # preferred_actions: action indices that earn +0.5 bonus
    preferred_actions: list[int]
    split: str = "train"   # "train" or "test"


def _make_decay(social_mult: float, work_mult: float, learning_mult: float,
                fitness_mult: float, leisure_mult: float) -> list[float]:
    """Build decay modifier vector. Only deviating axes provided."""
    base = [1.0] * 8
    base[NEED_IDX["social"]] = social_mult
    base[NEED_IDX["work"]] = work_mult
    base[NEED_IDX["learning"]] = learning_mult
    base[NEED_IDX["fitness"]] = fitness_mult
    base[NEED_IDX["leisure"]] = leisure_mult
    return base


PERSONAS: list[Persona] = [
    # ── Extrovert × High Openness ───────────────────────────────────────────
    Persona(1, "외향적이고 새로운 경험을 즐기는 25세 마케터. 사람들과 어울리기 좋아하고 운동도 자주 한다.",
            {"E": "high", "N": "mid", "A": "mid", "C": "mid", "O": "high"},
            "마케터", 25, _make_decay(1.5, 0.8, 0.9, 1.2, 0.9),
            [ACTION_IDX["socialize"], ACTION_IDX["exercise"]]),

    Persona(2, "사교적이고 창의적인 28세 배우. 무대와 사람들을 사랑하며 즉흥 연기를 즐긴다.",
            {"E": "high", "N": "high", "A": "high", "C": "low", "O": "high"},
            "배우", 28, _make_decay(1.6, 0.7, 1.0, 0.9, 0.8),
            [ACTION_IDX["socialize"], ACTION_IDX["rest"]]),

    Persona(3, "활발하고 호기심 많은 22세 여행 블로거. 낯선 곳과 새로운 만남을 즐긴다.",
            {"E": "high", "N": "low", "A": "mid", "C": "low", "O": "high"},
            "여행블로거", 22, _make_decay(1.4, 0.6, 1.1, 1.0, 0.7),
            [ACTION_IDX["socialize"], ACTION_IDX["read"]]),

    # ── Introvert × High Conscientiousness ──────────────────────────────────
    Persona(4, "내성적이고 신중한 35세 소프트웨어 연구원. 독서와 혼자만의 집중 시간을 소중히 여긴다.",
            {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "high"},
            "SW연구원", 35, _make_decay(0.6, 1.0, 1.3, 1.0, 1.2),
            [ACTION_IDX["read"], ACTION_IDX["work"]]),

    Persona(5, "조용하고 분석적인 40세 회계사. 정확성을 중시하고 루틴에서 안정감을 얻는다.",
            {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "low"},
            "회계사", 40, _make_decay(0.5, 1.0, 1.2, 0.9, 1.1),
            [ACTION_IDX["work"], ACTION_IDX["rest"]]),

    Persona(6, "내성적이고 세심한 33세 편집자. 글과 단어 속에서 혼자 시간을 보내는 걸 좋아한다.",
            {"E": "low", "N": "mid", "A": "high", "C": "high", "O": "high"},
            "편집자", 33, _make_decay(0.6, 1.1, 1.4, 0.8, 1.2),
            [ACTION_IDX["read"], ACTION_IDX["work"]]),

    # ── High Agreeableness × Caring ────────────────────────────────────────
    Persona(7, "친절하고 공감능력이 뛰어난 29세 간호사. 타인 돌봄을 최우선으로 생각하고 팀워크를 중시한다.",
            {"E": "mid", "N": "mid", "A": "high", "C": "high", "O": "mid"},
            "간호사", 29, _make_decay(1.2, 0.9, 1.0, 0.9, 1.0),
            [ACTION_IDX["socialize"], ACTION_IDX["clean"]]),

    Persona(8, "온화하고 가족 중심적인 42세 초등교사. 아이들을 가르치는 데서 보람을 느낀다.",
            {"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
            "초등교사", 42, _make_decay(1.3, 0.8, 1.1, 0.8, 0.9),
            [ACTION_IDX["socialize"], ACTION_IDX["read"]]),

    Persona(9, "인내심 있고 배려심 깊은 37세 사회복지사. 취약 계층 지원에 삶의 의미를 둔다.",
            {"E": "mid", "N": "mid", "A": "high", "C": "mid", "O": "mid"},
            "사회복지사", 37, _make_decay(1.2, 0.9, 0.9, 0.9, 1.0),
            [ACTION_IDX["socialize"], ACTION_IDX["rest"]]),

    # ── High Conscientiousness × Performance ───────────────────────────────
    Persona(10, "경쟁적이고 목표 지향적인 32세 영업사원. 성과를 중시하고 끊임없이 새로운 도전을 찾는다.",
             {"E": "high", "N": "mid", "A": "low", "C": "high", "O": "mid"},
             "영업사원", 32, _make_decay(1.2, 1.3, 0.9, 1.1, 0.7),
             [ACTION_IDX["work"], ACTION_IDX["socialize"]]),

    Persona(11, "야망 있고 전략적인 38세 기업 임원. 효율과 결과를 추구하며 시간 관리를 철저히 한다.",
             {"E": "high", "N": "low", "A": "low", "C": "high", "O": "mid"},
             "기업임원", 38, _make_decay(1.1, 1.4, 0.8, 1.0, 0.7),
             [ACTION_IDX["work"], ACTION_IDX["exercise"]]),

    Persona(12, "성실하고 꼼꼼한 30세 공무원. 규정을 준수하고 안정적인 삶을 선호한다.",
             {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "low"},
             "공무원", 30, _make_decay(0.7, 1.0, 1.2, 0.9, 1.1),
             [ACTION_IDX["work"], ACTION_IDX["rest"]]),

    # ── High Openness × Creativity ─────────────────────────────────────────
    Persona(13, "창의적이고 즉흥적인 26세 그래픽 디자이너. 시각 예술에 몰두하고 자유로운 일정을 즐긴다.",
             {"E": "mid", "N": "mid", "A": "mid", "C": "low", "O": "high"},
             "그래픽디자이너", 26, _make_decay(1.0, 0.7, 1.3, 1.0, 0.8),
             [ACTION_IDX["read"], ACTION_IDX["rest"]]),

    Persona(14, "몽상적이고 철학적인 45세 작가. 글쓰기와 사색을 통해 세상을 이해한다.",
             {"E": "low", "N": "mid", "A": "mid", "C": "low", "O": "high"},
             "작가", 45, _make_decay(0.6, 0.8, 1.4, 0.9, 1.1),
             [ACTION_IDX["read"], ACTION_IDX["rest"]]),

    Persona(15, "실험적이고 도전적인 24세 스타트업 창업자. 새로운 아이디어와 빠른 실행을 중시한다.",
             {"E": "high", "N": "high", "A": "mid", "C": "mid", "O": "high"},
             "창업자", 24, _make_decay(1.3, 1.2, 1.0, 1.0, 0.8),
             [ACTION_IDX["work"], ACTION_IDX["socialize"]]),

    # ── Low Openness × Stability ────────────────────────────────────────────
    Persona(16, "현실적이고 실용적인 50세 건설 현장 감독. 경험과 노하우를 중시하고 변화를 싫어한다.",
             {"E": "mid", "N": "low", "A": "mid", "C": "high", "O": "low"},
             "건설감독", 50, _make_decay(0.9, 1.0, 1.1, 1.2, 0.9),
             [ACTION_IDX["work"], ACTION_IDX["rest"]]),

    Persona(17, "보수적이고 안정 지향적인 48세 은행원. 정해진 절차를 따르고 위험을 피한다.",
             {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "low"},
             "은행원", 48, _make_decay(0.6, 1.0, 1.2, 0.9, 1.1),
             [ACTION_IDX["work"], ACTION_IDX["rest"]]),

    # ── High Neuroticism ───────────────────────────────────────────────────
    Persona(18, "감수성이 풍부하고 걱정이 많은 27세 대학원생. 완벽주의적 경향이 있고 스트레스에 민감하다.",
             {"E": "low", "N": "high", "A": "mid", "C": "high", "O": "high"},
             "대학원생", 27, _make_decay(0.7, 0.9, 1.4, 1.0, 1.0),
             [ACTION_IDX["read"], ACTION_IDX["rest"]]),

    Persona(19, "열정적이지만 불안감이 높은 31세 프리랜서 번역가. 혼자 일하지만 외로움을 많이 탄다.",
             {"E": "low", "N": "high", "A": "mid", "C": "mid", "O": "high"},
             "번역가", 31, _make_decay(1.3, 0.8, 1.3, 1.1, 1.0),
             [ACTION_IDX["read"], ACTION_IDX["socialize"]]),

    # ── Fitness & Health Focused ──────────────────────────────────────────
    Persona(20, "건강에 집착하는 34세 개인 트레이너. 운동과 식단 관리를 삶의 중심으로 삼는다.",
             {"E": "high", "N": "low", "A": "mid", "C": "high", "O": "mid"},
             "개인트레이너", 34, _make_decay(1.0, 0.8, 1.1, 1.5, 0.7),
             [ACTION_IDX["exercise"], ACTION_IDX["eat"]]),

    Persona(21, "활동적이고 경쟁심 강한 23세 운동선수. 매일 훈련이 최우선이고 승부욕이 강하다.",
             {"E": "mid", "N": "mid", "A": "low", "C": "high", "O": "low"},
             "운동선수", 23, _make_decay(1.0, 1.0, 1.0, 1.6, 0.6),
             [ACTION_IDX["exercise"], ACTION_IDX["eat"]]),

    # ── Learning & Knowledge ──────────────────────────────────────────────
    Persona(22, "호기심 많고 지적인 36세 대학교수. 연구와 강의에 삶의 의미를 찾고 독서를 즐긴다.",
             {"E": "mid", "N": "low", "A": "high", "C": "high", "O": "high"},
             "대학교수", 36, _make_decay(0.9, 0.9, 1.3, 1.0, 1.1),
             [ACTION_IDX["read"], ACTION_IDX["work"]]),

    Persona(23, "탐구심이 강하고 꼼꼼한 29세 데이터 과학자. 데이터 분석에 몰두하고 새로운 알고리즘 학습을 즐긴다.",
             {"E": "low", "N": "low", "A": "mid", "C": "high", "O": "high"},
             "데이터과학자", 29, _make_decay(0.6, 0.9, 1.4, 0.9, 1.1),
             [ACTION_IDX["read"], ACTION_IDX["work"]]),

    # ── Social & Community ────────────────────────────────────────────────
    Persona(24, "사교적이고 열린 마음을 가진 39세 HR 매니저. 사람과의 관계를 통해 에너지를 얻는다.",
             {"E": "high", "N": "low", "A": "high", "C": "mid", "O": "mid"},
             "HR매니저", 39, _make_decay(1.5, 0.9, 0.8, 1.0, 0.8),
             [ACTION_IDX["socialize"], ACTION_IDX["work"]]),

    Persona(25, "밝고 유머러스한 31세 유튜버. 콘텐츠 제작과 팬들과의 소통으로 즐거움을 찾는다.",
             {"E": "high", "N": "mid", "A": "high", "C": "low", "O": "high"},
             "유튜버", 31, _make_decay(1.5, 0.7, 1.1, 0.9, 0.8),
             [ACTION_IDX["socialize"], ACTION_IDX["rest"]]),

    # ── Balanced / Mixed ─────────────────────────────────────────────────
    Persona(26, "균형 잡힌 삶을 추구하는 43세 중간관리자. 일과 가정 모두 소중히 여기고 루틴을 중시한다.",
             {"E": "mid", "N": "low", "A": "mid", "C": "high", "O": "mid"},
             "중간관리자", 43, _make_decay(1.0, 1.0, 1.0, 1.0, 1.0),
             [ACTION_IDX["work"], ACTION_IDX["socialize"]]),

    Persona(27, "다재다능한 30세 프리랜서 개발자. 자유로운 일정을 즐기지만 마감을 철저히 지킨다.",
             {"E": "mid", "N": "mid", "A": "mid", "C": "mid", "O": "high"},
             "프리랜서개발자", 30, _make_decay(0.9, 0.8, 1.2, 0.9, 1.0),
             [ACTION_IDX["work"], ACTION_IDX["read"]]),

    # ── Elderly / Life Experience ──────────────────────────────────────────
    Persona(28, "여유롭고 지혜로운 62세 은퇴자. 정원 가꾸기와 손자들과의 시간을 즐긴다.",
             {"E": "mid", "N": "low", "A": "high", "C": "mid", "O": "mid"},
             "은퇴자", 62, _make_decay(1.1, 1.0, 1.2, 1.3, 0.8),
             [ACTION_IDX["rest"], ACTION_IDX["socialize"]]),

    Persona(29, "경험 많고 멘토링을 즐기는 55세 시니어 엔지니어. 후배 양성과 기술 전수에 보람을 느낀다.",
             {"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
             "시니어엔지니어", 55, _make_decay(0.8, 1.0, 1.1, 0.9, 1.0),
             [ACTION_IDX["work"], ACTION_IDX["socialize"]]),

    Persona(30, "위생에 철저하고 규칙적인 33세 요리사. 청결을 생명으로 여기고 매일 새로운 레시피를 연구한다.",
             {"E": "mid", "N": "mid", "A": "mid", "C": "high", "O": "high"},
             "요리사", 33, _make_decay(0.9, 0.9, 1.0, 0.9, 1.3),
             [ACTION_IDX["clean"], ACTION_IDX["eat"]]),
]

# 24~30번은 test split
for p in PERSONAS:
    p.split = "test" if p.id >= 25 else "train"


def save_dataset(out_dir: str | pathlib.Path | None = None) -> None:
    if out_dir is None:
        out_dir = pathlib.Path(__file__).resolve().parents[2] / "data" / "personas"
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    records = [asdict(p) for p in PERSONAS]
    (out_path / "personas_30.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False)
    )

    train = [r for r in records if r["split"] == "train"]
    test  = [r for r in records if r["split"] == "test"]
    (out_path / "train.json").write_text(json.dumps(train, indent=2, ensure_ascii=False))
    (out_path / "test.json").write_text(json.dumps(test,  indent=2, ensure_ascii=False))

    print(f"Saved {len(train)} train / {len(test)} test personas → {out_path}")
    return records


if __name__ == "__main__":
    save_dataset()
