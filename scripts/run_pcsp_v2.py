"""
Phase 7 — PCSP v2 학습 스크립트
Mini-Inzoi v2 (12×12, 16 agents), 500 personas, obs_dim=56

리소스 최적화:
  - n_episodes_per_iter=2 (v1의 8에서 축소; 16 agents × 2 eps = 6400 transitions ≈ v1)
  - n_iterations=200 (v1의 300에서 축소; 총 경험량은 동등)
  - nice -n 19로 실행 권장

Usage:
  # smoke test (20 iter, 특정 mode)
  conda run -n paper python scripts/run_pcsp_v2.py --smoke --mode full

  # 전체 학습 (4 ablation 순차 실행)
  conda run -n paper python scripts/run_pcsp_v2.py --all

  # 단일 mode
  conda run -n paper python scripts/run_pcsp_v2.py --mode full
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.env.mini_inzoi_v2 import MiniInzoiEnvV2, PersonaConfig, N_AGENTS, N_ACTIONS, OBS_DIM
from src.models.film import FiLMBlock, PersonaProjection
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPConfig, PCSPTrainer
import torch.nn as nn

ALL_MODES = ["full", "no_consist", "no_diverse", "concat"]

ROOT      = Path(__file__).resolve().parents[1]
LLM_DIM   = 1024
N_ACTS    = N_ACTIONS   # 12
OBS_DIM_V2 = OBS_DIM   # 56


# ── v2 Actor-Critic (FiLM, obs_dim=56) ────────────────────────────────────────

class PCSPActorCriticV2(nn.Module):
    """FiLM-conditioned actor-critic for v2 environment (obs_dim=56)."""

    def __init__(
        self,
        obs_dim:     int  = OBS_DIM_V2,
        n_actions:   int  = N_ACTS,
        persona_dim: int  = 64,
        llm_dim:     int  = LLM_DIM,
        lora_r:      int  = 16,
        freeze_proj: bool = False,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)

        self.actor_b1   = FiLMBlock(obs_dim, 256, persona_dim)
        self.actor_b2   = FiLMBlock(256,     256, persona_dim)
        self.actor_b3   = FiLMBlock(256,     128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)

        self.critic_b1   = FiLMBlock(obs_dim, 256, persona_dim)
        self.critic_b2   = FiLMBlock(256,     128, persona_dim)
        self.critic_head = nn.Linear(128, 1)

    def _ep(self, e_llm: torch.Tensor) -> torch.Tensor:
        return self.persona_proj(e_llm)

    def action_logits(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        e_p = self._ep(e_llm)
        h = self.actor_b1(obs, e_p)
        h = self.actor_b2(h,   e_p)
        h = self.actor_b3(h,   e_p)
        return self.actor_head(h)

    def get_action(
        self, obs: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p  = self._ep(e_llm)
        h    = self.actor_b3(self.actor_b2(self.actor_b1(obs, e_p), e_p), e_p)
        h2   = self.critic_b2(self.critic_b1(obs, e_p), e_p)
        logits = self.actor_head(h)
        values = self.critic_head(h2).squeeze(-1)
        dist   = torch.distributions.Categorical(logits=logits)
        acts   = dist.sample()
        return acts, dist.log_prob(acts), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        e_p  = self._ep(e_llm)
        h    = self.actor_b3(self.actor_b2(self.actor_b1(obs, e_p), e_p), e_p)
        h2   = self.critic_b2(self.critic_b1(obs, e_p), e_p)
        logits = self.actor_head(h)
        values = self.critic_head(h2).squeeze(-1)
        dist   = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_llm": torch.cat([c["e_llm"] for c in ctxs], dim=0)}


class ConcatActorCriticV2(nn.Module):
    """Concat-conditioning ablation for v2 (obs_dim=56)."""

    def __init__(
        self,
        obs_dim:     int  = OBS_DIM_V2,
        n_actions:   int  = N_ACTS,
        persona_dim: int  = 64,
        llm_dim:     int  = LLM_DIM,
        lora_r:      int  = 16,
        freeze_proj: bool = False,
    ):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)

        inp = obs_dim + persona_dim
        self.input_norm = nn.LayerNorm(inp)
        self.actor = nn.Sequential(
            nn.Linear(inp, 256), nn.ReLU(),
            nn.Linear(256, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, n_actions),
        )
        self.critic = nn.Sequential(
            nn.Linear(inp, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 1),
        )

    def _feats(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        return self.input_norm(torch.cat([obs, self.persona_proj(e_llm)], dim=-1))

    def action_logits(self, obs: torch.Tensor, e_llm: torch.Tensor) -> torch.Tensor:
        return self.actor(self._feats(obs, e_llm))

    def get_action(
        self, obs: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x      = self._feats(obs, e_llm)
        logits = self.actor(x)
        values = self.critic(x).squeeze(-1)
        dist   = torch.distributions.Categorical(logits=logits)
        acts   = dist.sample()
        return acts, dist.log_prob(acts), values

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor, e_llm: torch.Tensor, **_
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        x      = self._feats(obs, e_llm)
        logits = self.actor(x)
        values = self.critic(x).squeeze(-1)
        dist   = torch.distributions.Categorical(logits=logits)
        return dist.log_prob(actions), values, dist.entropy()

    @staticmethod
    def stack_contexts(ctxs: list[dict]) -> dict:
        return {"e_llm": torch.cat([c["e_llm"] for c in ctxs], dim=0)}


# ── Training entry ─────────────────────────────────────────────────────────────

def train_pcsp_v2(
    mode:         str,
    device:       str       = "cuda",
    n_iterations: int | None = None,
    smoke:        bool       = False,
) -> dict:
    personas_json = ROOT / "data"    / "personas" / "train_400.json"
    embed_npy     = ROOT / "results" / "embeddings" / "persona_embeddings_500.npy"
    output_dir    = ROOT / "results" / "v2" / "pcsp" / mode
    output_dir.mkdir(parents=True, exist_ok=True)

    if not personas_json.exists():
        raise FileNotFoundError(f"Personas not found: {personas_json}\nRun generate_personas_500.py first.")
    if not embed_npy.exists():
        raise FileNotFoundError(f"Embeddings not found: {embed_npy}\nRun compute_embeddings_500.py first.")

    with open(personas_json) as f:
        personas_data = json.load(f)

    all_emb_500  = np.load(embed_npy)                              # (500, 1024) float16
    train_idxs   = [p["id"] - 1 for p in personas_data]           # IDs are 1-based
    train_emb    = all_emb_500[train_idxs].astype(np.float32)      # (400, 1024)
    embed_tensors = [torch.FloatTensor(train_emb[i]).unsqueeze(0)
                     for i in range(len(personas_data))]

    # Config — resource-friendly for concurrent GPU usage
    cfg = PCSPConfig(
        total_iterations     = 200,
        n_episodes_per_iter  = 2,   # 2 eps × 16 agents × 200 rounds ≈ v1's 8 × 4 × 200
        batch_size           = 256,
        n_epochs             = 4,
        lambda_consistency   = 0.5,
        lambda_diversity     = 0.1,
        n_diversity_states   = 16,  # reduce from 32 to save compute
        n_diversity_personas = 8,
    )

    if smoke:
        cfg.total_iterations    = 20
        cfg.n_episodes_per_iter = 1

    if n_iterations is not None:
        cfg.total_iterations = n_iterations

    # Apply ablation
    if mode == "no_consist":
        cfg.lambda_consistency = 0.0
    elif mode == "no_diverse":
        cfg.lambda_diversity = 0.0
    elif mode == "concat":
        cfg.use_film = False

    rng = np.random.default_rng(cfg.seed)

    def persona_sampler():
        idxs     = rng.choice(len(personas_data), size=N_AGENTS, replace=False)
        personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
        agent_ctxs = {
            f"agent_{j}": {"e_llm": embed_tensors[idxs[j]]}
            for j in range(N_AGENTS)
        }
        return personas, agent_ctxs

    def make_env_fn(personas):
        return MiniInzoiEnvV2(personas=personas, max_steps=200)

    # Build policy
    if mode == "concat":
        policy = ConcatActorCriticV2(obs_dim=OBS_DIM_V2, n_actions=N_ACTS,
                                     persona_dim=cfg.traj_output_dim, llm_dim=LLM_DIM)
    else:
        policy = PCSPActorCriticV2(obs_dim=OBS_DIM_V2, n_actions=N_ACTS,
                                   persona_dim=cfg.traj_output_dim, llm_dim=LLM_DIM)

    traj_encoder = TrajectoryEncoder(
        obs_dim    = OBS_DIM_V2,
        n_actions  = N_ACTS,
        hidden_dim = cfg.traj_hidden_dim,
        output_dim = cfg.traj_output_dim,
    )

    trainer = PCSPTrainer(policy, traj_encoder, cfg, device)

    n_params      = sum(p.numel() for p in policy.parameters())
    n_traj_params = sum(p.numel() for p in traj_encoder.parameters())
    print(
        f"\n[PCSPv2:{mode}] policy={n_params:,}  traj_enc={n_traj_params:,}  "
        f"obs_dim={OBS_DIM_V2}  n_agents={N_AGENTS}  "
        f"λ₁={cfg.lambda_consistency}  λ₂={cfg.lambda_diversity}  device={trainer.device}"
    )

    t0      = time.time()
    metrics = trainer.train(
        make_env_fn, persona_sampler, train_emb,
        n_iterations = cfg.total_iterations,
    )
    elapsed = time.time() - t0
    print(f"[PCSPv2:{mode}] done in {elapsed:.1f}s")

    torch.save(policy.state_dict(),       output_dir / "policy.pt")
    torch.save(traj_encoder.state_dict(), output_dir / "traj_encoder.pt")
    with open(output_dir / "metrics.json", "w") as f:
        json.dump({"mode": mode, "metrics": metrics, "elapsed_sec": elapsed}, f, indent=2)

    final = metrics[-1] if metrics else {}
    print(f"[PCSPv2:{mode}] final reward={final.get('mean_ep_reward', 'N/A'):.3f}")
    return final


def main():
    parser = argparse.ArgumentParser(description="PCSP v2 training (12×12, 16 agents, 500 personas)")
    parser.add_argument("--mode",  choices=ALL_MODES, default="full")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--all",   action="store_true")
    parser.add_argument("--n_iterations", type=int, default=None)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    modes = ALL_MODES if args.all else [args.mode]
    summary = {}
    t_total = time.time()

    for mode in modes:
        print(f"\n{'='*60}")
        print(f"  PCSPv2 mode={mode}  {'(SMOKE)' if args.smoke else ''}")
        print(f"{'='*60}")
        result = train_pcsp_v2(
            mode         = mode,
            device       = args.device,
            n_iterations = args.n_iterations,
            smoke        = args.smoke,
        )
        summary[mode] = result

    elapsed = time.time() - t_total

    print(f"\n{'='*60}")
    print("  PCSPv2 Summary")
    print(f"{'='*60}")
    for mode, res in summary.items():
        rew = res.get("mean_ep_reward", float("nan"))
        con = res.get("consistency_loss", float("nan"))
        div = res.get("diversity_loss",   float("nan"))
        print(f"  {mode:<14} reward={rew:7.3f}  con={con:.4f}  div={div:.4f}")
    print(f"\n  Total elapsed: {elapsed:.1f}s")

    out = ROOT / "results" / "v2" / "pcsp" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"modes": summary, "elapsed_sec": elapsed}, f, indent=2)
    print(f"  Summary saved: {out}")


if __name__ == "__main__":
    main()
