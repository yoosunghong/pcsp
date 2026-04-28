"""
Unified evaluation script — scripts/run_eval.py

Runs all Phase 5 metrics for PCSP (full + ablations) and all baselines,
then generates a comparison table (JSON + LaTeX).

Metrics computed:
  - Task reward        (mean episode reward, 100 episodes)
  - Persona accuracy   (k-NN classification, train personas)
  - Zero-shot acc      (k-NN classification, test_60 personas)  ★
  - Behavioral KL      (mean pairwise KL + Spearman ρ)
  - Inference latency  (ms/step on GPU)
  - Sample efficiency  (AUC from training logs)

Usage:
    # Full eval (all models, all metrics) — takes ~30 min on RTX 6000 Ada
    conda run -n paper python scripts/run_eval.py

    # Quick smoke test (fewer episodes/pairs)
    conda run -n paper python scripts/run_eval.py --smoke

    # Select specific models and metrics
    conda run -n paper python scripts/run_eval.py \\
        --models pcsp_full b1 b3 \\
        --metrics reward zeroshot latency

    # Skip slow zero-shot (only latency + reward)
    conda run -n paper python scripts/run_eval.py --skip_zeroshot
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import N_ACTIONS, PersonaConfig
from src.models.trajectory_encoder import TrajectoryEncoder
from src.training.pcsp_trainer import PCSPActorCritic, ConcatActorCritic
from src.training.baselines.no_persona_ppo import MLPActorCritic
from src.eval.consistency import persona_classification_accuracy
from src.eval.diversity import behavioral_kl_diversity
from src.eval.task_perf import (
    evaluate_task_reward,
    make_pcsp_sampler,
    make_no_persona_sampler,
    make_sbert_sampler,
    make_diayn_sampler,
)
from src.eval.efficiency import compare_efficiency
from src.eval.zeroshot import zero_shot_consistency
from src.eval.latency import measure_policy_latency, measure_llm_policy_latency

OBS_DIM = 20
N_ACTS  = N_ACTIONS  # 12
LLM_DIM = 1024


# ── Model loaders ─────────────────────────────────────────────────────────────

def _load_pcsp(mode: str, device: torch.device) -> tuple[torch.nn.Module, TrajectoryEncoder]:
    use_film = mode != "concat"
    Cls = PCSPActorCritic if use_film else ConcatActorCritic
    policy = Cls(OBS_DIM, N_ACTS)
    policy.load_state_dict(
        torch.load(ROOT / f"results/pcsp/{mode}/policy.pt", map_location="cpu")
    )
    traj_enc = TrajectoryEncoder(OBS_DIM, N_ACTS)
    traj_enc.load_state_dict(
        torch.load(ROOT / f"results/pcsp/{mode}/traj_encoder.pt", map_location="cpu")
    )
    return policy.to(device).eval(), traj_enc.to(device).eval()


def _load_b1(device: torch.device) -> torch.nn.Module:
    policy = MLPActorCritic(OBS_DIM, N_ACTS)
    policy.load_state_dict(
        torch.load(ROOT / "results/baselines/b1_no_persona/policy.pt", map_location="cpu")
    )
    return policy.to(device).eval()


def _load_b3(device: torch.device) -> torch.nn.Module:
    from src.training.baselines.sbert_policy import SBERTActorCritic
    policy = SBERTActorCritic(OBS_DIM, N_ACTS)
    policy.load_state_dict(
        torch.load(ROOT / "results/baselines/b3_sbert/policy.pt", map_location="cpu")
    )
    return policy.to(device).eval()


def _load_b4(device: torch.device) -> torch.nn.Module:
    from src.training.baselines.diayn import DIAYNActorCritic
    policy = DIAYNActorCritic(OBS_DIM, N_ACTS)
    policy.load_state_dict(
        torch.load(ROOT / "results/baselines/b4_diayn/policy.pt", map_location="cpu")
    )
    return policy.to(device).eval()


# ── Per-model evaluation ──────────────────────────────────────────────────────

def eval_model(
    label:           str,
    policy:          torch.nn.Module,
    traj_enc:        TrajectoryEncoder | None,
    train_data:      list[dict],
    test_data:       list[dict],
    all_emb:         np.ndarray,
    dev:             torch.device,
    cfg:             argparse.Namespace,
    sampler_fn:      object = None,   # pre-built sampler; if None, defaults to pcsp/no-persona
    latency_context: dict | None = None,  # context dict for latency; None = no-persona
) -> dict:
    """Run all requested metrics for one model. Returns a result dict."""
    result: dict = {"model": label}
    is_persona_conditioned = traj_enc is not None

    print(f"\n{'='*60}")
    print(f"  Evaluating: {label}")
    print(f"{'='*60}")

    # ── Task reward ────────────────────────────────────────────────────────────
    if "reward" in cfg.metrics:
        print(f"  [reward] Running {cfg.n_reward_episodes} episodes...")
        t0 = time.time()
        if sampler_fn is not None:
            sampler = sampler_fn
        elif is_persona_conditioned:
            sampler = make_pcsp_sampler(train_data, all_emb, dev)
        else:
            sampler = make_no_persona_sampler(train_data)
        reward_stats = evaluate_task_reward(
            policy, sampler,
            n_episodes=cfg.n_reward_episodes,
            device=str(dev),
        )
        result["reward"] = reward_stats
        print(f"  [reward] mean={reward_stats['mean']:.2f} ± {reward_stats['std']:.2f}  "
              f"({time.time()-t0:.1f}s)")

    # ── Persona classification (train) ─────────────────────────────────────────
    if "consistency" in cfg.metrics and is_persona_conditioned:
        print(f"  [consistency] {cfg.n_consistency_personas} personas × {cfg.n_episodes} episodes...")
        t0 = time.time()
        con = persona_classification_accuracy(
            policy, traj_enc, train_data, all_emb,
            n_episodes=cfg.n_episodes,
            n_personas=cfg.n_consistency_personas,
            device=str(dev),
        )
        result["consistency"] = con
        print(f"  [consistency] acc={con['accuracy']:.3f}  "
              f"intra={con['intra_cos_mean']:.3f}  inter={con['inter_cos_mean']:.3f}  "
              f"({time.time()-t0:.1f}s)")

    # ── Zero-shot (test_60) ────────────────────────────────────────────────────
    if "zeroshot" in cfg.metrics and not cfg.skip_zeroshot and is_persona_conditioned:
        print(f"  [zeroshot] {len(test_data)} test personas × {cfg.n_episodes} episodes...")
        t0 = time.time()
        zs = zero_shot_consistency(
            policy, traj_enc, test_data, all_emb,
            n_episodes=cfg.n_episodes,
            device=str(dev),
        )
        result["zeroshot"] = zs
        print(f"  [zeroshot] acc={zs['accuracy']:.3f}  "
              f"coherence={zs['coherence_ratio']:.3f}  ({time.time()-t0:.1f}s)")

    # ── Behavioral KL ──────────────────────────────────────────────────────────
    if "diversity" in cfg.metrics and is_persona_conditioned:
        print(f"  [diversity] {cfg.n_persona_pairs} pairs × {cfg.n_states} states...")
        t0 = time.time()
        div = behavioral_kl_diversity(
            policy, all_emb, train_data,
            n_states=cfg.n_states,
            n_persona_pairs=cfg.n_persona_pairs,
            device=str(dev),
        )
        result["diversity"] = div
        print(f"  [diversity] mean_kl={div['mean_kl']:.4f}  "
              f"ρ={div['spearman_rho']:.3f}  ({time.time()-t0:.1f}s)")

    # ── Latency ────────────────────────────────────────────────────────────────
    if "latency" in cfg.metrics:
        print(f"  [latency] {cfg.n_latency_trials} trials...")
        t0 = time.time()
        # Use caller-supplied context; fall back to e_llm dummy for PCSP-style models
        if latency_context is None and is_persona_conditioned:
            latency_context = {
                "e_llm": torch.FloatTensor(all_emb[0].astype(np.float32)).unsqueeze(0)
            }
        lat = measure_policy_latency(
            policy, latency_context,
            n_warmup=200,
            n_trials=cfg.n_latency_trials,
            device=str(dev),
        )
        result["latency"] = lat
        print(f"  [latency] mean={lat['mean_ms']:.3f}ms  "
              f"p99={lat['p99_ms']:.3f}ms  ({time.time()-t0:.1f}s)")

    return result


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt(v: float | None, fmt: str = ".3f") -> str:
    if v is None:
        return "—"
    return format(v, fmt)


def print_comparison_table(results: list[dict]) -> None:
    """Print a comparison table to stdout."""
    cols = [
        ("Model",          "model",          20, "s"),
        ("Task Reward",    "reward.mean",     12, ".2f"),
        ("Consist Acc",    "consistency.accuracy", 12, ".3f"),
        ("ZeroShot Acc",   "zeroshot.accuracy",    12, ".3f"),
        ("Mean KL",        "diversity.mean_kl",    10, ".4f"),
        ("Spearman ρ",     "diversity.spearman_rho", 12, ".3f"),
        ("Latency (ms)",   "latency.mean_ms",      13, ".3f"),
    ]

    def get(d: dict, key: str):
        parts = key.split(".")
        v = d
        for k in parts:
            if isinstance(v, dict) and k in v:
                v = v[k]
            else:
                return None
        return v

    header = "  ".join(f"{name:{w}s}" for name, _, w, _ in cols)
    sep    = "  ".join("-" * w for _, _, w, _ in cols)
    print("\n" + header)
    print(sep)
    for r in results:
        row_vals = []
        for name, key, w, fmt in cols:
            v = get(r, key)
            if v is None:
                row_vals.append(f"{'—':{w}s}")
            elif fmt == "s":
                row_vals.append(f"{str(v):{w}s}")
            else:
                row_vals.append(f"{v:{w}{fmt}}")
        print("  ".join(row_vals))
    print()


def to_latex_table(results: list[dict]) -> str:
    """Generate a LaTeX tabular string for the paper."""
    rows = []
    for r in results:
        def g(key):
            v = r
            for k in key.split("."):
                v = v.get(k, {}) if isinstance(v, dict) else None
                if v is None:
                    return "—"
            return f"{v:.3f}" if isinstance(v, float) else str(v)

        rows.append(
            f"  {r['model']} & {g('reward.mean')} & {g('consistency.accuracy')} "
            f"& {g('zeroshot.accuracy')} & {g('diversity.mean_kl')} "
            f"& {g('diversity.spearman_rho')} & {g('latency.mean_ms')} \\\\"
        )

    header = (
        "\\begin{tabular}{lrrrrrrr}\n"
        "\\toprule\n"
        "Model & Task Reward & Consist Acc & Zero-Shot Acc & Mean KL & Spearman $\\rho$ & Latency (ms) \\\\\n"
        "\\midrule\n"
    )
    footer = "\\bottomrule\n\\end{tabular}"
    return header + "\n".join(rows) + "\n" + footer


# ── Main ──────────────────────────────────────────────────────────────────────

ALL_MODELS   = ["pcsp_full", "pcsp_no_consist", "pcsp_no_diverse", "pcsp_concat",
                "pcsp_frozen_proj", "b1", "b3", "b4"]
ALL_METRICS  = ["reward", "consistency", "zeroshot", "diversity", "latency"]


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--models",    nargs="+", default=ALL_MODELS,
                   help="Models to evaluate")
    p.add_argument("--metrics",   nargs="+", default=ALL_METRICS,
                   help="Metrics to compute")
    p.add_argument("--smoke",     action="store_true",
                   help="Quick smoke test (very few episodes)")
    p.add_argument("--skip_zeroshot", action="store_true")
    p.add_argument("--device",    default="cuda")

    # Eval scale
    p.add_argument("--n_reward_episodes",    type=int, default=100)
    p.add_argument("--n_episodes",           type=int, default=5,
                   help="Episodes per persona for consistency/zeroshot")
    p.add_argument("--n_consistency_personas", type=int, default=48,
                   help="Number of train personas to use for consistency eval")
    p.add_argument("--n_states",             type=int, default=200)
    p.add_argument("--n_persona_pairs",      type=int, default=100)
    p.add_argument("--n_latency_trials",     type=int, default=2000)

    p.add_argument("--output",    default="results/eval/comparison.json")
    return p.parse_args()


def main():
    args = _parse_args()

    if args.smoke:
        args.n_reward_episodes     = 10
        args.n_episodes            = 2
        args.n_consistency_personas = 8
        args.n_states              = 50
        args.n_persona_pairs       = 20
        args.n_latency_trials      = 100
        print("[smoke] Running quick smoke test with reduced scale.")

    dev = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"Device: {dev}")

    # Load shared data
    with open(ROOT / "data/personas/train_240.json") as f:
        train_data = json.load(f)
    with open(ROOT / "data/personas/test_60.json") as f:
        test_data = json.load(f)
    all_emb = np.load(ROOT / "results/embeddings/persona_embeddings_300.npy")

    # Pre-load B3/B4 embeddings (only if needed)
    sbert_emb = None
    diayn_emb = None
    if any(m == "b3" for m in args.models):
        sbert_path = ROOT / "results/embeddings/sbert_embeddings_train240.npy"
        if sbert_path.exists():
            sbert_emb = np.load(sbert_path)
        else:
            print("[warn] SBERT embeddings not found; B3 reward eval will be skipped.")
    if any(m == "b4" for m in args.models):
        diayn_path = ROOT / "results/baselines/b4_diayn/random_embeddings.npy"
        if diayn_path.exists():
            diayn_emb = np.load(diayn_path)
        else:
            print("[warn] DIAYN random embeddings not found; B4 reward eval will be skipped.")

    # Sample efficiency from training logs (fast, no GPU)
    if "efficiency" in args.metrics:
        eff_dirs = {}
        for mode in ["full", "no_consist", "no_diverse", "concat", "frozen_proj"]:
            d = ROOT / f"results/pcsp/{mode}"
            if d.exists():
                eff_dirs[f"pcsp_{mode}"] = d
        for bname in ["b1_no_persona", "b3_sbert", "b4_diayn"]:
            d = ROOT / f"results/baselines/{bname}"
            if d.exists():
                eff_dirs[bname] = d
        if eff_dirs:
            eff_results = compare_efficiency(eff_dirs, threshold=80.0)
            eff_out = ROOT / "results/eval/efficiency.json"
            eff_out.parent.mkdir(parents=True, exist_ok=True)
            with open(eff_out, "w") as f:
                json.dump(eff_results, f, indent=2)
            print(f"\n[efficiency] saved to {eff_out}")

    results: list[dict] = []
    t_total = time.time()

    for model_key in args.models:
        traj_enc         = None
        sampler_fn       = None
        latency_context  = None
        try:
            if model_key.startswith("pcsp_"):
                mode = model_key[5:]   # strip "pcsp_"
                policy, traj_enc = _load_pcsp(mode, dev)
                label            = f"PCSP ({mode})"
                sampler_fn       = make_pcsp_sampler(train_data, all_emb, dev)
                # latency_context falls back to e_llm dummy in eval_model
            elif model_key == "b1":
                policy     = _load_b1(dev)
                label      = "B1 No-Persona"
                sampler_fn = make_no_persona_sampler(train_data)
                latency_context = None
            elif model_key == "b3":
                policy = _load_b3(dev)
                label  = "B3 SBERT"
                if sbert_emb is not None:
                    sampler_fn = make_sbert_sampler(train_data, sbert_emb, dev)
                    latency_context = {
                        "e_embed": torch.FloatTensor(sbert_emb[0]).unsqueeze(0)
                    }
                else:
                    sampler_fn = make_no_persona_sampler(train_data)
            elif model_key == "b4":
                policy = _load_b4(dev)
                label  = "B4 DIAYN"
                if diayn_emb is not None:
                    sampler_fn = make_diayn_sampler(train_data, diayn_emb, dev)
                    latency_context = {
                        "e_embed": torch.FloatTensor(diayn_emb[0]).unsqueeze(0)
                    }
                else:
                    sampler_fn = make_no_persona_sampler(train_data)
            else:
                print(f"[warn] Unknown model key: {model_key}, skipping.")
                continue
        except Exception as e:
            print(f"[warn] Could not load {model_key}: {e}")
            results.append({"model": model_key, "error": str(e)})
            continue

        r = eval_model(
            label=label,
            policy=policy,
            traj_enc=traj_enc,
            train_data=train_data,
            test_data=test_data,
            all_emb=all_emb,
            dev=dev,
            cfg=args,
            sampler_fn=sampler_fn,
            latency_context=latency_context,
        )
        results.append(r)

        # Save intermediate (in case of OOM/timeout)
        out = ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(results, f, indent=2)

    # LLM-as-policy latency (offline, from cached benchmark)
    if "latency" in args.metrics:
        llm_lat = measure_llm_policy_latency()
        results.append({"model": "B5 LLM-as-policy", "latency": llm_lat})

    # Final output
    out = ROOT / args.output
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out}")

    # LaTeX table
    latex = to_latex_table(results)
    latex_out = out.with_suffix(".tex")
    with open(latex_out, "w") as f:
        f.write(latex)
    print(f"LaTeX table saved to {latex_out}")

    # Human-readable table
    print_comparison_table(results)
    print(f"Total evaluation time: {(time.time()-t_total)/60:.1f} min")


if __name__ == "__main__":
    main()
