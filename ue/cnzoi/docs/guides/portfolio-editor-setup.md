# PCSP Portfolio — Editor Settings Guide

Editor configuration needed to make `Map_PCSPDistrict_Portfolio` capture-ready.
This guide covers the **settings** work (GameMode/World Settings, the D2 agent
camera mount, spawner config, Project Settings, and capture CVars). The UMG
HUD (D4) and zone-overlay (D5) asset work has its own guide:
[demo-hud-widgets.md](demo-hud-widgets.md).

> **Where you are now:** you have set `PlayerControllerClass =
> BP_PCSPDemoPlayerController` on the portfolio level. The sections below pick
> up from there. The single most important *remaining* setting is the
> **default pawn override** (§1.2) — without it player 0 spawns as an AI agent
> and the free-camera / `ClearFocus` path has nothing to return to.

Asset-path convention in this guide: BPs under `Content/Game/Blueprints/`,
PCSP content under `Content/PCSP/`. Adjust to match your project layout.

---

## 1. GameMode and World Settings

### Background — why an override is required

- The project's `GlobalDefaultGameMode` is `BP_SimGameMode`
  (`Config/DefaultEngine.ini`), derived from C++ `APCSPSimGameMode`, which sets
  `DefaultPawnClass = APCSPAgentCharacter` and
  `PlayerControllerClass = APCSPAIController`
  ([PCSPSimGameMode.cpp](../../Source/cnzoi/PCSP/Private/Sim/PCSPSimGameMode.cpp)).
- That is correct for the **experiment** map (`Map_PCSPDistrict_M`) where every
  spawned actor is an AI agent and there is no human viewer.
- For the **portfolio** map you instead want a human player 0 that is a
  detached free camera and uses `APCSPDemoPlayerController`. So the portfolio
  map needs its own GameMode settings — applied as a **World Settings GameMode
  Override**, leaving the experiment map untouched.

### 1.1 Apply the GameMode override (verify)

1. Open `Map_PCSPDistrict_Portfolio`.
2. **Window ▸ World Settings**.
3. Under **Game Mode**:
   - `GameMode Override` = `BP_SimGameMode` (or a dedicated
     `BP_PCSPDemoGameMode` you create — see note below).
   - Expand **Selected GameMode**. These fields override the GameMode class
     defaults *for this level only*:
     - `Player Controller Class` = `BP_PCSPDemoPlayerController`  ✅ (done)
     - `Default Pawn Class` = **see §1.2**
     - `HUD Class` = leave default (HUD is added by the controller BP, not the
       AHUD slot — see hud-widget-guide.md §D4.2).

> **Cleaner alternative:** create `BP_PCSPDemoGameMode` (parent
> `APCSPSimGameMode` or `GameModeBase`) with the controller/pawn defaults baked
> in, then just set `GameMode Override = BP_PCSPDemoGameMode` with no per-field
> overrides. Either works; the per-field override is faster for a one-off.

### 1.2 Default pawn = free-camera spectator (REQUIRED)

`APCSPDemoPlayerController::ClearFocus()` returns the view to
`GetPawn()` → falls back to `GetSpectatorPawn()`. The establishing/transition
shots (Beat 1, free spectator) also need a movable detached camera. Pick one:

- **Option A — Spectator pawn (recommended).**
  In the Selected GameMode override set `Default Pawn Class = SpectatorPawn`
  (engine class) or a BP child of it with tuned fly speed. This gives WASD +
  mouse free-fly out of the box, and `F` blends from that camera to the nearest
  agent.
- **Option B — DefaultPawn.**
  `Default Pawn Class = DefaultPawn` if you want the simple flying pawn with a
  collision sphere. Slightly heavier than SpectatorPawn; usually unnecessary.

Do **not** leave `Default Pawn Class = APCSPAgentCharacter` on this map — player
0 would possess an AI agent body and the camera/HUD logic breaks.

> If you prefer no pawn at all, set `Default Pawn Class = None` and tick
> **bStartPlayersAsSpectators** on the GameMode; then `ClearFocus` uses the
> auto-created spectator. Option A is simpler and is what the smoke checklist
> assumes.

### 1.3 Verify the controller actually receives keys

The controller binds `F / Tab / H / Z` directly via legacy
`InputComponent->BindKey` ([PCSPDemoPlayerController.cpp](../../Source/cnzoi/PCSP/Private/Agent/PCSPDemoPlayerController.cpp)),
so **no Input Action / Mapping Context authoring is needed**. For the binds to
fire, the controller must be the input owner — it is, as the only player
controller. Confirm in PIE that pressing `F` focuses an agent (see §6).

---

## 2. D2 — Agent camera mount

The camera blend targets the agent **actor**, so the agent must own a camera
component for framing. `APCSPAgentCharacter` is C++ and has no camera; add one
on the **Blueprint child** that the spawner instantiates (do not edit the
experiment agents).

### 2.1 Add camera components to `BP_PCSPAgent`

1. Open (or create) `BP_PCSPAgent` — parent class `APCSPAgentCharacter`. This
   is the same BP referenced by the spawner's `AgentClass` (§3).
2. In the Components panel, add to the existing capsule/mesh root:
   - `SpringArmComponent` named `DemoSpringArm`.
   - `CameraComponent` named `DemoCamera`, parented to `DemoSpringArm`.
3. `DemoSpringArm` settings for follow/third-person footage:
   - `Target Arm Length` = `350`
   - `Socket Offset` = `(0, 0, 90)` (raise to head height)
   - `Use Pawn Control Rotation` = **false** (the AI controller drives rotation;
     the demo player controller is not possessing, so leave the arm relative to
     the agent's facing).
   - `Enable Camera Lag` = true, `Camera Lag Speed` = `6.0`
   - `Enable Camera Rotation Lag` = true, `Rotation Lag Speed` = `8.0`
4. `DemoCamera`: `Field Of View` = `75`, small downward pitch (`-8°`) for a
   shoulder-ish framing.

Because `bAutoManageActiveCameraTarget = false` is set on the controller, the
engine will use this `DemoCamera` automatically when the agent becomes the view
target (`SetViewTargetWithBlend`). No `FindCameraComponentWhenViewTarget` toggle
needed — `ACharacter`/`APawn` already prefer the camera component as view point.

### 2.2 Optional — alternate view modes

The demo-video plan lists Follow / Shoulder / Top-down / Free modes. For a first
pass, the single follow spring-arm above is enough. If you want top-down lock
later, add a second `CameraComponent` and switch the active camera from the HUD
BP — out of scope for the minimum viable demo.

---

## 3. Spawner configuration (portfolio map)

Confirm exactly one `BP_PCSPAgentSpawner` (or the C++ `APCSPAgentSpawner`) is
placed in the portfolio map and set:

| Property | Value | Why |
| --- | --- | --- |
| `AgentClass` | `BP_PCSPAgent` (the one with the camera from §2) | so focused agents have a camera |
| `AIControllerClass` | `BP_PCSPAIController` (with `BehaviorTreeAsset = BT_PCSPAgent`) | drives behavior; unchanged from experiment map |
| `AgentCount` | `16` for readable shots, `64` for the scale shot | overridable at launch by `pcsp.AgentCount` / `-PCSP_AgentCount` |
| `RandomSeed` | `0` (or any fixed value) | reproducible placement across takes |
| `StreamingSourceRadius` | `50000` | guarantees all zones stream in (World Partition) |
| `SpawnDelay` | `30` | NavMesh settle time for `-game` capture |

All four runtime knobs (`AgentCount`, `RandomSeed`, persona list, run duration)
can be overridden at launch — see §5 — so you do not have to re-edit the
spawner between takes.

### 3.1 World Partition `Is Spatially Loaded` (carry-over check)

The portfolio map was duplicated from `Map_PCSPDistrict_M`, so the
`Is Spatially Loaded = false` flag on every `BP_AffordanceZone`,
`BP_InteractionPoint`, and the spawner should have carried over. Verify, because
if any zone is spatially loaded and no streaming source covers it, it never
registers and you get 100% `move_failed` for that category
([PLAN.md Phase 4 streaming note](../../PLAN.md)).

- Select each affordance zone / interaction point / spawner.
- Details ▸ **World Partition** ▸ `Is Spatially Loaded` = **unchecked**.

### 3.2 NavMesh

Confirm a `RecastNavMeshBoundsVolume` covers the district and the NavMesh is
built (green when you press `P` in the viewport). The duplicate map keeps the
bounds volume, but rebuild if the floor geometry was moved for filming.

---

## 4. Project Settings

Most demo behavior is per-map; only a couple of project-wide settings matter.

### 4.1 Maps & Modes

- **Edit ▸ Project Settings ▸ Maps & Modes.**
- For **PIE / editor capture**: no change needed — you launch from the open
  portfolio map.
- For **standalone `-game` capture** (e.g. the scaling-sweep driver path): set
  `Editor Startup Map` and `Game Default Map` to
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio` *before* launching, OR pass the
  map on the command line. The repo default
  (`Config/DefaultEngine.ini:2-3`) still points at `Map_PCSPDistrict_M`, so
  change it only if you are capturing headless and remember to revert.
- Leave `Global Default Game Mode = BP_SimGameMode`; the portfolio map's World
  Settings override takes precedence for that level.

### 4.2 Input — nothing to author

The demo controller uses legacy `BindKey`, so you do **not** need an Input
Mapping Context, Input Actions, or the Enhanced Input plugin for the demo keys.
If a free-fly SpectatorPawn needs WASD and your project uses Enhanced Input for
movement, that is the pawn's concern, not the demo controller's.

### 4.3 Engine config already in place (no action)

`Config/DefaultEngine.ini` already carries the headless-capture hardening from
the T1.3 sweep — `t.IdleWhenNotForeground=0`, `bPauseOnLossOfFocus=False`,
`bSuppressLostFocusMessage=True`. These keep the engine ticking when the capture
window is unfocused. Nothing to change.

---

## 5. Capture CVars and presets

Set these in the PIE console (`~`) or as `-ExecCmds` / `-PCSP_*` launch
switches. The spawner and perf sampler read the `-PCSP_*` command-line forms in
`BeginPlay` (the `-ExecCmds` form can arrive too late — see
[DONE.md 2026-05-19](../../DONE.md)).

| CVar | Launch switch | Purpose |
| --- | --- | --- |
| `pcsp.PolicyMode` | (console only) | `0`=HybridPCSP (use this), `1`=BTOnly, `2`=HybridNoPersona |
| `pcsp.AgentCount` | `-PCSP_AgentCount=N` | override spawner count without editing the level |
| `pcsp.SpawnSeed` | `-PCSP_SpawnSeed=N` | reproducible placement |
| `pcsp.PersonaIds` | `-PCSP_PersonaIds=17,42,103` | **pin the Beat-3 persona-contrast trio** so takes are repeatable (already wired in the spawner) |
| `pcsp.RunDurationSeconds` | `-PCSP_RunDurationSeconds=300` | auto-quit for headless captures |

### Two presets

| Preset | Setting | Use |
| --- | --- | --- |
| Demo readable | `-PCSP_AgentCount=16 -PCSP_SpawnSeed=0` | clean persona/affordance close-ups (Beats 2–4) |
| Demo scale | `-PCSP_AgentCount=64 -PCSP_SpawnSeed=0` | crowd + performance proof (Beats 1, 5) |

### Ablation/model selection (optional)

If a take should advertise a specific checkpoint, run
`research/scripts/swap_ue5_onnx.py <tag>` first; it writes
`Content/PCSP/Models/active_ablation.txt`, which the trajectory log stamps into
`session_start` and the HUD run-badge reads. Keep `pcsp.PolicyMode 0` for the
"real" demo.

---

## 6. Pre-capture smoke checklist

Run 16-agent PIE on `Map_PCSPDistrict_Portfolio` and confirm, in order:

1. **Output Log** shows
   `PCSPPolicySubsystem: ready (obs=33, persona_dim=64, n_actions=20)` and
   `PCSPTrajectoryLog: session dir = .../Saved/PCSP/Logs/<stamp>`.
   No `pcsp_actor.onnx not found` / `persona_embeddings.json not found` errors.
2. Player 0 starts as a **free camera** (you can fly around), not as an agent
   body. → confirms §1.2.
3. Press **`F`** → camera blends (~0.35 s) to the nearest agent; that agent's
   Behavior Tree keeps running (check Gameplay Debugger with `'`). Press `F`
   again → returns to free camera. → confirms §1.2 + §2.1.
4. Press **`Tab` / `Shift+Tab`** → view cycles through agents in PersonaId order.
5. Press **`H`** → HUD hides / shows (once D4 widgets are built).
6. Press **`Z`** → zone floor overlays toggle (once D5 is built).
7. `FindBestZone` query reports `reg=10, valid=10` (no streaming dropouts). →
   confirms §3.1.
8. After ~5 min, `Saved/PCSP/Logs/<stamp>/` has one `agent_p*.jsonl` per spawned
   agent, and ≥7 of the 9 active categories appear in
   `interaction_complete` rows.
9. 64-agent take: `move_failed / (interaction_complete + move_failed) < 5%`.

When all pass, capture the beats per
[the demo video runbook](../portfolio/demo/video-runbook.md), then run
`research/scripts/analyze_ue_session.py <stamp>` for the data-proof beat.

---

## Cross-references

- [demo-hud-widgets.md](demo-hud-widgets.md) — D4 UMG widgets + D5 zone overlay
  asset work (the other half of the editor effort).
- [demo video runbook](../portfolio/demo/video-runbook.md) — scenario and beats.
- [PCSPDemoPlayerController.h](../../Source/cnzoi/PCSP/Public/Agent/PCSPDemoPlayerController.h)
  — key bindings, delegates, `ViewBlendTime`.
- [PCSPAgentSpawner.h](../../Source/cnzoi/PCSP/Public/Sim/PCSPAgentSpawner.h)
  — spawn properties and the `pcsp.*` / `-PCSP_*` overrides.
- [PLAN.md](../../PLAN.md) — Phase 4 streaming/NavMesh notes and the debug log map.
</content>
</invoke>
