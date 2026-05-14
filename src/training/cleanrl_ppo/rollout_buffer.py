"""On-policy rollout buffer with GAE.

Layout: per-update buffers of shape ``(T, N, ...)`` where:
- ``T`` = ``num_steps``
- ``N`` = ``num_envs * num_players`` (flattened agent batch)

All policies in this Phase 1 trainer are *shared* across agents and envs, so
flattening over agent and env axes early simplifies the rest of the trainer.
The buffer is reused across updates (overwritten in place) to avoid
allocation pressure.
"""

from __future__ import annotations

import numpy as np
import torch


class RolloutBuffer:
    def __init__(
        self,
        *,
        num_steps: int,
        batch: int,                # num_envs * num_players
        obs_shape: tuple[int, int, int],
        device: torch.device,
        use_lstm: bool,
        lstm_hidden: int,
    ) -> None:
        self.num_steps = num_steps
        self.batch = batch
        self.device = device
        self.use_lstm = use_lstm

        # Observations stored as uint8 to keep memory bounded; the encoder
        # casts to float on-device.
        self.obs = torch.zeros(
            (num_steps, batch, *obs_shape), dtype=torch.uint8, device=device
        )
        self.actions = torch.zeros((num_steps, batch), dtype=torch.long, device=device)
        self.logprobs = torch.zeros((num_steps, batch), dtype=torch.float32, device=device)
        self.values = torch.zeros((num_steps, batch), dtype=torch.float32, device=device)
        self.rewards = torch.zeros((num_steps, batch), dtype=torch.float32, device=device)
        # ``dones`` here is "the step that *started* with a fresh episode" — i.e.
        # done flag for env step t (terminal *after* this step). Used by both
        # GAE and the LSTM mask. We also store a per-step "done at start" mask
        # used to reset LSTM hidden state.
        self.dones = torch.zeros((num_steps, batch), dtype=torch.float32, device=device)
        # Persona id per (t, agent-slot). -1 sentinel means "no persona". The
        # trainer overwrites this on every write when persona conditioning is
        # enabled; downstream code looks up embeddings from the encoder table.
        self.persona_ids = torch.full(
            (num_steps, batch), -1, dtype=torch.long, device=device
        )
        if use_lstm:
            self.initial_lstm_h = torch.zeros((1, batch, lstm_hidden), device=device)
            self.initial_lstm_c = torch.zeros((1, batch, lstm_hidden), device=device)

    # ----- writes -----------------------------------------------------------

    def write(
        self,
        t: int,
        obs: torch.Tensor,
        action: torch.Tensor,
        logprob: torch.Tensor,
        value: torch.Tensor,
        reward: torch.Tensor,
        done: torch.Tensor,
        persona_ids: torch.Tensor | None = None,
    ) -> None:
        self.obs[t] = obs
        self.actions[t] = action
        self.logprobs[t] = logprob
        self.values[t] = value
        self.rewards[t] = reward
        self.dones[t] = done
        if persona_ids is not None:
            self.persona_ids[t] = persona_ids

    # ----- GAE --------------------------------------------------------------

    def compute_gae(
        self,
        last_value: torch.Tensor,    # (batch,) bootstrap value for s_T
        last_done: torch.Tensor,     # (batch,) "is s_T fresh because step T-1 terminated?"
        gamma: float,
        gae_lambda: float,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # CleanRL convention: ``self.dones[t]`` is the *before*-step flag —
        # "is the observation at index t the start of a fresh episode" (i.e.
        # did step t-1 terminate). Therefore the "did step t terminate" flag
        # that gates bootstrapping from ``values[t+1]`` is ``dones[t+1]`` for
        # t < T-1 and ``last_done`` for t == T-1.
        advantages = torch.zeros_like(self.rewards)
        last_gae = torch.zeros(self.batch, device=self.device)
        for t in reversed(range(self.num_steps)):
            if t == self.num_steps - 1:
                next_nonterminal = 1.0 - last_done.float()
                next_value = last_value
            else:
                next_nonterminal = 1.0 - self.dones[t + 1]
                next_value = self.values[t + 1]
            delta = (
                self.rewards[t] + gamma * next_value * next_nonterminal - self.values[t]
            )
            last_gae = delta + gamma * gae_lambda * next_nonterminal * last_gae
            advantages[t] = last_gae
        returns = advantages + self.values
        return advantages, returns
