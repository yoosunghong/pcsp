"""
FiLM (Feature-wise Linear Modulation) conditioning module.

persona embedding e_p → (γ, β) scales/shifts each hidden layer:
    h' = γ(e_p) ⊙ h + β(e_p)

Reference: Perez et al. 2018, "FiLM: Visual Reasoning with a General Conditioning Layer"
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FiLMLayer(nn.Module):
    """Single FiLM conditioning layer.

    Given persona embedding e_p, produces (γ, β) to modulate feature h:
        h' = γ(e_p) ⊙ h + β(e_p)
    """

    def __init__(self, persona_dim: int, hidden_dim: int):
        super().__init__()
        self.gamma_net = nn.Linear(persona_dim, hidden_dim)
        self.beta_net  = nn.Linear(persona_dim, hidden_dim)
        # Init γ→1, β→0 so the module starts as identity
        nn.init.zeros_(self.gamma_net.weight)
        nn.init.ones_(self.gamma_net.bias)
        nn.init.zeros_(self.beta_net.weight)
        nn.init.zeros_(self.beta_net.bias)

    def forward(self, h: torch.Tensor, e_p: torch.Tensor) -> torch.Tensor:
        gamma = self.gamma_net(e_p)  # (B, hidden_dim)
        beta  = self.beta_net(e_p)   # (B, hidden_dim)
        return gamma * h + beta


class FiLMBlock(nn.Module):
    """Linear → LayerNorm → ReLU → FiLM block."""

    def __init__(self, in_dim: int, out_dim: int, persona_dim: int):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)
        self.norm   = nn.LayerNorm(out_dim)
        self.film   = FiLMLayer(persona_dim, out_dim)

    def forward(self, x: torch.Tensor, e_p: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.norm(self.linear(x)))
        return self.film(h, e_p)


class PersonaProjection(nn.Module):
    """LoRA-style projection: frozen LLM embedding → task embedding space.

    In full training this wraps a frozen LLM encoder; here it accepts
    pre-computed embeddings and applies a learned linear projection.
    """

    def __init__(self, llm_dim: int, persona_dim: int, lora_r: int = 16):
        super().__init__()
        # Low-rank factorization: W = B @ A  (rank r)
        self.lora_A = nn.Linear(llm_dim, lora_r, bias=False)
        self.lora_B = nn.Linear(lora_r, persona_dim, bias=False)
        self.scale  = persona_dim ** -0.5
        nn.init.kaiming_uniform_(self.lora_A.weight)
        nn.init.normal_(self.lora_B.weight, std=0.02)

    def forward(self, e_llm: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.lora_B(self.lora_A(e_llm)) * self.scale, dim=-1)


class PersonaConditionedPolicy(nn.Module):
    """
    Shared policy π_θ(a | s, e_p) with FiLM conditioning.

    Architecture:
        obs → FiLMBlock(obs_dim, 256, persona_dim)
            → FiLMBlock(256, 256, persona_dim)
            → FiLMBlock(256, 128, persona_dim)
            → Linear(128, n_actions)

    persona_embedding e_p conditions every hidden layer via FiLM.
    """

    def __init__(
        self,
        obs_dim:     int,
        n_actions:   int,
        persona_dim: int = 64,
        llm_dim:     int = 1024,
        lora_r:      int = 16,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        self.block1 = FiLMBlock(obs_dim, 256, persona_dim)
        self.block2 = FiLMBlock(256,     256, persona_dim)
        self.block3 = FiLMBlock(256,     128, persona_dim)
        self.head   = nn.Linear(128, n_actions)

    def forward(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        """
        obs:   (B, obs_dim)   — game state
        e_llm: (B, llm_dim)   — frozen LLM embedding (pre-computed)
        returns: (B, n_actions) logits
        """
        e_p = self.persona_proj(e_llm)
        h   = self.block1(obs, e_p)
        h   = self.block2(h,   e_p)
        h   = self.block3(h,   e_p)
        return self.head(h)

    def act(self, obs: torch.Tensor, e_llm: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.forward(obs, e_llm)
        dist   = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        return action, dist.log_prob(action)


class PersonaConditionedValue(nn.Module):
    """Critic V(s, e_p) — same FiLM structure, scalar output."""

    def __init__(self, obs_dim: int, persona_dim: int = 64, llm_dim: int = 1024, lora_r: int = 16):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        self.block1 = FiLMBlock(obs_dim, 256, persona_dim)
        self.block2 = FiLMBlock(256,     128, persona_dim)
        self.head   = nn.Linear(128, 1)

    def forward(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        e_p = self.persona_proj(e_llm)
        h   = self.block1(obs, e_p)
        h   = self.block2(h,   e_p)
        return self.head(h).squeeze(-1)
