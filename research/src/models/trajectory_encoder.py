"""
Trajectory encoder for PCSP consistency loss.

2-layer GRU encodes (obs_t, action_t) sequences into a trajectory embedding
aligned with the persona embedding space for the InfoNCE contrastive loss.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TrajectoryEncoder(nn.Module):
    """
    2-layer GRU: (obs, action_onehot) sequence → L2-normalized embedding.

    obs_seq:  (B, T, obs_dim)
    act_seq:  (B, T) LongTensor of action indices
    returns:  (B, output_dim) — aligned with persona_dim for contrastive loss
    """

    def __init__(
        self,
        obs_dim:    int,
        n_actions:  int,
        hidden_dim: int = 128,
        output_dim: int = 64,
    ):
        super().__init__()
        self.n_actions  = n_actions
        self.output_dim = output_dim
        self.gru = nn.GRU(
            obs_dim + n_actions,
            hidden_dim,
            num_layers=2,
            batch_first=True,
            dropout=0.0,
        )
        self.proj = nn.Linear(hidden_dim, output_dim)
        nn.init.xavier_uniform_(self.proj.weight)
        nn.init.zeros_(self.proj.bias)

    def forward(self, obs_seq: torch.Tensor, act_seq: torch.Tensor) -> torch.Tensor:
        act_onehot = F.one_hot(act_seq, self.n_actions).float()   # (B, T, n_actions)
        x = torch.cat([obs_seq, act_onehot], dim=-1)              # (B, T, obs+n_act)
        _, h = self.gru(x)                                        # h: (2, B, hidden)
        return F.normalize(self.proj(h[-1]), dim=-1)              # (B, output_dim)
