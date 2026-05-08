# Mini-Inzoi v3 — Environment Design

**Status:** Draft v0.2 — 2026-05-08 (open questions closed; refactor plan and v1→v3 mapping pinned)
**Source plan:** [PLAN.md §4.1, §5, §6 Phase C](../PLAN.md)
**Predecessors:** [src/env/mini_inzoi.py](../src/env/mini_inzoi.py) (v1, 6×6, 4 agents), [src/env/mini_inzoi_v2.py](../src/env/mini_inzoi_v2.py) (v2, 12×12, 16 agents)

---

## 1. Why v3

The §3 immediate problem in PLAN.md: v1/v2's 12-action discrete space exposes only a thin slice of persona-relevant behavior. The pilot Korean human-eval surveys revealed that participants struggle to discriminate personalities from short coarse-action sequences (`read`, `rest`, `eat` are too close). The §4.1 §5 decision committed to keeping rich semantics **display-only** for v1/v2 and graduating them to environment state/reward in v3.

v3's job is to make persona-driven behavior **observable in the trajectory itself**, so:
1. Human raters can recover persona signal from short traces without prose annotation.
2. The trained encoder doesn't depend on rendering tricks for its persona-identification accuracy.
3. The same architecture (frozen LLM + LoRA + FiLM + PPO) carries over without major rework.

## 2. Goals & non-goals

**Goals.**
- Expand the action space so persona traits influence *which* action is taken, not just whether the action is preferred.
- Add observation features (location affordance, social context, routine) so persona differences enter the policy's observation distribution.
- Add reward shaping that rewards stylistic match to persona, not just need-satisfaction overlap.
- Keep the policy/encoder architecture compatible with PCSP modulo `n_actions` and `obs_dim`.
- Live in a new file (`src/env/mini_inzoi_v3.py`); v1/v2 remain untouched and runnable for paper-table reproduction.

**Non-goals (explicitly deferred).**
- Continuous action space.
- Factorized (multi-head) actions — revisit only if v3 results show flat discrete is bottlenecking compositional generalization (PLAN §5).
- Larger world / more agents than v2 (16). The v3 contribution is per-agent richness, not population scaling.
- Long-horizon memory beyond the current within-episode trajectory (deferred to research-agenda §VI.C of the paper).

## 3. Action ontology (20 actions)

Flat discrete `Discrete(20)` — 16 activity + 4 movement. Action IDs are stable; each action carries one "intent" and one "style." Style is a fixed property of the action ID (it does not need a separate head).

| ID  | Name                  | Intent     | Style hint                | Restores need |
|----:|:----------------------|:-----------|:--------------------------|:--------------|
| 0   | `focused_work`        | work       | deep, solo                | work          |
| 1   | `planning_work`       | work       | structured, slow          | work          |
| 2   | `eat_quick`           | self_care  | fast intake               | hunger        |
| 3   | `eat_slow`            | self_care  | savoring                  | hunger        |
| 4   | `sleep`               | self_care  | full restorative          | sleep         |
| 5   | `nap`                 | self_care  | brief recovery            | sleep (small) |
| 6   | `socialize_initiate`  | social     | proactive                 | social        |
| 7   | `socialize_respond`   | social     | reactive                  | social        |
| 8   | `exercise_intense`    | fitness    | high effort               | fitness       |
| 9   | `exercise_light`      | fitness    | low effort                | fitness (small) |
| 10  | `read_deep`           | learning   | study, focus              | learning      |
| 11  | `read_casual`         | leisure    | leisurely                 | leisure       |
| 12  | `clean`               | self_care  | tidy                      | hygiene       |
| 13  | `rest_alone`          | leisure    | solo recovery             | leisure       |
| 14  | `rest_with_others`    | social+leisure | group leisure         | social+leisure (split) |
| 15  | `explore`             | leisure    | novelty-seeking           | leisure (small) |
| 16  | `move_up`             | move       | —                         | —             |
| 17  | `move_down`           | move       | —                         | —             |
| 18  | `move_left`           | move       | —                         | —             |
| 19  | `move_right`          | move       | —                         | —             |

**Style profile** is a fixed 5-dim Big-Five-aligned vector per action ID, embedded in `ACTION_STYLE_PROFILE: np.ndarray (20, 5)`. For example:
- `focused_work` ≈ `[E=0, N=0, A=0, C=+1, O=0]` (rewards conscientiousness)
- `socialize_initiate` ≈ `[E=+1, N=0, A=+0.5, C=0, O=0]`
- `rest_alone` ≈ `[E=-1, N=+0.5, A=0, C=0, O=0]`
- `explore` ≈ `[E=+0.5, N=-0.5, A=0, C=0, O=+1]`

This profile feeds the reward (§5) and is the source of style-driven persona signal.

## 4. Observation schema (extends v1/v2)

v3 obs vector dimensions for the 4-agent v3 base scale (a 12×12 v3-large variant analogous to v2 follows the same template):

| Slice                              | Dim | Content                                                              |
|:-----------------------------------|----:|:---------------------------------------------------------------------|
| position                           | 2   | row, col / (GRID_SIZE − 1)                                            |
| time_of_day                        | 1   | hour / 23                                                             |
| needs                              | 8   | per-need normalized [0, 1]                                            |
| **affordance one-hot**             | 8   | one-hot for the WORLD_OBJECTS cell currently nearest the agent        |
| **social context**                 | 3   | nearby_count / N_AGENTS, in_conversation flag, last_responder flag    |
| **routine signal**                 | 2   | repeat_count of last action / max_repeat, time-since-last-novel       |
| other agents (per j ≠ i)           | 3·(N−1) | row, col / (GRID_SIZE − 1), last_action / (N_ACTIONS − 1)         |

**Base scale (4 agents):** `2 + 1 + 8 + 8 + 3 + 2 + 9 = 33` (was 20 in v1).
**Large scale (16 agents, parallel to v2):** `2 + 1 + 8 + 8 + 3 + 2 + 45 = 69` (was 56 in v2).

The new slices (affordance / social / routine) are the persona-observability handles:
- **Affordance** lets the policy condition on *what is reachable here*, so a high-conscientiousness NPC at the desk is in a different obs distribution than the same NPC at the sofa.
- **Social context** exposes "currently in a conversation" to the policy — extraverts and introverts can branch on this directly.
- **Routine signal** captures regularity: high-C personas should prefer states with low time-since-last-novel; high-N personas should not.

## 5. Reward function

```
r_total = r_need + r_persona_action + r_persona_style + r_social
```

| Term              | Description                                                                                                           | v1/v2 status         |
|:------------------|:----------------------------------------------------------------------------------------------------------------------|:---------------------|
| `r_need`          | Standard need-restoration reward.                                                                                      | unchanged            |
| `r_persona_action`| `+0.5` if action ID is in `persona.preferred_actions` (now over the 20-action space).                                  | unchanged in form    |
| `r_persona_style` | `+0.3 * cos(persona.bf_vec, ACTION_STYLE_PROFILE[a])`. Rewards stylistic match independent of preferred-action membership. | **new**          |
| `r_social`        | v1/v2 social-compatibility bonus, scaled by Big-Five compatibility of nearby agents.                                   | unchanged in form    |

The `r_persona_style` term is what makes choice between e.g. `eat_quick` and `eat_slow` carry persona signal — both restore hunger by the same amount, but different personas get different stylistic bonuses.

## 6. Action interface decision: flat discrete

We commit to flat `Discrete(20)`, not factorized (intent × style), for v3.

**Rationale.**
- The current PCSP actor head is a single `nn.Linear(128, n_actions)`. Flat discrete is a one-line change (`n_actions=20`).
- Factorized actions require: separate intent and style heads, joint distribution sampling, per-head log-probs, and updated PPO clipping. That's a significant trainer rewrite.
- The §5 PLAN guidance: "consider factorized actions only after v3 results show the need." We have no evidence yet that factorization helps; do not pre-pay the complexity cost.
- 20 actions × 33 obs is small enough that flat discrete should learn cleanly with the same PPO hyperparameters.

**When to revisit.** If v3 zero-shot accuracy on `unseen_archetype` saturates well below v1/v2's `unseen_occupation` accuracy, or if the policy collapses on stylistic dimensions (e.g., always picks `eat_quick` regardless of persona), factorize.

## 7. Backward compatibility & retraining requirements

| Component                    | v1/v2 keeps working? | v3 change                                                       |
|:-----------------------------|:---------------------|:----------------------------------------------------------------|
| `src/env/mini_inzoi.py`      | yes (untouched)      | —                                                               |
| `src/env/mini_inzoi_v2.py`   | yes (untouched)      | —                                                               |
| `src/env/action_semantics.py`| yes (untouched)      | add `V3_ACTION_SEMANTICS` dict and `describe_v3_action_ko()`; v1/v2 entry points unchanged. |
| `src/models/film.py`         | yes                  | constructed with `n_actions=20` for v3 runs.                     |
| `src/models/trajectory_encoder.py` | yes            | constructed with `n_actions=20` for v3 runs.                     |
| `src/training/pcsp_trainer.py`     | yes (after refactor) | thread `obs_dim` / `n_actions` / `env_factory` through signatures (see refactor note below). |
| `src/training/baselines/*.py`      | yes (after refactor) | same refactor: per_persona_ppo, diayn, sbert_policy, no_persona_ppo, llm_policy. |
| `src/eval/zeroshot.py`             | yes (after refactor) | same refactor; the `compositional_zero_shot` wrapper already accepts a split family — extend to accept obs/action dims. |
| `data/personas/personas_300.json` | yes             | needs v3 `preferred_actions` mapping (20-action space) → write `personas_300_v3.json`. |
| Existing checkpoints (`results/pcsp/*`) | **incompatible with v3** | retrain from scratch on v3 environment.                  |

**Refactor decision: thread, don't fork.** The current trainers and eval scripts hardcode `OBS_DIM = 20` and `N_ACTS = N_ACTIONS  # 12` at module level and import `MiniInzoiEnv` directly:

- `src/training/pcsp_trainer.py:31,36-37,635`
- `src/training/baselines/per_persona_ppo.py:23,26-27,147`
- `src/training/baselines/diayn.py:27,31-32,189`
- `src/training/baselines/sbert_policy.py:22,26-27,167`
- `src/training/baselines/no_persona_ppo.py:21,24-25,98`
- `src/training/baselines/llm_policy.py:26,30-31,170`
- `src/eval/zeroshot.py:46,55-56,281,284`

Each file is a near-identical edit: replace the module-level constants with constructor / function arguments, replace the hardcoded `MiniInzoiEnv(...)` factory with an injected `env_factory` callable, and add a `personas_path` parameter where currently the v1 persona file is implicit. **Forking** every trainer to a `*_v3.py` doubles maintenance and forces every future change to land twice; **threading** is a one-time edit (~7 files, mostly mechanical) that yields a clean v1/v2/v3 path. We commit to threading.

The threading edits are additive — every existing v1/v2 caller continues to work because the new arguments default to v1's `(20, 12, MiniInzoiEnv, personas_300.json)` constants. After this refactor, `scripts/run_pcsp_v3.py` is a thin wrapper that supplies v3 values; v1/v2 reproduction scripts are unchanged.

**Retraining required.** v3 changes both `obs_dim` (20→33 base, 56→69 large) and `n_actions` (12→20). Existing PCSP-full + ablations checkpoints cannot be reused on v3. Expected scope:
- PCSP-full (v3 base, 4 agents): one full run, ~6 GPU-hours by v1 protocol scaling.
- 3 critical ablations (`no_consist`, `no_diverse`, `concat`): another ~18 GPU-hours.
- Baselines (B1, B3): ~6 GPU-hours each.
- Total estimate: ~36 GPU-hours of training before v3 paper tables can be filled.

## 8. Implementation plan

Concrete file-by-file checklist for the v3 implementation phase. Ordering matters — earlier items are prerequisites.

1. [ ] `src/env/v3_constants.py` — new module exporting `N_ACTIONS_V3`, `ACTION_NAMES_V3`, `ACTION_STYLE_PROFILE`, `ACTION_RESTORE_V3`, `OBS_DIM_V3_BASE`, `OBS_DIM_V3_LARGE`. Single source of truth so trainers/evaluators don't hardcode.
2. [ ] `src/env/action_semantics.py` — add `V3_ACTION_SEMANTICS` (one entry per v3 action ID, with `intent`, `default_place`, `variants_ko`) and `describe_v3_action_ko()`; keep v1/v2 entry points unchanged.
3. [ ] `data/personas/personas_300_v3.json` — re-emit `preferred_actions` over the 20-action space using the **deterministic mapping table below (§8.1)**.
4. [ ] `src/env/mini_inzoi_v3.py` — new `MiniInzoiV3Env` (4-agent base scale).
   - `_make_obs`: add affordance one-hot, social context, routine signal.
   - `_compute_reward`: add `r_persona_style` term.
   - `step`: track `last_actions[agent]` repeat count for routine signal.
5. [ ] `scripts/test_env_v3.py` — PettingZoo API conformance test, mirrors `scripts/test_env.py`.
6. [ ] **Trainer/eval refactor** (per §7 threading decision): replace module-level `OBS_DIM`/`N_ACTS` constants and hardcoded `MiniInzoiEnv` factories with injected arguments in `pcsp_trainer.py`, `baselines/{per_persona_ppo,diayn,sbert_policy,no_persona_ppo,llm_policy}.py`, and `eval/zeroshot.py`. Default values reproduce v1 behavior; v1 callers are unchanged.
7. [ ] `scripts/run_pcsp_v3.py` — thin wrapper that calls the threaded `train_pcsp(...)` with `OBS_DIM_V3_BASE`, `N_ACTIONS_V3`, `env_factory=MiniInzoiV3Env`, `personas_path="data/personas/personas_300_v3.json"`.
8. [ ] (optional, post-smoke) `src/env/mini_inzoi_v3_large.py` — 12×12, 16-agent variant matching v2.

### 8.1 v1 → v3 `preferred_actions` mapping rule

`personas_300_v3.json` is generated deterministically from `personas_300.json`. Each v1 preferred action expands to a v3 set, modulated by the persona's Big-Five level on the relevant axis. `bf` levels are `high` / `mid` / `low`.

| v1 action | v3 split             | Modulator | high → keep | mid → keep | low → keep |
|----------:|:---------------------|:---------:|:------------|:-----------|:-----------|
| 0 work    | 0 focused_work, 1 planning_work | C | {0, 1} | {0}        | {0}        |
| 1 eat     | 2 eat_quick, 3 eat_slow         | C | {3}    | {2, 3}     | {2}        |
| 2 sleep   | 4 sleep, 5 nap                  | C | {4}    | {4, 5}     | {5}        |
| 3 socialize | 6 socialize_initiate, 7 socialize_respond | E | {6, 7} | {6, 7} | {7}    |
| 4 exercise | 8 exercise_intense, 9 exercise_light | E | {8} | {8, 9}     | {9}        |
| 5 read    | 10 read_deep, 11 read_casual    | O | {10, 11} | {10, 11} | {11}     |
| 6 clean   | 12 clean                        | — | {12}   | {12}       | {12}       |
| 7 rest    | 13 rest_alone, 14 rest_with_others | E | {14} | {13, 14}  | {13}       |

After expansion, **add `15 explore`** to the persona's `preferred_actions` set if `O = high` (openness drives novelty-seeking). This is the only v3 action without a v1 ancestor.

The output is the union of all expanded sets, sorted ascending. Example: a v1 persona with `preferred_actions=[3, 5]`, `big_five={E: high, O: high}` → v3 `{6, 7} ∪ {10, 11} ∪ {15} = [6, 7, 10, 11, 15]`.

The mapping is **deterministic** and **reproducible**: regenerating from `personas_300.json` always yields byte-identical `personas_300_v3.json`. The script that performs this mapping lives at `scripts/build_personas_v3.py` (added in step 3).

## 9. Smoke tests & acceptance criteria

A v3 environment is "implementation-correct" when:

- [ ] `scripts/test_env_v3.py` passes the PettingZoo AEC API test.
- [ ] All 20 actions are reachable from at least one initial state (no dead actions).
- [ ] `_compute_reward(persona, action)` produces persona-discriminating values: for two personas A and B with very different Big-Five vectors, the action that maximizes `r_persona_style` differs.
- [ ] Random rollout renders cleanly via `describe_v3_action_ko()` with no `KeyError` on unmapped action IDs.
- [ ] **Style-profile non-degeneracy:** no two activity actions (IDs 0–15) share identical rows in `ACTION_STYLE_PROFILE`. Pairwise L1 distance ≥ 0.1.
- [ ] **Need coverage:** every one of the 8 needs is restored by ≥ 1 entry in `ACTION_RESTORE_V3`. (The read-deep / read-casual split moves `learning` and `leisure` around, so this is worth pinning.)
- [ ] **Action ID stability:** test snapshot of `ACTION_NAMES_V3` ordering. Reordering would silently break loaded checkpoints because `TrajectoryEncoder` one-hots by ID.
- [ ] **Routine signal calibration:** under a *repeat-heavy* policy (50% probability of repeating the last action), `routine_signal[0]` (`repeat_count / max_repeat`) achieves working dynamic range — at least 10% of timesteps fall in `(0, 1)` and no more than 30% pin at 1. (We do not check saturation under uniform-random, because `1/N_ACTIONS` correctly drives most samples to 0.)

A v3 PCSP run is "training-correct" when:

- [ ] PCSP-full smoke training (50 PPO iterations on `personas_300_v3.json`, 4 train personas) shows monotonic reward improvement.
- [ ] Trajectory encoder outputs differ across two distinct personas after training (mean cosine similarity < 0.95 across 5 episodes each).
- [ ] InfoNCE consistency loss converges below 1.0 within 50 iterations (sanity vs v1's typical convergence trajectory).

A v3 PCSP run is "ready for the paper" when:

- [ ] Full training (300 iters) on the unseen_occupation v3 split reproduces or beats v1's unseen-occupation `compositional_zero_shot` accuracy.
- [ ] Human persona-identification on v3 rich traces (re-using the existing Korean survey infrastructure) is meaningfully above 50% chance.

## 10. Open questions — decisions for v3

The five open questions from v0.1 have been resolved as follows. Items deferred to v4 are listed under §11.

1. **Persona-style fitting.** **Decision: ship hand-authored** for v3. Learning the style table couples encoder convergence to a moving target and would force re-authoring `ACTION_STYLE_PROFILE` as an ablation baseline; the §7 36-GPU-hour budget already does not carry that. Revisit in v4 if v3 persona discrimination plateaus.
2. **Action availability filtering.** **Decision: do not filter** for v3. Masked PPO is a real trainer rewrite (action masking in log-prob computation, sampling, policy loss) that lands outside the §7 "additive threading" scope. Keep all 20 actions always available; let `r_persona_action` and `r_persona_style` drive behavior. Revisit when v4 introduces masking infra.
3. **`personas_300_v3.json` derivation.** **Decision: deterministic auto-mapping** per the table in §8.1. Re-generating from Big-Five via LLM is deferred — first see whether the deterministic mapping is sufficient for the v3 paper-table runs.
4. **Routine signal saturation.** **Decision: calibrate during smoke tests**, with explicit acceptance criterion added to §9 ("histogram does not saturate at 0 or 1 for >50% of timesteps in random rollout").
5. **Baseline parity.** **Decision: re-measure B5 latency** before any v3 paper update reuses the 22× figure. Document the v3 prompt length (20-action choice list, longer than v1's 12-action prompt) and rerun the latency benchmark.

## 11. Deferred to v4

Tracked here so they don't get lost; not in scope for the CoG submission.

- Richer interaction ontology (avoided / argued / comforted etc.) requiring multi-step interaction state, not just per-step flags.
- Masked PPO with location-affordance action filtering.
- Learned `ACTION_STYLE_PROFILE` via a style-attribution head.
- Long-horizon memory beyond the within-episode trajectory.

---

Once §1-§7 of this doc are accepted, the §8 implementation tasks become the active work for Phase C in PLAN.md.
