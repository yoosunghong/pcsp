"""Persona conditioning heads.

Implements two trainable modules that fuse a (frozen) persona embedding into
the policy's feature stream:

- ``ConcatConditioning``: features ← MLP(concat(features, projected_persona)).
  Simple, well-behaved, and keeps the policy free to learn how strongly to
  attend to the persona.
- ``FiLMConditioning``: features ← γ(persona) ⊙ features + β(persona).
  Multiplicative conditioning gives the persona a more aggressive lever on
  the feature distribution — useful when persona-dependent behavioral shifts
  should be obvious (e.g., Phase 2 diagnostics).

Both modules consume a persona embedding of dim ``persona_dim`` and a feature
vector of dim ``feature_dim`` and return a vector of dim ``feature_dim`` so
downstream policy/value heads need no changes. The "none" mode is a passthrough.
"""

from __future__ import annotations

import torch
import torch.nn as nn


def _orthogonal_init(layer: nn.Module, gain: float) -> nn.Module:
    if isinstance(layer, nn.Linear):
        nn.init.orthogonal_(layer.weight, gain=gain)
        if layer.bias is not None:
            nn.init.zeros_(layer.bias)
    return layer


class _NoneConditioning(nn.Module):
    def forward(self, features: torch.Tensor, persona: torch.Tensor) -> torch.Tensor:
        return features


class ConcatConditioning(nn.Module):
    def __init__(self, feature_dim: int, persona_dim: int, hidden: int | None = None) -> None:
        super().__init__()
        hidden = hidden or feature_dim
        self.proj = _orthogonal_init(nn.Linear(persona_dim, hidden), gain=2 ** 0.5)
        self.fuse = _orthogonal_init(
            nn.Linear(feature_dim + hidden, feature_dim), gain=2 ** 0.5
        )

    def forward(self, features: torch.Tensor, persona: torch.Tensor) -> torch.Tensor:
        p = torch.relu(self.proj(persona))
        return torch.relu(self.fuse(torch.cat([features, p], dim=-1)))


class FiLMConditioning(nn.Module):
    def __init__(self, feature_dim: int, persona_dim: int) -> None:
        super().__init__()
        # Initialize γ to ≈ 1 (zero-init weight, ones bias) and β to ≈ 0
        # so the conditioning starts as identity and gradually learns to
        # modulate. This is the standard FiLM warm-start trick.
        self.to_gamma = nn.Linear(persona_dim, feature_dim)
        self.to_beta = nn.Linear(persona_dim, feature_dim)
        nn.init.zeros_(self.to_gamma.weight)
        nn.init.ones_(self.to_gamma.bias)
        nn.init.zeros_(self.to_beta.weight)
        nn.init.zeros_(self.to_beta.bias)

    def forward(self, features: torch.Tensor, persona: torch.Tensor) -> torch.Tensor:
        gamma = self.to_gamma(persona)
        beta = self.to_beta(persona)
        return gamma * features + beta


class ConditioningHead(nn.Module):
    """Dispatcher selected by ``mode``: ``none``, ``concat``, or ``film``.

    Always exposes a ``forward(features, persona) -> features`` signature so
    the policy network has a single uniform call site.
    """

    def __init__(self, mode: str, feature_dim: int, persona_dim: int) -> None:
        super().__init__()
        self.mode = mode
        if mode == "none":
            self.inner: nn.Module = _NoneConditioning()
        elif mode == "concat":
            self.inner = ConcatConditioning(feature_dim, persona_dim)
        elif mode == "film":
            self.inner = FiLMConditioning(feature_dim, persona_dim)
        else:
            raise ValueError(f"Unknown persona-conditioning mode: {mode!r}")

    def forward(self, features: torch.Tensor, persona: torch.Tensor) -> torch.Tensor:
        return self.inner(features, persona)


def build_conditioning_head(mode: str, feature_dim: int, persona_dim: int) -> ConditioningHead:
    return ConditioningHead(mode, feature_dim, persona_dim)
