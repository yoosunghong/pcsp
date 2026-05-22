# EQS-Driven Affordance Congestion Handling

**Status:** Deferred from Phase 2. Current substitute: per-zone capacity +
`RecentFailureCount` backoff in `BTTask_PCSPDecision`.
**Owner:** AI / Gameplay Programmer
**Target scale:** 32–64 agents competing for a 9-category affordance set

## Problem

The hybrid stack uses `UPCSPAffordanceSubsystem::FindBestZone` to map a semantic
action (`FocusedWork`, `EatQuick`, …) to a concrete zone instance. The current
selector is deterministic per category and only knows about hard capacity:

```
FindBestZone(category) :=
    argmin over zones where (free_interaction_points > 0 AND category matches)
        of (distance_to_agent)
```

This produces two pathologies at scale:

1. **Thundering herd on the nearest zone.** With 64 agents and a single
   one-zone category (e.g. Office at 32-agent baseline), 8–16 agents arrive
   in the same decision tick, all reserve the same closest instance, and
   most lose the reservation race. The 2026-05-17 32-agent run logged
   91.7% of `move_failed` as `FindBestZone:AllOverCapacity` on Rest zones.
2. **Reservation hot-spotting.** Once a zone fills, agents iterate to the
   second-nearest. With identical heuristic ordering this herds them again.
   The current mitigation is `RecentFailureCount` backoff on the decision
   throttle, which delays retries but does not change the selection target.

## Goal

Replace the deterministic nearest-with-capacity rule with an EQS-scored
selector that takes occupancy pressure, reservation contention, and a small
randomness term into account, *without* changing the BT contract
(`UBTTask_MoveToAffordance` still consumes an `AffordanceZone` Blackboard
key). Target: drop `FindBestZone:AllOverCapacity` from the 64-agent dominant
failure mode (currently 65% pre-mitigation, 42 events post-capacity-fix) to
below 10 events per 10-minute session at 64 agents.

## Design

### Query

`EQS_AffordanceForCategory` (run from `BTTask_MoveToAffordance` before the
existing `FindBestZone` call):

| Generator | Context |
|---|---|
| `Actors of Class` filtered by `APCSPAffordanceZone` and tag match | Querier = agent pawn |

| Test | Score | Weight | Notes |
|---|---|---|---|
| `Distance 2D` | Inverse linear, clamp $[200, 4000]$ cm | 0.5 | Same shape as current heuristic |
| `PathLength` to nearest InteractionPoint | Inverse, fail-on-no-path | 0.25 | Catches navmesh holes the straight-line check misses |
| `OccupancyRatio` (custom test) | Linear, $1 - \text{used}/\text{capacity}$ | 0.6 | Drives selector *away* from saturated zones |
| `ReservationPressure` (custom test) | Linear, $1 - \text{pending}/\text{capacity}$ | 0.3 | Counts in-flight reservations, not just current occupancy |
| `RecentFailureBias` (custom test) | Discrete bonus if the zone is not in the agent's `RecentlyFailedZones` ring | 0.15 | Per-agent state in Blackboard |
| `Score Randomness` | Uniform $\in [0.85, 1.0]$ multiplier | — | Breaks ties without losing the rest of the ordering |

Final score = weighted sum; rejected items: no path, capacity == 0,
category tag mismatch.

### C++ surface

Add two `UEnvQueryTest_*` subclasses:

```cpp
UCLASS()
class UEnvQueryTest_PCSPOccupancy : public UEnvQueryTest {
    // reads UPCSPAffordanceSubsystem::GetZoneOccupancy(Zone)
};

UCLASS()
class UEnvQueryTest_PCSPReservationPressure : public UEnvQueryTest {
    // reads UPCSPAffordanceSubsystem::GetZoneReservationPressure(Zone)
};
```

Extend `UPCSPAffordanceSubsystem` with two cheap O(1) accessors backed by the
existing reservation map. No new state — purely read views over
`ZoneState::ReservedInteractionPoints` and `ZoneState::ActiveOccupants`.

### BT integration

`UBTTask_MoveToAffordance` runs the EQS first. On query failure (no item
returned within budget), it falls back to the existing `FindBestZone`
path, preserving today's behavior. On success, the chosen
`AffordanceZone` is written to Blackboard and the rest of the task is
untouched. **No change to the policy or the BT graph itself** — the
contract stays "policy chooses category, EQS chooses instance."

## Work Breakdown

1. `UPCSPAffordanceSubsystem`: add `GetZoneOccupancy`, `GetZoneReservationPressure`, and a `GetCategoryZones` accessor that returns a filtered `TArrayView`. ~1 day.
2. Two `UEnvQueryTest` subclasses + `UEnvQueryContext_Querier` wiring. ~1 day.
3. `EQS_AffordanceForCategory.uasset` authored in editor (test list, weights from §Design). ~0.5 day.
4. `UBTTask_MoveToAffordance::ExecuteTask` runs EQS first, fallback to `FindBestZone` on empty/timeout. ~0.5 day.
5. Add `RecentlyFailedZones` ring buffer to Blackboard, populated on `move_failed` events. ~0.5 day.
6. **Validation:** rerun the 32-agent and 64-agent stress sessions; compare `FindBestZone:AllOverCapacity` event counts and `interactions_per_agent` against the 2026-05-17 baselines. ~1 day.

Estimated total: **4–5 engineering days** including measurement.

## Validation criteria

| Metric | Baseline (64 agents, 2026-05-17 Run 3) | Target |
|---|---|---|
| `FindBestZone:AllOverCapacity` events / 8 min | 42 | ≤ 10 |
| `interactions_per_agent` over the same window | 38.1 | ≥ 38 (no regression) |
| Per-category coverage | 9 of 10 | 9 of 10 (no regression) |
| Mean inference budget per decision | <1 ms (ONNX dominates) | <1.5 ms incl. EQS |

## Risk notes

- **EQS cost at 64 agents.** Querying 10 zones with 5 tests at 0.5 s throttle = ~1.3k tests/sec. Well inside budget, but each `PathLength` is a navmesh query; cap the candidate set with `Distance` pre-filter at 4000 cm.
- **Reservation pressure feedback loop.** A zone with high pressure becomes less attractive, releasing pressure, becoming attractive again. The `Score Randomness` term and the `RecentlyFailedZones` ring are the dampers — if oscillation appears in logs, raise the ring size from 2 to 4.
- **EQS asset churn.** EQS assets are notoriously merge-unfriendly. Keep the query in one `.uasset` and avoid splitting tests across multiple queries.

## Cross-references

- `BTTask_PCSPDecision::ApplyDecisionThrottle` — current backoff (decision-side).
- `BTTask_MoveToAffordance::TryBeginMove` — where the new EQS call attaches.
- `UPCSPAffordanceSubsystem::FindBestZone` — fallback path; do not delete.
- `docs/affordance-system.md` — three-layer zone architecture this builds on.
