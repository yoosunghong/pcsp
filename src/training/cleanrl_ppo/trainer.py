"""CleanRL-style PPO trainer for Melting Pot substrates.

Single-policy shared across all (env, player) slots — Phase 1 does not yet
implement persona conditioning, so this is a vanilla shared-policy PPO.

Episode-return bookkeeping: Melting Pot substrates have fixed horizons. The
``SingleSubstrateEnv`` wrapper auto-resets on ``truncated=True`` and we treat
the ``done`` flag at that step as marking the *next* observation as the
start of a new episode. We accumulate per-(env, player) returns and snapshot
them at done boundaries.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import os

# Disable torch._dynamo before importing torch. Some torch builds attempt to
# JIT-compile the Adam optimizer step at construction time, which crashes if
# the CUDA driver on the host is older than the torch build expects (we have
# seen this with torch 2.12+cu130 on a 12.0 driver). Dynamo is unnecessary
# for this trainer, so we disable it unconditionally to keep startup robust
# across hosts.
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import numpy as np
import torch

# Eagerly import torch._dynamo before constructing optimizers. On some
# torch+CUDA combinations (we hit this with torch 2.12+cu130 against an older
# CUDA driver), lazy import of dynamo inside ``Optimizer.add_param_group``
# segfaults during triton initialization. Importing it eagerly at module load
# avoids the crash; dynamo itself is still effectively disabled because we
# never call ``torch.compile``.
import torch._dynamo  # noqa: F401

import torch.nn as nn
import torch.nn.functional as F

from .config import PPOConfig
from .networks import ActorCritic
from .rollout_buffer import RolloutBuffer
from src.persona import (
    InfoNCEHead,
    TrajectoryEncoder,
    build_assigner,
    build_conditioning_head,
    build_encoder,
    load_personas,
)


# ----- Utilities -------------------------------------------------------------


def resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ----- Trainer ---------------------------------------------------------------


class PPOTrainer:
    def __init__(self, cfg: PPOConfig, env, *, writer=None) -> None:
        self.cfg = cfg
        self.env = env  # AsyncVectorMeltingPot or SyncVectorMeltingPot
        self.device = resolve_device(cfg.device)
        self.writer = writer

        spec = env.spec
        self.num_envs = env.num_envs
        self.num_players = env.num_players
        self.batch = self.num_envs * self.num_players

        # ----- Persona conditioning -------------------------------------------
        self.persona_enabled = cfg.persona_conditioning != "none"
        self.persona_registry = None
        self.persona_encoder = None
        self.persona_assigner = None
        conditioning_head = None
        if self.persona_enabled:
            self.persona_registry = load_personas(cfg.persona_path)
            self.persona_encoder = build_encoder(
                self.persona_registry,
                source=cfg.persona_source,
                embedding_dim=cfg.persona_embedding_dim,
                cache_path=cfg.persona_cache_path,
                seed=cfg.persona_seed,
            ).to(self.device)
            self.persona_assigner = build_assigner(
                self.persona_registry,
                mode=cfg.persona_assignment,
                num_envs=self.num_envs,
                num_players=self.num_players,
                seed=cfg.seed ^ cfg.persona_seed,
                split=cfg.persona_split,
                population_kind=cfg.persona_population_kind,
            )
            conditioning_head = build_conditioning_head(
                mode=cfg.persona_conditioning,
                feature_dim=cfg.feature_dim,
                persona_dim=self.persona_encoder.embedding_dim,
            )

        self.agent = ActorCritic(
            obs_height=spec.obs_height,
            obs_width=spec.obs_width,
            obs_channels=spec.obs_channels,
            num_actions=spec.num_actions,
            feature_dim=cfg.feature_dim,
            use_lstm=cfg.use_lstm,
            lstm_hidden=cfg.lstm_hidden,
            conditioning=conditioning_head,
        ).to(self.device)

        # ----- Trajectory consistency (Phase 3) -------------------------------
        self.trajectory_encoder: TrajectoryEncoder | None = None
        self.infonce_head: InfoNCEHead | None = None
        self.kl_diversity_enabled = (
            cfg.kl_diversity_coef > 0.0 and self.persona_enabled
        )
        self.infonce_enabled = cfg.infonce_coef > 0.0 and self.persona_enabled
        if self.infonce_enabled:
            self.trajectory_encoder = TrajectoryEncoder(
                num_actions=spec.num_actions,
                traj_dim=cfg.infonce_traj_dim,
                hidden_dim=cfg.infonce_traj_hidden,
                include_reward=cfg.infonce_include_reward,
            ).to(self.device)
            self.infonce_head = InfoNCEHead(
                traj_dim=cfg.infonce_traj_dim,
                persona_dim=self.persona_encoder.embedding_dim,
                temperature=cfg.infonce_temperature,
            ).to(self.device)
            # Phase 5 §2: training-time contrast-pool restriction.
            # When cfg.infonce_candidate_pool == "train", limit candidates
            # to persona_split indices so held-out slots receive no gradient
            # signal. None means "full vocabulary" (Phase 4/5 §1 behaviour).
            self._infonce_train_candidates: torch.Tensor | None = None
            if cfg.infonce_candidate_pool == "train":
                train_idx = self.persona_registry.split_indices(cfg.persona_split)
                self._infonce_train_candidates = torch.tensor(
                    train_idx, dtype=torch.long, device=self.device
                )
            elif cfg.infonce_candidate_pool != "full":
                raise ValueError(
                    f"Unknown infonce_candidate_pool: {cfg.infonce_candidate_pool!r}. "
                    "Expected 'full' or 'train'."
                )
        if self.kl_diversity_enabled and cfg.use_lstm:
            raise ValueError("kl_diversity_coef > 0 is not supported with use_lstm=True.")

        param_groups = [{"params": list(self.agent.parameters())}]
        if self.trajectory_encoder is not None:
            traj_lr = cfg.traj_encoder_lr if cfg.traj_encoder_lr is not None else cfg.learning_rate
            param_groups.append({
                "params": list(self.trajectory_encoder.parameters()) + list(self.infonce_head.parameters()),
                "lr": traj_lr,
            })
        self.optimizer = torch.optim.Adam(
            param_groups, lr=cfg.learning_rate, eps=1e-5
        )

        self.buffer = RolloutBuffer(
            num_steps=cfg.num_steps,
            batch=self.batch,
            obs_shape=spec.rgb_shape,
            device=self.device,
            use_lstm=cfg.use_lstm,
            lstm_hidden=cfg.lstm_hidden,
        )

        self._lstm_state = None
        if cfg.use_lstm:
            self._lstm_state = self.agent.initial_lstm_state(self.batch, self.device)

        self._next_obs: torch.Tensor | None = None
        self._next_done: torch.Tensor | None = None
        self._current_persona: torch.Tensor | None = None  # (batch,) long

        # Diagnostics accumulators (reset per diagnostics window).
        self._diag_action_counts: dict[int, np.ndarray] = {}
        self._diag_reward_sum: dict[int, float] = {}
        self._diag_reward_count: dict[int, int] = {}
        self._diag_episode_returns: dict[int, list[float]] = {}
        self._diag_positive_reward_count: dict[int, int] = {}
        self._persona_episode_returns: np.ndarray | None = None

        # Bookkeeping
        self.global_step = 0
        self.update_idx = 0
        self.episode_returns = np.zeros(self.batch, dtype=np.float32)
        self.episode_lengths = np.zeros(self.batch, dtype=np.int64)
        self.completed_returns: list[float] = []
        self.completed_lengths: list[int] = []
        self.reset_count = 0

    # ----- Setup ------------------------------------------------------------

    def initialize(self) -> None:
        obs = self.env.reset(seed=self.cfg.seed)
        # obs: (num_envs, num_players, H, W, C) → (batch, H, W, C)
        obs_flat = obs.reshape(self.batch, *obs.shape[2:])
        self._next_obs = torch.as_tensor(obs_flat, device=self.device, dtype=torch.uint8)
        self._next_done = torch.zeros(self.batch, device=self.device, dtype=torch.float32)

        if self.persona_assigner is not None:
            assignment = self.persona_assigner.initial()  # (E, P)
            self._current_persona = torch.as_tensor(
                assignment.reshape(self.batch), device=self.device, dtype=torch.long
            )
            self._log_persona_assignment(reset_kind="initial")
            self._persona_episode_returns = np.zeros(self.batch, dtype=np.float32)

    # ----- Rollout ----------------------------------------------------------

    @torch.no_grad()
    def collect_rollout(self) -> dict[str, float]:
        assert self._next_obs is not None and self._next_done is not None
        if self.cfg.use_lstm:
            self.buffer.initial_lstm_h.copy_(self._lstm_state[0])
            self.buffer.initial_lstm_c.copy_(self._lstm_state[1])

        t0 = time.time()
        for t in range(self.cfg.num_steps):
            persona_emb = self._persona_embedding(self._current_persona)
            action, log_prob, value, new_state = self.agent.act(
                self._next_obs,
                lstm_state=self._lstm_state,
                done=self._next_done if self.cfg.use_lstm else None,
                persona=persona_emb,
            )
            if self.cfg.use_lstm:
                self._lstm_state = new_state

            actions_np = action.cpu().numpy().reshape(self.num_envs, self.num_players)
            next_obs_np, rew_np, done_np, _trunc_np, _infos = self.env.step(actions_np)
            self.global_step += self.num_envs * self.num_players

            # Per-(env, player) reward / done flatten.
            rew_flat = rew_np.reshape(self.batch).astype(np.float32)
            # Done in Melting Pot is synchronous across players within an env,
            # so broadcast the per-env done to per-(env, player).
            done_per_env = done_np.astype(np.float32)
            done_flat = np.repeat(done_per_env, self.num_players).astype(np.float32)

            # Bookkeeping ----------------------------------------------------
            self.episode_returns += rew_flat
            self.episode_lengths += 1
            for i in np.where(done_flat > 0.5)[0]:
                self.completed_returns.append(float(self.episode_returns[i]))
                self.completed_lengths.append(int(self.episode_lengths[i]))
                self.episode_returns[i] = 0.0
                self.episode_lengths[i] = 0
            self.reset_count += int(done_per_env.sum())

            # CleanRL convention: dones[t] is the *before-step* done flag, i.e.
            # "is the obs at index t the start of a fresh episode (did step
            # t-1 terminate)". So we write ``self._next_done`` *before* the
            # update, and only then advance ``self._next_done`` with the
            # post-step done.
            self.buffer.write(
                t,
                self._next_obs,
                action,
                log_prob,
                value,
                torch.as_tensor(rew_flat, device=self.device),
                self._next_done,
                persona_ids=self._current_persona,
            )

            # Per-persona diagnostics accumulators ----------------------------
            if self.persona_enabled and self._current_persona is not None:
                self._update_persona_diagnostics(
                    self._current_persona.cpu().numpy(),
                    action.cpu().numpy(),
                    rew_flat,
                    done_flat,
                )

            next_obs_flat = next_obs_np.reshape(self.batch, *next_obs_np.shape[2:])
            self._next_obs = torch.as_tensor(next_obs_flat, device=self.device, dtype=torch.uint8)
            self._next_done = torch.as_tensor(done_flat, device=self.device)

            # On episode boundary, advance persona assignment (env-level done).
            if self.persona_assigner is not None and done_per_env.any():
                new_assignment = self.persona_assigner.on_done(done_per_env.astype(bool))
                self._current_persona = torch.as_tensor(
                    new_assignment.reshape(self.batch),
                    device=self.device,
                    dtype=torch.long,
                )
                self._log_persona_assignment(reset_kind="episode")

        elapsed = time.time() - t0
        sps = (self.cfg.num_steps * self.num_envs * self.num_players) / max(elapsed, 1e-6)
        return {"rollout/sec": elapsed, "rollout/sps": sps}

    # ----- Update -----------------------------------------------------------

    def update(self) -> dict[str, float]:
        cfg = self.cfg

        with torch.no_grad():
            last_persona = self._persona_embedding(self._current_persona)
            if cfg.use_lstm:
                # Bootstrap value uses current LSTM state.
                features = self.agent.forward_encoder(self._next_obs)
                features = self.agent._apply_conditioning(features, last_persona)
                features = features.unsqueeze(0)
                hidden, _ = self.agent._lstm_unroll(
                    features, self._lstm_state, self._next_done.unsqueeze(0)
                )
                hidden = hidden.squeeze(0)
                last_value = self.agent.critic(hidden).squeeze(-1)
            else:
                features = self.agent.forward_encoder(self._next_obs)
                features = self.agent._apply_conditioning(features, last_persona)
                last_value = self.agent.critic(features).squeeze(-1)

        advantages, returns = self.buffer.compute_gae(
            last_value, self._next_done, cfg.gamma, cfg.gae_lambda
        )

        T = cfg.num_steps
        B = self.batch
        b_obs = self.buffer.obs.reshape(T * B, *self.buffer.obs.shape[2:])
        b_actions = self.buffer.actions.reshape(T * B)
        b_logprobs = self.buffer.logprobs.reshape(T * B)
        b_values = self.buffer.values.reshape(T * B)
        b_advantages = advantages.reshape(T * B)
        b_returns = returns.reshape(T * B)
        b_dones = self.buffer.dones  # (T, B) kept for LSTM unroll
        b_persona_ids = self.buffer.persona_ids  # (T, B) long

        # Optimization loop --------------------------------------------------
        clipfracs = []
        approx_kls = []
        pg_losses = []
        v_losses = []
        ent_losses = []
        kl_div_terms: list[float] = []
        infonce_terms: list[float] = []
        infonce_top1: list[float] = []
        infonce_top3: list[float] = []

        # KL-diversity uses a per-update fixed persona permutation so the
        # signal does not flip every minibatch step.
        kl_div_perm = None
        if self.kl_diversity_enabled:
            kl_div_perm = torch.randperm(self.persona_registry.num_personas, device=self.device)

        if cfg.use_lstm:
            # For LSTM we keep B contiguous per minibatch and shuffle env-major
            # indices only — preserve time order.
            assert B % cfg.num_minibatches == 0, (
                "num_envs*num_players must be divisible by num_minibatches when "
                "use_lstm=True"
            )
            envs_per_minibatch = B // cfg.num_minibatches
            env_indices = np.arange(B)
            for _ in range(cfg.update_epochs):
                np.random.shuffle(env_indices)
                for start in range(0, B, envs_per_minibatch):
                    mb_env_idx = env_indices[start : start + envs_per_minibatch]
                    mb_env_idx_t = torch.as_tensor(mb_env_idx, device=self.device)
                    # Gather (T, mb) tensors then reshape to (T*mb).
                    obs_tb = self.buffer.obs[:, mb_env_idx_t]   # (T, mb, H, W, C)
                    obs_flat = obs_tb.reshape(
                        T * envs_per_minibatch, *self.buffer.obs.shape[2:]
                    )
                    actions_flat = self.buffer.actions[:, mb_env_idx_t].reshape(-1)
                    logprob_old = self.buffer.logprobs[:, mb_env_idx_t].reshape(-1)
                    advantages_mb = advantages[:, mb_env_idx_t].reshape(-1)
                    returns_mb = returns[:, mb_env_idx_t].reshape(-1)
                    values_old = self.buffer.values[:, mb_env_idx_t].reshape(-1)
                    dones_mb = b_dones[:, mb_env_idx_t]
                    h0 = self.buffer.initial_lstm_h[:, mb_env_idx_t].contiguous()
                    c0 = self.buffer.initial_lstm_c[:, mb_env_idx_t].contiguous()
                    persona_mb = self._persona_for_ids(
                        b_persona_ids[:, mb_env_idx_t].reshape(-1)
                    )

                    new_logprob, entropy, new_value = self.agent.evaluate(
                        obs_flat,
                        actions_flat,
                        batch_size=envs_per_minibatch,
                        num_steps=T,
                        lstm_state=(h0, c0),
                        dones=dones_mb,
                        persona=persona_mb,
                    )
                    self._ppo_step(
                        new_logprob, entropy, new_value,
                        logprob_old, advantages_mb, returns_mb, values_old,
                        clipfracs, approx_kls, pg_losses, v_losses, ent_losses,
                    )
        else:
            assert T * B % cfg.num_minibatches == 0
            mb_size = (T * B) // cfg.num_minibatches
            indices = np.arange(T * B)
            for _ in range(cfg.update_epochs):
                np.random.shuffle(indices)
                for start in range(0, T * B, mb_size):
                    mb = torch.as_tensor(indices[start : start + mb_size], device=self.device)
                    mb_persona_ids = b_persona_ids.reshape(-1)[mb]
                    persona_mb = self._persona_for_ids(mb_persona_ids)
                    new_logprob, entropy, new_value = self.agent.evaluate(
                        b_obs[mb], b_actions[mb], persona=persona_mb,
                    )
                    extra = None
                    if self.kl_diversity_enabled and kl_div_perm is not None:
                        shuffled_ids = kl_div_perm[mb_persona_ids]
                        shuffled_persona = self.persona_encoder(shuffled_ids)
                        logits_true = self.agent.policy_logits(b_obs[mb], persona_mb)
                        logits_alt = self.agent.policy_logits(b_obs[mb], shuffled_persona)
                        log_p_true = F.log_softmax(logits_true, dim=-1)
                        log_p_alt = F.log_softmax(logits_alt, dim=-1)
                        p_true = log_p_true.exp()
                        kl = (p_true * (log_p_true - log_p_alt)).sum(-1).mean()
                        kl_div_terms.append(float(kl.item()))
                        # Maximize KL ⇒ subtract from loss.
                        extra = -cfg.kl_diversity_coef * kl
                    self._ppo_step(
                        new_logprob, entropy, new_value,
                        b_logprobs[mb], b_advantages[mb], b_returns[mb], b_values[mb],
                        clipfracs, approx_kls, pg_losses, v_losses, ent_losses,
                        extra_loss=extra,
                    )

                if cfg.target_kl is not None and len(approx_kls) > 0:
                    if approx_kls[-1] > cfg.target_kl:
                        break

        # Trajectory consistency (InfoNCE) -------------------------------------
        # One opt step over all B trajectories per update epoch. The trajectory
        # is encoded from per-slot (action, reward, done) over the full T window;
        # the done-aware GRU resets hidden state on episode boundaries so each
        # trajectory embedding represents at most one episode.
        if self.infonce_enabled:
            persona_table = self.persona_encoder.table
            final_persona_ids = self.buffer.persona_ids[-1].clamp_min(0)  # (B,)
            for _ in range(cfg.update_epochs):
                # Phase 5 §4: optionally stratify the InfoNCE batch over
                # personas so every present id contributes the same number
                # of trajectories. Resampling is with replacement when a
                # persona is under-represented in the rollout; this trades a
                # small amount of repeated examples for a flat persona prior
                # in every opt step.
                if cfg.infonce_balanced_batch:
                    balanced_idx = self._build_balanced_idx(final_persona_ids)
                    actions_in = self.buffer.actions[:, balanced_idx]
                    rewards_in = self.buffer.rewards[:, balanced_idx]
                    dones_in = self.buffer.dones[:, balanced_idx]
                    target_ids = final_persona_ids[balanced_idx]
                else:
                    actions_in = self.buffer.actions
                    rewards_in = self.buffer.rewards
                    dones_in = self.buffer.dones
                    target_ids = final_persona_ids
                z_traj = self.trajectory_encoder(actions_in, rewards_in, dones_in)
                infonce_loss, stats = self.infonce_head(
                    z_traj,
                    persona_table,
                    target_ids,
                    candidate_indices=self._infonce_train_candidates,
                )
                weighted = cfg.infonce_coef * infonce_loss
                self.optimizer.zero_grad(set_to_none=True)
                weighted.backward()
                nn.utils.clip_grad_norm_(
                    list(self.trajectory_encoder.parameters()) + list(self.infonce_head.parameters()),
                    cfg.max_grad_norm,
                )
                self.optimizer.step()
                infonce_terms.append(stats["infonce_loss"])
                infonce_top1.append(stats["infonce_top1"])
                infonce_top3.append(stats["infonce_top3"])

        # Explained variance ----------------------------------------------------
        y_pred = b_values.detach().cpu().numpy()
        y_true = b_returns.detach().cpu().numpy()
        var_y = float(np.var(y_true))
        explained_var = float("nan") if var_y == 0 else 1.0 - float(np.var(y_true - y_pred) / var_y)

        out = {
            "loss/policy": float(np.mean(pg_losses)),
            "loss/value": float(np.mean(v_losses)),
            "loss/entropy": float(np.mean(ent_losses)),
            "loss/approx_kl": float(np.mean(approx_kls)) if approx_kls else 0.0,
            "loss/clip_frac": float(np.mean(clipfracs)) if clipfracs else 0.0,
            "loss/explained_var": explained_var,
        }
        if kl_div_terms:
            out["loss/kl_diversity"] = float(np.mean(kl_div_terms))
        if infonce_terms:
            out["loss/infonce"] = float(np.mean(infonce_terms))
            out["persona/infonce_top1"] = float(np.mean(infonce_top1))
            out["persona/infonce_top3"] = float(np.mean(infonce_top3))
        return out

    def _ppo_step(
        self,
        new_logprob, entropy, new_value,
        old_logprob, advantages, returns, old_values,
        clipfracs, approx_kls, pg_losses, v_losses, ent_losses,
        extra_loss: torch.Tensor | None = None,
        modules_to_clip: list | None = None,
    ) -> None:
        cfg = self.cfg

        log_ratio = new_logprob - old_logprob
        ratio = log_ratio.exp()
        with torch.no_grad():
            approx_kl = ((ratio - 1) - log_ratio).mean().item()
            clipfrac = ((ratio - 1.0).abs() > cfg.clip_coef).float().mean().item()

        adv = advantages
        if cfg.norm_adv and adv.numel() > 1:
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)

        pg1 = -adv * ratio
        pg2 = -adv * torch.clamp(ratio, 1 - cfg.clip_coef, 1 + cfg.clip_coef)
        pg_loss = torch.max(pg1, pg2).mean()

        if cfg.clip_value_loss:
            v_clipped = old_values + torch.clamp(
                new_value - old_values, -cfg.clip_coef, cfg.clip_coef
            )
            v1 = (new_value - returns) ** 2
            v2 = (v_clipped - returns) ** 2
            v_loss = 0.5 * torch.max(v1, v2).mean()
        else:
            v_loss = 0.5 * ((new_value - returns) ** 2).mean()

        ent_loss = entropy.mean()

        loss = pg_loss - cfg.ent_coef * ent_loss + cfg.vf_coef * v_loss
        if extra_loss is not None:
            loss = loss + extra_loss

        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        clip_params = list(self.agent.parameters())
        if modules_to_clip:
            for m in modules_to_clip:
                clip_params = clip_params + list(m.parameters())
        nn.utils.clip_grad_norm_(clip_params, cfg.max_grad_norm)
        self.optimizer.step()

        pg_losses.append(float(pg_loss.item()))
        v_losses.append(float(v_loss.item()))
        ent_losses.append(float(ent_loss.item()))
        clipfracs.append(clipfrac)
        approx_kls.append(approx_kl)

    # ----- Training loop ---------------------------------------------------

    def train(self) -> None:
        self.initialize()
        cfg = self.cfg
        steps_per_update = cfg.num_steps * self.num_envs * self.num_players
        num_updates = max(1, cfg.total_env_steps // steps_per_update)
        t_start = time.time()

        log_path = Path(cfg.run_dir) / (cfg.run_name or "run") / "logs.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_f = log_path.open("a", buffering=1)

        try:
            for update in range(1, num_updates + 1):
                self.update_idx = update
                if cfg.anneal_lr:
                    frac = 1.0 - (update - 1) / num_updates
                    for g in self.optimizer.param_groups:
                        g["lr"] = frac * cfg.learning_rate

                rollout_metrics = self.collect_rollout()
                update_metrics = self.update()

                wallclock = time.time() - t_start
                metrics: dict[str, Any] = {
                    "update": update,
                    "global_step": self.global_step,
                    "wallclock_s": wallclock,
                    "lr": self.optimizer.param_groups[0]["lr"],
                    **rollout_metrics,
                    **update_metrics,
                    "env/reset_count": self.reset_count,
                }
                if self.completed_returns:
                    recent = self.completed_returns[-self.batch :]
                    recent_lens = self.completed_lengths[-self.batch :]
                    metrics["env/episode_return_mean"] = float(np.mean(recent))
                    metrics["env/episode_return_min"] = float(np.min(recent))
                    metrics["env/episode_return_max"] = float(np.max(recent))
                    metrics["env/episode_length_mean"] = float(np.mean(recent_lens))
                if torch.cuda.is_available():
                    metrics["sys/gpu_mem_mb"] = float(
                        torch.cuda.max_memory_allocated() / (1024 * 1024)
                    )

                if (
                    self.persona_enabled
                    and (
                        update % cfg.persona_diagnostics_interval_updates == 0
                        or update == num_updates
                    )
                ):
                    persona_metrics = self._flush_persona_diagnostics(update)
                    metrics.update(persona_metrics)

                if update % cfg.log_interval_updates == 0:
                    log_f.write(json.dumps(metrics) + "\n")
                    if self.writer is not None:
                        for k, v in metrics.items():
                            if isinstance(v, (int, float)):
                                self.writer.add_scalar(k, v, self.global_step)
                    self._print_progress(metrics)

                if update % cfg.checkpoint_interval_updates == 0 or update == num_updates:
                    self.save_checkpoint(update=update)
        finally:
            log_f.close()
            if self.writer is not None:
                self.writer.flush()
            if getattr(self, "_persona_log_f", None) is not None:
                self._persona_log_f.close()
                self._persona_log_f = None

    # ----- Checkpointing ----------------------------------------------------

    def save_checkpoint(self, update: int) -> Path:
        cfg = self.cfg
        ckpt_dir = Path(cfg.run_dir) / (cfg.run_name or "run") / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        path = ckpt_dir / f"ckpt_update{update:06d}.pt"
        torch.save(
            {
                "update": update,
                "global_step": self.global_step,
                "model": self.agent.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "config": asdict(cfg),
                "rng": {
                    "python": random.getstate(),
                    "numpy": np.random.get_state(),
                    "torch": torch.get_rng_state(),
                    "torch_cuda": (
                        torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None
                    ),
                },
                "lstm_state": (
                    [t.detach().cpu() for t in self._lstm_state]
                    if self._lstm_state is not None
                    else None
                ),
                "trajectory_encoder": (
                    self.trajectory_encoder.state_dict()
                    if self.trajectory_encoder is not None
                    else None
                ),
                "infonce_head": (
                    self.infonce_head.state_dict()
                    if self.infonce_head is not None
                    else None
                ),
                "persona": (
                    {
                        "registry": self.persona_registry.to_dict(),
                        "current_assignment": (
                            self.persona_assigner.current.tolist()
                            if self.persona_assigner is not None
                            else None
                        ),
                        "encoder_table": self.persona_encoder.table.detach().cpu()
                        if self.persona_encoder is not None
                        else None,
                    }
                    if self.persona_enabled
                    else None
                ),
            },
            path,
        )
        return path

    def load_checkpoint(self, path: str | os.PathLike) -> None:
        data = torch.load(path, map_location=self.device, weights_only=False)
        self.agent.load_state_dict(data["model"])
        self.optimizer.load_state_dict(data["optimizer"])
        self.update_idx = data["update"]
        self.global_step = data["global_step"]
        rng = data["rng"]
        random.setstate(rng["python"])
        np.random.set_state(rng["numpy"])
        torch.set_rng_state(rng["torch"])
        if rng.get("torch_cuda") is not None and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(rng["torch_cuda"])
        if data.get("lstm_state") is not None and self._lstm_state is not None:
            self._lstm_state = tuple(t.to(self.device) for t in data["lstm_state"])
        if data.get("trajectory_encoder") is not None and self.trajectory_encoder is not None:
            self.trajectory_encoder.load_state_dict(data["trajectory_encoder"])
        if data.get("infonce_head") is not None and self.infonce_head is not None:
            self.infonce_head.load_state_dict(data["infonce_head"])
        persona_blob = data.get("persona")
        if persona_blob is not None and self.persona_assigner is not None:
            assignment = np.array(persona_blob["current_assignment"], dtype=np.int64)
            # Restore live assignment so rollout picks up where it left off.
            self.persona_assigner._current = assignment
            self._current_persona = torch.as_tensor(
                assignment.reshape(self.batch), device=self.device, dtype=torch.long
            )

    # ----- Persona helpers --------------------------------------------------

    def _build_balanced_idx(self, persona_ids: torch.Tensor) -> torch.Tensor:
        """Return indices (B',) into the rollout batch that produce a
        persona-balanced InfoNCE input.

        For each persona id present in ``persona_ids``, sample
        ``target_per_persona`` indices (with replacement when the rollout has
        fewer than that many trajectories of the persona) and concatenate.
        """
        cfg = self.cfg
        K = int(persona_ids.numel())
        unique = torch.unique(persona_ids)
        n_unique = int(unique.numel())
        target = cfg.infonce_per_persona
        if target <= 0:
            # Auto: round up so the balanced batch is roughly the rollout size.
            target = max(1, (K + n_unique - 1) // n_unique)
        out_indices = []
        for pid in unique:
            pool = (persona_ids == pid).nonzero(as_tuple=True)[0]
            n = int(pool.numel())
            if n == 0:
                continue
            if n >= target:
                perm = torch.randperm(n, device=pool.device)[:target]
                out_indices.append(pool[perm])
            else:
                draws = torch.randint(0, n, (target,), device=pool.device)
                out_indices.append(pool[draws])
        return torch.cat(out_indices)

    def _persona_embedding(self, persona_ids: torch.Tensor | None) -> torch.Tensor | None:
        if self.persona_encoder is None or persona_ids is None:
            return None
        return self.persona_encoder(persona_ids)

    def _persona_for_ids(self, ids_flat: torch.Tensor) -> torch.Tensor | None:
        if self.persona_encoder is None:
            return None
        # Buffer may contain -1 for the very first update if assignment was
        # ever skipped. Clamp those to 0 — the corresponding rows will be
        # ignored by the (frozen) encoder semantically, since persona_enabled
        # implies every step writes a real id.
        ids = ids_flat.clamp_min(0)
        return self.persona_encoder(ids)

    def _log_persona_assignment(self, *, reset_kind: str) -> None:
        if self.persona_assigner is None or self.persona_registry is None:
            return
        assignment = self.persona_assigner.current  # (E, P)
        per_env = [
            [self.persona_registry.index_to_id(int(idx)) for idx in row]
            for row in assignment
        ]
        record = {
            "global_step": self.global_step,
            "reset_kind": reset_kind,
            "assignment": per_env,
        }
        if not hasattr(self, "_persona_log_f") or self._persona_log_f is None:
            log_path = Path(self.cfg.run_dir) / (self.cfg.run_name or "run") / "persona_assignments.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._persona_log_f = log_path.open("a", buffering=1)
        self._persona_log_f.write(json.dumps(record) + "\n")

    def _update_persona_diagnostics(
        self,
        persona_ids: np.ndarray,
        actions: np.ndarray,
        rewards: np.ndarray,
        dones: np.ndarray,
    ) -> None:
        num_actions = self.env.spec.num_actions
        # Per-step accumulation.
        for pid in np.unique(persona_ids):
            mask = persona_ids == pid
            if pid not in self._diag_action_counts:
                self._diag_action_counts[pid] = np.zeros(num_actions, dtype=np.int64)
                self._diag_reward_sum[pid] = 0.0
                self._diag_reward_count[pid] = 0
                self._diag_episode_returns[pid] = []
                self._diag_positive_reward_count[pid] = 0
            counts = np.bincount(actions[mask], minlength=num_actions)
            self._diag_action_counts[pid] += counts
            self._diag_reward_sum[pid] += float(rewards[mask].sum())
            self._diag_reward_count[pid] += int(mask.sum())
            self._diag_positive_reward_count[pid] += int((rewards[mask] > 0).sum())

        # Per-slot persona-tagged episode return: accumulate reward, snapshot
        # on done, and reset.
        if self._persona_episode_returns is None:
            self._persona_episode_returns = np.zeros(self.batch, dtype=np.float32)
        self._persona_episode_returns += rewards
        done_idx = np.where(dones > 0.5)[0]
        for i in done_idx:
            pid = int(persona_ids[i])
            ret = float(self._persona_episode_returns[i])
            self._diag_episode_returns.setdefault(pid, []).append(ret)
            self._persona_episode_returns[i] = 0.0

    def _flush_persona_diagnostics(self, update: int) -> dict[str, Any]:
        """Compute and write per-persona behavioral diagnostics.

        Returns an in-memory summary suitable for logging. Side effect: writes
        ``persona_diagnostics.json`` (overwritten each call so the file always
        reflects the latest state).
        """
        if not self.persona_enabled or self.persona_registry is None:
            return {}

        # Action distribution per persona.
        action_dists: dict[str, list[float]] = {}
        action_freq: dict[str, list[float]] = {}
        mean_return: dict[str, float] = {}
        mean_per_step_reward: dict[str, float] = {}
        ep_count: dict[str, int] = {}
        social: dict[str, dict[str, float]] = {}
        # commons_harvest__open action ontology (index → label):
        # 0 NOOP, 1 FORWARD, 2 BACKWARD, 3 STEP_LEFT, 4 STEP_RIGHT,
        # 5 TURN_LEFT, 6 TURN_RIGHT, 7 FIRE_ZAP
        for pid, counts in self._diag_action_counts.items():
            name = self.persona_registry.index_to_id(int(pid))
            total = int(counts.sum())
            if total == 0:
                continue
            probs = counts / total
            action_dists[name] = probs.tolist()
            action_freq[name] = counts.tolist()
            mean_per_step_reward[name] = (
                self._diag_reward_sum[pid] / max(1, self._diag_reward_count[pid])
            )
            eps = self._diag_episode_returns.get(pid, [])
            ep_count[name] = len(eps)
            mean_return[name] = float(np.mean(eps)) if eps else float("nan")

            steps = max(1, self._diag_reward_count[pid])
            harvest_freq = self._diag_positive_reward_count[pid] / steps
            aggression = float(probs[7]) if len(probs) > 7 else 0.0
            stationarity = float(probs[0] + probs[5] + probs[6])
            exploration = float(probs[1] + probs[2] + probs[3] + probs[4])
            cooperation = harvest_freq / max(1e-8, harvest_freq + aggression)
            social[name] = {
                "harvest_freq": float(harvest_freq),
                "aggression": aggression,
                "cooperation_ratio": float(cooperation),
                "stationarity": stationarity,
                "exploration": exploration,
            }

        # Pairwise KL between persona action distributions.
        pairwise_kl: dict[str, float] = {}
        names = list(action_dists.keys())
        for i, a in enumerate(names):
            pa = np.array(action_dists[a]) + 1e-8
            pa = pa / pa.sum()
            for b in names[i + 1 :]:
                pb = np.array(action_dists[b]) + 1e-8
                pb = pb / pb.sum()
                kl_ab = float(np.sum(pa * np.log(pa / pb)))
                kl_ba = float(np.sum(pb * np.log(pb / pa)))
                pairwise_kl[f"{a}||{b}"] = kl_ab
                pairwise_kl[f"{b}||{a}"] = kl_ba

        mean_pairwise_kl = (
            float(np.mean(list(pairwise_kl.values()))) if pairwise_kl else 0.0
        )

        # Trajectory retrieval (Phase 3): one-shot top-1/top-3 accuracy of
        # the trajectory encoder against the frozen persona table on the
        # latest rollout buffer. Only computed when InfoNCE is enabled.
        traj_block: dict | None = None
        if self.infonce_enabled and self.trajectory_encoder is not None:
            with torch.no_grad():
                z_traj = self.trajectory_encoder(
                    self.buffer.actions,
                    self.buffer.rewards,
                    self.buffer.dones,
                )
                ids = self.buffer.persona_ids[-1].clamp_min(0)
                logits = self.infonce_head.logits(z_traj, self.persona_encoder.table)
                pred = logits.argmax(dim=-1)
                top1 = (pred == ids).float().mean().item()
                top3_vals, top3_idx = logits.topk(min(3, logits.shape[-1]), dim=-1)
                top3 = (top3_idx == ids.unsqueeze(-1)).any(dim=-1).float().mean().item()
                # Per-persona retrieval breakdown.
                per_persona_top1: dict[str, float] = {}
                ids_np = ids.cpu().numpy()
                pred_np = pred.cpu().numpy()
                for pid in np.unique(ids_np):
                    mask = ids_np == pid
                    if mask.sum() == 0:
                        continue
                    pname = self.persona_registry.index_to_id(int(pid))
                    per_persona_top1[pname] = float((pred_np[mask] == pid).mean())
            traj_block = {
                "top1": top1,
                "top3": top3,
                "per_persona_top1": per_persona_top1,
                "num_classes": self.persona_registry.num_personas,
                "chance_top1": 1.0 / self.persona_registry.num_personas,
            }

        diag = {
            "update": update,
            "global_step": self.global_step,
            "conditioning": self.cfg.persona_conditioning,
            "assignment": self.cfg.persona_assignment,
            "embedding_dim": self.persona_encoder.embedding_dim if self.persona_encoder else 0,
            "infonce_coef": self.cfg.infonce_coef,
            "kl_diversity_coef": self.cfg.kl_diversity_coef,
            "personas_seen": names,
            "action_distribution": action_dists,
            "action_count": action_freq,
            "mean_per_step_reward": mean_per_step_reward,
            "mean_episode_return": mean_return,
            "episode_count": ep_count,
            "pairwise_action_kl": pairwise_kl,
            "mean_pairwise_action_kl": mean_pairwise_kl,
            "social_metrics": social,
            "trajectory_retrieval": traj_block,
        }
        out_path = Path(self.cfg.run_dir) / (self.cfg.run_name or "run") / "persona_diagnostics.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(diag, indent=2))

        # Reset accumulators so the next window is independent.
        self._diag_action_counts.clear()
        self._diag_reward_sum.clear()
        self._diag_reward_count.clear()
        self._diag_episode_returns.clear()
        self._diag_positive_reward_count.clear()

        metrics = {
            "persona/mean_pairwise_action_kl": mean_pairwise_kl,
            "persona/num_seen": len(names),
        }
        if traj_block is not None:
            metrics["persona/traj_retrieval_top1"] = traj_block["top1"]
            metrics["persona/traj_retrieval_top3"] = traj_block["top3"]
        if social:
            # Spread of each social metric across personas (a one-number
            # behavioral-divergence summary per metric).
            for key in ("harvest_freq", "aggression", "cooperation_ratio", "stationarity", "exploration"):
                vals = [d[key] for d in social.values()]
                metrics[f"social/{key}_spread"] = float(max(vals) - min(vals))
        return metrics

    def _print_progress(self, m: dict[str, Any]) -> None:
        keys = ("global_step", "rollout/sps", "loss/policy", "loss/value", "loss/entropy", "loss/approx_kl")
        bits = []
        for k in keys:
            if k in m:
                v = m[k]
                bits.append(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}")
        if "env/episode_return_mean" in m:
            bits.append(f"ep_ret={m['env/episode_return_mean']:.3f}")
        print("[ppo] " + " ".join(bits), flush=True)
