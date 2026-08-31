# CNZOI UE5 Development Log

Use this file to record completed UE5 work, important implementation decisions, generated artifact paths, failed attempts, and follow-up requirements.

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
- [docs/phase0/research-environment-summary.md](docs/phase0/research-environment-summary.md)
  — UE-facing summary of v3 action ontology, 33-d observation schema, reward
  function (training-only), persona splits, and the ONNX I/O contract. Pins
  the four things UE must keep stable across research updates: I/O shapes,
  action ID ordering, need ordering, persona-slot ordering.
- [docs/phase0/affordance-taxonomy.md](docs/phase0/affordance-taxonomy.md)
  — Canonical 10-category roster with per-zone capacity targets and the
  empirical provenance (Phase 4 stress-run progressions) for those numbers.
  Documents the `Leisure`-folded-into-`Observe` quirk and the
  `Is Spatially Loaded = false` World Partition rule.
- [docs/phase0/bt-blackboard-policy-contract.md](docs/phase0/bt-blackboard-policy-contract.md)
  — Wire format between policy / blackboard / BT. Every blackboard key
  (type, writers, readers, lifecycle), the policy interface
  (`RunInference` + `RunInferenceWithLogits` + `pcsp.PolicyMode` CVar),
  the three-branch BT structure, and per-task contracts for
  `BTTask_PCSPDecision` / `MoveToAffordance` / `PerformInteraction`.
- [docs/phase0/scale-targets.md](docs/phase0/scale-targets.md)
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

- Added [docs/portfolio/demo-video-hud-plan.md](docs/portfolio/demo-video-hud-plan.md).
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
  `docs/portfolio/mass-visible-benchmark-20260901.md` and a reproducible
  `mass-scaling-evidence` PNG/SVG generated from checked-in JSON.
