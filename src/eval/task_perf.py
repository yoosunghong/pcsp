"""
Task performance evaluation — eval/task_perf.py

Runs n_episodes episodes with a given policy and persona set, and reports
mean / std / min / max episode reward (needs satisfaction).

Supports all model types (PCSP, baselines) via a generic interface:
  - For persona-conditioned models: pass persona_sampler that returns (personas, agent_ctxs)
  - For no-persona models:         pass persona_sampler that returns agent_ctxs with empty dicts

Usage (standalone):
    python src/eval/task_perf.py \
        --policy results/pcsp/full/policy.pt \
        --model_type pcsp \
        --personas data/personas/train_240.json \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --n_episodes 100
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024


def evaluate_task_reward(
    policy:          torch.nn.Module,
    persona_sampler: Callable,
    n_episodes:      int  = 100,
    max_steps:       int  = 200,
    device:          str  = "cuda",
    seed:            int  = 0,
) -> dict:
    """
    Roll out n_episodes episodes.  persona_sampler() returns (personas, agent_ctxs)
    where agent_ctxs maps agent_name → context dict (can be empty).

    Returns mean / std / min / max episode reward.
    """
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    policy.to(dev).eval()

    ep_rewards: list[float] = []

    for ep in range(n_episodes):
        rng_seed = seed + ep * 1009
        personas, agent_ctxs = persona_sampler()
        env = MiniInzoiEnv(personas=personas, max_steps=max_steps)
        env.reset(seed=rng_seed)

        ep_rew = {a: 0.0 for a in env.possible_agents}

        for agent in env.agent_iter():
            obs, rew, term, trunc, _ = env.last()
            ep_rew[agent] += rew

            if term or trunc:
                env.step(None)
                continue

            ctx = agent_ctxs.get(agent, {})
            obs_t   = torch.FloatTensor(obs).unsqueeze(0).to(dev)
            ctx_dev = {k: (v.to(dev) if isinstance(v, torch.Tensor) else v)
                       for k, v in ctx.items()}
            with torch.no_grad():
                action_t, _, _ = policy.get_action(obs_t, **ctx_dev)
            env.step(action_t.item())

        env.close()
        ep_rewards.append(sum(ep_rew.values()) / len(ep_rew))

    arr = np.array(ep_rewards)
    return {
        "mean":   float(arr.mean()),
        "std":    float(arr.std()),
        "min":    float(arr.min()),
        "max":    float(arr.max()),
        "median": float(np.median(arr)),
        "n_episodes": n_episodes,
    }


def make_pcsp_sampler(
    personas_data:   list[dict],
    all_embeddings:  np.ndarray,  # (300, LLM_DIM)
    device:          torch.device,
    seed:            int = 42,
) -> Callable:
    """Returns a persona_sampler for PCSP-style models (FiLM / concat)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(all_embeddings[p["id"] - 1].astype(np.float32)).unsqueeze(0)
        for p in personas_data
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_llm": embed_tensors[idxs[j]].to(device)}
            for j in range(4)
        }
        return personas, agent_ctxs

    return sampler


def make_no_persona_sampler(
    personas_data: list[dict],
    seed:          int = 42,
) -> Callable:
    """Returns a persona_sampler for no-persona baselines."""
    rng = np.random.default_rng(seed)

    def sampler():
        idxs    = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {f"agent_{j}": {} for j in range(4)}
        return personas, agent_ctxs

    return sampler


def make_sbert_sampler(
    personas_data:    list[dict],
    sbert_embeddings: np.ndarray,   # (N_train, 384) from sbert_embeddings_train240.npy
    device:           torch.device,
    seed:             int = 42,
) -> Callable:
    """Returns a persona_sampler for B3 SBERT (context key: e_embed, 384-dim)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(sbert_embeddings[i]).unsqueeze(0)
        for i in range(len(personas_data))
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embed_tensors[idxs[j]].to(device)}
            for j in range(4)
        }
        return personas, agent_ctxs

    return sampler


def make_diayn_sampler(
    personas_data:     list[dict],
    random_embeddings: np.ndarray,   # (N_train, Z_DIM) from random_embeddings.npy
    device:            torch.device,
    seed:              int = 42,
) -> Callable:
    """Returns a persona_sampler for B4 DIAYN (context key: e_embed, random latent)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(random_embeddings[i]).unsqueeze(0)
        for i in range(len(personas_data))
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embed_tensors[idxs[j]].to(device)}
            for j in range(4)
        }
        return personas, agent_ctxs

    return sampler


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--policy",      required=True)
    p.add_argument("--model_type",  choices=["pcsp", "no_persona", "sbert", "diayn"],
                   default="pcsp")
    p.add_argument("--personas",    default="data/personas/train_240.json")
    p.add_argument("--embeddings",  default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--n_episodes",  type=int, default=100)
    p.add_argument("--device",      default="cuda")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    with open(ROOT / args.personas) as f:
        personas_data = json.load(f)
    all_emb = np.load(ROOT / args.embeddings)

    dev = torch.device(args.device if torch.cuda.is_available() else "cpu")

    if args.model_type == "no_persona":
        from src.training.baselines.no_persona_ppo import MLPActorCritic
        policy = MLPActorCritic(OBS_DIM, N_ACTS)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))
        sampler = make_no_persona_sampler(personas_data)
    else:
        from src.training.pcsp_trainer import PCSPActorCritic
        policy = PCSPActorCritic(OBS_DIM, N_ACTS)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))
        sampler = make_pcsp_sampler(personas_data, all_emb, dev)

    result = evaluate_task_reward(
        policy, sampler,
        n_episodes=args.n_episodes,
        device=args.device,
    )
    print(json.dumps(result, indent=2))
