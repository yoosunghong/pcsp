"""
Phase 3 — Baseline runner.

Runs all 5 baselines (B1–B5) with consistent seeds and config.
Results saved to results/baselines/{b1..b5_*}/

Usage:
  # Run all baselines (full training)
  conda run -n paper python scripts/run_baselines.py

  # Quick smoke-test (20 iterations)
  conda run -n paper python scripts/run_baselines.py --smoke

  # Single baseline
  conda run -n paper python scripts/run_baselines.py --baseline b1

  # B5 latency benchmark only
  conda run -n paper python scripts/run_baselines.py --baseline b5 --b5_steps 20
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.training.ppo_trainer import PPOConfig

ROOT = Path(__file__).resolve().parent.parent


def get_config(smoke: bool) -> PPOConfig:
    if smoke:
        return PPOConfig(
            total_iterations=20,
            n_episodes_per_iter=4,
            n_epochs=2,
            batch_size=128,
            log_interval=5,
        )
    return PPOConfig(
        total_iterations=300,
        n_episodes_per_iter=8,
        n_epochs=4,
        batch_size=256,
        log_interval=20,
    )


def run_b1(args):
    from src.training.baselines.no_persona_ppo import train_b1
    print("\n" + "="*60)
    print("B1: No-Persona PPO")
    print("="*60)
    return train_b1(
        config=get_config(args.smoke),
        device=args.device,
        n_iterations=args.iterations,
    )


def run_b2(args):
    from src.training.baselines.per_persona_ppo import train_b2
    print("\n" + "="*60)
    print("B2: Per-Persona PPO")
    print("="*60)
    return train_b2(
        config=get_config(args.smoke),
        device=args.device,
        n_train_personas=24,
        n_iterations=args.iterations,
    )


def run_b3(args):
    from src.training.baselines.sbert_policy import train_b3
    print("\n" + "="*60)
    print("B3: SBERT + frozen embed")
    print("="*60)
    return train_b3(
        config=get_config(args.smoke),
        device=args.device,
        n_iterations=args.iterations,
    )


def run_b4(args):
    from src.training.baselines.diayn import train_b4
    print("\n" + "="*60)
    print("B4: DIAYN (random latent)")
    print("="*60)
    return train_b4(
        config=get_config(args.smoke),
        device=args.device,
        n_iterations=args.iterations,
    )


def run_b5(args):
    from src.training.baselines.llm_policy import benchmark_llm_policy
    print("\n" + "="*60)
    print("B5: LLM-as-Policy (Qwen3-1.7B latency benchmark)")
    print("="*60)
    return benchmark_llm_policy(
        n_steps=args.b5_steps,
        device=args.device,
    )


def print_summary(results: dict):
    print("\n" + "="*60)
    print("PHASE 3 SUMMARY")
    print("="*60)
    headers = ["Baseline", "Final Reward", "Notes"]
    rows = []
    for name, r in results.items():
        reward = r.get("mean_ep_reward") or r.get("total_reward", "N/A")
        reward_str = f"{reward:.3f}" if isinstance(reward, float) else str(reward)

        if name == "b5":
            notes = f"lat={r.get('mean_latency_ms', 'N/A'):.1f}ms/step (no training)"
        elif name == "b2":
            notes = "oracle upper bound"
        elif name == "b1":
            notes = "lower bound (no persona)"
        elif name == "b3":
            notes = "SBERT 384-dim embed"
        elif name == "b4":
            notes = "random 64-dim embed"
        else:
            notes = ""
        rows.append((name.upper(), reward_str, notes))

    col_w = [12, 14, 35]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_w)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_w))
    for row in rows:
        print(fmt.format(*row))


def main():
    parser = argparse.ArgumentParser(description="Run Phase 3 baselines")
    parser.add_argument(
        "--baseline", choices=["b1", "b2", "b3", "b4", "b5", "all"],
        default="all", help="Which baseline to run (default: all)"
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="Quick smoke-test (20 iterations, small batch)"
    )
    parser.add_argument(
        "--iterations", type=int, default=None,
        help="Override total_iterations (default: 20 smoke / 300 full)"
    )
    parser.add_argument(
        "--device", default="cuda",
        help="PyTorch device (default: cuda)"
    )
    parser.add_argument(
        "--b5_steps", type=int, default=50,
        help="Number of LLM steps for B5 benchmark (default: 50)"
    )
    parser.add_argument(
        "--skip_b5", action="store_true",
        help="Skip B5 (LLM benchmark takes a long time)"
    )
    args = parser.parse_args()

    t_start = time.time()
    results = {}

    runners = {
        "b1": run_b1,
        "b2": run_b2,
        "b3": run_b3,
        "b4": run_b4,
        "b5": run_b5,
    }

    if args.baseline == "all":
        targets = list(runners.keys())
        if args.skip_b5:
            targets.remove("b5")
    else:
        targets = [args.baseline]

    for name in targets:
        try:
            results[name] = runners[name](args)
        except Exception as e:
            print(f"\n[ERROR] {name.upper()} failed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = {"error": str(e)}

    # Save combined results
    out_path = ROOT / "results/baselines/summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "results": results,
            "total_elapsed_sec": time.time() - t_start,
        }, f, indent=2)

    print_summary(results)
    print(f"\nTotal elapsed: {time.time()-t_start:.1f}s")
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
