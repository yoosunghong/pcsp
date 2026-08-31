"""Verify the expected PCSP loss-to-module gradient topology."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPActorCritic, PCSPConfig, PCSPTrainer


def _build() -> PCSPTrainer:
    torch.manual_seed(13)
    policy = PCSPActorCritic(obs_dim=4, n_actions=3, persona_dim=6, llm_dim=8, lora_r=2)
    # FiLM starts as an exact identity, so a never-trained policy legitimately
    # has zero PPO/diversity gradient into persona projection. Perturb only the
    # FiLM conditioning weights to test the post-warmup structural paths.
    with torch.no_grad():
        for name, parameter in policy.named_parameters():
            if ".film." in name and name.endswith("weight"):
                parameter.fill_(0.01)
    encoder = TrajectoryEncoder(obs_dim=4, n_actions=3, hidden_dim=8, output_dim=6)
    return PCSPTrainer(policy, encoder, PCSPConfig(n_epochs=1, batch_size=4), device="cpu")


def _trajectories() -> list[dict]:
    rng = np.random.default_rng(5)
    return [{
        "obs_seq": rng.normal(size=(5, 4)).astype(np.float32),
        "act_seq": rng.integers(0, 3, size=5, dtype=np.int64),
        "e_llm": torch.tensor(rng.normal(size=8), dtype=torch.float32),
    } for _ in range(4)]


def main() -> None:
    trainer = _build()
    consistency = trainer._consistency_loss(_trajectories())
    norms = trainer.attributable_gradient_norms(consistency)
    assert norms["persona_projection"] > 0
    assert norms["trajectory_encoder"] > 0
    assert norms["actor"] == 0
    assert norms["critic"] == 0

    obs = torch.randn(8, 4)
    embeddings = torch.randn(8, 8)
    actions = torch.randint(0, 3, (8,))
    log_probs, values, entropy = trainer.policy.evaluate_actions(obs, actions, e_llm=embeddings)
    ppo = -log_probs.mean() + 0.5 * F.mse_loss(values, torch.randn(8)) - 0.01 * entropy.mean()
    norms = trainer.attributable_gradient_norms(ppo)
    assert norms["persona_projection"] > 0
    assert norms["actor"] > 0
    assert norms["critic"] > 0
    assert norms["trajectory_encoder"] == 0

    transitions = [{"obs": row.numpy()} for row in obs]
    np.random.seed(11)
    diversity = trainer._diversity_loss(transitions, torch.randn(8, 8))
    norms = trainer.attributable_gradient_norms(diversity)
    assert norms["persona_projection"] > 0
    assert norms["actor"] > 0
    assert norms["critic"] == 0
    assert norms["trajectory_encoder"] == 0

    trainer = _build()
    trainer.config.log_attributable_gradients = True
    rng = np.random.default_rng(19)
    transitions = []
    for _ in range(8):
        obs_np = rng.normal(size=4).astype(np.float32)
        embedding = torch.tensor(rng.normal(size=(1, 8)), dtype=torch.float32)
        with torch.no_grad():
            action, log_prob, value = trainer.policy.get_action(
                torch.from_numpy(obs_np).unsqueeze(0), e_llm=embedding
            )
        transitions.append({
            "obs": obs_np, "action": int(action), "log_prob": float(log_prob),
            "advantage": float(rng.normal()), "return": float(value + rng.normal()),
            "context": {"e_llm": embedding},
        })
    stats = trainer.update(transitions, _trajectories(), torch.randn(8, 8))
    assert set(stats["gradient_norms"]) == {"ppo", "consistency", "diversity"}
    assert stats["gradient_norms"]["consistency"]["trajectory_encoder"] > 0
    print("PCSP attributable gradient topology PASS")


if __name__ == "__main__":
    main()
