"""
PCSP Trainer — Persona-Conditioned Shared Policy.

L_total = L_PPO + λ₁ · L_consistency + λ₂ · L_diversity

L_consistency: InfoNCE contrastive — trajectory_emb ↔ persona_emb (same persona = positive)
L_diversity:   -E[KL(π(·|s,eₚ) ‖ π(·|s,eₚ'))] across sampled state-persona pairs

Ablation flags in PCSPConfig:
  use_film=False       → ConcatActorCritic (concat conditioning)
  lambda_consistency=0 → no consistency loss
  lambda_diversity=0   → no diversity loss
  freeze_projection=True → raw LLM embed (no LoRA training)
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS
from src.models.film import FiLMBlock, PersonaProjection
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.ppo_trainer import PPOConfig, _attach_gae

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024       # Qwen3-Embedding-0.6B


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class PCSPConfig(PPOConfig):
    # Co-training
    lambda_consistency:   float = 0.5
    lambda_diversity:     float = 0.01   # start small per risk mitigation; ramp up if stable
    temperature:          float = 0.07   # InfoNCE temperature
    # Trajectory encoder
    traj_hidden_dim:      int   = 128
    traj_output_dim:      int   = 64     # must equal persona_dim
    traj_lr:              float = 3e-4
    lora_lr:              float = 1e-4   # separate lr for LoRA projection
    # Diversity sampling
    n_diversity_states:   int   = 32
    n_diversity_personas: int   = 8      # personas to sample per diversity update
    # Ablations
    use_film:             bool  = True   # False → ConcatActorCritic
    freeze_projection:    bool  = False  # True → no LoRA gradient


# ── Actor-critics ──────────────────────────────────────────────────────────────

class PCSPActorCritic(nn.Module):
    """
    Shared FiLM-conditioned actor-critic for PCSP.

    A single shared PersonaProjection conditions both actor and critic,
    so the consistency loss trains the same projection used for behavior.

    context key: e_llm (B, 1024)
    """

    def __init__(
        self,
        obs_dim:     int   = OBS_DIM,
        n_actions:   int   = N_ACTS,
        persona_dim: int   = 64,
        llm_dim:     int   = LLM_DIM,
        lora_r:      int   = 16,
        freeze_proj: bool  = False,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)

        self.actor_b1   = FiLMBlock(obs_dim, 256, persona_dim)
        self.actor_b2   = FiLMBlock(256,     256, persona_dim)
        self.actor_b3   = FiLMBlock(256,     128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)

        self.critic_b1   = FiLMBlock(obs_dim, 256, persona_dim)
        self.critic_b2   = FiLMBlock(256,     128, persona_dim)
        self.critic_head = nn.Linear(128, 1)

    def _ep(self, e_llm: torch.Tensor) -> torch.Tensor:
        return self.persona_proj(e_llm)

    def action_logits(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        e_p = self._ep(e_llm)
        h = self.actor_b1(obs, e_p)
        h = self.actor_b2(h,   e_p)
        h = self.actor_b3(h,   e_p)
        return self.actor_head(h)

    def get_action(
        self, obs: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p = self._ep(e_llm)
        h = self.actor_b1(obs, e_p)
        h = self.actor_b2(h,   e_p)
        h = self.actor_b3(h,   e_p)
        logits = self.actor_head(h)

        h2 = self.critic_b1(obs, e_p)
        h2 = self.critic_b2(h2,  e_p)
        values = self.critic_head(h2).squeeze(-1)

        dist    = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        return actions, dist.log_prob(actions), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p = self._ep(e_llm)
        h = self.actor_b1(obs, e_p)
        h = self.actor_b2(h,   e_p)
        h = self.actor_b3(h,   e_p)
        logits = self.actor_head(h)

        h2 = self.critic_b1(obs, e_p)
        h2 = self.critic_b2(h2,  e_p)
        values = self.critic_head(h2).squeeze(-1)

        dist = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_llm": torch.cat([c["e_llm"] for c in ctxs], dim=0)}


class ConcatActorCritic(nn.Module):
    """
    Ablation: concat(obs, proj(e_llm)) → MLP, no FiLM.

    context key: e_llm (B, 1024)
    """

    def __init__(
        self,
        obs_dim:     int  = OBS_DIM,
        n_actions:   int  = N_ACTS,
        persona_dim: int  = 64,
        llm_dim:     int  = LLM_DIM,
        lora_r:      int  = 16,
        freeze_proj: bool = False,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)

        inp = obs_dim + persona_dim
        self.actor = nn.Sequential(
            nn.Linear(inp, 256), nn.ReLU(),
            nn.Linear(256, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, n_actions),
        )
        self.critic = nn.Sequential(
            nn.Linear(inp, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 1),
        )

    def _feats(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        return torch.cat([obs, self.persona_proj(e_llm)], dim=-1)

    def action_logits(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        return self.actor(self._feats(obs, e_llm))

    def get_action(
        self, obs: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x       = self._feats(obs, e_llm)
        logits  = self.actor(x)
        values  = self.critic(x).squeeze(-1)
        dist    = torch.distributions.Categorical(logits=logits)
        actions = dist.sample()
        return actions, dist.log_prob(actions), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x      = self._feats(obs, e_llm)
        logits = self.actor(x)
        values = self.critic(x).squeeze(-1)
        dist   = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_llm": torch.cat([c["e_llm"] for c in ctxs], dim=0)}


# ── Trainer ────────────────────────────────────────────────────────────────────

class PCSPTrainer:
    """
    PCSP trainer: PPO + InfoNCE consistency loss + diversity loss.

    all_e_llm: (N_train_personas, 1024) float32 tensor on device —
               pre-computed Qwen3 embeddings for all train personas,
               used by the diversity loss to sample diverse persona pairs.
    """

    def __init__(
        self,
        policy:       nn.Module,
        traj_encoder: TrajectoryEncoder,
        config:       PCSPConfig,
        device:       str = "cuda",
    ):
        self.policy       = policy
        self.traj_encoder = traj_encoder
        self.config       = config
        self.device       = torch.device(device if torch.cuda.is_available() else "cpu")
        self.policy.to(self.device)
        self.traj_encoder.to(self.device)
        self.iteration = 0
        self.metrics: list[dict] = []

        # LoRA projection at lower lr; rest of policy at default lr
        cfg = config
        proj_ids    = {id(p) for p in policy.persona_proj.parameters()}
        other_params = [p for p in policy.parameters()
                        if id(p) not in proj_ids and p.requires_grad]
        proj_params  = [p for p in policy.persona_proj.parameters()
                        if p.requires_grad]

        param_groups = [{"params": other_params, "lr": cfg.lr}]
        if proj_params:
            param_groups.append({"params": proj_params, "lr": cfg.lora_lr})
        self.optimizer      = Adam(param_groups)
        self.traj_optimizer = Adam(traj_encoder.parameters(), lr=cfg.traj_lr)

    # ── Rollout ────────────────────────────────────────────────────────────────

    def collect_rollout(
        self,
        make_env_fn:     Callable,
        persona_sampler: Callable,
        n_episodes:      int,
    ) -> tuple[list[dict], list[float], list[dict]]:
        """
        Collect n_episodes episodes.

        Returns:
          transitions: step-level data for PPO (with GAE attached)
          ep_rewards:  mean reward per episode
          trajectories: episode-level (obs_seq, act_seq, e_llm) for consistency loss
        """
        all_transitions: list[dict] = []
        ep_rewards:      list[float] = []
        trajectories:    list[dict]  = []

        for ep_idx in range(n_episodes):
            personas, agent_ctxs = persona_sampler()
            env = make_env_fn(personas)
            env.reset(seed=self.iteration * n_episodes + ep_idx)

            pending:         dict = {}
            ep_rew           = {a: 0.0 for a in env.possible_agents}
            ep_transitions:  list[dict] = []
            agent_obs_lists: dict = {a: [] for a in env.possible_agents}
            agent_act_lists: dict = {a: [] for a in env.possible_agents}

            for agent in env.agent_iter():
                obs, rew, term, trunc, _ = env.last()
                done = term or trunc

                if agent in pending:
                    s, a, lp, v, ctx = pending.pop(agent)
                    ep_transitions.append({
                        "agent": agent, "obs": s, "action": a,
                        "log_prob": lp, "reward": rew,
                        "value": v, "done": done, "context": ctx,
                    })

                ep_rew[agent] += rew

                if done:
                    env.step(None)
                    continue

                ctx = {k: (v.cpu() if isinstance(v, torch.Tensor) else v)
                       for k, v in agent_ctxs.get(agent, {}).items()}

                obs_t   = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
                ctx_dev = {k: (v.to(self.device) if isinstance(v, torch.Tensor) else v)
                           for k, v in ctx.items()}
                with torch.no_grad():
                    action_t, lp_t, val_t = self.policy.get_action(obs_t, **ctx_dev)

                agent_obs_lists[agent].append(obs.copy())
                agent_act_lists[agent].append(action_t.item())
                pending[agent] = (obs.copy(), action_t.item(), lp_t.item(), val_t.item(), ctx)
                env.step(action_t.item())

            for agent, (s, a, lp, v, ctx) in pending.items():
                ep_transitions.append({
                    "agent": agent, "obs": s, "action": a,
                    "log_prob": lp, "reward": 0.0,
                    "value": v, "done": True, "context": ctx,
                })

            env.close()
            _attach_gae(ep_transitions, self.config.gamma, self.config.gae_lambda)
            all_transitions.extend(ep_transitions)
            ep_rewards.append(sum(ep_rew.values()) / len(ep_rew))

            for agent in env.possible_agents:
                obs_list = agent_obs_lists[agent]
                act_list = agent_act_lists[agent]
                if len(obs_list) < 2:
                    continue
                e_llm_ctx = agent_ctxs.get(agent, {}).get("e_llm")
                if e_llm_ctx is None:
                    continue
                trajectories.append({
                    "obs_seq": np.stack(obs_list),                       # (T, obs_dim)
                    "act_seq": np.array(act_list, dtype=np.int64),       # (T,)
                    "e_llm":   e_llm_ctx.cpu().squeeze(0).float(),       # (llm_dim,)
                })

        advs     = np.array([t["advantage"] for t in all_transitions], dtype=np.float32)
        adv_mean = advs.mean()
        adv_std  = advs.std() + 1e-8
        for t in all_transitions:
            t["advantage"] = (t["advantage"] - adv_mean) / adv_std

        return all_transitions, ep_rewards, trajectories

    # ── Co-training losses ─────────────────────────────────────────────────────

    def _consistency_loss(self, trajectories: list[dict]) -> torch.Tensor:
        """
        InfoNCE contrastive loss.

        Positive pairs: (trajectory_emb_i, persona_emb_i) — same persona.
        Negative pairs: all other (i, j) in-batch combinations.
        Temperature T controls sharpness of the distribution.
        """
        if len(trajectories) < 2:
            return torch.tensor(0.0, device=self.device)

        max_T   = min(max(len(t["obs_seq"]) for t in trajectories), 200)
        obs_dim = trajectories[0]["obs_seq"].shape[-1]
        B       = len(trajectories)

        obs_batch = np.zeros((B, max_T, obs_dim), dtype=np.float32)
        act_batch = np.zeros((B, max_T),          dtype=np.int64)
        e_llm_list = []

        for k, traj in enumerate(trajectories):
            T = min(len(traj["obs_seq"]), max_T)
            obs_batch[k, :T] = traj["obs_seq"][:T]
            act_batch[k, :T] = traj["act_seq"][:T]
            e_llm_list.append(traj["e_llm"])

        obs_t    = torch.FloatTensor(obs_batch).to(self.device)     # (B, T, obs_dim)
        act_t    = torch.LongTensor(act_batch).to(self.device)      # (B, T)
        e_llm_t  = torch.stack(e_llm_list).to(self.device)          # (B, llm_dim)

        traj_emb    = self.traj_encoder(obs_t, act_t)               # (B, traj_output_dim)
        persona_emb = self.policy.persona_proj(e_llm_t)             # (B, persona_dim)

        sim    = torch.matmul(traj_emb, persona_emb.T) / self.config.temperature  # (B, B)
        labels = torch.arange(B, device=self.device)
        return F.cross_entropy(sim, labels)

    def _diversity_loss(
        self, transitions: list[dict], all_e_llm: torch.Tensor
    ) -> torch.Tensor:
        """
        Diversity loss: maximize KL divergence between different personas.

        Samples n_diversity_personas persona embeddings and n_diversity_states states.
        Computes all action distributions in one batched forward pass, then
        averages pairwise KL over all persona pairs.
        """
        cfg = self.config
        n_p = all_e_llm.shape[0]
        if n_p < 2:
            return torch.tensor(0.0, device=self.device)

        N        = len(transitions)
        n_states = min(cfg.n_diversity_states, N)
        n_sample = min(cfg.n_diversity_personas, n_p)

        state_idxs = np.random.choice(N, size=n_states, replace=False)
        p_idxs     = np.random.choice(n_p, size=n_sample, replace=False)

        obs = torch.FloatTensor(
            np.stack([transitions[i]["obs"] for i in state_idxs])
        ).to(self.device)  # (S, obs_dim)

        e_sample = all_e_llm[p_idxs]  # (P, llm_dim)

        # Batched forward: expand obs for each persona
        # (P, S, obs_dim) → (P*S, obs_dim)
        obs_rep = obs.unsqueeze(0).expand(n_sample, -1, -1).reshape(-1, obs.shape[-1])
        e_rep   = e_sample.unsqueeze(1).expand(-1, n_states, -1).reshape(-1, all_e_llm.shape[-1])

        logits = self.policy.action_logits(obs_rep, e_rep)          # (P*S, n_actions)
        logits = logits.view(n_sample, n_states, -1)                 # (P, S, n_actions)
        logits = logits.clamp(-20.0, 20.0)                           # guard against extreme values

        log_probs = F.log_softmax(logits, dim=-1)  # (P, S, n_actions)
        log_probs = log_probs.clamp(min=-10.0)     # prevent -inf → NaN in kl_div
        probs     = log_probs.exp()

        total_kl = torch.tensor(0.0, device=self.device)
        n_pairs  = 0
        for i in range(n_sample):
            for j in range(i + 1, n_sample):
                kl = F.kl_div(log_probs[i], probs[j], reduction="batchmean")
                if torch.isnan(kl) or torch.isinf(kl):
                    continue
                kl = kl.clamp(max=2.0)
                total_kl = total_kl + kl
                n_pairs += 1

        return -(total_kl / max(1, n_pairs))

    # ── PPO + co-training update ───────────────────────────────────────────────

    def update(
        self,
        transitions:  list[dict],
        trajectories: list[dict],
        all_e_llm:    torch.Tensor,
    ) -> dict:
        """
        n_epochs of PPO mini-batch updates, plus one co-training update per epoch.
        """
        cfg = self.config
        N   = len(transitions)

        obs_t    = torch.FloatTensor(np.stack([t["obs"] for t in transitions])).to(self.device)
        acts_t   = torch.LongTensor([t["action"]   for t in transitions]).to(self.device)
        lps_t    = torch.FloatTensor([t["log_prob"] for t in transitions]).to(self.device)
        advs_t   = torch.FloatTensor([t["advantage"] for t in transitions]).to(self.device)
        rets_t   = torch.FloatTensor([t["return"]   for t in transitions]).to(self.device)
        contexts = [t["context"] for t in transitions]

        stats = dict(policy_loss=0., value_loss=0., entropy=0.,
                     consistency_loss=0., diversity_loss=0.)
        n_ppo = 0

        for _ in range(cfg.n_epochs):
            # PPO mini-batch loop
            perm = torch.randperm(N)
            for start in range(0, N, cfg.batch_size):
                idx      = perm[start:start + cfg.batch_size].tolist()
                batch_ctx = self.policy.stack_contexts([contexts[i] for i in idx])
                batch_ctx = {k: (v.to(self.device) if isinstance(v, torch.Tensor) else v)
                             for k, v in batch_ctx.items()}

                new_lps, vals, ent = self.policy.evaluate_actions(
                    obs_t[idx], acts_t[idx], **batch_ctx
                )

                ratio    = (new_lps - lps_t[idx]).exp()
                adv_b    = advs_t[idx]
                pol_loss = -torch.min(
                    ratio * adv_b,
                    torch.clamp(ratio, 1 - cfg.clip_eps, 1 + cfg.clip_eps) * adv_b,
                ).mean()
                val_loss = F.mse_loss(vals, rets_t[idx])
                entropy  = ent.mean()
                loss     = pol_loss + cfg.value_coef * val_loss - cfg.entropy_coef * entropy

                self.optimizer.zero_grad()
                loss.backward()
                grad_norm = nn.utils.clip_grad_norm_(self.policy.parameters(), cfg.max_grad_norm)
                if torch.isnan(grad_norm) or torch.isinf(grad_norm):
                    self.optimizer.zero_grad()
                    continue
                self.optimizer.step()

                stats["policy_loss"] += pol_loss.item()
                stats["value_loss"]  += val_loss.item()
                stats["entropy"]     += entropy.item()
                n_ppo += 1

            # Co-training: once per epoch (not per mini-batch)
            con_loss = self._consistency_loss(trajectories) * cfg.lambda_consistency
            div_loss = self._diversity_loss(transitions, all_e_llm) * cfg.lambda_diversity
            co_loss  = con_loss + div_loss

            if co_loss.requires_grad and not (torch.isnan(co_loss) or torch.isinf(co_loss)):
                self.optimizer.zero_grad()
                self.traj_optimizer.zero_grad()
                co_loss.backward()
                gn1 = nn.utils.clip_grad_norm_(self.policy.parameters(), cfg.max_grad_norm)
                gn2 = nn.utils.clip_grad_norm_(self.traj_encoder.parameters(), cfg.max_grad_norm)
                if not (torch.isnan(gn1) or torch.isinf(gn1) or
                        torch.isnan(gn2) or torch.isinf(gn2)):
                    self.optimizer.step()
                    self.traj_optimizer.step()
                else:
                    self.optimizer.zero_grad()
                    self.traj_optimizer.zero_grad()

            stats["consistency_loss"] += con_loss.item()
            stats["diversity_loss"]   += div_loss.item()

        for k in ("policy_loss", "value_loss", "entropy"):
            stats[k] /= max(1, n_ppo)
        for k in ("consistency_loss", "diversity_loss"):
            stats[k] /= max(1, cfg.n_epochs)

        return stats

    # ── Main training loop ─────────────────────────────────────────────────────

    def train(
        self,
        make_env_fn:     Callable,
        persona_sampler: Callable,
        all_e_llm_np:    np.ndarray,
        n_iterations:    int | None = None,
        log_fn:          Callable | None = None,
    ) -> list[dict]:
        cfg      = self.config
        n_iter   = n_iterations or cfg.total_iterations
        all_e_llm = torch.FloatTensor(all_e_llm_np.astype(np.float32)).to(self.device)

        for i in range(n_iter):
            self.iteration = i

            transitions, ep_rewards, trajectories = self.collect_rollout(
                make_env_fn, persona_sampler, cfg.n_episodes_per_iter
            )
            update_stats = self.update(transitions, trajectories, all_e_llm)

            metric = {
                "iteration":      i,
                "mean_ep_reward": float(np.mean(ep_rewards)),
                "n_transitions":  len(transitions),
                **update_stats,
            }
            self.metrics.append(metric)

            if log_fn:
                log_fn(metric)
            elif i % cfg.log_interval == 0:
                print(
                    f"[{i:4d}/{n_iter}] reward={metric['mean_ep_reward']:6.3f}  "
                    f"pol={metric['policy_loss']:.4f}  "
                    f"con={metric['consistency_loss']:.4f}  "
                    f"div={metric['diversity_loss']:.4f}  "
                    f"n={metric['n_transitions']}"
                )

        return self.metrics


# ── Training entry point ───────────────────────────────────────────────────────

def train_pcsp(
    mode:          str        = "full",
    personas_json: str | Path = "data/personas/train_240.json",
    embed_npy:     str | Path = "results/embeddings/persona_embeddings_300.npy",
    config:        PCSPConfig | None = None,
    device:        str        = "cuda",
    output_dir:    str | Path = "results/pcsp",
    n_iterations:  int | None = None,
) -> dict:
    """
    Train PCSP (or an ablation variant) and save results.

    mode options:
      full          — full PCSP (FiLM + consistency + diversity)
      no_consist    — λ₁ = 0 (no consistency loss)
      no_diverse    — λ₂ = 0 (no diversity loss)
      concat        — concat conditioning instead of FiLM
      frozen_proj   — freeze LoRA projection (raw LLM embed)
    """
    root       = Path(__file__).resolve().parents[2]
    output_dir = root / output_dir / mode
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(root / personas_json) as f:
        personas_data = json.load(f)

    # Load pre-computed Qwen3 embeddings; index = persona_id - 1
    all_emb_300 = np.load(root / embed_npy)                        # (300, 1024) float16
    train_idxs  = [p["id"] - 1 for p in personas_data]
    train_emb   = all_emb_300[train_idxs].astype(np.float32)       # (240, 1024)
    embed_tensors = [torch.FloatTensor(train_emb[i]).unsqueeze(0)
                     for i in range(len(personas_data))]

    if config is None:
        config = PCSPConfig()

    # Apply ablation mode to config
    if mode == "no_consist":
        config.lambda_consistency = 0.0
    elif mode == "no_diverse":
        config.lambda_diversity = 0.0
    elif mode == "concat":
        config.use_film = False
    elif mode == "frozen_proj":
        config.freeze_projection = True

    rng = np.random.default_rng(config.seed)

    def persona_sampler():
        idxs    = rng.choice(len(personas_data), size=4, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_llm": embed_tensors[idxs[j]]}
            for j in range(4)
        }
        return personas, agent_ctxs

    def make_env_fn(personas):
        return MiniInzoiEnv(personas=personas, max_steps=200)

    # Build policy
    if config.use_film:
        policy = PCSPActorCritic(
            OBS_DIM, N_ACTS,
            persona_dim=config.traj_output_dim,
            llm_dim=LLM_DIM,
            freeze_proj=config.freeze_projection,
        )
    else:
        policy = ConcatActorCritic(
            OBS_DIM, N_ACTS,
            persona_dim=config.traj_output_dim,
            llm_dim=LLM_DIM,
            freeze_proj=config.freeze_projection,
        )

    traj_encoder = TrajectoryEncoder(
        obs_dim=OBS_DIM,
        n_actions=N_ACTS,
        hidden_dim=config.traj_hidden_dim,
        output_dim=config.traj_output_dim,
    )
    trainer = PCSPTrainer(policy, traj_encoder, config, device)

    n_params       = sum(p.numel() for p in policy.parameters())
    n_traj_params  = sum(p.numel() for p in traj_encoder.parameters())
    print(
        f"\n[PCSP:{mode}] policy={n_params:,}  traj_enc={n_traj_params:,}  "
        f"λ₁={config.lambda_consistency}  λ₂={config.lambda_diversity}  "
        f"device={trainer.device}"
    )

    t0      = time.time()
    metrics = trainer.train(
        make_env_fn, persona_sampler, train_emb,
        n_iterations=n_iterations,
    )
    elapsed = time.time() - t0
    print(f"[PCSP:{mode}] done in {elapsed:.1f}s")

    torch.save(policy.state_dict(),       output_dir / "policy.pt")
    torch.save(traj_encoder.state_dict(), output_dir / "traj_encoder.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({"mode": mode, "metrics": metrics, "elapsed_sec": elapsed}, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[PCSP:{mode}] final reward={final.get('mean_ep_reward', 'N/A'):.3f}")
    return final
