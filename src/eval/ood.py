"""OOD / held-out persona evaluator (Phase 4).

This module loads a trained PCSP checkpoint and runs a *frozen* rollout
under one of four persona-assignment regimes:

- ``train``      — random sampling from the train pool (in-distribution).
- ``heldout``    — random sampling from the held-out pool (zero-shot OOD).
- ``mixed``      — each env has a fixed cast of half train / half heldout.
- ``all``        — random sampling from the full registry.

It then computes:

1. Retrieval top-1 / top-3 against (a) the full vocabulary, (b) the train
   subset only, (c) the heldout subset only. Implemented via
   :class:`InfoNCEHead.logits(candidate_indices=...)`.
2. Per-persona action distributions and pairwise behavioural KL between
   personas. The mean train-vs-heldout block-KL is reported alongside
   the within-block KLs.
3. Persona-embedding cosine distance vs behavioral action-KL
   correlation (Spearman ρ on the upper triangle).
4. Nearest-neighbour retrieval diagnostics: for every persona, the
   top-3 nearest personas by trajectory-embedding centroid; reports the
   fraction of "right-split" neighbours (a train persona should
   neighbour mostly train personas under a non-leaky encoder).
5. Per-seed per-persona stability: top-1 retrieval per persona, used by
   the cross-seed summarizer to compute std across seeds.

The evaluator is purely *post-hoc*: it never mutates the loaded
checkpoint or its optimizer state, and it never writes to a training
log. All outputs go into a single ``ood_eval.json`` next to the
checkpoint by default.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from src.persona import (
    InfoNCEHead,
    PersonaRegistry,
    TrajectoryEncoder,
    build_assigner,
    build_encoder,
    build_conditioning_head,
    load_personas,
    split_indices,
)
from src.training.cleanrl_ppo.config import PPOConfig
from src.training.cleanrl_ppo.networks import ActorCritic
from src.training.cleanrl_ppo.trainer import resolve_device, seed_everything

from .analysis import DEFAULT_ANALYSIS_HOOKS, persona_arithmetic


@dataclass
class OODEvalConfig:
    """Configuration for one OOD-eval pass."""

    checkpoint_path: str
    eval_split: str = "heldout"                       # train|heldout|all
    eval_assignment: str = "random"                   # random|population
    eval_population_kind: str | None = "heldout_only"  # used when assignment==population
    eval_steps: int = 1024
    num_envs: int = 8
    seed: int = 12345
    device: str = "auto"
    output_dir: str | None = None
    persona_path: str = "research/meltingpot/personas/personas_v0.json"
    substrate: str = "commons_harvest__open"
    # Diagnostic toggles
    run_analysis_hooks: bool = True
    run_persona_arithmetic: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ----- Small utilities -------------------------------------------------------


def _spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman ρ without scipy."""
    if x.size < 3:
        return float("nan")
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = float(np.sqrt((rx * rx).sum() * (ry * ry).sum()))
    if denom == 0:
        return float("nan")
    return float((rx * ry).sum() / denom)


def _action_kl(p: np.ndarray, q: np.ndarray, eps: float = 1e-8) -> float:
    p = p + eps
    q = q + eps
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))


def _retrieval_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    k: int = 3,
) -> dict:
    pred = logits.argmax(dim=-1)
    top1 = (pred == targets).float().mean().item()
    kk = min(k, logits.shape[-1])
    _, topk_idx = logits.topk(kk, dim=-1)
    topk = (topk_idx == targets.unsqueeze(-1)).any(dim=-1).float().mean().item()
    return {f"top1": top1, f"top{kk}": topk}


# ----- Loading model state from a checkpoint --------------------------------


def _load_components(
    cfg: PPOConfig,
    *,
    spec,
    device: torch.device,
    ckpt_path: str | os.PathLike,
) -> dict:
    """Load agent + persona encoder + trajectory encoder + InfoNCE head."""
    registry = load_personas(cfg.persona_path)
    persona_encoder = build_encoder(
        registry,
        source=cfg.persona_source,
        embedding_dim=cfg.persona_embedding_dim,
        cache_path=cfg.persona_cache_path,
        seed=cfg.persona_seed,
    ).to(device)

    conditioning_head = None
    if cfg.persona_conditioning != "none":
        conditioning_head = build_conditioning_head(
            mode=cfg.persona_conditioning,
            feature_dim=cfg.feature_dim,
            persona_dim=persona_encoder.embedding_dim,
        )

    agent = ActorCritic(
        obs_height=spec.obs_height,
        obs_width=spec.obs_width,
        obs_channels=spec.obs_channels,
        num_actions=spec.num_actions,
        feature_dim=cfg.feature_dim,
        use_lstm=cfg.use_lstm,
        lstm_hidden=cfg.lstm_hidden,
        conditioning=conditioning_head,
    ).to(device)

    traj_encoder: TrajectoryEncoder | None = None
    infonce_head: InfoNCEHead | None = None
    if cfg.infonce_coef > 0.0 and cfg.persona_conditioning != "none":
        traj_encoder = TrajectoryEncoder(
            num_actions=spec.num_actions,
            traj_dim=cfg.infonce_traj_dim,
            hidden_dim=cfg.infonce_traj_hidden,
            include_reward=cfg.infonce_include_reward,
        ).to(device)
        infonce_head = InfoNCEHead(
            traj_dim=cfg.infonce_traj_dim,
            persona_dim=persona_encoder.embedding_dim,
            temperature=cfg.infonce_temperature,
        ).to(device)

    blob = torch.load(ckpt_path, map_location=device, weights_only=False)
    agent.load_state_dict(blob["model"])
    if traj_encoder is not None and blob.get("trajectory_encoder") is not None:
        traj_encoder.load_state_dict(blob["trajectory_encoder"])
    if infonce_head is not None and blob.get("infonce_head") is not None:
        infonce_head.load_state_dict(blob["infonce_head"])

    return {
        "registry": registry,
        "persona_encoder": persona_encoder,
        "agent": agent,
        "traj_encoder": traj_encoder,
        "infonce_head": infonce_head,
        "checkpoint_update": int(blob.get("update", -1)),
    }


# ----- Frozen evaluation rollout --------------------------------------------


@torch.no_grad()
def _rollout(
    *,
    env,
    agent: ActorCritic,
    persona_encoder,
    assigner,
    num_steps: int,
    device: torch.device,
):
    obs = env.reset(seed=12345)
    batch = env.num_envs * env.num_players

    assignment = assigner.initial()
    current_persona = torch.as_tensor(
        assignment.reshape(batch), device=device, dtype=torch.long
    )

    obs_t = torch.as_tensor(
        obs.reshape(batch, *obs.shape[2:]), device=device, dtype=torch.uint8
    )
    done_t = torch.zeros(batch, device=device, dtype=torch.float32)

    actions_buf = torch.zeros(num_steps, batch, dtype=torch.long, device=device)
    rewards_buf = torch.zeros(num_steps, batch, dtype=torch.float32, device=device)
    dones_buf = torch.zeros(num_steps, batch, dtype=torch.float32, device=device)
    persona_buf = torch.zeros(num_steps, batch, dtype=torch.long, device=device)
    ep_returns: list[tuple[int, float]] = []
    ep_running = np.zeros(batch, dtype=np.float32)

    for t in range(num_steps):
        persona_emb = persona_encoder(current_persona)
        action, _logp, _val, _ = agent.act(obs_t, persona=persona_emb)
        actions_np = action.cpu().numpy().reshape(env.num_envs, env.num_players)
        next_obs, rew, done, _trunc, _infos = env.step(actions_np)

        rew_flat = rew.reshape(batch).astype(np.float32)
        done_per_env = done.astype(np.float32)
        done_flat = np.repeat(done_per_env, env.num_players).astype(np.float32)

        actions_buf[t] = action
        rewards_buf[t] = torch.as_tensor(rew_flat, device=device)
        dones_buf[t] = done_t  # before-step convention, matches trainer
        persona_buf[t] = current_persona

        ep_running += rew_flat
        for i in np.where(done_flat > 0.5)[0]:
            ep_returns.append((int(persona_buf[t, i].item()), float(ep_running[i])))
            ep_running[i] = 0.0

        obs_t = torch.as_tensor(
            next_obs.reshape(batch, *next_obs.shape[2:]),
            device=device,
            dtype=torch.uint8,
        )
        done_t = torch.as_tensor(done_flat, device=device)

        if done_per_env.any():
            new_assignment = assigner.on_done(done_per_env.astype(bool))
            current_persona = torch.as_tensor(
                new_assignment.reshape(batch), device=device, dtype=torch.long
            )

    return {
        "actions": actions_buf,
        "rewards": rewards_buf,
        "dones": dones_buf,
        "persona_ids": persona_buf,
        "final_persona_ids": current_persona,
        "episode_returns": ep_returns,
    }


# ----- Metric computation ---------------------------------------------------


def _per_persona_action_dist(
    actions: torch.Tensor,
    persona_ids: torch.Tensor,
    num_actions: int,
) -> dict[int, np.ndarray]:
    a = actions.reshape(-1).cpu().numpy()
    p = persona_ids.reshape(-1).cpu().numpy()
    out: dict[int, np.ndarray] = {}
    for pid in np.unique(p):
        mask = p == pid
        counts = np.bincount(a[mask], minlength=num_actions).astype(np.float64)
        total = counts.sum()
        if total > 0:
            out[int(pid)] = counts / total
    return out


def _pairwise_kl_matrix(dists: dict[int, np.ndarray]) -> tuple[np.ndarray, list[int]]:
    keys = sorted(dists.keys())
    K = len(keys)
    mat = np.zeros((K, K), dtype=np.float64)
    for i, a in enumerate(keys):
        for j, b in enumerate(keys):
            if i == j:
                continue
            mat[i, j] = _action_kl(dists[a], dists[b])
    return mat, keys


def _embedding_distance_matrix(
    persona_table: torch.Tensor, keys: list[int]
) -> np.ndarray:
    sub = persona_table[keys].cpu().numpy()
    sub_n = sub / (np.linalg.norm(sub, axis=1, keepdims=True) + 1e-8)
    cos = sub_n @ sub_n.T
    return 1.0 - cos     # cosine distance


# ----- Public entry point ---------------------------------------------------


def run_ood_eval(eval_cfg: OODEvalConfig) -> dict:
    """Run one OOD-eval pass; return the full result dict and write JSON."""
    ckpt_path = Path(eval_cfg.checkpoint_path).resolve()
    run_dir = ckpt_path.parent.parent          # .../runs/<name>/checkpoints/ckpt.pt
    cfg_path = run_dir / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Missing config.json next to checkpoint: {cfg_path}")
    cfg_dict = json.loads(cfg_path.read_text())
    cfg = PPOConfig(**{k: v for k, v in cfg_dict.items() if k in PPOConfig.__dataclass_fields__})

    device = resolve_device(eval_cfg.device or cfg.device)
    seed_everything(eval_cfg.seed)

    # Lazy env import so this module remains usable in offline analyses.
    from src.env.meltingpot import SyncVectorMeltingPot

    env = SyncVectorMeltingPot(
        cfg.substrate,
        num_envs=eval_cfg.num_envs,
        num_players=cfg.num_players,
        base_seed=eval_cfg.seed,
    )

    try:
        spec = env.spec
        comp = _load_components(cfg, spec=spec, device=device, ckpt_path=ckpt_path)
        registry: PersonaRegistry = comp["registry"]
        persona_encoder = comp["persona_encoder"]
        agent = comp["agent"]
        traj_encoder = comp["traj_encoder"]
        infonce_head = comp["infonce_head"]

        agent.eval()
        if traj_encoder is not None:
            traj_encoder.eval()
        if infonce_head is not None:
            infonce_head.eval()

        assigner = build_assigner(
            registry,
            mode=eval_cfg.eval_assignment,
            num_envs=env.num_envs,
            num_players=env.num_players,
            seed=eval_cfg.seed,
            split=eval_cfg.eval_split if eval_cfg.eval_assignment != "population" else "all",
            population_kind=(
                eval_cfg.eval_population_kind
                if eval_cfg.eval_assignment == "population"
                else None
            ),
        )

        roll = _rollout(
            env=env,
            agent=agent,
            persona_encoder=persona_encoder,
            assigner=assigner,
            num_steps=eval_cfg.eval_steps,
            device=device,
        )
    finally:
        env.close()

    train_idx = split_indices(registry, "train") if "train" in registry.splits else []
    held_idx = split_indices(registry, "heldout") if "heldout" in registry.splits else []
    persona_table = persona_encoder.table

    actions = roll["actions"]
    rewards = roll["rewards"]
    dones = roll["dones"]
    persona_ids = roll["persona_ids"]

    # 1) Retrieval ---------------------------------------------------------
    retrieval: dict = {}
    if traj_encoder is not None and infonce_head is not None:
        with torch.no_grad():
            z_traj = traj_encoder(actions, rewards, dones)            # (B, D_traj)
            final_ids = roll["final_persona_ids"]                     # (B,)
            full_logits = infonce_head.logits(z_traj, persona_table)
            retrieval["full"] = _retrieval_metrics(full_logits, final_ids, k=3)
            if train_idx:
                cand = torch.as_tensor(train_idx, device=device, dtype=torch.long)
                mapping = {int(c): k for k, c in enumerate(train_idx)}
                # Only score targets whose persona is in the candidate set.
                mask = torch.as_tensor(
                    [int(i) in mapping for i in final_ids.cpu().tolist()],
                    device=device, dtype=torch.bool,
                )
                if mask.any():
                    sub_logits = infonce_head.logits(
                        z_traj[mask], persona_table, candidate_indices=cand
                    )
                    sub_targets = torch.as_tensor(
                        [mapping[int(i)] for i in final_ids[mask].cpu().tolist()],
                        device=device, dtype=torch.long,
                    )
                    retrieval["train_only"] = _retrieval_metrics(sub_logits, sub_targets, k=3)
                    retrieval["train_only"]["n"] = int(mask.sum().item())
            if held_idx:
                cand = torch.as_tensor(held_idx, device=device, dtype=torch.long)
                mapping = {int(c): k for k, c in enumerate(held_idx)}
                mask = torch.as_tensor(
                    [int(i) in mapping for i in final_ids.cpu().tolist()],
                    device=device, dtype=torch.bool,
                )
                if mask.any():
                    sub_logits = infonce_head.logits(
                        z_traj[mask], persona_table, candidate_indices=cand
                    )
                    sub_targets = torch.as_tensor(
                        [mapping[int(i)] for i in final_ids[mask].cpu().tolist()],
                        device=device, dtype=torch.long,
                    )
                    retrieval["heldout_only"] = _retrieval_metrics(sub_logits, sub_targets, k=3)
                    retrieval["heldout_only"]["n"] = int(mask.sum().item())
            # Per-persona top-1 (against the *full* vocabulary).
            pred_full = full_logits.argmax(dim=-1).cpu().numpy()
            tgt_np = final_ids.cpu().numpy()
            per_persona_top1: dict[str, float] = {}
            for pid in np.unique(tgt_np):
                m = tgt_np == pid
                per_persona_top1[registry.index_to_id(int(pid))] = float(
                    (pred_full[m] == pid).mean()
                ) if m.any() else float("nan")
            retrieval["per_persona_top1_full"] = per_persona_top1

    # 2) Per-persona action distributions + KLs ---------------------------
    dists = _per_persona_action_dist(actions, persona_ids, spec.num_actions)
    pair_kl_mat, keys = _pairwise_kl_matrix(dists)
    mean_pairwise_kl = float(pair_kl_mat[pair_kl_mat > 0].mean()) if (pair_kl_mat > 0).any() else 0.0

    # train-vs-heldout block KL
    train_keys = [k for k in keys if k in set(train_idx)]
    held_keys = [k for k in keys if k in set(held_idx)]
    block_kls = []
    if train_keys and held_keys:
        for a in train_keys:
            ia = keys.index(a)
            for b in held_keys:
                ib = keys.index(b)
                block_kls.append(float(pair_kl_mat[ia, ib]))
        train_vs_heldout_kl = float(np.mean(block_kls))
    else:
        train_vs_heldout_kl = float("nan")

    # 3) Embedding distance vs behavioral KL correlation ------------------
    embed_dist = _embedding_distance_matrix(persona_table, keys)
    # Symmetrise behavior KL for correlation (KL is asymmetric).
    sym_kl = 0.5 * (pair_kl_mat + pair_kl_mat.T)
    iu = np.triu_indices(len(keys), k=1)
    rho = _spearman_rho(embed_dist[iu], sym_kl[iu]) if len(keys) > 2 else float("nan")

    # 4) Nearest-neighbour diagnostics ------------------------------------
    nn_diag: dict = {}
    if traj_encoder is not None and infonce_head is not None and keys:
        with torch.no_grad():
            z_traj = traj_encoder(actions, rewards, dones)
            # Centroid per persona id in z_traj space.
            ids = roll["final_persona_ids"].cpu().numpy()
            centroids: dict[int, torch.Tensor] = {}
            for pid in np.unique(ids):
                mask = torch.as_tensor(ids == pid, device=device)
                if mask.any():
                    centroids[int(pid)] = z_traj[mask].mean(dim=0)
            if centroids:
                cmat = torch.stack([centroids[k] for k in keys], dim=0)  # (K', D)
                cmat = F.normalize(cmat, dim=-1)
                sim = (cmat @ cmat.t()).cpu().numpy()
                # For each key: top-3 nearest other keys (exclude self)
                top3_neighbours: dict[str, list[str]] = {}
                right_split_frac: list[float] = []
                for i, k_idx in enumerate(keys):
                    sims_row = sim[i].copy()
                    sims_row[i] = -np.inf
                    nn = np.argsort(sims_row)[::-1][:3]
                    neighbours = [registry.index_to_id(keys[j]) for j in nn]
                    top3_neighbours[registry.index_to_id(k_idx)] = neighbours
                    # Right-split fraction: how many of the 3 NN share the
                    # train/heldout membership of the anchor?
                    anchor_in_train = k_idx in set(train_idx)
                    same = sum(
                        ((keys[j] in set(train_idx)) == anchor_in_train) for j in nn
                    )
                    right_split_frac.append(same / max(1, len(nn)))
                nn_diag = {
                    "top3_neighbours": top3_neighbours,
                    "mean_right_split_frac": float(np.mean(right_split_frac)),
                }

    # 5) Per-persona episode returns --------------------------------------
    ep_by_persona: dict[str, list[float]] = {}
    for pid, ret in roll["episode_returns"]:
        ep_by_persona.setdefault(registry.index_to_id(int(pid)), []).append(float(ret))
    ep_summary = {
        k: {"mean": float(np.mean(v)), "n": len(v)} for k, v in ep_by_persona.items()
    }

    # 6) Analysis hooks ----------------------------------------------------
    hook_out: dict = {}
    if eval_cfg.run_analysis_hooks and traj_encoder is not None:
        with torch.no_grad():
            z_traj_h = traj_encoder(actions, rewards, dones)
            final_ids_h = roll["final_persona_ids"]
            for hook in DEFAULT_ANALYSIS_HOOKS:
                try:
                    hook_out[hook.name] = hook.fn(z_traj_h, final_ids_h, persona_table)
                except Exception as e:  # pragma: no cover - hooks are stubs
                    hook_out[hook.name] = {"error": str(e)}

    arithmetic_out: dict = {}
    if eval_cfg.run_persona_arithmetic:
        ids = [registry.index_to_id(i) for i in range(registry.num_personas)]
        # Run on a small, interpretable subset of pairs to keep output bounded.
        sample_pairs = [
            (registry.id_to_index("cooperative_sustainer"),
             registry.id_to_index("aggressive_zapper")),
            (registry.id_to_index("cleaner_helper"),
             registry.id_to_index("free_rider")),
            (registry.id_to_index("explorer"),
             registry.id_to_index("territorial_defender")),
        ] if "cooperative_sustainer" in [p.id for p in registry.personas] else None
        arithmetic_out = persona_arithmetic(
            persona_table, pairs=sample_pairs, ids=ids
        )

    # 7) Assemble report --------------------------------------------------
    summary = {
        "eval_cfg": eval_cfg.to_dict(),
        "checkpoint": {
            "path": str(ckpt_path),
            "update": comp["checkpoint_update"],
        },
        "run_cfg": {
            "substrate": cfg.substrate,
            "persona_conditioning": cfg.persona_conditioning,
            "persona_source": cfg.persona_source,
            "persona_embedding_dim": cfg.persona_embedding_dim,
            "persona_cache_path": cfg.persona_cache_path,
            "infonce_coef": cfg.infonce_coef,
            "kl_diversity_coef": cfg.kl_diversity_coef,
            "seed": cfg.seed,
        },
        "splits": {
            "train": [registry.index_to_id(i) for i in train_idx],
            "heldout": [registry.index_to_id(i) for i in held_idx],
            "leakage_train_pool_contains_heldout":
                bool(set(train_idx) & set(held_idx)),
        },
        "retrieval": retrieval,
        "behavior": {
            "personas_seen": [registry.index_to_id(k) for k in keys],
            "mean_pairwise_action_kl": mean_pairwise_kl,
            "train_vs_heldout_action_kl": train_vs_heldout_kl,
            "n_block_pairs": len(block_kls),
        },
        "correlation": {
            "embed_distance_vs_action_kl_spearman_rho": rho,
            "n_pairs": int(len(iu[0])),
        },
        "nearest_neighbours": nn_diag,
        "episode_returns_per_persona": ep_summary,
        "analysis_hooks": hook_out,
        "persona_arithmetic": arithmetic_out,
    }

    out_dir = Path(eval_cfg.output_dir) if eval_cfg.output_dir else (run_dir / "ood_evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{eval_cfg.eval_split}-{eval_cfg.eval_assignment}"
    if eval_cfg.eval_assignment == "population":
        tag += f"-{eval_cfg.eval_population_kind}"
    out_path = out_dir / f"ood_eval__{tag}__seed{eval_cfg.seed}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    summary["_output_path"] = str(out_path)
    return summary
