# PCSP Demo HUD + Zone Overlay — Editor Guide

Step-by-step guide for the editor work that the 2026-05-23 C++ scaffold left
open: **D4 (UMG widgets)** and **D5 (zone overlays)** from
[observer-and-hud.md](../portfolio/demo/observer-and-hud.md).

Prerequisites:

- C++ build is current (the scaffold from `DONE.md §"2026-05-23 - Diagram
  Polish + HUD/Camera C++ Scaffold"` is compiled).
- The portfolio map exists: `Content/PCSP/Maps/Map_PCSPDistrict_Portfolio`
  with `BP_SimGameMode.PlayerControllerClass = BP_PCSPDemoPlayerController`.
- `BP_PCSPAgent` inherits `APCSPAgentCharacter`; the native class owns the
  spectator spring arm and follow camera.

The implemented assets live in `Content/PCSP/Blueprints/Widgets/`.

## Implemented automatic path

The HUD no longer requires a Blueprint Tick, property bindings, or an Event
Graph fan-out. `WBP_PCSPDemoHUD` is parented to `UPCSPDemoHUDWidgetBase`; the
base binds controller delegates and refreshes at 10 Hz. The player controller
creates the assigned `DemoHudClass` during `BeginPlay`.

Mass is the default population (1,024 entities, zero Actor NPCs). Selection,
needs, action distributions, eight recent decisions, slot occupancy, and the
follow button read Mass fragments through the same ViewModel. The camera uses
a lightweight camera proxy; it does not convert entities to Characters.
The affordance panel resolves the goal zone as soon as the decision is made,
not only once a slot is reserved. The social panel reports the crowd
neighbourhood within 800 cm: Actor agents show mean affinity from their
per-pair ledger, crowd entities show how many neighbours chose the same
affordance category, because the crowd keeps no affinity ledger. The run badge
shows failure counts as `n/a` because the crowd history does not track
failures. Its history is a bounded decision ring, not a complete JSONL event
mirror. The HUD never labels an NPC as a Mass entity - the backend is not
something a viewer can act on.

The native view sizes authored text to 14 pt (12 pt for narrow flow values) and
generated rows to 13 pt, makes needs bars fill their row, and auto-sizes the
persona card's rows so a wrapped description cannot paint over the zone row
beneath it. Blueprint assets retain
their authored layout. The legacy WBP-local `ViewModel` is initialized before
Construct, and all widget timers are cleared on Destruct to avoid PIE teardown
errors. Historical Actor-oriented setup examples below are not additional
steps required for Mass mode.

The following names are the only required Designer contract. The official
Unreal MCP created these widgets and marked the interactive containers as
variables:

| Widget | Required child name | Native behavior |
| --- | --- | --- |
| `WBP_PCSPSmallRunBadge` | `T_RunSummary`, `T_CameraMode`, `T_SelectionHint` | live scale/failure summary and controls |
| `WBP_PCSPZoneLegend` | `VB_GlobalDistribution` | population action-distribution bars |
| `WBP_PCSPAgnetCard` | `VB_SelectedDistribution`, `Btn_ToggleCamera`, `T_CameraButtonLabel` | selected NPC distribution and follow toggle |
| `WBP_PCSPTrajectoryStrip` | `VB_TrajectoryRows` | newest-last decision/event rows |
| other existing panels | existing snapshot field names plus `T_AffordanceSummary`, `T_Occupancy`, `T_Distance`, `T_SocialSummary` | persona, needs, decision, affordance, and social state |

Editor assignments after restarting for the new native class:

1. `BP_PCSPDemoPlayerController` → Class Defaults → `Demo Hud Class` =
   `WBP_PCSPDemoHUD` (already serialized by MCP; verify only).
2. `BP_SimGameMode` → Class Defaults → `Player Controller Class` =
   `BP_PCSPDemoPlayerController`. The native GameMode fallback is also the demo
   controller, but this BP currently stores its own override.
3. Leave `WBP_PCSPDemoHUD` Event Graph empty unless presentation animations are
   desired. Override `ReceiveHudDataUpdated` only for cosmetic transitions.

Controls: click an NPC to inspect it, use the HUD button or `F` to toggle its
third-person camera, `Tab`/`Shift+Tab` to cycle, `H` to hide/show the HUD, and
`Z` for zone overlays.

---

## D4 — UMG widget configuration

### D4.0 Data contract

The selected-agent panels read `FPCSPHudAgentSnapshot`; the native base also
builds `FPCSPHudRunSnapshot` for population-level visualizations:

- `FPCSPHudAgentSnapshot` — declared in
  [PCSPAgentDebugViewModel.h](../../Source/cnzoi/PCSP/Public/Components/PCSPAgentDebugViewModel.h).
- Built by `UPCSPAgentDebugViewModel::BuildSnapshot(RecentEventsToShow)`.
- Owned by `APCSPDemoPlayerController` (via `GetViewModel()`).

The snapshot is a **pure read**. The implemented base uses a 10 Hz timer rather
than Tick to keep HUD draw cost out of the frame-time chart.

Three multicast delegates broadcast from the controller — BP can bind to all
three via "Assign on Event Dispatcher" once `Get Player Controller` is cast
to `APCSPDemoPlayerController`:

| Delegate | Payload | UI reaction |
| --- | --- | --- |
| `OnObservedAgentChanged` | new `APCSPAgentCharacter*` (may be null) | rebuild snapshot, swap persona-card content, flash agent-changed indicator |
| `OnHudToggle` | — | toggle `WBP_PCSPDemoHUD` visibility |
| `OnZoneOverlayToggle` | — | toggle zone overlay actors (see D5) |

### D4.1 Widget hierarchy

Create one parent widget and eight sub-widgets. The hierarchy matches the
layout contract in [observer-and-hud.md](../portfolio/demo/observer-and-hud.md).

```
WBP_PCSPDemoHUD  (UCommonActivatableWidget or UserWidget root, Canvas Panel)
├── WBP_PCSPSmallRunBadge       (top-left or top-right anchor)
├── WBP_PCSPZoneLegend          (top-right, key for zone colors)
├── WBP_PCSPAgentCard           (bottom-left)
├── WBP_PCSPNeedsBars           (under agent card)
├── WBP_PCSPDecisionStack       (bottom-center)
├── WBP_PCSPAffordancePanel     (right of decision stack)
├── WBP_PCSPSocialPanel         (under agent card / right column)
└── WBP_PCSPTrajectoryStrip     (bottom-center, full-width strip)
```

Use one **Canvas Panel** at the root for absolute positioning, then a
**Horizontal/Vertical Box** inside each sub-widget for content. Set
**Render Opacity 0.85** on background images so the agent stays visible.

### D4.2 Parent widget — `WBP_PCSPDemoHUD` (implemented)

**Designer:**

1. Open `Content/PCSP/Blueprints/Widgets/WBP_PCSPDemoHUD`.
2. Confirm parent class `PCSPDemoHUDWidgetBase`.
3. Keep its Canvas Panel and eight subwidgets; MCP has already applied the
   responsive top/bottom anchors and dark translucent panel styling.

**Graph (optional customization only):**

- Variables:
  - `Snapshot : FPCSPHudAgentSnapshot` (default).
  - `Controller : APCSPDemoPlayerController` (Object reference).
  - `ViewModel : UPCSPAgentDebugViewModel` (Object reference).
  - `RefreshHz : Float = 10.0`.

- **Event Construct:**

  ```
  Get Player Controller (Index 0)
    → Cast to APCSPDemoPlayerController       → Set Controller
    → Call GetViewModel                       → Set ViewModel
    → Bind Event to OnObservedAgentChanged    → Custom Event "HandleAgentChanged"
    → Bind Event to OnHudToggle               → Custom Event "HandleHudToggle"
    → Bind Event to OnZoneOverlayToggle       → Custom Event "HandleOverlayToggle"
  Set Timer by Function Name
    Function Name: "RefreshSnapshot"
    Time: 1.0 / RefreshHz
    Looping: true
  ```

- **Function `RefreshSnapshot`:**

  ```
  ViewModel → BuildSnapshot (RecentEventsToShow=5) → Set Snapshot
  PropagateSnapshot()
  ```

- **Function `PropagateSnapshot`:** call one setter per sub-widget, passing
  `Snapshot`. Each sub-widget exposes a `SetSnapshot(FPCSPHudAgentSnapshot)`
  function that rebuilds its bindings.

  This pattern avoids 50+ per-property bindings; the sub-widget owns its
  own field extraction.

- **Custom Event `HandleAgentChanged`** (input pin: `NewAgent : APCSPAgentCharacter`):
  immediately call `RefreshSnapshot` so the HUD doesn't show stale state
  for one frame while waiting for the next timer tick.

- **Custom Event `HandleHudToggle`:**

  ```
  Self → Is Visible? → Branch
    True  → Set Visibility (Hidden)
    False → Set Visibility (Visible)
  ```

- **Custom Event `HandleOverlayToggle`:** broadcast a separate
  in-level event dispatcher (`OnPCSPOverlayToggle`) that zone-overlay
  actors are bound to. See D5.

**Adding the HUD to PIE:** handled by
`APCSPDemoPlayerController::BeginPlay`; do not add a duplicate Blueprint
`Create Widget` path.

### D4.3 `WBP_PCSPSmallRunBadge`

Purpose: prove demo mode and scale at a glance (top corner).

**Designer:** Horizontal Box → four `TextBlock`s separated by `|`.

**Bindings (in `SetSnapshot`):**

| TextBlock | Source | Notes |
| --- | --- | --- |
| `T_PolicyMode` | `Snapshot.PolicyMode` | Map enum to "HybridPCSP" / "BTOnly" / "HybridNoPersona" via a small `Switch on EPCSPPolicyMode` |
| `T_AblationTag` | `Snapshot.ActiveAblation` | Show only when not `"unknown"` (set visibility) |
| `T_AgentCount` | `Get All Actors of Class APCSPAgentCharacter → Length` | Cache once on construct; long actor scans are slow on Tick |
| `T_Session` | `UPCSPTrajectoryLogComponent::GetSessionDir` (call once) | Show last path segment only |

### D4.4 `WBP_PCSPAgentCard`

Purpose: whose mind are we watching.

| Field | Source |
| --- | --- |
| `T_PersonaId` | `FString::Printf("#%03d", PersonaId)` |
| `T_PersonaText` | first 80 chars of `Snapshot.PersonaText`; collapse newlines |
| `Img_EmbeddingStatus` | `bEmbeddingActive` → green dot / gray dot |
| `T_ZoneTag` | `Snapshot.CurrentZoneTag.ToString()` or `"—"` if empty |

If you authored short trait chips per persona offline, expose them as a
`TMap<int32, FText>` data table and look up by `PersonaId`. Optional.

### D4.5 `WBP_PCSPNeedsBars`

Purpose: show why some actions are urgent.

**Designer:** Vertical Box with 8 `Horizontal Box (TextBlock + ProgressBar)` rows.

**Bindings:** index `Snapshot.Needs` by `EPCSPNeed` order:
`Hunger, Sleep, Social, Leisure, Hygiene, Fitness, Work, Learning` (0..7).

**Visual rules:**

- Bar `Percent = Snapshot.Needs[i]` (assume 0..1; clamp).
- If `Needs[i] >= 0.85`, set bar `Fill Color` to coral; otherwise category color.
- Place a small vertical tick at 0.85 (a thin `Image` overlay) so the
  critical threshold reads at a glance.
- Bold the row label of the most-urgent need (max of the array).

### D4.6 `WBP_PCSPDecisionStack`

Purpose: make the four-step hybrid stack legible.

**Designer:** Vertical Box with four rows, each row is a `Horizontal Box`
holding a step icon, a label `TextBlock`, and a state `TextBlock`. Background
of the *current* step gets a 30% white tint.

**Step mapping:**

| Step | "Current" condition | Right-column text |
| --- | --- | --- |
| 1. Observe | always shown | `"Persona #017 · obs[33]"` |
| 2. PCSP Decision | `Snapshot.DesiredAction != IdleReflect && TargetActor == null` | `ActionDisplayName(DesiredAction)` + " (u=" + `UrgencyScore` + ")" |
| 3. Affordance Target | `TargetActor != null && DistanceToTarget > 30` | `CategoryDisplayName(DesiredCategory)` + " · " + `CurrentZoneTag` |
| 4. Interaction | `bAffordanceReserved && DistanceToTarget <= 30` | `"reserved · " + ZoneOccupancy + "/" + ZoneCapacity` |

Display `RecentFailureCount` as a small red badge top-right of step 3 if
`> 0` — this is the visible recovery signal the demo-video plan wants.

### D4.7 `WBP_PCSPAffordancePanel`

Purpose: ground actions in world affordances.

| Field | Source |
| --- | --- |
| `T_ZoneTag` | `Snapshot.CurrentZoneTag` |
| `T_Category` | `CategoryDisplayName(Snapshot.ZoneCategory)` |
| `Bar_Occupancy` | `Snapshot.ZoneOccupancy / Snapshot.ZoneCapacity` |
| `T_OccupancyText` | `Printf("%d / %d", Occupancy, Capacity)` |
| `T_Distance` | `Printf("%.0f cm", DistanceToTarget)` if `>= 0` else `"—"` |
| `Img_Reservation` | `bAffordanceReserved` → padlock-closed / open |

**Color rule** (occupancy bar):

- `0 ≤ ratio < 0.6` → green
- `0.6 ≤ ratio < 0.9` → amber
- `ratio ≥ 0.9` → red

### D4.8 `WBP_PCSPSocialPanel`

| Field | Source |
| --- | --- |
| `T_NearbyCount` | `Snapshot.NearbyCount` |
| `T_MeanAffinity` | `Printf("%+.2f", MeanAffinity)` |
| `T_SocialTarget` | `Snapshot.SocialTarget ? SocialTarget->GetName() : "—"` |

Bonus: if `SocialTarget` is a valid `APCSPAgentCharacter`, look up its
persona id and show `"→ #042"` instead of the raw actor name.

### D4.9 `WBP_PCSPTrajectoryStrip`

Purpose: connect live behavior to logged evaluation.

**Designer:** `Horizontal Box` of 5 fixed-width event chips. Each chip is a
small widget (`WBP_PCSPEventChip`) with an icon, action text, and reward delta.

**Bindings (in `SetSnapshot`):**

- `Snapshot.RecentEvents` is already newest-last.
- For each chip `i` (0..4):
  - Get `RecentEvents[RecentEvents.Num() - 5 + i]` (handle short arrays).
  - Color by `EventType`:
    - `Decision` → amber
    - `InteractionComplete` → green
    - `InteractionFailed` → red
    - `MoveFailed` → red (darker)
  - Show `ActionDisplayName(Action)` + (if reward != 0) `Printf("%+.2f", Reward)`.

For a smoother portfolio look, animate new chips sliding in from the right
with a 200ms `Translate X` animation when `Snapshot.RecentEvents.Num()`
increases.

### D4.10 `WBP_PCSPZoneLegend`

A static key — 9 colored squares + labels. No bindings; just authored
once to match the D5 category palette.

### D4.11 Color palette

Use the same hex values across HUD chips and D5 overlay materials so the
viewer's eye links them.

| Category | Hex | UE Linear (R,G,B) |
| --- | --- | --- |
| Eat | `#FFD166` | 1.000, 0.620, 0.149 |
| Rest | `#A8C5E6` | 0.396, 0.585, 0.804 |
| Work | `#8A99A8` | 0.247, 0.318, 0.396 |
| Study | `#5BBFB0` | 0.103, 0.534, 0.451 |
| Exercise | `#7FB57F` | 0.214, 0.476, 0.214 |
| Hygiene | `#7FD0E0` | 0.214, 0.616, 0.730 |
| Social | `#FF8C8C` | 1.000, 0.275, 0.275 |
| Observe | `#B07ED0` | 0.434, 0.214, 0.661 |
| Shop | `#FFC04D` | 1.000, 0.534, 0.078 |
| Idle | `#888888` | 0.247, 0.247, 0.247 |

Save these as a UE5 `Color Curve Atlas` or a `UDataTable` keyed on
`EPCSPAffordanceCategory` so D4 and D5 share one source of truth.

### D4.12 Smoke test

In PIE on `Map_PCSPDistrict_Portfolio` (16 agents):

1. Output Log shows `PCSPPolicySubsystem: ready (obs=33, persona_dim=64, n_actions=20)`.
2. Press `F` → camera blends to a nearby agent, HUD populates within ~200 ms.
3. Press `Tab` → HUD persona card flips to the next persona id.
4. Press `H` → HUD hides; press again → HUD returns.
5. `Snapshot.RecentEvents` populates with `decision` chips immediately,
   `interaction_complete` within a few seconds.
6. Force a failure: pick an agent whose target zone is full, watch the
   decision-stack step-3 badge increment and a `move_failed` chip appear.

---

## D5 — Zone overlay

The overlay marks each `APCSPAffordanceZone` floor with a translucent
category-colored quad and an occupancy-driven outline. It serves three
purposes: orient the viewer, visualize congestion live, and signal active
reservations.

### D5.1 Approach choice

| Option | When to use | Complexity |
| --- | --- | --- |
| **A. Translucent floor decal** | Most levels — projects onto whatever floor mesh is below the zone. | Low |
| **B. Translucent box mesh** | If your floor is uneven and decals tile badly. | Medium |
| **C. PostProcess outline** | If you want a strict outline-only look (no fill). | Higher |

Recommendation: **Option A (decal)** with a fallback **outline material on
zone Bounds box mesh** for the active-target zone only. Decals are cheap,
work over NavMesh-built floors, and don't add geometry per zone.

### D5.2 Master material — `M_PCSPZoneOverlay`

Create `Content/PCSP/UI/M_PCSPZoneOverlay`.

**Material domain:** `Deferred Decal` (Option A) or `Surface` (Option B).
**Blend mode:** `Translucent`. **Shading model:** `Unlit`.

**Parameters:**

| Parameter | Type | Default | Purpose |
| --- | --- | --- | --- |
| `BaseColor` | Vector4 | (1,1,1,1) | Set per-instance from the category palette |
| `Opacity` | Scalar | 0.35 | Floor tint alpha |
| `OutlineStrength` | Scalar | 1.5 | Edge brightness multiplier (Fresnel-driven) |
| `Occupancy` | Scalar | 0.0 | 0..1, drives pulsing |
| `PulseSpeed` | Scalar | 1.5 | Hz of the congestion pulse |

**Graph sketch:**

```
BaseColor → Multiply by (1 + sin(Time * PulseSpeed * 2π) * Occupancy * 0.4)
           → Emissive Color (Unlit)
Opacity   * lerp(1, 1.5, Occupancy) → Opacity output
```

That gives a steady tint at low occupancy, a brighter pulse near capacity,
and full red-shift if you also drive `BaseColor` lerp toward red on the
material instance.

Create **10 material instances** (`MI_PCSPZoneOverlay_Eat`, …`_Idle`),
each setting `BaseColor` to the corresponding hex from D4.11.

### D5.3 Overlay actor — option A (data-only BP)

Two paths. Pick one.

**Path 1 — add to existing `APCSPAffordanceZone` BP:**

Open `BP_AffordanceZone`. Add:

1. **`Decal`** component:
   - `DecalMaterial = MI_PCSPZoneOverlay_*` (matching this zone's category).
     Set via `Construction Script`:
     `Make Material Instance Dynamic → Set Vector Parameter "BaseColor" by
     category lookup`.
   - Decal Size: roughly `(20, ZoneRadius, ZoneRadius)` (X is projection
     depth — keep small to avoid bleeding through ceilings).
   - Sort Order: `-1` (under interaction-point gizmos).
2. **Construction Script:** read `Self → Category` and call
   `Set Vector Parameter Value` on the dynamic material instance to apply
   the category color.
3. **Event Tick (with `ComponentTickInterval = 0.2`):** call
   `GetCurrentOccupancy() / Capacity` → `Set Scalar Parameter "Occupancy"`.
   Throttled — no need to refresh every frame.
4. **Bind to OnZoneOverlayToggle:**
   - Variable `bOverlayVisible : bool = true`.
   - On `BeginPlay`: cast `GetPlayerController(0)` to
     `APCSPDemoPlayerController` → `Bind Event to OnZoneOverlayToggle` →
     custom event flips `bOverlayVisible` and calls
     `Decal → Set Visibility (bOverlayVisible)`.

**Path 2 — separate overlay actor (`BP_PCSPZoneOverlay`):**

Cleaner separation; doesn't pollute the experiment-map zone BP.

1. New BP class: `Actor` parent.
2. Components: `Scene Root` + `Decal`.
3. Property `TargetZone : APCSPAffordanceZone` (Editable, ExposeOnSpawn).
4. On `BeginPlay`:
   - Attach to `TargetZone` (`AttachToActor`, keep-relative).
   - Build dynamic material, apply category color, store reference.
5. Tick (0.2s): same `Occupancy` write as above.
6. In the demo map, run a one-shot **Editor Utility Widget** or a
   `Construction Script` on a manager BP that iterates all
   `APCSPAffordanceZone` actors and spawns one overlay per zone.

For repeatability, prefer Path 2 — it leaves the experiment map and zone
BP untouched.

### D5.4 Highlighting the active target zone

The portfolio "congestion + recovery" beat reads better if the *currently
selected* zone for the observed agent is outlined more strongly.

Add to `WBP_PCSPDemoHUD` (or `APCSPDemoPlayerController` as a BP override):

```
On RefreshSnapshot:
  Resolve Snapshot.CurrentZoneTag → APCSPAffordanceZone (linear scan or
                                                       cache map)
  For each previously-highlighted overlay:
    Set Scalar Parameter "OutlineStrength" = 1.5  (default)
  For the new highlight:
    Set Scalar Parameter "OutlineStrength" = 3.5
```

Cache the "last highlighted zone" so you only do two writes per frame, not
N writes.

### D5.5 Floating zone labels (optional)

For the wide establishing shot, add a `WidgetComponent` to each overlay
actor:

- Widget class: `WBP_PCSPZoneLabel` — single `TextBlock` showing
  `CategoryDisplayName + " · " + occupancy/capacity`.
- Space: `Screen` (always faces camera).
- Draw Size: `200x40`. Pivot: `0.5, 1.0` (anchor above zone center).
- Cull Distance: `4000` cm so labels don't render in the wide shot.

Bind to the same `OnZoneOverlayToggle` so labels hide together with the
floor tint.

### D5.6 Performance budget

- 10 decals at 0.2 s tick interval: negligible.
- WidgetComponent per zone: ~0.05 ms / 10 zones in screen space — fine.
- For the 64-agent stress capture, keep widget labels off (the overlay
  alone is enough) and limit `OutlineStrength` updates to the highlighted
  zone only.

### D5.7 Smoke test

In PIE with the overlay live:

1. Press `Z` once → 10 colored floor tints appear.
2. Watch a busy zone: the pulse rate increases as `GetCurrentOccupancy()`
   approaches `Capacity`.
3. Press `F` to focus an agent → its target zone's outline brightens.
4. Press `Z` again → all overlays hide; HUD unaffected.

---

## Sanity-check checklist before recording

- `pcsp.PolicyMode 0` (HybridPCSP).
- `active_ablation.txt` reads `full` (or set via `swap_ue5_onnx.py`).
- HUD `T_AblationTag` matches the swap script's tag.
- `F` toggle works and doesn't stop Behavior Tree execution (gameplay
  debugger still shows decisions for the followed agent).
- Tab / Shift+Tab cycles through 16 personas in id order (1..16).
- `H` toggles HUD; `Z` toggles zone overlay.
- Trajectory strip shows new chips within a few seconds of pressing `F`.
- 5-min capture run → `Saved/PCSP/Logs/<stamp>/` has 16 (or 64) JSONL files
  with `session_start.active_ablation` set.

## Cross-references

- [demo observer and HUD contract](../portfolio/demo/observer-and-hud.md) — high-level scenario,
  layout sketch, beat table.
- [PCSPAgentDebugViewModel.h](../../Source/cnzoi/PCSP/Public/Components/PCSPAgentDebugViewModel.h)
  — `FPCSPHudAgentSnapshot` field list.
- [PCSPDemoPlayerController.h](../../Source/cnzoi/PCSP/Public/Agent/PCSPDemoPlayerController.h)
  — delegate signatures + key bindings.
- [observability.md](../portfolio/observability.md) — JSONL schema; HUD trajectory
  chips mirror the same `EventType` enum that JSONL rows carry.

## Selection outline material

Clicking an NPC draws a bright green outline around it. The outline is an
inflated second copy of the crowd mesh drawn with
`/Game/PCSP/Materials/MI_PCSPSelectionOutline`: unlit, masked, two-sided, with
the opacity mask discarding every front face. Only the sliver of the hull that
pokes past the body silhouette survives, so the NPC keeps its own material
instead of being repainted by the highlight.

The material is duplicated from AnimToTexture's `M_Body_BoneAnimation` so the
hull inherits the same GPU vertex animation and holds the agent's pose.

That source material is authored against the single **Material Attributes**
pin, so its individual `EmissiveColor` / `OpacityMask` / `WorldPositionOffset`
inputs are dead: writing to them produces a material that still renders as the
body. The outline's shading is therefore injected into the attribute stream
with `SetMaterialAttributes`, and the hull is widened by reading the animation's
own offset back out with `GetMaterialAttributes` and adding
`VertexNormalWS * OutlineThickness` to it. Inflating the *instance transform*
does nothing here — the pose is written by the material, so the animated
vertices land in the same place at any scale.

Run `-run=PCSPSelectionOutlineMaterial -Probe` to print how the source material
is wired and what the built outline ended up with; it is the fastest way to
check this assumption after an engine or plugin upgrade.

It is authored by an editor commandlet, not by hand:

```
UnrealEditor-Cmd cnzoi.uproject -run=PCSPSelectionOutlineMaterial
```

Add `-Force` to rebuild it. Source:
`Source/cnzoiEditor/Private/PCSPSelectionOutlineMaterialCommandlet.cpp`.

Without the asset — or on the legacy cylinder representation, whose mesh the
material was not derived from — `APCSPMassSpawner` logs a warning and falls
back to drawing the selected agent *only* through the highlight component,
tinted solid. Drawing both copies is what produced the mottled overlay the
outline replaced.
