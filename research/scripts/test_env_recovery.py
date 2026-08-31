"""Regression-test recovered Mini-Inzoi dynamics against committed rollouts.

The target-agent records contain the other agents' most recent action IDs in
their observation.  Replaying those actions reconstructs the complete AEC
cycle, which lets us verify every subsequent target observation and reward.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.mini_inzoi import MiniInzoiEnv, PersonaConfig  # noqa: E402
from src.env.mini_inzoi_v3 import MiniInzoiV3Env  # noqa: E402

TOLERANCE = 1e-5
CASES = (
    ("pcsp_full_zero_shot_rollouts.json", MiniInzoiEnv, 11, 11),
    ("pcsp_v3_full_zero_shot_rollouts.json", MiniInzoiV3Env, 24, 19),
)


def replay_case(filename: str, env_cls, other_slice: int, action_denominator: int) -> tuple[int, float, float]:
    artifact = json.loads(
        (ROOT / "results" / "human_eval" / filename).read_text(encoding="utf-8")
    )
    persona_data = json.loads((ROOT / artifact["personas"]).read_text(encoding="utf-8"))
    personas_by_id = {int(persona["id"]): persona for persona in persona_data}
    transitions = 0
    max_obs_error = 0.0
    max_reward_error = 0.0

    for rollout in artifact["rollouts"]:
        personas = [
            PersonaConfig.from_dict(personas_by_id[int(persona_id)])
            for persona_id in rollout["context_persona_ids"]
        ]
        env = env_cls(personas=personas, max_steps=int(artifact["max_steps"]))
        env.reset(seed=int(rollout["seed"]))
        actions = rollout["actions"]

        for index, event in enumerate(actions):
            expected_obs = np.asarray(event["obs"], dtype=np.float32)
            max_obs_error = max(
                max_obs_error,
                float(np.max(np.abs(env.observe("agent_0") - expected_obs))),
            )
            env.step(int(event["action_id"]))
            max_reward_error = max(
                max_reward_error,
                abs(float(env.rewards["agent_0"]) - float(event["reward"])),
            )
            transitions += 1

            next_obs = actions[index + 1]["obs"] if index + 1 < len(actions) else None
            for other_idx in range(3):
                if next_obs is None:
                    other_action = 0
                else:
                    encoded = next_obs[other_slice + 3 * other_idx + 2]
                    other_action = int(round(float(encoded) * action_denominator))
                env.step(other_action)
        env.close()

    assert max_obs_error < TOLERANCE, (filename, max_obs_error)
    assert max_reward_error < TOLERANCE, (filename, max_reward_error)
    return transitions, max_obs_error, max_reward_error


def main() -> None:
    for case in CASES:
        transitions, obs_error, reward_error = replay_case(*case)
        print(
            f"{case[0]}: PASS ({transitions} transitions, "
            f"obs_max={obs_error:.3g}, reward_max={reward_error:.3g})"
        )


if __name__ == "__main__":
    main()
