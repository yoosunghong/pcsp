"""
Qualitative comparison: NPCs that share an occupation but differ in personality.

For §4.3, we want to show that PCSP produces visibly different behavior for
two personas that share occupation but have different Big Five archetypes
(and the symmetric case: different occupations, same archetype). This script
selects pairs from a persona file, runs the trained policy on each, renders
rich Korean traces, and writes a side-by-side markdown report plus a JSON
dump of the rollouts.

Usage:
    conda run -n paper python scripts/qualitative_persona_comparison.py \
        --pairs same_occupation \
        --personas data/personas/train_240.json \
        --policy results/pcsp/full/policy.pt \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --output_md results/human_eval/qualitative_same_occupation.md \
        --output_json results/human_eval/qualitative_same_occupation.json
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
from src.training.pcsp_trainer import PCSPActorCritic

OBS_DIM = 20
N_ACTIONS = len(ACTION_NAMES)
TRAIT_KEYS = ("E", "N", "A", "C", "O")


def _archetype(p: dict[str, Any]) -> tuple[str, ...]:
    return tuple(p["big_five"][k] for k in TRAIT_KEYS)


def _persona_label(p: dict[str, Any]) -> str:
    return f"#{p['id']} {p.get('age', '?')}세 {p['occupation']} | BF=[{','.join(p['big_five'][k] for k in TRAIT_KEYS)}]"


def _select_pairs(personas: list[dict[str, Any]], mode: str, n: int, rng: random.Random) -> list[tuple[dict, dict]]:
    if mode == "same_occupation":
        # Pairs with identical occupation, different archetypes.
        groups: dict[str, list[dict[str, Any]]] = {}
        for p in personas:
            groups.setdefault(p["occupation"], []).append(p)
        candidates = [g for g in groups.values() if len(g) >= 2]
    elif mode == "same_archetype":
        groups = {}
        for p in personas:
            groups.setdefault(_archetype(p), []).append(p)
        candidates = [g for g in groups.values() if len(g) >= 2]
    else:
        raise ValueError(f"Unknown pair mode {mode!r}.")

    rng.shuffle(candidates)
    pairs: list[tuple[dict, dict]] = []
    for group in candidates:
        if len(pairs) >= n:
            break
        a, b = rng.sample(group, 2)
        pairs.append((a, b))
    return pairs


def _rollout(
    policy: torch.nn.Module,
    target: dict[str, Any],
    context: list[dict[str, Any]],
    embeddings: np.ndarray,
    device: torch.device,
    seed: int,
    max_steps: int,
) -> list[dict[str, Any]]:
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed % (2**32))

    env_personas = [PersonaConfig.from_dict(p) for p in context]
    env = MiniInzoiEnv(personas=env_personas, max_steps=max_steps)
    env.reset(seed=seed)

    agent_ctxs = {
        f"agent_{idx}": torch.tensor(
            embeddings[int(p["id"]) - 1], dtype=torch.float32, device=device
        ).unsqueeze(0)
        for idx, p in enumerate(context)
    }
    target_agent = "agent_0"
    events: list[dict[str, Any]] = []

    for agent in env.agent_iter():
        obs, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
            continue
        agent_idx = env.agent_name_mapping[agent]
        pre_pos = list(env.positions[agent_idx])
        pre_t = int(env.time_of_day)
        nearby = [
            int(j) for j, op in enumerate(env.positions)
            if j != agent_idx and np.abs(np.array(pre_pos) - np.array(op)).max() <= 1
        ]
        obs_t = torch.FloatTensor(obs).unsqueeze(0).to(device)
        with torch.no_grad():
            action_t, _, _ = policy.get_action(obs_t, e_llm=agent_ctxs[agent])
        action_id = int(action_t.item())
        env.step(action_id)
        if agent == target_agent:
            event = {
                "step": len(events) + 1,
                "action_id": action_id,
                "action": ACTION_NAMES[action_id],
                "time_of_day": pre_t,
                "position": pre_pos,
                "place": nearest_place_name(pre_pos, WORLD_OBJECTS),
                "nearby_agents": nearby,
            }
            event["description_ko"] = describe_action_ko(event, WORLD_OBJECTS)
            events.append(event)
    env.close()
    return events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="data/personas/train_240.json")
    ap.add_argument("--policy", default="results/pcsp/full/policy.pt")
    ap.add_argument("--embeddings", default="results/embeddings/persona_embeddings_300.npy")
    ap.add_argument("--pairs", choices=("same_occupation", "same_archetype"), default="same_occupation")
    ap.add_argument("--n_pairs", type=int, default=3)
    ap.add_argument("--max_steps", type=int, default=80)
    ap.add_argument("--display_len", type=int, default=12)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--output_md", required=True)
    ap.add_argument("--output_json", required=True)
    args = ap.parse_args()

    with open(ROOT / args.personas, encoding="utf-8") as f:
        personas = json.load(f)
    embeddings = np.load(ROOT / args.embeddings)

    device = torch.device(args.device if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    policy = PCSPActorCritic(OBS_DIM, N_ACTIONS)
    policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu", weights_only=True))
    policy.to(device).eval()

    rng = random.Random(args.seed)
    pairs = _select_pairs(personas, args.pairs, args.n_pairs, rng)
    if len(pairs) < args.n_pairs:
        print(f"Warning: only found {len(pairs)} pairs for mode {args.pairs}.")

    md_lines = [f"# Qualitative comparison ({args.pairs})", ""]
    md_lines.append(
        f"Each pair uses the same trained PCSP-full policy. Seed={args.seed}, max_steps={args.max_steps}."
    )
    md_lines.append("")

    json_payload: dict[str, Any] = {
        "mode": args.pairs,
        "policy": str(args.policy),
        "personas": str(args.personas),
        "n_pairs": len(pairs),
        "max_steps": args.max_steps,
        "seed": args.seed,
        "pairs": [],
    }

    for pair_idx, (a, b) in enumerate(pairs):
        # Use the same context personas (drawn from train) so each NPC sees a
        # similar social environment; difference in trace must come from the
        # target's persona conditioning.
        pool = [p for p in personas if int(p["id"]) not in {int(a["id"]), int(b["id"])}]
        rng_pair = random.Random(args.seed + pair_idx)
        ctx_extras = rng_pair.sample(pool, 3)

        events_a = _rollout(policy, a, [a] + ctx_extras, embeddings, device,
                            seed=args.seed + pair_idx * 1009, max_steps=args.max_steps)
        events_b = _rollout(policy, b, [b] + ctx_extras, embeddings, device,
                            seed=args.seed + pair_idx * 1009, max_steps=args.max_steps)

        def render(events: list[dict[str, Any]]) -> list[str]:
            return [e["description_ko"] for e in events if e["action_id"] < 8][: args.display_len]

        rendered_a = render(events_a)
        rendered_b = render(events_b)

        md_lines.append(f"## Pair {pair_idx + 1}")
        md_lines.append("")
        md_lines.append(f"- A: {_persona_label(a)}")
        md_lines.append(f"- B: {_persona_label(b)}")
        md_lines.append("")
        md_lines.append("| 단계 | A의 행동 | B의 행동 |")
        md_lines.append("|---|---|---|")
        for i, (line_a, line_b) in enumerate(zip(rendered_a, rendered_b)):
            md_lines.append(f"| {i+1} | {line_a} | {line_b} |")
        md_lines.append("")

        json_payload["pairs"].append({
            "pair_index": pair_idx,
            "a": {"id": int(a["id"]), "label": _persona_label(a), "events": events_a},
            "b": {"id": int(b["id"]), "label": _persona_label(b), "events": events_b},
        })

    out_md = ROOT / args.output_md
    out_json = ROOT / args.output_json
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "output_md": str(out_md.relative_to(ROOT)),
        "output_json": str(out_json.relative_to(ROOT)),
        "n_pairs": len(pairs),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
