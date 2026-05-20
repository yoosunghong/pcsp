"""T2.1 — held-out persona retrieval (within substrate) and cross-substrate
transfer (CH ↔ CU). Reuses Layer-2 checkpoints under
``research/meltingpot/runs/t1_2/*/{full,no_infonce}_seed{1,2,3}_1M/``.

Two modes:
  --mode held-out
      For each checkpoint, run rollouts conditioning each agent on one of the
      12 personas (10 train + 2 held-out), encode each agent's trajectory via
      the trained traj_encoder, and retrieve the persona id against the full
      12-vocab projection. Reports overall top-1/top-3 and a held-out-only
      slice. Chance top-1 = 1/12 ≈ 0.083.

  --mode cross
      Cross-substrate transfer. Use substrate S's traj_encoder and
      persona_proj on trajectories collected by substrate T's policy in T's
      environment. The traj encoder's GRU input layer is zero-padded from
      ``feat_dim + n_actions_S`` to ``feat_dim + n_actions_T`` when needed;
      no other parameters are touched. Restricted to CH ↔ CU (matched
      88×88×3 observations). Reports top-1/top-3 over S's 10 train
      personas (chance 0.10).

Outputs JSON per run to ``research/meltingpot/runs/t2_1/{mode}/...``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]                       # research/
REPO = RESEARCH.parent                            # repo root
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from cnn_film_policy import PCSPCnnFiLMActorCritic  # noqa: E402
from mp_env import MeltingPotEnv                      # noqa: E402
from src.models.trajectory_encoder import TrajectoryEncoder  # noqa: E402


SUBSTRATES = {
    "commons_harvest__open": {"n_actions": 8, "in_hw": 88, "n_agents": 7},
    "clean_up":              {"n_actions": 9, "in_hw": 88, "n_agents": 7},
    "prisoners_dilemma_in_the_matrix__repeated": {"n_actions": 8, "in_hw": 40, "n_agents": 2},
}


def load_personas():
    j = json.load(open(RESEARCH / "meltingpot/personas/personas_v0.json"))
    cache = torch.load(REPO / "results/embeddings/persona_emb_qwen_emb.pt",
                       map_location="cpu", weights_only=False)
    all_ids = cache["ids"]
    emb = cache["embeddings"].float()  # (12, 1024)
    train_ids = j["splits"]["train"]
    held_ids = j["splits"]["heldout"]
    full_ids = train_ids + held_ids
    full_idx = [all_ids.index(i) for i in full_ids]
    return {
        "full_ids": full_ids,
        "train_ids": train_ids,
        "held_ids": held_ids,
        "full_emb": emb[full_idx].contiguous(),  # (12, 1024)
        "train_emb": emb[[all_ids.index(i) for i in train_ids]].contiguous(),
        "held_emb": emb[[all_ids.index(i) for i in held_ids]].contiguous(),
    }


def build_policy(substrate: str, device) -> PCSPCnnFiLMActorCritic:
    cfg = SUBSTRATES[substrate]
    return PCSPCnnFiLMActorCritic(
        n_actions=cfg["n_actions"], in_channels=3,
        feat_dim=256, persona_dim=64, lora_r=16, in_hw=cfg["in_hw"],
    ).to(device)


def build_encoder(n_actions: int, device) -> TrajectoryEncoder:
    return TrajectoryEncoder(
        obs_dim=256, n_actions=n_actions, hidden_dim=128, output_dim=64,
    ).to(device)


def pad_encoder_action_dim(enc_src: TrajectoryEncoder, n_actions_tgt: int,
                           device) -> TrajectoryEncoder:
    """Zero-pad GRU input weights of a source encoder so it accepts a wider
    one-hot action vector. Source columns ``[:obs_dim+n_actions_src]`` are
    preserved verbatim; the new columns are zero. Layer-2 GRU is unchanged.
    """
    n_src = enc_src.n_actions
    if n_actions_tgt == n_src:
        return enc_src
    enc_tgt = build_encoder(n_actions_tgt, device)
    sd_src = enc_src.state_dict()
    sd_tgt = enc_tgt.state_dict()
    # GRU layer 0 input weight: shape (3*hidden, input_dim)
    w_ih_src = sd_src["gru.weight_ih_l0"]               # (3H, obs+n_src)
    w_ih_tgt = sd_tgt["gru.weight_ih_l0"].clone().zero_()
    keep = 256 + n_src
    w_ih_tgt[:, :keep] = w_ih_src
    sd_tgt["gru.weight_ih_l0"] = w_ih_tgt
    # Copy everything else as-is.
    for k in ["gru.weight_hh_l0", "gru.bias_ih_l0", "gru.bias_hh_l0",
              "gru.weight_ih_l1", "gru.weight_hh_l1",
              "gru.bias_ih_l1", "gru.bias_hh_l1",
              "proj.weight", "proj.bias"]:
        sd_tgt[k] = sd_src[k]
    enc_tgt.load_state_dict(sd_tgt)
    return enc_tgt


@torch.no_grad()
def rollout(env: MeltingPotEnv, policy: PCSPCnnFiLMActorCritic,
            persona_emb_per_agent: torch.Tensor, n_steps: int, device):
    """Run n_steps in env with each agent conditioned on its own persona
    embedding. Returns dict with obs_seq (T,A,H,W,3) uint8 and act_seq (T,A)
    int64."""
    A = env.n_agents
    H, W, C = env.obs_shape
    obs_buf = np.zeros((n_steps, A, H, W, C), dtype=np.uint8)
    act_buf = np.zeros((n_steps, A), dtype=np.int64)
    obs = env.reset()
    e_llm = persona_emb_per_agent.to(device)
    for t in range(n_steps):
        obs_buf[t] = obs
        obs_t = torch.from_numpy(obs).to(device)
        a, _, _ = policy.get_action(obs_t, e_llm)
        a_np = a.cpu().numpy()
        act_buf[t] = a_np
        obs, _, done = env.step(a_np)
        if done:
            obs = env.reset()
    return {"obs_seq": obs_buf, "act_seq": act_buf}


@torch.no_grad()
def encode_trajectories(policy: PCSPCnnFiLMActorCritic,
                        encoder: TrajectoryEncoder,
                        obs_seq: np.ndarray, act_seq: np.ndarray,
                        device) -> torch.Tensor:
    """obs_seq: (T,A,H,W,3) uint8. act_seq: (T,A). Returns (A, 64) L2-normed."""
    T, A, H, W, C = obs_seq.shape
    # (A, T, H, W, C) for feature extraction
    obs = torch.from_numpy(obs_seq.transpose(1, 0, 2, 3, 4)).to(device)  # (A,T,H,W,C)
    act = torch.from_numpy(act_seq.transpose(1, 0)).to(device)            # (A,T)
    feat = policy.features(obs.reshape(A * T, H, W, C)).view(A, T, -1)
    # Clip any out-of-vocab actions for cross-substrate (shouldn't happen if
    # padded correctly, but be defensive).
    act = act.clamp_(0, encoder.n_actions - 1)
    return encoder(feat, act)


@torch.no_grad()
def retrieve(traj_emb: torch.Tensor, persona_proj, vocab_emb_1024: torch.Tensor,
             vocab_ids, true_ids):
    """traj_emb: (B, 64). vocab_emb_1024: (P, 1024). Returns dict of metrics."""
    pemb = persona_proj(vocab_emb_1024.to(traj_emb.device))   # (P, 64)
    sim = traj_emb @ pemb.T                                    # (B, P)
    id_to_idx = {pid: i for i, pid in enumerate(vocab_ids)}
    labels = torch.tensor([id_to_idx[t] for t in true_ids], device=sim.device)
    top1 = sim.argmax(dim=-1)
    top3 = sim.topk(min(3, sim.shape[1]), dim=-1).indices
    return {
        "top1": float((top1 == labels).float().mean()),
        "top3": float((top3 == labels.unsqueeze(1)).any(dim=-1).float().mean()),
        "top1_pred_ids": [vocab_ids[int(i)] for i in top1.cpu().tolist()],
        "n": int(sim.shape[0]),
    }


def run_held_out(substrate: str, ckpt_dir: Path, n_steps: int,
                 device, n_repeats: int | None = None) -> dict:
    cfg = SUBSTRATES[substrate]
    pers = load_personas()
    full_ids = pers["full_ids"]
    full_emb = pers["full_emb"].to(device)        # (12, 1024)
    held_ids = set(pers["held_ids"])

    policy = build_policy(substrate, device)
    policy.load_state_dict(torch.load(ckpt_dir / "policy.pt", map_location=device,
                                       weights_only=False))
    policy.eval()
    encoder = build_encoder(cfg["n_actions"], device)
    encoder.load_state_dict(torch.load(ckpt_dir / "traj_encoder.pt",
                                        map_location=device, weights_only=False))
    encoder.eval()

    A = cfg["n_agents"]
    # Cycle 12 personas across n_agents over n_repeats rollouts so every
    # persona is observed by at least one agent at least once. Need ceil(12/A)
    # rollouts at minimum to cover all personas.
    if n_repeats is None:
        n_repeats = max(2, (12 + A - 1) // A)
    env = MeltingPotEnv(substrate, seed=0)
    try:
        traj_embs, true_ids = [], []
        for r in range(n_repeats):
            # Build a 12-persona schedule: agents 0..A-1 take personas
            # ((r*A + i) % 12).
            agent_persona_idx = [((r * A + i) % 12) for i in range(A)]
            persona_per_agent = full_emb[agent_persona_idx]   # (A, 1024)
            roll = rollout(env, policy, persona_per_agent, n_steps, device)
            te = encode_trajectories(policy, encoder, roll["obs_seq"],
                                     roll["act_seq"], device)
            traj_embs.append(te)
            true_ids.extend([full_ids[k] for k in agent_persona_idx])
        traj_emb = torch.cat(traj_embs, dim=0)
    finally:
        env.close()

    overall = retrieve(traj_emb, policy.persona_proj, full_emb, full_ids, true_ids)
    # Held-out slice: indices whose true persona is held-out.
    held_mask = np.array([t in held_ids for t in true_ids])
    if held_mask.any():
        held_te = traj_emb[torch.from_numpy(np.where(held_mask)[0]).to(device)]
        held_true = [true_ids[i] for i in np.where(held_mask)[0]]
        held = retrieve(held_te, policy.persona_proj, full_emb, full_ids, held_true)
        # Match-rate: how often the top-1 picked persona is *one of* the
        # held-out personas.
        held["held_picked_rate"] = float(
            np.mean([p in held_ids for p in held["top1_pred_ids"]])
        )
        held.pop("top1_pred_ids", None)
    else:
        held = None
    overall.pop("top1_pred_ids", None)
    return {
        "substrate": substrate,
        "ckpt_dir": str(ckpt_dir.relative_to(RESEARCH)),
        "n_steps": n_steps,
        "n_repeats": n_repeats,
        "n_trajectories": int(traj_emb.shape[0]),
        "overall": overall,
        "held_out": held,
    }


def run_cross(source_substrate: str, target_substrate: str,
              source_ckpt: Path, target_ckpt: Path,
              n_steps: int, device) -> dict:
    """Use SOURCE's persona_proj + traj_encoder (padded if needed) on
    trajectories generated by TARGET's policy in TARGET's environment."""
    assert SUBSTRATES[source_substrate]["in_hw"] == SUBSTRATES[target_substrate]["in_hw"], \
        "Cross-substrate transfer requires matching obs shape (88×88 only)."
    cfg_s = SUBSTRATES[source_substrate]
    cfg_t = SUBSTRATES[target_substrate]
    pers = load_personas()
    train_ids = pers["train_ids"]
    train_emb = pers["train_emb"].to(device)        # (10, 1024)

    # SOURCE checkpoint: policy gives us persona_proj + cnn used for encoding.
    policy_s = build_policy(source_substrate, device)
    policy_s.load_state_dict(torch.load(source_ckpt / "policy.pt",
                                         map_location=device, weights_only=False))
    policy_s.eval()
    encoder_s = build_encoder(cfg_s["n_actions"], device)
    encoder_s.load_state_dict(torch.load(source_ckpt / "traj_encoder.pt",
                                          map_location=device, weights_only=False))
    encoder_s.eval()
    # Pad to target action count (e.g., 8→9 for CH→CU; CU→CH truncates by clamp).
    if cfg_t["n_actions"] > cfg_s["n_actions"]:
        encoder_for_target = pad_encoder_action_dim(encoder_s,
                                                    cfg_t["n_actions"], device)
        encoder_for_target.eval()
    else:
        encoder_for_target = encoder_s

    # TARGET checkpoint: policy is used to *generate* trajectories on TARGET env.
    policy_t = build_policy(target_substrate, device)
    policy_t.load_state_dict(torch.load(target_ckpt / "policy.pt",
                                         map_location=device, weights_only=False))
    policy_t.eval()

    A_t = cfg_t["n_agents"]
    env = MeltingPotEnv(target_substrate, seed=0)
    try:
        n_train = len(train_ids)
        n_repeats = max(2, (n_train + A_t - 1) // A_t * 2)
        traj_embs, true_ids = [], []
        for r in range(n_repeats):
            agent_persona_idx = [((r * A_t + i) % n_train) for i in range(A_t)]
            persona_per_agent = train_emb[agent_persona_idx]
            roll = rollout(env, policy_t, persona_per_agent, n_steps, device)
            # Extract per-step features with SOURCE's CNN; encode with padded
            # SOURCE encoder.
            te = encode_trajectories(policy_s, encoder_for_target,
                                     roll["obs_seq"], roll["act_seq"], device)
            traj_embs.append(te)
            true_ids.extend([train_ids[k] for k in agent_persona_idx])
        traj_emb = torch.cat(traj_embs, dim=0)
    finally:
        env.close()

    # Retrieve against SOURCE's persona projection over the 10-train vocab.
    metrics = retrieve(traj_emb, policy_s.persona_proj, train_emb,
                       train_ids, true_ids)
    metrics.pop("top1_pred_ids", None)
    return {
        "source_substrate": source_substrate,
        "target_substrate": target_substrate,
        "source_ckpt": str(source_ckpt.relative_to(RESEARCH)),
        "target_ckpt": str(target_ckpt.relative_to(RESEARCH)),
        "n_steps": n_steps,
        "n_trajectories": int(traj_emb.shape[0]),
        "metrics": metrics,
        "chance_top1": 1.0 / len(train_ids),
        "chance_top3": 3.0 / len(train_ids),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["held-out", "cross"], required=True)
    p.add_argument("--n-steps", type=int, default=256)
    p.add_argument("--device", default="auto")
    p.add_argument("--out-dir", default=str(RESEARCH / "meltingpot/runs/t2_1"))
    p.add_argument("--ckpt-root", default=str(RESEARCH / "meltingpot/runs/t1_2"))
    args = p.parse_args()

    device = torch.device(
        "cuda" if (args.device == "auto" and torch.cuda.is_available())
        else (args.device if args.device != "auto" else "cpu")
    )
    print(f"[device] {device}", flush=True)
    ckpt_root = Path(args.ckpt_root)
    out_root = Path(args.out_dir) / args.mode
    out_root.mkdir(parents=True, exist_ok=True)

    # Substrate -> list[(label, ckpt_path)]
    ch_root = ckpt_root.parent / "cog_clean"
    ckpt_index: dict[str, list[tuple[str, Path]]] = {s: [] for s in SUBSTRATES}
    if ch_root.exists():
        for d in sorted(ch_root.iterdir()):
            if d.is_dir() and (d / "policy.pt").exists() and "1M" in d.name:
                ckpt_index["commons_harvest__open"].append((d.name, d))
    for substrate in ("clean_up", "prisoners_dilemma_in_the_matrix__repeated"):
        sub_dir = ckpt_root / substrate
        if sub_dir.exists():
            for d in sorted(sub_dir.iterdir()):
                if d.is_dir() and (d / "policy.pt").exists():
                    ckpt_index[substrate].append((d.name, d))

    results = []
    if args.mode == "held-out":
        for substrate, entries in ckpt_index.items():
            for label, ckpt in entries:
                print(f"[held-out] {substrate}/{label}", flush=True)
                r = run_held_out(substrate, ckpt, args.n_steps, device)
                r["condition"] = "no_infonce" if "no_infonce" in label else "full"
                r["label"] = label
                results.append(r)
                out_path = out_root / f"{substrate}__{label}.json"
                out_path.write_text(json.dumps(r, indent=2))
                ho = r["held_out"] or {}
                print(f"  overall top-1={r['overall']['top1']:.3f}  "
                      f"held top-1={ho.get('top1', float('nan')):.3f}  "
                      f"held picked-rate={ho.get('held_picked_rate', float('nan')):.3f}",
                      flush=True)
    else:
        # CH ↔ CU, full seeds 1/2/3 of each — only "full" (not no_infonce).
        def full_only(lst):
            return [(l, c) for l, c in lst if "no_infonce" not in l]
        ch_full = full_only(ckpt_index["commons_harvest__open"])[:3]
        cu_full = full_only(ckpt_index["clean_up"])[:3]
        if not ch_full or not cu_full:
            print("[skip] missing CH or CU full checkpoints")
        n = min(len(ch_full), len(cu_full))
        for direction in ("CH->CU", "CU->CH"):
            for k in range(n):
                ch_l, ch_c = ch_full[k]
                cu_l, cu_c = cu_full[k]
                if direction == "CH->CU":
                    src_sub, src_ck, tgt_sub, tgt_ck = (
                        "commons_harvest__open", ch_c, "clean_up", cu_c)
                    pair = f"CH-{ch_l}__to__CU-{cu_l}"
                else:
                    src_sub, src_ck, tgt_sub, tgt_ck = (
                        "clean_up", cu_c, "commons_harvest__open", ch_c)
                    pair = f"CU-{cu_l}__to__CH-{ch_l}"
                print(f"[cross] {pair}", flush=True)
                r = run_cross(src_sub, tgt_sub, src_ck, tgt_ck,
                              args.n_steps, device)
                r["pair"] = pair
                r["direction"] = direction
                results.append(r)
                (out_root / f"{pair}.json").write_text(json.dumps(r, indent=2))
                print(f"  top-1={r['metrics']['top1']:.3f}  "
                      f"top-3={r['metrics']['top3']:.3f}  "
                      f"(chance top-1={r['chance_top1']:.3f})", flush=True)
        # Aggregate
        for direction in ("CH->CU", "CU->CH"):
            sub = [r for r in results if r.get("direction") == direction]
            if sub:
                t1 = [r["metrics"]["top1"] for r in sub]
                t3 = [r["metrics"]["top3"] for r in sub]
                print(f"[agg {direction}] top-1 mean={np.mean(t1):.3f} "
                      f"std={np.std(t1):.3f}  top-3 mean={np.mean(t3):.3f} "
                      f"std={np.std(t3):.3f}  n={len(sub)}", flush=True)

    (out_root / "summary.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} run(s) to {out_root}", flush=True)


if __name__ == "__main__":
    main()
