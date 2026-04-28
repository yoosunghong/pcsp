"""
B5: LLM-as-Policy — Qwen3-1.7B reads persona + state and outputs action each step.

No training. This baseline measures:
  - Inference latency (ms/step)
  - Task performance with zero RL training

The prompt includes the persona description and current game state (needs, position).
The model outputs a single action token (/no_think mode for speed).

Target: < 30ms/step. Expected actual: ~500ms/step (Qwen3-1.7B on GPU).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.env.mini_inzoi import (
    MiniInzoiEnv, PersonaConfig, DEFAULT_PERSONAS,
    N_ACTIONS, N_NEEDS, NEED_NAMES, ACTION_NAMES,
)

OBS_DIM   = 20
N_ACTS    = N_ACTIONS  # 12

# Map action names to token strings the LLM can output
ACTION_TOKENS = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
]

SYSTEM_PROMPT = (
    "You are controlling an NPC in a life simulation game. "
    "Choose the single best action number (0-11) for the NPC given its persona and current needs. "
    "Output only the action number and nothing else.\n\n"
    "Actions:\n"
    + "\n".join(f"  {i}: {name}" for i, name in enumerate(ACTION_NAMES))
)


def _obs_to_text(obs: np.ndarray, persona_text: str) -> str:
    """Convert observation vector and persona to a concise prompt."""
    pos_x = int(obs[0] * 5)
    pos_y = int(obs[1] * 5)
    hour  = int(obs[2] * 23)
    needs = obs[3:3 + N_NEEDS]

    need_str = ", ".join(
        f"{NEED_NAMES[i]}={needs[i]*100:.0f}%" for i in range(N_NEEDS)
    )
    # Highlight critically low needs
    critical = [NEED_NAMES[i] for i in range(N_NEEDS) if needs[i] < 0.2]
    critical_str = f"CRITICAL: {', '.join(critical)}" if critical else "No critical needs"

    return (
        f"Persona: {persona_text}\n"
        f"Position: ({pos_x}, {pos_y})  Time: {hour:02d}:00\n"
        f"Needs: {need_str}\n"
        f"{critical_str}\n"
        f"Choose action (0-11):"
    )


# ── LLM Policy ─────────────────────────────────────────────────────────────────

class LLMPolicy:
    """
    Wraps Qwen3-1.7B for per-step action selection.

    Loaded once; call `act(obs, persona_text)` per step.
    Uses greedy decoding (max_new_tokens=3) for speed.
    """

    MODEL_NAME = "Qwen/Qwen3-1.7B"

    def __init__(self, device: str = "cuda", use_no_think: bool = True):
        from transformers import AutoTokenizer, AutoModelForCausalLM

        print(f"[B5] Loading {self.MODEL_NAME} …")
        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_NAME, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            self.MODEL_NAME,
            torch_dtype=torch.float16,
            device_map=device,
            trust_remote_code=True,
        )
        self.model.eval()
        self.device = device
        self.use_no_think = use_no_think
        print(f"[B5] Model loaded in {time.time()-t0:.1f}s")

    @torch.no_grad()
    def act(self, obs: np.ndarray, persona_text: str) -> int:
        """Return action index (0-11) for the given observation and persona."""
        user_msg = _obs_to_text(obs, persona_text)

        # /no_think suffix disables chain-of-thought for speed
        if self.use_no_think:
            user_msg += " /no_think"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=4,
            do_sample=False,         # greedy for determinism
            pad_token_id=self.tokenizer.eos_token_id,
        )
        # Decode only generated tokens
        new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        # Parse first integer token from response
        for token in response.split():
            try:
                action = int(token)
                if 0 <= action < N_ACTS:
                    return action
            except ValueError:
                continue
        # Fallback: random action
        return int(np.random.randint(0, N_ACTS))


# ── Benchmark ─────────────────────────────────────────────────────────────────

def benchmark_llm_policy(
    personas_json: str | Path = "data/personas/train_240.json",
    n_steps: int = 50,
    device: str = "cuda",
    output_dir: str | Path = "results/baselines/b5_llm",
    seed: int = 42,
) -> dict:
    """
    Run the LLM policy for n_steps in the environment.
    Measures latency and records episode reward.

    n_steps=50 by default (full 200-step episode would take ~100s+ at 500ms/step).
    """
    root = Path(__file__).resolve().parents[3]
    output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(root / personas_json) as f:
        personas_data = json.load(f)

    rng = np.random.default_rng(seed)
    idxs = rng.choice(len(personas_data), size=4, replace=False)
    personas = [PersonaConfig.from_dict(personas_data[i]) for i in idxs]
    persona_texts = {f"agent_{j}": personas_data[int(idxs[j])]["text"] for j in range(4)}

    policy = LLMPolicy(device=device)

    env = MiniInzoiEnv(personas=personas, max_steps=n_steps)
    env.reset(seed=seed)

    latencies: list[float] = []
    total_reward = 0.0
    actions_taken: list[dict] = []
    step_count = 0

    print(f"[B5] Running {n_steps} agent-steps (4 agents, {n_steps//4} full rounds)…")

    for agent in env.agent_iter():
        obs, rew, term, trunc, _ = env.last()
        total_reward += rew

        if term or trunc:
            env.step(None)
            continue

        persona_text = persona_texts[agent]

        t0 = time.perf_counter()
        action = policy.act(obs, persona_text)
        latency_ms = (time.perf_counter() - t0) * 1000

        latencies.append(latency_ms)
        actions_taken.append({"agent": agent, "action": action, "latency_ms": latency_ms})
        env.step(action)

        step_count += 1
        if step_count % 10 == 0:
            print(f"  step {step_count:3d}/{n_steps}  lat={latency_ms:.1f}ms  action={ACTION_NAMES[action]}")

        if step_count >= n_steps:
            break

    env.close()

    latencies_arr = np.array(latencies)
    results = {
        "n_steps":         step_count,
        "mean_latency_ms": float(latencies_arr.mean()),
        "p50_latency_ms":  float(np.percentile(latencies_arr, 50)),
        "p95_latency_ms":  float(np.percentile(latencies_arr, 95)),
        "total_reward":    total_reward,
        "actions":         actions_taken,
        "model":           LLMPolicy.MODEL_NAME,
    }

    print(
        f"\n[B5] Results | latency: mean={results['mean_latency_ms']:.1f}ms "
        f"p50={results['p50_latency_ms']:.1f}ms p95={results['p95_latency_ms']:.1f}ms | "
        f"total_reward={total_reward:.3f}"
    )

    with open(output_dir / "benchmark.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"[B5] Results saved to {output_dir / 'benchmark.json'}")

    return results
