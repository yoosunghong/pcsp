# Affordance System — Three-Layer Architecture

A common point of confusion is that `DT_PCSPAffordanceTags` looks like it defines the
action space. It does not. There are three distinct layers with different purposes.

---

## Overview

```
EPCSPActionType (20)               EPCSPAffordanceCategory (11 enum, 9 active)  DT_PCSPAffordanceTags
────────────────────────           ────────────────────────────      ──────────────────────────
Policy output / action space       Coarse zone-routing enum          GameplayTag registration
(what the agent decides)           (bridges action → zone type)      (physical zone identifiers)
Defined in: PCSPTypes.h            Defined in: PCSPTypes.h           Asset: Content/PCSP/Data/
```

---

## Layer 1 — Action Space (`EPCSPActionType`, 20 values)

This is the **policy output** — the 20 semantic actions that PCSP selects from.
Defined in `Source/cnzoi/PCSP/PCSPTypes.h`.

```cpp
enum class EPCSPActionType : uint8
{
    EatQuick, EatSlow,
    RestAlone, RestWithOthers,
    FocusedWork, PlanningWork,
    DeepStudy, CasualLearning,
    ExerciseSolo, ExerciseSocial,
    HygieneQuick, HygieneCareful,
    SocializeInitiate, SocializeRespond,
    LeisureIndoor, LeisureOutdoor,
    ShopEssentials, BrowseArea,
    ObserveCrowd, IdleReflect
};
```

The Behavior Tree reads this value from the Blackboard key `DesiredActionType`
(written by `UBTTask_PCSPDecision`) and uses it to determine **where to go next**.

---

## Layer 2 — Affordance Category (`EPCSPAffordanceCategory`, 11 enum values, 9 active)

This is the **routing enum** that maps each action to a zone type.
It is not the action space; it is a lookup key.

| `EPCSPAffordanceCategory` | Actions that map to it |
|---|---|
| `Eat` | `EatQuick`, `EatSlow` |
| `Rest` | `RestAlone`, `RestWithOthers` |
| `Work` | `FocusedWork`, `PlanningWork` |
| `Study` | `DeepStudy`, `CasualLearning` |
| `Exercise` | `ExerciseSolo`, `ExerciseSocial` |
| `Hygiene` | `HygieneQuick`, `HygieneCareful` |
| `Social` | `SocializeInitiate`, `SocializeRespond` |
| `Shop` | `ShopEssentials`, `BrowseArea` |
| `Observe` | `LeisureIndoor`, `LeisureOutdoor`, `ObserveCrowd` |
| `Idle` | `IdleReflect` |

Multiple actions collapse to one category because they share the same physical
destination type. The **difference between them** (e.g., `EatQuick` vs `EatSlow`) is
expressed via the `InteractionStyle` Blackboard key and resolved inside
`UBTTask_PerformInteraction` (Phase 2).

---

## Layer 3 — Gameplay Tags (`DT_PCSPAffordanceTags`, 9+ active rows)

These are **physical zone identifiers** — `FGameplayTag` values assigned to
`APCSPAffordanceZone` actors placed in the level. They are registered with UE's
`GameplayTagManager` via the data table so they can be used as typed
`FGameplayTag` values in C++ and Blueprints without string typos.

```
PCSP.Zone.Eat       ← tag assigned to Kitchen / Dining zone actors
PCSP.Zone.Rest      ← tag assigned to Bedroom / Rest zone actors
PCSP.Zone.Work      ← ...
```

A single category can have **multiple sub-tags** for finer resolution:

```
PCSP.Zone.Eat                   ← root tag, matches any Eat zone
PCSP.Zone.Eat.Kitchen           ← specific indoor kitchen
PCSP.Zone.Eat.CafeOutdoor       ← outdoor cafe, preferred for LeisureOutdoor overlap
```

`UPCSPPolicySubsystem::ActionToCategory` owns the action-to-category mapping.
`UPCSPAffordanceSubsystem::FindBestZone` scores candidate zones by distance and
tag match. A preferred sub-tag (written to `DesiredAffordanceTag`) scores +5 000 UU
over distance, so the agent can still be routed to the nearest available zone if the
preferred one is at capacity.

---

## Runtime Data Flow

```
1. UBTTask_PCSPDecision
   ├── reads: NeedsComponent (most urgent need)
   │          ObservationComponent (full obs vector)   ← Phase 3: PCSP policy inference
   └── writes BB: DesiredActionType = EatQuick
                  UrgencyScore = 0.72

2. BT Subtree (Phase 2)
   ├── resolves: EPCSPActionType::EatQuick → EPCSPAffordanceCategory::Eat
   ├── calls:    UPCSPAffordanceSubsystem::FindBestZone(Category=Eat, bRequireCapacity=true)
   └── writes BB: TargetActor = <nearest free APCSPAffordanceZone>
                  TargetLocation = <interaction point location>
                  bAffordanceReserved = false

3. UBTTask_MoveToAffordance (Phase 2)
   ├── MoveTo TargetLocation via NavMesh
   └── on arrival: APCSPInteractionPoint::TryReserve(Agent)
                   writes BB: bAffordanceReserved = true

4. UBTTask_PerformInteraction (Phase 2)
   ├── wait InteractionDuration seconds
   ├── apply need restoration (NeedsComponent::AdjustNeed)
   ├── record: TrajectoryLogComponent::RecordEntry(Action, Tag, Reward)
   └── APCSPInteractionPoint::Release(Agent)
```

---

## Why Not Make the Tags Match the Actions Directly?

Having 20 tags (one per action) was considered and rejected for three reasons:

1. **Zone placement cost**: You would need separate zone meshes and interaction
   points for `EatQuick` and `EatSlow` even though they share the same kitchen.
   One `PCSP.Zone.Eat` zone serves both, with `InteractionStyle` controlling
   behaviour inside it.

2. **Congestion resolution**: The subsystem picks the *nearest available* zone of
   the right category. If zones were per-action, an `EatQuick` agent could be
   stuck while an identical physical seat sits empty because it is tagged `EatSlow`.

3. **Policy expressiveness**: The 20-action vocabulary is designed to give the
   *policy* room to express persona-conditioned preferences (an introverted persona
   chooses `RestAlone` over `RestWithOthers`). That distinction is encoded in the
   action, not in the affordance target — the physical bed is the same either way.

---

## Summary Table

| Layer | Count | Role | Where |
|---|---|---|---|
| `EPCSPActionType` | **20** | Policy action space | `PCSPTypes.h` |
| `EPCSPAffordanceCategory` | **11 enum / 9 active** | Zone routing bucket | `PCSPTypes.h` |
| `DT_PCSPAffordanceTags` rows | **9 active minimum** | GameplayTag registration | `Content/PCSP/Data/` |
| `APCSPAffordanceZone` actors | **10–30+** | Physical locations in level | Map actors |
| `APCSPInteractionPoint` actors | **40–80** | Specific seats / stations | Children of zones |
