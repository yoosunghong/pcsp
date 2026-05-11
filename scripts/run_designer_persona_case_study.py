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
from src.env.v3_constants import ACTION_NAMES_V3, N_ACTIONS_V3, OBS_DIM_V3_BASE
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
        text="성실하고 목표 지향적인 기업 전략가입니다. 완성도 높은 계획을 세우는 것을 중요하게 여기며, 쉬는 시간에도 업무 성과와 다음 학습 목표를 점검합니다.",
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
        text="조용하고 신중한 내성적인 연구원입니다. 사람 많은 장소보다 혼자 책을 읽고 자료를 정리하는 시간을 선호하며, 불안이 올라오면 익숙한 루틴으로 마음을 가라앉힙니다.",
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
        text="사교적이고 붙임성 좋은 이벤트 플래너입니다. 사람들을 한자리에 모으고 분위기를 띄우는 데 에너지를 얻으며, 하루 일과도 대화와 공동 휴식 중심으로 흘러갑니다.",
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
        text="용감하고 절제력이 강한 개인 트레이너입니다. 경쟁적인 운동 목표를 세우고 꾸준히 몸을 단련하며, 어려운 상황에서도 먼저 행동하는 편입니다.",
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
        text="느긋하고 의욕이 낮은 프리랜서입니다. 일을 미루고 소파에서 쉬거나 간단히 먹는 습관이 있으며, 청소나 운동처럼 에너지가 많이 드는 일은 자주 피합니다.",
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
        text="음식과 잠을 좋아하는 느긋한 마을 주민입니다. 서두르기보다 천천히 먹고 쉬는 일상을 즐기며, 친근하지만 큰 계획에는 별로 매달리지 않습니다.",
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
        text="운동에 집착하는 활기찬 마을 주민입니다. 하루의 대부분을 체력 단련과 활동적인 놀이로 채우고, 대화에서도 더 강해지는 방법을 자주 이야기합니다.",
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
        text="고집 있고 옛 방식을 좋아하는 무뚝뚝한 마을 주민입니다. 처음에는 까칠하게 굴지만 익숙한 사람에게는 조용히 챙겨 주며, 유행보다 혼자 쉬는 시간을 더 편하게 여깁니다.",
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
        text="위생과 정돈을 중시하는 다정하고 보살피는 마을 주민입니다. 차분한 루틴 속에서 청소와 자기관리를 챙기며, 주변 사람이 편안하게 지내도록 조용히 도와줍니다.",
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
        text="팝스타를 꿈꾸는 에너지 넘치는 마을 주민입니다. 새로운 사람에게 먼저 말을 걸고 활동적인 놀이를 즐기며, 하루를 공연 연습처럼 밝고 빠르게 움직입니다.",
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
        text="패션에 집착하고 자기 기준이 뚜렷한 마을 주민입니다. 세련된 모습을 유지하는 데 신경을 쓰며, 남들과 어울릴 때도 자신감 있고 약간 거리를 둔 태도를 보입니다.",
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
        text="신사적이지만 스스로에게 꽤 만족하는 마을 주민입니다. 매너 있는 대화를 즐기고 자기 취향을 자주 드러내며, 일과 휴식 모두를 멋지게 보이도록 조율하려 합니다.",
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
        text="직설적이고 씩씩하며 주변 사람을 보호하려는 마을 주민입니다. 말투는 거칠 수 있지만 도움이 필요한 사람에게 먼저 다가가고, 활동적인 일과 공동 휴식을 모두 중요하게 여깁니다.",
        big_five={"E": "high", "N": "mid", "A": "high", "C": "mid", "O": "mid"},
        preferred_actions=[7, 14, 8],
        decay_modifiers=[1.0, 1.0, 1.5, 1.0, 1.1, 1.3, 1.0, 0.9],
        alignment_expectation="Expected to favor socialize_respond, rest_with_others, and exercise.",
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
        alpha=0.58,
        edgecolors="none",
        label="train_240_v3",
    )
    ax.scatter(
        designer_xy[:, 0],
        designer_xy[:, 1],
        s=95,
        c="#D62728",
        marker="*",
        edgecolors="black",
        linewidths=0.5,
        label="designer personas",
        zorder=4,
    )
    for xy, rec in zip(designer_xy, designer_records):
        ax.annotate(
            rec["persona_name"],
            xy,
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=7.5,
            alpha=0.92,
        )
    ax.set_title("Qwen3 persona embeddings: train_240_v3 + designer-authored personas")
    ax.set_xlabel("t-SNE dim 1")
    ax.set_ylabel("t-SNE dim 2")
    ax.grid(alpha=0.22)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def top_actions(dist: np.ndarray, k: int = 3) -> list[dict[str, Any]]:
    idxs = np.argsort(-dist)[:k]
    return [{"action": ACTION_NAMES_V3[int(i)], "proportion": float(dist[int(i)])} for i in idxs]


def qualitative_commentary(record: dict[str, Any], top3: list[dict[str, Any]]) -> str:
    top_names = [t["action"] for t in top3]
    expected_names = [ACTION_NAMES_V3[i] for i in record["preferred_actions"]]
    overlap = [a for a in top_names if a in expected_names]

    if len(overlap) >= 2:
        alignment = "strong alignment"
        reading = "The policy mostly preserves the designer-authored behavioral intent."
    elif len(overlap) == 1:
        alignment = "partial alignment"
        reading = "The rollout captures one intended behavior but also exposes a competing policy bias."
    else:
        alignment = "weak alignment"
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
        "| persona_name | top3_actions | nearest_train_persona | cosine_sim |",
        "|---|---|---|---:|",
    ]
    for row in rows:
        nearest = row["nearest_neighbors"][0]
        top3 = ", ".join(f"{a['action']} ({a['proportion']:.2f})" for a in row["top3_actions"])
        nearest_label = f"#{nearest['id']} {nearest['occupation']}"
        lines.append(
            f"| {row['persona_name']} | {top3} | {nearest_label} | {row['mean_top5_cosine_sim']:.3f} |"
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
        row["commentary"] = qualitative_commentary(row, top3)
        rows.append(row)
        print(
            f"  {i + 1:02d}/{len(designer_records)} {record['persona_name']}: "
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
        ],
    }
    (out_dir / "case_study_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    source_note = (
        "Persona descriptions were authored from the requested Sims 3 trait combinations "
        "and Animal Crossing villager personality categories, then encoded with the same "
        "Qwen3 last-token-pooling normalization used by training."
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
