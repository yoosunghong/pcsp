"""
Phase 7 — PCSP v2 평가 스크립트
Mini-Inzoi v2 (12×12, 16 agents, 500 personas)

기존 eval 모듈의 metric 함수들을 재사용하되,
환경 생성 부분만 v2로 교체.

Usage:
  # 전체 평가
  conda run -n paper python scripts/run_eval_v2.py

  # smoke test (빠른 확인)
  conda run -n paper python scripts/run_eval_v2.py --smoke

  # 특정 model만
  conda run -n paper python scripts/run_eval_v2.py --models full no_consist
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi_v2 import (
    MiniInzoiEnvV2, PersonaConfig, _default_16_personas,
    N_AGENTS, N_ACTIONS, OBS_DIM,
)
from src.models.trajectory_encoder import TrajectoryEncoder
from src.eval.latency import measure_policy_latency
from scripts.run_pcsp_v2 import PCSPActorCriticV2, ConcatActorCriticV2

LLM_DIM    = 1024
N_ACTS     = N_ACTIONS   # 12
OBS_DIM_V2 = OBS_DIM     # 56

MODELS_DIR = ROOT / "results" / "v2" / "pcsp"
EVAL_DIR   = ROOT / "results" / "v2" / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

ALL_MODES = ["full", "no_consist", "no_diverse", "concat"]


# ── v2-specific env helpers ────────────────────────────────────────────────────

def _rollout_persona_v2(
    policy:      torch.nn.Module,
    e_llm:       torch.Tensor,
    persona_cfg: PersonaConfig,
    n_episodes:  int,
    device:      torch.device,
    seed_offset: int = 0,
) -> list[dict]:
    """Collect n_episodes trajectories for one persona (v2: 16 agents, same persona)."""
    trajs = []
    for ep in range(n_episodes):
        env = MiniInzoiEnvV2(personas=[persona_cfg] * N_AGENTS, max_steps=100)
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


def _encode_trajectories_v2(
    traj_encoder: TrajectoryEncoder,
    trajs:        list[dict],
    device:       torch.device,
    max_T:        int = 200,
) -> torch.Tensor:
    """Encode a list of trajectories → (N, traj_output_dim)."""
    obs_dim  = trajs[0]["obs_seq"].shape[-1]
    B        = len(trajs)
    T        = min(max(len(t["obs_seq"]) for t in trajs), max_T)

    obs_b = np.zeros((B, T, obs_dim),  dtype=np.float32)
    act_b = np.zeros((B, T),            dtype=np.int64)
    for k, t in enumerate(trajs):
        tlen = min(len(t["obs_seq"]), T)
        obs_b[k, :tlen] = t["obs_seq"][:tlen]
        act_b[k, :tlen] = t["act_seq"][:tlen]

    with torch.no_grad():
        embs = traj_encoder(
            torch.FloatTensor(obs_b).to(device),
            torch.LongTensor(act_b).to(device),
        )
    return F.normalize(embs, dim=-1).cpu()


def _sample_states_v2(n_states: int, seed: int = 0) -> np.ndarray:
    """Sample random observations from v2 env (for diversity eval)."""
    rng      = np.random.default_rng(seed)
    obs_list: list[np.ndarray] = []
    step = 0
    while step < n_states:
        env = MiniInzoiEnvV2(personas=_default_16_personas(), max_steps=100)
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
    return np.stack(obs_list[:n_states]).astype(np.float32)


# ── Metric functions ───────────────────────────────────────────────────────────

def eval_reward(
    policy:       torch.nn.Module,
    personas_data: list[dict],
    embed_tensors: list[torch.Tensor],
    device:       torch.device,
    n_episodes:   int = 10,
    seed:         int = 42,
) -> dict:
    rng      = np.random.default_rng(seed)
    ep_rews: list[float] = []

    for ep in range(n_episodes):
        idxs     = rng.choice(len(personas_data), size=N_AGENTS, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        e_llms   = [embed_tensors[idxs[j]].to(device) for j in range(N_AGENTS)]

        env = MiniInzoiEnvV2(personas=personas, max_steps=200)
        env.reset(seed=seed + ep * 37)
        agent_rews = {a: 0.0 for a in env.possible_agents}

        for agent in env.agent_iter():
            obs, rew, term, trunc, _ = env.last()
            agent_rews[agent] += rew
            if term or trunc:
                env.step(None)
                continue
            i   = env.agent_name_mapping[agent]
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(device)
            with torch.no_grad():
                act, _, _ = policy.get_action(obs_t, e_llm=e_llms[i])
            env.step(act.item())
        env.close()
        ep_rews.append(float(np.mean(list(agent_rews.values()))))

    return {
        "mean": float(np.mean(ep_rews)),
        "std":  float(np.std(ep_rews)),
    }


def eval_consistency(
    policy:        torch.nn.Module,
    traj_encoder:  TrajectoryEncoder,
    personas_data: list[dict],
    all_emb:       np.ndarray,
    device:        torch.device,
    n_personas:    int = 30,
    n_episodes:    int = 3,
    seed:          int = 0,
) -> dict:
    rng      = np.random.default_rng(seed)
    idxs     = rng.choice(len(personas_data), size=n_personas, replace=False)
    selected = [personas_data[i] for i in idxs]

    e_llm_all = torch.FloatTensor(
        np.stack([all_emb[p["id"] - 1].astype(np.float32) for p in selected])
    ).to(device)
    with torch.no_grad():
        p_embs = policy.persona_proj(e_llm_all).cpu()   # (n_personas, 64)

    all_traj_embs: list[torch.Tensor] = []
    all_labels:    list[int]          = []

    for p_idx, persona_dict in enumerate(selected):
        e_llm = torch.FloatTensor(
            all_emb[persona_dict["id"] - 1].astype(np.float32)
        ).unsqueeze(0).to(device)
        pcfg  = PersonaConfig.from_dict(persona_dict)

        trajs = _rollout_persona_v2(
            policy, e_llm, pcfg, n_episodes, device,
            seed_offset=seed + p_idx * 997,
        )
        if not trajs:
            continue
        t_embs = _encode_trajectories_v2(traj_encoder, trajs, device)
        all_traj_embs.append(t_embs)
        all_labels.extend([p_idx] * len(trajs))

    if not all_traj_embs:
        return {"accuracy": 0.0, "coherence_ratio": 0.0}

    traj_mat   = torch.cat(all_traj_embs, dim=0)   # (total, 64)
    labels_arr = np.array(all_labels)

    sim_mat     = traj_mat @ p_embs.T
    pred_labels = sim_mat.argmax(dim=1).numpy()
    accuracy    = float((pred_labels == labels_arr).mean())

    n_total     = traj_mat.shape[0]
    intra, inter = [], []
    for i in range(n_total):
        for j in range(i + 1, n_total):
            cos = float((traj_mat[i] * traj_mat[j]).sum())
            (intra if labels_arr[i] == labels_arr[j] else inter).append(cos)

    intra_mean = float(np.mean(intra)) if intra else 0.0
    inter_mean = float(np.mean(inter)) if inter else 0.0
    coherence  = intra_mean / (inter_mean + 1e-8)

    return {"accuracy": accuracy, "coherence_ratio": coherence}


def eval_zeroshot(
    policy:       torch.nn.Module,
    traj_encoder: TrajectoryEncoder,
    test_data:    list[dict],
    all_emb:      np.ndarray,
    device:       torch.device,
    n_episodes:   int = 3,
    seed:         int = 1000,
) -> dict:
    e_llm_test = torch.FloatTensor(
        np.stack([all_emb[p["id"] - 1].astype(np.float32) for p in test_data])
    ).to(device)
    with torch.no_grad():
        p_embs = policy.persona_proj(e_llm_test).cpu()

    all_traj_embs: list[torch.Tensor] = []
    all_labels:    list[int]          = []

    for p_idx, persona_dict in enumerate(test_data):
        e_llm = torch.FloatTensor(
            all_emb[persona_dict["id"] - 1].astype(np.float32)
        ).unsqueeze(0).to(device)
        pcfg  = PersonaConfig.from_dict(persona_dict)

        trajs = _rollout_persona_v2(
            policy, e_llm, pcfg, n_episodes, device,
            seed_offset=seed + p_idx * 997,
        )
        if not trajs:
            continue
        t_embs = _encode_trajectories_v2(traj_encoder, trajs, device)
        all_traj_embs.append(t_embs)
        all_labels.extend([p_idx] * len(trajs))

    if not all_traj_embs:
        return {"accuracy": 0.0, "coherence_ratio": 0.0}

    traj_mat   = torch.cat(all_traj_embs, dim=0)
    labels_arr = np.array(all_labels)
    sim_mat     = traj_mat @ p_embs.T
    pred_labels = sim_mat.argmax(dim=1).numpy()
    accuracy    = float((pred_labels == labels_arr).mean())

    n_total     = traj_mat.shape[0]
    intra, inter = [], []
    for i in range(n_total):
        for j in range(i + 1, n_total):
            cos = float((traj_mat[i] * traj_mat[j]).sum())
            (intra if labels_arr[i] == labels_arr[j] else inter).append(cos)

    intra_mean = float(np.mean(intra)) if intra else 0.0
    inter_mean = float(np.mean(inter)) if inter else 0.0
    coherence  = intra_mean / (inter_mean + 1e-8)

    return {"accuracy": accuracy, "coherence_ratio": coherence}


def eval_diversity_v2(
    policy:       torch.nn.Module,
    all_emb:      np.ndarray,
    personas_data: list[dict],
    device:       torch.device,
    n_states:     int = 100,
    n_pairs:      int = 60,
    seed:         int = 0,
) -> dict:
    from scipy.stats import spearmanr

    states_np = _sample_states_v2(n_states, seed=seed)
    states    = torch.FloatTensor(states_np).to(device)

    N   = len(personas_data)
    rng = np.random.default_rng(seed)
    pairs: list[tuple[int, int]] = []
    while len(pairs) < min(n_pairs, N * (N - 1) // 2):
        i, j = rng.choice(N, size=2, replace=False)
        if (int(i), int(j)) not in pairs and (int(j), int(i)) not in pairs:
            pairs.append((int(i), int(j)))

    kl_vals, dist_vals = [], []
    for (i, j) in pairs:
        e_i = torch.FloatTensor(all_emb[personas_data[i]["id"] - 1].astype(np.float32)
                                ).unsqueeze(0).to(device)
        e_j = torch.FloatTensor(all_emb[personas_data[j]["id"] - 1].astype(np.float32)
                                ).unsqueeze(0).to(device)
        with torch.no_grad():
            li = policy.action_logits(states, e_i.expand(n_states, -1))
            lj = policy.action_logits(states, e_j.expand(n_states, -1))
        lp_i, lp_j = F.log_softmax(li, dim=-1), F.log_softmax(lj, dim=-1)
        sym_kl = (F.kl_div(lp_j, lp_i.exp(), reduction="batchmean").item() +
                  F.kl_div(lp_i, lp_j.exp(), reduction="batchmean").item()) / 2.0
        with torch.no_grad():
            pe_i = policy.persona_proj(e_i)
            pe_j = policy.persona_proj(e_j)
        l2 = float(torch.norm(pe_i - pe_j, dim=-1).item())
        kl_vals.append(sym_kl)
        dist_vals.append(l2)

    kl_arr   = np.array(kl_vals)
    dist_arr = np.array(dist_vals)
    rho, _   = spearmanr(kl_arr, dist_arr)

    return {
        "mean_kl":      float(kl_arr.mean()),
        "spearman_rho": float(rho),
    }


def eval_latency_v2(policy: torch.nn.Module, device: str = "cuda") -> dict:
    ctx = {"e_llm": torch.randn(1, LLM_DIM, device=device)}
    return measure_policy_latency(
        policy, ctx, obs_dim=OBS_DIM_V2,
        n_warmup=100, n_trials=1000, device=device,
    )


# ── Model loader ───────────────────────────────────────────────────────────────

def _load_model(mode: str, device: str) -> tuple[torch.nn.Module, TrajectoryEncoder] | None:
    policy_path  = MODELS_DIR / mode / "policy.pt"
    traj_path    = MODELS_DIR / mode / "traj_encoder.pt"

    if not policy_path.exists():
        print(f"  [SKIP] {mode}: model not found at {policy_path}")
        return None

    if mode == "concat":
        policy = ConcatActorCriticV2(obs_dim=OBS_DIM_V2, n_actions=N_ACTS,
                                     persona_dim=64, llm_dim=LLM_DIM)
    else:
        policy = PCSPActorCriticV2(obs_dim=OBS_DIM_V2, n_actions=N_ACTS,
                                   persona_dim=64, llm_dim=LLM_DIM)

    policy.load_state_dict(torch.load(policy_path, map_location="cpu"))
    policy.to(device).eval()

    traj_enc = TrajectoryEncoder(obs_dim=OBS_DIM_V2, n_actions=N_ACTS,
                                 hidden_dim=128, output_dim=64)
    traj_enc.load_state_dict(torch.load(traj_path, map_location="cpu"))
    traj_enc.to(device).eval()

    return policy, traj_enc


# ── LaTeX table generation ─────────────────────────────────────────────────────

def _to_latex(results: dict) -> str:
    header = (
        r"\begin{table}[t]" + "\n"
        r"\centering" + "\n"
        r"\caption{PCSP v2 results (12$\times$12, 16 agents, 500 personas)}" + "\n"
        r"\label{tab:pcsp_v2}" + "\n"
        r"\begin{tabular}{lrrrrr}" + "\n"
        r"\toprule" + "\n"
        r"Model & Reward & Consist & ZeroShot & KL & $\rho$ \\" + "\n"
        r"\midrule" + "\n"
    )
    rows = []
    for mode, res in results.items():
        rew = res.get("reward_mean", float("nan"))
        con = res.get("consist_acc", float("nan"))
        zs  = res.get("zeroshot_acc", float("nan"))
        kl  = res.get("mean_kl", float("nan"))
        rho = res.get("spearman_rho", float("nan"))
        bold = r"\textbf{" + mode + "}" if mode == "full" else mode
        rows.append(
            f"{bold} & {rew:.1f} & {con:.3f} & {zs:.3f} & {kl:.2f} & {rho:.3f} \\\\"
        )
    footer = (
        r"\bottomrule" + "\n"
        r"\end{tabular}" + "\n"
        r"\end{table}"
    )
    return header + "\n".join(rows) + "\n" + footer


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate PCSP v2 models")
    parser.add_argument("--models", nargs="+", default=ALL_MODES)
    parser.add_argument("--smoke",  action="store_true")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    train_path = ROOT / "data" / "personas" / "train_400.json"
    test_path  = ROOT / "data" / "personas" / "test_100.json"
    emb_path   = ROOT / "results" / "embeddings" / "persona_embeddings_500.npy"

    for p in [train_path, test_path, emb_path]:
        if not p.exists():
            print(f"ERROR: {p} not found. Run prerequisite scripts first.")
            return

    with open(train_path) as f:
        train_data = json.load(f)
    with open(test_path) as f:
        test_data  = json.load(f)

    all_emb       = np.load(emb_path)                           # (500, 1024) float16
    dev           = torch.device(args.device if torch.cuda.is_available() else "cpu")
    embed_tensors = [
        torch.FloatTensor(all_emb[p["id"] - 1].astype(np.float32)).unsqueeze(0)
        for p in train_data
    ]

    # Scale for smoke test
    n_ep_reward   = 3 if args.smoke else 10
    n_ep_consist  = 2 if args.smoke else 3
    n_personas_c  = 10 if args.smoke else 30
    n_ep_zs       = 2 if args.smoke else 3
    n_personas_zs = 10 if args.smoke else len(test_data)
    n_states_div  = 50 if args.smoke else 100
    n_pairs_div   = 20 if args.smoke else 60

    results = {}

    for mode in args.models:
        print(f"\n{'='*55}")
        print(f"  Evaluating: {mode}")
        print(f"{'='*55}")

        loaded = _load_model(mode, args.device)
        if loaded is None:
            continue
        policy, traj_enc = loaded

        res = {}
        t0  = time.time()

        print("  reward ...", flush=True)
        rew = eval_reward(policy, train_data, embed_tensors, dev,
                          n_episodes=n_ep_reward)
        res["reward_mean"] = rew["mean"]
        res["reward_std"]  = rew["std"]

        print("  consistency ...", flush=True)
        con = eval_consistency(policy, traj_enc, train_data, all_emb, dev,
                               n_personas=n_personas_c, n_episodes=n_ep_consist)
        res["consist_acc"]   = con["accuracy"]
        res["coherence"]     = con["coherence_ratio"]

        print("  zero-shot ...", flush=True)
        zs  = eval_zeroshot(policy, traj_enc,
                             test_data[:n_personas_zs], all_emb, dev,
                             n_episodes=n_ep_zs)
        res["zeroshot_acc"]     = zs["accuracy"]
        res["zeroshot_coherence"] = zs["coherence_ratio"]

        print("  diversity ...", flush=True)
        div = eval_diversity_v2(policy, all_emb, train_data, dev,
                                n_states=n_states_div, n_pairs=n_pairs_div)
        res["mean_kl"]      = div["mean_kl"]
        res["spearman_rho"] = div["spearman_rho"]

        print("  latency ...", flush=True)
        lat = eval_latency_v2(policy, args.device)
        res["latency_ms_median"] = lat.get("median_ms", float("nan"))

        res["eval_time_sec"] = time.time() - t0
        results[mode] = res

        print(f"  reward={res['reward_mean']:.2f}  consist={res['consist_acc']:.3f}  "
              f"zs={res['zeroshot_acc']:.3f}  KL={res['mean_kl']:.2f}  "
              f"ρ={res['spearman_rho']:.3f}  lat={res['latency_ms_median']:.2f}ms")

    # Save JSON
    out_json = EVAL_DIR / "comparison_v2.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {out_json}")

    # Save LaTeX
    out_tex = EVAL_DIR / "comparison_v2.tex"
    out_tex.write_text(_to_latex(results))
    print(f"LaTeX table: {out_tex}")

    # Print summary table
    print(f"\n{'Model':<14} {'Reward':>8} {'Consist':>8} {'ZeroShot':>9} {'KL':>6} {'ρ':>6} {'Lat':>7}")
    print("-" * 65)
    for mode, res in results.items():
        print(
            f"{mode:<14} {res.get('reward_mean', float('nan')):8.2f} "
            f"{res.get('consist_acc', float('nan')):8.3f} "
            f"{res.get('zeroshot_acc', float('nan')):9.3f} "
            f"{res.get('mean_kl', float('nan')):6.2f} "
            f"{res.get('spearman_rho', float('nan')):6.3f} "
            f"{res.get('latency_ms_median', float('nan')):6.2f}ms"
        )


if __name__ == "__main__":
    main()
