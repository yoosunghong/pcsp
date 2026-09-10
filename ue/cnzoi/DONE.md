# CNZOI UE5 Development Log

Use this file to record completed UE5 work, important implementation decisions, generated artifact paths, failed attempts, and follow-up requirements.

## 2026-09-06 - Runtime inspection, live comparison, and validation pages

- Added five editable portfolio pages and fixed 1600×1000 renders:
  `npc-persona-inspection`, `live-performance-comparison`,
  `why-this-action`, `city-scale-simulation`, and
  `validation-reproducibility`. They share
  `docs/portfolio/assets/portfolio-case-pages.css` and use only actual runtime
  captures or previously checked-in evidence figures.
- Ran a fresh standalone persona-axis sequence at 1,024 Mass NPCs, seed 17,
  1920×1080, VSync off, FPS cap 0, five-second excluded warm-up, and 30-second
  measured windows. All three variants completed and emitted CSV, JSON, PNG,
  and trajectory evidence under
  `Saved/PCSP/Evaluation/EDC694244639003FCDDB748C5334A936/`.
- Completed results were PCSP/Persona `30.06 s / 13.97 FPS / 171.66 ms p95`,
  Needs heuristic `30.02 s / 16.26 FPS / 137.10 ms p95`, and No Persona
  `30.02 s / 5.96 FPS / 197.47 ms p95`, all with zero inference failures.
  These are a one-seed live-HUD capture, not a benchmark conclusion: the first
  run immediately followed the first-launch PSO/DDC rebuild and showed runtime
  priming behavior, while the third screenshot displayed a
  413 MB video-memory-over-budget warning after repeated map travel.
- Selected the clean run-2 screenshot for
  `docs/portfolio/assets/live-performance-source.png`; it retains both
  completed 30-second results on screen. The run-3 screenshot and raw results
  are preserved but not used as clean presentation evidence. A repeated clean
  multi-seed capture is still required for policy-mode performance claims.
- Initial unattended launches failed because the host DDC and default shader
  working directory were not writable. The successful launch used
  `-DDC-ForceMemoryCache` and
  `-ShaderWorkingDir=D:/Github/pcsp/ue/cnzoi/Saved/ShaderWorkingDir`.
  This forced a one-time in-memory rebuild of shaders, 619+ static meshes,
  textures, and distance fields before measurement. The requested human-readable
  series name was also rejected by the existing GUID-only parser, so the
  generated GUID path above is the source of truth.

## 2026-09-06 - Rendering and multithreading portfolio deep dives

- Added `rendering-optimization-comparison.{png,svg}` and a fixed 1600×1000
  `rendering-optimization.png` page. The figure separates the historical
  representation design screen and controlled cylinder/Manny LOD1 A/B from
  the current AnimToTexture ordinary-ISM architecture, so old static-HISM
  timings are not reused as a current VAT performance claim.
- Added `multithreading-optimization-comparison.{png,svg}` and a fixed 1600×1000
  `multithreading-optimization.png` page. It presents scoped Game Thread
  reductions for POD/grid spatial queries and dynamic-batch ONNX, plus the
  observed decision/arrival throughput deltas; it does not present the
  renderer-contaminated aggregate frame values as an FPS result.
- Editable pages are `docs/portfolio/rendering-optimization.html` and
  `docs/portfolio/multithreading-optimization.html`. Reproducible chart source
  is `tools/generate_optimization_deepdives.py`; provenance is recorded in
  `docs/portfolio/assets/portfolio-assets.md`.
- Corrected the environment-optimization page's stale HISM wording to the
  current AnimToTexture ordinary-ISM path. Async spatial and inference remain
  opt-in pending the documented 300-second x 3-seed behavior regression gate.

## 2026-09-06 - Matched Actor+PCSP versus Mass+PCSP scaling comparison

- Ran a new matched 24-session matrix on the current build: Actor+PCSP and
  Mass+PCSP at 128/256/512/1,024 NPCs, seeds 0/1/2, Portfolio map, visible
  800×450 standalone, 60-second wall-clock runs, five-second telemetry warm-up,
  and identical VSync/FPS-cap/throttling settings. All 24 runs exited normally.
- Actor/Mass mean frame costs were `27.015/15.380`, `53.665/21.362`,
  `139.970/32.808`, and `309.445/62.343 ms`; Mass reduced mean cost by
  `1.76x`, `2.51x`, `4.27x`, and `4.96x` respectively.
- Actor window-p95 was `53.199`, `276.788`, `400+`, and `400+ ms`; the last two
  reached the telemetry cap. Mass p95 was `16.983`, `23.341`, `36.206`, and
  `67.751 ms`.
- Regenerated `environment-optimization-summary.{png,svg}` with only matched
  frame-cost evidence: mean, p95, and mean-cost ratio. Movement failures and
  render attribution are absent. Updated the portfolio page and provenance.

## 2026-09-06 - Dieselpunk Texture Resolution Raised To 4096

- Raised `MaxTextureSize` from 2048 to 4096 for the same 24 large textures
  under `/Game/dieselpunk/Textures`; AnimToTexture data textures remain
  untouched. The live UE 5.8 editor saved all 24 assets successfully and a
  final readback reported 4096 plus a 4096x4096 effective resource size for
  every target.
- Created a 24-file pre-change backup at
  `Saved/PCSP/Backups/texture_2048_before_4096_20260906_0415/`; all 24 current
  package hashes differ from their backup copies. The backup is local/ignored
  and can restore the previous 2048-capped packages if needed.
- Added `tools/set_dieselpunk_texture_resolution.py` for repeatable live-editor
  inspection and updates. Current-state manifest:
  `docs/portfolio/texture-cap-20260906.json`.
- The higher cap can increase the top-mip footprint by up to 4x relative to
  2048. The existing 512 MB streaming pool remains unchanged; visible 4 GB GPU
  performance and VRAM acceptance must be rechecked separately.

## 2026-09-06 - Portfolio NPC scaling and rendering-attribution visuals

- Replaced the dark theme in both portfolio graph generators with a coordinated
  white print/slide theme and regenerated six root figures plus six
  persona-training figures. The raw UE5 top-view image was not modified; only
  the overlay veil and information surfaces were lightened.
- Revalidated all source-derived values after regeneration: the paired Insights
  delta remains `Frame +2.691`, `RenderViewFamily +2.683`, `InitViews +2.681`,
  `BasePass +2.617`, and `PCSP_Mass_Execute +0.119 ms`; trajectory decision-row
  counts remain `36/46/31`, and all training arrays retain their original
  hashes. No experiment, evaluation, or research-plan change was made.
- Reframed `docs/portfolio/reward-vs-persona.html` from a paper-like ablation
  sheet into a portfolio design-decision page. The new page explains the reward
  as need recovery + preferred activity + social compatibility, then separates
  persona evidence into traceability, behavioral distinguishability,
  state-conditional consistency, and human readability. Experiment IDs,
  dataset counts, confidence intervals, and p-values were removed from the
  visible page while the source evidence remains documented elsewhere.
- Regenerated `assets/reward-vs-persona.png` at 1600 × 1000 and visually checked
  the fixed page for clipping and section overlap.
- Added reproducible `npc-scaling-non-model-evidence.{png,svg}` from the
  confirmed All-Mass 128/256/512/1,024 three-seed aggregate. It shows frame
  mean/p95, policy-service time per decision, and per-NPC arrival throughput as
  separate claims; it does not assume total model workload is constant.
- Added `npc-rendering-bottleneck-evidence.{png,svg}`. The controlled panel is
  read directly from the paired cylinder/Manny LOD1 Unreal Insights timer CSVs:
  frame `+2.69 ms`, render-view and init-view `+2.68 ms`, BasePass `+2.62 ms`,
  and `PCSP_Mass_Execute +0.12 ms`. Inclusive scopes are labeled as overlapping.
- The representation-design panel recomputes sample-count-weighted frame means
  from the raw skeletal, Leader Pose, LOD0 HISM, and adopted LOD1 HISM session
  telemetry. Those bars are explicitly labeled diagnostic smokes, not matched
  publication A/B evidence.
- Updated the root portfolio, visual-evidence index, representation report,
  README, and asset provenance. The generator remains
  `tools/generate_portfolio_visuals.py` and emits PNG plus SVG.
- Native desktop-app control was unavailable in the authoring environment, so
  the actual Unreal Insights UI screenshot and a new memory-enabled trace remain
  capture work. The existing matched traces are preserved under
  `Saved/Profiling/PCSP/mass_rep_ab_{cylinder,manny}_final/`.

## 2026-09-05 - Action distribution restoration and performance comparison

- Restored bottom-right live population action bars (top five + Other, absolute
  0-100% scale). Details expands all action bars. Persona comparison remains.
- Performance button opens a CPU/FPS comparison table and two overlaid plots.
  PCSP / BT Only / No Persona buttons switch the real policy CVar and start a
  run; P-key changes are detected. Same-mode clicks start another run. Every
  transition drops a five-second warm-up before collecting complete windows.
- Windows GetProcessTimes kernel+user deltas measure normalized whole-process
  CPU. FPS counts world ticks per elapsed wall time. Summary means are weighted
  by window duration; missing CPU reports N/A. PIE includes editor CPU.
- Latest run per mode survives other mode selections. Bounded plotting history
  thins old points after 600 samples; totals remain complete. Distinct CSVs per
  world preserve every window and prevent repeated PIE header/run-ID mixing.
  CSV also records NPC count, resolution, VSync, and FPS cap.
- Mass follow camera holds its pose while Performance is open. This reduces
  camera-induced GPU changes but does not reset the live world or isolate ONNX
  CPU time. BT Only is explicitly identified as needs rules / ONNX off in Mass.
- Initial rendered three-mode smoke passed, and `validate_performance_csv.py`
  verified per-run mode isolation and metric arithmetic. Initial screenshot
  revealed the FPS x-axis label overlapping footer text; spacing was corrected.
  Do not interpret the first short/offscreen trial's FPS deltas as benchmark
  conclusions; it exercised the recorder with a moving follow camera.
- Final Editor Development build and `PCSP.Performance.WallClockAndCPU`
  automation test passed. The final 1280x720 rendered smoke passed three-mode
  recording and layout checks; see `Saved/PCSP/Validation/performance_widgets_final.log`,
  `performance_math_test.log`, `performance_comparison.png`, and `distribution_widget.png`.
- CSV validation passed for session `20260905_184612`, file
  `mode_performance_31E6A5924A4CAF2A95FFCB829EF1FBB7.csv`. The validator accounts
  for millisecond CSV timestamp rounding, including one-frame partial windows.
  Shutdown may emit a final partial window with zero NPCs; exclude teardown
  and unequal measurement conditions from benchmark interpretation.
- The functional smoke invokes the same callbacks bound to the buttons;
  physical mouse hit-testing and packaged Shipping execution remain unverified.


## 2026-09-05 - Portfolio presentation and runtime data staging

- Official Unreal MCP inspected, modified, compiled, and saved
  `WBP_PCSPDemoHUD` (refresh 10 -> 5 Hz), and capped 24 large Dieselpunk
  textures at 2048. Each texture was read back after save; original cap=0,
  streaming remained enabled. Exact list: `docs/portfolio/texture-cap-20260905.json`.
- Native HUD now presents selected/live and pinned/frozen persona evidence,
  full scrollable descriptions, current intent/execution, and up to six grouped
  history rows from 32 recent samples. Pin/clear/camera/details buttons work
  without developer console commands. Details use the same responsive cards.
  Font sizes and geometry compensate for DPI rather than stretching small glyphs.
- Rendering: 512 MB streaming pool limited to VRAM, FXAA, no motion blur,
  no instanced RT geometry, optional selection hull off (HUD arrow retained).
  The 768 MB first trial still showed ~87 MB VRAM over budget at 720p;
  the later 512 MB 1920x1080 capture showed no over-budget warning. This is
  a rendered smoke observation, not a controlled frame-time/VRAM benchmark.
- Removed the pre-existing `t.IdleWhenNotForeground` Engine.ini entry after
  UE 5.8 logged an ensure: cheat CVars are rejected in that config section.
  Unattended validation uses `-ExecCmds="t.IdleWhenNotForeground 0"` instead.
- Staged raw ONNX/persona files as UFS, added Visual map to cook list and
  PCSP materials to always-cook for dynamic path loading. Preserved the user's
  Visual default/startup map. Policy and research API contracts unchanged.
- Editor Development build passed. Initial build caught unsupported
  `UButton::SetIsFocusable`; removed it and rebuilt successfully. Official
  MCP compiled the HUD BP with warnings treated as errors before native rebuild.
- Independent rendered `-game` smoke passed ONNX readiness (33/64/20),
  1,024 Mass entities, HUD needs/history, follow camera, policy label, and
  pin/selection/clear checks. Logs/images: `Saved/PCSP/Validation/portfolio_*.log`
  and `portfolio_1080_comparison.png`. An initial nominal 1080p run resized to
  888x500; the subsequent `-ForceRes` run verified actual 1920x1080 screenshots.
- Uncooked `-game` also emits existing toolset Python initialization errors
  (missing editor-only ToolsetDefinition); this is not a policy failure and
  has not been presented as a clean Shipping run. Shipping package execution,
  visible GPU benchmark, and physical mouse hit-testing remain release gates.
- Final 1280x720 run (`portfolio_final720.log`) passed pin/selection/clear and
  Mass HUD smoke, captured comparison plus details (`portfolio_final_comparison.png`,
  `portfolio_final_details.png`), and exited cleanly. No config ensure or
  ViewModel Accessed None occurred; neither final image has a VRAM warning.
- Reopened the Visual editor with the final native build, restarted official
  MCP on port 8000, compiled the HUD BP with warnings-as-errors again, verified
  persisted RefreshHz=5, and saved it successfully.


## 2026-09-04 - Visual Mass Cadence, District Spawning, Collision, and Render Audit

- Corrected the AnimToTexture walking cadence to use body-relative speed. The
  previous formula scaled both 780 uu/s translation and playback by the 3x body
  scale, producing 3.6x rapid short-looking steps. Normal movement now uses the
  authored 1.2x cadence; 450 uu/s strolls use about 0.69x. Idle remains 1.0x,
  and per-instance autoplay data is refreshed when speed or occupant changes.
- `Map_PCSPDistrict_Portfolio_Visual` now enables affordance-slot-based starts.
  Loaded slots are projected onto reachable NavMesh, filtered for initial body
  overlap, sparse spatial districts receive deterministic NavMesh samples, and
  starts are round-robined across a 4x4 city partition. Local stratified spawning
  remains the fallback for other maps or insufficient loaded anchors.
- Disabled Mass NPC-to-NPC separation and swept-disc contact by default through
  `pcsp.MassAgentCollision=0`; the runtime neighbor grid is not populated in this
  mode. The ISM already has no physical collision response. Its query-only
  Visibility channel remains enabled solely for mouse selection. Setting the
  CVar to 1 restores the diagnostic separation/contact implementation.
- Added `mass_run_config.json` evidence for movement mode, spawn method/anchors,
  exact XY bounds and 4x4 district counts, agent collision, and selection query.
  Final NullRHI functional session `Saved/PCSP/Logs/20260904_044331` spawned
  1,024/1,024 entities from 1,400 valid anchors with district counts
  `[64,64,64,64,64,64,64,64,64,64,64,64,64,64,64,64]` and reported
  `recast_paths_no_agent_collision` / `agent_collision: off`.
- Added a 300 m end-cull distance to every Mass representation ISM. Existing
  shadow, decal, distance-field-lighting, overlap, and navigation influence
  suppression remains active. `r.RayTracing.ForceAllRayTracingEffects=0` prevents
  unused RT effects while retaining the project's current RT-capable DDC.
- Static audit of `Content/dieselpunk` found 2,093 files / 10.81 GiB: textures
  account for 8.13 GiB (121 files over 32 MiB) and geometry 2.63 GiB (13 files
  over 32 MiB). The next measured A/B order is large texture mip limits, the 13
  largest meshes with Nanite/HLOD, spatial streaming, material overdraw, then a
  distant static Mass representation. Full report:
  `docs/portfolio/dieselpunk-city-rendering-optimization.md`.
- Rejected changing the project-wide `r.RayTracing` compile setting: it began
  rebuilding 619 KitBash meshes and the local Zen DDC returned HTTP 507 with only
  about 2.23 GiB free on C: and 5.42 GiB on D:. The setting was restored; do not
  repeat a project-wide derived-data-key change until cache capacity is secured.
- Final UE 5.8 `cnzoiEditor Win64 Development` build succeeded. All four
  `PCSP.Mass` tests passed, covering cadence normalization, collision-off movement,
  separation diagnostics, capacity/duration, missing navigation, and HUD history.
  NullRHI proves spawn/runtime behavior only; a visible same-camera GPU/memory A/B
  and visual stride inspection remain required before making rendering claims.
- No observation schema, action ontology, training export, or evaluation protocol
  changed, so no retraining or `research/PLAN.md` update is required.

## 2026-09-04 - Tripled Mass Bodies and Recast Movement

- Added `RepresentationScale=3` for animated bodies, fallback meshes, and the
  selection overlay. Separation uses a matching 105 cm body radius. Recast and
  NavigationSystem supported-agent clearance are 105 cm radius / 600 cm height.
- Movement speed now preserves body-lengths per second by scaling the 1x CVar
  baselines from each entity's body radius. At 3x, normal movement is 780 uu/s
  (260 x 3) and reachable strolls are 450 uu/s (150 x 3). The later cadence
  repair above keeps playback body-relative at 1.2x / about 0.69x.
- Selection presentation now reads the selected Mass spawner's visual scale.
  The HUD arrow anchor changes from 205 to 615 cm, third-person framing changes
  from 380/210/120 to 1,140/630/360 cm distance/height/look-at, and the ray-pick
  fallback scales its body center and radius. Actor-tier selections use their
  actor scale through the same controller query.
- Replaced shared grid-center routing in `PCSPMassSimulationProcessor` with
  `FPCSPMassNavigation`: cached per-NPC Recast paths, 32 new queries/frame,
  local spatial hashing, separation steering, swept-disc crowd contact limits,
  and `FindMoveAlongSurface` to constrain travel to navigation polygons.
- Mass mode now requests a navigation build. Spawn retries until navigation is
  ready; starts are projected, checked for body clearance and connectivity to
  the origin, with an expanded area for 1,024 enlarged NPCs. Removed the second
  cohort startup delay that made agents miss their first decision window.
- Full/unreachable interaction targets now lead to reachable NavMesh strolls,
  with failed claims released and failed zones cooled down before retrying.
  Dynamic path invalidation and a five-second movement stall trigger retries.
- Disabled the old flow-field builder by default. Its tests and historical
  geometry evidence remain available; no straight-line movement fallback is used.
- Initial 9041/9042/9043 editor builds passed. Suffix builds did not rewrite the
  editor module's import-library dependency, causing isolated launch failures;
  relinking against the matching suffixed library resolved the test harness.
  Four Mass tests then passed. Normal unsuffixed build after clean editor shutdown
  also passed; final contact/spawn/runtime validation is recorded below.
- Preliminary session `Saved/PCSP/Logs/20260904_020752` exposed repeated failures
  for uncovered targets and closely packed arrivals. This prompted reachable
  recovery strolls, connected spawn validation, and swept-disc contact limits.
  Its metrics are not acceptance evidence for the final implementation.
- Visual map external actors were saved through the editor, including updated
  Recast clearance. Existing NavMeshBoundsVolume extends to X=80860 cm, so it
  does not cover the entire expanded city's eastern destinations. The user is
  authoring the navigation volume; cover roads, bridges and all desired slots.
- Research observation/action/training/export contracts are unchanged.
- Final normal build passed. Four tests in `PCSP.Mass` passed, including exact
  overlap escape, hash-cell neighbors, cross-floor exclusion, swept contact,
  missing-NavMesh behavior, reservation admission and history.
  Test log: `Saved/Logs/mass_nav_tests_normal.log`.
- The intermediate 90-second run (`20260904_021321`) had zero overlap samples,
  but dense starts delayed substantial movement for some agents. Increased
  initial grid spacing to five body radii and minimum sampled spawn spacing
  to four body radii, leaving passages between the enlarged bodies.
- Final 30-second NullRHI functional run: `Saved/PCSP/Logs/20260904_021636`;
  reproduce its analysis with `python tools/validate_mass_navigation.py
  Saved/PCSP/Logs/20260904_021636`. All 1,024 moved over 100 cm within the run;
  no overlapping pair samples (1 cm log-rounding tolerance). This is movement
  evidence, not an FPS benchmark or proof that every city slot is reachable.
- Speed follow-up validation: the normal Editor build and all four `PCSP.Mass`
  tests passed (`Saved/Logs/mass_speed_tests.log`). The 20-second Visual-map run
  `Saved/PCSP/Logs/20260904_023957` spawned 1,024 entities at scale 3/radius
  105 cm. Its 17,459 moving audit rows contain only 780 and 450 uu/s; all 1,024
  entities reported moving samples, and 19 sampled frames had zero overlaps.
- Selection/camera follow-up build passed. The 1,024-NPC Visual-map demo smoke
  passed in `Saved/Logs/mass_scaled_selection_camera.log`, reporting
  `visual_scale=3.00`, `marker_height=615.0`, `camera_distance=1140.0`,
  `camera_height=630.0`, and `look_at_height=360.0`.

## 2026-09-04 - Shared City Routes and Verified NPC Arrivals

- Replaced the old origin-centered, NavMesh-dependent category flow pilot with
  authored city geometry and one shared reverse field per exact Zone ID.
  58 tagged walkable rectangles and 158 tagged obstacles cover roads, sidewalks,
  courts, three bridge decks/walks, 40 buildings, 104 furniture actors, and
  14 parapets. Water/canal-bottom actors are excluded. Tags persist in the
  Visual map's World Partition external actor packages.
- Grid is 292 x 288 at 200 cm/cell; obstacle padding is 230 cm. The geometry
  snapshot runs on GT and 118 reverse fields build once on a worker. Runtime
  uses shared lookups and retained cell-center waypoints, forbids diagonal
  corner cutting, follows surface height, and finishes at the exact reserved
  slot. Unavailable slots wait instead of starting an unsafe random stroll.
- Added a geometry-checked local connector for safe exact points that land in
  conservatively blocked cells: 4-cell search, 80 cm obstacle clearance, 50 cm
  support samples. This handles both initial positions and departures from
  exact slots without teleportation or a straight-line fallback through water.
  Spawner remains at (65850, -12650, 1.5) cm; radius 1700 -> 1600 gives a
  32 x 32 m start area inside the route grid. NPC count and authored slots unchanged.
- Full normal Editor build succeeded. PCSP.Navigation.CityRouteFields passed,
  including bridge access, disconnected goals, corner cutting, exact Zone/slot
  selection, safe grid entry, and refusal to recover through an obstacle.
  Report: Saved/PCSP/CityNavigation/automation-final; log: automation-final.log.
- Final NullRHI fixed-step functional session: Saved/PCSP/Logs/20260904_005608,
  1,024 NPCs, 300-second run / 299.033 s last sample, 306,176 position samples,
  2,157 arrivals, 5,494,771 route movement steps, zero route_blocked counts,
  zero obstacle intrusions at 40 cm clearance, and zero unsupported positions.
  441 unique NPCs crossed the canal. South/middle/north bridges had 364/80/17
  users (these sets can overlap); 88 distinct zones were sampled interacting.
  Actual runtime snapshot: 60,863 walkable cells, 118 fields, worker 523.70 ms.
  Editor AABBs yield a more conservative 60,000 connected cells; all 118 Zone
  centers and three bridges connect to the spawn. These counts are not FPS claims.
- Separate rendered Simulate PIE session Saved/PCSP/Logs/20260904_005649 ran to
  159.134 s, recorded 151 arrivals / 335,063 route movement steps / zero
  route_blocked counts, and was stopped cleanly. Screenshot:
  docs/portfolio/assets/dieselpunk-city-npc-routes-20260904.png.
- Earlier run 20260904_004947 reached 2,061 destinations / 430 canal crossings
  without geometry violations, but exposed excluded-cell starts/departures.
  Corrected the connector and spawn area, then repeated the full functional
  gate above. An earlier center-field version also required an explicit finish
  rectangle to avoid stopping before distant slots in the same zone.
- Editor restart initially paused at Restore Packages. Automatic approval
  rejected an untargeted ESC. Confirmed Save All=true; all 98 restore candidates
  were older than their current saved packages. Preserved both versions with
  SHA-256 verification under Saved/PCSP/CityNavigation/restore-candidates-preserved,
  then closed only the verified restore dialog after re-review. Later restart
  used a normal editor close and completed without recovery. The official MCP
  server was restarted with -ModelContextProtocolStartServer; sessions renewed.
- Guide: docs/portfolio/dieselpunk-city-navigation.md. Tools:
  tag_dieselpunk_navigation.py, invoke_dieselpunk_navigation_tags.ps1, and
  verify_city_route_geometry.py. runtime-route-validation.json,
  geometry-validation.json, pie-final-summary.json and run logs are in
  Saved/PCSP/CityNavigation. Opt-in -PCSP_CityRouteAudit records all-NPC 1Hz
  positions in mass_routes.jsonl; mass_stats now includes route_moves/route_blocked.
- Remaining scope: NPC-to-NPC separation, dynamic obstacles, Actor/BT Recast
  routing, and rendering optimization. PCG regeneration needs obstacle tags on
  replacement actors and a fresh PIE build of the fields. Source changes from
  the earlier persona/needs/HUD work were preserved; the research observation,
  action, training/export and evaluation contracts were not changed here.

## 2026-09-04 - City Affordances for 1,024 Mass NPCs

- Relocated all 118 existing affordance zones / 1,704 slots from the Visual
  map's original test floor into the 16 city blocks (7-9 zones per block).
  Preserved actor identities, unique Gameplay Tags / VisualizationIndex values,
  categories, capacities, and interaction durations. No new per-slot Actors:
  native InteractionSlots arrays and HISM markers remain in use.
- Authored rectangular slot grids with 280 cm minimum center spacing and
  ground-aligned local Z. Zone bounds exclude building AABBs by 180 cm and
  furniture AABBs by 100 cm; slots are another 140 cm inside those bounds.
  All zones are non-spatially-loaded with automatic grid regeneration disabled.
  Outliner: PCSP_City/09_Affordances/<block>.
- Moved the existing Actor=0 / Mass=1024 Spawner to the hotel's paved courtyard,
  (65850, -12650, 1.5) cm, SpawnRadius=1700 cm. Its actual square start area is
  34 x 34 m; the rectangle plus 200 cm clearance intersects no building or prop
  AABB. Existing count and seed remain unchanged. Folder: PCSP_City/10_NPC_Spawn.
  City folder total is now 417 actors, including 298 background/PCG actors.
- Saved all packages and reopened the map. All 118 zones / 1,704 world-space
  slots passed identity, capacity, transform, and persistence checks. All 354
  sampled ground traces matched the authored sidewalk/courtyard elevations.
  Reload Map Check: zero errors / warnings.
- Simulate PIE session Saved/PCSP/Logs/20260904_000847 confirmed 1,024 Mass
  entities, 118 registered zones, and total capacity 1,704. Nine occupancy
  samples reached 587 reservations at t=9.4 s with zero over-capacity zones.
  These include en-route reservations; the short run recorded zero arrivals.
  It is not a navigation or FPS acceptance test. PIE was stopped afterward.
- Remaining: current Mass movement is straight-line, FlowField is disabled,
  and a RecastNavMesh-missing CrowdManager warning remains. Road/bridge routing,
  building avoidance, arrival validation, and the existing GPU-memory limitation
  need separate work. PCG building edits do not automatically relocate zones.
- Backup: Saved/PCSP/CityAffordances/backup_20260903_235145, 462 map/external
  actor/object files copied and SHA-256 verified. Evidence in the parent folder:
  inventory-before.json, city-geometry.json, layout-plan.json,
  validation-summary.json, pie-occupancy-summary.json, pie-run_config.json,
  pie-zone_occupancy.jsonl, pie-mass_stats.jsonl, and pie-cnzoi.log. An initial
  telemetry lookup used an older session directory; corrected to the new session
  above before interpreting results. Saved artifacts remain outside Git.
- Guide: docs/portfolio/dieselpunk-city-affordances.md. Reusable scripts:
  tools/plan_city_affordances.py, tools/apply_city_affordances.py,
  tools/verify_city_affordances.py and the two invoke_city_affordance_*.ps1
  wrappers. No C++ or research API/training contract changes in this task.
- Final editor viewport: docs/portfolio/assets/dieselpunk-city-affordances-20260904.png.

## 2026-09-03 - Fourfold City Expansion and Editable PCG

- Expanded the same Visual map from 288 x 286 m to 576 x 572 m, exactly 4x
  footprint, with 16 blocks. The original PCSP gameplay floor is excluded from
  that area calculation. Added a 18 m wide canal, quays, three road bridges,
  three KitBash covered walkways, and an arch across the northern canal.
- City now contains 40 building Blueprint actors (previously five): 29 generated
  by PCG and 11 curated. Added Parliament, Riveter Church, Hotel Noir, Tram
  Station, Ironside Distillery, Museum, and six repeated building families.
  There are 104 furniture actors and 298 actors in the city folder in total.
- Created `/Game/PCSP/City/PCG/PCG_DieselpunkCityBlock` with 20 nodes / 20 edges
  and six `City_PCG_*` volumes. Twelve exposed parameters drive actual graph
  inputs: class, area, spacing, fill, seed, rotation, min/max offset, min/max
  uniform scale, generated label, and spatial streaming. Explicitly enabled
  PCG in `cnzoi.uproject`; the editor already had the module loaded.
- Graph uses native points grid, random choice, transform, two attribute copies,
  and Spawn Actor by class attribute. Source KitBash Blueprints/meshes remain
  unchanged. `SpatiallyLoaded=false` is applied on each regeneration, so the
  generated buildings survive editor map reopen without manual cell loading.
- Fixed initial XY overlaps in ApartmentsStore / FactoryApartments by widening
  lot spacing and adjusting scale/center. Also aligned bridge sidewalks and
  parapet openings and removed a duplicate coplanar quay surface.
- PCG control checks: Apartments 9 -> 5 -> 9 for FillRatio 1 -> 0.5 -> 1;
  LotSpacing.X 2800 -> 4000 -> 2800 yields 9 -> 6 -> 9. The native Random Choice
  source uses CeilToInt, explaining the initially expected four vs actual five
  half-filled lots. Seeds 7/99 produced different positions with +/-100 cm
  jitter. Restored all final presets, including zero jitter and seed 152.
- A streamed-actor override initially used a skill-example selector wrapper
  that the native tool interpreted literally. Replaced it with the plain
  `SpatiallyLoaded` attribute name; subsequent generation and property reads
  confirmed false. Some immediate Execute calls raced editor auto-generation;
  after it completed, explicit execution returned no issues. Initial KitBash
  loads emitted existing empty-engine-version warnings; source assets were not
  resaved just to suppress them.
- Saved all packages and reopened the map. All 40 buildings, 29 PCG outputs,
  six volumes, 104 props, and 298 city actors persisted. Reload Map Check:
  zero errors / warnings. Before and after reload: zero building-building and
  furniture-building XY AABB intersections. Twelve vertical traces match road,
  sidewalk, bridge, and water elevations. Graph parameters were read back after
  reload. No new runtime navigation or performance gate was claimed.
- Actual remaining performance limitation: final viewport captures reported
  video memory over budget (approximately 0.8-1.3 GB). Editor log identifies a
  4004 MB dedicated-VRAM adapter. Existing texture pool was already 400 MB and
  Streaming.Boost about 0.3; sampled large Parliament/Distillery meshes had
  Nanite disabled. Further lowering unrelated global settings was not applied.
  Follow-up: optimize city geometry with appropriate Nanite/LOD/proxy assets,
  HLOD/streaming, and profile on this hardware. The warning was not hidden.
- Backup before expansion: `Saved/PCSP/CityExpansion/backup_v1_20260903_230614/`,
  244 files copied and SHA-256 checked. Evidence is in `Saved/PCSP/CityExpansion/`,
  including `validation-after-reload.json`, `pcg-control-tests.json`,
  `seed-tests.json`, `persisted-settings.json`, and `graph-final.json`.
- Editing guide: `docs/portfolio/dieselpunk-city-pcg.md`. Authoring and validation
  scripts: `tools/build_dieselpunk_pcg.py`, `tools/expand_dieselpunk_city.py`,
  `tools/verify_dieselpunk_expansion.py`. Raw viewport screenshots are under
  `docs/portfolio/assets/dieselpunk-city-expanded-overview-20260903.png` and
  `dieselpunk-city-canal-20260903.png`. Research contracts and training unchanged.

## 2026-09-03 - Dieselpunk Visual District Authored Through MCP

- Worked in `Map_PCSPDistrict_Portfolio_Visual`, using the official local UE 5.8
  MCP endpoint. Extended the ground eastward around the user's three dieselpunk
  buildings: 288 x 286 m roadbed, four paved blocks, cross streets, ring roads,
  sidewalks, stone crossings, and a link to the existing PCSP demo floor.
- Added 70 actors: 34 ground/paving pieces, Library and General Store buildings,
  28 lamps, three benches, a bus stop, phone booth, and armillary sculpture.
  Organized these and the three existing landmarks in `PCSP_City` folders.
- Lowered Observatory from Z=3870 to 0; moved Casino south by 2200 cm while
  retaining Yaw=90; moved Factory HQ east by 5200 cm. All five building footprints
  fit their blocks. Prototype city actors are non-spatially loaded.
- Created 18 material instances under `Content/PCSP/City/Materials`, reusing the
  pack's cobblestone and sidewalk materials. Original dieselpunk assets and
  gameplay/research code were not edited.
- Saved through `AssetTools.save_assets([])` because `SceneTools.save_actor`
  rejected newly created World Partition external-actor packages. A map-only save
  returned success but did not save the new external actors. Saved packages and
  reloaded the Visual map; engine reload Map Check reported 0 errors / 0 warnings.
- Initial actor-wide inspection exceeded its 60-second timeout. Continued with
  smaller batches. Transform tools filled omitted fields with identity, briefly
  resetting the casino's rotation; full explicit transforms restored it before
  final saving. Placement overlap checks also caught and corrected the initial
  shop/library, armillary/shop, and north-lamp/factory spacing.
- Live checks: five buildings, 34 furniture actors, no building-building or
  furniture-building XY AABB overlaps; all 11 sampled road/sidewalk/link positions
  have ground collision. The same checks passed after level reload, with 70
  generated actors / 73 total city-folder actors retained. No PIE navigation or
  performance claim is made.
- Pre-edit disk backup: `Saved/PCSP/CityAuthoring/backup_20260903_223821/`;
  146 files copied and SHA-256 verified. The original disk snapshot's files remain
  unchanged. Pre-edit in-memory landmark transforms are separately preserved in
  `key-actors-before.json`; those are necessary to reproduce the user's initial
  unsaved three-building arrangement. External actor file count grew 133 -> 206.
- Reusable tool script: `tools/build_dieselpunk_city.py`; editor usage, design,
  backups, and next steps: `docs/portfolio/dieselpunk-city-authoring.md`.
  Detailed MCP outputs and captures are in `Saved/PCSP/CityAuthoring/`.
  Final unedited viewport captures are also in `docs/portfolio/assets/` as
  `dieselpunk-city-overview-20260903.png` and `dieselpunk-city-street-20260903.png`.
- This is an editor-authored visual district, with no new PCG graph or runtime
  generation. Follow-up: city affordance entrances and obstacle-aware Mass paths,
  then fresh runtime navigation/performance validation; spline/PCG expansion when
  more districts are needed. Research observation/action/export contracts remain
  unchanged, so no retraining or research PLAN update is required.

## 2026-09-03 - Mixed Portfolio Layout Saved / Repeated PIE Passed

- After the user closed the Editor, backed up and SHA-256 verified all 126
  current map files (map + 113 external actors + 12 external objects) in
  `Saved/PCSP/Backups/portfolio_mixed_layout_20260903_021533/`.
  The current user-authored state, including an already absent external actor,
  was preserved; no deleted actor was restored or additional actor removed.
- Normal `cnzoiEditor Win64 Development -NoHotReloadFromIDE` build succeeded.
  UBT cleaned its generated hot-reload artifacts and the module manifest now
  references the regular `UnrealEditor-cnzoi.dll` / `cnzoiEditor.dll` binaries.
- Applied `PCSPZoneLayout -RelayoutCompact -LayoutSeed=17`. Exactly 97 backed-up
  packages changed (96 zone actors + map); the other 29 files are byte-identical.
  Apply log: `Saved/Logs/PCSPMixedLayoutApply_20260903.log`.
- Independent read-only `tools/validate_mixed_layout.py` reload passed: 96
  zones, 592 slots, 0 horizontal/vertical same-category neighbors, 0 zone
  overlaps, minimum slot distance 420 cm, unique indices 0–95, and no legacy
  interaction points. The placed spawner has Actor=0 / Mass=1024 without CLI
  count overrides. Log: `Saved/Logs/PCSPMixedLayoutReload_20260903.log`.
  Both commandlets exit 1 because of the pre-existing cheat-CVar/GameFeatureData
  configuration errors described below; both explicit PCSP audits passed.
- `tools/validate_mass_pie.py` ran two real PIE start/stop cycles in a dedicated
  hidden NullRHI Editor, then closed only that owned test process. Both cycles
  verified 1,024 Mass / zero Actor NPCs, 96 zones, eight needs, eight recent
  decisions, selection cycling, enabled camera button and its native click
  callback toggling both ways, and the WBP-local ViewModel binding. Both PIE
  worlds tore down; the full log contains zero Accessed None errors.
  Log: `Saved/Logs/PCSPMassPIE_20260903.log` (`result=PASS cycles=2`).
  This tests the UMG callback path, not physical mouse hit testing or GPU output.
- The isolated 1080p render (`-ForceRes`, `r.SetRes 1920x1080w`) established
  that prior text overflow was not just a small-viewport artifact. Added
  compact native text sizing (14 pt authored / 13 pt generated), fill-width
  needs bars, accurate Mass pipeline/history headings, and decision-only Mass
  rows without fictitious reward zeros. No widget asset was resaved. A compile
  warning treated as error (local `Slot` hiding `UWidget::Slot`) was fixed;
  normal build and two additional PIE cycles passed afterward.
  Final PIE log: `Saved/Logs/PCSPMassPIEFinal_20260903.log`.
- Python widget-template inspection was abandoned after UE rejected access to
  its protected `WidgetTree`; no property/asset was mutated. The temporary
  failing inspection script was removed; native widget traversal supplies the
  presentation adjustment. Logs: `PCSPHudLayoutInspect*_20260903.log`.
- Final narrow flow values use 12 pt; the unassigned diagram image is collapsed
  only in the legacy decision-stack card (assigned images are preserved).
  Mass failure counts now read `n/a`, not an unmeasured zero. The final normal
  Editor build succeeded, and the 20-second isolated 1080p run exited 0 with
  `PCSPMassDemoSmoke: result=PASS`, zero Accessed None errors, 1,024 category
  bodies, GPU animation, and no head indicators. Readable cards and no blank
  diagram were visually confirmed in `Saved/PCSP/Validation/mass_demo_frame_02.png`.
  Log: `Saved/Logs/PCSPMassPresentationFinal_20260903.log`.
  Earlier captures are preserved in `pre_mixed_layout_captures/`,
  `pre_compact_hud_captures/`, and `pre_flow_hud_captures/` under Validation.
- Isolated earlier 1080p runs also showed VRAM-budget warnings, so Editor
  concurrency is not a sufficient explanation. No GPU optimization or FPS
  claim is made; a visible memory/performance benchmark, physical mouse hit
  testing, and lower-resolution presentation checks remain follow-ups.
- The asset-modification-wizard safety workflow supplied the backup, preview,
  scoped native save, and independent reload checks; no raw binary edits used.

## 2026-09-03 - Mass-first Runtime Repair (implemented; presentation follow-up remains)

- Root causes: Mass selected only the nearest category-matching zone and used
  `StableIndex % SlotCount` without reservations; interaction duration was a
  fixed 2–2.75 seconds; the HUD/ViewModel/controller only enumerated Actor NPCs;
  the Mass mesh was a static reference pose; the WBP-local ViewModel was never
  assigned and its Blueprint timer survived native timer cleanup.
- Added per-entity slot ownership and bounded eight-decision history. The
  processor reconstructs claims before decisions, excludes full zones, scores
  distance plus congestion, claims an exact free slot immediately, and releases
  it on completion. Recently completed zones receive a revisit penalty so a
  repeated semantic action can execute at another venue instead of looking like
  an indefinitely extended stay. Shared flow directions are used only when
  their destination matches the reserved venue. Decision admission now rotates
  through stable indices, so low-index full-zone retries cannot starve later
  entities; the observation's population value is counted before chunk processing.
- Mass interaction duration uses `pcsp.MassInteractionDurationScale=0.35`:
  authored 3-second slots become 1.05–1.21 seconds, clamped to 0.65–1.6 seconds.
  Zone occupancy now includes Mass reservations as well as Actor reservations.
- Added Mass snapshot reads to the ViewModel and HUD, stable-index click/Tab
  selection, nearest-Mass focus, and a camera proxy that follows a fragment
  transform without creating/possessing a Character. Mass social-neighbor data
  is explicitly shown as not sampled instead of presenting zero as a measurement.
- Bound the legacy Blueprint `ViewModel` property before Blueprint Construct;
  the first smoke exposed an earlier Blueprint/level-created HUD path, so the
  controller now lazily creates its ViewModel before Blueprint BeginPlay and
  adopts an existing HUD rather than creating a duplicate. The native HUD also
  resolves a missing owning player and retains a safe fallback adapter. Teardown
  clears all widget-owned timers and removes the HUD on controller EndPlay.
  Needs warning colors now mark low (not satisfied/high) values red.
- Enabled Epic's AnimToTexture runtime. Read-only inspection confirmed the
  bundled bone-animation mesh/data/material, idle clip 0 (frames 0–319), walk
  clip 2 (339–428), and the `BodyColor` vector parameter. ISM groups are split
  by category and idle/walk state; GPU autoplay and category MIDs replace all
  head spheres. A static procedural fallback remains if the paired VAT assets
  are unavailable; no performance result is claimed for the new representation.
- The first HISM capture showed a transient missing body during group/tree
  rebuilds. Dynamic crowd groups now use ordinary ISM (GPU instance culling)
  instead of rebuilding a hierarchical tree as moving entities change groups.
  Both final consecutive captures contain the selected animated NPC.
- The requested Unity path was not present. The matching PCSP scaling city was
  found under `D:/Github/careful-what-you-say/unity/AstroPopsLocal`; the inspected
  `PuzzleScspCitySceneBuilder.cs`, `ScspCityView.cs`, `ScspCity.cs`, and
  `ScspDistrict.cs` supplied the deterministic seeded/interleaved-venue and
  instanced-material presentation patterns. No Unity files were modified.
- Added a seeded layout permutation with neighbor repair and three automation
  tests covering full-zone exclusion/short duration, Mass HUD history rollover,
  and reproducible category mixing without losing authored zones.
- First build compiled all changed C++ files, but linking the unsuffixed DLLs
  failed with LNK1104 because UnrealEditor PID 2140 holds them open. A separate
  suffix build was used for safe verification. A later fair-admission edit had
  duplicate declarations; these were removed and the final suffix-9475 Editor
  build succeeded. The open editor was not closed and no Portfolio map package
  was overwritten in this repair.
- Final validation:
  - `PCSP.Layout.SeededCategoryMix`, `PCSP.Mass.CapacityAndDuration`, and
    `PCSP.Mass.HudHistoryRing` all passed. The capacity test also checks that all
    1,024 indices receive one admission per rotation and that the window wraps.
    Report: `Saved/PCSP/Validation/mass_demo_20260903_final/`; log:
    `Saved/Logs/PCSPMassAutomationFinal_20260903.log`.
  - Layout seed 17 dry-run: 96 zones / 592 slots, 0 same-category neighbor pairs,
    0 zone overlaps, 0 slot overlaps, minimum slot distance 420 cm. Proposed
    extent 29,190 x 15,480 cm. Log: `Saved/Logs/PCSPMixedLayoutDryRun_20260903.log`.
    Exit code 1 is from the pre-existing Engine.ini cheat-CVar and GameFeatureData
    Asset Manager errors; the explicit PCSP dry-run audit passed without saving.
  - Final offscreen session `Saved/PCSP/Logs/20260903_020011/` completed its
    25-second run and clean shutdown. It logged 1,024 category-tinted bodies,
    `gpu_animation=true`, `head_indicators=0`, and zero `Accessed None` warnings.
    Opt-in `-PCSP_DemoSmoke` selected Mass #0 and verified needs=8, history=1,
    HUD agents=1024, and follow camera=true. Log:
    `Saved/Logs/PCSPMassISMSmoke_20260903.log`.
  - `Saved/PCSP/Validation/mass_demo_frame_01.png` and `_02.png` show category
    body tint and changing walk poses. Actual captured viewport was 888x500
    despite requested 1080p; HUD text overlaps at this small size. A VRAM budget
    warning was visible while the editor remained open. Its cause has not been
    isolated, and these captures must not be cited as FPS evidence.
- Map save/reload and real PIE start/stop gates were subsequently passed (see
  above). Remaining presentation checks: physical mouse hit testing, final HUD
  layout, and visible-run GPU memory/performance.
- Research observation/action/export/evaluation contracts are unchanged; old
  static-HISM performance evidence must not be reused for the new VAT renderer.

## 2026-09-02 - Compact Portfolio Layout + Interactive Demo HUD

- Added `UPCSPDemoHUDWidgetBase`, a 10 Hz native HUD adapter that aggregates
  the live Actor population into action-distribution rows and exposes the
  selected NPC's persona, eight needs, decision/target state, occupancy,
  distance, social context, recent action distribution, and trajectory.
- Extended `APCSPDemoPlayerController` with automatic HUD creation,
  click-to-select, explicit follow-camera on/off, and selection/camera state
  separation. Added a non-possessing spring-arm camera to
  `APCSPAgentCharacter`, so observation never steals the agent from its AI
  controller. `APCSPSimGameMode` now defaults to the demo player controller.
- Used the official Unreal MCP to reparent `WBP_PCSPDemoHUD` to the native base,
  add dynamic distribution/trajectory containers and `Btn_ToggleCamera`,
  reorganize the 1920x1080 anchors, apply translucent navy panel styling, fix
  the `Fitness` label, and compile/save all nine HUD widget assets. Saved
  `DemoHudClass = WBP_PCSPDemoHUD` on `BP_PCSPDemoPlayerController`.
- Reworked `PCSPZoneLayout -RelayoutCompact`: category instances are
  interleaved across a deterministic 12x8 grid at 2,500 x 2,000 cm spacing.
  Dry-run validation reduced the measured layout from `67,690 x 40,680 cm` to
  `29,190 x 15,690 cm` while retaining 96 zones / 592 slots, zero zone or slot
  overlaps, and 420 cm minimum slot-center distance.
- After the editor was closed, backed up the Portfolio map plus all 114 World
  Partition external-actor packages under
  `Saved/PCSP/Backups/portfolio_compact_layout_20260903_001309/`, then applied
  the compact layout. A fresh commandlet reload confirmed the saved extent is
  `29,190 x 15,690 cm` with 96 zones / 592 slots, zero zone or slot overlaps,
  and 420 cm minimum slot-center distance.
- UE 5.8 `cnzoiEditor` suffix build 7313 succeeded. All nine widget blueprints
  also passed `CompileWidgetBlueprint`. Existing project-level Engine.ini cheat
  CVar and GameFeatureData Asset Manager errors still make successful
  commandlets report process exit code 1; use the explicit PCSP audit lines.

## 2026-09-02 - Wide Portfolio Rebuild And All-Mass Benchmark

- Added a guarded `PCSPZoneLayout -RelayoutWide` workflow with a read-only
  `-DryRun`, Portfolio-map path guard, exact 96-Zone / 592-slot preconditions,
  deterministic category/tag ordering, and geometric overlap validation.
- Backed up the pre-change map and 114 World Partition external-actor packages
  under `Saved/PCSP/Backups/portfolio_wide_layout_20260902_180814/` before any
  binary asset write.
- Rebuilt the Portfolio destination layout from `14,210 × 13,590 cm` to
  `67,690 × 40,680 cm` as a 12×8 district. Zone overlap pairs changed
  `66 -> 0`, slot overlap pairs `33 -> 0`, and minimum slot-center distance
  `40 -> 420 cm`. All Zone slots now use centered 420-cm grids, 320-cm bounds
  padding, and 72-cm Zone-colored floor markers. A post-save reload audit
  reproduced the zero-overlap result.
- Extended `run_scaling_sweep.ps1` with explicit `-MapPath` and
  `-RenderOffscreen` routing. Corrected `analyze_scaling_sweep.py` so all-Mass
  sessions derive duration from frame/Mass telemetry instead of reporting zero
  duration and zero throughput when Actor logs are absent.
- Ran the stable visible Portfolio scaling matrix at 128/256/512/1,024 Mass
  entities × seeds 0/1/2 × 60 seconds. All 12 final sessions used 0 Actor NPCs,
  emitted 60 frame windows, exited code 0, and required no watchdog kill.
  At 1,024 entities, frame mean was `28.42 ± 0.17 ms`, frame p95
  `34.14 ± 0.11 ms`, arrival throughput `4.76 ± 0.06/NPC/min`, and Mass policy
  mean `178.8 ± 0.6 us`. Aggregate artifacts are under
  `research/results/ue_sessions/all_mass_portfolio_20260902/`.
- Rejected initial hidden/offscreen and seven visible measurements contaminated
  by the platform's approximately 15-FPS unfocused throttle. Replacements used
  `t.IdleWhenNotForeground=0`, `Slate.bAllowThrottling=0`, `r.VSync=0`, and
  `t.MaxFPS=0`; the final per-scale frame-mean standard deviation is
  `0.07–0.17 ms`.

## 2026-09-02 - All-Mass Contract, Goal Beacons, And Integrated Zone Slots

- Replaced the 1,024-NPC mixed-tier contract with an all-Mass invariant. Any
  non-zero Mass run folds configured Actor NPCs into the Mass count, preserving
  the requested total; `run_scaling_sweep.ps1 -MassHybrid` now requires
  `HeroAgentCount=0`.
- Added one small HISM goal beacon per Mass NPC. Beacons are grouped by the live
  destination Zone visualization ID and use the exact same stable color as that
  Zone's floor slots, making destination distribution visible at population scale.
- Moved capacity, reservation, duration, target position, automatic grid layout,
  automatic bounds sizing, and circular Zone-unique floor markers into
  `APCSPAffordanceZone::InteractionSlots`. Actor BT tasks and Mass zone-level
  movement now target these slots without depending on standalone point actors.
- Generalized `UPCSPZoneLayoutCommandlet -Repair` and completed both migrations:
  `Map_PCSPDistrict_M` is 10 uniquely colored Zones/210 persisted slots/0 Point
  actors; `Map_PCSPDistrict_Portfolio` is 96/592/0. External actor packages are
  deleted only after their map-specific package prefix is verified.
- UE 5.8 Editor and Development Game targets link successfully. A 1,024-NPC
  offscreen Editor `-game` smoke logged `actor_debug_agents=0` and
  `mass_entities=1024`; at six seconds it logged `goal indicators=1024`,
  `active_goal_zones=6`, and `no_goal=0`. A screenshot verified the integrated
  circular floor markers and removal of the former standalone Point visuals.
  Commandlets still return process code 1 after successful PCSP work because of
  pre-existing Engine.ini cheat-CVar and GameFeatureData Asset Manager errors.

## 2026-05-13

- Created UE5-specific planning documents under `ue/cnzoi/`.
- Established `PLAN.md` as the active UE5 implementation plan.
- Established `PROPOSAL.md` as the high-level rationale and scope document.
- Established `DONE.md` as the UE5 progress and decision log.

## Decision Log

Record durable decisions here.

| Date | Decision | Rationale | Follow-up |
| --- | --- | --- | --- |
| 2026-05-13 | Use a hybrid PCSP + Behavior Tree architecture. | PCSP should choose high-level persona-conditioned intent while UE5 handles tactical execution, navigation, interaction, and recovery. | Specify the Blackboard contract before implementing BT tasks. |
| 2026-05-13 | Treat movement as a Behavior Tree execution node, not a policy action. | This keeps policy capacity focused on semantic behavior and leaves continuous movement to NavMesh and BT logic. | Implement `UBTTask_MoveToAffordance`. |
| 2026-05-13 | Target 16 agents for the main prototype and 32-64 agents for stress testing. | This matches and extends the research scale while demonstrating engine integration value. | Add performance and latency logging early. |
| 2026-08-31 | Scale beyond 64 high-fidelity NPCs with a two-tier Actor/Mass architecture. | The 128-Actor sweep failed primarily in bursty NavMesh submission, while ONNX inference remained inexpensive. Keeping every NPC as a Character/Controller/BT is the wrong cost model for 1,024 entities. | Preserve 16-32 hero Actors and move background semantic state into Mass chunks. |
| 2026-08-31 | Bound Actor path admission by urgency plus wait age. | Raising Recast limits alone moves the bottleneck; load shaping controls bursts and age prevents starvation. | Validate queue depth/wait in the visible three-seed sweep. |
| 2026-08-31 | Treat straight-line Mass movement as an explicit prototype simulation LOD. | It proves the data-oriented semantic tier without pretending to be production obstacle-aware navigation. | Replace with ZoneGraph/MassCrowd and shared coarse-route caching. |
| 2026-09-01 | Scale authored destinations for the 1,024-NPC district without creating one zone per NPC. | A shared Mass route/density system needs diverse origins and destinations, while Hero Actors alone require reservable interaction points. | Author 96 zone instances / 592 interaction points, then benchmark weighted/EQS congestion before replacing Mass movement. |
| 2026-09-01 | Introduce a reversible weighted Hero-zone selector before EQS asset integration. | Nearest-zone-only selection creates deterministic hot spots even with sufficient capacity; normalized distance plus remaining capacity distributes arrivals while preserving the policy-to-category contract. | `pcsp.WeightedZoneScoring=0` reproduces the legacy baseline; measure it against the default after editor zone expansion. |
| 2026-09-01 | Use the live official MCP to prepare the 1,024-NPC zone expansion safely. | The portfolio map currently has 10 zone actors / 210 interaction points, all non-spatially-loaded and capacity-consistent. MCP supports discovery, tag registration, map verification, and PIE control but has no EQS-asset factory; direct World Partition actor writes did not persist after a reload. | Registered 96 stable instance tags plus `PCSP.Zone.Hygiene` in `Config/DefaultGameplayTags.ini`; create the EQS asset and place/validate new actors through the level editor before C++ EQS integration. |
| 2026-09-01 | Gate bulk World Partition placement on durable property serialization. | A live five-actor `Rest.Apt_02` probe proved MCP can spawn and initially save external-actor packages, but after a map reload `Category`, `ZoneTag`, and `InteractionPoints` reverted to defaults. The probe was then removed at the exact external-package paths and the portfolio map returned to 10 zones. | Add/use an editor utility that invokes `Modify` plus package save for actor properties, then run the documented 86-zone / 382-point expansion. |
| 2026-09-01 | Use an editor-only commandlet for durable 1,024-NPC zone authoring. | `UPCSPZoneLayoutCommandlet` uses native `Modify`, `PostEditChange`, `MarkPackageDirty`, and UnrealEd's dirty-package save path, avoiding the generic MCP property-writer persistence defect. | Successfully authored `Map_PCSPDistrict_Portfolio`: legacy Leisure was folded into Observe, 86 zones and 382 interaction points were added, for a saved total of 96 zones / 592 points. The external-actor file count increased exactly 236 → 704. |
| 2026-09-02 | Organize UE documentation by concern and split the portfolio demo plan. | Contracts, architecture, guides, validation, benchmarks, and demo runbooks change at different rates; a single large page makes targeted updates and context loading costly. | Use `docs/index.md` as the entry point, add new runtime evidence under `docs/portfolio/benchmarks/`, and keep only compatibility stubs at retired paths. |
| 2026-09-02 | Use a wide deterministic 12×8 Portfolio Zone layout and reject geometrically overlapping authoring. | The previous expansion preserved 96 Zones but compressed them into a 142×136 m area, producing 66 Zone overlaps and 33 slot overlaps. | Keep `-RelayoutWide -DryRun` as the pre-save and post-save audit for future layout edits. |
| 2026-09-02 | Replace the filming layout with a compact, category-interleaved 12×8 grid. | The zero-overlap wide grid is safe but makes NPC travel and establishing shots unnecessarily long; interleaving also keeps semantic alternatives nearby. | Use 25 m × 20 m zone-center spacing; close any editor holding the map before the guarded `-RelayoutCompact` save. |
| 2026-09-02 | Exclude background-throttled timing runs rather than average them into performance evidence. | A 15-FPS platform limit produced bimodal 26–28 ms versus 65–68 ms sessions unrelated to NPC count. | Keep throttle/VSync/MaxFPS CVars explicit in visible benchmark reproduction commands. |

## 2026-05-13 - Phase 1 C++ Scaffold

Branch: `ue5/phase1-prototype`. Added the Phase 1 C++ scaffold under `Source/cnzoi/PCSP/`:

- `PCSP/PCSPTypes.h` - `EPCSPActionType` (20 actions), `EPCSPAffordanceCategory`, `EPCSPNeed`, `FPCSPDecision`, and a `PCSPBlackboard::` namespace of canonical Blackboard key names (Blackboard asset must match).
- `PCSP/Components/` - `UPCSPNeedsComponent` (8 needs with per-need decay/critical config), `UPCSPSocialContextComponent` (radius-based nearby summary + affinity map), `UPCSPObservationComponent` (fixed-length 40-d vector: needs + day phase + social summary, padded for Phase 2/3 fields), `UPCSPPersonaComponent` (id/text/projected vector skeleton), `UPCSPTrajectoryLogComponent` (action/affordance/reward entries).
- `PCSP/Affordance/` - `APCSPInteractionPoint` (reservation), `APCSPAffordanceZone` (gameplay-tag + category + capacity + child interaction points, registers with subsystem in BeginPlay), `UPCSPAffordanceSubsystem` (`UWorldSubsystem`, `FindBestZone`/`GetZonesByCategory`).
- `PCSP/Agent/` - `APCSPAgentCharacter` (composes all five components), `APCSPAIController` (runs assigned `BehaviorTreeAsset` on possession).
- `PCSP/Sim/` - `APCSPSimGameMode` (defaults pawn + controller), `APCSPAgentSpawner` (`AgentCount=16`, NavMesh-aware random reachable points with non-NavMesh fallback).
- `PCSP/BT/BTTask_PCSPDecision` - Phase 1 stub that writes `DesiredActionType` + `UrgencyScore` from the most urgent need; Phase 2/3 replaces the body with the PCSP shared policy inference call.
- `Source/cnzoi/cnzoi.Build.cs` - added `NavigationSystem`, `GameplayTags`, `GameplayTasks` to `PublicDependencyModuleNames` and added the PCSP subdirectories to `PublicIncludePaths`.

### Editor-side follow-ups still required for Phase 1

- Create `Content/PCSP/Maps/Map_PCSPDistrict_M.umap` (Medium district geometry).
- Drop in a `RecastNavMeshBoundsVolume`; verify NavMesh build.
- Place `APCSPAffordanceZone` instances with `ZoneTag`/`Category`/child interaction points covering Eat / Rest / Work / Study / Exercise / Hygiene / Social / Leisure / Shop.
- Author `BB_PCSPAgent` Blackboard with keys exactly matching `PCSPBlackboard::` (DesiredActionType as enum, DesiredAffordanceTag as gameplay tag, TargetActor, TargetLocation, InteractionStyle, UrgencyScore, RecentFailureCount, SocialTargetActor, CurrentZoneTag, bAffordanceReserved).
- Author `BT_PCSPAgent` Behavior Tree skeleton matching the layout in section 6.2 of `PCSP_UE5_Implementation_Plan.md`; root selector with Emergency / Persona / Idle branches; the Persona branch begins with `BTTask_PCSPDecision`.
- Place one `APCSPAgentSpawner` per spawn cluster; set `AgentClass` to a BP child of `APCSPAgentCharacter` whose controller defaults to a BP child of `APCSPAIController` with `BehaviorTreeAsset = BT_PCSPAgent`.
- Set the World Settings `GameMode Override` to `APCSPSimGameMode` (or a BP child).

### Decisions

| Date | Decision | Rationale | Follow-up |
| --- | --- | --- | --- |
| 2026-05-13 | Observation vector is fixed at 40 floats with explicit slots for needs (8) + time (2) + social (5) and a zero-padded tail. | Matches the 32-48 dim target from the implementation plan and gives stable shapes for Python parity / future ONNX export. | Fill remaining slots in Phase 2 (zone occupancy, affordance availability, routine, persona memory hooks). |
| 2026-05-13 | Affordances are exposed via `UWorldSubsystem` rather than `GameInstanceSubsystem`. | Affordance set is per-level; per-world lifetime avoids stale references across map loads. | Confirm before adding cross-map persistence. |
| 2026-05-13 | Reservation lives on `APCSPInteractionPoint`, not on the zone. | Allows multiple agents in one zone while still serializing interactions at a specific seat / station / station-point. | Add reservation timeout in Phase 2 to avoid deadlock. |

## 2026-05-13 - PCSP Public/Private Layout

- Moved PCSP headers to `Source/cnzoi/PCSP/Public/` and PCSP implementation files to `Source/cnzoi/PCSP/Private/`, preserving the existing `Affordance`, `Agent`, `BT`, `Components`, and `Sim` subdirectories.
- Updated `Source/cnzoi/cnzoi.Build.cs` with explicit PCSP public and private include paths so short includes such as `#include "PCSPTypes.h"` resolve from nested PCSP headers.
- Verified with `Build.bat cnzoiEditor Win64 Development -Project=D:\Github\pcsp\ue\cnzoi\cnzoi.uproject -WaitMutex -NoHotReload`; result succeeded.

## 2026-05-18 - Policy Logit Export + KL Compare

Closed the last open analytics item in Phase 4.

- `UPCSPPolicySubsystem::RunInferenceWithLogits` returns the raw 20-dim
  logit vector alongside the argmax action; the original `RunInference`
  path is unchanged.
- `BTTask_PCSPDecision` calls the new entry point and forwards logits to
  `UPCSPTrajectoryLogComponent::RecordDecisionWithLogits`. Throttled
  "reuse last action" hits do not call inference and therefore do not
  emit logits — only fresh decisions produce a `logits` field.
- `decision` JSONL rows now carry `"logits":[20 floats]` (spot-checked
  on `agent_p001_*.jsonl` in `Saved/PCSP/Logs/20260518_151255/`).
- `research/scripts/analyze_ue_session.py` softmaxes each row's logits
  into a running per-agent mean; `analyze_session()` aggregates that
  into a decision-weighted per-persona policy distribution.
  `--compare` adds `kl_ab`, `kl_ba`, and `kl_symmetric` per matched
  persona plus `per_persona_kl_mean/median`.
- **Verification** — paired PIE runs `20260518_145353` vs `20260518_151255`
  (64 agents, ~5.7min each, same train personas):
  matched personas = 64, mean Spearman ρ = 0.648, mean symmetric KL =
  0.712 nats (median 0.475). Per-persona spread is wide
  (pid=1 KL = 0.086, pid=2 KL = 2.726) — driven by short-window
  need-trajectory variance, as expected. Wrote
  `research/results/ue_sessions/kl_20260518_151255/{summary,compare}.json`.

## Open Follow-ups

- Define the first UE5 affordance taxonomy.
- Write the BT-Blackboard-Policy interface contract.
- Decide the initial inference bridge: Python service, ONNX Runtime, or TorchScript.
- Confirm which Python artifacts are required for UE5 runtime loading.
- Phase 4 ablations: BT-only, RL-only, Hybrid-PCSP, Hybrid-NoConsist,
  Hybrid-NoPersona comparison runs (last remaining Phase 4 item).
  Runtime ablations (HybridPCSP / BTOnly / HybridNoPersona) are wired
  via the `pcsp.PolicyMode` CVar — see Phase 4 entry in PLAN.md.
  Hybrid-NoConsist and RL-only still need new ONNX exports from
  `research/`.

## 2026-05-18 - Runtime Ablation Results

Three back-to-back 64-agent PIE runs, identical map/persona set,
`pcsp.PolicyMode` cycled between modes. Sessions:
`20260518_153310` (HybridPCSP), `20260518_154015` (BTOnly),
`20260518_154827` (HybridNoPersona). Aggregate:
`research/results/ue_sessions/ablation_20260518_154827/ablation.json`.

| mode             | n_int | fail% | reward | rho_ref | KL_ref | rho_intra |
| ---------------- | ----: | ----: | -----: | ------: | -----: | --------: |
| HybridPCSP       |  2077 |  0.0% |  708.9 |     ref |      - |     0.368 |
| BTOnly           |  1152 | 87.6% |  395.2 |   0.319 |      - |     0.989 |
| HybridNoPersona  |  1752 | 13.3% |  573.9 |   0.539 |  1.049 |     0.990 |

Findings:
- Persona embedding is load-bearing — inter-persona action dispersion
  collapses from 0.368 → 0.990 the moment the embedding is zeroed.
  Throughput -16%, reward -19%. The policy is genuinely conditioning
  on the embedding, not on needs alone.
- BTOnly's 87.6% failure rate is 8,062 / 8,148 `FindBestZone` failures
  — 64 agents synchronize on the single most-urgent need each tick,
  so they pile into the same zone and bounce off `AllOverCapacity`.
  Category coverage drops to 6 of 10 (Exercise/Study/Shop/Observe
  never reached). Throughput -45%, reward -44%.
- BTOnly KL vs reference is suppressed because its logits are zero
  by construction — KL would just measure distance from uniform.
- HybridNoPersona vs HybridPCSP symmetric KL = 1.05 nats; for context,
  self-vs-self KL on two HybridPCSP runs was 0.71 nats (Phase 4 KL
  verification entry above).

## 2026-05-18 - Phase 0 Documentation + Phase 5 Artifacts

Cleared the remaining Phase 0 docs and the doc-only portion of Phase 5 in
one pass.

**Phase 0:**
- [docs/contracts/research-environment-summary.md](docs/contracts/research-environment-summary.md)
  — UE-facing summary of v3 action ontology, 33-d observation schema, reward
  function (training-only), persona splits, and the ONNX I/O contract. Pins
  the four things UE must keep stable across research updates: I/O shapes,
  action ID ordering, need ordering, persona-slot ordering.
- [docs/contracts/affordance-taxonomy.md](docs/contracts/affordance-taxonomy.md)
  — Canonical 10-category roster with per-zone capacity targets and the
  empirical provenance (Phase 4 stress-run progressions) for those numbers.
  Documents the `Leisure`-folded-into-`Observe` quirk and the
  `Is Spatially Loaded = false` World Partition rule.
- [docs/contracts/bt-blackboard-policy-contract.md](docs/contracts/bt-blackboard-policy-contract.md)
  — Wire format between policy / blackboard / BT. Every blackboard key
  (type, writers, readers, lifecycle), the policy interface
  (`RunInference` + `RunInferenceWithLogits` + `pcsp.PolicyMode` CVar),
  the three-branch BT structure, and per-task contracts for
  `BTTask_PCSPDecision` / `MoveToAffordance` / `PerformInteraction`.
- [docs/validation/scale-targets.md](docs/validation/scale-targets.md)
  — Confirms Debug/Main/Stress targets with reference runs: 16 verified
  in 2026-05-17 baseline, 32 at 5.4% failure, 64 at 1.7% failure (Run 3),
  held-out 64 at 0.04% (`20260518_140432`). Also enumerates what 128+
  would need (async batched inference, more zones, WP streaming sources).

**Phase 5:**
- [docs/portfolio/diagrams.md](docs/portfolio/diagrams.md) — 5 Mermaid diagrams:
  system overview (research→UE→analysis), per-decision sequence diagram,
  BT subtree with failure branches, three-layer affordance system,
  ablation runtime switch. Render via mermaid-cli for paper inclusion.
**Training-side ablation spec** added to `research/PLAN.md` Phase E. Lists
the two ONNX exports still needed for the full ablation table
(`Hybrid-NoConsist` and `RL-only`) with concrete recipes — `no_consist`
reuses `export_pcsp_onnx.py` as-is; `RL-only` (baseline B1) needs a
new wrapper because B1 has no persona-conditioning layer.

**Docs index** ([docs/index.md](docs/index.md)) updated with all six new
doc links.

## 2026-05-18 - Runtime Ablation Switch

- Added `EPCSPPolicyMode { HybridPCSP, BTOnly, HybridNoPersona }` to
  `PCSPTypes.h`. Selected at inference time via console variable
  `pcsp.PolicyMode` (0/1/2). Switch from PIE console between runs —
  no rebuild needed.
- `UPCSPPolicySubsystem::RunInference` branches on the mode:
  - `BTOnly` skips ONNX entirely and returns `NeedsHeuristic(Obs)`;
    logits are emitted as a zero vector so the JSONL schema stays
    uniform.
  - `HybridNoPersona` zeroes `PersonaBuffer` before the NNE bind.
    Same architecture and model, just an empty persona slot.
  - `HybridPCSP` is unchanged (default).
- `UPCSPTrajectoryLogComponent::BeginPlay` writes
  `"policy_mode":"<name>"` into each agent's `session_start` row so
  analysis tooling can label runs.
- `research/scripts/analyze_ue_session.py` surfaces `policy_mode` in
  the per-session summary; `compare_ablations.py` aggregates N
  sessions into one table (interactions, failure rate, reward,
  inter-persona dispersion, ρ + symmetric KL vs reference). BTOnly
  KL vs reference is reported as `null` because its logits are zero
  by construction.

## 2026-05-18 - Intra-Session Persona-Distance vs Action-KL

- Added `research/scripts/analyze_persona_distance_vs_kl.py`. Reads a
  session `summary.json` (per-persona `policy_probs` from logits, with
  fallback to the 20-bin action histogram) and the active
  `persona_embeddings.json`, then for every persona pair computes
  cosine distance over the 64-d embedding vs symmetric KL over the
  policy distribution and reports the Spearman ρ between the two
  pairwise vectors. Optional `--manifest` arg handles held-out slot
  remapping. Output written next to the session summary as
  `persona_distance_vs_kl.json` with `n_pairs`, `spearman_rho`,
  `pearson_r`, plus the full scatter table for follow-up plotting.
- Results across the four logit-bearing 64-agent sessions:
  - `noconsist_ablation_20260518` (Full PCSP, 2,016 pairs):
    ρ = 0.236, mean cos-dist 0.532, mean KL 1.78.
  - `noconsist_only_20260518` (NoConsist checkpoint, same map): ρ = 0.569.
  - `kl_20260518_151255` (Full PCSP): ρ = 0.257.
  - `btonly_detail` (BTOnly, sanity check): ρ = 0.007 with KL ≡ 0 —
    expected, since BTOnly emits zero logits and bypasses the persona
    vector entirely.
- Headline: in-engine ρ ≈ 0.24-0.26 for the consistency-trained
  checkpoint, well below the paper's research-side ρ ≈ 0.73 — the BT
  + capacity contention layer compresses the persona signal at
  execution time. Interestingly the NoConsist checkpoint scores
  *higher* (0.57) here, mirroring the v1/v3 "reward hides the
  failure" pattern: removing the consistency loss does not collapse
  the engine-level persona separability metric, even though
  research-side analysis flags it. Worth noting in the paper
  extension's limitations section.

## 2026-05-19 - T1 telemetry prep (scaling-curve / persistence / contention)

Three additive telemetry hooks landed ahead of the T1.3 scaling sweep
([research/revised/260519/REVISE_PLAN.md](../../research/revised/260519/REVISE_PLAN.md)).
All emit to the existing `Saved/PCSP/Logs/<stamp>/` session dir; no schema
break — existing `analyze_ue_session.py` aggregations continue to work.

- **ONNX inference latency (Gap 1, T1.3).**
  `UPCSPPolicySubsystem::RunInferenceWithLogits` now returns wall-time in
  microseconds via a `double& OutInferenceMicros` out-parameter (timed with
  `FPlatformTime::Seconds()` around the existing `RunInference` body).
  `BTTask_PCSPDecision::ExecuteTask` plumbs the value through to
  `UPCSPTrajectoryLogComponent::RecordDecisionWithLogits(..., double InferenceMicros = -1.0)`,
  which appends `"infer_us":<f>` to each `decision` JSONL row alongside the
  existing `logits` array. Direct measurement was required because the
  pre-existing throttle (`MinDecisionInterval`, `BTTask_PCSPDecision.cpp:58`)
  makes per-decision `t` deltas useless as a latency proxy.

- **Zone occupancy sampler (Gap 3, T1.5).**
  `UPCSPAffordanceSubsystem` now overrides `OnWorldBeginPlay` to start a
  1 Hz timer (`SampleOccupancy`) that iterates `Zones[]` and appends one row
  per zone per second to `<session>/zone_occupancy.jsonl`:
  `{t, zone_tag, category, occupants, capacity}`. Drives the §7.6
  contention heatmap. `APCSPAffordanceZone::GetCurrentOccupancy()` already
  existed but was never emitted.

- **Frame-time sampler (Gap 2, T1.3).**
  New `UPCSPPerfSamplerSubsystem` (`PCSP/Sim/PCSPPerfSamplerSubsystem.{h,cpp}`)
  — a `UTickableWorldSubsystem` that captures DeltaTime each frame into a
  rolling buffer and on a 1 Hz timer dumps
  `{t, n_samples, mean_ms, p50_ms, p95_ms, p99_ms}` to
  `<session>/frame_stats.jsonl`. Gated to `PIE` / `Game` world types; no-op
  in editor preview. Single writer, zero per-agent overhead.

All additions are local — no changes to `cnzoi.Build.cs` (Sim/Public &
Sim/Private already in PublicIncludePaths/PrivateIncludePaths). Next step
is an editor rebuild + 16-agent / 60-s PIE smoke run to verify the three
new JSONL files populate, then the T1.3 sweep `{8, 16, 32, 64, 96, 128}`
× 3 seeds × 10 min.

### 16-agent / 60 s smoke verification (session `20260519_121204`)

All three telemetry streams populate cleanly:

- `frame_stats.jsonl` (84 rows, 1 Hz): warm steady-state mean 10.0 ms /
  p95 12.9 ms / p99 18.9 ms (≈100 FPS). First-row p99 = 400 ms is the PIE
  startup hitch — the sweep analyzer trims the first 5 s.
- `zone_occupancy.jsonl` (840 rows = 10 zones × 84 s): all zone tags +
  capacities emitted at 1 Hz.
- `decision` rows now carry `"infer_us"`: mean 159 µs, p50 149, p95 173,
  p99 205, max 3547 (single cold-path inference). At 159 µs/agent, even
  128 concurrent agents at full throttle would only cost ~20 ms/s of
  inference total — ONNX will not be the scaling bottleneck.

### Spawner: reproducible sweep config

`APCSPAgentSpawner` extended for T1.3 sweep automation:

- New `RandomSeed` UPROPERTY (default -1 = non-deterministic).
- New CVar `pcsp.SpawnSeed` overrides `RandomSeed` when ≥ 0.
- New CVar `pcsp.AgentCount` overrides `AgentCount` when ≥ 1.
- When seed is set, `FMath::RandInit(seed)` runs once in `BeginPlay`
  before any `FMath::VRand` / `GetRandomReachablePointInRadius` call,
  making the spawn pattern reproducible.
- A `run_config.json` sidecar is written into the session dir on
  spawner BeginPlay:
  `{n_agents, seed, spawn_radius, spawn_on_navmesh}` — keyed by session
  stamp, so the sweep analyzer can label runs without parsing PIE logs.

Sweep can now be driven from a small startup-CVar list per run
(e.g. `pcsp.AgentCount=64 pcsp.SpawnSeed=2`), no editor edits required
between settings.

### Auto-quit + headless sweep driver

`UPCSPPerfSamplerSubsystem` gained a one-shot auto-quit hook keyed off
the new CVar `pcsp.RunDurationSeconds` (default -1 = never). When set
to a positive value at startup, a timer scheduled in `OnWorldBeginPlay`
calls `FPlatformMisc::RequestExit(false)` after that many seconds.
Combined with `pcsp.AgentCount` and `pcsp.SpawnSeed`, three CVars now
fully parameterize a single sweep run.

The PowerShell driver [tools/run_scaling_sweep.ps1](tools/run_scaling_sweep.ps1)
loops `{agent_count} × {seed}`, launching `UnrealEditor.exe -game
-WINDOWED -ResX=800 -ResY=450 -Unattended -NoSplash -NoSound` per
combination with all three CVars set via `-ExecCmds`. It auto-detects
the engine install from the `.uproject` EngineAssociation (registry
lookup with `C:\Program Files\Epic Games\UE_<ver>` fallback), and the
project path resolves relative to the script. `-DryRun` prints the
planned 18 invocations without launching anything; tested locally and
the resulting commands point at UE_5.7. The script `Start-Process
-Wait`s on each invocation so runs are strictly serial — no log-dir
collisions, no GPU thrash.

Standalone `-game` mode uses the map set as Project Settings → Maps &
Modes → Editor Startup Map. Rendering stays on (windowed 800×450) so
`frame_stats.jsonl` reflects the realtime budget the paper claims, not
a no-render artifact.

### Sweep analyzer: `research/scripts/analyze_scaling_sweep.py`

Ingests N session dirs (one per PIE run), reads `run_config.json` (or
falls back to `len(agent_p*.jsonl)` for legacy sessions like the smoke
run), `frame_stats.jsonl`, `zone_occupancy.jsonl`, and the per-agent
JSONL. Outputs:

- `per_session.json` — one row per PIE run (latency / frame / fail /
  intent metrics, plus per-zone mean utilization and failure-reason
  histogram).
- `scaling_curve.json` — per-`n_agents` aggregate across seeds (mean +
  std for inference µs, frame p95 ms, fail rate, intents/agent/min).
- `latency_budget.tsv` — tab-separated, paste-ready for the §7 latency
  table.
- Optional `scaling_curve.png` (Fig 5) when `--plot` is passed
  (matplotlib).

First WARMUP_SECONDS = 5 s of every session are dropped before computing
latency / frame-time aggregates to remove the cold-start hitch.

Smoke-run dry-run validated the fallback path (no `run_config.json`,
inferred n_agents=16 from file count, seed=-1) and produced sensible
numbers: 149.6 µs mean / 170.4 µs p95 inference, 9.77 ms mean / 13.19 ms
p95 frame, 1.6% fail rate, 5.44 intents/agent/min.

### Sweep driver hardening (post-smoke regressions)

First attempted sweep (`-DurationSeconds 180 -AgentCounts 8,64 -Seeds 0`)
exposed three independent bugs in the unattended path; all fixed:

1. **Engine idled on focus loss.** UnrealEditor.exe `-game` launched via
   `Start-Process` starts unfocused, and the editor's default
   `t.IdleWhenNotForeground=1` throttles the *entire* engine loop —
   FTSTicker, world TimerManager, and agent BTs all stop together.
   Symptom: agents freeze, auto-quit timer never fires, process lives
   forever. Fix: `[ConsoleVariables] t.IdleWhenNotForeground=0` in
   `Config/DefaultEngine.ini` (applied at engine init, before any world).
   Also added `bPauseOnLossOfFocus=False` and
   `bSuppressLostFocusMessage=True` as belt-and-suspenders.
2. **Auto-quit timer was on world TimerManager.** Originally scheduled
   via `World->GetTimerManager().SetTimer(...)` — stops when the world
   is paused for any reason. Moved to `FTSTicker::GetCoreTicker()` in
   `PCSPPerfSamplerSubsystem.cpp` so the quit fires regardless of
   world pause state.
3. **`-ExecCmds` CVars arrived after `BeginPlay`.** Three runs in the
   first post-fix attempt produced clean frame_stats but all showed
   `n_agents=16` (default), `seed=-1`, and ran ~255 s instead of the
   requested 180 s — proof that `pcsp.AgentCount` / `pcsp.SpawnSeed` /
   `pcsp.RunDurationSeconds` were still at defaults when the spawner
   and perf-sampler read them in `BeginPlay`. Root cause: UE processes
   `-ExecCmds` from `UGameEngine::Tick` *after* the first map's
   `BeginPlay`. Fix: read from the command line directly using
   `FParse::Value(FCommandLine::Get(), TEXT("PCSP_AgentCount="), ...)`
   (and the analogous switches for seed / duration). `FCommandLine`
   is populated before any `BeginPlay` so the override is always
   visible. `-ExecCmds` is still passed as a belt-and-suspenders for
   any future late readers. Driver
   [tools/run_scaling_sweep.ps1](tools/run_scaling_sweep.ps1) now
   emits both `-PCSP_*=N` switches and the original `-ExecCmds` list.

Also hardened the driver itself:
- Switched `Start-Process -ArgumentList` from a `@()` array to a single
  string — PS 5.1 mangles embedded quotes when the array form is used
  with `-ExecCmds="..."`.
- Added a `Duration + 90 s` PowerShell watchdog that force-kills the
  process if the in-engine auto-quit ever fails to fire, so one stuck
  run can't block a multi-hour sweep.

### Verification (session `20260519_163305`)

One-run sanity sweep (`-DurationSeconds 90 -AgentCounts 8 -Seeds 0`)
after all three fixes:

- `run_config.json` = `{"n_agents":8,"seed":0,...}` — switches reached
  the spawner.
- 8 `agent_p*.jsonl` files, 89 frame_stats rows (90 s @ 1 Hz), 890
  zone_occupancy rows (10 zones × 89 s) — all telemetry streams
  populated cleanly.
- Mean frame time 7.5 ms / p95 10.7 ms (~130 FPS at 8 agents,
  windowed 800×450) — engine genuinely ticking, not idle.
- Wall-clock 103.5 s = ~13 s startup + 90 s sim + clean exit — the
  in-engine FTSTicker quit fired; watchdog never engaged.
- Decision rows still carry `logits` and `infer_us` from the prior
  schema extension.

Pipeline is now ready for the real T1.3 sweep
(`{8,16,32,64,96,128} × 3 seeds × 600 s` ≈ 3.5 h wall-clock).

## 2026-05-20 - T1.3 Scaling Sweep Results

**18-run sweep** (`{8,16,32,64,96,128} agents × seeds {0,1,2} × 630 s`).
Original sweep PS ran all 18 runs sequentially; sessions logged to
`ue/cnzoi/Saved/PCSP/Logs/20260520_000614` … `20260520_030856`.
Analyzer: `research/scripts/analyze_scaling_sweep.py`
Output: `research/results/ue_sessions/scaling_20260520/`

### Latency budget (`latency_budget.tsv`)

| n_agents | seeds | infer_µs mean | infer_µs p95 | frame_ms mean | frame_ms p95 | fail_rate | intents/agent/min |
|----------|-------|--------------|-------------|--------------|-------------|-----------|-------------------|
| 8        | 3     | 183.2        | 234.8       | 5.57         | 7.75        | 0.1%      | 5.67              |
| 16       | 3     | 184.1        | 230.5       | 5.84         | 8.19        | 0.0%      | 5.67              |
| 32       | 3     | 202.6        | 257.6       | 7.53         | 11.27       | 0.0%      | 6.06              |
| 64       | 3     | 199.8        | 264.1       | 10.25        | 13.38       | 0.2%      | 5.61              |
| 96       | 3     | 153.7        | 198.1       | 11.62        | 15.89       | 4.7%      | 5.35              |
| 128      | 3     | 132.0        | 181.6       | 14.39        | 17.05       | **44.9%** | 4.98              |

### Findings

1. **Inference is not the bottleneck.** ONNX inference latency stays flat at
   183–202 µs from n=8 to n=64. The per-agent inference budget (≤ 250 µs mean)
   holds across all tested counts. The drop to 153/132 µs at n≥96 reflects
   CPU scheduler timeslicing at saturation — per-call wall-time shrinks while
   total throughput degrades.

2. **Frame time scales near-linearly**, at ~0.27 ms/agent from n=8 to n=128.
   The 60 fps budget (16.67 ms) is maintained through n=96 (mean 11.62 ms,
   p95 15.89 ms). At n=128 the p95 hits 17.05 ms, just over the limit.

3. **NavMesh pathfinding is the hard ceiling.** Fail rate is 0% for n≤32,
   rises to 4.7% at n=96, and collapses to **44.9% at n=128**. This is
   NavMesh query-queue saturation — 128 simultaneous `FindPath` requests from
   `BTTask_MoveToAffordance` exceed the recast navigation system's async
   capacity. Intent throughput drops from 5.67 to 4.98 intents/agent/min
   as failed agents stall their BT branch.

4. **Recommended operating point: ≤ 64 agents** for reliable real-time
   behavior (fail rate < 0.2%, frame p95 < 14 ms). 96 agents is a soft-cap
   (borderline frame budget, manageable fail rate). 128+ requires async
   batched pathfinding or a crowd-simulation movement fallback.

5. **Intents/agent/min is stable** at 5.6–6.1 for n≤64 (within 8% of the
   n=8 baseline) — the policy's per-agent decision rate does not degrade as
   the crowd scales, confirming the ONNX inference path is genuinely parallel
   with BT execution.

### Session index (original sweep — resumed-sweep duplicates excluded)

| Run | Session dir       | n   | seed |
|-----|-------------------|-----|------|
| 1   | 20260520_000614   | 8   | 0    |
| 2   | 20260520_001656   | 8   | 1    |
| 3   | 20260520_002739   | 8   | 2    |
| 4   | 20260520_003821   | 16  | 0    |
| 5   | 20260520_004906   | 16  | 1    |
| 6   | 20260520_005949   | 16  | 2    |
| 7   | 20260520_011032   | 32  | 0    |
| 8   | 20260520_012120   | 32  | 1    |
| 9   | 20260520_013209   | 32  | 2    |
| 10  | 20260520_014258   | 64  | 0    |
| 11  | 20260520_015347   | 64  | 1    |
| 12  | 20260520_020437   | 64  | 2    |
| 13  | 20260520_021526   | 96  | 0    |
| 14  | 20260520_022609   | 96  | 1    |
| 15  | 20260520_023651   | 96  | 2    |
| 16  | 20260520_024732   | 128 | 0    |
| 17  | 20260520_025814   | 128 | 1    |
| 18  | 20260520_030856   | 128 | 2    |

Note: sessions 011402, 012457, 013551, 014644, 015736, 020829 are from a
duplicate sweep script that ran parallel UE instances; excluded from analysis.

## 2026-05-22 - Portfolio Demo Video And HUD Plan

- Added the portfolio demo documentation (now split under [docs/portfolio/demo/](docs/portfolio/demo/README.md)).
- The document defines the portfolio video structure, shot list, scenario beats,
  demo-map policy, capture checklist, and a concrete HUD information
  architecture for selected agents.
- It also specifies the planned nearest-agent camera focus feature:
  use `SetViewTargetWithBlend()` from a demo observer controller instead of
  true controller possession, so `APCSPAIController` and the Behavior Tree keep
  running while the player observes an agent's camera.
- Updated [docs/portfolio/README.md](docs/portfolio/README.md) and
  [docs/index.md](docs/index.md) with the new artifact.

## 2026-05-22 - Portfolio Documentation Consolidation

- Moved Phase 5 architecture diagrams into the portfolio directory:
  [docs/portfolio/diagrams.md](docs/portfolio/diagrams.md).
- Reworked [docs/portfolio/README.md](docs/portfolio/README.md) around the
  intended implementation order: hybrid cleanup, EQS congestion, async
  inference, observability extensions, then camera/HUD capture.
- Updated [PLAN.md](PLAN.md) so portfolio work is now explicitly
  engine-extension-first and demo-UI-second.

## 2026-05-23 - Portfolio Hybrid Stack Cleanup

- Implemented the P0 portfolio cleanup from
  [docs/portfolio/hybrid-stack.md](docs/portfolio/hybrid-stack.md).
- Centralized action-to-category routing in
  `UPCSPPolicySubsystem::ActionToCategory`; `BTTask_PCSPDecision` writes the
  optional `DesiredCategory` Blackboard key and `BTTask_MoveToAffordance` reads
  it with a fallback to the same subsystem function.
- Routed `LeisureIndoor`, `LeisureOutdoor`, and `ObserveCrowd` to the authored
  Observe category so the effective 9-category taxonomy remains executable
  without a dedicated Leisure zone.
- Added `active_ablation` to the trajectory `session_start` row by reading
  `Content/PCSP/Models/active_ablation.txt`, and updated
  `research/scripts/analyze_ue_session.py` to preserve the field in
  `summary.json`.
- Fixed `BTOnly` decision execution so it can use the needs heuristic even when
  ONNX assets are absent or the policy subsystem is not ready.

## 2026-05-23 - Observability Pipeline Extensions

Closed the two "What's next" items on
[docs/portfolio/observability.md](docs/portfolio/observability.md).

- **Coarse trace renderer**:
  `research/scripts/render_session_trace.py`. Reads
  `Saved/PCSP/Logs/<stamp>/agent_p*.jsonl`, emits chronological events
  (`DECIDE` / `INTERACT` / `MFAIL` / `IFAIL` / `START`) or a compressed
  `schedule` of completed interactions only. Flags: `--persona`,
  `--from` / `--until`, `--group-by {time,persona}`. Pure stdlib;
  smoke-tested against session `20260517_230327` per-persona window
  with both `full` and `schedule` modes.
- **Persona-distance vs KL output carries `active_ablation`**:
  `research/scripts/analyze_persona_distance_vs_kl.py` now forwards
  `summary.json["active_ablation"]` into its output as
  `session_active_ablation` so paired comparisons across the
  full/no_consist ONNX swaps can be matched without filesystem
  inspection.

## 2026-05-23 - Diagram Polish + HUD/Camera C++ Scaffold

Closed roadmap items #5 (engine-side C++ scaffold) and #6 (diagram polish)
from [PLAN.md §"Portfolio Engineering Roadmap"](PLAN.md).

### Diagram polish

- Refreshed [docs/portfolio/diagrams.md](docs/portfolio/diagrams.md) so the
  five Mermaid figures match the 2026-05-23 hybrid-stack cleanup:
  - Diagram 2 (per-decision sequence) now shows `ActionToCategory()` called
    on `UPCSPPolicySubsystem`, the `DesiredCategory` Blackboard writeback on
    both the throttle-reuse and fresh-decision paths, and the relaxed
    `IsReady()` guard for `BTOnly` mode.
  - Diagram 3 (BT subtree) labels `BTTask_PCSPDecision` and
    `BTTask_MoveToAffordance` as readers/writers of the centralized
    `DesiredCategory` key.
  - Diagram 4 (three-layer affordance) annotates that
    `Leisure*` / `ObserveCrowd` route to the authored Observe category,
    so the effective taxonomy is 9 categories.
  - Diagram 5 (ablation switch) shows `swap_ue5_onnx.py` →
    `active_ablation.txt` → `UPCSPTrajectoryLogComponent::BeginPlay` →
    `session_start` row, closing the loop with `compare_ablations.py`.
- Added a "Change log" section to diagrams.md.

### HUD/camera C++ scaffold (items D1, D3, ring buffer from the plan)

- **`APCSPDemoPlayerController`** ([PCSP/Public/Agent/PCSPDemoPlayerController.h](Source/cnzoi/PCSP/Public/Agent/PCSPDemoPlayerController.h),
  [PCSP/Private/Agent/PCSPDemoPlayerController.cpp](Source/cnzoi/PCSP/Private/Agent/PCSPDemoPlayerController.cpp)) —
  spectator-style controller for portfolio capture. Legacy `InputComponent`
  bindings (no Enhanced Input asset authoring required):
  `F` toggle focus on nearest agent, `Tab` / `Shift+Tab` cycle by `PersonaId`,
  `H` broadcasts `OnHudToggle`, `Z` broadcasts `OnZoneOverlayToggle`.
  Uses `SetViewTargetWithBlend(0.35s)` instead of `Possess()` so each
  agent's `APCSPAIController` and Behavior Tree continue to run undisturbed
  (per demo-video-hud-plan.md risk table).
- **`UPCSPAgentDebugViewModel`** ([PCSP/Public/Components/PCSPAgentDebugViewModel.h](Source/cnzoi/PCSP/Public/Components/PCSPAgentDebugViewModel.h),
  [PCSP/Private/Components/PCSPAgentDebugViewModel.cpp](Source/cnzoi/PCSP/Private/Components/PCSPAgentDebugViewModel.cpp)) —
  read-only adapter that reads persona / needs / social / Blackboard /
  trajectory state from the observed agent and returns
  `FPCSPHudAgentSnapshot` (persona id+text+embedding status, policy mode,
  active ablation, decision stack, 8 needs, social summary, target zone
  occupancy resolved via interaction-point membership, recent events).
  Pure — never mutates agent state, safe to bind to a UMG widget that
  ticks every frame. Owned by `APCSPDemoPlayerController`; rebound on
  `SetObservedAgent`.
- **In-memory event ring buffer on `UPCSPTrajectoryLogComponent`** —
  closes the open follow-up in demo-video-hud-plan.md. `FPCSPTrajectoryEntry`
  gained `EventType`, `Category`, and `UrgencyScore` fields; `Entries` is now
  bounded by `MaxRecentEntries` (default 64, FIFO drop). New
  `GetRecentEvents(MaxCount)` returns the newest-last tail for the HUD
  trajectory strip. JSONL output is unchanged — the ring buffer is purely
  an in-process mirror.

### Editor-side follow-ups for the demo HUD (D2, D4, D5, D6)

Asset/level work that the C++ scaffold above cannot do; deferred to the next
editor session:

- **D2 — Agent camera mount.** Add `USpringArmComponent + UCameraComponent`
  to a BP child of `APCSPAgentCharacter`, or stand up a `APCSPAgentCameraProxy`
  that attaches to the observed agent. `SetViewTargetWithBlend` already targets
  the agent actor; the camera component just controls framing.
- **D4 — UMG widgets.** Author `WBP_PCSPDemoHUD` and the eight sub-widgets in
  `docs/portfolio/demo-video-hud-plan.md §"Implementation Work Breakdown".`
  Bind to `UPCSPAgentDebugViewModel::BuildSnapshot()`; consume the new
  `FPCSPHudAgentSnapshot` USTRUCT. Listen to
  `APCSPDemoPlayerController::OnObservedAgentChanged` / `OnHudToggle` /
  `OnZoneOverlayToggle` from BP.
- **D5 — Zone overlay materials/decals** on the affordance-zone floors,
  toggled by `OnZoneOverlayToggle`.
- **D6 — Capture presets.** Duplicate `Map_PCSPDistrict_M` to
  `Map_PCSPDistrict_Portfolio`, set the demo World Settings
  `PlayerControllerClass = APCSPDemoPlayerController`, leave the experiment
  map untouched.
- **Phase 5 PIE captures.** With the controller + HUD live, capture the
  story beats (16-agent close-up, 64-agent crowd, persona contrast trio,
  congestion recovery, data-trail proof) per the demo-video-hud-plan beats
  table. Then run `analyze_ue_session.py` on the captured stamp.

## 2026-08-31 - 1,024-NPC Mass Hybrid And Path-Request Scheduling

Implemented the first complete scale-up pass described in
`docs/portfolio/mass-1024-scaling.md`.

### Actor-tier navigation admission

- Added `UPCSPPathRequestSchedulerSubsystem`, a tickable world subsystem that
  queues Actor-tier path permits and releases at most
  `pcsp.PathRequestsPerFrame` per frame (default 8).
- Requests are ranked by semantic urgency plus time spent waiting, which keeps
  emergency needs responsive without starving low-urgency agents.
- `UBTTask_MoveToAffordance` now requests a permit before choosing/reserving an
  affordance. Abort cancels the queued request. This prevents queued agents
  from consuming interaction capacity while they are unable to submit a path.
- Added `path_scheduler.jsonl`: queue/peak depth, enqueued, granted, submitted,
  cancelled, mean wait, p95 wait, and current budget.
- Baseline reproduction remains available with
  `pcsp.PathSchedulingEnabled 0`.

### Mass background simulation

- Added PCSP Mass fragments for persona/cohort, eight needs, semantic intent,
  zone-level move target, and transform; added an editor-facing
  `UPCSPMassAgentTrait`.
- Added `APCSPMassSpawner`, which programmatically creates the archetype,
  batch-spawns the requested population, cycles through the 300 persona IDs,
  distributes decisions across 32 cohorts, and renders the background through
  a low-frequency HISM update.
- Added `UPCSPMassSimulationProcessor`. It preserves the existing 33-d
  observation layout and 20-action ontology, calls the same
  `UPCSPPolicySubsystem` when ready, falls back to the needs heuristic when it
  is not, chooses the closest authored zone matching the selected category,
  and advances background entities chunk-by-chunk.
- Added CVars `pcsp.MassDecisionInterval`,
  `pcsp.MassMaxDecisionsPerFrame`, and `pcsp.MassMoveSpeed`.
- Added `mass_stats.jsonl` with population, decisions, arrivals, and policy
  timing. Mass background movement deliberately avoids a per-entity Recast
  query; this first pass is zone-level straight-line movement and is documented
  as a prototype simulation LOD.
- `APCSPAgentSpawner` now accepts `pcsp.MassEntityCount` /
  `-PCSP_MassEntityCount`; `run_config.json` records hero, Mass, and total NPC
  counts. The recommended portfolio composition is 16 hero Actors + 1,008 Mass
  entities.

### Sweep and analysis tooling

- Extended `tools/run_scaling_sweep.ps1` with `-MassHybrid`,
  `-TotalNpcCounts`, and `-HeroAgentCount`. A dry run verified the intended
  16+112, 16+240, 16+496, and 16+1008 matrix.
- Extended `research/scripts/analyze_scaling_sweep.py` to distinguish
  `actor_bt` and `mass_hybrid`, ingest `path_scheduler.jsonl` and
  `mass_stats.jsonl`, emit architecture/count/queue/wait/Mass metrics, and
  plot Actor and hybrid scaling curves together.
- Generated smoke analysis artifacts:
  `research/results/ue_sessions/mass_smoke_20260831/`. A 4-Actor control is in
  `research/results/ue_sessions/actor4_smoke_20260831/`.

### Verification

- UE 5.8 compatibility build of `cnzoiEditor Win64 Development` succeeded with
  the project's UE 5.7 include order. UE 5.8 splits reflected Mass types into
  `MassCore`, so `cnzoi.Build.cs` adds that module only for UE 5.8+ while
  retaining the 5.7 dependency set.
- The installed UE 5.7 directory on this machine is incomplete (no
  `Engine/Build/BatchFiles/Build.bat` or development headers), so a native 5.7
  build could not be executed here.
- Runtime compatibility smoke session `Saved/PCSP/Logs/20260831_035336`:
  4 hero Actors + 1,020 Mass entities, 1,024 total, 29.4 seconds, 3,322 Mass
  decisions, 3,933 Mass arrivals, 0 hero movement failures, scheduler p95 wait
  about 10 ms, and mean Mass policy call about 106 microseconds.
- The smoke used UE 5.8 `-RenderOffscreen`. A separate 4-Actor control was also
  throttled in that mode, so smoke frame time is explicitly excluded from
  performance claims. Final proof requires normal PIE/visible standalone runs.
- Python `py_compile` passed for the updated analyzer; the PowerShell hybrid
  sweep dry run generated the correct counts; project JSON remained valid.

### Portfolio artifacts and remaining work

- Replaced the placeholder READMEs with a research-to-runtime root README and a
  UE-specific build/run/telemetry README.
- Added `docs/portfolio/mass-1024-scaling.md` and refreshed the portfolio index
  and PLAN. The case study covers the measured 128-Actor failure, the
  architectural intervention, current limitations, runbook, and acceptance
  criteria.
- HUD widgets, portfolio map, player controller, and debug view-model assets are
  present. The earlier editor-side follow-up list above is historical; final
  map/HUD validation, screenshots, and video capture remain presentation work.
- Highest-value next engineering steps: ZoneGraph/MassCrowd navigation, shared
  hierarchical route caching, density-aware admission, near/mid/far simulation
  LOD promotion, true dynamic-batch ONNX inference, and sampled rich logging.

## 2026-08-31 - Reproducible Portfolio Visual Evidence

- Added `tools/generate_portfolio_visuals.py`, which reads checked-in UE result
  JSON and emits PNG plus SVG masters under `docs/portfolio/assets/`.
- Added three portfolio-facing figures: persona-conditioning ablation,
  Actor/Behavior Tree scaling ceiling, and 1,024-NPC Mass-hybrid runtime proof.
- Added [docs/portfolio/visual-evidence.md](docs/portfolio/visual-evidence.md)
  with source paths, interpretation, reproduction command, and the remaining
  visible-capture checklist; surfaced the figures from the repository README.
- Kept evidence classes explicit: the May visible Actor sweep supports frame
  and failure-rate claims, while the August offscreen Mass smoke supports only
  runtime-path compatibility. Its throttled frame timing is not plotted or used
  as a performance claim.

## 2026-08-31 - Unreal Engine 5.8 Migration and Official MCP Verification

- Changed `cnzoi.uproject` to `EngineAssociation` 5.8 and moved both editor and
  game targets to Build Settings V7 with the UE 5.8 include order.
- Replaced the unavailable `NarshaMCP` project dependency with Unreal 5.8's
  official `ModelContextProtocol` and `AllToolsets` plugins. Added the local
  Streamable HTTP endpoint to `.mcp.json`.
- Updated the UE 5.8 Mass include to `Mass/EntityHandle.h`, replaced the removed
  `/Engine/BasicShapes/Capsule` representation with a scaled Cylinder, and
  migrated two deprecated StateTree instance-data declarations to the explicit
  zero-initialized macro.
- `cnzoiEditor Win64 Development` completed successfully on UE 5.8 with no
  compiler warnings in the final incremental build.
- Through the live UE MCP server, loaded
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio`, compiled 16 PCSP Blueprints with
  warnings treated as errors, and ran a 10-second Simulate PIE smoke. The policy
  initialized with the 33/64/20 contract and the spawner created all 16 hero
  agents after NavMesh readiness; the prior Capsule CDO load error did not recur.
- The checked map and representative Blueprint assets remained clean, so no
  binary assets were resaved. MCP automation discovery succeeded, but there are
  currently no tests registered under the `PCSP` filter.

## 2026-09-01 - Visible 128–1,024 Mass-Hybrid Benchmark

- Ran `128,256,512,1024` total NPCs × seeds `0,1,2` × 300 seconds in visible
  UE 5.8 standalone mode with 16 hero Actors and the remaining population in
  Mass. All 12 runs exited with code 0 and none required watchdog termination.
- Each session produced 16 agent logs plus `frame_stats.jsonl`,
  `mass_stats.jsonl`, `path_scheduler.jsonl`, `zone_occupancy.jsonl`, and run
  configuration files. Eleven sessions contain 300 frame samples and the first
  contains 299; all contain 296 Mass samples.
- Aggregate artifact: `research/results/ue_sessions/mass_scaling_20260901/`.
- At 1,024 NPCs: frame mean `25.47 ± 0.47 ms`, frame p95
  `30.15 ± 0.53 ms`, hero movement failure `0.0%`, throughput
  `14.10 ± 0.01` completed intents/NPC/min, Mass policy mean
  `101.0 ± 2.0 us`.
- From 128 to 1,024 NPCs, frame p95 changed only `29.90 → 30.15 ms`; this
  supports bounded incremental population cost. Absolute frame time is still
  above 16.67 ms, so the result is explicitly not presented as 60 FPS.
- Added the full report at
  `docs/portfolio/benchmarks/visible-mass-20260901.md` and a reproducible
  `mass-scaling-evidence` PNG/SVG generated from checked-in JSON.

## 2026-09-01 - Sampled Mass Behavior Telemetry And Tier Audit

- Actor decision JSONL now records the canonical 0--19
  `policy_action_index` before UE semantic remapping.
- `UPCSPMassSimulationProcessor` records the lowest 16 stable-index entities
  to buffered `mass_trajectories.jsonl`; the budget is controlled by
  `pcsp.MassTrajectorySampleCount` and can be disabled with zero.
- Each sampled row carries stable index, persona ID, canonical policy action,
  executed action, position, and eight needs. Mass run config declares the
  `pcsp_ue_behavior_v1` trajectory schema.
- UE 5.8 editor build passed after the C++ change. Visible standalone session
  `20260901_044431` (16 Actor + 112 Mass, seed 7, 300 seconds) exited code 0
  with 993 sampled Mass decisions and all 16 indexed Actor logs.
- The frozen external action probe found mean Actor/Mass action JS `0.066`,
  trait prediction agreement `71.25%`, Actor BA `0.458`, and Mass BA `0.571`
  across 16 paired personas. This validates the telemetry/evaluator bridge;
  it is not a multi-seed Mass-superiority result.
- Analysis and compact source evidence are checked in under
  `research/results/ue_sessions/tier_behavior_20260901_044431/`.

## 2026-09-01 - Full-PCSP Actor/Mass Multi-Seed Confirmation

- Completed three visible 300-second UE 5.8 standalone runs with the full
  PCSP export, 16 Actor/BT agents, 112 Mass agents, and spawn seeds 0/1/2.
- All runs exited with code 0; each has 16 indexed Actor trajectories, 300
  frame samples, and 676--685 sampled Mass decisions.
- The frozen independent evaluator found action JS `0.068+/-0.013` and trait
  prediction agreement `67.9+/-4.7%` across seeds. Actor BA was
  `0.498+/-0.063`; Mass BA was `0.450+/-0.012`.
- The tier difference changes sign across seeds, so the portfolio claim is
  cross-tier persona-signal preservation, not Mass or Actor superiority.
- Restored the pre-run `no_consist` ONNX/persona export after validating its
  original SHA-256 hashes.

## 2026-09-02 - Expanded Zone Point Metadata Repair

- Follow-up verification is in progress through the reattached official UE MCP
  bridge. The first full actor-property audit found one duplicate reference in
  `Rest.Apt_01` and one unreferenced default interaction point, so the native
  repair path is being strengthened before the final map/PIE sign-off.

- Rebuilt `cnzoiEditor` successfully after adding the editor-only
  `UPCSPZoneLayoutCommandlet` module; the previous compile blockers were the
  unavailable `EditorLoadingAndSavingUtils.h` include and an `FName`/`FString`
  mismatch in `SetActorLabel`.
- Ran `-run=PCSPZoneLayout -Repair` against
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio`. The commandlet loaded the map,
  normalized and saved all 592 interaction points so each now inherits its
  parent zone's tag and affordance category, and set zones/points non-spatially
  loaded for the current World Partition baseline.
- The commandlet completed with `PCSP zone repair complete: normalized 592
  interaction points.` The user-authored
  `EQS_PCSP_SelectAffordanceZone.uasset` remains present and untouched.
- A visible UE 5.8 editor was reopened afterward. Its local official toolsets
  initialized, but the external MCP endpoint was not exposed to this Codex
  session, so a final remote PIE invocation is deferred until that endpoint is
  reattached.

## 2026-09-02 - Zone Expansion MCP And PIE Sign-off

- Restarted the UE 5.8 editor with the official
  `ModelContextProtocol.StartServer 8000` command. The configured
  `http://127.0.0.1:8000/mcp` endpoint reconnected and loaded
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio`.
- The first complete MCP property audit found one duplicate reference in
  `Rest.Apt_01` and one unowned, default-metadata interaction point. Updated
  `UPCSPZoneLayoutCommandlet -Repair` to remove duplicate references, attach
  any orphan point to its nearest zone, require exactly 592 uniquely assigned
  points, then persist the native World Partition packages.
- `cnzoiEditor Win64 Development` rebuilt successfully. The repaired
  commandlet completed with `normalized 592 points, removed 1 duplicate
  references, reattached 1 orphan points`.
- A post-save MCP batch audit passed: 96 zones, 592 interaction points, 592
  unique parent links, zero zone/point metadata or spatial-loading violations.
  `EQS_PCSP_SelectAffordanceZone` exists at
  `/Game/PCSP/AI/EQS/EQS_PCSP_SelectAffordanceZone` and was not modified.
- Simulate PIE smoke session `Saved/PCSP/Logs/20260902_001749/` ran for more
  than 10 seconds. `PCSPPolicySubsystem` initialized with `obs=33`,
  `persona_dim=64`, and `n_actions=20`; NavMesh was ready after 0.5 seconds
  and the spawner created 16 Hero agents. The session produced 16 agent logs,
  55 decision events, and zero `move_failed` events. No fatal PCSP, ONNX, or
  Behavior Tree error was logged.

## 2026-09-02 - Async Spatial, Flow-Field, And ONNX Insights Ablation

- Added native Unreal Insights scopes for Actor observation/social work, Mass
  execution, path scheduling, synchronous/worker ONNX inference, spatial
  snapshot/grid/apply, and flow-field snapshot/build/query. Added
  `tools/export_insights_stats.ps1` for repeatable headless CSV export and
  extended `tools/run_scaling_sweep.ps1` with trace channels, absolute trace
  paths, optional memory tracing, and experiment CVars.
- Implemented `UPCSPSpatialQuerySubsystem`: the game thread copies weak actor
  identities and POD positions/radii, a ThreadPool uniform-grid job computes
  neighbor/nearest results without UObject access, and the next tick commits
  results. `pcsp.AsyncSpatialQueries` retains the legacy fallback. At 128 Actor
  agents across seeds 0/1/12, targeted GT cost fell from
  `637.85 +/- 78.55` to `85.90 +/- 8.72 ms` per 30-second capture
  (`86.4 +/- 2.1%` reduction); worker cost was `17.68 +/- 1.88 ms` per capture.
- Implemented `UPCSPFlowFieldSubsystem`: a GT NavMesh/grid/zone snapshot feeds
  a worker multi-source four-neighbor integration build, and Mass movement uses
  O(1) direction/goal lookups. On the current flat map with one relevant shared
  destination, it increased `PCSP_Mass_Execute` `0.510 -> 0.515 ms/frame`, left
  frame mean unchanged (`106.38 -> 106.47 ms`), and reduced post-warm-up
  decisions/arrivals by `19.4%/15.2%`. It remains disabled pending an
  obstacle-rich, multi-goal benchmark.
- Implemented Mass-only asynchronous dynamic-batch ORT inference behind
  `pcsp.AsyncInference`, with configurable `pcsp.InferenceBatchSize` (default
  32). Inputs/personas are copied on GT; a separate NNE model instance runs on a
  worker; actions are committed by stable entity ID next frame; shutdown joins
  the future. Actor/BT inference remains synchronous.
- At 16 Hero + 1,008 Mass agents across seeds 0/1/12, ONNX-related GT time fell
  `1.142 +/- 0.017 -> 0.045 +/- 0.003 ms/frame` and Mass execution fell
  `1.586 +/- 0.026 -> 0.566 +/- 0.036 ms/frame`. Worker inference cost was
  `0.978 +/- 0.009 ms/frame`. Frame mean/p95 improved
  `107.31/112.24 -> 104.26/108.37 ms`; these absolute values are contaminated by
  a concurrently open editor and do not replace the clean 2026-09-01 result.
  Aggregate decisions/arrivals changed only `-0.6%/-0.3%`.
- Primary telemetry sessions: spatial legacy/async seed 0
  `20260902_014934`/`20260902_015343`, seed 12
  `20260902_021444`/`20260902_021551`, seed 1
  `20260902_021658`/`20260902_021805`; ONNX sync/async seed 0
  `20260902_021125`/`20260902_021235`, seed 1
  `20260902_021954`/`20260902_022101`, seed 12
  `20260902_022208`/`20260902_022319`; final flow OFF/ON pair
  `20260902_022545`/`20260902_022656`.
- Full protocol, per-seed tables, trace directories and adoption gates are in
  `docs/portfolio/benchmarks/async-systems-20260902.md`. Spatial and ONNX remain
  opt-in until a clean 300-second x 3-seed trajectory-equivalence sweep passes;
  no research observation/action/export contract changed, so no retraining or
  `research/PLAN.md` update is required.
- Final UE 5.8 editor target build succeeded as suffixed module `9026` while the
  user's original editor remained open. An all-features 1,024-NPC smoke
  (`pcsp.AsyncSpatialQueries=1`, `pcsp.AsyncInference=1`, flow field on) exited
  normally at 15 seconds in session `20260902_023343`, produced all 16 Hero logs
  plus Mass telemetry, and recorded zero Hero `move_failed` events. No ONNX
  batch failure or fatal PCSP error appeared; the only ensure was the pre-existing
  `t.IdleWhenNotForeground` config warning during engine startup.

## 2026-09-02 - Mass Default-Character Representation And Insights A/B

- Replaced the Mass cylinder proxy with `/Game/PCSP/Mass/SM_Manny_Mass`, baked
  from the same `SKM_Manny_Simple` mesh/material slots referenced by
  `BP_PCAPAgent`. Every Mass entity now renders as the default character through
  one HISM; movement direction also drives instance yaw.
- Added `tools/bake_mass_manny_static.py`. The helper uses the bundled
  `AnimToTexture` editor conversion API, generates a 5%-triangle static LOD1,
  and saves the reusable asset. Runtime forces LOD1 to prevent nearby Mass
  instances from switching back to the expensive source LOD0.
- Rejected one `USkeletalMeshComponent` per Mass entity: session
  `20260902_023955` measured `234.14 ms` mean frame time. A leader-pose variant
  in `20260902_024233` was worse at `316.27 ms`; sharing bone evaluation did not
  eliminate 1,008 skeletal render proxies. Manny LOD0 HISM session
  `20260902_025644` still measured `231.62 ms` and was also rejected.
- Added default-on `pcsp.MassCharacterRepresentation` plus an early command-line
  override and `run_scaling_sweep.ps1 -MassCharacterRepresentation 0/1`.
  Mode `0` retains the legacy cylinder strictly for repeatable profiling; normal
  runtime defaults to Manny mode `1`.
- Same build `9032`, seed `107`, 16 Hero + 1,008 Mass, 15-second paired Insights
  runs measured cylinder session `20260902_031453` versus Manny session
  `20260902_031548`: telemetry frame mean `111.82 -> 114.54 ms` (`+2.4%`),
  Insights `Frame` `115.36 -> 118.06 ms` (`+2.3%`), `RenderViewFamily`
  `108.57 -> 111.25 ms`, and `BasePass` `1.30 -> 3.91 ms`. Both runs produced
  all 16 Hero logs, 14 Mass telemetry windows, and zero `move_failed` events.
  Absolute frame times remain contaminated by the already-open editor; the
  paired delta is the result.
- Trace and exported timer CSVs are under
  `Saved/Profiling/PCSP/mass_rep_ab_cylinder_final/` and
  `mass_rep_ab_manny_final/`. Full table and reproduction command:
  `docs/portfolio/benchmarks/mass-character-representation-20260902.md`.
- Final editor target build succeeded as suffixed module `9032`. No research
  observation/action/export contract changed, so retraining and a
  `research/PLAN.md` update are not required.

## 2026-09-03 - Korean End-to-End Technical Portfolio

- Authored repository-root `PORTFOLIO.md`: "NPC 1,024명, 정책은 하나".
  The portfolio connects persona-conditioned shared RL, gradient/independent
  evaluation audits, ONNX deployment contracts, the Actor navigation ceiling,
  All-Mass architecture, targeted async pilots, rejected flow-field/rendering
  variants, instrumentation, and current Mass-first HUD work.
- Replaced the previous proposed mixed-tier headline with the confirmed
  `all_mass_portfolio_20260902` 12-run matrix: 0 Actor NPCs, 1,024 Mass entities,
  mean 28.42 +/- 0.17 ms and window-p95 aggregate 34.14 +/- 0.11 ms.
  Preserved mean/population-SD definitions, 60-second runs with 5-second warm-up,
  800x450/static-Manny conditions, and Mass arrivals rather than Actor-completion
  semantics. Actor failure zeros are explicitly not Mass reliability evidence.
- Separated historical Actor/mixed-tier results and opt-in async component
  measurements from the all-Mass benchmark. The newer GPU-animated/slot-aware
  demo still needs fresh visible performance and memory measurements.
- Copied the existing 1920x1080 functional screenshot to
  `docs/portfolio/assets/portfolio-mass-demo-20260903.png` without image edits.
  Source and SHA-256 provenance are recorded in `portfolio-assets.md`; the
  image is never used as evidence for the older benchmark's frame time.
- Added entry links in root and portfolio READMEs and connected the work to
  PLAN Phase 5. No source code, model, map, research API, or experiment results
  were changed; no retraining or runtime benchmark was performed for this
  documentation task.
- Documentation verification: all 51 main-document links/anchors resolve;
  16 performance mean/SD cells match source JSON within display rounding;
  all 12 source sessions are all-Mass with zero Actor NPCs; screenshot hashes
  match; scoped `git diff --check` is clean.


## 2026-09-05 — Separate portfolio evaluation axes and restartable HUD

- Added `UPCSPEvaluationSubsystem` (GameInstance archive/setup) and a dedicated
  evaluation sampler. HUD tabs separate persona effect, Actor+BT versus Mass,
  and individual synchronous versus worker-batched inference. Mass rules are
  labelled Needs heuristic; removed automatic FPS-vs-BT percentages.
- Variant buttons reload the current world and retain comparison results and
  camera. Count/seed changes create new series; completed runs last 30 seconds
  after population readiness and 5-second warmup. Context changes invalidate
  recording. Per-run CSV/JSON and separate trajectory directories prevent
  policy variants from mixing during map travel.
- Added individual-frame p95, policy service/latency, decision throughput,
  actual sync/worker request counts, failure counts, action entropy and
  per-persona action histograms. These measure outputs, not completed actions
  or persona fidelity. Architecture remains a whole-stack comparison because
  existing spawn/observation/movement/representation semantics differ.
- Added fixed-input replay of up to 32 captured observations and persona IDs,
  alternating six repetitions after warming both paths. Logit agreement gate
  is max absolute difference <= 0.001. First validated fixture had zero error:
  `Saved/PCSP/Evaluation/fixed_input_992002364DFB201A1D66A6931DA15E75.json`.
  Replay timing is a microbenchmark; it is not a frame-rate claim.
- Added `tools/run_evaluation.py`, `summarize_evaluation.py`, and Python tests.
  Matrix rotates variant order across seeds and records full commands/results.
  Native tests `PCSP.Performance.EvaluationAxes` and `WallClockAndCPU` passed
  in `Saved/PCSP/evaluation_automation_final.log`; both Python tests passed.
- Actor+BT 16 -> Mass 16 fresh-map travel passed, preserving both results:
  `Saved/PCSP/Evaluation/3CF725D44C406110F42236BF62B4E199/`.
  Three fresh-process persona variants passed with CSV/JSON arithmetic checks:
  `Saved/PCSP/Evaluation/suite_48b68f7c552f4c559483c7b60cc8214d/manifest.json`.
  These NullRHI runs are excluded from performance summaries by design.
- Rendered 1280x720 inference-tab travel and fixed-input replay passed in
  `Saved/PCSP/evaluation_inference_render.log`, captures in
  `Saved/PCSP/Evaluation/5F35AC094B775EDD24218991C0ED4CE4/`.
- Build: cnzoiEditor Win64 Development succeeded with runtime suffix 9509.
  Open editor held previous DLLs, so it was left running. UBT suffix linking
  retained an unsuffixed runtime import in cnzoiEditor; relinked the generated
  editor response against `UnrealEditor-cnzoi-9509.lib` to editor suffix 9510
  and updated generated `UnrealEditor.modules`. Fresh Entry editor startup
  and native tests then passed. A normal unsuffixed build after closing the
  editor remains the clean release path; generated binaries are not committed.
- Failed attempts: simultaneous Visual-map validation alongside the open
  editor exhausted system/GPU memory. Retried native tests in Entry and
  rendered HUD validation in the smaller Portfolio map. Toolset Python
  startup errors and GameFeatureData configuration warnings are pre-existing.
  No target-GPU performance or 1,024-Visual acceptance claim is made.
- User guide: `docs/portfolio/evaluation-axes.md`. Research PLAN now records
  the separated UE protocol; research observation/action/export contracts and
  COG results are unchanged.

Final 9509 runtime render verification: `Saved/PCSP/evaluation_inference_final.log`
and `Saved/PCSP/Evaluation/4314003E419ED554FA8EF3A97B5EEF39/` passed both
variants with matching context and verified nonzero worker requests only in
the batch variant. Final 1280x720 screenshot inspected; no table/footer overlap.

## 2026-09-05 - Detailed portfolio learning/runtime documentation

- Authored `../../output/portfolio-continuation/PCSP_포트폴리오_상세설명.md` with
  source-checked learning definitions, UE action mapping, HUD interpretation,
  historical benchmark conditions and optimization evidence boundaries.
- Direct builder comparison records unresolved semantic differences: Mass
  affordance slots encode Intent categories in UE enum order rather than Python
  nearest-facility order; slots 24–32 remain zero; remapped actions can change
  social-history flag meaning. Actor observations also differ from Python.
  Matching 33/64/20 dimensions is not full observation/behavior equivalence.
- Follow-up is observation/action semantic alignment or an explicitly evaluated
  UE-specific contract, with retraining implications reviewed before changes.
  Documentation only: no runtime code, assets, model, research contract or
  evaluation protocol changed. Existing measurements were not rerun.

## 2026-09-05 - PPT-ready persona trajectory and training visuals

- Captured a clean top-down source image of
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual` through the official
  Unreal MCP. Existing map content was sufficient, so no UE level or asset was
  created or modified.
- Added `tools/generate_persona_training_assets.py` and generated three
  persona-specific colored decision-position traces (sociable persona 3,
  independent persona 7, active/exploratory persona 16), plus a shared
  comparison image under `docs/portfolio/assets/persona-training/`.
- Generated English PNG/SVG curves for behavior diversity and trajectory-
  persona consistency from the actual PCSP v3-large seed 42/43/44 logs. Curves
  use a 15-iteration moving average and show the three-seed mean and spread;
  the consistency chart keeps the raw loss direction and labels lower as
  better instead of inventing a normalized score.
- Recorded exact source paths, camera transform, persona colors, derived path
  lengths, action counts, and curve processing in
  `docs/portfolio/assets/persona-training/provenance.json`. Trajectory lines
  connect logged decision positions and are not high-frequency NavMesh route
  samples. Research results, contracts, and evaluation protocols are unchanged.
# 2026-09-06 — Reward-versus-persona portfolio page

- Added `docs/portfolio/reward-vs-persona.html` and the fixed render
  `docs/portfolio/assets/reward-vs-persona.png`.
- Reframed InfoNCE in portfolio language as the training rule that links an
  NPC's action record to its persona description, while preserving the precise
  boundary that the learned retrieval metric is not an independent behavior
  evaluator.
- Recomputed late-training reward summaries from the final 50 iterations of
  the v3 unseen-occupation Full and no-consistency logs: `106.3 +/- 5.5` and
  `107.8 +/- 7.4`. The page separately identifies the paper's `104.1` and
  `118.4` values as final-iteration training rollouts.
- Combined the 60-way learned retrieval result, the v3-large three-seed
  independent behavior audit, and the 30-participant coarse 2AFC pilot into
  four explicitly separated evidence axes: task score, learned trace,
  independent behavior, and human reading.
- Updated the root `PORTFOLIO.md`, portfolio asset provenance, and portfolio
  index to reference the new page.

## 2026-09-06 - 4K portfolio cover capture

- Raised the 24 Dieselpunk portfolio textures' maximum imported resolution to
  4096 and verified every affected texture saved with a 4096 effective resource
  size. The pre-change 2048 assets remain recoverable under
  `Saved/PCSP/Backups/texture_2048_before_4096_20260906_0415/`.
- Added `tools/capture_portfolio_cover.py` and captured a direct 3840 x 2160
  SceneCapture2D render from
  `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio_Visual`. The final boulevard view
  uses TSR, 200% history resolution, 0.7 sharpening, forced high-detail LOD and
  streaming, 72-degree horizontal FOV, and +2 EV exposure.
- The presentation capture hides `City_Affordance_*` components only on the
  transient capture camera, so colored development markers and editor UI are
  absent while the map asset remains unchanged.
- Final cover: `docs/portfolio/assets/pcsp-portfolio-cover-4k.png` (3840 x 2160,
  SHA-256 `90F7B947C685E0A3883997DA5FD25207F336DC30945A8D70FB5E189772446FBC`).
  A 1:1 pixel crop was inspected to confirm facade, brick, pipe, and window
  detail rather than relying on an upscaled viewport screenshot.

## 2026-09-06 - Training-result portfolio page

- Added `docs/portfolio/training-result.html` and the fixed 1600 x 1000 render
  `docs/portfolio/assets/training-result.png`.
- Extended `tools/generate_persona_training_assets.py` with the compact
  `training-result-curves.{png,svg}` summary. It uses the existing v3-large
  seed 42/43/44 metrics, a centered 15-iteration moving average, the three-seed
  mean, and a +/- one-standard-deviation band. The displayed terminal values
  are the recomputed means: diversity objective `0.015948` and consistency
  loss `2.564416 -> 1.604794`.
- The page compares the recorded decision-position traces for persona IDs 3,
  7, and 16 on the same UE5 top view and tabulates their actual recorded
  duration, path-length estimate, decision count, and top action frequencies.
  It explicitly identifies these as one approximately 131-second record and
  not continuous NavMesh samples or a population-wide generalization.
- Research metrics, training runs, UE runtime code, and evaluation contracts
  were not changed; this work only adds a reproducible portfolio presentation.

## 2026-09-06 - Environment-optimization portfolio page

- Added `docs/portfolio/environment-optimization.html` and its fixed 1600 x
  1000 render at `docs/portfolio/assets/environment-optimization.png`.
- Extended `tools/generate_portfolio_visuals.py` with the compact
  `environment-optimization-summary.{png,svg}` figure. It reads the existing
  Actor/BT scaling JSON, visible All-Mass scaling JSON, and matched Unreal
  Insights cylinder/Manny timer exports directly.
- The page presents the evidence as a three-stage engineering loop: locate the
  128-Actor movement-failure cliff, rebuild the background tier around Mass
  chunks/cohort scheduling/HISM representation, then attribute the remaining
  representation delta to rendering (`Frame +2.69 ms`, `BasePass +2.62 ms`,
  `PCSP_Mass_Execute +0.12 ms`). Inclusive scopes are not added together.
- The 128-to-1,024 All-Mass result is reported as bounded incremental cost
  (`+2.21 ms` frame mean, `+4.98 ms` p95) and explicitly not as a 60-FPS
  result. Panels with different protocols are not presented as an absolute
  before/after comparison. Research data, runtime code, and benchmarks were
  not modified.
# 2026-09-06 — Shipping camera and Mass presentation diagnosis

- Reproduced the staged Shipping executable in an unattended evaluation run.
  `Saved/PCSP/Logs/20260906_222849/mass_stats.jsonl` recorded continuous entity
  updates, route movement, decisions, and arrivals, proving the policy and Mass
  simulation were running despite the reported frozen presentation.
- Scheduled `APCSPMassSpawner` in `TG_PostPhysics` and force-enabled its actor tick
  at BeginPlay. Its ISM representation pass intentionally avoids fragment reads
  while Mass is processing; the old default tick group could therefore leave
  positions, category materials, and animation frozen at their spawn state in a
  packaged run while HUD intent counts continued to change.
- Tuned non-agent free-camera pawns from the demo controller to 8,000 uu/s max
  speed, 24,000 uu/s2 acceleration, and 32,000 uu/s2 deceleration. The agent follow
  camera remains unchanged.
- Corrected `GlobalDefaultGameMode` from the nonexistent `/Game/Game/...` path to
  `/Game/PCSP/Blueprints/Core/BP_SimGameMode`, removing the corresponding cook
  warning and making packaged startup independent of the map override.
- `cnzoi Win64 Shipping` compiled and linked successfully. A full Windows
  BuildCookRun then cooked 1,653 packages and rebuilt the staged IoStore package
  under `Saved/StagedBuilds/Windows`; the stale GameMode cook warning did not
  recur. Rendered acceptance remains required.

## 2026-09-07 - Shipping Blueprint serialization crash repair

- The packaged executable crashed at startup with `ObjectSerializationError` and
  `Bad export index 67108863/11` while loading
  `BP_PCSPDemoPlayerController.Default__BP_PCSPDemoPlayerController_C`.
- Root cause: the running editor locked `UnrealEditor-cnzoi.dll`, so the editor
  target could not relink after three reflected camera-tuning properties were
  added to the native controller. Cook then serialized the Blueprint child using
  the old parent layout while the Shipping executable loaded it with the new one.
- Removed those tuning values from reflection and retained them as non-serialized
  C++ constants. This restores the previous Blueprint property layout without
  requiring the user's editor process to be terminated.
- Rebuilt the Shipping target and restaged the Windows IoStore package. The new
  `Saved/StagedBuilds/Windows/cnzoi.exe` completed an unattended packaged launch
  on 2026-09-07 in 12.7 seconds with exit code 0; no new crash report was
  generated. The newest crash directory therefore remains the pre-fix 01:07:31
  report. On-screen movement and category-tint acceptance still require a normal
  rendered launch.

## 2026-09-07 - Packaged Mass NPC click routing repair

- The initial `SelfHitTestInvisible` change on the viewport-sized
  `WBP_PCSPDemoHUD` and root canvas was insufficient in the packaged build: the
  user's retest confirmed that the controller's legacy LeftMouse binding still
  did not receive world clicks reliably under `GameAndUI` routing.
- Added a transparent full-viewport `WorldClickSurface` button at the lowest HUD
  Z-order. Slate now deliberately handles empty HUD-space clicks and forwards
  them to the controller's shared Actor/Mass cursor-picking implementation.
  Existing cards and controls remain above the surface and keep their normal
  interactions. The legacy controller binding remains as a non-UMG fallback.
- Renamed the shared native entry point to `SelectAgentUnderCursor` and exposed it
  to the HUD without adding serialized fields. `cnzoiEditor Win64 Development`
  and `cnzoi Win64 Shipping` compiled and linked successfully.
- Performed a non-incremental cook of all 1,653 packages and rebuilt the Windows
  IoStore stage. The resulting package completed a 12.9-second unattended launch
  with exit code 0. A physical rendered click remains the final manual acceptance
  because NullRHI cannot exercise OS-to-Slate pointer routing.
