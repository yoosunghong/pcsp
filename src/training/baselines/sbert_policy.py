"""
B3: SBERT + frozen embed — FiLM policy conditioned on SentenceBERT embeddings.

Uses all-MiniLM-L6-v2 (384-dim) instead of Qwen3-Embed (1024-dim).
Tests whether the choice of text encoder (and its semantic quality) matters.

Embeddings are computed once and cached to disk.
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

OBS_DIM   = 20
N_ACTS    = N_ACTIONS  # 12
SBERT_DIM = 384        # all-MiniLM-L6-v2 output dimension


# ── SBERT encoder ──────────────────────────────────────────────────────────────

def compute_sbert_embeddings(
    texts: list[str],
    cache_path: Path | None = None,
    device: str = "cuda",
    batch_size: int = 64,
) -> np.ndarray:
    """
    Encode texts with all-MiniLM-L6-v2. Returns (N, 384) float32 array.
    Loads from cache_path if it exists; saves after computation.
    """
    if cache_path and cache_path.exists():
        return np.load(cache_path)

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    embeddings = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True,
        show_progress_bar=True, convert_to_numpy=True,
    )  # (N, 384)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, embeddings)
        print(f"[B3] SBERT embeddings saved to {cache_path}")

    return embeddings.astype(np.float32)


# ── Policy ─────────────────────────────────────────────────────────────────────

class SBERTActorCritic(nn.Module):
    """
    FiLM-conditioned actor-critic with SBERT embeddings.

    Same architecture as PCSP (film.py) but llm_dim=384 instead of 1024.
    context key: e_embed (Tensor, shape (B, 384))
    """

    def __init__(
        self,
        obs_dim:    int = OBS_DIM,
        n_actions:  int = N_ACTS,
        embed_dim:  int = SBERT_DIM,
        persona_dim: int = 64,
        lora_r:     int = 16,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(embed_dim, persona_dim, lora_r)
        # Actor
        self.actor_b1 = FiLMBlock(obs_dim, 256, persona_dim)
        self.actor_b2 = FiLMBlock(256,     256, persona_dim)
        self.actor_b3 = FiLMBlock(256,     128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)
        # Critic (lighter)
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
        e_p    = self.persona_proj(e_embed)
        logits = self._actor(obs, e_p)
        values = self._critic(obs, e_p)
        dist   = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        return actions, dist.log_prob(actions), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_embed: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p    = self.persona_proj(e_embed)
        logits = self._actor(obs, e_p)
        values = self._critic(obs, e_p)
        dist   = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_embed": torch.cat([c["e_embed"] for c in ctxs], dim=0)}


# ── Training entry point ───────────────────────────────────────────────────────

def train_b3(
    personas_json: str | Path = "data/personas/train_240.json",
    config: PPOConfig | None = None,
    device: str = "cuda",
    output_dir: str | Path = "results/baselines/b3_sbert",
    n_iterations: int | None = None,
) -> dict:
    """Train B3 and save results."""
    root = Path(__file__).resolve().parents[3]
    output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(root / personas_json) as f:
        personas_data = json.load(f)

    # Compute / load SBERT embeddings
    texts = [p["text"] for p in personas_data]
    cache = root / "results/embeddings/sbert_embeddings_train240.npy"
    embeddings = compute_sbert_embeddings(texts, cache_path=cache, device=device)
    # embeddings: (N, 384)

    # Build lookup: index -> Tensor(1, 384)
    embed_tensors = [torch.FloatTensor(embeddings[i]).unsqueeze(0) for i in range(len(personas_data))]

    if config is None:
        config = PPOConfig()

    rng = np.random.default_rng(config.seed)

    def persona_sampler():
        idxs = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_embed": embed_tensors[idxs[j]]}
            for j in range(4)
        }
        return personas, agent_ctxs

    def make_env_fn(personas):
        return MiniInzoiEnv(personas=personas, max_steps=200)

    policy = SBERTActorCritic(OBS_DIM, N_ACTS, SBERT_DIM)
    n_params = sum(p.numel() for p in policy.parameters())
    trainer = PPOTrainer(policy, config, device)

    print(f"\n[B3] SBERT Policy | embed_dim=384 | params={n_params:,} | device={trainer.device}")
    t0 = time.time()
    metrics = trainer.train(make_env_fn, persona_sampler, n_iterations=n_iterations)
    elapsed = time.time() - t0
    print(f"[B3] Training done in {elapsed:.1f}s")

    torch.save(policy.state_dict(), output_dir / "policy.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({"metrics": metrics, "elapsed_sec": elapsed}, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[B3] Final reward: {final.get('mean_ep_reward', 'N/A'):.3f}")
    return final
