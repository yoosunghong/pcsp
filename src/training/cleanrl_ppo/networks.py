"""IMPALA-style CNN encoder + actor/critic heads for Melting Pot RGB obs.

Architecture (matches MELTINGPOT_PLAN.md Phase 1 §"In-house PPO trainer"):

- IMPALA-CNN torso: 3 conv blocks with channel widths [16, 32, 32]. Each
  block: conv3x3 → maxpool stride-2 → 2× (residual block of two conv3x3s).
- Global ReLU → flatten → Linear → ReLU → ``feature_dim`` features.
- Optional LSTM layer (cell size = ``lstm_hidden``).
- Categorical policy head + scalar value head.

Inputs: uint8 RGB tensors of shape ``(B, H, W, C)``. We do the uint8→float
cast and the ``/255`` rescaling on-device inside ``forward_encoder`` so the
parent process never pays the cost.

Weight init: orthogonal with gain √2 for conv/linear layers, gain 0.01 for
the policy head, gain 1.0 for the value head — CleanRL convention.
"""

from __future__ import annotations

from typing import NamedTuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ----- Init helpers ----------------------------------------------------------


def _orthogonal_init(layer: nn.Module, gain: float) -> nn.Module:
    if isinstance(layer, (nn.Linear, nn.Conv2d)):
        nn.init.orthogonal_(layer.weight, gain=gain)
        if layer.bias is not None:
            nn.init.zeros_(layer.bias)
    return layer


# ----- IMPALA-CNN ------------------------------------------------------------


class ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = _orthogonal_init(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1), gain=2 ** 0.5
        )
        self.conv2 = _orthogonal_init(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1), gain=2 ** 0.5
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = F.relu(x)
        h = self.conv1(h)
        h = F.relu(h)
        h = self.conv2(h)
        return x + h


class ImpalaBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv = _orthogonal_init(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            gain=2 ** 0.5,
        )
        self.pool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.res1 = ResidualBlock(out_channels)
        self.res2 = ResidualBlock(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.pool(x)
        x = self.res1(x)
        x = self.res2(x)
        return x


class ImpalaCNN(nn.Module):
    def __init__(
        self,
        in_channels: int,
        height: int,
        width: int,
        feature_dim: int,
        channels: tuple[int, int, int] = (16, 32, 32),
    ) -> None:
        super().__init__()
        c1, c2, c3 = channels
        self.blocks = nn.Sequential(
            ImpalaBlock(in_channels, c1),
            ImpalaBlock(c1, c2),
            ImpalaBlock(c2, c3),
        )
        # Probe the flattened size with a dummy tensor.
        with torch.no_grad():
            dummy = torch.zeros(1, in_channels, height, width)
            flat = self.blocks(dummy).flatten(1).shape[1]
        self.flat_dim = flat
        self.fc = _orthogonal_init(nn.Linear(flat, feature_dim), gain=2 ** 0.5)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, H, W) float in [0, 1].
        h = self.blocks(x)
        h = F.relu(h)
        h = h.flatten(1)
        h = F.relu(self.fc(h))
        return h


# ----- Actor-critic ----------------------------------------------------------


class ActorCriticOutput(NamedTuple):
    logits: torch.Tensor      # (B, A)
    value: torch.Tensor       # (B,)
    lstm_state: tuple[torch.Tensor, torch.Tensor] | None


class ActorCritic(nn.Module):
    """Shared-trunk actor-critic with optional LSTM and persona conditioning.

    Persona conditioning is applied to the CNN features *before* the LSTM
    (if any) and the policy/value heads. The conditioning module is injected
    via ``conditioning`` (a ``ConditioningHead``-like ``nn.Module`` with a
    ``forward(features, persona) -> features`` signature). If
    ``conditioning is None`` or its mode is "none", behavior is identical to
    the Phase 1 baseline.

    Forward modes:
    - ``forward_encoder(obs)``: encode uint8 (B, H, W, C) → features (B, D).
    - ``policy_value(features, lstm_state=None, done=None)``: produce logits
      and value. If LSTM is enabled and a sequence of features is provided
      with shape ``(T, B, D)`` plus a done mask ``(T, B)``, the LSTM is
      unrolled with hidden-state resets on episode boundaries.
    """

    def __init__(
        self,
        *,
        obs_height: int,
        obs_width: int,
        obs_channels: int,
        num_actions: int,
        feature_dim: int = 256,
        use_lstm: bool = False,
        lstm_hidden: int = 256,
        conditioning: nn.Module | None = None,
    ) -> None:
        super().__init__()
        self.use_lstm = use_lstm
        self.feature_dim = feature_dim
        self.lstm_hidden = lstm_hidden
        self.num_actions = num_actions

        self.encoder = ImpalaCNN(
            in_channels=obs_channels,
            height=obs_height,
            width=obs_width,
            feature_dim=feature_dim,
        )
        self.conditioning = conditioning
        head_in = feature_dim
        if use_lstm:
            self.lstm = nn.LSTM(feature_dim, lstm_hidden, num_layers=1)
            for name, p in self.lstm.named_parameters():
                if "weight" in name:
                    nn.init.orthogonal_(p, gain=1.0)
                elif "bias" in name:
                    nn.init.zeros_(p)
            head_in = lstm_hidden

        self.actor = _orthogonal_init(nn.Linear(head_in, num_actions), gain=0.01)
        self.critic = _orthogonal_init(nn.Linear(head_in, 1), gain=1.0)

    # --- encoding --------------------------------------------------------

    def forward_encoder(self, obs_uint8: torch.Tensor) -> torch.Tensor:
        """obs_uint8: (B, H, W, C) uint8 → features (B, D)."""
        # NHWC uint8 → NCHW float / 255.
        x = obs_uint8.permute(0, 3, 1, 2).contiguous().float().div_(255.0)
        return self.encoder(x)

    # --- LSTM unroll -----------------------------------------------------

    def _lstm_unroll(
        self,
        features: torch.Tensor,         # (T, B, D)
        lstm_state: tuple[torch.Tensor, torch.Tensor],
        dones: torch.Tensor,            # (T, B) float
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        h, c = lstm_state
        outputs = []
        for t in range(features.shape[0]):
            # Reset hidden state on episode boundary at the start of this step.
            mask = (1.0 - dones[t]).view(1, -1, 1)
            h = h * mask
            c = c * mask
            out, (h, c) = self.lstm(features[t : t + 1], (h, c))
            outputs.append(out)
        return torch.cat(outputs, dim=0), (h, c)

    def initial_lstm_state(self, batch_size: int, device: torch.device):
        return (
            torch.zeros(1, batch_size, self.lstm_hidden, device=device),
            torch.zeros(1, batch_size, self.lstm_hidden, device=device),
        )

    # --- step / unroll API ----------------------------------------------

    def _apply_conditioning(
        self, features: torch.Tensor, persona: torch.Tensor | None
    ) -> torch.Tensor:
        if self.conditioning is None or persona is None:
            return features
        return self.conditioning(features, persona)

    def act(
        self,
        obs_uint8: torch.Tensor,
        lstm_state: tuple[torch.Tensor, torch.Tensor] | None = None,
        done: torch.Tensor | None = None,
        persona: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple | None]:
        """Single-step act path used during rollout collection.

        Returns ``(action, log_prob, value, new_lstm_state)``.
        """
        features = self.forward_encoder(obs_uint8)
        features = self._apply_conditioning(features, persona)
        if self.use_lstm:
            assert lstm_state is not None and done is not None
            features_seq = features.unsqueeze(0)         # (1, B, D)
            done_seq = done.float().unsqueeze(0)         # (1, B)
            hidden, new_state = self._lstm_unroll(features_seq, lstm_state, done_seq)
            hidden = hidden.squeeze(0)
        else:
            hidden = features
            new_state = None
        logits = self.actor(hidden)
        value = self.critic(hidden).squeeze(-1)
        dist = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob, value, new_state

    def policy_logits(
        self,
        obs_uint8: torch.Tensor,
        persona: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Return (B, num_actions) action logits for a non-recurrent eval.

        Used by the KL-diversity auxiliary loss, which probes how much
        the policy distribution shifts when the persona embedding is
        permuted across the same observations. LSTM path is intentionally
        not supported — the caller gates this loss on ``use_lstm=False``.
        """
        features = self.forward_encoder(obs_uint8)
        features = self._apply_conditioning(features, persona)
        return self.actor(features)

    def evaluate(
        self,
        obs_uint8: torch.Tensor,                  # (T*B, H, W, C) flat
        actions: torch.Tensor,                    # (T*B,)
        *,
        batch_size: int | None = None,            # B if LSTM, else ignored
        num_steps: int | None = None,             # T if LSTM, else ignored
        lstm_state: tuple[torch.Tensor, torch.Tensor] | None = None,
        dones: torch.Tensor | None = None,        # (T, B)
        persona: torch.Tensor | None = None,      # (T*B, D_p) flat
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute ``(log_prob, entropy, value)`` for a minibatch.

        For the MLP (no LSTM) path the inputs are simply flat. For the LSTM
        path the caller must pass ``batch_size`` and ``num_steps``; the
        observations are reshaped to ``(T, B, ...)`` and unrolled with the
        provided initial hidden state and dones mask.
        """
        features = self.forward_encoder(obs_uint8)
        features = self._apply_conditioning(features, persona)
        if self.use_lstm:
            assert batch_size is not None and num_steps is not None
            assert lstm_state is not None and dones is not None
            features = features.view(num_steps, batch_size, -1)
            hidden, _ = self._lstm_unroll(features, lstm_state, dones.float())
            hidden = hidden.reshape(num_steps * batch_size, -1)
        else:
            hidden = features
        logits = self.actor(hidden)
        value = self.critic(hidden).squeeze(-1)
        dist = torch.distributions.Categorical(logits=logits)
        log_prob = dist.log_prob(actions)
        entropy = dist.entropy()
        return log_prob, entropy, value
