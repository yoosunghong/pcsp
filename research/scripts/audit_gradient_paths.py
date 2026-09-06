"""Measure loss-attributable PCSP gradient norms on a trained v3-large model."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import PersonaConfig
from src.env.mini_inzoi_v3_large import MiniInzoiV3LargeEnv, N_AGENTS
from src.env.v3_constants import N_ACTIONS_V3, OBS_DIM_V3_LARGE
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPActorCritic, PCSPConfig, PCSPTrainer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", type=Path, default=ROOT / "results/pcsp_v3_large/full_seed42/full")
    parser.add_argument("--personas", type=Path, default=ROOT / "data/personas/train_400_v3.json")
    parser.add_argument("--embeddings", type=Path, default=REPO / "results/embeddings/persona_embeddings_500.npy")
    parser.add_argument("--output", type=Path, default=ROOT / "results/gradient_path_audit")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    torch.manual_seed(31_013)
    np.random.seed(31_013)
    device = torch.device(args.device if args.device == "cpu" or torch.cuda.is_available() else "cpu")
    records = json.loads(args.personas.read_text(encoding="utf-8"))[:N_AGENTS]
    embeddings = np.load(args.embeddings).astype(np.float32)

    policy = PCSPActorCritic(OBS_DIM_V3_LARGE, N_ACTIONS_V3)
    policy.load_state_dict(torch.load(args.checkpoint_dir / "policy.pt", map_location="cpu", weights_only=True))
    encoder = TrajectoryEncoder(OBS_DIM_V3_LARGE, N_ACTIONS_V3)
    encoder.load_state_dict(torch.load(args.checkpoint_dir / "traj_encoder.pt", map_location="cpu", weights_only=True))
    config = PCSPConfig(n_epochs=1, batch_size=64, log_attributable_gradients=True)
    trainer = PCSPTrainer(policy, encoder, config, device=str(device))

    def sampler():
        personas = [PersonaConfig.from_dict(row) for row in records]
        contexts = {
            f"agent_{index}": {"e_llm": torch.from_numpy(embeddings[int(row["id"]) - 1]).unsqueeze(0)}
            for index, row in enumerate(records)
        }
        return personas, contexts

    transitions, rewards, trajectories = trainer.collect_rollout(
        lambda personas: MiniInzoiV3LargeEnv(personas=personas, max_steps=200),
        sampler,
        n_episodes=1,
    )
    sample = transitions[:64]
    obs = torch.as_tensor(np.stack([row["obs"] for row in sample]), device=device)
    actions = torch.as_tensor([row["action"] for row in sample], dtype=torch.long, device=device)
    old_log_probs = torch.as_tensor([row["log_prob"] for row in sample], device=device)
    advantages = torch.as_tensor([row["advantage"] for row in sample], device=device)
    returns = torch.as_tensor([row["return"] for row in sample], device=device)
    context = trainer.policy.stack_contexts([row["context"] for row in sample])
    context = {key: value.to(device) for key, value in context.items()}
    log_probs, values, entropy = trainer.policy.evaluate_actions(obs, actions, **context)
    ratio = (log_probs - old_log_probs).exp()
    policy_loss = -torch.min(
        ratio * advantages,
        torch.clamp(ratio, 1 - config.clip_eps, 1 + config.clip_eps) * advantages,
    ).mean()
    value_loss = F.mse_loss(values, returns)
    ppo_loss = policy_loss + config.value_coef * value_loss - config.entropy_coef * entropy.mean()
    consistency_loss = trainer._consistency_loss(trajectories) * config.lambda_consistency
    all_e_llm = torch.from_numpy(embeddings[[int(row["id"]) - 1 for row in records]]).to(device)
    np.random.seed(31_013)
    diversity_loss = trainer._diversity_loss(transitions, all_e_llm) * config.lambda_diversity

    losses = {"ppo": ppo_loss, "consistency": consistency_loss, "diversity": diversity_loss}
    norms = {name: trainer.attributable_gradient_norms(loss) for name, loss in losses.items()}
    expected = {
        "ppo": {"persona_projection": True, "actor": True, "critic": True, "trajectory_encoder": False},
        "consistency": {"persona_projection": True, "actor": False, "critic": False, "trajectory_encoder": True},
        "diversity": {"persona_projection": True, "actor": True, "critic": False, "trajectory_encoder": False},
    }
    threshold = 1e-12
    checks = {
        loss: {module: (norms[loss][module] > threshold) == should_exist for module, should_exist in modules.items()}
        for loss, modules in expected.items()
    }
    if not all(all(values.values()) for values in checks.values()):
        raise RuntimeError(f"gradient topology mismatch: {checks}")

    args.output.mkdir(parents=True, exist_ok=True)
    result = {
        "protocol": {
            "checkpoint": str(args.checkpoint_dir.relative_to(ROOT)),
            "device": str(device),
            "rollout_transitions": len(transitions),
            "rollout_trajectories": len(trajectories),
            "ppo_probe_batch": len(sample),
            "loss_weights": {"consistency": config.lambda_consistency, "diversity": config.lambda_diversity},
            "measurement": "torch.autograd.grad per loss before optimizer step; L2 norm by module",
        },
        "loss_values": {name: float(loss.detach()) for name, loss in losses.items()},
        "gradient_norms": norms,
        "expected_nonzero": expected,
        "checks": checks,
        "mean_episode_reward": float(np.mean(rewards)),
    }
    (args.output / "gradient_paths.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    modules = ("persona_projection", "actor", "critic", "trajectory_encoder")
    matrix = np.asarray([[norms[loss][module] for module in modules] for loss in losses])
    display = np.log10(matrix + 1e-12)
    fig, axis = plt.subplots(figsize=(9.3, 4.4))
    image = axis.imshow(display, cmap="viridis", vmin=-12, vmax=max(0, float(display.max())))
    axis.set_xticks(np.arange(len(modules)), [name.replace("_", "\n") for name in modules])
    axis.set_yticks(np.arange(len(losses)), list(losses))
    axis.set_title("PCSP attributable gradient paths (trained v3-large seed 42)", fontweight="bold")
    for row in range(len(losses)):
        for column in range(len(modules)):
            axis.text(column, row, f"{matrix[row, column]:.2e}", ha="center", va="center", color="white" if display[row, column] < -1 else "black", fontsize=8)
    fig.colorbar(image, ax=axis, label="log10 gradient L2 norm")
    fig.tight_layout()
    fig.savefig(args.output / "gradient_paths.png", dpi=180, bbox_inches="tight")
    fig.savefig(args.output / "gradient_paths.svg", bbox_inches="tight")
    plt.close(fig)
    print(json.dumps({"gradient_norms": norms, "checks": checks, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
