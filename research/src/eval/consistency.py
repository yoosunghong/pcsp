"""
Persona classification accuracy — eval/consistency.py

Given trajectories collected by a trained policy, encode each with the
TrajectoryEncoder and classify the persona by nearest-neighbor in persona
embedding space.  Reports top-1 accuracy and mean intra/inter cosine similarity.

Usage (standalone):
    python src/eval/consistency.py \
        --policy results/pcsp/full/policy.pt \
        --traj_enc results/pcsp/full/traj_encoder.pt \
        --personas data/personas/train_240.json \
        --embeddings results/embeddings/persona_embeddings_300.npy \
        --n_episodes 5 --n_personas 24
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig, N_ACTIONS
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPActorCritic

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024


def _rollout_persona(
    policy:      torch.nn.Module,
    e_llm:       torch.Tensor,     # (1, LLM_DIM)
    persona_cfg: PersonaConfig,
    n_episodes:  int,
    device:      torch.device,
    seed_offset: int = 0,
    n_agents:    int = 4,
    env_factory: Callable | None = None,
) -> list[dict]:
    """Collect n_episodes trajectories for one persona.

    n_agents / env_factory let v3 callers swap envs without forking; defaults
    reproduce v1 (4-agent MiniInzoiEnv with persona_cfg replicated)."""
    trajs = []
    if env_factory is None:
        make_env = lambda: MiniInzoiEnv(personas=[persona_cfg] * n_agents, max_steps=200)
    else:
        make_env = lambda: env_factory([persona_cfg] * n_agents)

    for ep in range(n_episodes):
        env = make_env()
        env.reset(seed=seed_offset + ep * 997)

        obs_list: list[np.ndarray] = []
        act_list: list[int]        = []

        for agent in env.agent_iter():
            obs, _, term, trunc, _ = env.last()
            if term or trunc:
                env.step(None)
                continue
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(device)
            with torch.no_grad():
                action_t, _, _ = policy.get_action(obs_t, e_llm=e_llm)
            obs_list.append(obs.copy())
            act_list.append(action_t.item())
            env.step(action_t.item())

        env.close()
        if len(obs_list) >= 2:
            trajs.append({
                "obs_seq": np.stack(obs_list),
                "act_seq": np.array(act_list, dtype=np.int64),
            })
    return trajs


def _encode_trajectories(
    traj_encoder: TrajectoryEncoder,
    trajs:        list[dict],
    device:       torch.device,
) -> torch.Tensor:
    """Encode a list of trajectory dicts → (N, output_dim) L2-normalised."""
    if not trajs:
        return torch.zeros(0, traj_encoder.output_dim)

    max_T    = min(max(len(t["obs_seq"]) for t in trajs), 200)
    obs_dim  = trajs[0]["obs_seq"].shape[-1]
    B        = len(trajs)

    obs_b = np.zeros((B, max_T, obs_dim), dtype=np.float32)
    act_b = np.zeros((B, max_T),          dtype=np.int64)
    for k, t in enumerate(trajs):
        T = min(len(t["obs_seq"]), max_T)
        obs_b[k, :T] = t["obs_seq"][:T]
        act_b[k, :T] = t["act_seq"][:T]

    obs_t = torch.FloatTensor(obs_b).to(device)
    act_t = torch.LongTensor(act_b).to(device)
    with torch.no_grad():
        embs = traj_encoder(obs_t, act_t)   # already L2-normalised
    return embs.cpu()


def persona_classification_accuracy(
    policy:           torch.nn.Module,
    traj_encoder:     TrajectoryEncoder,
    personas_data:    list[dict],
    all_embeddings:   np.ndarray,          # (300, LLM_DIM) all e_llm
    n_episodes:       int  = 5,
    n_personas:       int  | None = None,  # None → use all
    device:           str  = "cuda",
    seed:             int  = 0,
    n_agents:         int  = 4,
    env_factory:      Callable | None = None,
) -> dict:
    """
    For each persona in personas_data (up to n_personas), roll out n_episodes
    episodes and encode trajectories.  Classify by nearest-neighbor cosine
    similarity in persona_proj(e_llm) space.

    Returns:
        accuracy:         top-1 kNN accuracy (float)
        intra_cos_mean:   mean cosine sim within same persona
        inter_cos_mean:   mean cosine sim across different personas
        per_persona_acc:  list of per-persona accuracy values
    """
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    policy.to(dev).eval()
    traj_encoder.to(dev).eval()

    personas = personas_data[:n_personas] if n_personas else personas_data

    # Build persona projection embeddings (persona_dim=64) for all candidates
    e_llm_all = torch.FloatTensor(
        all_embeddings[[p["id"] - 1 for p in personas]].astype(np.float32)
    ).to(dev)                                              # (N, LLM_DIM)
    with torch.no_grad():
        p_embs = policy.persona_proj(e_llm_all).cpu()     # (N, 64) L2-normed

    all_traj_embs:  list[torch.Tensor] = []
    all_labels:     list[int]          = []
    per_persona_acc: list[float]       = []

    for p_idx, persona_dict in enumerate(personas):
        e_llm = torch.FloatTensor(
            all_embeddings[persona_dict["id"] - 1].astype(np.float32)
        ).unsqueeze(0).to(dev)                             # (1, LLM_DIM)
        pcfg  = PersonaConfig.from_dict(persona_dict)

        trajs = _rollout_persona(
            policy, e_llm, pcfg, n_episodes, dev,
            seed_offset=seed + p_idx * 1000,
            n_agents=n_agents,
            env_factory=env_factory,
        )
        if not trajs:
            continue

        t_embs = _encode_trajectories(traj_encoder, trajs, dev)  # (n_ep, 64)
        all_traj_embs.append(t_embs)
        all_labels.extend([p_idx] * len(trajs))

    if not all_traj_embs:
        return {"accuracy": 0.0, "intra_cos_mean": 0.0, "inter_cos_mean": 0.0}

    traj_emb_mat = torch.cat(all_traj_embs, dim=0)        # (total_trajs, 64)
    labels_arr   = np.array(all_labels)

    # Cosine similarity between trajectory embeddings and persona projections
    sim_mat = traj_emb_mat @ p_embs.T                     # (total_trajs, N_personas)

    # k-NN top-1 classification
    pred_labels = sim_mat.argmax(dim=1).numpy()
    top1_correct = (pred_labels == labels_arr).astype(float)
    accuracy     = top1_correct.mean()

    # Per-persona accuracy
    for p_idx in range(len(personas)):
        mask = labels_arr == p_idx
        if mask.any():
            per_persona_acc.append(float(top1_correct[mask].mean()))

    # Intra / inter cosine similarity (using trajectory-to-trajectory)
    n_total = traj_emb_mat.shape[0]
    intra, inter = [], []
    for i in range(n_total):
        for j in range(i + 1, n_total):
            cos = float((traj_emb_mat[i] * traj_emb_mat[j]).sum())
            if labels_arr[i] == labels_arr[j]:
                intra.append(cos)
            else:
                inter.append(cos)

    return {
        "accuracy":         float(accuracy),
        "intra_cos_mean":   float(np.mean(intra)) if intra else 0.0,
        "inter_cos_mean":   float(np.mean(inter)) if inter else 0.0,
        "per_persona_acc":  per_persona_acc,
        "n_trajectories":   n_total,
        "n_personas":       len(personas),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--policy",      default="results/pcsp/full/policy.pt")
    p.add_argument("--traj_enc",    default="results/pcsp/full/traj_encoder.pt")
    p.add_argument("--personas",    default="data/personas/train_240.json")
    p.add_argument("--embeddings",  default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--n_episodes",  type=int, default=5)
    p.add_argument("--n_personas",  type=int, default=24)
    p.add_argument("--device",      default="cuda")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    with open(ROOT / args.personas) as f:
        personas_data = json.load(f)
    all_emb = np.load(ROOT / args.embeddings)

    policy = PCSPActorCritic(OBS_DIM, N_ACTS)
    policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))

    traj_enc = TrajectoryEncoder(OBS_DIM, N_ACTS)
    traj_enc.load_state_dict(torch.load(ROOT / args.traj_enc, map_location="cpu"))

    result = persona_classification_accuracy(
        policy, traj_enc, personas_data, all_emb,
        n_episodes=args.n_episodes,
        n_personas=args.n_personas,
        device=args.device,
    )
    print(json.dumps(result, indent=2))
