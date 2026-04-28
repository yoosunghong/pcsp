"""Mini-Inzoi 환경 sanity check — AEC API 검증"""
import sys
sys.path.insert(0, "/home/swim/Documents/Projects/co-spec")

import numpy as np
from pettingzoo.test import api_test
from src.env.mini_inzoi import MiniInzoiEnv, N_ACTIONS

def test_api():
    env = MiniInzoiEnv(max_steps=50)
    api_test(env, num_cycles=10, verbose_progress=False)
    print("PettingZoo API test: PASS ✓")

def test_rollout():
    env = MiniInzoiEnv(max_steps=48)
    env.reset(seed=42)

    total_rewards = {a: 0.0 for a in env.agents}
    step = 0
    for agent in env.agent_iter():
        obs, rew, term, trunc, info = env.last()
        total_rewards[agent] += rew
        if term or trunc:
            action = None
        else:
            action = env.action_space(agent).sample()
        env.step(action)
        step += 1

    print(f"\nRandom rollout complete: {step} agent steps")
    print(f"Obs shape: {env.observe('agent_0').shape}")
    for a, r in total_rewards.items():
        idx = env.agent_name_mapping[a]
        persona_name = env.personas[idx].name
        print(f"  {a} ({persona_name}): total_reward={r:.3f}")

    print("Rollout test: PASS ✓")

def test_render():
    env = MiniInzoiEnv(max_steps=5)
    env.reset(seed=0)
    for agent in env.agent_iter():
        _, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
        else:
            env.step(env.action_space(agent).sample())
    print("\nRender output:")
    print(env.render())

if __name__ == "__main__":
    test_api()
    test_rollout()
    test_render()
