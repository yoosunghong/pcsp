"""
Behavioral diversity evaluation — eval/diversity.py

Measures:
  1. Mean pairwise KL divergence between action distributions of different personas
     on a shared set of randomly sampled states.
  2. Spearman ρ between KL(π_i ‖ π_j) and ‖e_p_i − e_p_j‖₂ (embedding distance).
     ρ > 0.6 indicates that behaviorally-distinct personas are also semantically distant.

Usage (standalone):
    python src/eval/diversity.py \
        --policy results/pcsp/full/policy.pt \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --personas data/personas/train_240.json \
        --n_states 200 --n_persona_pairs 100
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS
from src.training.pcsp_trainer import PCSPActorCritic

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024


def _sample_random_states(
    n_states: int,
    seed: int = 0,
    env_factory=None,
    state_personas: list[PersonaConfig] | None = None,
) -> np.ndarray:
    """
    Sample diverse observations by running a random policy for n_states steps.
    Uses DEFAULT_PERSONAS to avoid bias toward specific persona configs.
    """
    from src.env.mini_inzoi import DEFAULT_PERSONAS
    rng = np.random.default_rng(seed)
    obs_list: list[np.ndarray] = []
    step = 0

    while step < n_states:
        if env_factory is None:
            env = MiniInzoiEnv(
                personas=state_personas or DEFAULT_PERSONAS,
                max_steps=200,
            )
        else:
            if not state_personas:
                raise ValueError("state_personas are required with env_factory")
            env = env_factory(state_personas)
        env.reset(seed=int(rng.integers(0, 2**31)))
        for agent in env.agent_iter():
            obs, _, term, trunc, _ = env.last()
            if not (term or trunc):
                obs_list.append(obs.copy())
                env.step(env.action_space(agent).sample())
                step += 1
                if step >= n_states:
                    break
            else:
                env.step(None)
        env.close()

    return np.stack(obs_list[:n_states]).astype(np.float32)   # (n_states, obs_dim)


def behavioral_kl_diversity(
    policy:         torch.nn.Module,
    all_embeddings: np.ndarray,       # (300, LLM_DIM)
    personas_data:  list[dict],
    n_states:       int  = 200,
    n_persona_pairs: int = 100,
    device:         str  = "cuda",
    seed:           int  = 0,
    env_factory=None,
    state_personas: list[PersonaConfig] | None = None,
) -> dict:
    """
    Sample n_persona_pairs random pairs from personas_data.
    For each pair, compute:
      - mean KL(π_i ‖ π_j) + KL(π_j ‖ π_i) averaged over sampled states
      - ‖proj(e_i) − proj(e_j)‖₂ (L2 distance in persona projection space)

    Also report Spearman ρ between KL and L2 distance, and mean KL.
    """
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    policy.to(dev).eval()

    rng = np.random.default_rng(seed)
    states_np = _sample_random_states(
        n_states,
        seed=seed,
        env_factory=env_factory,
        state_personas=state_personas,
    )
    states    = torch.FloatTensor(states_np).to(dev)           # (S, obs_dim)

    N = len(personas_data)
    n_pairs = min(n_persona_pairs, N * (N - 1) // 2)

    # Sample random pairs
    pairs: list[tuple[int, int]] = []
    while len(pairs) < n_pairs:
        i, j = rng.choice(N, size=2, replace=False)
        if (int(i), int(j)) not in pairs and (int(j), int(i)) not in pairs:
            pairs.append((int(i), int(j)))

    kl_values:   list[float] = []
    dist_values: list[float] = []

    for (i, j) in pairs:
        e_i = torch.FloatTensor(
            all_embeddings[personas_data[i]["id"] - 1].astype(np.float32)
        ).unsqueeze(0).to(dev)
        e_j = torch.FloatTensor(
            all_embeddings[personas_data[j]["id"] - 1].astype(np.float32)
        ).unsqueeze(0).to(dev)

        with torch.no_grad():
            logits_i = policy.action_logits(states, e_i.expand(n_states, -1))  # (S, A)
            logits_j = policy.action_logits(states, e_j.expand(n_states, -1))

        log_p_i = F.log_softmax(logits_i, dim=-1)
        log_p_j = F.log_softmax(logits_j, dim=-1)
        p_i     = log_p_i.exp()
        p_j     = log_p_j.exp()

        # Symmetric KL
        kl_ij = F.kl_div(log_p_j, p_i, reduction="batchmean").item()
        kl_ji = F.kl_div(log_p_i, p_j, reduction="batchmean").item()
        sym_kl = (kl_ij + kl_ji) / 2.0

        # L2 distance in persona_proj space
        with torch.no_grad():
            pe_i = policy.persona_proj(e_i)  # (1, 64) already L2-normed
            pe_j = policy.persona_proj(e_j)
        l2_dist = float(torch.norm(pe_i - pe_j, dim=-1).item())

        kl_values.append(sym_kl)
        dist_values.append(l2_dist)

    kl_arr   = np.array(kl_values)
    dist_arr = np.array(dist_values)

    # Spearman ρ
    from scipy.stats import spearmanr
    rho, p_val = spearmanr(kl_arr, dist_arr)

    return {
        "mean_kl":          float(kl_arr.mean()),
        "std_kl":           float(kl_arr.std()),
        "median_kl":        float(np.median(kl_arr)),
        "spearman_rho":     float(rho),
        "spearman_p":       float(p_val),
        "n_pairs":          len(pairs),
        "n_states":         n_states,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--policy",           default="results/pcsp/full/policy.pt")
    p.add_argument("--embeddings",       default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--env_variant",      choices=["v1", "v3"], default="v1")
    p.add_argument("--personas",         default=None,
                   help="Defaults to train_240.json for v1 and train_240_v3.json for v3.")
    p.add_argument("--n_states",         type=int, default=200)
    p.add_argument("--n_persona_pairs",  type=int, default=100)
    p.add_argument("--n_agents",         type=int, default=4)
    p.add_argument("--obs_dim",          type=int, default=None)
    p.add_argument("--n_actions",        type=int, default=None)
    p.add_argument("--device",           default="cuda")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.n_agents < 1:
        raise ValueError("--n_agents must be at least 1")

    if args.env_variant == "v3":
        from src.env.mini_inzoi_v3 import MiniInzoiV3Env
        from src.env.v3_constants import N_ACTIONS_V3, obs_dim_v3

        obs_dim = args.obs_dim if args.obs_dim is not None else obs_dim_v3(args.n_agents)
        n_actions = args.n_actions if args.n_actions is not None else N_ACTIONS_V3
        personas_path = args.personas or "data/personas/train_240_v3.json"

        def selected_env_factory(personas):
            return MiniInzoiV3Env(personas=personas, max_steps=200)
    else:
        obs_dim = args.obs_dim if args.obs_dim is not None else OBS_DIM
        n_actions = args.n_actions if args.n_actions is not None else N_ACTS
        personas_path = args.personas or "data/personas/train_240.json"
        selected_env_factory = None

    with open(ROOT / personas_path) as f:
        personas_data = json.load(f)
    if len(personas_data) < args.n_agents:
        raise ValueError(
            f"Need at least {args.n_agents} personas, found {len(personas_data)} in {personas_path}"
        )
    all_emb = np.load(ROOT / args.embeddings)

    policy = PCSPActorCritic(obs_dim, n_actions)
    policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))

    state_personas = None
    if args.env_variant == "v3":
        state_personas = [
            PersonaConfig.from_dict(p) for p in personas_data[:args.n_agents]
        ]

    result = behavioral_kl_diversity(
        policy, all_emb, personas_data,
        n_states=args.n_states,
        n_persona_pairs=args.n_persona_pairs,
        device=args.device,
        env_factory=selected_env_factory,
        state_personas=state_personas,
    )
    result.update({
        "env_variant": args.env_variant,
        "obs_dim": obs_dim,
        "n_actions": n_actions,
        "n_agents": args.n_agents,
    })
    print(json.dumps(result, indent=2))
