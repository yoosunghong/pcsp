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
    env_factory:     Callable | None = None,
) -> dict:
    """
    Roll out n_episodes episodes.  persona_sampler() returns (personas, agent_ctxs)
    where agent_ctxs maps agent_name → context dict (can be empty).

    ``env_factory`` accepts the sampled persona list and returns an environment.
    The default preserves the original v1 ``MiniInzoiEnv`` behavior; v3 callers
    can inject ``MiniInzoiV3Env`` without forking this evaluator.

    Returns mean / std / min / max episode reward.
    """
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    policy.to(dev).eval()

    ep_rewards: list[float] = []

    for ep in range(n_episodes):
        rng_seed = seed + ep * 1009
        personas, agent_ctxs = persona_sampler()
        if env_factory is None:
            env = MiniInzoiEnv(personas=personas, max_steps=max_steps)
        else:
            env = env_factory(personas)
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
    n_agents:        int = 4,
) -> Callable:
    """Returns a persona_sampler for PCSP-style models (FiLM / concat)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(all_embeddings[p["id"] - 1].astype(np.float32)).unsqueeze(0)
        for p in personas_data
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=n_agents, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_llm": embed_tensors[idxs[j]].to(device)}
            for j in range(n_agents)
        }
        return personas, agent_ctxs

    return sampler


def make_no_persona_sampler(
    personas_data: list[dict],
    seed:          int = 42,
    n_agents:      int = 4,
) -> Callable:
    """Returns a persona_sampler for no-persona baselines."""
    rng = np.random.default_rng(seed)

    def sampler():
        idxs    = rng.choice(len(personas_data), size=n_agents, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {f"agent_{j}": {} for j in range(n_agents)}
        return personas, agent_ctxs

    return sampler


def make_sbert_sampler(
    personas_data:    list[dict],
    sbert_embeddings: np.ndarray,   # (N_train, 384) from sbert_embeddings_train240.npy
    device:           torch.device,
    seed:             int = 42,
    n_agents:         int = 4,
) -> Callable:
    """Returns a persona_sampler for B3 SBERT (context key: e_embed, 384-dim)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(sbert_embeddings[i]).unsqueeze(0)
        for i in range(len(personas_data))
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=n_agents, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embed_tensors[idxs[j]].to(device)}
            for j in range(n_agents)
        }
        return personas, agent_ctxs

    return sampler


def make_diayn_sampler(
    personas_data:     list[dict],
    random_embeddings: np.ndarray,   # (N_train, Z_DIM) from random_embeddings.npy
    device:            torch.device,
    seed:              int = 42,
    n_agents:          int = 4,
) -> Callable:
    """Returns a persona_sampler for B4 DIAYN (context key: e_embed, random latent)."""
    rng = np.random.default_rng(seed)
    embed_tensors = [
        torch.FloatTensor(random_embeddings[i]).unsqueeze(0)
        for i in range(len(personas_data))
    ]

    def sampler():
        idxs    = rng.choice(len(personas_data), size=n_agents, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embed_tensors[idxs[j]].to(device)}
            for j in range(n_agents)
        }
        return personas, agent_ctxs

    return sampler


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--policy",      required=True)
    p.add_argument("--model_type",  choices=["pcsp", "no_persona", "sbert", "diayn"],
                   default="pcsp")
    p.add_argument("--env_variant", choices=["v1", "v3"], default="v1")
    p.add_argument("--personas",    default=None,
                   help="Defaults to train_240.json for v1 and train_240_v3.json for v3.")
    p.add_argument("--embeddings",  default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--n_episodes",  type=int, default=100)
    p.add_argument("--max_steps",   type=int, default=200)
    p.add_argument("--n_agents",    type=int, default=4)
    p.add_argument("--obs_dim",     type=int, default=None)
    p.add_argument("--n_actions",   type=int, default=None)
    p.add_argument("--device",      default="cuda")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.n_agents < 1:
        raise ValueError("--n_agents must be at least 1")

    if args.env_variant == "v3":
        from src.env.mini_inzoi_v3 import MiniInzoiV3Env
        from src.env.v3_constants import N_ACTIONS_V3, obs_dim_v3

        obs_dim = args.obs_dim if args.obs_dim is not None else obs_dim_v3(args.n_agents)
        n_actions = args.n_actions if args.n_actions is not None else N_ACTIONS_V3
        personas_path = args.personas or "data/personas/train_240_v3.json"

        def selected_env_factory(personas):
            return MiniInzoiV3Env(personas=personas, max_steps=args.max_steps)
    else:
        obs_dim = args.obs_dim if args.obs_dim is not None else OBS_DIM
        n_actions = args.n_actions if args.n_actions is not None else N_ACTS
        personas_path = args.personas or "data/personas/train_240.json"

        def selected_env_factory(personas):
            return MiniInzoiEnv(personas=personas, max_steps=args.max_steps)

    with open(ROOT / personas_path) as f:
        personas_data = json.load(f)
    if len(personas_data) < args.n_agents:
        raise ValueError(
            f"Need at least {args.n_agents} personas, found {len(personas_data)} in {personas_path}"
        )
    all_emb = np.load(ROOT / args.embeddings)

    dev = torch.device(args.device if torch.cuda.is_available() else "cpu")

    if args.model_type == "no_persona":
        from src.training.baselines.no_persona_ppo import MLPActorCritic
        policy = MLPActorCritic(obs_dim, n_actions)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))
        sampler = make_no_persona_sampler(personas_data, n_agents=args.n_agents)
    else:
        from src.training.pcsp_trainer import PCSPActorCritic
        policy = PCSPActorCritic(obs_dim, n_actions)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))
        sampler = make_pcsp_sampler(
            personas_data, all_emb, dev, n_agents=args.n_agents,
        )

    result = evaluate_task_reward(
        policy, sampler,
        n_episodes=args.n_episodes,
        max_steps=args.max_steps,
        device=args.device,
        env_factory=selected_env_factory,
    )
    result.update({
        "env_variant": args.env_variant,
        "obs_dim": obs_dim,
        "n_actions": n_actions,
        "n_agents": args.n_agents,
    })
    print(json.dumps(result, indent=2))
