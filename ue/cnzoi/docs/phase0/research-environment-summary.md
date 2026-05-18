# Phase 0 — Mini-Inzoi v3 Environment Summary (for UE5)

This is the UE5-side reference for what the Python research environment provides.
It exists so engine engineers don't have to read the full research design doc to
understand what the policy expects.

**Authoritative source:** [`research/docs/mini_inzoi_v3_design.md`](../../../../research/docs/mini_inzoi_v3_design.md).
If anything here disagrees with that doc, the research doc wins — open an issue.

---

## What the policy is

A flat discrete actor-critic over the v3 Mini-Inzoi gridworld. Frozen Qwen3
embeddings → 64-d LoRA projection → FiLM-conditioned MLP → 20-way action head.

The trained checkpoint lives at `research/results/pcsp_v3/full/policy.pt` on the
training machine. The UE5 runtime never loads that checkpoint directly —
`research/scripts/export_pcsp_onnx.py` produces the two files the engine reads:

| File | UE path | Owner |
|---|---|---|
| `pcsp_actor.onnx` | `ue/cnzoi/Content/PCSP/Models/` | `UPCSPPolicySubsystem` |
| `persona_embeddings.json` | `ue/cnzoi/Content/PCSP/Data/` | `UPCSPPersonaCache` |

## Action space (20)

The flat `Discrete(20)` ordering is **load-bearing** — `ACTION_NAMES_V3` indexes
the actor head and is one-hot'd by the trajectory encoder. Renumbering breaks
loaded checkpoints silently.

| ID | Name | Intent | UE remap (`PCSPPolicySubsystem.cpp`) |
|---:|---|---|---|
| 0 | focused_work | work | `FocusedWork` |
| 1 | planning_work | work | `PlanningWork` |
| 2 | eat_quick | self_care | `EatQuick` |
| 3 | eat_slow | self_care | `EatSlow` |
| 4 | sleep | self_care | `RestAlone` |
| 5 | nap | self_care | `RestWithOthers` |
| 6 | socialize_initiate | social | `SocializeInitiate` |
| 7 | socialize_respond | social | `SocializeRespond` |
| 8 | exercise_intense | fitness | `ExerciseSolo` |
| 9 | exercise_light | fitness | `ExerciseSocial` |
| 10 | read_deep | learning | `DeepStudy` |
| 11 | read_casual | leisure | `CasualLearning` |
| 12 | clean | self_care | `HygieneQuick` |
| 13 | rest_alone | leisure | `RestAlone` |
| 14 | rest_with_others | social+leisure | `RestWithOthers` |
| 15 | explore | leisure | `BrowseArea` |
| 16 | move_up | move | `LeisureOutdoor` *(remapped)* |
| 17 | move_down | move | `ObserveCrowd` *(remapped)* |
| 18 | move_left | move | `LeisureOutdoor` *(remapped)* |
| 19 | move_right | move | `ObserveCrowd` *(remapped)* |

**Movement indices 16–19** have no semantic meaning in UE — the engine owns
pathing — so the policy bridge remaps them to outdoor/observe actions so the
Park/Observe zone has reachable producers. This is an engine-only remap;
training and Python eval still see the original movement labels.

## Observation schema (33-d v3 base)

The order is fixed — `UPCSPObservationComponent::BuildObservation` must match.

| Slice | Dim | Content |
|---|---:|---|
| position | 2 | row, col normalized to `[0, 1]` |
| time_of_day | 1 | hour / 23 |
| needs | 8 | hunger, sleep, social, leisure, hygiene, fitness, work, learning ∈ `[0, 1]` |
| affordance one-hot | 8 | one-hot of the nearest WORLD_OBJECT cell |
| social context | 3 | nearby_count / N, in_conversation, last_responder |
| routine signal | 2 | repeat_count / max_repeat, time-since-last-novel |
| other agents (4-agent base) | 9 | 3·(N−1) — row, col, last_action / (N_ACTIONS − 1) per other agent |

Total: `2 + 1 + 8 + 8 + 3 + 2 + 9 = 33`. The UE side runs the 4-agent base
schema regardless of agent count — the "other agents" slot is the only piece
that scales with N in research, and we hold it at the training format so the
ONNX model never sees an unfamiliar shape.

## Reward function (Python training only)

UE5 does not compute reward at runtime — it only logs `interaction_complete`
events and the per-interaction "reward" the BT applies via the need-satisfaction
delta. The training reward is:

```
r_total = r_need + r_persona_action + r_persona_style + r_social
```

- `r_need`: standard need-restoration delta
- `r_persona_action`: `+0.5` if action ID ∈ `persona.preferred_actions`
- `r_persona_style`: `+0.3 · cos(persona.bf_vec, ACTION_STYLE_PROFILE[a])`
- `r_social`: Big-Five-compatibility bonus from nearby agents

The `r_persona_style` term is what makes EatQuick vs EatSlow carry persona
signal — both restore hunger identically, but different personas get different
stylistic bonuses. The trained policy has internalized this; the UE5 reward log
is a downstream proxy, not a training signal.

## Personas (300)

`personas_300_v3.json` (canonical) holds 300 LLM-generated personas. The split
the UE5 runs use:

| Split | IDs | File | Used in UE |
|---|---|---|---|
| Train | 1..240 | `train_240_v3.json` | Default `persona_embeddings.json` |
| Held-out | 241..300 | `test_60_v3.json` | `run_zeroshot_eval.py prepare` swap |

The 1024-d Qwen3 embedding is projected to 64-d at export time
(`PersonaProjection`, L2-normalised). UE consumes the projected vectors only —
no LLM runs at game time.

## What UE5 must keep stable

If any of these changes in research, UE breaks silently:

1. **ONNX I/O contract** — `obs(1, 33)`, `persona_proj(1, 64)`, `logits(1, 20)`.
2. **Action ID ordering** — see table above.
3. **Need ordering** — `Hunger, Sleep, Social, Leisure, Hygiene, Fitness, Work, Learning`.
4. **Persona-embedding ordering** — slot N in `persona_embeddings.json` is persona ID N+1.

The export script encodes the first three in its constants block; the persona
JSON encodes the fourth.
