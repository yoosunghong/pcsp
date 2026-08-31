# PCSP Unreal Engine Runtime

`cnzoi/` is the Unreal Engine 5.8 deployment of PCSP. It turns a shared
persona-conditioned ONNX policy into executable NPC behavior through a hybrid
Behavior Tree/affordance stack and scales background simulation with Mass Entity.

## Runtime architecture

| Layer | Responsibility |
| --- | --- |
| `UPCSPPolicySubsystem` | Loads the ONNX actor and cached persona embeddings; maps the 20 policy actions to authored affordance categories |
| `BTTask_PCSPDecision` | Builds the 33-dimensional observation and writes semantic intent to the Blackboard |
| `BTTask_MoveToAffordance` | Selects/reserves a destination and executes high-fidelity movement |
| `UPCSPPathRequestSchedulerSubsystem` | Applies urgency/fairness ordering and caps new Actor-tier `MoveTo` requests per frame |
| `UPCSPMassSimulationProcessor` | Updates persona, needs, decisions, zone targets, and movement for background entities in chunks |
| `APCSPMassSpawner` | Creates the Mass archetype and low-frequency HISM representation |
| `UPCSPTrajectoryLogComponent` | Emits per-agent decision, movement, interaction, latency, and ablation traces |

The default portfolio configuration is **16 hero Actor NPCs + 1,008 Mass
background NPCs**. Hero NPCs retain CharacterMovement, AIController, Blackboard,
Behavior Tree, collision, and NavMesh paths. Background NPCs retain semantic
persona state and needs but use a cheaper zone-level movement approximation.

## Project requirements

- Unreal Engine 5.8 with a complete C++ build installation
- Visual Studio 2022 C++ game-development workload
- Enabled plugins: NNE Runtime ORT, Mass Gameplay, Mass AI, Mass Crowd,
  ZoneGraph, Smart Objects, StateTree, and Gameplay StateTree
- `Content/PCSP/Models/pcsp_actor.onnx`
- `Content/PCSP/Data/persona_embeddings.json`

The project enables Unreal Engine 5.8's official `ModelContextProtocol` plugin
and the `AllToolsets` bundle. `.mcp.json` connects MCP clients to
`http://127.0.0.1:8000/mcp`; launch the editor with
`-ModelContextProtocolStartServer -ModelContextProtocolPort=8000` when editor
automation is required.

## Build and open

From a Developer PowerShell:

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" `
  cnzoiEditor Win64 Development `
  "D:\Github\pcsp\ue\cnzoi\cnzoi.uproject" `
  -WaitMutex -NoHotReloadFromIDE
```

Open `cnzoi.uproject` and use one of these maps:

- `/Game/PCSP/Maps/Map_PCSPDistrict_M` — default simulation map
- `/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio` — presentation/capture map

The map must contain authored `APCSPAffordanceZone` actors and a
`BP_PCSPAgentSpawner`. The GameMode, player controller, AI controller,
Blackboard, Behavior Tree, HUD widgets, and agent Blueprints are already under
`Content/PCSP/Blueprints/`.

## Scaling modes

### Actor/Behavior Tree baseline

```text
-PCSP_AgentCount=64
-PCSP_MassEntityCount=0
-PCSP_SpawnSeed=0
-PCSP_RunDurationSeconds=300
```

This is the high-fidelity baseline. The existing sweep found a practical 64-NPC
operating point; a burst of independent path requests becomes the dominant
failure mode at 96–128 Actors.

### Mass-hybrid 1,024 NPCs

```text
-PCSP_AgentCount=16
-PCSP_MassEntityCount=1008
-PCSP_SpawnSeed=0
-PCSP_RunDurationSeconds=300
```

Or run the full matrix:

```powershell
cd D:\Github\pcsp\ue\cnzoi
./tools/run_scaling_sweep.ps1 `
  -MassHybrid `
  -TotalNpcCounts 128,256,512,1024 `
  -HeroAgentCount 16 `
  -Seeds 0,1,2 `
  -DurationSeconds 300
```

Useful runtime controls:

| CVar | Default | Purpose |
| --- | ---: | --- |
| `pcsp.PathSchedulingEnabled` | `1` | Enable bounded Actor-tier path admission |
| `pcsp.PathRequestsPerFrame` | `8` | Maximum newly released `MoveTo` permits per frame |
| `pcsp.MassDecisionInterval` | `1.0` | Background semantic-decision interval in seconds |
| `pcsp.MassMaxDecisionsPerFrame` | `32` | Maximum background policy decisions in one frame |
| `pcsp.MassMoveSpeed` | `260` | Background zone-level movement speed in cm/s |

## Telemetry and analysis

Each run writes to `Saved/PCSP/Logs/<timestamp>/`:

| File | Contents |
| --- | --- |
| `run_config.json` | total, hero, and Mass counts plus seed |
| `agent_p*.jsonl` | rich sampled Actor trajectories and inference latency |
| `frame_stats.jsonl` | frame mean/p50/p95/p99 samples |
| `zone_occupancy.jsonl` | affordance capacity utilization |
| `path_scheduler.jsonl` | queue depth, permits, cancellations, and wait latency |
| `mass_stats.jsonl` | entity count, decisions, arrivals, and policy cost |

Analyze one or more sessions from the repository root:

```powershell
conda run -n paper python research/scripts/analyze_scaling_sweep.py `
  --sessions ue/cnzoi/Saved/PCSP/Logs/<session-a> ue/cnzoi/Saved/PCSP/Logs/<session-b> `
  --out research/results/ue_sessions/mass_scaling_<date> `
  --plot
```

The output includes `per_session.json`, an architecture-aware
`scaling_curve.json`, `latency_budget.tsv`, and an optional comparison plot.

## What the 1,024-NPC solution proves

The engineering value is the measured transition from a failing architecture
to a tiered one:

1. Actor scaling establishes the Recast request burst as the first ceiling.
2. The path scheduler shapes high-fidelity requests without starving urgent NPCs.
3. Mass removes the per-NPC Actor/Controller/BT/NavMesh tax from the background.
4. Decision cohorts prevent all background NPCs from running ONNX in one frame.
5. Shared semantic state keeps persona-conditioned behavior comparable across tiers.

The current Mass movement is intentionally zone-level straight-line movement.
Production navigation should add ZoneGraph/MassCrowd, shared coarse-route caches,
density-aware admission, and promotion/demotion between simulation LODs. The
full design and benchmark acceptance criteria are in
[`docs/portfolio/mass-1024-scaling.md`](cnzoi/docs/portfolio/mass-1024-scaling.md).

## Portfolio documentation

- [`docs/portfolio/README.md`](cnzoi/docs/portfolio/README.md) — artifact index
- [`docs/portfolio/mass-1024-scaling.md`](cnzoi/docs/portfolio/mass-1024-scaling.md) — 1,024-NPC case study
- [`docs/portfolio/diagrams.md`](cnzoi/docs/portfolio/diagrams.md) — system diagrams
- [`docs/portfolio/observability.md`](cnzoi/docs/portfolio/observability.md) — telemetry design
- [`docs/portfolio/demo-video-hud-plan.md`](cnzoi/docs/portfolio/demo-video-hud-plan.md) — capture runbook
- [`cnzoi/PLAN.md`](cnzoi/PLAN.md) / [`cnzoi/DONE.md`](cnzoi/DONE.md) — active plan and evidence log

## Honest limitations

- The verified 1,024-entity run is a runtime smoke test; offscreen frame time is
  not valid performance evidence.
- A visible, normal-priority, three-seed sweep and Unreal Insights captures are
  still required for final FPS/CPU/memory claims.
- Mass background entities do not yet use obstacle-aware ZoneGraph navigation.
- Rich per-agent logs should remain sampled at large scale to avoid replacing
  navigation with an I/O bottleneck.
