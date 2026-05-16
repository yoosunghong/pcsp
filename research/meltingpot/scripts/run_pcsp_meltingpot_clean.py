"""Phase A pilot: faithful Mini-Inzoi §III PCSP on Melting Pot commons_harvest__open.

Single-substrate external validation rerun for the COG2026 paper. The only
deviation from §III is the CNN front-end (image obs → 256-d feature) before
the FiLM trunk; everything else (LoRA r=16 1024→64, 3-FiLM-block trunk,
2-layer GRU traj encoder, InfoNCE T=0.07 λ=0.5 with full-batch contrast pool,
KL diversity λ=0.1 over 8×32, PPO γ=0.99 GAE-λ=0.95 clip=0.2 ent=0.01,
LoRA lr=1e-4, traj lr=3e-4) matches the source-of-truth pcsp_trainer.py.

Usage:
  python run_pcsp_meltingpot_clean.py --total-env-steps 500000 --seed 1 \
      --run-dir research/meltingpot/runs/cog_clean_pilot
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

REPO = Path(__file__).resolve().parents[3]                # co-spec/
RESEARCH = Path(__file__).resolve().parents[2]            # co-spec/research/
sys.path.insert(0, str(RESEARCH))

from src.models.trajectory_encoder import TrajectoryEncoder  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cnn_film_policy import PCSPCnnFiLMActorCritic  # noqa: E402
from mp_env import MeltingPotEnv  # noqa: E402


# ── persona loading ───────────────────────────────────────────────────────────

def load_personas(personas_json: Path, embed_pt: Path):
    with open(personas_json) as f:
        meta = json.load(f)
    cache = torch.load(embed_pt, map_location="cpu", weights_only=False)
    ids: list[str] = cache["ids"]
    emb: torch.Tensor = cache["embeddings"].float()  # (12, 1024)
    train_ids = meta["splits"]["train"]
    held_ids  = meta["splits"]["heldout"]
    train_idx = [ids.index(i) for i in train_ids]
    held_idx  = [ids.index(i) for i in held_ids]
    return {
        "ids":       ids,
        "train_ids": train_ids,
        "held_ids":  held_ids,
        "train_emb": emb[train_idx].contiguous(),  # (10, 1024)
        "held_emb":  emb[held_idx].contiguous(),   # (2, 1024)
    }


# ── GAE ───────────────────────────────────────────────────────────────────────

def compute_gae(rewards, values, dones, last_value, gamma: float, lam: float):
    """rewards/values/dones: (T, A); last_value: (A,). Returns (advs, rets) (T,A)."""
    T, A = rewards.shape
    advs = np.zeros_like(rewards, dtype=np.float32)
    last_gae = np.zeros(A, dtype=np.float32)
    next_val = last_value.astype(np.float32)
    next_nonterminal = 1.0 - dones[-1].astype(np.float32)
    for t in reversed(range(T)):
        if t < T - 1:
            next_val = values[t + 1]
            next_nonterminal = 1.0 - dones[t].astype(np.float32)
        delta = rewards[t] + gamma * next_val * next_nonterminal - values[t]
        last_gae = delta + gamma * lam * next_nonterminal * last_gae
        advs[t] = last_gae
    rets = advs + values
    return advs, rets


# ── Eval metrics ──────────────────────────────────────────────────────────────

@torch.no_grad()
def eval_pairwise_action_kl(policy, obs_buf: torch.Tensor, train_emb: torch.Tensor,
                            n_states: int = 64) -> float:
    """obs_buf: (N, H, W, 3) float in [0,1] OR uint8. train_emb: (P, 1024)."""
    N = obs_buf.shape[0]
    n_states = min(n_states, N)
    idx = torch.randperm(N)[:n_states]
    obs_s = obs_buf[idx].to(train_emb.device)
    P = train_emb.shape[0]
    obs_rep = obs_s.unsqueeze(0).expand(P, -1, *([-1] * (obs_s.dim() - 1))).reshape(-1, *obs_s.shape[1:])
    e_rep   = train_emb.unsqueeze(1).expand(-1, n_states, -1).reshape(-1, train_emb.shape[-1])
    logits = policy.action_logits(obs_rep, e_rep).view(P, n_states, -1)
    log_probs = F.log_softmax(logits, dim=-1)
    probs = log_probs.exp()
    total, n_pairs = 0.0, 0
    for i in range(P):
        for j in range(i + 1, P):
            kl = F.kl_div(log_probs[i], probs[j], reduction="batchmean")
            if torch.isfinite(kl):
                total += float(kl)
                n_pairs += 1
    return total / max(1, n_pairs)


@torch.no_grad()
def eval_retrieval(traj_encoder, policy, trajectories, train_emb, train_ids,
                   device) -> dict:
    """Top-1 / top-3 trajectory→persona retrieval over train personas."""
    if not trajectories:
        return {"top1": 0.0, "top3": 0.0, "n": 0}
    max_T = min(max(len(t["obs_seq"]) for t in trajectories), 200)
    H, W, C = trajectories[0]["obs_seq"].shape[1:]
    B = len(trajectories)
    obs_b = np.zeros((B, max_T, H, W, C), dtype=np.uint8)
    act_b = np.zeros((B, max_T), dtype=np.int64)
    pids  = []
    for k, t in enumerate(trajectories):
        T = min(len(t["obs_seq"]), max_T)
        obs_b[k, :T] = t["obs_seq"][:T]
        act_b[k, :T] = t["act_seq"][:T]
        pids.append(t["persona_id"])
    # Encode per-step CNN features (B*T) → (B, T, feat_dim)
    obs_t = torch.from_numpy(obs_b).to(device)               # uint8
    act_t = torch.from_numpy(act_b).to(device)
    feat = policy.features(obs_t.view(B * max_T, H, W, C)).view(B, max_T, -1)
    traj_emb = traj_encoder(feat, act_t)                     # (B, 64) L2-normed
    persona_emb = policy.persona_proj(train_emb.to(device))  # (P, 64) L2-normed
    sim = traj_emb @ persona_emb.T                           # (B, P)
    pid_to_idx = {pid: i for i, pid in enumerate(train_ids)}
    labels = torch.tensor([pid_to_idx[p] for p in pids], device=device)
    top3 = sim.topk(min(3, sim.shape[1]), dim=-1).indices
    top1 = sim.argmax(dim=-1)
    return {
        "top1": float((top1 == labels).float().mean()),
        "top3": float((top3 == labels.unsqueeze(1)).any(dim=-1).float().mean()),
        "n":    B,
    }


# ── Training loop ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--substrate", default="commons_harvest__open")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-env-steps", type=int, default=500_000)
    p.add_argument("--num-envs", type=int, default=4, help="serial episode collections per rollout")
    p.add_argument("--num-steps", type=int, default=256, help="steps per env per rollout")
    p.add_argument("--lr", type=float, default=2.5e-4)
    p.add_argument("--lora-lr", type=float, default=1e-4)
    p.add_argument("--traj-lr", type=float, default=3e-4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--gae-lambda", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--vf-coef", type=float, default=0.5)
    p.add_argument("--max-grad-norm", type=float, default=0.5)
    p.add_argument("--update-epochs", type=int, default=4)
    p.add_argument("--num-minibatches", type=int, default=4)
    p.add_argument("--lambda-consistency", type=float, default=0.5)
    p.add_argument("--lambda-diversity",   type=float, default=0.1)
    p.add_argument("--temperature", type=float, default=0.07)
    p.add_argument("--n-div-personas", type=int, default=8)
    p.add_argument("--n-div-states",   type=int, default=32)
    p.add_argument("--persona-dim",    type=int, default=64)
    p.add_argument("--lora-r",         type=int, default=16)
    p.add_argument("--traj-hidden",    type=int, default=128)
    p.add_argument("--feat-dim",       type=int, default=256)
    p.add_argument("--persona-json", default=str(RESEARCH / "meltingpot/personas/personas_v0.json"))
    p.add_argument("--persona-cache", default=str(REPO / "results/embeddings/persona_emb_qwen_emb.pt"))
    p.add_argument("--run-dir", required=True)
    p.add_argument("--eval-every", type=int, default=10)
    p.add_argument("--device", default="auto")
    p.add_argument("--ablation-no-infonce", action="store_true",
                   help="Set λ_consistency=0 (Phase C optional ablation)")
    p.add_argument("--collective-reward-alpha", type=float, default=0.0,
                   help="Per-step reward shaping: r_i ← r_i + alpha * mean_j(r_j). "
                        "Persona-agnostic potential to escape the apple-depletion trap. "
                        "Alpha=0 disables (default). For MP commons_harvest we use 0.1.")
    args = p.parse_args()

    if args.ablation_no_infonce:
        args.lambda_consistency = 0.0

    device = torch.device(
        "cuda" if (args.device == "auto" and torch.cuda.is_available())
        else (args.device if args.device != "auto" else "cpu")
    )
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(json.dumps(vars(args), indent=2))
    log_f = open(run_dir / "logs.jsonl", "w", buffering=1)

    # ── Personas + env probe ───────────────────────────────────────────────
    pers = load_personas(Path(args.persona_json), Path(args.persona_cache))
    train_emb = pers["train_emb"].to(device)        # (10, 1024)
    n_train_p = train_emb.shape[0]

    probe = MeltingPotEnv(args.substrate, seed=args.seed)
    n_agents = probe.n_agents
    n_actions = probe.n_actions
    H, W, C = probe.obs_shape
    probe.close()
    print(f"[env] substrate={args.substrate} n_agents={n_agents} "
          f"n_actions={n_actions} obs={(H,W,C)}", flush=True)
    print(f"[personas] train={pers['train_ids']}\n           held={pers['held_ids']}", flush=True)

    # ── Models ─────────────────────────────────────────────────────────────
    policy = PCSPCnnFiLMActorCritic(
        n_actions=n_actions, in_channels=C,
        feat_dim=args.feat_dim, persona_dim=args.persona_dim,
        lora_r=args.lora_r, in_hw=H,
    ).to(device)
    traj_encoder = TrajectoryEncoder(
        obs_dim=args.feat_dim, n_actions=n_actions,
        hidden_dim=args.traj_hidden, output_dim=args.persona_dim,
    ).to(device)

    proj_ids = {id(q) for q in policy.persona_proj.parameters()}
    other = [q for q in policy.parameters() if id(q) not in proj_ids and q.requires_grad]
    proj  = [q for q in policy.persona_proj.parameters() if q.requires_grad]
    optim = Adam([{"params": other, "lr": args.lr}, {"params": proj, "lr": args.lora_lr}])
    optim_traj = Adam(traj_encoder.parameters(), lr=args.traj_lr)

    n_pol_params = sum(q.numel() for q in policy.parameters())
    n_traj_params = sum(q.numel() for q in traj_encoder.parameters())
    print(f"[model] policy={n_pol_params:,} traj={n_traj_params:,} device={device}", flush=True)

    # ── Per-env state ──────────────────────────────────────────────────────
    envs   = [MeltingPotEnv(args.substrate) for _ in range(args.num_envs)]
    cur_obs = []         # (n_agents, H, W, 3) uint8
    cur_personas = []    # list[list[int]] persona idx into pers['train_ids'] per agent
    rng = np.random.default_rng(args.seed)
    for e in envs:
        cur_obs.append(e.reset())
        cur_personas.append(rng.choice(n_train_p, size=n_agents, replace=False).tolist())

    total_env_steps = 0
    update_idx = 0
    t_start = time.time()

    while total_env_steps < args.total_env_steps:
        update_idx += 1
        T = args.num_steps
        N = args.num_envs

        obs_buf  = np.zeros((T, N, n_agents, H, W, C), dtype=np.uint8)
        act_buf  = np.zeros((T, N, n_agents), dtype=np.int64)
        rew_buf  = np.zeros((T, N, n_agents), dtype=np.float32)
        done_buf = np.zeros((T, N), dtype=np.bool_)
        val_buf  = np.zeros((T, N, n_agents), dtype=np.float32)
        lp_buf   = np.zeros((T, N, n_agents), dtype=np.float32)
        pid_buf  = np.zeros((T, N, n_agents), dtype=np.int64)

        # Per-(env,agent) trajectory snapshot for InfoNCE: full rollout window
        traj_obs_lists = [[[] for _ in range(n_agents)] for _ in range(N)]
        traj_act_lists = [[[] for _ in range(n_agents)] for _ in range(N)]
        traj_persona   = [list(cur_personas[ei]) for ei in range(N)]

        ep_rewards = []  # mean per-episode reward at boundaries

        for t in range(T):
            for ei in range(N):
                obs_buf[t, ei] = cur_obs[ei]
                pid_buf[t, ei] = cur_personas[ei]

            # Build batched forward over (N * n_agents) steps
            obs_flat = np.concatenate(cur_obs, axis=0)  # (N*n_agents, H, W, C) uint8
            e_llm_flat = train_emb[
                torch.tensor(np.concatenate(cur_personas, axis=0), device=device)
            ]
            obs_t = torch.from_numpy(obs_flat).to(device)
            with torch.no_grad():
                a_t, lp_t, v_t = policy.get_action(obs_t, e_llm_flat)
            actions = a_t.cpu().numpy().reshape(N, n_agents)
            lp      = lp_t.cpu().numpy().reshape(N, n_agents)
            vals    = v_t.cpu().numpy().reshape(N, n_agents)

            for ei in range(N):
                next_obs, rew, done = envs[ei].step(actions[ei])
                if args.collective_reward_alpha > 0:
                    rew = rew + args.collective_reward_alpha * float(rew.mean())
                act_buf[t, ei]  = actions[ei]
                lp_buf[t, ei]   = lp[ei]
                val_buf[t, ei]  = vals[ei]
                rew_buf[t, ei]  = rew
                done_buf[t, ei] = done

                for ai in range(n_agents):
                    traj_obs_lists[ei][ai].append(cur_obs[ei][ai].copy())
                    traj_act_lists[ei][ai].append(int(actions[ei][ai]))

                if done:
                    # Episode boundary: log return, reset, resample personas, close traj window
                    ep_rewards.append(float(rew_buf[:t + 1, ei].sum() / n_agents))
                    cur_obs[ei] = envs[ei].reset()
                    cur_personas[ei] = rng.choice(n_train_p, size=n_agents, replace=False).tolist()
                else:
                    cur_obs[ei] = next_obs
            total_env_steps += N * n_agents

        # Bootstrap last value
        obs_flat = np.concatenate(cur_obs, axis=0)
        e_llm_flat = train_emb[
            torch.tensor(np.concatenate(cur_personas, axis=0), device=device)
        ]
        with torch.no_grad():
            _, _, last_v = policy.get_action(
                torch.from_numpy(obs_flat).to(device), e_llm_flat
            )
        last_v = last_v.cpu().numpy().reshape(N, n_agents)

        # GAE per (env, agent)
        adv_buf = np.zeros_like(rew_buf)
        ret_buf = np.zeros_like(rew_buf)
        for ei in range(N):
            done_e = done_buf[:, ei:ei + 1].repeat(n_agents, axis=1)  # (T, n_agents)
            advs, rets = compute_gae(
                rew_buf[:, ei], val_buf[:, ei], done_e, last_v[ei],
                args.gamma, args.gae_lambda,
            )
            adv_buf[:, ei] = advs
            ret_buf[:, ei] = rets

        # Flatten
        flat_obs  = obs_buf.reshape(-1, H, W, C)
        flat_act  = act_buf.reshape(-1)
        flat_lp   = lp_buf.reshape(-1)
        flat_val  = val_buf.reshape(-1)
        flat_adv  = adv_buf.reshape(-1)
        flat_ret  = ret_buf.reshape(-1)
        flat_pid  = pid_buf.reshape(-1)
        N_total   = flat_obs.shape[0]

        # Normalize advantages
        flat_adv = (flat_adv - flat_adv.mean()) / (flat_adv.std() + 1e-8)

        flat_obs_t = torch.from_numpy(flat_obs).to(device)             # uint8
        flat_act_t = torch.from_numpy(flat_act).to(device)
        flat_lp_t  = torch.from_numpy(flat_lp.astype(np.float32)).to(device)
        flat_adv_t = torch.from_numpy(flat_adv.astype(np.float32)).to(device)
        flat_ret_t = torch.from_numpy(flat_ret.astype(np.float32)).to(device)
        flat_pid_t = torch.from_numpy(flat_pid).to(device)

        # Build trajectory list for InfoNCE: one per (env, agent), windowed at min len
        trajectories = []
        for ei in range(N):
            for ai in range(n_agents):
                if len(traj_obs_lists[ei][ai]) >= 2:
                    trajectories.append({
                        "obs_seq":    np.stack(traj_obs_lists[ei][ai]),
                        "act_seq":    np.array(traj_act_lists[ei][ai], dtype=np.int64),
                        "persona_id": pers["train_ids"][traj_persona[ei][ai]],
                        "persona_idx": traj_persona[ei][ai],
                    })

        # ── PPO + co-training updates ─────────────────────────────────────
        mb_size = N_total // args.num_minibatches
        stats = dict(pol=0.0, val=0.0, ent=0.0, con=0.0, div=0.0, kl=0.0); n_mb = 0

        for _ in range(args.update_epochs):
            perm = torch.randperm(N_total, device=device)
            for start in range(0, N_total, mb_size):
                idx = perm[start:start + mb_size]
                b_obs   = flat_obs_t[idx]
                b_act   = flat_act_t[idx]
                b_lp    = flat_lp_t[idx]
                b_adv   = flat_adv_t[idx]
                b_ret   = flat_ret_t[idx]
                b_pid   = flat_pid_t[idx]
                b_e_llm = train_emb[b_pid]

                new_lp, vals, ent = policy.evaluate_actions(b_obs, b_act, b_e_llm)
                ratio = (new_lp - b_lp).exp()
                pol_loss = -torch.min(
                    ratio * b_adv,
                    torch.clamp(ratio, 1 - args.clip, 1 + args.clip) * b_adv,
                ).mean()
                val_loss = F.mse_loss(vals, b_ret)
                entropy  = ent.mean()
                loss = pol_loss + args.vf_coef * val_loss - args.ent_coef * entropy

                optim.zero_grad()
                loss.backward()
                gn = nn.utils.clip_grad_norm_(policy.parameters(), args.max_grad_norm)
                if torch.isfinite(gn):
                    optim.step()
                with torch.no_grad():
                    approx_kl = ((ratio - 1) - (new_lp - b_lp)).mean().item()
                stats["pol"] += float(pol_loss); stats["val"] += float(val_loss)
                stats["ent"] += float(entropy);  stats["kl"]  += approx_kl
                n_mb += 1

            # Co-training once per epoch
            con_loss = torch.tensor(0.0, device=device)
            div_loss = torch.tensor(0.0, device=device)

            if args.lambda_consistency > 0 and len(trajectories) >= 2:
                B = len(trajectories)
                max_T = min(max(len(t["obs_seq"]) for t in trajectories), 200)
                obs_arr = np.zeros((B, max_T, H, W, C), dtype=np.uint8)
                act_arr = np.zeros((B, max_T), dtype=np.int64)
                pidx    = np.zeros(B, dtype=np.int64)
                for k, tr in enumerate(trajectories):
                    Tk = min(len(tr["obs_seq"]), max_T)
                    obs_arr[k, :Tk] = tr["obs_seq"][:Tk]
                    act_arr[k, :Tk] = tr["act_seq"][:Tk]
                    pidx[k] = tr["persona_idx"]
                obs_t_ = torch.from_numpy(obs_arr).to(device)
                act_t_ = torch.from_numpy(act_arr).to(device)
                pidx_t = torch.from_numpy(pidx).to(device)
                feat = policy.features(obs_t_.view(B * max_T, H, W, C)).view(B, max_T, -1)
                traj_emb = traj_encoder(feat, act_t_)                  # (B, 64)
                persona_emb = policy.persona_proj(train_emb[pidx_t])   # (B, 64)
                sim = traj_emb @ persona_emb.T / args.temperature      # (B, B)
                labels = torch.arange(B, device=device)
                con_loss = F.cross_entropy(sim, labels) * args.lambda_consistency

            if args.lambda_diversity > 0:
                n_p = n_train_p
                n_states = min(args.n_div_states, N_total)
                n_sample = min(args.n_div_personas, n_p)
                state_idx = torch.randperm(N_total, device=device)[:n_states]
                p_idx = torch.from_numpy(
                    np.random.choice(n_p, size=n_sample, replace=False)
                ).to(device)
                obs_d = flat_obs_t[state_idx]                          # (S, H, W, C)
                e_d   = train_emb[p_idx]                               # (P, 1024)
                obs_rep = obs_d.unsqueeze(0).expand(n_sample, -1, *([-1] * (obs_d.dim() - 1))).reshape(-1, *obs_d.shape[1:])
                e_rep   = e_d.unsqueeze(1).expand(-1, n_states, -1).reshape(-1, e_d.shape[-1])
                logits  = policy.action_logits(obs_rep, e_rep).view(n_sample, n_states, -1)
                logits  = logits.clamp(-20, 20)
                logp    = F.log_softmax(logits, dim=-1).clamp(min=-10.0)
                probs   = logp.exp()
                total_kl = torch.tensor(0.0, device=device)
                npairs = 0
                for i in range(n_sample):
                    for j in range(i + 1, n_sample):
                        kl = F.kl_div(logp[i], probs[j], reduction="batchmean")
                        if torch.isfinite(kl):
                            total_kl = total_kl + kl.clamp(max=2.0)
                            npairs += 1
                div_loss = -(total_kl / max(1, npairs)) * args.lambda_diversity

            co_loss = con_loss + div_loss
            if co_loss.requires_grad and torch.isfinite(co_loss):
                optim.zero_grad(); optim_traj.zero_grad()
                co_loss.backward()
                gn1 = nn.utils.clip_grad_norm_(policy.parameters(), args.max_grad_norm)
                gn2 = nn.utils.clip_grad_norm_(traj_encoder.parameters(), args.max_grad_norm)
                if torch.isfinite(gn1) and torch.isfinite(gn2):
                    optim.step(); optim_traj.step()
            stats["con"] += float(con_loss); stats["div"] += float(div_loss)

        for k in ("pol", "val", "ent", "kl"): stats[k] /= max(1, n_mb)
        for k in ("con", "div"):                stats[k] /= args.update_epochs

        # ── Eval ───────────────────────────────────────────────────────────
        eval_kl = None; retrieval = None
        if update_idx % args.eval_every == 0 or total_env_steps >= args.total_env_steps:
            eval_kl = eval_pairwise_action_kl(policy, flat_obs_t, train_emb, n_states=64)
            retrieval = eval_retrieval(traj_encoder, policy, trajectories,
                                       train_emb, pers["train_ids"], device)

        mean_ep_rew = float(np.mean(ep_rewards)) if ep_rewards else float("nan")
        mean_step_rew = float(rew_buf.mean())
        elapsed = time.time() - t_start
        log = {
            "update":          update_idx,
            "total_env_steps": total_env_steps,
            "mean_ep_reward":  mean_ep_rew,
            "mean_step_reward": mean_step_rew,
            "n_episodes_done": len(ep_rewards),
            "policy_loss":     stats["pol"],
            "value_loss":      stats["val"],
            "entropy":         stats["ent"],
            "approx_kl":       stats["kl"],
            "consistency":     stats["con"],
            "diversity":       stats["div"],
            "n_trajectories":  len(trajectories),
            "elapsed_sec":     elapsed,
            "sps":             total_env_steps / max(1.0, elapsed),
        }
        if eval_kl is not None:
            log["eval_pairwise_action_kl"] = eval_kl
            log["eval_retrieval_top1"] = retrieval["top1"]
            log["eval_retrieval_top3"] = retrieval["top3"]
            log["eval_retrieval_n"]    = retrieval["n"]

        log_f.write(json.dumps(log) + "\n")
        if update_idx % 1 == 0:
            extra = ""
            if eval_kl is not None:
                extra = f" | eval_kl={eval_kl:.4f} top1={retrieval['top1']:.3f} top3={retrieval['top3']:.3f}"
            print(f"[u{update_idx:4d} step{total_env_steps:>8d}] "
                  f"ep_rew={mean_ep_rew:.2f} sr={mean_step_rew:.4f} "
                  f"pol={stats['pol']:+.3f} "
                  f"val={stats['val']:.3f} ent={stats['ent']:.3f} "
                  f"con={stats['con']:.3f} div={stats['div']:.4f} "
                  f"sps={log['sps']:.0f}{extra}", flush=True)

    # ── Final checkpoint ──────────────────────────────────────────────────
    torch.save(policy.state_dict(),       run_dir / "policy.pt")
    torch.save(traj_encoder.state_dict(), run_dir / "traj_encoder.pt")
    log_f.close()
    for e in envs: e.close()
    print(f"[done] {total_env_steps} steps in {time.time() - t_start:.1f}s -> {run_dir}", flush=True)


if __name__ == "__main__":
    main()
