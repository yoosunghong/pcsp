"""GRU trajectory encoder + InfoNCE consistency loss.

The encoder consumes per-step *behavioural* signals (action one-hot +
scalar reward) over a window of length ``T`` for each agent-slot, runs a
single-layer GRU, and returns a per-trajectory embedding ``z_traj`` in
``ℝ^{traj_dim}``. The InfoNCE head projects ``z_traj`` into the persona
embedding space and computes a temperature-scaled cross-entropy against
the frozen persona table.

Why action+reward (and not pixel features)? Two reasons:

1. Cost. The CNN encoder already runs ``T·B`` times per update inside
   PPO; reusing those features would couple trajectory-loss gradients
   to the policy trunk, which is exactly the entanglement Phase 3 is
   trying to *test*, not assume. Keeping the trajectory encoder
   separate gives a clean ablation: is consistency improving even when
   the trunk is shared?
2. Behavioural fingerprinting. Persona is a *behavior* claim. Encoding
   the (action, reward) trace forces the encoder to compress *what the
   policy did and what it got* into the embedding, which is what a
   downstream retrieval check is supposed to ground.

Determinism: the GRU uses orthogonal init and is fully deterministic
given the global torch seed. The InfoNCE temperature is a fixed scalar
buffer.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class TrajectoryEncoder(nn.Module):
    """GRU over (action one-hot, reward) sequences.

    Inputs:
        actions  : (T, B) long
        rewards  : (T, B) float
        dones    : (T, B) float — used to zero the hidden state at episode
                                  boundaries so trajectory embeddings
                                  represent at-most-one episode.

    Output:
        z_traj   : (B, traj_dim) — final hidden state (post-tanh-proj).
    """

    def __init__(
        self,
        *,
        num_actions: int,
        traj_dim: int = 64,
        hidden_dim: int = 128,
        include_reward: bool = True,
    ) -> None:
        super().__init__()
        self.num_actions = num_actions
        self.traj_dim = traj_dim
        self.hidden_dim = hidden_dim
        self.include_reward = include_reward

        in_dim = num_actions + (1 if include_reward else 0)
        self.gru = nn.GRU(in_dim, hidden_dim, num_layers=1)
        for name, p in self.gru.named_parameters():
            if "weight" in name:
                nn.init.orthogonal_(p, gain=1.0)
            elif "bias" in name:
                nn.init.zeros_(p)

        self.head = nn.Linear(hidden_dim, traj_dim)
        nn.init.orthogonal_(self.head.weight, gain=1.0)
        nn.init.zeros_(self.head.bias)

    def forward(
        self,
        actions: torch.Tensor,         # (T, B) long
        rewards: torch.Tensor,         # (T, B) float
        dones: torch.Tensor | None = None,  # (T, B) float
    ) -> torch.Tensor:
        T, B = actions.shape
        act_oh = F.one_hot(actions.long(), num_classes=self.num_actions).float()
        inputs = [act_oh]
        if self.include_reward:
            inputs.append(rewards.unsqueeze(-1))
        x = torch.cat(inputs, dim=-1)   # (T, B, in_dim)

        if dones is None:
            out, h = self.gru(x)
            return torch.tanh(self.head(h.squeeze(0)))

        # Done-aware unroll: zero hidden state at the *start* of any step
        # whose "before-step done" flag is set (CleanRL convention).
        h = torch.zeros(1, B, self.hidden_dim, device=x.device, dtype=x.dtype)
        outputs = []
        for t in range(T):
            mask = (1.0 - dones[t]).view(1, B, 1)
            h = h * mask
            out, h = self.gru(x[t : t + 1], h)
            outputs.append(out)
        return torch.tanh(self.head(h.squeeze(0)))


class InfoNCEHead(nn.Module):
    """Projects ``z_traj`` to persona space and computes InfoNCE.

    The contrast is between trajectory embeddings (anchors) and the
    *frozen* persona embedding table (candidates). The positive for the
    i-th trajectory is the persona embedding indexed by that
    trajectory's true persona id; negatives are the other K-1 persona
    embeddings.

    Loss form: cross-entropy(softmax(z_traj_proj · persona_table.T / τ),
    true_id), matching SimCLR's standard "one-hot contrastive" objective
    when the negative pool is the candidate vocabulary rather than other
    in-batch anchors.
    """

    def __init__(self, traj_dim: int, persona_dim: int, *, temperature: float = 0.1) -> None:
        super().__init__()
        self.proj = nn.Linear(traj_dim, persona_dim)
        nn.init.orthogonal_(self.proj.weight, gain=1.0)
        nn.init.zeros_(self.proj.bias)
        self.register_buffer("log_temperature", torch.tensor(float(torch.log(torch.tensor(temperature)))))

    @property
    def temperature(self) -> torch.Tensor:
        return self.log_temperature.exp()

    def logits(
        self,
        z_traj: torch.Tensor,
        persona_table: torch.Tensor,
        *,
        candidate_indices: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Trajectory-vs-candidate logits.

        ``candidate_indices`` (optional) restricts the contrast pool to a
        subset of the persona vocabulary — used at OOD-evaluation time to
        measure retrieval against only the train split, only the heldout
        split, or a mixed cast. When ``None`` the full table is used.
        """
        table = persona_table
        if candidate_indices is not None:
            table = persona_table.index_select(0, candidate_indices.long())
        z = F.normalize(self.proj(z_traj), dim=-1)             # (B, P)
        c = F.normalize(table, dim=-1)                         # (K', P)
        return (z @ c.t()) / self.temperature                  # (B, K')

    def forward(
        self,
        z_traj: torch.Tensor,
        persona_table: torch.Tensor,
        persona_ids: torch.Tensor,
        *,
        candidate_indices: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        logits = self.logits(z_traj, persona_table, candidate_indices=candidate_indices)
        # Remap target ids to positions inside ``candidate_indices``.
        if candidate_indices is not None:
            mapping = torch.full(
                (persona_table.shape[0],), -1, dtype=torch.long, device=logits.device
            )
            mapping[candidate_indices.long()] = torch.arange(
                candidate_indices.numel(), device=logits.device
            )
            persona_ids = mapping[persona_ids.long()]
        loss = F.cross_entropy(logits, persona_ids.long())
        with torch.no_grad():
            pred = logits.argmax(dim=-1)
            top1 = (pred == persona_ids).float().mean().item()
            top3_vals, top3_idx = logits.topk(min(3, logits.shape[-1]), dim=-1)
            top3 = (top3_idx == persona_ids.unsqueeze(-1)).any(dim=-1).float().mean().item()
        return loss, {"infonce_top1": top1, "infonce_top3": top3, "infonce_loss": float(loss.item())}
