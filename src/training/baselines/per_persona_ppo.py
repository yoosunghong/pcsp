"""
B2: Per-Persona PPO — one independent policy per persona (oracle upper bound).

Demonstrates the memory/time cost of not sharing a policy.
Cannot generalize to unseen personas (zero-shot test set).

For practicality, we train on the first N_TRAIN_PERSONAS from the training set
(default 24) and measure convergence speed vs. memory overhead.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS
from src.training.ppo_trainer import PPOConfig, PPOTrainer

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12

# Number of personas to train independent policies for (feasibility limit)
N_TRAIN_PERSONAS = 24


class _SingleMLP(nn.Module):
    """Minimal MLP actor-critic for one persona."""

    def __init__(self, obs_dim: int, n_actions: int, hidden: int = 256):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),  nn.ReLU(),
        )
        self.actor = nn.Linear(hidden, n_actions)
        self.critic = nn.Linear(hidden, 1)

    def forward(self, obs):
        h = self.trunk(obs)
        return self.actor(h), self.critic(h).squeeze(-1)


class PerPersonaActorCritic(nn.Module):
    """
    Dict of independent MLPs — one per persona index.

    context key: persona_idx (int, 0-indexed into policies dict)
    stack_contexts returns {"persona_idx": [list of ints]}
    """

    def __init__(self, n_personas: int, obs_dim: int = OBS_DIM, n_actions: int = N_ACTS, hidden: int = 256):
        super().__init__()
        self.policies = nn.ModuleList([
            _SingleMLP(obs_dim, n_actions, hidden) for _ in range(n_personas)
        ])

    def get_action(
        self, obs: torch.Tensor, persona_idx: int | list[int], **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if isinstance(persona_idx, int):
            persona_idx = [persona_idx] * obs.shape[0]

        actions   = torch.zeros(len(persona_idx), dtype=torch.long, device=obs.device)
        log_probs = torch.zeros(len(persona_idx), device=obs.device)
        values    = torch.zeros(len(persona_idx), device=obs.device)

        unique_ids = set(persona_idx)
        for pid in unique_ids:
            mask = [i for i, p in enumerate(persona_idx) if p == pid]
            logits, v = self.policies[pid](obs[mask])
            dist = torch.distributions.Categorical(logits=logits)
            a = dist.sample()
            actions[mask]   = a
            log_probs[mask] = dist.log_prob(a)
            values[mask]    = v

        return actions, log_probs, values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, persona_idx: list[int], **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        log_probs = torch.zeros(len(persona_idx), device=obs.device)
        values    = torch.zeros(len(persona_idx), device=obs.device)
        entropy   = torch.zeros(len(persona_idx), device=obs.device)

        unique_ids = set(persona_idx)
        for pid in unique_ids:
            mask = [i for i, p in enumerate(persona_idx) if p == pid]
            logits, v = self.policies[pid](obs[mask])
            dist = torch.distributions.Categorical(logits=logits)
            log_probs[mask] = dist.log_prob(actions[mask])
            values[mask]    = v
            entropy[mask]   = dist.entropy()

        return log_probs, values, entropy

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"persona_idx": [c["persona_idx"] for c in ctxs]}


# ── Training entry point ───────────────────────────────────────────────────────

def train_b2(
    personas_json: str | Path = "data/personas/train_240.json",
    config: PPOConfig | None = None,
    device: str = "cuda",
    output_dir: str | Path = "results/baselines/b2_per_persona",
    n_train_personas: int = N_TRAIN_PERSONAS,
    n_iterations: int | None = None,
) -> dict:
    """Train B2 and save results."""
    root = Path(__file__).resolve().parents[3]
    output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(root / personas_json) as f:
        all_personas = json.load(f)

    # Take the first n_train_personas from training set
    train_personas = all_personas[:n_train_personas]
    persona_id_map = {p["id"]: idx for idx, p in enumerate(train_personas)}

    if config is None:
        config = PPOConfig()

    rng = np.random.default_rng(config.seed)

    def persona_sampler():
        """Sample 4 personas from our subset, return policy indices."""
        idxs = rng.choice(len(train_personas), size=4, replace=False)
        personas = [PersonaConfig.from_dict(train_personas[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"persona_idx": int(idxs[j])}
            for j in range(4)
        }
        return personas, agent_ctxs

    def make_env_fn(personas):
        return MiniInzoiEnv(personas=personas, max_steps=200)

    policy = PerPersonaActorCritic(n_train_personas, OBS_DIM, N_ACTS)
    n_params = sum(p.numel() for p in policy.parameters())
    trainer = PPOTrainer(policy, config, device)

    print(
        f"\n[B2] Per-Persona PPO | {n_train_personas} policies | "
        f"total params={n_params:,} ({n_params/n_train_personas:,.0f}/policy) | device={trainer.device}"
    )
    t0 = time.time()
    metrics = trainer.train(make_env_fn, persona_sampler, n_iterations=n_iterations)
    elapsed = time.time() - t0
    print(f"[B2] Training done in {elapsed:.1f}s")

    torch.save(policy.state_dict(), output_dir / "policy.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({
            "metrics": metrics,
            "elapsed_sec": elapsed,
            "n_train_personas": n_train_personas,
            "total_params": n_params,
        }, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[B2] Final reward: {final.get('mean_ep_reward', 'N/A'):.3f}")
    return final
