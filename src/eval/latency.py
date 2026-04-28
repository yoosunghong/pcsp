"""
Inference latency — eval/latency.py

Measures wall-clock time per policy forward pass on GPU.
Compares PCSP (FiLM + LoRA) vs LLM-as-policy (Qwen3-1.7B).

The goal metric is PCSP < 5ms/step vs LLM-as-policy ~500ms/step (>100× speedup).

Usage:
    python src/eval/latency.py \
        --policy results/pcsp/full/policy.pt \
        --model_type pcsp \
        --n_warmup 200 --n_trials 2000 --device cuda
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import N_ACTIONS

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024


def measure_policy_latency(
    policy:    torch.nn.Module,
    context:   dict | None,       # e.g. {"e_llm": tensor} or {"e_embed": tensor} or None
    obs_dim:   int   = OBS_DIM,
    n_warmup:  int   = 200,
    n_trials:  int   = 2000,
    batch:     int   = 1,          # single-step inference (batch=1)
    device:    str   = "cuda",
) -> dict:
    """
    Measure pure forward-pass latency on GPU.

    Warmup: n_warmup iterations (not recorded).
    Measurement: n_trials iterations, median / p95 / p99 reported.
    CUDA synchronisation ensures accurate timing.
    """
    dev = torch.device(device if torch.cuda.is_available() else "cpu")
    policy.to(dev).eval()

    obs_dummy = torch.randn(batch, obs_dim, device=dev)
    ctx_dev   = ({k: v.to(dev) if isinstance(v, torch.Tensor) else v
                  for k, v in context.items()}
                 if context else {})

    def one_step():
        if ctx_dev:
            return policy.get_action(obs_dummy, **ctx_dev)
        else:
            return policy.get_action(obs_dummy)

    # Warmup
    with torch.no_grad():
        for _ in range(n_warmup):
            one_step()
    if dev.type == "cuda":
        torch.cuda.synchronize()

    # Timed trials
    times_ms: list[float] = []
    with torch.no_grad():
        for _ in range(n_trials):
            if dev.type == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            one_step()
            if dev.type == "cuda":
                torch.cuda.synchronize()
            times_ms.append((time.perf_counter() - t0) * 1000.0)

    arr = np.array(times_ms)
    return {
        "mean_ms":   float(arr.mean()),
        "median_ms": float(np.median(arr)),
        "p95_ms":    float(np.percentile(arr, 95)),
        "p99_ms":    float(np.percentile(arr, 99)),
        "std_ms":    float(arr.std()),
        "n_trials":  n_trials,
        "device":    str(dev),
        "batch":     batch,
    }


def measure_llm_policy_latency(
    llm_benchmark_json: str | Path | None = None,
) -> dict:
    """
    Load B5 LLM-as-policy benchmark from pre-computed file,
    or return placeholder if not yet measured.
    """
    if llm_benchmark_json is None:
        llm_benchmark_json = ROOT / "results/baselines/b5_llm/benchmark.json"

    p = Path(llm_benchmark_json)
    if p.exists():
        with open(p) as f:
            data = json.load(f)
        # Normalise to latency format
        ms = data.get("mean_latency_ms") or data.get("latency_ms") or data.get("ms_per_step")
        return {
            "mean_ms":  float(ms) if ms else None,
            "source":   "benchmark.json",
            "note":     "Qwen3-1.7B /no_think mode",
        }
    return {
        "mean_ms": None,
        "source":  "not_measured",
        "note":    "Run scripts/run_baselines.py --baseline b5 to measure",
    }


def latency_comparison(
    pcsp_policy:  torch.nn.Module,
    e_llm:        torch.Tensor,
    no_persona_policy: torch.nn.Module | None = None,
    n_warmup:     int  = 200,
    n_trials:     int  = 2000,
    device:       str  = "cuda",
) -> dict:
    """Compare PCSP vs no-persona MLP vs LLM-as-policy latency."""
    results: dict = {}

    results["pcsp"] = measure_policy_latency(
        pcsp_policy, {"e_llm": e_llm},
        n_warmup=n_warmup, n_trials=n_trials, device=device,
    )

    if no_persona_policy is not None:
        results["no_persona_mlp"] = measure_policy_latency(
            no_persona_policy, None,
            n_warmup=n_warmup, n_trials=n_trials, device=device,
        )

    results["llm_policy"] = measure_llm_policy_latency()

    # Compute speedup ratio
    pcsp_ms = results["pcsp"]["mean_ms"]
    llm_ms  = results["llm_policy"].get("mean_ms")
    results["speedup_vs_llm"] = float(llm_ms / pcsp_ms) if (llm_ms and pcsp_ms) else None

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--policy",      default="results/pcsp/full/policy.pt")
    p.add_argument("--model_type",  choices=["pcsp", "no_persona"], default="pcsp")
    p.add_argument("--embeddings",  default="results/embeddings/persona_embeddings_300.npy")
    p.add_argument("--n_warmup",    type=int, default=200)
    p.add_argument("--n_trials",    type=int, default=2000)
    p.add_argument("--device",      default="cuda")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    context = None
    if args.model_type == "pcsp":
        from src.training.pcsp_trainer import PCSPActorCritic
        policy = PCSPActorCritic(OBS_DIM, N_ACTS)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))
        all_emb = np.load(ROOT / args.embeddings)
        context = {"e_llm": torch.FloatTensor(all_emb[0].astype(np.float32)).unsqueeze(0)}
    else:
        from src.training.baselines.no_persona_ppo import MLPActorCritic
        policy = MLPActorCritic(OBS_DIM, N_ACTS)
        policy.load_state_dict(torch.load(ROOT / args.policy, map_location="cpu"))

    result = measure_policy_latency(
        policy, context,
        n_warmup=args.n_warmup,
        n_trials=args.n_trials,
        device=args.device,
    )
    print(json.dumps(result, indent=2))
