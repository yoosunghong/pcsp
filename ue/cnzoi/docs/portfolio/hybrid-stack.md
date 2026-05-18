# Hybrid Policy ↔ Behavior Tree Integration Contract

**Status:** Live since Phase 2. Stable as of 2026-05-18.
**Owner:** AI Programmer

## Problem

A trained PPO policy chooses **what the NPC should do** (semantic action:
`EatQuick`, `FocusedWork`, `SocializeInitiate`, …). It does **not** know:

- Which Kitchen actor in the level is closest, free, or reachable.
- How to reserve an InteractionPoint inside that Kitchen without race
  conditions against 63 other agents.
- How to retry when the navmesh path partially fails 80 cm short of the
  goal.
- How to abandon a long interaction when an urgent need (Hygiene at 0.95)
  becomes more important than finishing the current one.

These are engine concerns. Mixing them into a learned policy means the
policy has to relearn level geometry every time the level changes — and a
production team cannot ship that.

The hybrid stack splits the work: **policy chooses intent, BT executes
intent.** This document is the contract that lets a research-trained ONNX
policy drop into a UE5 project without retraining when the world changes.

## Layered architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Trained policy (ONNX, frozen at deploy)                           │
│  obs[1,33] + persona_proj[1,64] -> logits[1,20]                    │
└────────────────────────────────────┬───────────────────────────────┘
                                     │ argmax + lookup
                                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  EPCSPActionType enum (20 actions)                                 │
│  EatQuick / EatSlow / FocusedWork / PlanningWork / DeepStudy / ... │
└────────────────────────────────────┬───────────────────────────────┘
                                     │ ActionToCategory()
                                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  EPCSPAffordanceCategory (9 active)                                │
│  Eat / Rest / Work / Study / Exercise / Hygiene / Social /         │
│  Observe / Shop  (Leisure folded into Observe)                     │
└────────────────────────────────────┬───────────────────────────────┘
                                     │ FindBestZone(category)
                                     ▼
┌────────────────────────────────────────────────────────────────────┐
│  APCSPAffordanceZone instance + APCSPInteractionPoint reservation  │
└────────────────────────────────────┬───────────────────────────────┘
                                     │ AIController MoveTo
                                     ▼
                              NavMesh + path follow
```

Each layer has one job and is replaceable. Swap the ONNX model: layer 1
changes. Re-tag a zone: layer 4 changes. The interfaces between layers
are stable.

## Blackboard contract

Five keys are the entire interface between policy and BT:

| Key | Type | Writer | Reader |
|---|---|---|---|
| `DesiredActionType` | `EPCSPActionType` | `BTTask_PCSPDecision` | `BTTask_MoveToAffordance`, `BTTask_PerformInteraction` |
| `DesiredCategory` | `EPCSPAffordanceCategory` | `BTTask_PCSPDecision` (via `ActionToCategory`) | `BTTask_MoveToAffordance` |
| `UrgencyScore` | float | `BTTask_PCSPDecision` (from needs urgency) | BT decorator (Observer Aborts = Both) |
| `AffordanceZone` | `APCSPAffordanceZone*` | `BTTask_MoveToAffordance` after `FindBestZone` | `BTTask_PerformInteraction` |
| `bAffordanceReserved` | bool | `BTTask_MoveToAffordance` after reservation | `BTTask_PerformInteraction`, abort path |

No other keys cross the boundary. The policy never reads
`AffordanceZone`; the BT never reads `logits`. This separation is what
makes ablations possible — flipping `pcsp.PolicyMode` to `BTOnly` swaps
the policy for a needs heuristic without touching the BT.

## The decision throttle

A learned policy at 60 Hz produces 60 decisions per agent per second.
Most are identical (the situation hasn't changed in 16 ms). Two
mitigations:

1. **`MinDecisionInterval`** (default 0.5 s) caches the last action and
   short-circuits the ONNX call. ~120× reduction in inference traffic.
2. **`RecentFailureCount`** multiplies the effective interval by
   `(1 + RecentFailureCount)`. Three consecutive `move_failed` events
   stretch the interval to 2 s, giving congested zones time to clear.
3. **Urgency bypass.** If `UrgencyScore ≥ 0.85`, the throttle is
   ignored — needs are critical and the BT should re-decide every tick.

This is in `BTTask_PCSPDecision::ApplyDecisionThrottle`, not in the
policy. The reason: the policy is the same checkpoint as the research
artifact; the throttle is engine-specific scaling work. Keeping them
separate means research can rerun ablations without re-validating engine
performance.

## Reservation protocol

`APCSPInteractionPoint` is the actual capacity-bearing entity, not the
zone:

```
Agent A: zone->ReserveInteractionPoint(self)  -> Point_03
Agent B: zone->ReserveInteractionPoint(self)  -> Point_04
Agent C: zone->ReserveInteractionPoint(self)  -> nullptr (zone full)
         BTTask_MoveToAffordance fails with
         "zone_no_free_interaction_point"
```

Reservation is **per-tick atomic** at the subsystem level. Two agents
that decide on the same tick still serialize through the subsystem's
`FScopeLock`. The race condition that actually appears in logs is
*post-reservation*: agent reserves, starts moving, another agent
arrives faster, the first agent's interaction is preempted on
re-decision. The failure tag for that is
`interaction_point_reserve_race_lost` and the BT just re-runs the
decision branch.

## Emergency branch

Top-level BT structure:

```
Selector
├── [Observer: UrgencyScore > 0.85, Both aborts]
│       └── Emergency sub-tree (force re-decide, ignore throttle)
└── Main loop
    ├── BTTask_PCSPDecision (throttled)
    ├── BTTask_MoveToAffordance
    └── BTTask_PerformInteraction
```

`Observer Aborts = Both` is what makes a high-urgency Hygiene need
abort an in-progress `FocusedWork` interaction *immediately*, even
inside the `PerformInteraction::WaitInteractionDuration` sleep. Without
it, agents stay in a 30-second activity while their bladder need crosses
1.0. This was the single most impactful BT decoration in Phase 2.

## Ablation harness in-engine

`pcsp.PolicyMode` CVar at runtime (no rebuild):

| Value | Mode | Behavior |
|---|---|---|
| 0 | `HybridPCSP` | ONNX policy + persona embedding |
| 1 | `BTOnly` | Needs heuristic only, ONNX skipped |
| 2 | `HybridNoPersona` | ONNX policy + zero persona vector |

Combined with the ONNX-swap script
(`research/scripts/swap_ue5_onnx.py {full,no_consist}`), this yields
five settings without touching code:

| Setting | CVar | ONNX file |
|---|---|---|
| Full PCSP | 0 | `pcsp_actor_full.onnx` |
| NoConsist | 0 | `pcsp_actor_no_consist.onnx` |
| NoPersona (inference) | 2 | `pcsp_actor_full.onnx` |
| BT-only | 1 | — |
| RL-only (training-time) | — | research-side only |

The 2026-05-18 ablation table in `PLAN.md` Phase 4 is the result of
running this matrix; the engine never had to be rebuilt between
conditions.

## What this design gets right

- **The policy is portable.** Same ONNX runs in a Python eval loop and
  in UE5. The export script's I/O contract (obs[1,33], persona_proj[1,64],
  logits[1,20]) is the entire ABI.
- **The level is portable.** Adding a second Office zone or retagging
  Park as Observe requires zero changes to the policy. The 32→64
  agent scale-up was a capacity edit on existing zone assets, not new
  C++.
- **Ablations cost nothing.** A new ablation is a new ONNX file plus a
  CVar flip plus a paired PIE session. The 2026-05-18 NoConsist
  experiment was 25 minutes of wall-clock from "checkpoints exist" to
  "compare.json written."

## Open issues

- The Blackboard key `DesiredCategory` is derived from `DesiredActionType`
  in two places (`BTTask_PCSPDecision` and `BTTask_MoveToAffordance`).
  Centralize in `UPCSPPolicySubsystem::ActionToCategory` and have both
  call it.
- `Leisure` is an unreachable enum value (folded into Observe during
  Phase 2 remap). Either delete the enum case or wire a `Leisure` zone.
- `active_ablation.txt` is filesystem-side; the engine should read it
  at `BeginPlay` and emit it on the `session_start` JSONL row.

## Cross-references

- `Source/cnzoi/PCSP/Public/PCSPTypes.h` — `EPCSPActionType`, `EPCSPAffordanceCategory`, `EPCSPPolicyMode`.
- `Source/cnzoi/PCSP/Private/BT/BTTask_PCSPDecision.cpp` — decision throttle, urgency bypass.
- `Source/cnzoi/PCSP/Private/BT/BTTask_MoveToAffordance.cpp` — `FindBestZone` integration, reservation, failure-reason labelling.
- `Source/cnzoi/PCSP/Private/Inference/PCSPPolicySubsystem.cpp` — CVar plumbing, ONNX loading.
- `docs/phase0/bt-blackboard-policy-contract.md` — original spec this implements.
