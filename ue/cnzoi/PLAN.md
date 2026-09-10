# CNZOI UE5 Development Plan

This document is the active implementation plan for the Unreal Engine 5 side of PCSP. It is derived from `PCSP_UE5_Implementation_Plan.md` and should be updated whenever the UE5 architecture, task order, or research interface changes.

## Engine and Editor Automation Baseline

- Target engine: Unreal Engine 5.8 (`EngineAssociation` 5.8, Build Settings V7,
  UE 5.8 include order).
- Editor automation: Unreal's official `ModelContextProtocol` and
  `AllToolsets` plugins, served at `http://127.0.0.1:8000/mcp`.
- Migration gate: `cnzoiEditor Win64 Development` must build cleanly, all PCSP
  Blueprint assets must compile with warnings treated as errors, and
  `Map_PCSPDistrict_Portfolio` must complete a 16-agent Simulate PIE smoke.

## Direction

Build a UE5 life-simulation sandbox that integrates Persona-Conditioned Shared Policy (PCSP) with Unreal-native AI systems. The core design is a hybrid decision stack:

1. PCSP chooses the high-level semantic intent.
2. Behavior Tree, Blackboard, EQS, AIController, and NavMesh execute that intent.
3. UE5 records rich trajectory traces for evaluation and human-readable demonstrations.

Movement is an execution detail, not a policy action. The policy should output semantic actions such as `EatQuick`, `FocusedWork`, `ExerciseSocial`, or `IdleReflect`; UE5 should resolve affordance targets, pathing, reservation, retry, and interaction execution.

## Current Targets

| Scale | World | Agents | Personas | Purpose |
| --- | --- | ---: | ---: | --- |
| Debug | Small district | 8 | 100 | Communication, reward, and behavior validation |
| Main | Medium district | 16 | 300-500 | Paper reproduction plus UE5 extension |
| Stress | Large district | 32-64 | 500+ | Scalability and real-time evaluation |

## Current Portfolio Focus

### Packaged Shipping presentation repair (2026-09-06)

- [x] Route packaged world clicks explicitly through a transparent lowest-Z HUD
      surface to the controller's shared Actor/Mass cursor picker. Keep HUD
      controls above it and retain the legacy controller binding as fallback;
      self-hit-test-invisible roots alone did not fix Shipping `GameAndUI` routing.
- [x] Diagnose and remove the startup crash caused by cooking the Blueprint
      controller against an editor-locked, stale native parent layout. Keep the
      new camera tuning in non-serialized C++ constants so the cooked Blueprint
      and Shipping executable share the same reflected layout.
- [x] Diagnose the apparent Shipping simulation freeze: packaged headless telemetry
      confirms policy decisions, Recast route movement, and arrivals continue.
- [x] Move the Mass ISM representation tick to PostPhysics and force it enabled at
      BeginPlay so fragment reads do not repeatedly collide with PrePhysics Mass
      processing; this is the shared position, category-tint, and animation path.
- [x] Tune the free-fly pawn to 8,000 uu/s with responsive acceleration for the
      576 m portfolio district instead of inheriting the small template-map speed.
- [x] Correct the Shipping default GameMode cook path to the actual
      `/Game/PCSP/Blueprints/Core/BP_SimGameMode` asset.
- [x] Rebuild and stage the Windows Shipping package successfully.
- [ ] Visually confirm moving category-tinted NPCs in the rebuilt package.

### Separate evaluation questions (2026-09-05)

- [x] Separate Persona effect, Execution architecture, and Inference
      optimization in the Performance HUD; rename the Mass rules baseline to
      Needs heuristic and remove the uncontrolled FPS-vs-BT percentage.
- [x] Add fresh-map variants, shared series/count/seed/camera, population-gated
      warmup, fixed recording windows, per-run CSV/JSON and isolated trajectories.
- [x] Record decision throughput, per-persona action distributions, inference
      service/latency and failures alongside wall-clock FPS/p95/process CPU.
- [x] Add identical captured-input sync/worker replay with logit agreement and
      a fresh-process repeated-seed driver; keep these separate from live FPS.
- [x] Validate build, native regression tests, Actor/Mass travel and rendered HUD.
- [ ] Collect performance evidence with the editor closed; matching intent and
      placement replay remains necessary for isolated BT-overhead claims.

See `docs/portfolio/evaluation-axes.md`. Architecture is a whole-stack comparison;
its existing movement, observation and representation differences remain explicit.

### Population distribution and mode performance comparison (2026-09-05)

- [x] Restore an always-visible compact population action bar chart and an
      expanded all-action chart in Details.
- [x] Add PCSP / BT Only / No Persona recording buttons, per-mode summary
      table, and overlaid CPU/FPS time-series in the Performance window.
- [x] Sample Windows process CPU normalized to logical cores and wall-clock
      frames; isolate mode changes with five-second warm-up and distinct runs.
      Keep latest runs for comparison and write every raw sample to unique CSV.
- [x] Verify metric arithmetic, live three-mode recording, and rendered layout.

This is live whole-process performance observation, not an isolated inference
benchmark. In the Mass implementation BT Only means needs rules with ONNX off.

### Portfolio readability and package data (2026-09-05)

- [x] Replace the default diagnostics wall with readable, pixel-scaled persona
      evidence cards, a frozen comparison pin, and explicit details controls.
- [x] Group consecutive repeated decisions with their time range and sample
      count; distinguish recorded decisions from completed interactions.
- [x] Set 24 large Dieselpunk textures to a 4096 maximum (raised from the
      earlier 2048 VRAM cap), preserve animation data textures, budget
      streaming, and disable the optional animated selection hull by default.
- [x] Stage ONNX and persona JSON data, cook the Visual map and dynamically
      loaded PCSP materials. Preserve the user's Visual startup-map selection.
- [x] Rendered 1280x720 comparison/details and 1920x1080 comparison checks;
      1,024-agent policy/HUD/pin smoke passed. Final captures have no VRAM warning.
- [ ] Visible target-GPU performance acceptance and packaged Shipping execution
      remain separate release gates.

See `DONE.md` and `docs/portfolio/portfolio-presentation.md` for evidence and
limitations. Policy, observation, and research evaluation contracts are unchanged.

### Mass NavMesh movement repair (2026-09-04)

- [x] Triple Mass body/selection scale and use matching 105 cm separation radii.
- [x] Scale translation with body size, but drive AnimToTexture cadence from
      body-relative speed. At 3x scale, normal movement remains 780 uu/s with
      1.2x playback; 450 uu/s strolls use about 0.69x instead of multiplying
      playback by scale a second time.
- [x] Scale the click fallback, HUD selection-arrow height, and Mass third-person
      framing from the selected NPC's visual scale. At 3x the marker is 615 cm
      above the feet and the camera uses 1,140/630/360 cm distance/height/look-at.
- [x] Replace shared city grid waypoints with per-entity cached Recast paths,
      bounded path queries, and NavMesh-constrained movement. Mass-to-Mass
      separation/contact is disabled by default (`pcsp.MassAgentCollision=0`)
      so NPCs can pass through each other; selection retains Visibility queries.
- [x] Build/wait for navigation before spawning. In the Visual map, project
      affordance-slot anchors onto reachable NavMesh, fill sparse districts, and
      round-robin the first 1,024 starts across a 4x4 city partition. Initial
      starts still avoid exact overlap; runtime crowd collision stays off.
- [x] Add a 300 m Mass representation cull distance and suppress ray-tracing
      effects without invalidating all mesh DDC. Record texture/geometry pressure
      and the next visible-GPU A/B gates in the rendering optimization guide.
- [x] Normal Editor build and four Mass automation tests passed. Final functional
      session `20260904_044331` spawned exactly 64 NPCs in every 4x4 district,
      with 1,400 valid anchors and collision reported off. NullRHI validates the
      function and telemetry, not animation appearance or rendered frame rate.

The legacy city flow fields are disabled by default. Mass movement now requires
a built NavMesh covering the spawner, roads, and interaction slots. Research
observation/action/export contracts remain unchanged.

### Dieselpunk Visual district (2026-09-03)

- [x] Author an eastern four-block district in
      `Map_PCSPDistrict_Portfolio_Visual` through the official Unreal MCP:
      cobblestone roads, sidewalks, civic court, five buildings, and street furniture.
- [x] Correct the floating observatory and separate landmark footprints from roads;
      keep the original PCSP demonstration floor and gameplay actors intact.
- [x] Save World Partition external actors and inspect building overlap and ground
      collision. Authoring script: `tools/build_dieselpunk_city.py`.
- [x] Relocate the Visual map's 118 affordance zones / 1,704 slots to its 16 city
      blocks, retaining identity and capacity. Move the 1,024-Mass start area to
      the hotel courtyard. Verify all slots after save/reload, 354 ground samples,
      and a short PIE run with 118 registered zones and 587 reservations.
- [x] Add shared per-zone Mass routes through city roads and bridges, excluding
      tagged buildings, furniture, and parapets. Full build and route regression
      test passed. Final 1,024-NPC / 300-second functional run: 2,157 arrivals,
      441 canal crossings, all three bridges used, zero route failures or sampled
      obstacle/ground violations. Real rendered PIE also reached 151 destinations.
      This is a navigation acceptance result; rendering performance and crowd
      separation remain separate gates.
- [x] Expand the visual city to 576 x 572 m (4x area), 16 blocks, 40 buildings,
      a canal, three road bridges with KitBash covered walkways, and 104 props.
- [x] Add `PCG_DieselpunkCityBlock` and six editable PCG volumes producing 29
      buildings. Expose class, area, spacing, fill ratio, seed, facing, jitter,
      scale, label, and streaming parameters. Validate regeneration and spacing.
- [ ] Optimize the expanded visual district for the current 4 GB VRAM adapter:
      final viewport showed about 0.8-1.3 GB over budget. Profile geometry and
      evaluate Nanite/LOD/proxies and streaming before claiming smooth editing.

Current PCG editing guide: [dieselpunk-city-pcg.md](docs/portfolio/dieselpunk-city-pcg.md).
NPC destination editing guide: [dieselpunk-city-affordances.md](docs/portfolio/dieselpunk-city-affordances.md).
Road and bridge routing guide: [dieselpunk-city-navigation.md](docs/portfolio/dieselpunk-city-navigation.md).
Rendering optimization audit: [dieselpunk-city-rendering-optimization.md](docs/portfolio/dieselpunk-city-rendering-optimization.md).
Initial layout record: [dieselpunk-city-authoring.md](docs/portfolio/dieselpunk-city-authoring.md).

### Mass-first demo repair (2026-09-03)

Mass entities are now the default presentation and simulation population;
Actor/BT agents remain an explicitly requested debug baseline. The current
repair connects the Mass fragments to HUD selection, population aggregation,
slot occupancy, and a non-possessing camera proxy. It also replaces the static
reference-pose/head-beacon representation with AnimToTexture idle/walk ISM
groups tinted by the same category palette as the affordance floor markers.

- [x] Implement capacity-aware Mass slot claims and weighted alternative-zone
      selection; release claims after short, authored-duration-scaled interactions.
- [x] Implement Mass snapshots, bounded decision history, click/Tab selection,
      and third-person camera support without converting entities into Actors.
- [x] Bind the legacy WBP-local ViewModel before Blueprint Construct and clear
      all widget timers during teardown.
- [x] Implement seeded category mixing (`-RelayoutCompact -LayoutSeed=17`) that
      retains every authored zone/capacity and repairs same-category neighbors.
- [x] Suffix-9475 Editor build, three automation tests (including fair admission
      rotation), and 1,024-Mass offscreen smoke passed. HUD selection/needs/history/
      population/follow-camera checks passed; startup through shutdown logged zero
      ViewModel Accessed None warnings. Two captures confirmed animated poses and
      category body tint with no head beacons.
- [x] With the editor closed, hash-verify a 126-file map backup and apply the
      mixed Portfolio layout. A fresh load audited 96 zones / 592 slots,
      zero same-category neighbors and overlaps, and 420 cm slot clearance.
      Normal (unsuffixed) Editor build and two real PIE start/stop cycles passed:
      default 1,024 Mass, needs/history, UMG camera-button callback and legacy
      ViewModel binding; zero Accessed None errors through teardown. NullRHI PIE
      verifies behavior, not rendered hit testing or final presentation.
- [x] Inspect actual 1920x1080 rendered output and repair HUD text overflow,
      narrow needs bars, and the unassigned diagram placeholder without changing
      widget assets. Final render verified animated category-tinted bodies and
      readable Mass snapshots/camera state.
- [ ] Run a fresh visible GPU-memory/performance benchmark and physical mouse
      selection check. VRAM-budget warnings also occurred in isolated offscreen
      runs with no Editor open; functionality tests are not performance evidence.
      Lower-resolution HUD layout still needs an interactive presentation check.

The 33-float observation, persona projection, policy actions, training export,
and research evaluation contracts are unchanged. New performance claims require
a fresh visible benchmark: the old static-Manny numbers do not describe the
GPU-skinned representation.

Near-term UE5 agent work is portfolio-focused. Prioritize engine-facing
extensions before demo presentation:

1. Stabilize the live hybrid policy / Behavior Tree contract.
2. Improve affordance selection under congestion with EQS or weighted scoring.
3. Add async/batched inference only when targeting larger showcase runs or
   when synchronous inference becomes visible in capture.
4. Extend observability so live HUD panels can reuse the same event stream as
   JSONL logs.
5. Iterate on the implemented click-to-inspect HUD and non-possessing
   third-person follow camera as presentation feedback arrives.

Detailed portfolio docs live under [docs/portfolio/](docs/portfolio/).

## Architecture Tasks

- Define an affordance-zone taxonomy for the UE5 level.
- Specify the Behavior Tree, Blackboard, and policy interface contract.
- Implement C++ components for persona state, needs, social context, observations, and trajectory logging.
- Implement affordance registration and lookup as a world-level service or subsystem.
- Implement custom Behavior Tree nodes for PCSP decisions, affordance movement, and interactions.
- Decide whether the first inference bridge uses a Python service, ONNX Runtime, or TorchScript.
- Keep the Python research implementation reproducible while adding UE-facing export or bridge code only where needed.

## Phase Roadmap

### Phase 0: Environment Redesign Documentation

- [x] Summarize the Python Mini-Inzoi reward, observation, and action logic
      ([docs/contracts/research-environment-summary.md](docs/contracts/research-environment-summary.md)).
- [x] Define the UE5 affordance taxonomy
      ([docs/contracts/affordance-taxonomy.md](docs/contracts/affordance-taxonomy.md);
       three-layer architecture in [docs/architecture/affordance-system.md](docs/architecture/affordance-system.md)).
- [x] Write the BT-Blackboard-Policy interface specification
      ([docs/contracts/bt-blackboard-policy-contract.md](docs/contracts/bt-blackboard-policy-contract.md)).
- [x] Confirm Main and Stress scale targets
      ([docs/validation/scale-targets.md](docs/validation/scale-targets.md);
       16/32/64 all empirically verified, 64 stress at 1.7% failure rate).

### Phase 1: Continuous-Space Prototype

- [x] Build a Medium district level (`Content/PCSP/Maps/Map_PCSPDistrict_M.umap`)
      with one zone per category (Kitchen/Eat, Bedroom+Lounge/Rest, Office/Work,
      Library/Study, Gym/Exercise, Bathroom/Hygiene, SocialHub/Social, Park/Observe,
      Shop/Shop). Map uses World Partition; all gameplay actors (zones,
      interaction points, spawner) must have `Is Spatially Loaded = false` —
      see Phase 4 streaming note below.
- [x] Spawn and schedule 16 agents (C++ `APCSPAgentSpawner`, configurable `AgentCount`).
- [x] Create NavMesh, affordance zones, and interaction points
      (C++ `APCSPAffordanceZone`, `APCSPInteractionPoint`, `UPCSPAffordanceSubsystem` in place;
      all 10 zone instances + interaction points placed in map; NavMesh built).
- [x] Implement needs, social, and observation components
      (`UPCSPNeedsComponent`, `UPCSPSocialContextComponent`, `UPCSPObservationComponent`,
       `UPCSPPersonaComponent`, `UPCSPTrajectoryLogComponent`).
- [x] Build the baseline Blackboard-driven Behavior Tree skeleton
      (`BB_PCSPAgent` + `BT_PCSPAgent` authored in editor; `UBTTask_PCSPDecision` live and writing keys).

### Phase 2: Hybrid Behavior Tree Implementation

- [x] Implement `UBTTask_PCSPDecision` (Phase 1 stub, maps needs → action type).
- [x] Implement `UBTTask_MoveToAffordance` — queries subsystem, reserves interaction point, moves agent; retries up to MaxRetries times on path failure.
- [x] Implement `UBTTask_PerformInteraction` — waits InteractionDuration, applies needs satisfaction delta, releases reservation.
- [x] Add retry and reservation conflict handling (MoveToAffordance RetryCount + RecentFailureCount BB key; PerformInteraction checks reservation validity each tick).
- [x] Emergency branch for critical needs (UrgencyScore > 0.85 Blackboard Decorator, Observer Aborts = Both).
- [ ] Congestion handling — first weighted scorer is implemented (`pcsp.WeightedZoneScoring=1`);
      build/PIE validation, expanded-zone measurement, and editor-owned EQS integration remain pending.
- [x] Zone-coverage fix for engine-integration experiment (2026-05-17):
      Park (Observe) and Gym (Exercise) were systematically unvisited.
      Resolution: agents now run on ONNX inference exclusively — heuristic
      fallback removed. (a) ONNX v3 indices 16-19 (movement, unused in UE)
      remapped to `LeisureOutdoor`/`ObserveCrowd` so the Observe category has
      a reachable action; (b) Gym (Exercise) is reachable via v3 indices 8/9
      which the policy already emits. If `pcsp_actor.onnx` or
      `persona_embeddings.json` is missing, `BTTask_PCSPDecision` now logs
      an Error and returns Failed — agents do not move rather than fall back
      to a heuristic surrogate.

### Phase 3: PCSP Policy Integration

- [x] Implement persona embedding cache loading (`UPCSPPersonaCache` — reads persona_embeddings.json).
- [x] Load projected persona vectors into `UPCSPPersonaCache`; `UPCSPPersonaComponent::GetPersonaId()` exposes 1-based ID.
- [x] Connect ONNX Runtime inference via `UPCSPPolicySubsystem` (NNE / NNERuntimeORT plugin).
      Graceful fallback to needs heuristic when model files are absent.
- [x] Align `UPCSPObservationComponent` to v3 33-dim schema (pos/time/needs/zone-onehot/social/routine/neighbors).
- [x] Export script: `research/scripts/export_pcsp_onnx.py` → pcsp_actor.onnx + persona_embeddings.json.
- [ ] Add async/batched inference (deferred — synchronous is sufficient for ≤16 agents at 60Hz).
- [x] Export reward and trajectory logs from `UPCSPTrajectoryLogComponent` (2026-05-17):
      Per-agent JSONL written to `Saved/PCSP/Logs/<YYYYMMDD_HHMMSS>/agent_p<id>_<actor>.jsonl`.
      Events: `decision`, `interaction_complete`, `interaction_failed`, `move_failed`.
      Each entry carries t, persona_id, pos, action, affordance, category, urgency, reward,
      and 8-need snapshot. Buffered + auto-flushed every 5s and on EndPlay.

### Phase 4: Scaling And Experiments

- [x] All-Mass 1,024-NPC runtime and visible goal distribution (2026-09-02):
      Mass mode now enforces `0 Actor + N Mass` by folding any configured Actor
      count into `MassEntityCount`; the sweep defaults to `HeroAgentCount=0`.
      Each Mass NPC renders a small beacon colored by its exact destination
      Zone's stable visualization ID. UE 5.8 Editor/Game targets build cleanly;
      an offscreen 1,024 run logged `0 Actor + 1024 Mass` and rendered the markers.
- [x] Integrated affordance slots (2026-09-02): `APCSPAffordanceZone` now owns
      interaction slot definitions, reservation state, auto-generated grids,
      auto-expanded bounds, and Zone-unique circular floor markers. Actor
      BT and Mass target selection consume the Zone slots directly. The editor
      commandlet migrated `Map_PCSPDistrict_M` to 10 Zones/210 slots and the
      portfolio map to 96 Zones/592 slots; both now contain zero legacy Point actors.

- [x] Decision throttle + failure backoff (2026-05-17): `BTTask_PCSPDecision`
      now caches the last action and only re-runs ONNX every
      `MinDecisionInterval` seconds (default 0.5s). Effective interval is
      multiplied by `(1 + RecentFailureCount)` so repeated MoveTo failures
      back off instead of hot-looping. UrgencyScore ≥ 0.85 bypasses the
      throttle. Removes the ~7.5 inferences/agent/s observed in the
      2026-05-17 run.
- [x] Spawner deferred-spawn fix (2026-05-17): `APCSPAgentSpawner` now uses
      `SpawnActorDeferred → set PersonaId → FinishSpawning` so
      `TrajectoryLog::BeginPlay` sees the correct PersonaId when naming the
      log file. Previously all log files were named `agent_p001_*` even though
      per-record `persona_id` was correct.
- [x] World Partition streaming fix (2026-05-17): all `BP_AffordanceZone`,
      `BP_InteractionPoint`, and `BP_PCSPAgentSpawner` instances in
      `Map_PCSPDistrict_M` set to `Is Spatially Loaded = false`. With no
      `WorldPartitionStreamingSource` present (16 AI-only pawns), spatially
      loaded zones outside the editor camera's startup streaming radius were
      never spawned, so `UPCSPAffordanceSubsystem` only registered 7 of 10
      zones — Kitchen/Gym/Shop never streamed in, producing 100% move_failed
      for Eat/Exercise/Shop. After the toggle: `FindBestZone` reports
      `reg=10,valid=10` every query.
- [x] Move-task failure isolation (2026-05-17): `UPCSPAffordanceSubsystem::FindBestZone`
      gained a diagnostic overload returning `FPCSPZoneSelectionDebug`
      (rejection enum + per-stage counts). `BTTask_MoveToAffordance` now
      labels every failure branch (`FindBestZone:<reason>`,
      `zone_no_free_interaction_point`, `interaction_point_reserve_race_lost`,
      `pathfinding_request_failed`, `path_follow_idle_short:dist=<cm>`) and
      writes `failure_reason`, `intended_zone`, `distance_to_target` to the
      JSONL. These are the fields the Phase 4 verification recipes below
      depend on.
- [x] Path-follow acceptance fix (2026-05-17):
      `FAIMoveRequest::SetReachTestIncludesAgentRadius(false)` in
      `BTTask_MoveToAffordance::TryBeginMove`. Without it, pathfollowing
      treats `AcceptanceRadius` as capsule-inclusive and stops at
      `AcceptanceRadius + AgentRadius (~40cm)` from the goal; our 2D distance
      success check then misses by 15–30 cm. Logs before fix clustered failures
      at `dist=313–331` for a 300 cm acceptance; after fix, `path_follow_idle_short`
      dropped from 2,414 to 84 events (−96.5%).
- [x] 16-agent baseline verified (2026-05-17, session `20260517_150713`,
      10 min PIE): 690 `interaction_complete` across 8 of 10 categories
      (Eat, Rest, Work, Study, Exercise, Hygiene, Social, Observe). Remaining
      55% failure rate is 90% `FindBestZone:AllOverCapacity` — capacity
      contention from 8 of 10 categories having only 1 zone each. This is
      the realistic-competition failure mode the throttle's `RecentFailureCount`
      backoff was designed for; not a blocker. Missing: Shop (policy emits
      `BrowseArea` at ~0.25% — almost never tried). Note: the `Leisure` enum
      value has no zone in the level — it was folded into Observe during the
      Phase 2 remap (v3 indices 16/18 emit `LeisureOutdoor`, which routes to
      the Park/Observe zone via `UPCSPPolicySubsystem::ActionToCategory`).
      Effective taxonomy is 9 categories, not 10.
- [x] Test 32 agents (2026-05-17, session `20260517_150713`, 32-agent window ~343s):
      Capacity raised from 4 to 8 on bottleneck zones before this run.
      Results: 1,049 `interaction_complete` across all 9 active categories
      (Shop appeared for the first time at 2 completions). The `Leisure` enum
      value has no zone in the level — see 16-agent note above. Failure rate collapsed from 55% to
      5.4%; 60 `move_failed` total, 91.7% `FindBestZone:AllOverCapacity` on Rest
      zones (Bedroom/Lounge still single-zone — primary bottleneck at 32 agents).
      Avg 32.8 interactions/agent over 343s (~4× throughput vs 16-agent baseline).
      Total reward: 347.85. Prerequisite for 64-agent run: add a second Rest zone
      or raise Rest capacity further to keep AllOverCapacity below 50%.
- [x] **T1.3 scaling sweep {8,16,32,64,96,128} × 3 seeds × 630 s**
      (2026-05-20, 18 sessions `20260520_000614`..`030856`,
      `research/results/ue_sessions/scaling_20260520/`):
      Inference latency flat 183--202 µs through n=64 (well under 250 µs
      budget); the apparent drop to 153/132 µs at n≥96 is CPU-scheduler
      timeslicing at saturation, not model speedup.
      Frame time scales ≈ 0.27 ms/agent: mean 5.57 ms (n=8) →
      14.39 ms (n=128); p95 stays inside the 60 fps budget (16.67 ms)
      through n=96.
      Failure rate is 0\% at n≤32, 0.2\% at n=64, **4.7\% at n=96, 44.9\% at n=128**.
      NavMesh `FindPath` queue saturation is the hard ceiling above n=96.
      Intent throughput stable at 5.6--6.1/agent/min for n≤64.
      **Headline:** ≤64 agents is the recommended real-time operating
      point; 96 is a soft cap; 128+ requires async batched pathfinding.
      Driver: `ue/cnzoi/tools/run_scaling_sweep.ps1` (added `-StartIndex`
      for resume after PS death); analyzer: `analyze_scaling_sweep.py`;
      outputs `per_session.json`, `scaling_curve.json`, `latency_budget.tsv`.
      Three sweep-driver bugs fixed beforehand:
      `t.IdleWhenNotForeground=1` engine freeze on focus loss,
      world-TimerManager auto-quit not firing on paused world (moved to
      `FTSTicker::GetCoreTicker`), and `-ExecCmds` arriving after
      `BeginPlay` (replaced by `-PCSP_AgentCount/SpawnSeed/RunDurationSeconds`
      cmdline switches read via `FParse::Value`). Also added a WP
      streaming source on the spawner + `RuntimeGeneration=Dynamic` for
      standalone NavMesh parity with PIE — was 95 % pathfind failure
      before, 0 % after.
- [x] **1024-NPC Mass-hybrid first pass + bounded Actor path admission**
      (2026-08-31): added `UPCSPPathRequestSchedulerSubsystem`, which grants
      at most `pcsp.PathRequestsPerFrame` new `MoveTo` requests each frame
      using urgency plus wait age. `BTTask_MoveToAffordance` now waits for a
      permit before reserving a zone/interaction point. Added
      `APCSPMassSpawner`, PCSP Mass fragments/trait, and
      `UPCSPMassSimulationProcessor`: background entities retain persona,
      eight needs, 33-d observation semantics, 20-action policy intent,
      cohort, zone target, and transform while avoiding one Character,
      Controller, BT, collision body, and Recast request per entity.
      Decisions are distributed over 32 cohorts and capped with
      `pcsp.MassMaxDecisionsPerFrame`; HISM rendering updates at low
      frequency. The original cylinder proxy was replaced on 2026-09-02 by
      a reference-pose Manny static mesh baked from the same mesh/materials
      as `BP_PCAPAgent`; the Mass HISM forces a 5%-triangle LOD1. The legacy
      cylinder remains available only through
      `pcsp.MassCharacterRepresentation=0` for reproducible A/B profiling.
      `run_scaling_sweep.ps1 -MassHybrid` now drives
      128/256/512/1024 totals, and `analyze_scaling_sweep.py` aggregates
      Actor/Mass counts, path queue/wait, and Mass policy/arrival metrics.
      Compatibility smoke `20260831_035336` ran 4 hero + 1,020 Mass entities
      for 29.4s: 3,322 Mass decisions, 3,933 arrivals, and 0 hero move
      failures. The offscreen run was throttled, so its frame time is not a
      publishable performance result. Design and acceptance criteria:
      [docs/portfolio/mass-1024-scaling.md](docs/portfolio/mass-1024-scaling.md).
      Same-build/seed 107 profiling measured `111.82 -> 114.54 ms` telemetry
      frame mean (`+2.4%`) and `115.36 -> 118.06 ms` Insights Frame timer
      (`+2.3%`) for cylinder -> Manny LOD1; report:
      [docs/portfolio/benchmarks/mass-character-representation-20260902.md](docs/portfolio/benchmarks/mass-character-representation-20260902.md).
- [x] Run the final visible Mass-hybrid benchmark at 128/256/512/1024 total
      NPCs × 3 seeds. All 12 visible standalone runs completed on 2026-09-01;
      at 1,024 NPCs frame mean is `25.47 ± 0.47 ms`, frame p95 is
      `30.15 ± 0.53 ms`, and hero movement failure is `0.0%`. Report:
      [docs/portfolio/benchmarks/visible-mass-20260901.md](docs/portfolio/benchmarks/visible-mass-20260901.md).
      This is retained as historical mixed-tier evidence.
- [x] Rebuild `Map_PCSPDistrict_Portfolio` as a wide non-overlapping 12×8
      layout and rerun the current all-Mass scaling benchmark. The saved map
      spans `67,690 × 40,680 cm`, contains 96 Zones / 592 integrated slots,
      and reload-audits at 0 Zone overlaps / 0 slot overlaps / 420 cm minimum
      slot spacing. The stable 128/256/512/1024 × 3-seed visible sweep completed
      on 2026-09-02 with 0 Actor NPCs. At 1,024 Mass entities, frame mean is
      `28.42 ± 0.17 ms` and p95 is `34.14 ± 0.11 ms`. Report:
      [docs/portfolio/benchmarks/all-mass-portfolio-20260902.md](docs/portfolio/benchmarks/all-mass-portfolio-20260902.md).
- [ ] Attach Unreal Insights captures and report game/navigation/Mass/render
      breakdown plus memory per NPC. Persona-distinctness by simulation tier is
      now covered by the [full-PCSP three-seed independent-evaluator audit](../../research/docs/integration/ue-simulation-tier-behavior.md).
      Do not use
      `-RenderOffscreen` results as FPS proof.
- [x] Stress test 64 agents — three-run progression (2026-05-17):
      **Run 1** session `20260517_150713` (1,490s, Rest cap=20, Social cap unchanged):
      9,833 `interaction_complete`, 69,421 `move_failed`, failure rate 87.6%.
      Dominant failure: `FindBestZone:AllOverCapacity` (65,618, 94.5%) — Social zone
      saturated at zone level. Total reward: 3,348.50. Fix: raise Social zone capacity.

      **Run 2** session `20260517_224132` (1,012s, Social cap raised):
      4,738 `interaction_complete`, 7,501 `move_failed`, failure rate 61.3%.
      `FindBestZone:AllOverCapacity` collapsed to 262; new dominant failure:
      `zone_no_free_interaction_point` on `PCSP.Zone.Rest` (7,219, 96.2%) —
      zone capacity raised but insufficient `BP_InteractionPoint` actors in Rest zone.
      Total reward: 1,663.45. Fix: add interaction points inside Rest zone.

      **Run 3** session `20260517_230327` (483s, Rest interaction points expanded):
      2,438 `interaction_complete` across all 9 active categories, only 43 `move_failed`,
      failure rate **1.7%** — residual `AllOverCapacity` spikes (42 events), not
      structural. Total reward: 835.30. Avg 38.1 interactions/agent (~4.7/agent/min).
      Category coverage: Social 876, Rest 856, Work 403, Hygiene 121, Study 62,
      Observe 52, Eat 47, Exercise 15, Shop 6 (Leisure enum has no zone — folded
      into Observe; see 16-agent note). 64-agent stress target validated.
- [x] Automate zero-shot persona evaluation (2026-05-18):
      `research/scripts/analyze_ue_session.py` ingests
      `Saved/PCSP/Logs/<stamp>/agent_p*.jsonl`, aggregates per-persona
      action histograms (20 v3 actions), category coverage,
      interaction/failure counts, reward sums, decision-latency stats,
      and failure-reason breakdown. Supports `--compare <other-session>`
      to compute matched-persona Spearman ρ between two PIE runs.
      `research/scripts/run_zeroshot_eval.py` orchestrates the held-out
      run end-to-end: `prepare` swaps `persona_embeddings.json` so UE
      slots 1..N hold `test_60_v3.json` personas (IDs 241..300) and
      writes a slot→real-id manifest; user runs PIE; `finish`
      auto-detects the new session, relabels per-persona output via
      the manifest, compares aggregates vs the train baseline, then
      restores the train embeddings.
- [x] Validate zero-shot persona generalization on held-out IDs 241..300
      (2026-05-18, capacity-fix progression):
      **Pre-fix** session `20260518_112540` (64 held-out personas, 7.4min):
      2,180 interactions, **12.5% failure rate** (vs 2.0% train baseline);
      99.4% of failures were `FindBestZone:AllOverCapacity` on
      `FocusedWork`/`PlanningWork` (310 of 312). Held-out persona demand
      profile differed from train and saturated the single Office zone.
      **Mid-fix** session `20260518_114841` (train personas, Work expanded):
      Work failures collapsed 302→1; new dominant bottleneck was Hygiene
      (134 `HygieneQuick` `AllOverCapacity` failures).
      **Post-fix** session `20260518_133852` (train personas, +Hygiene
      expanded): **0 failures** across 1,474 interactions in 5min.
      **Clean zero-shot** session `20260518_140432` (held-out personas,
      both fixes, 9.75min): 2,792 interactions, **0.04% failure rate
      (1 `path_follow_idle_short`)**, 43.6 interactions/agent (vs 33.5
      train), reward 960.4 (vs 730.6 train), inter-persona action
      ρ = **0.368** (vs 0.383 train — actually *more* persona-distinct
      on unseen personas). Category coverage 9/10 in both. Headline:
      policy preserves persona-distinct behavior on personas it has
      never seen during training, once environment capacity matches
      the held-out demand profile.
- [x] Collect policy KL and richer path-failure/congestion deltas
      across paired sessions (2026-05-18): `UPCSPPolicySubsystem`
      gained `RunInferenceWithLogits`; `BTTask_PCSPDecision` now calls it
      and forwards the 20-dim logit vector to
      `UPCSPTrajectoryLogComponent::RecordDecisionWithLogits`, which
      appends `"logits":[...]` to each `decision` JSONL row.
      `analyze_ue_session.py` softmaxes per-decision logits into a
      per-persona mean policy distribution; `--compare` now emits
      symmetric KL (mean of `KL(p_a||p_b)` and `KL(p_b||p_a)`) per
      matched persona alongside the existing Spearman ρ. Re-run any
      paired PIE sessions after rebuilding to populate `kl_*` fields
      in `compare.json`.
- [x] Compare BT-only, RL-only, Hybrid-PCSP, Hybrid-NoConsist, and Hybrid-NoPersona settings.
      **Runtime ablations (2026-05-18):** `pcsp.PolicyMode` CVar
      switches between `HybridPCSP` (0, default), `BTOnly` (1, uses
      `NeedsHeuristic`, skips ONNX) and `HybridNoPersona` (2, ONNX with
      zeroed persona vector). Mode tagged on each agent's
      `session_start` JSONL row. Three paired 64-agent / ~5min PIE runs
      aggregated into a single table via
      `research/scripts/compare_ablations.py`:
      HybridPCSP 2,077 int / 0.0% fail / reward 708.9 / dispersion 0.368;
      BTOnly 1,152 int / 87.6% fail / 395.2 / 0.989; HybridNoPersona
      1,752 int / 13.3% fail / 573.9 / 0.990 (sym KL vs PCSP = 1.05).
      Persona embedding is load-bearing (dispersion 0.37→0.99 when
      zeroed); ONNX strictly dominates needs heuristic (BTOnly collapses
      under capacity contention). Full results:
      `research/results/ue_sessions/ablation_20260518_154827/ablation.json`,
      writeup in DONE.md.
      **Hybrid-NoConsist training-side ablation (2026-05-18):**
      `research/scripts/export_pcsp_onnx_ablations.py` exports both `full`
      and `no_consist` v3 checkpoints to ONNX side-by-side; the
      `research/scripts/swap_ue5_onnx.py <tag>` utility copies the
      selected pair into `Content/PCSP/Models/pcsp_actor.onnx` and
      `Content/PCSP/Data/persona_embeddings.json` and writes
      `active_ablation.txt` for session tagging. Paired 64-agent PIE runs
      under identical `HybridPCSP` CVar mode but different ONNX weights:
      Full (session `20260518_171226`, 658s) 3,110 int / 0.32% fail /
      reward 1,079.8 / inter-persona ρ 0.379; NoConsist (session
      `20260518_172443`, 681s) 4,005 int / 0.05% fail / reward 1,423.5 /
      inter-persona ρ 0.312. Matched-persona pairing
      (`research/results/ue_sessions/noconsist_ablation_20260518/compare.json`):
      mean Spearman ρ 0.348, mean symmetric KL 1.79 across 64 personas.
      The two checkpoints diverge meaningfully per persona in-engine;
      NoConsist preserves task reward (mirrors v1/v3 "reward hides the
      failure" pattern). Intra-session persona-distance vs action-KL
      Spearman now computed by
      `research/scripts/analyze_persona_distance_vs_kl.py` — see
      Phase 5 entry below.
      **RL-only:** identical to HybridNoPersona at inference (zero
      persona vector); the meaningful RL-only delta is training-time only
      and is covered by the research-side ablation tables.

### Phase 5: Paper And Portfolio Artifacts

- [x] Write the main Korean portfolio document (2026-09-03):
      [../../PORTFOLIO.md](../../PORTFOLIO.md). The narrative covers shared RL,
      independent evaluation, the engine contract, Actor bottlenecks, All-Mass
      scaling, accepted/rejected optimization pilots, and observability. Use
      the 2026-09-02 all-Mass 12-run table as the performance baseline; label
      the animated 2026-09-03 capture as functional evidence only. Document
      window-p95 aggregation, Mass arrivals rather than Actor completions,
      repeated persona IDs, and missing run-specific model/hardware manifests.

- [x] Prepare implementation diagrams
      ([docs/portfolio/diagrams.md](docs/portfolio/diagrams.md) — 5 Mermaid figures:
      system overview, per-decision sequence, BT subtree, three-layer
      affordance, ablation mode switch).
- [ ] Capture rich trajectory clips (requires PIE; use the capture sequence in
      [docs/portfolio/demo/video-runbook.md](docs/portfolio/demo/video-runbook.md)).
- [x] Draft portfolio demo video and HUD plan
      ([docs/portfolio/demo/video-runbook.md](docs/portfolio/demo/video-runbook.md)):
      scenario beats, capture checklist, nearest-agent camera focus via
      `SetViewTargetWithBlend`, and HUD panels for persona, needs,
      decision stack, affordance state, social context, and trajectory events.
- [/] Prepare UE5 screenshots, performance tables, and architecture figures.
      Architecture figures, Actor baseline tables, and the reproducible static
      evidence pack are done
      ([docs/portfolio/visual-evidence.md](docs/portfolio/visual-evidence.md)).
      The pack separates visible Actor performance from the offscreen Mass
      compatibility smoke and generates PNG/SVG from checked-in JSON. Final
      visible Mass sweep, Unreal Insights captures, and PIE screenshots
      (`[NEEDS CAPTURE]` slots X.5, X.6) deferred to next editor session.
- [x] Write portfolio-facing README and 1,024-NPC engineering case study
      (2026-08-31): root `README.md`, `ue/README.md`, and
      [docs/portfolio/mass-1024-scaling.md](docs/portfolio/mass-1024-scaling.md)
      now describe the research-to-runtime architecture, measured Actor
      ceiling, implemented scheduler/Mass intervention, honest limitations,
      runbook, telemetry, and follow-up optimizations.
- [x] Intra-session persona-distance vs action-KL Spearman
      (2026-05-18): `research/scripts/analyze_persona_distance_vs_kl.py`
      reads `summary.json` (per-persona `policy_probs` from logits, with
      fallback to the 20-bin action histogram) plus the active
      `persona_embeddings.json`, and for every persona pair computes
      cosine distance over the 64-d embedding vs symmetric KL over the
      policy distribution. Output: `persona_distance_vs_kl.json` next
      to each session summary (n_pairs, spearman_rho, pearson_r,
      full scatter rows). Results across 64-agent logit-bearing
      sessions: Full PCSP ρ = 0.236 (`noconsist_ablation_20260518`) /
      0.257 (`kl_20260518_151255`); NoConsist ρ = 0.569
      (`noconsist_only_20260518`); BTOnly ρ = 0.007 (sanity — zero
      logits). In-engine ρ is well below the research-side ρ ≈ 0.73
      headline, indicating BT + capacity contention compress the
      persona signal at execution time; NoConsist scoring *higher*
      than Full PCSP here echoes the v1/v3 "reward hides the failure"
      pattern and is worth a limitations-section note.

### Portfolio Engineering Roadmap

Portfolio work is now ordered around engine-facing technical depth first and
demo presentation second. Start with the runtime extensions that make the
simulation more robust and explainable; build the camera/HUD only after those
systems have at least a first pass. All portfolio planning docs live under
`docs/portfolio/`.

| Order | Item | Status | Planning doc | UE5 update target |
| --- | --- | --- | --- | --- |
| 1 | Hybrid policy/BT contract cleanup | Implemented 2026-05-23 | [docs/portfolio/hybrid-stack.md](docs/portfolio/hybrid-stack.md) | centralized action-to-category mapping, routed `Leisure` to Observe, logged active ablation |
| 2 | 1,024-NPC Mass hybrid + path admission | Visible 12-run benchmark complete 2026-09-01; scoped Insights capture and headless export complete 2026-09-02 | [docs/portfolio/mass-1024-scaling.md](docs/portfolio/mass-1024-scaling.md) | `UPCSPPathRequestSchedulerSubsystem`, `APCSPMassSpawner`, Mass fragments/processor, sweep/analyzer telemetry |
| 3 | 1,024-NPC zone expansion + EQS asset | Completed and MCP-verified 2026-09-02: native World Partition serialization contains 96 zones / 592 uniquely owned points, all metadata is normalized and non-spatially-loaded, and `EQS_PCSP_SelectAffordanceZone` is present without modification. The 16-Hero Simulate PIE smoke also passed. | [docs/portfolio/zone-expansion-eqs-editor-guide.md](docs/portfolio/zone-expansion-eqs-editor-guide.md) | 96 zone instances / 592 interaction points in `Map_PCSPDistrict_Portfolio`; `EQS_PCSP_SelectAffordanceZone` |
| 4 | Weighted/EQS affordance congestion handling | First weighted scorer implemented; build and expanded-zone/EQS baseline pending | [docs/portfolio/eqs-congestion.md](docs/portfolio/eqs-congestion.md) | `UPCSPAffordanceSubsystem`, `UBTTask_MoveToAffordance`, EQS query/tests |
| 5 | ZoneGraph/MassCrowd + shared routes + density admission | Async flow-field pilot measured 2026-09-02 and rejected for the current flat/single-goal map; obstacle-rich route benchmark still queued | [docs/portfolio/mass-1024-scaling.md](docs/portfolio/mass-1024-scaling.md) | `UPCSPFlowFieldSubsystem`, future Mass route fragments/processors, shared route cache, predicted-arrival admission telemetry |
| 6 | Async spatial queries + batched ONNX inference | Opt-in implementations and 3-seed Insights pilot complete 2026-09-02; 300-second behavior regression required before default-on | [docs/portfolio/async-inference.md](docs/portfolio/async-inference.md) | `UPCSPSpatialQuerySubsystem`, `UPCSPPolicySubsystem`, next-frame Mass result commit, dynamic `[B,*]` ORT batch |
| 7 | Trajectory observability pipeline extensions | Scaling-aware; sampled Actor/Mass independent-eval bridge live 2026-09-01 | [docs/portfolio/observability.md](docs/portfolio/observability.md) | canonical Actor action index, sampled `mass_trajectories.jsonl`, frozen evaluator adapter, existing scheduler/Mass stats/HUD ring buffer |
| 8 | Agent-camera focus + demo HUD | Native click selection, independent third-person follow, 10 Hz HUD aggregation, global/selected action distributions, trajectory rows, and MCP-authored WBP hierarchy implemented and compiled 2026-09-02; PIE capture validation remains | [docs/portfolio/demo/README.md](docs/portfolio/demo/README.md) | `APCSPDemoPlayerController`, `UPCSPDemoHUDWidgetBase`, `UPCSPAgentDebugViewModel`, HUD widgets, portfolio map |
| 9 | Diagram polish | Refreshed 2026-05-23 | [docs/portfolio/diagrams.md](docs/portfolio/diagrams.md) | diagrams 2, 3, 4, 5 updated for hybrid-stack cleanup |
| 10 | Static visual evidence pack | Implemented 2026-08-31 | [docs/portfolio/visual-evidence.md](docs/portfolio/visual-evidence.md) | reproducible ablation, Actor-scaling, and Mass-runtime PNG/SVG figures |

## Debug Log Map

When verifying a PIE session, check logs in this order. The first three are sufficient for the 16-agent baseline; the rest are scaling diagnostics.

### A. PIE startup — Output Log (Window ▸ Output Log)

Filter on `LogTemp`. Required lines on a healthy boot:

| Source | Expected line | What it confirms |
| --- | --- | --- |
| `UPCSPPolicySubsystem::Initialize` | `PCSPPolicySubsystem: ready (obs=33, persona_dim=64, n_actions=20)` | ONNX model + persona cache loaded. Missing → agents will freeze. |
| `UPCSPTrajectoryLogComponent::GetSessionDir` | `PCSPTrajectoryLog: session dir = .../Saved/PCSP/Logs/<stamp>` | Log directory created; emitted on first agent BeginPlay. |

Error lines that *must not appear*:
- `PCSPPolicySubsystem: pcsp_actor.onnx not found` — export missing.
- `PCSPPolicySubsystem: persona_embeddings.json not found` — export missing.
- `PCSPPolicySubsystem: invalid persona_id=N` — cache too small (need ≥16 personas).
- `BTTask_PCSPDecision: PCSPPolicySubsystem is not ready` — model load failed.

### B. Per-agent behavior — `Saved/PCSP/Logs/<stamp>/agent_p<id>_*.jsonl`

One file per spawned agent. Each line is a JSON object. Use these to answer Phase 4 verification questions:

| Question | jq / grep recipe |
| --- | --- |
| Are all 16 personas active? | `ls Saved/PCSP/Logs/<stamp>/` — expect 16 files. |
| Is every agent producing decisions? | `grep -c '"event":"decision"' agent_p*.jsonl` per file. |
| Is the action distribution non-degenerate? | `jq -r 'select(.event=="decision") \| .action' agent_p*.jsonl \| sort \| uniq -c` |
| Are Park (Observe) + Gym (Exercise) reached? | `jq -r 'select(.event=="interaction_complete") \| .category' \| sort \| uniq -c` — both `Observe` and `Exercise` must appear. |
| Reward accumulation per persona | `jq -s 'map(select(.event=="interaction_complete") \| .reward) \| add' agent_p001_*.jsonl` |
| Path-failure rate | `grep -c '"event":"move_failed"' agent_p*.jsonl` vs decision count. |
| Failure-cause breakdown | `jq -r 'select(.event=="move_failed") \| .failure_reason' agent_p*.jsonl \| cut -d: -f1 \| sort \| uniq -c`. Top-level reasons: `FindBestZone`, `path_follow_idle_short`, `pathfinding_request_failed`, `zone_no_free_interaction_slot`, `interaction_slot_reserve_race_lost`. A `FindBestZone:AllCategoryMismatch` spike means a zone class did not register — usually World Partition streaming. A `path_follow_idle_short:dist=<cm>` cluster well above `AcceptanceRadius` means the `SetReachTestIncludesAgentRadius(false)` call regressed or a slot lies outside NavMesh coverage. |
| Intended-zone audit | `jq -r 'select(.event=="move_failed") \| [.action, .intended_zone] \| @tsv' agent_p*.jsonl \| sort \| uniq -c`. If an action consistently has `intended_zone:""`, the chosen category has no registered zone (streaming/config issue). |
| Reservation contention | `grep -c '"event":"interaction_failed"' agent_p*.jsonl` (look for `reservation_stolen_mid_interaction`). |
| Emergency-branch firing | `jq 'select(.event=="decision" and .urgency > 0.85)' agent_p*.jsonl` |

### C. Runtime spot-checks (PIE)

- **`stat unit`** — frame time at 16 agents (baseline) vs 32 (Phase 4 target).
- **Gameplay Debugger (Apostrophe key)** — Blackboard keys per agent: `DesiredActionType`, `UrgencyScore`, `bAffordanceReserved`. Confirms BT decorator routing.
- **`showdebug ai`** — current MoveTo target / path status; correlates with `move_failed` entries.

### D. Cross-run analysis (offline)

Aggregate across many PIE sessions for the metrics named in [PLAN.md:90](PLAN.md):
- Spearman ρ — load all `decision` rows, group by `persona_id`, compare action histograms vs the research baseline.
- Policy KL — `decision` rows include `logits` (20-dim); `analyze_ue_session.py --compare` produces per-persona symmetric KL between paired sessions.
- Latency — derive from `t` deltas on consecutive `decision` events per agent.

## Working Rules

- Treat this file as the active UE5 task plan.
- Keep `PROPOSAL.md` aligned with the high-level research and product rationale.
- Record completed tasks, decisions, result paths, failed attempts, and retraining requirements in `DONE.md`.
- If a UE5 change alters the Python research API, observation schema, action ontology, or training/export contract, also update `../../research/PLAN.md`.
- Do not commit Unreal-generated build/cache directories unless explicitly required.
