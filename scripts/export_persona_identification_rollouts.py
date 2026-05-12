"""
Export real policy rollouts for the Korean 2AFC persona-identification survey.

This script runs a trained PCSP-style policy in Mini-Inzoi on held-out personas
and records the target agent's action sequence. The output is the rollout JSON
consumed by scripts/generate_persona_identification_survey_ko.py.

Usage:
    conda run -n paper python scripts/export_persona_identification_rollouts.py \
        --env_variant v3 \
        --policy results/pcsp_v3/full/policy.pt \
        --personas data/personas/test_60_v3.json \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --output results/human_eval/pcsp_v3_full_zero_shot_rollouts.json
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

from src.env.action_semantics import describe_action_ko, describe_v3_action_ko, nearest_place_name
from src.env.mini_inzoi import ACTION_NAMES, WORLD_OBJECTS, MiniInzoiEnv, PersonaConfig
from src.env.mini_inzoi_v3 import MiniInzoiV3Env, WORLD_OBJECTS as WORLD_OBJECTS_V3
from src.env.v3_constants import ACTION_NAMES_V3, OBS_DIM_V3_BASE
from src.training.pcsp_trainer import ConcatActorCritic, PCSPActorCritic

ENV_SPECS = {
    "v1": {
        "env_cls": MiniInzoiEnv,
        "obs_dim": 20,
        "action_names": ACTION_NAMES,
        "world_objects": WORLD_OBJECTS,
        "describe": describe_action_ko,
    },
    "v3": {
        "env_cls": MiniInzoiV3Env,
        "obs_dim": OBS_DIM_V3_BASE,
        "action_names": ACTION_NAMES_V3,
        "world_objects": WORLD_OBJECTS_V3,
        "describe": describe_v3_action_ko,
    },
}


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_policy(
    policy_path: Path,
    model_type: str,
    obs_dim: int,
    n_actions: int,
    device: torch.device,
) -> torch.nn.Module:
    cls = ConcatActorCritic if model_type == "concat" else PCSPActorCritic
    policy = cls(obs_dim, n_actions)
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
    env_variant: str,
    env_cls: type,
    action_names: list[str],
    world_objects: dict[str, tuple[int, int]],
    describe_fn,
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
    env = env_cls(personas=env_personas, max_steps=max_steps)
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
                "action": action_names[action_id],
                "time_of_day": pre_time,
                "position": pre_position,
                "place": nearest_place_name(pre_position, world_objects),
                "nearby_agents": nearby_agents,
                "reward": action_reward,
                "obs": [float(x) for x in obs],
            }
            event["description_ko"] = describe_fn(event, world_objects)
            target_actions.append(event)

    env.close()
    return {
        "persona_id": int(target["id"]),
        "split": target.get("split", "test"),
        "env_variant": env_variant,
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
    env_variant: str,
    n_items: int,
    max_steps: int,
    seed: int,
    device_name: str,
) -> dict[str, Any]:
    personas = _load_json(personas_path)
    embeddings = np.load(embeddings_path)
    rng = random.Random(seed)
    spec = ENV_SPECS[env_variant]
    action_names = list(spec["action_names"])
    obs_dim = int(spec["obs_dim"])
    n_actions = len(action_names)

    device = torch.device(device_name if device_name == "cuda" and torch.cuda.is_available() else "cpu")
    policy = _load_policy(policy_path, model_type, obs_dim, n_actions, device)

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
            env_variant=env_variant,
            env_cls=spec["env_cls"],
            action_names=action_names,
            world_objects=spec["world_objects"],
            describe_fn=spec["describe"],
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
        "env_variant": env_variant,
        "obs_dim": obs_dim,
        "n_actions": n_actions,
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
    p.add_argument("--policy", default="results/pcsp_v3/full/policy.pt")
    p.add_argument("--personas", default="data/personas/test_60_v3.json")
    p.add_argument("--embeddings", default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--output", default="results/human_eval/pcsp_v3_full_zero_shot_rollouts.json")
    p.add_argument("--model_label", default="PCSP-full")
    p.add_argument("--model_type", choices=["pcsp", "concat"], default="pcsp")
    p.add_argument("--env_variant", choices=sorted(ENV_SPECS.keys()), default="v3")
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
        env_variant=args.env_variant,
        n_items=args.n_items,
        max_steps=args.max_steps,
        seed=args.seed,
        device_name=args.device,
    )
    print(json.dumps({
        "output": args.output,
        "n_rollouts": payload["n_rollouts"],
        "env_variant": payload["env_variant"],
        "obs_dim": payload["obs_dim"],
        "n_actions": payload["n_actions"],
        "device": payload["device"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
