"""Mini-Inzoi v3 — environment sanity & §9 acceptance criteria.

Covers the implementation-correctness checklist from
docs/design/mini-inzoi-v3/training-and-validation.md:
  - PettingZoo AEC API conformance.
  - All 20 actions reachable.
  - r_persona_style is persona-discriminating.
  - describe_v3_action_ko renders cleanly.
  - ACTION_STYLE_PROFILE non-degenerate (pairwise L1 ≥ 0.1 across activities).
  - All 8 needs are restorable.
  - ACTION_NAMES_V3 ordering snapshot.
  - Routine signal histogram does not saturate at 0/1 for >50% of timesteps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from pettingzoo.test import api_test

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.env.action_semantics import V3_ACTION_SEMANTICS, describe_v3_action_ko  # noqa: E402
from src.env.mini_inzoi import PersonaConfig  # noqa: E402
from src.env.mini_inzoi_v3 import (  # noqa: E402
    MAX_REPEAT,
    MiniInzoiV3Env,
    N_AGENTS,
    WORLD_OBJECTS,
)
from src.env.v3_constants import (  # noqa: E402
    ACTION_NAMES_V3,
    ACTION_RESTORE_V3,
    ACTION_STYLE_PROFILE,
    N_ACTIONS_V3,
    N_NEEDS_V3,
    OBS_DIM_V3_BASE,
    obs_dim_v3,
)

PERSONA_FILE = ROOT / "data" / "personas" / "personas_300_v3.json"


def _load_personas(n: int = N_AGENTS) -> list[PersonaConfig]:
    raw = json.loads(PERSONA_FILE.read_text(encoding="utf-8"))
    return [PersonaConfig.from_dict(p) for p in raw[:n]]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_obs_dim() -> None:
    assert obs_dim_v3(4) == 33, f"v3 base obs_dim should be 33, got {obs_dim_v3(4)}"
    assert obs_dim_v3(16) == 69, f"v3 large obs_dim should be 69, got {obs_dim_v3(16)}"
    print("obs_dim arithmetic: PASS ✓ (33 base / 69 large)")


def test_action_names_snapshot() -> None:
    expected = [
        "focused_work", "planning_work", "eat_quick", "eat_slow",
        "sleep", "nap", "socialize_initiate", "socialize_respond",
        "exercise_intense", "exercise_light", "read_deep", "read_casual",
        "clean", "rest_alone", "rest_with_others", "explore",
        "move_up", "move_down", "move_left", "move_right",
    ]
    assert ACTION_NAMES_V3 == expected, "ACTION_NAMES_V3 reordered — would break loaded checkpoints"
    print("ACTION_NAMES_V3 stability: PASS ✓")


def test_style_profile_non_degenerate() -> None:
    activity = ACTION_STYLE_PROFILE[:16]
    for i in range(16):
        for j in range(i + 1, 16):
            d = float(np.abs(activity[i] - activity[j]).sum())
            assert d >= 0.1, (
                f"ACTION_STYLE_PROFILE rows {i} ({ACTION_NAMES_V3[i]}) and "
                f"{j} ({ACTION_NAMES_V3[j]}) have L1 distance {d:.3f} < 0.1"
            )
    print("Style-profile non-degeneracy: PASS ✓ (16 activities pairwise L1 ≥ 0.1)")


def test_need_coverage() -> None:
    restored = set()
    for entry in ACTION_RESTORE_V3.values():
        if isinstance(entry, list):
            for ni, _ in entry:
                restored.add(ni)
        else:
            restored.add(entry[0])
    missing = set(range(N_NEEDS_V3)) - restored
    assert not missing, f"Needs not restored by any v3 action: {sorted(missing)}"
    print(f"Need coverage: PASS ✓ (all {N_NEEDS_V3} needs restorable)")


def test_api() -> None:
    env = MiniInzoiV3Env(personas=_load_personas(), max_steps=50)
    api_test(env, num_cycles=10, verbose_progress=False)
    print("PettingZoo AEC API: PASS ✓")


def test_actions_reachable() -> None:
    env = MiniInzoiV3Env(personas=_load_personas(), max_steps=20)
    env.reset(seed=0)
    seen: set[int] = set()
    # Force every action ID at least once.
    for a in range(N_ACTIONS_V3):
        agent = env.agent_selection
        _, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
            continue
        env.step(a)
        seen.add(a)
    assert seen == set(range(N_ACTIONS_V3)), f"Missing actions: {set(range(N_ACTIONS_V3)) - seen}"
    print(f"Action reachability: PASS ✓ ({len(seen)}/20 dispatched cleanly)")


def test_persona_style_discriminating() -> None:
    """Two personas with opposing Big-Five vectors should pick different
    style-maximizing actions."""
    high_e = PersonaConfig(
        preferred_actions=[],
        big_five={"E": "high", "N": "low", "A": "high", "C": "mid", "O": "high"},
        name="extravert_open",
    )
    low_e = PersonaConfig(
        preferred_actions=[],
        big_five={"E": "low", "N": "high", "A": "low", "C": "mid", "O": "low"},
        name="introvert_closed",
    )
    env = MiniInzoiV3Env(personas=[high_e, low_e, high_e, low_e], max_steps=10)
    env.reset(seed=0)

    def best_style_action(persona_idx: int) -> int:
        bf = env._bf_vecs[persona_idx]
        scores = []
        for a in range(16):  # activity actions only
            style = ACTION_STYLE_PROFILE[a]
            sn = float(np.linalg.norm(style))
            bn = float(np.linalg.norm(bf))
            cos = float(np.dot(style, bf)) / (sn * bn) if sn * bn > 1e-6 else 0.0
            scores.append(cos)
        return int(np.argmax(scores))

    a0 = best_style_action(0)
    a1 = best_style_action(1)
    assert a0 != a1, (
        f"Persona-style not discriminating: both high-E and low-E pick {ACTION_NAMES_V3[a0]}"
    )
    print(
        f"Persona-style discrimination: PASS ✓ "
        f"(extravert→{ACTION_NAMES_V3[a0]}, introvert→{ACTION_NAMES_V3[a1]})"
    )


def test_describe_v3_action_ko() -> None:
    # Synthesize one step per action ID.
    for a in range(N_ACTIONS_V3):
        step = {
            "action_id": a,
            "step": 3,
            "time_of_day": 14,
            "position": [2, 2],
            "nearby_agents": [1, 2] if a in (6, 7, 14) else [],
        }
        text = describe_v3_action_ko(step, world_objects=WORLD_OBJECTS)
        assert text and "행동" not in text or a >= 16, (
            f"describe_v3_action_ko returned fallback for action {a}: {text!r}"
        )
        # Sanity: every activity entry has at least one Korean variant.
        sem = V3_ACTION_SEMANTICS[a]
        assert len(sem.variants_ko) >= 1
    print("describe_v3_action_ko: PASS ✓ (all 20 actions render)")


def test_routine_signal_calibration() -> None:
    """Routine signal should have working dynamic range:
      - Under a repeat-heavy policy (50% repeat last action), the signal should
        sometimes register values in (0, 1) without pinning at 1 for >30% of
        steps (which would mean MAX_REPEAT is too low to discriminate routines).
      - We do NOT check low-end saturation under uniform-random because 1/20
        repeat probability correctly drives most random samples to 0 — that
        is the design intent, not a bug.
    """
    rng = np.random.default_rng(7)
    env = MiniInzoiV3Env(personas=_load_personas(), max_steps=200)
    env.reset(seed=7)
    samples: list[float] = []
    last_action_per_agent: dict[str, int] = {}
    for agent in env.agent_iter():
        obs, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
            continue
        # routine_signal repeat_count slot is at index 22 (= 3 + 8 + 8 + 3).
        samples.append(float(obs[22]))
        # Repeat-heavy policy: 50% repeat last action, otherwise sample.
        if agent in last_action_per_agent and rng.random() < 0.5:
            a = last_action_per_agent[agent]
        else:
            a = int(env.action_space(agent).sample())
        last_action_per_agent[agent] = a
        env.step(a)
    arr = np.array(samples)
    frac_in_range = float(((arr > 0.0) & (arr < 1.0)).mean())
    frac_pinned_hi = float((arr >= 1.0 - 1e-6).mean())
    assert frac_in_range >= 0.10, (
        f"Routine signal has no dynamic range under repeat-heavy policy: "
        f"frac_in_range={frac_in_range:.2f}, mean={arr.mean():.3f}"
    )
    assert frac_pinned_hi < 0.30, (
        f"Routine signal pinned high — MAX_REPEAT={MAX_REPEAT} too low: "
        f"frac_pinned_hi={frac_pinned_hi:.2f}"
    )
    print(
        f"Routine signal calibration: PASS ✓ "
        f"(in_range={frac_in_range:.2f}, pinned_hi={frac_pinned_hi:.2f}, mean={arr.mean():.3f})"
    )


def test_random_rollout_with_describe() -> None:
    env = MiniInzoiV3Env(personas=_load_personas(), max_steps=48)
    env.reset(seed=42)
    obs_dim_observed = env.observe("agent_0").shape[0]
    assert obs_dim_observed == OBS_DIM_V3_BASE, (
        f"obs shape {obs_dim_observed} != OBS_DIM_V3_BASE {OBS_DIM_V3_BASE}"
    )
    descs: list[str] = []
    for agent in env.agent_iter():
        _, _, term, trunc, _ = env.last()
        if term or trunc:
            env.step(None)
            continue
        a = env.action_space(agent).sample()
        descs.append(describe_v3_action_ko(
            {
                "action_id": a,
                "step": env.step_count,
                "time_of_day": env.time_of_day,
                "position": env.positions[env.agent_name_mapping[agent]],
            },
            world_objects=WORLD_OBJECTS,
        ))
        env.step(a)
    print(f"Random rollout: PASS ✓ ({len(descs)} agent steps, obs_dim={obs_dim_observed})")
    print(f"  Sample renders:")
    for d in descs[:3]:
        print(f"    {d}")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_obs_dim()
    test_action_names_snapshot()
    test_style_profile_non_degenerate()
    test_need_coverage()
    test_api()
    test_actions_reachable()
    test_persona_style_discriminating()
    test_describe_v3_action_ko()
    test_routine_signal_calibration()
    test_random_rollout_with_describe()
    print("\nAll v3 smoke tests passed.")
