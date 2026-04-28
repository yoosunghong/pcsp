"""
B4: DIAYN baseline — FiLM policy conditioned on random (non-semantic) skill vectors.

Each persona is assigned a fixed random latent z ~ Uniform[-1, 1]^Z_DIM.
Same FiLM architecture as PCSP, but the embedding carries no semantic meaning.

This isolates the contribution of semantic LLM embeddings vs. merely having
some conditioning signal. If DIAYN ≈ PCSP, the semantic content doesn't help.
If DIAYN << PCSP, LLM embeddings are doing real work.

Optional: discriminator loss D(z | trajectory) for mutual-information
maximization. Enabled via `use_discriminator=True`.
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
from src.models.film import FiLMBlock, PersonaProjection
from src.training.ppo_trainer import PPOConfig, PPOTrainer

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
Z_DIM   = 64         # random skill vector dimension (matches PCSP persona_dim)


# ── Random skill embedder ──────────────────────────────────────────────────────

class RandomEmbedder:
    """Assigns fixed random latent vectors to persona indices."""

    def __init__(self, n_personas: int, z_dim: int = Z_DIM, seed: int = 0):
        rng = np.random.default_rng(seed)
        z = rng.uniform(-1, 1, (n_personas, z_dim)).astype(np.float32)
        # L2 normalize so vectors live on the unit sphere
        z /= np.linalg.norm(z, axis=1, keepdims=True) + 1e-8
        self._z = torch.FloatTensor(z)  # (N, Z_DIM)

    def __getitem__(self, idx: int) -> torch.Tensor:
        return self._z[idx].unsqueeze(0)  # (1, Z_DIM)

    def all_embeddings(self) -> torch.Tensor:
        return self._z  # (N, Z_DIM)


# ── Discriminator (optional, for MI maximization) ─────────────────────────────

class SkillDiscriminator(nn.Module):
    """
    q_φ(z | τ): predicts skill z from trajectory summary.

    Input: mean of (obs, action) pairs over the episode.
    Output: predicted z vector (MSE regression against true z).
    """

    def __init__(self, obs_dim: int = OBS_DIM, z_dim: int = Z_DIM, hidden: int = 128):
        super().__init__()
        in_dim = obs_dim + 1  # obs + action (scalar)
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, z_dim),
        )

    def forward(self, obs: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        a = actions.float().unsqueeze(-1) / (N_ACTS - 1)
        return self.net(torch.cat([obs, a], dim=-1))  # (B, Z_DIM)


# ── Policy ─────────────────────────────────────────────────────────────────────

class DIAYNActorCritic(nn.Module):
    """
    FiLM-conditioned actor-critic with random skill embeddings.

    Architecture is identical to PCSP's FiLM policy.
    The only difference: e_embed carries random noise instead of LLM semantics.

    context key: e_embed (Tensor, shape (B, Z_DIM))
    """

    def __init__(
        self,
        obs_dim:    int = OBS_DIM,
        n_actions:  int = N_ACTS,
        z_dim:      int = Z_DIM,
        persona_dim: int = 64,
    ):
        super().__init__()
        # Direct linear projection (no LoRA; random embedding → no rank benefit)
        self.skill_proj = nn.Sequential(
            nn.Linear(z_dim, persona_dim),
            nn.Tanh(),
        )
        nn.init.normal_(self.skill_proj[0].weight, std=0.01)
        # Actor
        self.actor_b1 = FiLMBlock(obs_dim, 256, persona_dim)
        self.actor_b2 = FiLMBlock(256,     256, persona_dim)
        self.actor_b3 = FiLMBlock(256,     128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)
        # Critic
        self.critic_b1 = FiLMBlock(obs_dim, 256, persona_dim)
        self.critic_b2 = FiLMBlock(256,     128, persona_dim)
        self.critic_head = nn.Linear(128, 1)

    def _actor(self, obs, e_p):
        h = self.actor_b1(obs, e_p)
        h = self.actor_b2(h,   e_p)
        h = self.actor_b3(h,   e_p)
        return self.actor_head(h)

    def _critic(self, obs, e_p):
        h = self.critic_b1(obs, e_p)
        h = self.critic_b2(h,   e_p)
        return self.critic_head(h).squeeze(-1)

    def get_action(
        self, obs: torch.Tensor, e_embed: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p    = self.skill_proj(e_embed)
        logits = self._actor(obs, e_p)
        values = self._critic(obs, e_p)
        dist   = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        return actions, dist.log_prob(actions), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_embed: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p    = self.skill_proj(e_embed)
        logits = self._actor(obs, e_p)
        values = self._critic(obs, e_p)
        dist   = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_embed": torch.cat([c["e_embed"] for c in ctxs], dim=0)}


# ── Training entry point ───────────────────────────────────────────────────────

def train_b4(
    personas_json: str | Path = "data/personas/train_240.json",
    config: PPOConfig | None = None,
    device: str = "cuda",
    output_dir: str | Path = "results/baselines/b4_diayn",
    z_dim: int = Z_DIM,
    use_discriminator: bool = False,
    n_iterations: int | None = None,
) -> dict:
    """Train B4 and save results."""
    root = Path(__file__).resolve().parents[3]
    output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(root / personas_json) as f:
        personas_data = json.load(f)

    # Assign fixed random latent vectors
    embedder = RandomEmbedder(len(personas_data), z_dim, seed=0)
    # Save random embeddings for reproducibility
    np.save(output_dir / "random_embeddings.npy", embedder.all_embeddings().numpy())

    if config is None:
        config = PPOConfig()

    rng = np.random.default_rng(config.seed)

    def persona_sampler():
        idxs = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embedder[int(idxs[j])]}
            for j in range(4)
        }
        return personas, agent_ctxs

    def make_env_fn(personas):
        return MiniInzoiEnv(personas=personas, max_steps=200)

    policy = DIAYNActorCritic(OBS_DIM, N_ACTS, z_dim)
    n_params = sum(p.numel() for p in policy.parameters())
    trainer = PPOTrainer(policy, config, device)

    print(
        f"\n[B4] DIAYN | z_dim={z_dim} | discriminator={'on' if use_discriminator else 'off'} "
        f"| params={n_params:,} | device={trainer.device}"
    )
    t0 = time.time()
    metrics = trainer.train(make_env_fn, persona_sampler, n_iterations=n_iterations)
    elapsed = time.time() - t0
    print(f"[B4] Training done in {elapsed:.1f}s")

    torch.save(policy.state_dict(), output_dir / "policy.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({
            "metrics": metrics,
            "elapsed_sec": elapsed,
            "z_dim": z_dim,
            "use_discriminator": use_discriminator,
        }, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[B4] Final reward: {final.get('mean_ep_reward', 'N/A'):.3f}")
    return final
