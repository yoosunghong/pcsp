"""
PPO trainer shared by all Phase 3 baselines and PCSP.

Handles PettingZoo AEC rollout collection, GAE advantage estimation,
and the standard PPO clip update.

Policy interface (all baselines must implement):
    policy.get_action(obs: Tensor, **ctx) -> (actions, log_probs, values)
    policy.evaluate_actions(obs: Tensor, actions: Tensor, **ctx) -> (log_probs, values, entropy)
    policy.stack_contexts(ctxs: list[dict]) -> dict   # batch context dicts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam


@dataclass
class PPOConfig:
    # Rollout
    total_iterations: int = 300
    n_episodes_per_iter: int = 8     # complete episodes per rollout
    # PPO update
    n_epochs: int = 4
    batch_size: int = 256
    # Hyperparams (from PLAN.md)
    lr: float = 3e-4
    clip_eps: float = 0.2
    gamma: float = 0.99
    gae_lambda: float = 0.95
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    # Misc
    seed: int = 42
    log_interval: int = 20


class PPOTrainer:
    """
    Generic PPO trainer for PettingZoo AEC environments.

    env is re-created each episode via make_env_fn(personas) so that
    different persona combinations can be sampled each episode.
    """

    def __init__(
        self,
        policy: nn.Module,
        config: PPOConfig,
        device: str = "cuda",
    ):
        self.policy = policy
        self.config = config
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.policy.to(self.device)
        self.optimizer = Adam(policy.parameters(), lr=config.lr)
        self.iteration = 0
        self.metrics: list[dict] = []

    # ── Rollout collection ─────────────────────────────────────────────────────

    def collect_rollout(
        self,
        make_env_fn: Callable,
        persona_sampler: Callable,
        n_episodes: int,
    ) -> tuple[list[dict], list[float]]:
        """
        Collect n_episodes complete episodes from the AEC environment.

        persona_sampler() -> (personas: list[PersonaConfig],
                              agent_ctxs: dict[agent_name -> dict of Tensors])

        make_env_fn(personas) -> AECEnv

        Returns:
          transitions: list of dicts, each with obs/action/log_prob/reward/value/done/advantage/return/context
          ep_rewards: mean reward per episode
        """
        all_transitions: list[dict] = []
        ep_rewards: list[float] = []

        for ep_idx in range(n_episodes):
            personas, agent_ctxs = persona_sampler()
            env = make_env_fn(personas)
            env.reset(seed=self.iteration * n_episodes + ep_idx)

            # pending[agent] = (obs, action, log_prob, value, context)
            pending: dict = {}
            ep_rew = {a: 0.0 for a in env.possible_agents}
            ep_transitions: list[dict] = []

            for agent in env.agent_iter():
                obs, rew, term, trunc, _ = env.last()
                done = term or trunc

                # Complete the previous transition for this agent
                if agent in pending:
                    s, a, lp, v, ctx = pending.pop(agent)
                    ep_transitions.append({
                        "agent": agent,
                        "obs": s,
                        "action": a,
                        "log_prob": lp,
                        "reward": rew,
                        "value": v,
                        "done": done,
                        "context": ctx,
                    })

                ep_rew[agent] += rew

                if done:
                    env.step(None)
                    continue

                # Get context for this agent (CPU tensors)
                ctx = {k: (v.cpu() if isinstance(v, torch.Tensor) else v)
                       for k, v in agent_ctxs.get(agent, {}).items()}

                # Sample action
                obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self.device)
                ctx_dev = {k: (v.to(self.device) if isinstance(v, torch.Tensor) else v)
                           for k, v in ctx.items()}
                with torch.no_grad():
                    action_t, lp_t, val_t = self.policy.get_action(obs_t, **ctx_dev)

                pending[agent] = (
                    obs.copy(),
                    action_t.item(),
                    lp_t.item(),
                    val_t.item(),
                    ctx,
                )
                env.step(action_t.item())

            # Flush any pending (should be empty when all agents terminate together)
            for agent, (s, a, lp, v, ctx) in pending.items():
                ep_transitions.append({
                    "agent": agent, "obs": s, "action": a,
                    "log_prob": lp, "reward": 0.0, "value": v,
                    "done": True, "context": ctx,
                })

            env.close()

            # Compute GAE per agent over this episode
            _attach_gae(ep_transitions, self.config.gamma, self.config.gae_lambda)
            all_transitions.extend(ep_transitions)
            ep_rewards.append(sum(ep_rew.values()) / len(ep_rew))

        # Normalize advantages globally
        advs = np.array([t["advantage"] for t in all_transitions], dtype=np.float32)
        adv_mean, adv_std = advs.mean(), advs.std() + 1e-8
        for t in all_transitions:
            t["advantage"] = (t["advantage"] - adv_mean) / adv_std

        return all_transitions, ep_rewards

    # ── PPO update ─────────────────────────────────────────────────────────────

    def update(self, transitions: list[dict]) -> dict:
        """Run n_epochs of PPO on the collected transitions."""
        N = len(transitions)
        cfg = self.config

        obs_t   = torch.FloatTensor(np.array([t["obs"] for t in transitions])).to(self.device)
        acts_t  = torch.LongTensor([t["action"] for t in transitions]).to(self.device)
        lps_t   = torch.FloatTensor([t["log_prob"] for t in transitions]).to(self.device)
        advs_t  = torch.FloatTensor([t["advantage"] for t in transitions]).to(self.device)
        rets_t  = torch.FloatTensor([t["return"] for t in transitions]).to(self.device)
        contexts = [t["context"] for t in transitions]

        total_pol_loss = 0.0
        total_val_loss = 0.0
        total_entropy  = 0.0
        n_updates = 0

        for _ in range(cfg.n_epochs):
            perm = torch.randperm(N)
            for start in range(0, N, cfg.batch_size):
                idx = perm[start:start + cfg.batch_size].tolist()
                batch_ctx = self.policy.stack_contexts([contexts[i] for i in idx])
                # Move batch context to device
                batch_ctx = {k: (v.to(self.device) if isinstance(v, torch.Tensor) else v)
                             for k, v in batch_ctx.items()}

                new_lps, vals, ent = self.policy.evaluate_actions(
                    obs_t[idx], acts_t[idx], **batch_ctx
                )

                ratio = (new_lps - lps_t[idx]).exp()
                adv_b = advs_t[idx]

                pol_loss = -torch.min(
                    ratio * adv_b,
                    torch.clamp(ratio, 1 - cfg.clip_eps, 1 + cfg.clip_eps) * adv_b,
                ).mean()
                val_loss = F.mse_loss(vals, rets_t[idx])
                entropy  = ent.mean()

                loss = pol_loss + cfg.value_coef * val_loss - cfg.entropy_coef * entropy

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), cfg.max_grad_norm)
                self.optimizer.step()

                total_pol_loss += pol_loss.item()
                total_val_loss += val_loss.item()
                total_entropy  += entropy.item()
                n_updates += 1

        denom = max(1, n_updates)
        return {
            "policy_loss": total_pol_loss / denom,
            "value_loss":  total_val_loss / denom,
            "entropy":     total_entropy  / denom,
        }

    # ── Main training loop ─────────────────────────────────────────────────────

    def train(
        self,
        make_env_fn: Callable,
        persona_sampler: Callable,
        n_iterations: int | None = None,
        log_fn: Callable | None = None,
    ) -> list[dict]:
        cfg = self.config
        n_iter = n_iterations or cfg.total_iterations

        for i in range(n_iter):
            self.iteration = i

            transitions, ep_rewards = self.collect_rollout(
                make_env_fn, persona_sampler, cfg.n_episodes_per_iter
            )
            update_stats = self.update(transitions)

            metric = {
                "iteration":        i,
                "mean_ep_reward":   float(np.mean(ep_rewards)),
                "n_transitions":    len(transitions),
                **update_stats,
            }
            self.metrics.append(metric)

            if log_fn:
                log_fn(metric)
            elif i % cfg.log_interval == 0:
                print(
                    f"[{i:4d}/{n_iter}] reward={metric['mean_ep_reward']:6.3f}  "
                    f"pol={metric['policy_loss']:.4f}  "
                    f"val={metric['value_loss']:.4f}  "
                    f"ent={metric['entropy']:.4f}  "
                    f"n={metric['n_transitions']}"
                )

        return self.metrics


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_gae(
    rewards: list[float],
    values:  list[float],
    dones:   list[bool],
    gamma:   float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    """GAE-Lambda for a single agent's trajectory."""
    T = len(rewards)
    advantages = np.zeros(T, dtype=np.float32)
    gae = 0.0

    for t in reversed(range(T)):
        next_val = 0.0 if dones[t] or t == T - 1 else values[t + 1]
        delta = rewards[t] + gamma * next_val * (not dones[t]) - values[t]
        gae = delta + gamma * gae_lambda * (not dones[t]) * gae
        advantages[t] = gae

    returns = advantages + np.array(values, dtype=np.float32)
    return advantages, returns


def _attach_gae(
    transitions: list[dict],
    gamma: float,
    gae_lambda: float,
) -> None:
    """Compute and attach advantage/return in-place, grouped by agent."""
    from collections import defaultdict

    agent_idx: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(transitions):
        agent_idx[t["agent"]].append(i)

    for agent, idxs in agent_idx.items():
        ts = [transitions[i] for i in idxs]
        rews  = [t["reward"] for t in ts]
        vals  = [t["value"]  for t in ts]
        dones = [t["done"]   for t in ts]
        advs, rets = _compute_gae(rews, vals, dones, gamma, gae_lambda)
        for i, (adv, ret) in zip(idxs, zip(advs, rets)):
            transitions[i]["advantage"] = float(adv)
            transitions[i]["return"]    = float(ret)
