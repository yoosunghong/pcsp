"""
B1: No-Persona PPO — single generic policy that ignores all persona information.

This is the lower-bound baseline: one shared policy for all agents/personas.
Expected to underperform PCSP because it cannot adapt behavior to persona.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS
from src.training.ppo_trainer import PPOConfig, PPOTrainer

OBS_DIM  = 20
N_ACTS   = N_ACTIONS  # 12


class MLPActorCritic(nn.Module):
    """
    Simple 3-layer MLP actor-critic with no persona conditioning.

    stack_contexts returns {} so the trainer passes no extra kwargs.
    """

    def __init__(self, obs_dim: int = OBS_DIM, n_actions: int = N_ACTS, hidden: int = 256):
        super().__init__()
        # Shared trunk
        self.trunk = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),  nn.ReLU(),
        )
        self.actor_head = nn.Linear(hidden, n_actions)
        self.value_head = nn.Linear(hidden, 1)

    def _forward(self, obs: torch.Tensor):
        h = self.trunk(obs)
        return self.actor_head(h), self.value_head(h).squeeze(-1)

    def get_action(self, obs: torch.Tensor, **_ctx) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        logits, values = self._forward(obs)
        dist = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        return actions, dist.log_prob(actions), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, **_ctx
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        logits, values = self._forward(obs)
        dist = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {}


# ── Training entry point ───────────────────────────────────────────────────────

def train_b1(
    personas_json: str | Path = "data/personas/train_240.json",
    config: PPOConfig | None = None,
    device: str = "cuda",
    output_dir: str | Path = "results/baselines/b1_no_persona",
    n_iterations: int | None = None,
    obs_dim:    int = OBS_DIM,
    n_actions:  int = N_ACTS,
    n_agents:   int = 4,
    env_factory: Callable | None = None,
) -> dict:
    """Train B1 and save results. Returns final metrics dict.

    obs_dim / n_actions / n_agents / env_factory let v3 callers supply alternate
    dims and env constructor without forking; defaults reproduce v1.
    """
    root = Path(__file__).resolve().parents[3]
    output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load train personas
    with open(root / personas_json) as f:
        personas_data = json.load(f)

    if config is None:
        config = PPOConfig()

    rng = np.random.default_rng(config.seed)

    def persona_sampler():
        """Sample n_agents personas; no embeddings (no-persona baseline)."""
        idxs = rng.choice(len(personas_data), size=n_agents, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {f"agent_{j}": {} for j in range(n_agents)}
        return personas, agent_ctxs

    def _default_make_env_fn(personas):
        return MiniInzoiEnv(personas=personas, max_steps=200)

    make_env_fn = env_factory if env_factory is not None else _default_make_env_fn

    policy = MLPActorCritic(obs_dim, n_actions)
    trainer = PPOTrainer(policy, config, device)

    print(f"\n[B1] No-Persona PPO | device={trainer.device} | params={sum(p.numel() for p in policy.parameters()):,}")
    t0 = time.time()
    metrics = trainer.train(make_env_fn, persona_sampler, n_iterations=n_iterations)
    elapsed = time.time() - t0
    print(f"[B1] Training done in {elapsed:.1f}s")

    # Save checkpoint and metrics
    torch.save(policy.state_dict(), output_dir / "policy.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({"metrics": metrics, "elapsed_sec": elapsed}, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[B1] Final reward: {final.get('mean_ep_reward', 'N/A'):.3f}")
    return final
