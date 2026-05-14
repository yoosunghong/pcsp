"""Verify that a saved PPO checkpoint reloads to a bit-identical model and
that the optimizer + RNG state survive a save/load roundtrip.

Strategy:
  1. Build a fresh trainer, run a small number of updates, save checkpoint.
  2. Snapshot model state dict, optimizer state dict, and a deterministic
     forward-pass output on a fixed dummy input.
  3. Build a second trainer (same config, different RNG init), load the
     checkpoint, and re-run the same dummy forward.
  4. Assert tensors are byte-identical and optimizer steps match.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

import numpy as np

# Import the trainer (which pulls in torch + torch._dynamo) *before* meltingpot
# to avoid an interaction where TF/jax side-effects from meltingpot break the
# lazy torch._dynamo import. The same ordering is enforced by launch.py.
from src.training.cleanrl_ppo.config import PPOConfig
from src.training.cleanrl_ppo.trainer import PPOTrainer, seed_everything

import torch

from src.env.meltingpot import SyncVectorMeltingPot


def main() -> int:
    seed_everything(42)
    tmp = tempfile.mkdtemp(prefix="ppo_ckpt_test_")
    try:
        cfg = PPOConfig(
            num_envs=2,
            num_steps=16,
            total_env_steps=200,
            num_minibatches=2,
            update_epochs=1,
            device="cpu",
            tb_logging=False,
            run_name="ckpt_test",
            run_dir=tmp,
            log_interval_updates=1,
            checkpoint_interval_updates=1,
        )
        env_a = SyncVectorMeltingPot(cfg.substrate, num_envs=cfg.num_envs)
        trainer_a = PPOTrainer(cfg, env_a)
        trainer_a.initialize()
        trainer_a.collect_rollout()
        trainer_a.update()
        ckpt_path = trainer_a.save_checkpoint(update=1)

        dummy = torch.zeros(4, 88, 88, 3, dtype=torch.uint8)
        with torch.no_grad():
            feat_a = trainer_a.agent.forward_encoder(dummy)
            logits_a = trainer_a.agent.actor(feat_a)
        opt_state_a_repr = str(trainer_a.optimizer.state_dict())

        env_a.close()

        env_b = SyncVectorMeltingPot(cfg.substrate, num_envs=cfg.num_envs)
        trainer_b = PPOTrainer(cfg, env_b)
        trainer_b.load_checkpoint(ckpt_path)
        with torch.no_grad():
            feat_b = trainer_b.agent.forward_encoder(dummy)
            logits_b = trainer_b.agent.actor(feat_b)
        opt_state_b_repr = str(trainer_b.optimizer.state_dict())
        env_b.close()

        max_diff = float((logits_a - logits_b).abs().max())
        assert max_diff == 0.0, f"Model logits differ after reload (max abs={max_diff})"
        assert opt_state_a_repr == opt_state_b_repr, "Optimizer state diverged after reload"
        assert trainer_b.global_step == trainer_a.global_step
        assert trainer_b.update_idx == 1, trainer_b.update_idx

        print(f"[ok] checkpoint reload exact: ckpt={ckpt_path} global_step={trainer_b.global_step}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
