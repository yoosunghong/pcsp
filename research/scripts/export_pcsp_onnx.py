"""
Export the trained PCSP v3 actor head to ONNX and persona projections to JSON.

Standalone — does NOT import from src.env (which lives only on the training PC).
Only requires: torch, numpy, and src/models/film.py.

What is exported
----------------
1. pcsp_actor.onnx
   Inputs:
     obs          float32 (1, 33)  — v3 base observation (4-agent training format)
     persona_proj float32 (1, 64)  — pre-projected persona embedding
   Output:
     logits       float32 (1, 20)  — raw action logits (argmax in UE)

2. persona_embeddings.json
   Pre-projected 64-dim vectors for all 300 personas, indexed by persona_id (1-based).
   {"n_personas":300, "persona_dim":64, "obs_dim":33, "n_actions":20,
    "embeddings":[[...64 floats...], ...]}

Usage
-----
    # Copy from training PC first:
    #   results/pcsp_v3/full/policy.pt
    #   results/embeddings/persona_embeddings_300.npy

    conda run -n paper python scripts/export_pcsp_onnx.py

    # Then copy outputs to UE5:
    #   results/export_ue5/pcsp_actor.onnx          -> ue/cnzoi/Content/PCSP/Models/
    #   results/export_ue5/persona_embeddings.json   -> ue/cnzoi/Content/PCSP/Data/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.film import FiLMBlock, PersonaProjection  # only src.models needed

# ---------------------------------------------------------------------------
# Model constants — must match the training run
# ---------------------------------------------------------------------------

OBS_DIM     = 33    # v3 base (4 agents)
N_ACTIONS   = 20
PERSONA_DIM = 64
LLM_DIM     = 1024
LORA_R      = 16


# ---------------------------------------------------------------------------
# Minimal PCSPActorCritic (actor head only — inlined to avoid src.env import)
# ---------------------------------------------------------------------------

class PCSPActorCritic(nn.Module):
    """Mirrors pcsp_trainer.PCSPActorCritic exactly — kept in sync manually."""

    def __init__(self, obs_dim=OBS_DIM, n_actions=N_ACTIONS,
                 persona_dim=PERSONA_DIM, llm_dim=LLM_DIM, lora_r=LORA_R,
                 freeze_proj=False):
        super().__init__()
        self.persona_proj = PersonaProjection(llm_dim, persona_dim, lora_r)
        if freeze_proj:
            for p in self.persona_proj.parameters():
                p.requires_grad_(False)
        self.actor_b1   = FiLMBlock(obs_dim,  256, persona_dim)
        self.actor_b2   = FiLMBlock(256,       256, persona_dim)
        self.actor_b3   = FiLMBlock(256,       128, persona_dim)
        self.actor_head = nn.Linear(128, n_actions)
        self.critic_b1   = FiLMBlock(obs_dim,  256, persona_dim)
        self.critic_b2   = FiLMBlock(256,       128, persona_dim)
        self.critic_head = nn.Linear(128, 1)


# ---------------------------------------------------------------------------
# Actor-only ONNX wrapper: (obs, persona_proj) -> logits, no LLM inside
# ---------------------------------------------------------------------------

class ActorHead(nn.Module):
    def __init__(self, policy: PCSPActorCritic):
        super().__init__()
        self.b1   = policy.actor_b1
        self.b2   = policy.actor_b2
        self.b3   = policy.actor_b3
        self.head = policy.actor_head

    def forward(self, obs: torch.Tensor, persona_proj: torch.Tensor) -> torch.Tensor:
        h = self.b1(obs, persona_proj)
        h = self.b2(h,   persona_proj)
        h = self.b3(h,   persona_proj)
        return self.head(h)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_actor(policy: PCSPActorCritic, out_path: Path) -> None:
    actor = ActorHead(policy).eval()
    dummy_obs     = torch.zeros(1, OBS_DIM)
    dummy_persona = torch.zeros(1, PERSONA_DIM)

    torch.onnx.export(
        actor,
        (dummy_obs, dummy_persona),
        str(out_path),
        input_names=["obs", "persona_proj"],
        output_names=["logits"],
        dynamic_axes={
            "obs":          {0: "batch"},
            "persona_proj": {0: "batch"},
            "logits":       {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    print(f"[export] actor ONNX  -> {out_path}")
    print(f"         inputs : obs(1,{OBS_DIM})  persona_proj(1,{PERSONA_DIM})")
    print(f"         output : logits(1,{N_ACTIONS})")


def export_persona_embeddings(policy: PCSPActorCritic,
                              emb_npy: Path, out_path: Path) -> None:
    all_emb = np.load(emb_npy).astype(np.float32)   # (300, 1024)
    assert all_emb.shape[1] == LLM_DIM, \
        f"Expected embedding dim {LLM_DIM}, got {all_emb.shape[1]}"

    with torch.no_grad():
        projected = policy.persona_proj(
            torch.FloatTensor(all_emb)
        ).cpu().numpy()    # (300, 64) L2-normalised

    data = {
        "n_personas":  int(projected.shape[0]),
        "persona_dim": int(projected.shape[1]),
        "obs_dim":     OBS_DIM,
        "n_actions":   N_ACTIONS,
        "embeddings":  projected.tolist(),
    }
    with open(out_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"[export] persona embeddings -> {out_path}  ({size_kb:.1f} KB, {projected.shape})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint",  default="results/pcsp_v3/full/policy.pt")
    parser.add_argument("--embeddings",  default="results/embeddings/persona_embeddings_300.npy")
    parser.add_argument("--output_dir",  default="results/export_ue5")
    parser.add_argument("--device",      default="cpu")
    args = parser.parse_args()

    ckpt_path = ROOT / args.checkpoint
    emb_path  = ROOT / args.embeddings
    out_dir   = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not ckpt_path.exists():
        print(f"\n[ERROR] Checkpoint not found:\n  {ckpt_path}")
        print("Copy it from the training PC:  results/pcsp_v3/full/policy.pt")
        sys.exit(1)

    if not emb_path.exists():
        print(f"\n[ERROR] Embeddings not found:\n  {emb_path}")
        print("Copy it from the training PC:  results/embeddings/persona_embeddings_300.npy")
        sys.exit(1)

    print(f"[load] {ckpt_path}")
    policy = PCSPActorCritic()
    state  = torch.load(ckpt_path, map_location=args.device, weights_only=True)
    policy.load_state_dict(state)
    policy.eval()

    export_actor(policy, out_dir / "pcsp_actor.onnx")
    export_persona_embeddings(policy, emb_path, out_dir / "persona_embeddings.json")

    print()
    print("Next: copy to UE5 project")
    print(f"  {out_dir}/pcsp_actor.onnx         -> ue/cnzoi/Content/PCSP/Models/")
    print(f"  {out_dir}/persona_embeddings.json  -> ue/cnzoi/Content/PCSP/Data/")


if __name__ == "__main__":
    main()
