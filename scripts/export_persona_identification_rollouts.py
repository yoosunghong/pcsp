"""
Export real policy rollouts for the Korean 2AFC persona-identification survey.

This script runs a trained PCSP-style policy in Mini-Inzoi on held-out personas
and records the target agent's action sequence. The output is the rollout JSON
consumed by scripts/generate_persona_identification_survey_ko.py.

Usage:
    conda run -n paper python scripts/export_persona_identification_rollouts.py \
        --policy results/pcsp/full/policy.pt \
        --personas data/personas/test_60.json \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --output results/human_eval/pcsp_full_zero_shot_rollouts.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.action_semantics import describe_action_ko, nearest_place_name
from src.env.mini_inzoi import ACTION_NAMES, WORLD_OBJECTS, MiniInzoiEnv, PersonaConfig
from src.training.pcsp_trainer import ConcatActorCritic, PCSPActorCritic

OBS_DIM = 20
N_ACTIONS = len(ACTION_NAMES)


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_policy(policy_path: Path, model_type: str, device: torch.device) -> torch.nn.Module:
    cls = ConcatActorCritic if model_type == "concat" else PCSPActorCritic
    policy = cls(OBS_DIM, N_ACTIONS)
    policy.load_state_dict(torch.load(policy_path, map_location="cpu", weights_only=True))
    return policy.to(device).eval()


def _embedding_for(persona: dict[str, Any], embeddings: np.ndarray, device: torch.device) -> torch.Tensor:
    idx = int(persona["id"]) - 1
    if idx < 0 or idx >= len(embeddings):
        raise IndexError(f"Persona id {persona['id']} is outside embedding matrix shape {embeddings.shape}.")
    return torch.FloatTensor(embeddings[idx].astype(np.float32)).unsqueeze(0).to(device)


def _sample_context_personas(
    target: dict[str, Any],
    personas: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    pool = [p for p in personas if int(p["id"]) != int(target["id"])]
    if len(pool) < 3:
        raise ValueError("Need at least four personas to create a four-agent rollout.")
    return [target] + rng.sample(pool, 3)


def _rollout_one(
    policy: torch.nn.Module,
    target: dict[str, Any],
    context: list[dict[str, Any]],
    embeddings: np.ndarray,
    device: torch.device,
    seed: int,
    max_steps: int,
    target_agent: str,
) -> dict[str, Any]:
    # Seed torch + numpy so that policy.get_action sampling is reproducible.
    # Without this, the saved rollouts cannot be replayed and the obs stream
    # cannot be recovered after the fact.
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed % (2**32))

    env_personas = [PersonaConfig.from_dict(p) for p in context]
    env = MiniInzoiEnv(personas=env_personas, max_steps=max_steps)
    env.reset(seed=seed)

    agent_ctxs = {
        f"agent_{idx}": {"e_llm": _embedding_for(persona, embeddings, device)}
        for idx, persona in enumerate(context)
    }
    target_actions: list[dict[str, Any]] = []

    for agent in env.agent_iter():
        obs, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
            continue

        agent_idx = env.agent_name_mapping[agent]
        pre_position = list(env.positions[agent_idx])
        pre_time = int(env.time_of_day)
        nearby_agents = [
            int(j)
            for j, other_pos in enumerate(env.positions)
            if j != agent_idx and np.abs(np.array(pre_position) - np.array(other_pos)).max() <= 1
        ]

        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(device)
        with torch.no_grad():
            action_t, _, _ = policy.get_action(obs_t, **agent_ctxs[agent])
        action_id = int(action_t.item())
        env.step(action_id)
        action_reward = float(env.rewards.get(agent, 0.0))

        if agent == target_agent:
            event = {
                "step": len(target_actions) + 1,
                "action_id": action_id,
                "action": ACTION_NAMES[action_id],
                "time_of_day": pre_time,
                "position": pre_position,
                "place": nearest_place_name(pre_position, WORLD_OBJECTS),
                "nearby_agents": nearby_agents,
                "reward": action_reward,
                "obs": [float(x) for x in obs],
            }
            event["description_ko"] = describe_action_ko(event, WORLD_OBJECTS)
            target_actions.append(event)

    env.close()
    return {
        "persona_id": int(target["id"]),
        "split": target.get("split", "test"),
        "target_agent": target_agent,
        "context_persona_ids": [int(p["id"]) for p in context],
        "seed": seed,
        "actions": target_actions,
    }


def export_rollouts(
    policy_path: Path,
    personas_path: Path,
    embeddings_path: Path,
    output_path: Path,
    model_label: str,
    model_type: str,
    n_items: int,
    max_steps: int,
    seed: int,
    device_name: str,
) -> dict[str, Any]:
    personas = _load_json(personas_path)
    embeddings = np.load(embeddings_path)
    rng = random.Random(seed)

    device = torch.device(device_name if device_name == "cuda" and torch.cuda.is_available() else "cpu")
    policy = _load_policy(policy_path, model_type, device)

    selected = list(personas)
    rng.shuffle(selected)
    selected = selected[: min(n_items, len(selected))]

    rollouts = []
    for idx, target in enumerate(selected):
        context = _sample_context_personas(target, personas, rng)
        rollout_seed = seed + idx * 1009
        row = _rollout_one(
            policy=policy,
            target=target,
            context=context,
            embeddings=embeddings,
            device=device,
            seed=rollout_seed,
            max_steps=max_steps,
            target_agent="agent_0",
        )
        row["model"] = model_label
        row["trajectory_id"] = f"{model_label.lower().replace('-', '_')}_p{int(target['id']):03d}_s{rollout_seed}"
        rollouts.append(row)

    payload = {
        "source": "real_policy_rollouts",
        "model": model_label,
        "model_type": model_type,
        "policy": str(policy_path),
        "personas": str(personas_path),
        "embeddings": str(embeddings_path),
        "n_rollouts": len(rollouts),
        "max_steps": max_steps,
        "seed": seed,
        "device": str(device),
        "rollouts": rollouts,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--policy", default="results/pcsp/full/policy.pt")
    p.add_argument("--personas", default="data/personas/test_60.json")
    p.add_argument("--embeddings", default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--output", default="results/human_eval/pcsp_full_zero_shot_rollouts.json")
    p.add_argument("--model_label", default="PCSP-full")
    p.add_argument("--model_type", choices=["pcsp", "concat"], default="pcsp")
    p.add_argument("--n_items", type=int, default=30)
    p.add_argument("--max_steps", type=int, default=80)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    payload = export_rollouts(
        policy_path=ROOT / args.policy,
        personas_path=ROOT / args.personas,
        embeddings_path=ROOT / args.embeddings,
        output_path=ROOT / args.output,
        model_label=args.model_label,
        model_type=args.model_type,
        n_items=args.n_items,
        max_steps=args.max_steps,
        seed=args.seed,
        device_name=args.device,
    )
    print(json.dumps({
        "output": args.output,
        "n_rollouts": payload["n_rollouts"],
        "device": payload["device"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
