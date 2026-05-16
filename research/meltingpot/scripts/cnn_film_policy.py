"""CNN+FiLM persona-conditioned actor-critic for Melting Pot RGB observations.

Reuses src/models/film.py:FiLMBlock / PersonaProjection unchanged. The only
MP-specific addition vs. the Mini-Inzoi §III spec is the CNN front-end that
turns the (88,88,3) image into a 256-d feature vector before the FiLM trunk.
"""
from __future__ import annotations

from pathlib import Path
import sys

import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from src.models.film import FiLMBlock, PersonaProjection  # noqa: E402


class NatureCNN(nn.Module):
    """3-layer CNN (Mnih et al. 2015) → 256-d feature."""

    def __init__(self, in_channels: int = 3, feat_dim: int = 256, in_hw: int = 88):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=8, stride=4), nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),          nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),          nn.ReLU(),
        )
        with torch.no_grad():
            dummy = torch.zeros(1, in_channels, in_hw, in_hw)
            n_flat = self.conv(dummy).flatten(1).shape[1]
        self.fc = nn.Sequential(nn.Linear(n_flat, feat_dim), nn.ReLU())

    def forward(self, x_uint8_or_float: torch.Tensor) -> torch.Tensor:
        # Accept either (B,H,W,3) uint8 or (B,3,H,W) float in [0,1]
        if x_uint8_or_float.dtype == torch.uint8:
            x = x_uint8_or_float.float().div_(255.0).permute(0, 3, 1, 2)
        elif x_uint8_or_float.dim() == 4 and x_uint8_or_float.shape[-1] == 3:
            x = x_uint8_or_float.float().permute(0, 3, 1, 2)
        else:
            x = x_uint8_or_float
        return self.fc(self.conv(x).flatten(1))


class PCSPCnnFiLMActorCritic(nn.Module):
    """CNN → 3 FiLM blocks (256-256-128) → action head + value head.

    Persona projection: LoRA r=16, 1024 → 64 (matches §III spec).
    Conditions every hidden layer via FiLM (matches §III spec).
    """

    def __init__(
        self,
        n_actions:    int,
        in_channels:  int = 3,
        feat_dim:     int = 256,
        persona_dim:  int = 64,
        llm_dim:      int = 1024,
        lora_r:       int = 16,
        in_hw:        int = 88,
        freeze_proj:  bool = False,
    ):
        super().__init__()
        self.cnn = NatureCNN(in_channels, feat_dim, in_hw)
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)

        self.actor_b1   = FiLMBlock(feat_dim, 256, persona_dim)
        self.actor_b2   = FiLMBlock(256,      256, persona_dim)
        self.actor_b3   = FiLMBlock(256,      128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)

        self.critic_b1   = FiLMBlock(feat_dim, 256, persona_dim)
        self.critic_b2   = FiLMBlock(256,      128, persona_dim)
        self.critic_head = nn.Linear(128, 1)

    def _trunk(self, feat: torch.Tensor, e_p: torch.Tensor):
        h = self.actor_b1(feat, e_p)
        h = self.actor_b2(h,    e_p)
        h = self.actor_b3(h,    e_p)
        logits = self.actor_head(h)

        h2 = self.critic_b1(feat, e_p)
        h2 = self.critic_b2(h2,   e_p)
        v  = self.critic_head(h2).squeeze(-1)
        return logits, v

    def features(self, obs: torch.Tensor) -> torch.Tensor:
        return self.cnn(obs)

    def action_logits(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        feat = self.cnn(obs)
        e_p  = self.persona_proj(e_llm)
        h = self.actor_b1(feat, e_p)
        h = self.actor_b2(h,    e_p)
        h = self.actor_b3(h,    e_p)
        return self.actor_head(h)

    def get_action(self, obs: torch.Tensor, e_llm: torch.Tensor):
        feat = self.cnn(obs)
        e_p  = self.persona_proj(e_llm)
        logits, v = self._trunk(feat, e_p)
        dist = torch.distributions.Categorical(logits=logits)
        a = dist.sample()
        return a, dist.log_prob(a), v

    def evaluate_actions(self, obs: torch.Tensor, actions: torch.Tensor, e_llm: torch.Tensor):
        feat = self.cnn(obs)
        e_p  = self.persona_proj(e_llm)
        logits, v = self._trunk(feat, e_p)
        dist = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), v, dist.entropy()
