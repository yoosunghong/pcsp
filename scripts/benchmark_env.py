"""
Phase 2-3: Mini-Inzoi v0.2 환경 속도 벤치마크
목표: PPO 학습에 충분한 throughput 확인 (목표: > 10,000 steps/sec)

측정 항목:
  - steps/sec (random policy, single env)
  - steps/sec (with FiLM policy forward pass)
  - episode 길이 평균, reward 통계
"""
import sys, time
import numpy as np

sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")

from src.env.mini_inzoi import MiniInzoiEnv, DEFAULT_PERSONAS, N_ACTIONS, N_NEEDS


def benchmark_random_policy(n_episodes: int = 50, max_steps: int = 200) -> dict:
    env = MiniInzoiEnv(personas=DEFAULT_PERSONAS, max_steps=max_steps)

    total_steps = 0
    episode_rewards: list[float] = []

    t0 = time.perf_counter()
    for ep in range(n_episodes):
        env.reset(seed=ep)
        ep_reward = 0.0
        ep_steps = 0

        for agent in env.agent_iter():
            obs, rew, term, trunc, info = env.last()
            ep_reward += rew
            if term or trunc:
                env.step(None)
            else:
                action = env.action_space(agent).sample()
                env.step(action)
            ep_steps += 1

        total_steps += ep_steps
        episode_rewards.append(ep_reward)

    elapsed = time.perf_counter() - t0
    return {
        "policy": "random",
        "n_episodes": n_episodes,
        "total_steps": total_steps,
        "elapsed_sec": elapsed,
        "steps_per_sec": total_steps / elapsed,
        "mean_episode_reward": float(np.mean(episode_rewards)),
        "std_episode_reward": float(np.std(episode_rewards)),
        "mean_episode_length": total_steps / n_episodes,
    }


def benchmark_film_policy(n_episodes: int = 20, max_steps: int = 200) -> dict:
    import torch
    from src.models.film import PersonaConditionedPolicy

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Load precomputed LLM embeddings (fallback to random if not found)
    import pathlib
    emb_path = pathlib.Path(
        "/home/swim/Documents/Projects/co-spec/results/embeddings/persona_embeddings_30.npy"
    )
    if emb_path.exists():
        all_embs = np.load(emb_path)
        # Use first 4 as agent embeddings
        e_llm = torch.tensor(all_embs[:4], dtype=torch.float32).to(device)
    else:
        print("  (persona embeddings not found, using random)")
        e_llm = torch.randn(4, 1024, device=device)
        e_llm = torch.nn.functional.normalize(e_llm, dim=-1)

    policy = PersonaConditionedPolicy(
        obs_dim=20, n_actions=N_ACTIONS, persona_dim=64, llm_dim=1024
    ).to(device)
    policy.eval()

    env = MiniInzoiEnv(personas=DEFAULT_PERSONAS, max_steps=max_steps)

    total_steps = 0
    episode_rewards: list[float] = []

    t0 = time.perf_counter()
    for ep in range(n_episodes):
        env.reset(seed=ep + 1000)
        ep_reward = 0.0
        ep_steps = 0

        for agent in env.agent_iter():
            obs, rew, term, trunc, info = env.last()
            ep_reward += rew
            if term or trunc:
                env.step(None)
            else:
                i = env.agent_name_mapping[agent]
                obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0).to(device)
                e_i = e_llm[i].unsqueeze(0)
                with torch.no_grad():
                    action, _ = policy.act(obs_t, e_i)
                env.step(action.item())
            ep_steps += 1

        total_steps += ep_steps
        episode_rewards.append(ep_reward)

    elapsed = time.perf_counter() - t0
    return {
        "policy": "film",
        "device": device,
        "n_episodes": n_episodes,
        "total_steps": total_steps,
        "elapsed_sec": elapsed,
        "steps_per_sec": total_steps / elapsed,
        "mean_episode_reward": float(np.mean(episode_rewards)),
        "std_episode_reward": float(np.std(episode_rewards)),
        "mean_episode_length": total_steps / n_episodes,
    }


def print_result(r: dict) -> None:
    print(f"\n  Policy: {r['policy'].upper()}" + (f" ({r.get('device','')})" if "device" in r else ""))
    print(f"  Steps/sec  : {r['steps_per_sec']:>10,.0f}")
    print(f"  Ep. reward : {r['mean_episode_reward']:>10.3f} ± {r['std_episode_reward']:.3f}")
    print(f"  Ep. length : {r['mean_episode_length']:>10.1f}")
    target = 10_000
    status = "PASS ✓" if r["steps_per_sec"] >= target else "BELOW TARGET"
    print(f"  Target >{target:,} steps/sec → {status}")


def main():
    print("=" * 60)
    print("Mini-Inzoi v0.2 — Environment Benchmark")
    print("=" * 60)

    print("\n[1/2] Random policy (50 episodes × 200 steps)...")
    r1 = benchmark_random_policy(n_episodes=50)
    print_result(r1)

    print("\n[2/2] FiLM policy (20 episodes × 200 steps)...")
    r2 = benchmark_film_policy(n_episodes=20)
    print_result(r2)

    # Save results
    import json, pathlib
    out = {"random": r1, "film": r2}
    out_path = pathlib.Path(
        "/home/swim/Documents/Projects/co-spec/results/benchmark_env.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
