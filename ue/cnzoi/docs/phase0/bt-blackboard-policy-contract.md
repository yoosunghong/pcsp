# Phase 0 — BT ↔ Blackboard ↔ Policy Interface Contract

This is the wire format between the three actors in the hybrid stack:

1. **Policy** (`UPCSPPolicySubsystem`) — ONNX inference, returns one
   `EPCSPActionType` per call (plus 20 logits).
2. **Blackboard** (`BB_PCSPAgent`) — typed key-value store; the only mutable
   shared state between BT tasks.
3. **Behavior Tree** (`BT_PCSPAgent`) — schedules tasks that read and write
   blackboard keys; executes movement, reservation, and interaction.

The contract here is the **canonical** version. If `PCSPTypes.h`,
`BB_PCSPAgent`, or any BT task disagrees with this doc, that's a bug — open an
issue.

---

## Blackboard keys (`PCSPBlackboard::` in `PCSPTypes.h`)

| Key | Type | Writer(s) | Readers | Lifecycle |
|---|---|---|---|---|
| `DesiredActionType` | Enum `EPCSPActionType` (uint8) | `BTTask_PCSPDecision` | `BTTask_MoveToAffordance`, `BTTask_PerformInteraction`, Emergency Decorator | Set per decision; persists until next decision |
| `DesiredAffordanceTag` | `FGameplayTag` | `BTTask_MoveToAffordance` (optional preference) | `UPCSPAffordanceSubsystem::FindBestZone` | Optional; if Invalid, FindBestZone picks by category alone |
| `TargetActor` | `AActor*` | `BTTask_MoveToAffordance` | `BTTask_PerformInteraction` | Selected zone actor; cleared on completion |
| `TargetLocation` | `FVector` | `BTTask_MoveToAffordance` | UE `MoveTo` | Interaction-point world location |
| `InteractionStyle` | uint8 | `BTTask_PCSPDecision` (Phase 2+) | `BTTask_PerformInteraction` | Distinguishes EatQuick vs EatSlow inside a single zone category |
| `UrgencyScore` | float `[0, 1]` | `BTTask_PCSPDecision` | Emergency BB Decorator | `1 − GetNeed(MostUrgent)` |
| `RecentFailureCount` | int32 | `BTTask_MoveToAffordance` (++ on failure, reset on success) | `BTTask_PCSPDecision` (throttle backoff) | Drives the decision-throttle's exponential backoff |
| `SocialTargetActor` | `AActor*` | TBD (Phase 2 social branch) | TBD | Reserved for future social-initiate routing |
| `CurrentZoneTag` | `FGameplayTag` | `BTTask_PerformInteraction` (set on enter) | Future routine/cooldown logic | Where the agent currently is |
| `bAffordanceReserved` | bool | `BTTask_MoveToAffordance` (true on reserve), `BTTask_PerformInteraction` (false on release) | Emergency Decorator (allow interrupt) | Gates whether the interaction can start |

Authoring rule for `BB_PCSPAgent`: every name above must exist, with the type
shown, **spelled exactly as in `PCSPBlackboard::`**. A typo silently drops the
write (UE's `GetValueAsEnum` returns 0 for missing keys, which is
`EatQuick` — agents will all eat constantly).

---

## Policy interface

```cpp
// UPCSPPolicySubsystem.h
EPCSPActionType RunInference(const TArray<float>& Observation, int32 PersonaId);
EPCSPActionType RunInferenceWithLogits(const TArray<float>& Observation,
                                       int32 PersonaId,
                                       TArray<float>& OutLogits);
```

**Input shape (frozen):**
- `Observation` — exactly `ObsDim = 33` floats, ordering documented in
  [`research-environment-summary.md`](research-environment-summary.md).
  Larger arrays are truncated; smaller ones are zero-padded (`RunInference`
  does both, but treat that as a debug aid — Phase 4 agents always send 33).
- `PersonaId` — 1-based index into `persona_embeddings.json`. ID 1 = slot 0.

**Output:**
- Argmax action selected from the 20-way logit head, then translated through
  the V3→UE remap table (`PCSPPolicySubsystem.cpp:182`).
- `RunInferenceWithLogits` additionally returns the raw 20-float logit vector
  for trajectory-log policy KL.

**Mode switching (Phase 4 ablations):**
`pcsp.PolicyMode` CVar — 0 = HybridPCSP (default), 1 = BTOnly
(`NeedsHeuristic`, no ONNX), 2 = HybridNoPersona (ONNX with zeroed persona).
Mode is read on every inference, so it can be flipped mid-PIE; the active mode
is written to the trajectory `session_start` row as `policy_mode`.

---

## Behavior Tree structure

```
Root: Selector (with priority — first child to succeed wins)
├── 1. Emergency Branch       (BB Decorator: UrgencyScore >= 0.85, Observer Aborts = Both)
│      └── BTTask_PCSPDecision (forced re-evaluation; throttle bypassed)
│          └── BTTask_MoveToAffordance
│              └── BTTask_PerformInteraction
│
├── 2. Persona Branch         (default path)
│      └── BTTask_PCSPDecision
│          └── BTTask_MoveToAffordance
│              └── BTTask_PerformInteraction
│
└── 3. Idle Branch            (fallback when both above return Failed)
       └── Wait (1 s)
```

**Why three branches and not one:** the Emergency Decorator with
`Observer Aborts = Both` lets a sudden need-spike yank the agent out of a
current interaction. The Idle branch is a hard floor so an agent that can't
satisfy any need (e.g., all zones over capacity) still ticks instead of
returning Failed to the root forever.

---

## Per-task contract

### `BTTask_PCSPDecision`

**Reads:**
- `NeedsComponent::GetMostUrgentNeed()` (urgency calc + Emergency bypass)
- `ObservationComponent::BuildObservation()` (full 33-d vector)
- `PersonaComponent::GetPersonaId()` (1-based ID)
- BB `RecentFailureCount` (throttle backoff multiplier)

**Writes:**
- BB `DesiredActionType`
- BB `UrgencyScore`
- TrajectoryLog `decision` event (with logits if not BTOnly)

**Returns:** `Succeeded` on inference success, `Failed` if policy subsystem
is not ready and mode is not BTOnly.

**Throttle:** new inference at most every `MinDecisionInterval × (1 + RecentFailureCount)`
seconds (capped at ×9). Throttled calls reuse the last action without re-running ONNX.
UrgencyScore ≥ 0.85 bypasses the throttle.

### `BTTask_MoveToAffordance`

**Reads:** BB `DesiredActionType`, optional `DesiredAffordanceTag`.

**Calls:** `UPCSPAffordanceSubsystem::FindBestZone(Category, bRequireCapacity=true)`
with `FPCSPZoneSelectionDebug` to capture the rejection reason on failure.

**Writes on success:** BB `TargetActor`, `TargetLocation`, `bAffordanceReserved = true`.

**Writes on failure:** BB `RecentFailureCount += 1`. Logs `move_failed` with
`failure_reason ∈ {FindBestZone:<reason>, zone_no_free_interaction_point,
interaction_point_reserve_race_lost, pathfinding_request_failed,
path_follow_idle_short:dist=<cm>}`, `intended_zone`, `distance_to_target`.

### `BTTask_PerformInteraction`

**Reads:** BB `TargetActor`, `DesiredActionType`, `InteractionStyle`.

**Writes:** BB `CurrentZoneTag`, `bAffordanceReserved = false` on completion.

**Calls:** `NeedsComponent::AdjustNeed` with the per-action restoration delta,
TrajectoryLog `interaction_complete` (or `interaction_failed` if reservation
was stolen).

**Returns:** `Succeeded` after `InteractionDuration` seconds; `Failed` on
reservation loss.

---

## Where this contract is enforced

- **Type safety** — `PCSPBlackboard::` namespace centralizes key names; all
  task code uses these constants, never string literals.
- **Schema versioning** — `EPCSPActionType`, `EPCSPAffordanceCategory`, and
  the obs ordering are mirrored in `research/scripts/export_pcsp_onnx.py` and
  `research/scripts/analyze_ue_session.py`. Changing one without the other
  silently corrupts inference or analysis.
- **Session metadata** — every PIE run's `agent_p*.jsonl` opens with a
  `session_start` row carrying `policy_mode`, so downstream comparisons can
  trust the assigned mode without out-of-band tracking.
