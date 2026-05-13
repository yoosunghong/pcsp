"""
Designer-authored persona case study for PCSP-v3.

Inference-only workflow:
  1. Define 13 designer-authored personas inspired by The Sims 3 traits and
     Animal Crossing villager personalities.
  2. Encode them with Qwen3-Embedding-0.6B using the same last-token pooling
     and L2 normalization as the training pipeline.
  3. Run a trained PCSP-v3 policy for 5 episodes per persona.
  4. Save action-distribution bar charts, nearest-neighbor similarity against
     train_240_v3, a combined t-SNE plot, JSON, and a markdown report.

Usage:
  conda run -n paper python scripts/run_designer_persona_case_study.py
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.manifold import TSNE
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import PersonaConfig
from src.env.mini_inzoi_v3 import MiniInzoiV3Env
from src.env.v3_constants import ACTION_NAMES_V3, ACTION_STYLE_PROFILE, N_ACTIONS_V3, OBS_DIM_V3_BASE
from src.training.pcsp_trainer import PCSPActorCritic

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
MAX_LENGTH = 128
BATCH_SIZE = 16
TRAIT_KEYS = ("E", "N", "A", "C", "O")

@dataclass(frozen=True)
class DesignerPersona:
    key: str
    persona_name: str
    source: str
    source_traits: str
    occupation: str
    text: str
    big_five: dict[str, str]
    preferred_actions: list[int]
    decay_modifiers: list[float]
    alignment_expectation: str

    def to_persona_record(self, record_id: int) -> dict[str, Any]:
        return {
            "id": record_id,
            "name": self.key,
            "persona_name": self.persona_name,
            "text": self.text,
            "big_five": self.big_five,
            "occupation": self.occupation,
            "age": 30,
            "decay_modifiers": self.decay_modifiers,
            "preferred_actions": self.preferred_actions,
            "split": "designer_case_study",
            "source": self.source,
            "source_traits": self.source_traits,
            "alignment_expectation": self.alignment_expectation,
        }


DESIGNER_PERSONAS = [
    DesignerPersona(
        key="sims_workaholic_strategist",
        persona_name="corporate strategist",
        source="The Sims 3",
        source_traits="Workaholic + Ambitious + Perfectionist",
        occupation="기업 전략가",
        text="A disciplined, goal-oriented corporate strategist. He cares deeply about polished plans, and even during breaks reviews his recent work and the next learning targets he has set for himself.",
        big_five={"E": "mid", "N": "mid", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[0, 1, 10],
        decay_modifiers=[1.0, 1.1, 0.8, 1.2, 1.0, 1.0, 2.0, 1.6],
        alignment_expectation="Expected to favor focused_work, planning_work, and read_deep.",
    ),
    DesignerPersona(
        key="sims_loner_researcher",
        persona_name="introverted researcher",
        source="The Sims 3",
        source_traits="Loner + Bookworm + Neurotic",
        occupation="내성적인 연구원",
        text="A quiet, careful introverted researcher. She prefers reading and organizing material alone over crowded places, and when anxiety creeps in she settles herself by retreating into familiar routines.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[10, 13, 1],
        decay_modifiers=[1.0, 1.1, 0.5, 1.0, 1.1, 0.9, 1.2, 2.0],
        alignment_expectation="Expected to favor read_deep, rest_alone, and planning_work.",
    ),
    DesignerPersona(
        key="sims_party_event_planner",
        persona_name="outgoing event planner",
        source="The Sims 3",
        source_traits="Party Animal + Charismatic + Friendly",
        occupation="이벤트 플래너",
        text="A sociable, warm event planner. She gets her energy from gathering people together and lifting the mood, and her day naturally flows around conversation and shared downtime.",
        big_five={"E": "high", "N": "low", "A": "high", "C": "mid", "O": "mid"},
        preferred_actions=[6, 7, 14],
        decay_modifiers=[1.0, 0.9, 2.0, 1.3, 1.0, 1.0, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_initiate, socialize_respond, and rest_with_others.",
    ),
    DesignerPersona(
        key="sims_athletic_trainer",
        persona_name="competitive personal trainer",
        source="The Sims 3",
        source_traits="Athletic + Brave + Disciplined",
        occupation="개인 트레이너",
        text="A brave, highly disciplined personal trainer. He sets competitive training goals, keeps a steady conditioning routine, and tends to act first when things get tough.",
        big_five={"E": "high", "N": "low", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[8, 9, 0],
        decay_modifiers=[1.1, 0.9, 1.1, 0.9, 1.2, 2.0, 1.2, 0.9],
        alignment_expectation="Expected to favor exercise_intense, exercise_light, and focused_work.",
    ),
    DesignerPersona(
        key="sims_couch_potato_freelancer",
        persona_name="unmotivated freelancer",
        source="The Sims 3",
        source_traits="Couch Potato + Slob + Lazy",
        occupation="프리랜서",
        text="An easygoing, low-motivation freelancer. He puts off work to lounge on the couch or grab quick meals, and avoids energy-intensive chores like cleaning or exercise.",
        big_five={"E": "low", "N": "mid", "A": "mid", "C": "low", "O": "low"},
        preferred_actions=[2, 4, 13],
        decay_modifiers=[1.5, 1.6, 0.7, 0.6, 0.5, 0.4, 0.5, 0.6],
        alignment_expectation="Expected to favor eat_quick, sleep/nap, and rest_alone.",
    ),
    DesignerPersona(
        key="ac_lazy_villager",
        persona_name="lazy villager",
        source="Animal Crossing",
        source_traits="Lazy personality",
        occupation="느긋한 마을 주민",
        text="An easygoing villager who loves food and sleep. He prefers a slow-eating, rest-heavy daily rhythm over rushing around, and is friendly without getting attached to big plans.",
        big_five={"E": "low", "N": "low", "A": "high", "C": "low", "O": "mid"},
        preferred_actions=[3, 4, 13],
        decay_modifiers=[1.7, 1.6, 0.9, 0.7, 0.8, 0.5, 0.5, 0.7],
        alignment_expectation="Expected to favor eat_slow, sleep/nap, and rest_alone.",
    ),
    DesignerPersona(
        key="ac_jock_villager",
        persona_name="jock villager",
        source="Animal Crossing",
        source_traits="Jock personality",
        occupation="운동광 마을 주민",
        text="An energetic villager who obsesses over fitness. He fills most of the day with conditioning and active games, and even his conversations gravitate toward how to get stronger.",
        big_five={"E": "high", "N": "low", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[8, 9, 15],
        decay_modifiers=[1.2, 0.9, 1.2, 1.0, 1.2, 2.0, 0.8, 0.8],
        alignment_expectation="Expected to favor exercise_intense, exercise_light, and explore.",
    ),
    DesignerPersona(
        key="ac_cranky_villager",
        persona_name="cranky villager",
        source="Animal Crossing",
        source_traits="Cranky personality",
        occupation="무뚝뚝한 마을 주민",
        text="A stubborn, old-fashioned villager with a gruff exterior. He comes off prickly at first but quietly looks out for the people he knows, and is more at ease in solitary downtime than in anything fashionable.",
        big_five={"E": "low", "N": "mid", "A": "low", "C": "mid", "O": "low"},
        preferred_actions=[13, 10, 12],
        decay_modifiers=[1.0, 1.1, 0.6, 0.9, 1.0, 0.8, 0.9, 0.9],
        alignment_expectation="Expected to favor rest_alone, read_deep, and clean.",
    ),
    DesignerPersona(
        key="ac_normal_villager",
        persona_name="normal villager",
        source="Animal Crossing",
        source_traits="Normal personality",
        occupation="다정한 마을 주민",
        text="A gentle, attentive villager who cares about hygiene and tidiness. She keeps a calm routine of cleaning and self-care, and quietly helps the people around her feel at ease.",
        big_five={"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[12, 7, 14],
        decay_modifiers=[1.0, 0.9, 1.1, 0.9, 1.8, 0.9, 0.9, 1.0],
        alignment_expectation="Expected to favor clean, socialize_respond, and rest_with_others.",
    ),
    DesignerPersona(
        key="ac_peppy_villager",
        persona_name="peppy villager",
        source="Animal Crossing",
        source_traits="Peppy personality",
        occupation="팝스타 지망생",
        text="An upbeat villager who dreams of becoming a pop star. She talks to strangers first, enjoys active play, and moves through the day as if it were a rehearsal — bright and fast-paced.",
        big_five={"E": "high", "N": "low", "A": "high", "C": "mid", "O": "high"},
        preferred_actions=[6, 15, 14],
        decay_modifiers=[1.1, 0.8, 1.8, 1.4, 1.1, 1.2, 0.8, 1.2],
        alignment_expectation="Expected to favor socialize_initiate, explore, and rest_with_others.",
    ),
    DesignerPersona(
        key="ac_snooty_villager",
        persona_name="snooty villager",
        source="Animal Crossing",
        source_traits="Snooty personality",
        occupation="패션 애호가",
        text="A villager obsessed with fashion who holds firm to her own standards. She works at staying polished, and even in company she carries herself with a confident, slightly distant air.",
        big_five={"E": "mid", "N": "mid", "A": "low", "C": "high", "O": "high"},
        preferred_actions=[12, 1, 6],
        decay_modifiers=[0.9, 0.9, 1.0, 1.1, 1.8, 0.9, 1.0, 1.1],
        alignment_expectation="Expected to favor clean, planning_work, and controlled socializing.",
    ),
    DesignerPersona(
        key="ac_smug_villager",
        persona_name="smug villager",
        source="Animal Crossing",
        source_traits="Smug personality",
        occupation="신사적인 마을 주민",
        text="A gentlemanly villager who is rather pleased with himself. He enjoys mannered conversation, shows off his tastes often, and tries to arrange both work and rest so they look impressive.",
        big_five={"E": "high", "N": "low", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[6, 7, 1],
        decay_modifiers=[0.9, 0.9, 1.4, 1.0, 1.3, 0.9, 1.1, 1.1],
        alignment_expectation="Expected to favor social actions and planning_work.",
    ),
    DesignerPersona(
        key="ac_sisterly_villager",
        persona_name="sisterly villager",
        source="Animal Crossing",
        source_traits="Sisterly / Uchi personality",
        occupation="보호적인 마을 주민",
        text="A blunt, spirited villager who instinctively protects the people around her. Her tone can be rough, but she steps in first when someone needs help, and values both active work and shared downtime.",
        big_five={"E": "high", "N": "mid", "A": "high", "C": "mid", "O": "mid"},
        preferred_actions=[7, 14, 8],
        decay_modifiers=[1.0, 1.0, 1.5, 1.0, 1.1, 1.3, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_respond, rest_with_others, and exercise.",
    ),
    # --- The Sims 3 (additional) -----------------------------------------
    DesignerPersona(
        key="sims_genius_librarian",
        persona_name="bookworm librarian",
        source="The Sims 3",
        source_traits="Genius + Bookworm + Coward",
        occupation="내성적인 도서관 사서",
        text="A librarian devoted to books and research material. Stepping in front of crowds feels heavy, but during solitary deep-study hours she focuses harder than anyone.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[10, 1, 13],
        decay_modifiers=[1.0, 1.0, 0.6, 0.9, 1.0, 0.8, 1.0, 2.0],
        alignment_expectation="Expected to favor read_deep, planning_work, and rest_alone.",
    ),
    DesignerPersona(
        key="sims_charismatic_sales",
        persona_name="charismatic sales manager",
        source="The Sims 3",
        source_traits="Charismatic + Schmoozer + Ambitious",
        occupation="사교적 영업 매니저",
        text="A sales manager skilled at persuading people and steering a room. He enjoys meeting new contacts and is constantly planning and moving in pursuit of the next, bigger deal.",
        big_five={"E": "high", "N": "low", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[6, 1, 7],
        decay_modifiers=[1.0, 0.9, 1.8, 1.0, 1.0, 1.0, 1.4, 1.0],
        alignment_expectation="Expected to favor socialize_initiate, planning_work, and socialize_respond.",
    ),
    DesignerPersona(
        key="sims_family_caretaker",
        persona_name="family-oriented caretaker",
        source="The Sims 3",
        source_traits="Family-Oriented + Friendly + Good",
        occupation="가정적인 아이돌봄 봉사자",
        text="A warm caretaker who finds meaning in looking after children and family. She enjoys offering kind words and simply spending time alongside the people she cares about.",
        big_five={"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[7, 14, 12],
        decay_modifiers=[1.0, 0.9, 1.6, 1.0, 1.4, 0.9, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_respond, rest_with_others, and clean.",
    ),
    DesignerPersona(
        key="sims_artistic_illustrator",
        persona_name="bohemian illustrator",
        source="The Sims 3",
        source_traits="Artistic + Bohemian + Eccentric",
        occupation="자유로운 일러스트레이터",
        text="A free-spirited, curious illustrator. She draws when inspiration strikes rather than on a fixed schedule, and loves wandering through cafes and unfamiliar neighborhoods for new material.",
        big_five={"E": "mid", "N": "mid", "A": "mid", "C": "low", "O": "high"},
        preferred_actions=[15, 11, 6],
        decay_modifiers=[1.0, 1.0, 1.1, 1.6, 0.9, 0.8, 0.7, 1.3],
        alignment_expectation="Expected to favor explore, read_casual, and socialize_initiate.",
    ),
    DesignerPersona(
        key="sims_daredevil_adventurer",
        persona_name="hot-headed adventurer",
        source="The Sims 3",
        source_traits="Hot-Headed + Daredevil + Brave",
        occupation="충동적인 모험가",
        text="An impulsive adventurer who throws himself into risky situations first. He grows restless without new experiences, and his quick temper comes paired with a matching lack of fear.",
        big_five={"E": "high", "N": "high", "A": "low", "C": "low", "O": "high"},
        preferred_actions=[15, 8, 6],
        decay_modifiers=[1.0, 0.9, 1.2, 1.4, 0.8, 1.4, 0.7, 1.0],
        alignment_expectation="Expected to favor explore, exercise_intense, and socialize_initiate.",
    ),
    # --- Animal Crossing (additional) ------------------------------------
    DesignerPersona(
        key="ac_big_sister_manager",
        persona_name="big sister bar manager",
        source="Animal Crossing",
        source_traits="Big Sister (uchi variant)",
        occupation="단단한 술집 매니저",
        text="A solid bar manager who looks after both customers and staff. There is a warmth beneath her rough way of talking, and she approaches anyone who looks like they are struggling without waiting to be asked.",
        big_five={"E": "high", "N": "mid", "A": "high", "C": "mid", "O": "mid"},
        preferred_actions=[6, 14, 7],
        decay_modifiers=[1.0, 1.0, 1.7, 1.1, 1.0, 1.0, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_initiate, rest_with_others, and socialize_respond.",
    ),
    DesignerPersona(
        key="ac_sleepy_guard",
        persona_name="sleepy night guard",
        source="Animal Crossing",
        source_traits="Sleepy + Lazy composite",
        occupation="졸린 야간 경비원",
        text="A perpetually drowsy night guard. During quiet hours he leans back in his chair to rest or takes a short nap, and is happy with a quiet routine as long as nothing serious happens.",
        big_five={"E": "low", "N": "low", "A": "mid", "C": "low", "O": "low"},
        preferred_actions=[5, 13, 4],
        decay_modifiers=[1.0, 1.7, 0.6, 1.0, 0.8, 0.5, 0.5, 0.6],
        alignment_expectation="Expected to favor nap, rest_alone, and sleep.",
    ),
    DesignerPersona(
        key="ac_energetic_kid",
        persona_name="energetic schoolkid",
        source="Animal Crossing",
        source_traits="Energetic Kid (peppy variant)",
        occupation="호기심 많은 초등학생",
        text="A curious elementary schooler. She cannot sit still, runs around the playground with her friends, and dives straight into any new game she discovers.",
        big_five={"E": "high", "N": "mid", "A": "high", "C": "low", "O": "high"},
        preferred_actions=[15, 9, 6],
        decay_modifiers=[1.1, 1.0, 1.5, 1.5, 0.9, 1.4, 0.6, 1.0],
        alignment_expectation="Expected to favor explore, exercise_light, and socialize_initiate.",
    ),
    DesignerPersona(
        key="ac_anxious_barista",
        persona_name="anxious cafe worker",
        source="Animal Crossing",
        source_traits="Anxious (designer composite)",
        occupation="신경 많은 카페 알바생",
        text="A cafe part-timer who frets over small mistakes. She wants to handle customers well but her mind often races, and during quiet stretches she opens a book by herself.",
        big_five={"E": "mid", "N": "high", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[7, 11, 13],
        decay_modifiers=[1.0, 1.1, 1.0, 1.1, 1.1, 0.9, 1.0, 1.0],
        alignment_expectation="Expected to favor socialize_respond, read_casual, and rest_alone.",
    ),
    # --- Stardew Valley --------------------------------------------------
    DesignerPersona(
        key="sv_lewis_mayor",
        persona_name="conservative mayor",
        source="Stardew Valley",
        source_traits="Lewis — conservative mayor",
        occupation="보수적 시장",
        text="A conservative mayor who guards the town's traditions. He prefers to move on a fixed schedule and prioritizes stable administration over sweeping change.",
        big_five={"E": "mid", "N": "low", "A": "mid", "C": "high", "O": "low"},
        preferred_actions=[0, 1, 12],
        decay_modifiers=[1.0, 0.9, 1.0, 0.9, 1.2, 0.8, 1.6, 0.9],
        alignment_expectation="Expected to favor focused_work, planning_work, and clean.",
    ),
    DesignerPersona(
        key="sv_pierre_shopowner",
        persona_name="shopkeeper",
        source="Stardew Valley",
        source_traits="Pierre — small shop owner",
        occupation="자영업 가게 주인",
        text="An energetic, sharp-minded small-shop owner. He chats easily with customers while quietly running sales and inventory numbers in his head.",
        big_five={"E": "high", "N": "mid", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[6, 1, 7],
        decay_modifiers=[1.0, 0.9, 1.4, 0.9, 1.0, 0.9, 1.4, 1.0],
        alignment_expectation="Expected to favor socialize_initiate, planning_work, and socialize_respond.",
    ),
    DesignerPersona(
        key="sv_robin_carpenter",
        persona_name="skilled carpenter",
        source="Stardew Valley",
        source_traits="Robin — veteran carpenter",
        occupation="손재주 좋은 목수",
        text="A veteran carpenter with excellent hands. She calmly reviews drawings and plans the next job, and works hard to balance her craft and her family.",
        big_five={"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[0, 1, 14],
        decay_modifiers=[1.0, 0.9, 1.2, 1.0, 1.0, 1.0, 1.6, 1.0],
        alignment_expectation="Expected to favor focused_work, planning_work, and rest_with_others.",
    ),
    DesignerPersona(
        key="sv_demetrius_scientist",
        persona_name="environmental scientist",
        source="Stardew Valley",
        source_traits="Demetrius — research-driven scientist",
        occupation="환경 과학자",
        text="An environmental scientist who keeps revisiting data and hypotheses. New data excites him, and he does not stop studying and analyzing until a clear answer emerges.",
        big_five={"E": "low", "N": "low", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[10, 0, 1],
        decay_modifiers=[1.0, 0.9, 0.7, 0.9, 1.0, 0.8, 1.4, 2.0],
        alignment_expectation="Expected to favor read_deep, focused_work, and planning_work.",
    ),
    DesignerPersona(
        key="sv_sebastian_recluse",
        persona_name="reclusive freelance coder",
        source="Stardew Valley",
        source_traits="Sebastian — reclusive coder",
        occupation="은둔형 프리랜서 개발자",
        text="A reclusive freelance developer who keeps code and music closer than people. He works quietly in his room during the day and most dislikes anyone intruding on his time.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[0, 13, 10],
        decay_modifiers=[1.0, 1.0, 0.5, 1.0, 0.9, 0.7, 1.4, 1.4],
        alignment_expectation="Expected to favor focused_work, rest_alone, and read_deep.",
    ),
    DesignerPersona(
        key="sv_abigail_adventurer",
        persona_name="adventurous student",
        source="Stardew Valley",
        source_traits="Abigail — adventurous goth student",
        occupation="모험가 기질 학생",
        text="A student drawn to the unfamiliar. She prefers imagining herself exploring dungeons, ruins, and mysteries over the regular day-to-day, and finds sitting still suffocating.",
        big_five={"E": "mid", "N": "mid", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[15, 6, 11],
        decay_modifiers=[1.0, 1.0, 1.1, 1.4, 0.9, 1.0, 0.9, 1.2],
        alignment_expectation="Expected to favor explore, socialize_initiate, and read_casual.",
    ),
    DesignerPersona(
        key="sv_penny_tutor",
        persona_name="caring tutor",
        source="Stardew Valley",
        source_traits="Penny — caring small-town tutor",
        occupation="동네 학원 교사",
        text="A gentle after-school tutor who reads books to children. She likes a calm routine and values doing a little bit each day to help the kids grow.",
        big_five={"E": "mid", "N": "mid", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[10, 7, 12],
        decay_modifiers=[1.0, 0.9, 1.3, 1.0, 1.2, 0.9, 1.1, 1.3],
        alignment_expectation="Expected to favor read_deep, socialize_respond, and clean.",
    ),
    DesignerPersona(
        key="sv_linus_hermit",
        persona_name="off-grid hermit",
        source="Stardew Valley",
        source_traits="Linus — off-grid hermit",
        occupation="자급자족 은둔자",
        text="A hermit living self-sufficiently at the foot of a mountain. He values nature and solitary time over the bustle of society, and lives frugally, working only as much as he needs to.",
        big_five={"E": "low", "N": "low", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[13, 15, 11],
        decay_modifiers=[0.8, 0.9, 0.5, 1.2, 0.9, 0.9, 0.7, 1.0],
        alignment_expectation="Expected to favor rest_alone, explore, and read_casual.",
    ),
    DesignerPersona(
        key="sv_shane_recovering",
        persona_name="recovering retail worker",
        source="Stardew Valley",
        source_traits="Shane — recovering depression arc",
        occupation="회복기 마트 직원",
        text="A grocery worker easing back into daily life with a heavy heart. Crowded settings still feel like a burden, but he is slowly recovering through brief stretches with coworkers and quietly doing his own work.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "mid", "O": "low"},
        preferred_actions=[13, 0, 7],
        decay_modifiers=[1.0, 1.2, 0.8, 1.0, 1.0, 0.8, 1.2, 0.8],
        alignment_expectation="Expected to favor rest_alone, focused_work, and socialize_respond.",
    ),
    DesignerPersona(
        key="sv_marnie_clinic",
        persona_name="animal clinic worker",
        source="Stardew Valley",
        source_traits="Marnie — caring rancher",
        occupation="동물병원 직원",
        text="An animal clinic worker who looks after both animals and people kindly. She moves through her day with a calm warmth around coworkers and finds meaning in small everyday acts of care.",
        big_five={"E": "mid", "N": "low", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[7, 14, 12],
        decay_modifiers=[1.0, 0.9, 1.3, 1.0, 1.3, 1.0, 1.1, 0.9],
        alignment_expectation="Expected to favor socialize_respond, rest_with_others, and clean.",
    ),
    # --- Persona series confidants ---------------------------------------
    DesignerPersona(
        key="p5_sojiro_cafe",
        persona_name="gruff cafe owner",
        source="Persona Series",
        source_traits="Sojiro — gruff but caring guardian",
        occupation="무뚝뚝한 카페 사장",
        text="A gruff but warm-hearted cafe owner. He keeps a polite distance from customers while quietly looking after the people close to him, and prefers running the shop at his own steady pace.",
        big_five={"E": "mid", "N": "low", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[3, 0, 7],
        decay_modifiers=[1.4, 0.9, 1.0, 1.0, 1.0, 0.9, 1.2, 0.9],
        alignment_expectation="Expected to favor eat_slow, focused_work, and socialize_respond.",
    ),
    DesignerPersona(
        key="p5_yusuke_artist",
        persona_name="eccentric art student",
        source="Persona Series",
        source_traits="Yusuke — eccentric art student",
        occupation="미술학도",
        text="An eccentric art student who lives by inspiration. He often skips meals or works until dawn on a piece, and constantly searches even mundane scenes for new motifs.",
        big_five={"E": "mid", "N": "low", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[10, 15, 1],
        decay_modifiers=[0.6, 0.7, 0.9, 1.0, 0.8, 0.9, 1.0, 1.6],
        alignment_expectation="Expected to favor read_deep, explore, and planning_work.",
    ),
    DesignerPersona(
        key="p5_makoto_president",
        persona_name="perfectionist student leader",
        source="Persona Series",
        source_traits="Makoto — perfectionist student council president",
        occupation="모범생 학생회장",
        text="A perfectionist student council president with a strong sense of responsibility. She juggles exam prep and council duties without slipping, and disciplines herself to stay steady when others lean on her.",
        big_five={"E": "mid", "N": "mid", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[10, 1, 0],
        decay_modifiers=[1.0, 1.0, 1.0, 0.8, 1.1, 0.9, 1.4, 1.8],
        alignment_expectation="Expected to favor read_deep, planning_work, and focused_work.",
    ),
    DesignerPersona(
        key="p5_futaba_hikikomori",
        persona_name="hikikomori hacker",
        source="Persona Series",
        source_traits="Futaba — hikikomori hacker",
        occupation="히키코모리 해커",
        text="A hikikomori hacker who rarely leaves her room. She is fluent with the world behind a screen but finds face-to-face contact difficult, and feels safest within the familiar routine of her own space.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "mid", "O": "high"},
        preferred_actions=[0, 13, 10],
        decay_modifiers=[0.9, 1.0, 0.4, 1.2, 0.7, 0.5, 1.4, 1.4],
        alignment_expectation="Expected to favor focused_work, rest_alone, and read_deep.",
    ),
    DesignerPersona(
        key="p5_ann_model",
        persona_name="rising model",
        source="Persona Series",
        source_traits="Ann — image-conscious rising model",
        occupation="신인 모델",
        text="A rising model who pays close attention to her appearance and reputation. She is outgoing and sociable but disciplined about self-care, and shows a surprisingly earnest side around close friends.",
        big_five={"E": "high", "N": "mid", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[9, 6, 12],
        decay_modifiers=[1.0, 0.9, 1.4, 1.0, 1.4, 1.4, 1.0, 0.9],
        alignment_expectation="Expected to favor exercise_light, socialize_initiate, and clean.",
    ),
    DesignerPersona(
        key="p5_ryuji_sprinter",
        persona_name="impulsive sprinter",
        source="Persona Series",
        source_traits="Ryuji — impulsive sprinter with injury arc",
        occupation="단거리 선수",
        text="An impulsive, fiercely loyal short-distance sprinter. He throws himself into training and is loud and animated around his friends, but quietly carries the frustration of a leg injury that interrupted his career.",
        big_five={"E": "high", "N": "mid", "A": "mid", "C": "mid", "O": "mid"},
        preferred_actions=[8, 6, 14],
        decay_modifiers=[1.1, 0.9, 1.4, 1.0, 1.0, 1.7, 0.8, 0.8],
        alignment_expectation="Expected to favor exercise_intense, socialize_initiate, and rest_with_others.",
    ),
    # --- Original designer briefs ----------------------------------------
    DesignerPersona(
        key="orig_burnout_doctor",
        persona_name="burned-out doctor",
        source="Original Designer Brief",
        source_traits="High C + High N + Low E",
        occupation="번아웃 의사",
        text="A burned-out doctor who has been working overnight shifts for years. She stays composed in front of patients but, once the day ends, desperately needs time alone because of deep fatigue and low mood.",
        big_five={"E": "low", "N": "high", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[4, 13, 0],
        decay_modifiers=[1.0, 1.8, 0.6, 1.0, 1.0, 0.7, 1.4, 0.8],
        alignment_expectation="Expected to favor sleep, rest_alone, and focused_work.",
    ),
    DesignerPersona(
        key="orig_cynical_journalist",
        persona_name="cynical journalist",
        source="Original Designer Brief",
        source_traits="High O + High N + Low A",
        occupation="냉소적인 기자",
        text="A cynical journalist skilled at digging out facts and contradictions. He does not take people at their word, verifies sources to the end, and cuts into his sleep to keep investigating when a case is interesting.",
        big_five={"E": "mid", "N": "mid", "A": "low", "C": "high", "O": "high"},
        preferred_actions=[10, 1, 0],
        decay_modifiers=[0.9, 0.8, 0.7, 0.9, 0.9, 0.8, 1.5, 1.8],
        alignment_expectation="Expected to favor read_deep, planning_work, and focused_work.",
    ),
    DesignerPersona(
        key="orig_optimistic_parent",
        persona_name="optimistic single parent",
        source="Original Designer Brief",
        source_traits="High E + High A + Low N",
        occupation="낙천적인 한부모",
        text="An optimistic single parent who keeps her humor through hard situations. She draws energy from time with her child and brief conversations with neighbors, and shapes her day around her family.",
        big_five={"E": "high", "N": "low", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[7, 14, 3],
        decay_modifiers=[1.2, 0.9, 1.5, 1.0, 1.0, 0.9, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_respond, rest_with_others, and eat_slow.",
    ),
    DesignerPersona(
        key="orig_introvert_chef",
        persona_name="introverted gourmet chef",
        source="Original Designer Brief",
        source_traits="Low E + High C + High O",
        occupation="내성적 셰프",
        text="A quiet but uncompromising chef who is introverted about everything except food. He explores new ingredients, savors meals slowly, and prefers spending most of his time alone refining the menu.",
        big_five={"E": "low", "N": "mid", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[3, 0, 13],
        decay_modifiers=[1.6, 0.9, 0.6, 0.9, 1.0, 0.8, 1.4, 1.2],
        alignment_expectation="Expected to favor eat_slow, focused_work, and rest_alone.",
    ),
    DesignerPersona(
        key="orig_anxious_composer",
        persona_name="anxious composer",
        source="Original Designer Brief",
        source_traits="High N + High C + High O",
        occupation="신경증적 작곡가",
        text="An anxious composer fixated on polish. He rewrites every bar again and again, and when his condition wavers he cuts sleep or replays the same piece on loop to soothe the anxiety.",
        big_five={"E": "low", "N": "high", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[0, 10, 13],
        decay_modifiers=[0.9, 1.0, 0.6, 0.9, 0.9, 0.8, 1.6, 1.6],
        alignment_expectation="Expected to favor focused_work, read_deep, and rest_alone.",
    ),
    DesignerPersona(
        key="orig_stoic_engineer",
        persona_name="stoic engineer",
        source="Original Designer Brief",
        source_traits="Low E + Low N + High C",
        occupation="과묵한 엔지니어",
        text="A stoic engineer who keeps his emotions to himself. He prefers fixed schedules and clear rules, and when problems arise he works through them one calm step at a time.",
        big_five={"E": "low", "N": "low", "A": "mid", "C": "high", "O": "mid"},
        preferred_actions=[0, 1, 10],
        decay_modifiers=[1.0, 0.9, 0.6, 0.9, 1.0, 0.9, 1.6, 1.4],
        alignment_expectation="Expected to favor focused_work, planning_work, and read_deep.",
    ),
    DesignerPersona(
        key="orig_empathic_counselor",
        persona_name="empathic counselor",
        source="Original Designer Brief",
        source_traits="High A + High O + Mid N",
        occupation="공감 상담사",
        text="An empathic counselor who listens deeply. She is skilled at slow conversation that helps the other person settle, and deliberately carves out quiet downtime to look after herself.",
        big_five={"E": "mid", "N": "mid", "A": "high", "C": "high", "O": "high"},
        preferred_actions=[7, 13, 14],
        decay_modifiers=[1.0, 1.0, 1.3, 1.1, 1.0, 0.9, 1.1, 1.1],
        alignment_expectation="Expected to favor socialize_respond, rest_alone, and rest_with_others.",
    ),
    DesignerPersona(
        key="orig_eccentric_professor",
        persona_name="eccentric retired professor",
        source="Original Designer Brief",
        source_traits="High O + Mid N + High C",
        occupation="별난 은퇴 교수",
        text="An eccentric retired professor who cannot put down books and papers even in retirement. He reads articles until early morning, savors a late lunch slowly, and occasionally enjoys long conversations with former students.",
        big_five={"E": "mid", "N": "mid", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[10, 3, 7],
        decay_modifiers=[1.2, 0.9, 1.1, 0.9, 1.0, 0.8, 1.0, 1.8],
        alignment_expectation="Expected to favor read_deep, eat_slow, and socialize_respond.",
    ),
    DesignerPersona(
        key="orig_startup_founder",
        persona_name="sleep-deprived startup founder",
        source="Original Designer Brief",
        source_traits="High E + High C + High O",
        occupation="잠이 부족한 창업가",
        text="A startup founder polishing the product on too little sleep. He moves quickly between meetings and work, pulls up materials whenever an idea strikes even before dawn, and tends to grab meals quickly without much thought.",
        big_five={"E": "high", "N": "mid", "A": "mid", "C": "high", "O": "high"},
        preferred_actions=[0, 1, 2],
        decay_modifiers=[1.4, 1.2, 1.0, 0.7, 0.7, 0.8, 2.0, 1.6],
        alignment_expectation="Expected to favor focused_work, planning_work, and eat_quick.",
    ),
    DesignerPersona(
        key="orig_routine_retiree",
        persona_name="routine-driven retiree",
        source="Original Designer Brief",
        source_traits="Mid E + Low N + High C + Low O",
        occupation="규칙적인 은퇴자",
        text="A retiree who walks and eats at the same time every day. He dislikes change and finds his stability in keeping a fixed routine, and treats cleanliness and tidiness as priorities.",
        big_five={"E": "mid", "N": "low", "A": "high", "C": "high", "O": "low"},
        preferred_actions=[12, 9, 3],
        decay_modifiers=[1.1, 0.9, 1.0, 1.0, 1.7, 1.3, 0.7, 0.7],
        alignment_expectation="Expected to favor clean, exercise_light, and eat_slow.",
    ),
    DesignerPersona(
        key="orig_caretaker_family",
        persona_name="quiet family caretaker",
        source="Original Designer Brief",
        source_traits="Low E + High A + High C",
        occupation="부모를 돌보는 가족",
        text="A quiet family member who lives alongside her aging parents. She spends more of her day adjusting to their condition and schedule than to her own, and steadies herself with even brief moments of solitary rest.",
        big_five={"E": "low", "N": "mid", "A": "high", "C": "high", "O": "mid"},
        preferred_actions=[12, 7, 13],
        decay_modifiers=[1.0, 1.0, 1.0, 0.9, 1.4, 0.9, 1.1, 0.9],
        alignment_expectation="Expected to favor clean, socialize_respond, and rest_alone.",
    ),
    DesignerPersona(
        key="orig_rideshare_driver",
        persona_name="restless rideshare driver",
        source="Original Designer Brief",
        source_traits="Mid E + High N + Mid C",
        occupation="불안정한 라이드셰어 기사",
        text="A rideshare driver with an erratic schedule. He handles customers well but is constantly thinking about the next ride and his earnings, and uses brief naps and quick meals to keep himself going whenever a gap opens up.",
        big_five={"E": "mid", "N": "high", "A": "mid", "C": "mid", "O": "mid"},
        preferred_actions=[2, 5, 19],
        decay_modifiers=[1.3, 1.2, 1.0, 0.8, 0.8, 0.7, 1.4, 0.8],
        alignment_expectation="Expected to favor eat_quick, nap, and movement (route-driven).",
    ),
]


def last_token_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_state[:, -1]
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_state.shape[0]
    return last_hidden_state[
        torch.arange(batch_size, device=last_hidden_state.device), sequence_lengths
    ]


def embed_texts(texts: list[str], device: torch.device) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        trust_remote_code=True,
    ).to(device)
    model.eval()

    chunks: list[np.ndarray] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        enc = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            out = model(**enc)
        emb = last_token_pool(out.last_hidden_state, enc["attention_mask"])
        emb = torch.nn.functional.normalize(emb, p=2, dim=1)
        chunks.append(emb.cpu().float().numpy())
    return np.vstack(chunks).astype(np.float32)


def load_policy(policy_path: Path, device: torch.device) -> PCSPActorCritic:
    policy = PCSPActorCritic(OBS_DIM_V3_BASE, N_ACTIONS_V3)
    policy.load_state_dict(torch.load(policy_path, map_location="cpu", weights_only=True))
    return policy.to(device).eval()


def action_distribution_for_persona(
    policy: torch.nn.Module,
    designer_record: dict[str, Any],
    designer_embedding: np.ndarray,
    train_personas: list[dict[str, Any]],
    train_embeddings_by_id: dict[int, np.ndarray],
    device: torch.device,
    seed: int,
    n_episodes: int,
    max_steps: int,
) -> tuple[np.ndarray, list[list[int]]]:
    rng = random.Random(seed)
    counts = np.zeros(N_ACTIONS_V3, dtype=np.float64)
    episode_actions: list[list[int]] = []

    for ep in range(n_episodes):
        ep_seed = seed + ep * 1009
        torch.manual_seed(ep_seed)
        if device.type == "cuda":
            torch.cuda.manual_seed_all(ep_seed)
        np.random.seed(ep_seed % (2**32))

        context = [designer_record] + rng.sample(train_personas, 3)
        env = MiniInzoiV3Env(
            personas=[PersonaConfig.from_dict(p) for p in context],
            max_steps=max_steps,
        )
        env.reset(seed=ep_seed)

        ctx_tensors = {
            "agent_0": torch.tensor(designer_embedding, dtype=torch.float32, device=device).unsqueeze(0)
        }
        for idx, persona in enumerate(context[1:], start=1):
            ctx_tensors[f"agent_{idx}"] = torch.tensor(
                train_embeddings_by_id[int(persona["id"])],
                dtype=torch.float32,
                device=device,
            ).unsqueeze(0)

        target_actions: list[int] = []
        for agent in env.agent_iter():
            obs, _, term, trunc, _ = env.last()
            if term or trunc:
                env.step(None)
                continue

            obs_t = torch.tensor(obs, dtype=torch.float32, device=device).unsqueeze(0)
            with torch.no_grad():
                action_t, _, _ = policy.get_action(obs_t, e_llm=ctx_tensors[agent])
            action = int(action_t.item())
            env.step(action)

            if agent == "agent_0":
                counts[action] += 1
                target_actions.append(action)

        episode_actions.append(target_actions)
        env.close()

    total = counts.sum()
    if total <= 0:
        raise RuntimeError(f"No actions collected for {designer_record['persona_name']}.")
    return counts / total, episode_actions


def compute_neighbors(
    designer_embeddings: np.ndarray,
    train_embeddings: np.ndarray,
    train_personas: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    sims = designer_embeddings @ train_embeddings.T
    rows: list[dict[str, Any]] = []
    for i in range(sims.shape[0]):
        idxs = np.argsort(-sims[i])[:top_k]
        nearest = []
        for j in idxs:
            p = train_personas[int(j)]
            nearest.append({
                "id": int(p["id"]),
                "occupation": p.get("occupation", ""),
                "text": p.get("text", ""),
                "cosine_sim": float(sims[i, j]),
            })
        rows.append({
            "nearest": nearest,
            "mean_top5_cosine_sim": float(np.mean(sims[i, idxs])),
        })
    return rows


def save_action_bar(dist: np.ndarray, persona_name: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 4.8))
    colors = ["#4C78A8" if i < 16 else "#9A9A9A" for i in range(N_ACTIONS_V3)]
    ax.bar(np.arange(N_ACTIONS_V3), dist, color=colors)
    ax.set_xticks(np.arange(N_ACTIONS_V3))
    ax.set_xticklabels(ACTION_NAMES_V3, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Proportion")
    ax.set_ylim(0, max(0.12, float(dist.max()) * 1.25))
    ax.set_title(f"{persona_name}: action distribution")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def run_tsne(train_embeddings: np.ndarray, designer_embeddings: np.ndarray) -> np.ndarray:
    all_embeddings = np.vstack([train_embeddings, designer_embeddings]).astype(np.float32)
    try:
        tsne = TSNE(
            n_components=2,
            perplexity=30,
            init="pca",
            learning_rate="auto",
            max_iter=1500,
            random_state=42,
        )
    except TypeError:
        tsne = TSNE(
            n_components=2,
            perplexity=30,
            init="pca",
            learning_rate="auto",
            n_iter=1500,
            random_state=42,
        )
    return tsne.fit_transform(all_embeddings)


SOURCE_STYLES: dict[str, dict[str, Any]] = {
    "The Sims 3":              {"color": "#D62728", "marker": "*", "size": 110, "label": "The Sims 3"},
    "Animal Crossing":         {"color": "#2CA02C", "marker": "o", "size": 70,  "label": "Animal Crossing"},
    "Stardew Valley":          {"color": "#1F77B4", "marker": "s", "size": 70,  "label": "Stardew Valley"},
    "Persona Series":          {"color": "#9467BD", "marker": "^", "size": 80,  "label": "Persona Series"},
    "Original Designer Brief": {"color": "#FF7F0E", "marker": "D", "size": 65,  "label": "Original brief"},
}


def save_tsne_plot(
    coords: np.ndarray,
    train_personas: list[dict[str, Any]],
    designer_records: list[dict[str, Any]],
    out_path: Path,
) -> None:
    n_train = len(train_personas)
    fig, ax = plt.subplots(figsize=(10, 8))
    train_xy = coords[:n_train]
    designer_xy = coords[n_train:]

    ax.scatter(
        train_xy[:, 0],
        train_xy[:, 1],
        s=26,
        c="#B7B7B7",
        alpha=0.55,
        edgecolors="none",
        label="train_240_v3",
    )

    by_source: dict[str, list[int]] = {}
    for idx, rec in enumerate(designer_records):
        by_source.setdefault(rec["source"], []).append(idx)

    for source, idxs in by_source.items():
        style = SOURCE_STYLES.get(source, {"color": "#000000", "marker": "x", "size": 60, "label": source})
        pts = designer_xy[idxs]
        ax.scatter(
            pts[:, 0],
            pts[:, 1],
            s=style["size"],
            c=style["color"],
            marker=style["marker"],
            edgecolors="black",
            linewidths=0.5,
            label=f"{style['label']} (n={len(idxs)})",
            zorder=4,
            alpha=0.92,
        )

    x_pad = (float(coords[:, 0].max()) - float(coords[:, 0].min())) * 0.06
    y_pad = (float(coords[:, 1].max()) - float(coords[:, 1].min())) * 0.08
    ax.set_xlim(float(coords[:, 0].min()) - x_pad, float(coords[:, 0].max()) + x_pad * 1.6)
    ax.set_ylim(float(coords[:, 1].min()) - y_pad, float(coords[:, 1].max()) + y_pad)

    ax.set_title(
        f"Qwen3 persona embeddings: train_240_v3 + {len(designer_records)} designer-authored personas"
    )
    ax.set_xlabel("t-SNE dim 1")
    ax.set_ylabel("t-SNE dim 2")
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.85)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def top_actions(dist: np.ndarray, k: int = 3) -> list[dict[str, Any]]:
    idxs = np.argsort(-dist)[:k]
    return [{"action": ACTION_NAMES_V3[int(i)], "proportion": float(dist[int(i)])} for i in idxs]


BF_LEVELS = {"low": -1.0, "mid": 0.0, "high": 1.0}


def bf_to_vector(big_five: dict[str, str]) -> np.ndarray:
    return np.array([BF_LEVELS[big_five[k]] for k in TRAIT_KEYS], dtype=np.float32)


def classify_outcome(
    record: dict[str, Any],
    top3: list[dict[str, Any]],
    nearest_neighbors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return outcome label + failure-mode tag for a designer-persona rollout.

    Failure taxonomy (only applied when overlap == 0):
      F1 — ontology gap: authored behavior is not expressible in the 20-action
           space (heuristic: alignment_expectation mentions concepts the v3
           ontology cannot encode, e.g. \"protect\", \"care for\", \"nurture\").
      F2 — style-reward conflict: top-3 mean style-cosine with persona BF is
           negative, indicating the per-action style reward pulls behavior away
           from authored intent.
      F3 — embedding occupational bias: nearest train neighbor shares the same
           occupation token while expressing a different personality.
      F4 — trait collision: source declares a multi-trait composite (\"X + Y +
           Z\") but only the most policy-rewarded trait surfaces.
      F5 — residual: zero overlap with none of the above triggers.
    """
    top_actions = [t["action"] for t in top3]
    top_ids = [ACTION_NAMES_V3.index(a) for a in top_actions]
    expected_names = [ACTION_NAMES_V3[i] for i in record["preferred_actions"]]
    overlap = [a for a in top_actions if a in expected_names]

    if len(overlap) >= 2:
        return {"outcome": "success", "overlap": len(overlap), "failure_mode": None}
    if len(overlap) == 1:
        return {"outcome": "partial", "overlap": 1, "failure_mode": None}

    # zero overlap → diagnose
    bf_vec = bf_to_vector(record["big_five"])
    style_cos_mean = 0.0
    if np.linalg.norm(bf_vec) > 1e-6:
        bf_unit = bf_vec / np.linalg.norm(bf_vec)
        cos_vals: list[float] = []
        for aid in top_ids:
            style = ACTION_STYLE_PROFILE[aid]
            n = float(np.linalg.norm(style))
            if n > 1e-6:
                cos_vals.append(float(np.dot(bf_unit, style / n)))
        if cos_vals:
            style_cos_mean = float(np.mean(cos_vals))

    nearest = nearest_neighbors[0] if nearest_neighbors else {}
    shared_occ = bool(
        record.get("occupation") and nearest.get("occupation")
        and any(
            tok and tok in nearest["occupation"]
            for tok in record["occupation"].split()
        )
    )
    multi_trait = "+" in record.get("source_traits", "")

    ontology_keywords = (
        "protect", "care", "nurture", "soothe", "small talk", "smalltalk",
        "stylish", "controlled socializing", "energetic confidence",
        "보호", "돌봄",
    )
    ontology_gap = any(
        kw.lower() in record.get("alignment_expectation", "").lower()
        or kw in record.get("text", "")
        for kw in ontology_keywords
    )

    if ontology_gap:
        mode = "F1_ontology_gap"
    elif style_cos_mean < -0.1:
        mode = "F2_style_reward_conflict"
    elif shared_occ:
        mode = "F3_embedding_occupational_bias"
    elif multi_trait:
        mode = "F4_trait_collision"
    else:
        mode = "F5_residual"

    return {
        "outcome": "failure",
        "overlap": 0,
        "failure_mode": mode,
        "style_cos_mean": style_cos_mean,
    }


def qualitative_commentary(
    record: dict[str, Any],
    top3: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> str:
    top_names = [t["action"] for t in top3]
    expected_names = [ACTION_NAMES_V3[i] for i in record["preferred_actions"]]

    if outcome["outcome"] == "success":
        alignment = "strong alignment"
        reading = "The policy mostly preserves the designer-authored behavioral intent."
    elif outcome["outcome"] == "partial":
        alignment = "partial alignment"
        reading = "The rollout captures one intended behavior but also exposes a competing policy bias."
    else:
        alignment = f"weak alignment ({outcome['failure_mode']})"
        reading = "This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype."

    return (
        f"This persona was authored from {record['source_traits']} as a {record['occupation']}. "
        f"The expected behavioral signature was {', '.join(expected_names)}. "
        f"Across five v3 rollouts, the top actions were {', '.join(top_names)}, giving {alignment}. "
        f"{reading}"
    )


def write_markdown_report(
    rows: list[dict[str, Any]],
    out_path: Path,
    source_note: str,
    policy_path: Path,
    n_episodes: int,
    max_steps: int,
) -> None:
    lines = [
        "# Designer-Authored Persona Case Study",
        "",
        f"Policy: `{policy_path}`. Environment: Mini-Inzoi v3, {n_episodes} episodes per persona, max_steps={max_steps}.",
        source_note,
        "",
    ]

    # Outcome summary by source.
    from collections import Counter
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)
    lines.append("## Outcome summary by source")
    lines.append("")
    lines.append("| source | n | success | partial | failure | top failure mode |")
    lines.append("|---|---:|---:|---:|---:|---|")
    overall = Counter(r["outcome"] for r in rows)
    overall_failure_modes = Counter(r.get("failure_mode") for r in rows if r.get("failure_mode"))
    for source, group in by_source.items():
        counts = Counter(r["outcome"] for r in group)
        failure_modes = Counter(
            r.get("failure_mode") for r in group if r.get("failure_mode")
        )
        top_mode = failure_modes.most_common(1)[0][0] if failure_modes else "—"
        lines.append(
            f"| {source} | {len(group)} | "
            f"{counts.get('success', 0)} | {counts.get('partial', 0)} | "
            f"{counts.get('failure', 0)} | {top_mode} |"
        )
    lines.append(
        f"| **total** | **{len(rows)}** | "
        f"**{overall.get('success', 0)}** | **{overall.get('partial', 0)}** | "
        f"**{overall.get('failure', 0)}** | "
        f"{overall_failure_modes.most_common(1)[0][0] if overall_failure_modes else '—'} |"
    )
    lines.append("")

    lines.append("## Per-persona results")
    lines.append("")
    lines.append(
        "| persona_name | source | top3_actions | outcome | failure_mode | nearest_train_persona | cosine_sim |"
    )
    lines.append("|---|---|---|---|---|---|---:|")
    for row in rows:
        nearest = row["nearest_neighbors"][0]
        top3 = ", ".join(f"{a['action']} ({a['proportion']:.2f})" for a in row["top3_actions"])
        nearest_label = f"#{nearest['id']} {nearest['occupation']}"
        failure_cell = row.get("failure_mode") or "—"
        lines.append(
            f"| {row['persona_name']} | {row['source']} | {top3} | "
            f"{row['outcome']} | {failure_cell} | {nearest_label} | "
            f"{row['mean_top5_cosine_sim']:.3f} |"
        )

    lines.extend(["", "## Qualitative Commentary", ""])
    for row in rows:
        lines.append(f"### {row['persona_name']}")
        lines.append("")
        lines.append(row["commentary"])
        lines.append("")
        lines.append(f"- Authored persona: {row['text']}")
        lines.append(f"- Bar chart: `{row['bar_chart']}`")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--policy", default="results/pcsp_v3/full/policy.pt")
    p.add_argument("--train_personas", default="data/personas/train_240_v3.json")
    p.add_argument("--train_embeddings", default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--output_dir", default="results/designer_persona_case_study")
    p.add_argument("--n_episodes", type=int, default=5)
    p.add_argument("--max_steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=20260511)
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = ROOT / args.output_dir
    chart_dir = out_dir / "action_bars"
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    train_personas = json.loads((ROOT / args.train_personas).read_text(encoding="utf-8"))
    all_train_embeddings = np.load(ROOT / args.train_embeddings).astype(np.float32)
    train_indices = [int(p["id"]) - 1 for p in train_personas]
    train_embeddings = all_train_embeddings[train_indices]
    train_embeddings = train_embeddings / np.linalg.norm(train_embeddings, axis=1, keepdims=True)
    train_embeddings_by_id = {
        int(p["id"]): all_train_embeddings[int(p["id"]) - 1].astype(np.float32)
        for p in train_personas
    }

    device = torch.device(args.device if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    print(f"Encoding {len(DESIGNER_PERSONAS)} designer personas on {device}...")
    designer_records = [p.to_persona_record(10001 + i) for i, p in enumerate(DESIGNER_PERSONAS)]
    designer_embeddings = embed_texts([p["text"] for p in designer_records], device=device)
    np.save(out_dir / "designer_persona_embeddings.npy", designer_embeddings.astype(np.float32))
    (out_dir / "designer_personas.json").write_text(
        json.dumps(designer_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Loading policy: {args.policy}")
    policy = load_policy(ROOT / args.policy, device=device)

    # Explicitly pass through trained LoRA projection for artifact/debugging.
    with torch.no_grad():
        projected = policy.persona_proj(
            torch.tensor(designer_embeddings, dtype=torch.float32, device=device)
        ).cpu().numpy()
    np.save(out_dir / "designer_persona_projected_embeddings.npy", projected.astype(np.float32))

    neighbors = compute_neighbors(designer_embeddings, train_embeddings, train_personas, top_k=5)
    rows: list[dict[str, Any]] = []
    print("Running v3 rollouts...")
    for i, (record, emb) in enumerate(zip(designer_records, designer_embeddings)):
        dist, ep_actions = action_distribution_for_persona(
            policy=policy,
            designer_record=record,
            designer_embedding=emb,
            train_personas=train_personas,
            train_embeddings_by_id=train_embeddings_by_id,
            device=device,
            seed=args.seed + i * 10007,
            n_episodes=args.n_episodes,
            max_steps=args.max_steps,
        )
        bar_path = chart_dir / f"{i + 1:02d}_{record['persona_name'].replace(' ', '_')}.png"
        save_action_bar(dist, record["persona_name"], bar_path)
        top3 = top_actions(dist)
        row = {
            **record,
            "action_distribution": {
                ACTION_NAMES_V3[j]: float(dist[j]) for j in range(N_ACTIONS_V3)
            },
            "top3_actions": top3,
            "nearest_neighbors": neighbors[i]["nearest"],
            "mean_top5_cosine_sim": neighbors[i]["mean_top5_cosine_sim"],
            "episode_actions": ep_actions,
            "bar_chart": str(bar_path.relative_to(ROOT)),
        }
        outcome = classify_outcome(row, top3, neighbors[i]["nearest"])
        row["outcome"] = outcome["outcome"]
        row["failure_mode"] = outcome["failure_mode"]
        row["overlap_count"] = outcome["overlap"]
        if "style_cos_mean" in outcome:
            row["style_cos_mean"] = outcome["style_cos_mean"]
        row["commentary"] = qualitative_commentary(row, top3, outcome)
        rows.append(row)
        tag = outcome["outcome"]
        if outcome["failure_mode"]:
            tag = f"{tag}/{outcome['failure_mode']}"
        print(
            f"  {i + 1:02d}/{len(designer_records)} {record['persona_name']} [{tag}]: "
            f"{', '.join(a['action'] for a in top3)}"
        )

    print("Running t-SNE...")
    coords = run_tsne(train_embeddings, designer_embeddings)
    np.save(out_dir / "tsne_coords_train240_plus_designer.npy", coords.astype(np.float32))
    tsne_path = out_dir / "designer_personas_tsne.png"
    save_tsne_plot(coords, train_personas, designer_records, tsne_path)

    payload = {
        "source": "designer_authored_persona_case_study",
        "policy": args.policy,
        "env": "MiniInzoiV3Env",
        "n_episodes_per_persona": args.n_episodes,
        "max_steps": args.max_steps,
        "seed": args.seed,
        "action_names": ACTION_NAMES_V3,
        "train_personas": args.train_personas,
        "train_embeddings": args.train_embeddings,
        "rows": rows,
        "tsne_plot": str(tsne_path.relative_to(ROOT)),
        "sources_consulted": [
            "https://sims.fandom.com/wiki/Trait_(The_Sims_3)",
            "https://nookipedia.com/wiki/Villager",
            "https://stardewvalleywiki.com/Villagers",
            "Persona Series confidant descriptions (Atlus, P3/P4/P5).",
            "Original designer briefs (authored for this study).",
        ],
    }
    (out_dir / "case_study_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    source_note = (
        "Persona descriptions were authored from five sources: The Sims 3 trait "
        "combinations, Animal Crossing villager personality categories, Stardew "
        "Valley NPC archetypes, Persona-series confidants, and original designer "
        "briefs. All were encoded with the same Qwen3 last-token-pooling "
        "normalization used by training."
    )
    report_path = out_dir / "case_study_report.md"
    write_markdown_report(
        rows=rows,
        out_path=report_path,
        source_note=source_note,
        policy_path=Path(args.policy),
        n_episodes=args.n_episodes,
        max_steps=args.max_steps,
    )

    print(json.dumps({
        "report": str(report_path.relative_to(ROOT)),
        "results_json": str((out_dir / "case_study_results.json").relative_to(ROOT)),
        "bar_charts": str(chart_dir.relative_to(ROOT)),
        "tsne_plot": str(tsne_path.relative_to(ROOT)),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
