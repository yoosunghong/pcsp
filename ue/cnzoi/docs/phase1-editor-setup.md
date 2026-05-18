# Phase 1 — UE5 Editor Setup Guide

This guide covers all editor-side work required to complete Phase 1 of the PCSP UE5
implementation. The C++ scaffold (`Source/cnzoi/PCSP/`) must compile cleanly before
starting here. All editor-created assets should live under `Content/PCSP/`.

---

## 0. Prerequisites — Compile the C++ Scaffold

1. Right-click `cnzoi.uproject` → **Generate Visual Studio project files**.
2. Open `cnzoi.sln` in VS 2022; build target **cnzoi (Development Editor)**.
3. Confirm the five PCSP sub-folders in `Source/cnzoi/PCSP/` compile without errors.
4. Launch the editor from the `.uproject` file.

---

## 1. Project Settings

Open **Edit → Project Settings** and apply the following:

### Maps & Modes

| Setting | Value |
|---|---|
| Default GameMode | `APCSPSimGameMode` (or `BP_PCSPSimGameMode` — see §7) |
| Editor Startup Map | `Map_PCSPDistrict_M` (set after §3) |

### Navigation System

| Setting | Value |
|---|---|
| Agent Radius | `34` |
| Agent Height | `144` |
| Max Climb Height | `35` |
| Max Slope Angle | `44` |
| Default Navigation Filter Class | `NavigationQueryFilter` |

### Gameplay Tags

- Under **Gameplay Tag Table List** → press **+** → select `DT_PCSPAffordanceTags`
  (create this asset first in §2).

---

## 2. Gameplay Tag Table

**Location:** `Content/PCSP/Data/DT_PCSPAffordanceTags`

1. Content Browser → `Content/PCSP/Data/` → right-click →
   **Miscellaneous → Data Table**.
2. Pick row struct **GameplayTagTableRow**.
3. Name it `DT_PCSPAffordanceTags`.
4. Add one row per tag below. The **Tag** column is the only required field.

| Tag | DevComment |
|---|---|
| `PCSP.Zone.Eat` | Kitchen / Dining area |
| `PCSP.Zone.Rest` | Bedroom / Rest lounge |
| `PCSP.Zone.Work` | Office / Desk area |
| `PCSP.Zone.Study` | Study room / Library |
| `PCSP.Zone.Exercise` | Gym / Outdoor track |
| `PCSP.Zone.Hygiene` | Bathroom |
| `PCSP.Zone.Social` | Lounge / Social hub |
| `PCSP.Zone.Leisure` | Indoor leisure |
| `PCSP.Zone.Shop` | Shop / Market |
| `PCSP.Zone.Observe` | Park / Scenic viewpoint |
| `PCSP.Zone.Idle` | Any open area |

5. Back in Project Settings → **Gameplay Tags → Gameplay Tag Table List → +** →
   select `DT_PCSPAffordanceTags`.

> These tags are **zone identifiers**, not the action space.
> See [affordance-system.md](affordance-system.md) for the full three-layer breakdown.

---

## 3. Create the Medium District Map

**File → New Level → Empty Level**
Save as: `Content/PCSP/Maps/Map_PCSPDistrict_M.umap`

### 3a. Geometry — Block-out Layout

Footprint: approximately **6 000 × 6 000 Unreal Units** (≈ 60 m × 60 m).
Use **Modeling Tools (Shift+5)** or BSP cubes for the block-out.

```
┌─────────────────────────────────────────┐
│  Park / Observe  │   Shop              │
│  (2000 × 1500)   │   (1500 × 1000)     │
├──────────┬───────┴──────┬──────────────┤
│  Gym     │  Social Hub  │  Lounge      │
│ (1200×1200)│ (1500×1500) │ (1200×1200) │
├──────────┴───────┬──────┴──────────────┤
│  Office / Work   │  Study / Library    │
│  (2000 × 1200)   │  (2000 × 1200)      │
├──────────────────┴─────────────────────┤
│  Kitchen / Dining │ Bedroom / Hygiene  │
│  (2000 × 1200)    │ (2500 × 1200)      │
└────────────────────────────────────────┘
```

Add a floor plane (scaled flat `SM_Cube`) covering the whole district and simple
wall meshes for room boundaries.

### 3b. Lighting

Place: **Directional Light + Sky Atmosphere + Sky Light (Real-Time Capture)**.
This is sufficient for Phase 1 development.

### 3c. NavMesh

1. **Place Actors panel (Shift+1)** → search "Nav Mesh Bounds Volume" → drag into level.
2. In **Details**, scale to cover the entire playable floor:
   - Scale X ≈ `62`, Scale Y ≈ `62`, Scale Z ≈ `5`
   - Center on district origin.
3. Press **P** to visualize (green = navigable).
4. **Build → Build Paths** to bake. Fix any holes by expanding the volume.

**RecastNavMesh-Default actor settings** (auto-spawned, select it in Outliner):

| Property | Value |
|---|---|
| Cell Size | `19.0` |
| Cell Height | `10.0` |
| Agent Radius | `34.0` |
| Agent Max Step Height | `35.0` |
| Agent Max Slope | `44.0` |

---

## 4. Place Affordance Zones

For each zone block: **Place Actors → search `PCSPAffordanceZone`** → drag into level,
position over the matching geometry, then configure in **Details**.

| Zone | ZoneTag | Category | Capacity | Bounds Extent (X, Y, Z) |
|---|---|---|---|---|
| Kitchen / Dining | `PCSP.Zone.Eat` | `Eat` | `4` | `900, 550, 200` |
| Bedroom / Rest | `PCSP.Zone.Rest` | `Rest` | `4` | `1100, 550, 200` |
| Office | `PCSP.Zone.Work` | `Work` | `6` | `900, 550, 200` |
| Study / Library | `PCSP.Zone.Study` | `Study` | `4` | `900, 550, 200` |
| Gym | `PCSP.Zone.Exercise` | `Exercise` | `4` | `550, 550, 200` |
| Bathroom | `PCSP.Zone.Hygiene` | `Hygiene` | `2` | `300, 300, 200` |
| Social Hub | `PCSP.Zone.Social` | `Social` | `8` | `650, 650, 200` |
| Lounge | `PCSP.Zone.Leisure` | `Leisure` | `6` | `550, 550, 200` |
| Shop | `PCSP.Zone.Shop` | `Shop` | `4` | `650, 450, 200` |
| Park | `PCSP.Zone.Observe` | `Observe` | `16` | `950, 650, 200` |

### 4a. Interaction Points

For each zone, spawn `APCSPInteractionPoint` actors **inside** the zone bounds:

1. **Place Actors → `PCSPInteractionPoint`** → drag into zone.
2. Set **AffordanceTag** (same as parent zone), **Category**, and
   **InteractionDuration** (seconds):

   | Zone | Duration | Suggested count |
   |---|---|---|
   | Eat | `5.0` | 4 |
   | Rest | `6.0` | 4 |
   | Work | `8.0` | 6 |
   | Study | `8.0` | 4 |
   | Exercise | `6.0` | 4 |
   | Hygiene | `3.0` | 2 |
   | Social | `10.0` | 6 |
   | Leisure | `5.0` | 4 |
   | Shop | `4.0` | 3 |
   | Observe | `4.0` | 8 |

3. Select the **zone** actor → `InteractionPoints` array → add a reference to each
   point placed inside it.

---

## 5. Blackboard Asset — `BB_PCSPAgent`

**Location:** `Content/PCSP/AI/BB_PCSPAgent`

1. Content Browser → `Content/PCSP/AI/` → right-click →
   **Artificial Intelligence → Blackboard**.
2. Name it `BB_PCSPAgent`.
3. Add the following keys. Names must match `PCSPBlackboard::` constants in
   `Source/cnzoi/PCSP/PCSPTypes.h` exactly.

| Key Name | Type | Default / Notes |
|---|---|---|
| `DesiredActionType` | **Enum** | Enum class: `EPCSPActionType` |
| `DesiredAffordanceTag` | **Name** | Tag string written by BT tasks |
| `TargetActor` | **Object** | Base class: `Actor` |
| `TargetLocation` | **Vector** | |
| `InteractionStyle` | **Int** | `0` = default |
| `UrgencyScore` | **Float** | |
| `RecentFailureCount` | **Int** | Default: `0` |
| `SocialTargetActor` | **Object** | Base class: `Actor` |
| `CurrentZoneTag` | **Name** | |
| `bAffordanceReserved` | **Bool** | Default: `false` |

> If `EPCSPActionType` does not appear in the Enum dropdown, rebuild the project first.

---

## 6. Behavior Tree — `BT_PCSPAgent`

**Location:** `Content/PCSP/AI/BT_PCSPAgent`

1. Content Browser → `Content/PCSP/AI/` → right-click →
   **Artificial Intelligence → Behavior Tree**.
2. Name it `BT_PCSPAgent`.
3. In the BT editor, set **Blackboard Asset = BB_PCSPAgent**.
4. Build this tree structure:

```
ROOT
 └─ [Selector]  "Agent Main Loop"
     │
     ├─ [Sequence]  "Emergency Branch"
     │   ├─ [Decorator: Blackboard]  UrgencyScore > 0.85
     │   └─ [Task: BTTask_PCSPDecision]
     │
     ├─ [Sequence]  "Persona Decision Branch"
     │   ├─ [Task: BTTask_PCSPDecision]    ← writes DesiredActionType + UrgencyScore
     │   ├─ [Task: Wait]  0.1 s            ← placeholder: MoveToAffordance (Phase 2)
     │   └─ [Task: Wait]  1.0 s            ← placeholder: PerformInteraction (Phase 2)
     │
     └─ [Sequence]  "Idle / Fallback Branch"
         └─ [Task: Wait]  2.0 s
```

**Root Selector re-evaluation settings:**
- Observer Aborts: `Self`
- Notify Observer: `On Value Change`

> Phase 2 replaces the `Wait` placeholders with
> `UBTTask_MoveToAffordance` and `UBTTask_PerformInteraction`.

---

## 7. Blueprint Subclasses

Create thin Blueprint wrappers so defaults are tweakable without recompiling.

### BP_PCSPAgentCharacter
- **Blueprint Class → parent: `APCSPAgentCharacter`**
- Class Defaults:
  - `AIControllerClass` → `BP_PCSPAIController`
  - Auto Possess AI: `Placed in World or Spawned`
- Mesh component: assign a SkeletalMesh (ThirdPerson Mannequin is fine for Phase 1).
- Capsule: Half Height `88`, Radius `34`.

### BP_PCSPAIController
- **Blueprint Class → parent: `APCSPAIController`**
- Class Defaults → `BehaviorTreeAsset` → `BT_PCSPAgent`.

### BP_PCSPSimGameMode
- **Blueprint Class → parent: `APCSPSimGameMode`**
- No additional changes needed; exists so the map can reference a content-browser asset.

### BP_PCSPAgentSpawner
- **Blueprint Class → parent: `APCSPAgentSpawner`**
- Class Defaults:
  - `AgentClass` → `BP_PCSPAgentCharacter`
  - `AIControllerClass` → `BP_PCSPAIController`
  - `AgentCount` → `16`
  - `SpawnRadius` → `1500.0`
  - `bSpawnOnNavMesh` → ✓
- Place one instance in the map near the district centre.

---

## 8. World Settings

**Window → World Settings** (or select the WorldSettings actor in the Outliner):

| Setting | Value |
|---|---|
| GameMode Override | `BP_PCSPSimGameMode` |
| Kill Z | `-5000` |
| Enable World Bounds Checks | ✓ |

---

## 9. Recommended Content Folder Structure

```
Content/
└── PCSP/
    ├── AI/
    │   ├── BB_PCSPAgent.uasset
    │   └── BT_PCSPAgent.uasset
    ├── Blueprints/
    │   ├── BP_PCSPAgentCharacter.uasset
    │   ├── BP_PCSPAIController.uasset
    │   ├── BP_PCSPSimGameMode.uasset
    │   └── BP_PCSPAgentSpawner.uasset
    ├── Data/
    │   └── DT_PCSPAffordanceTags.uasset
    └── Maps/
        └── Map_PCSPDistrict_M.umap
```

---

## 10. Verification Checklist

Run **PIE in Simulate mode** (no human player needed):

| Check | How |
|---|---|
| NavMesh is green on the floor | Press **P** in viewport |
| 16 agent actors appear in Outliner | Play → check Outliner |
| Needs values are ~0.8 and decaying | Select agent → Details → NeedsComponent |
| `BTTask_PCSPDecision` is running | **'** key → AI Debugger → BehaviorTree tab |
| `DesiredActionType` BB key is being written | AI Debugger → Blackboard tab |
| Agents are visible in the viewport | Check Mesh component has a mesh assigned |
| No `NavigationSystem` warnings in Output Log | Output Log filter: `Warning` |

---

## Phase 1 Completion Checklist

- [ ] C++ scaffold compiles cleanly
- [ ] `DT_PCSPAffordanceTags` created and registered in Project Settings
- [ ] `Map_PCSPDistrict_M` created with floor geometry
- [ ] NavMesh volume covers full district; **Build Paths** passes without gaps
- [ ] All 10 `APCSPAffordanceZone` instances placed and tagged
- [ ] Interaction points placed and assigned to zone arrays
- [ ] `BB_PCSPAgent` has all 10 keys matching `PCSPBlackboard::` names
- [ ] `BT_PCSPAgent` skeleton built with `BTTask_PCSPDecision`
- [ ] `BP_PCSPAgentCharacter` has mesh and `AIControllerClass` set
- [ ] `BP_PCSPAIController` has `BT_PCSPAgent` assigned
- [ ] `BP_PCSPAgentSpawner` spawns 16 agents in PIE
- [ ] `BTTask_PCSPDecision` visible and writing keys in AI Debugger

Once all items are checked, Phase 1 is complete. Proceed to Phase 2:
`UBTTask_MoveToAffordance`, `UBTTask_PerformInteraction`, retry / reservation logic.
