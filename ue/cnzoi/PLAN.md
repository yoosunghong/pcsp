# CNZOI UE5 Development Plan

This document is the active implementation plan for the Unreal Engine 5 side of PCSP. It is derived from `PCSP_UE5_Implementation_Plan.md` and should be updated whenever the UE5 architecture, task order, or research interface changes.

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

- [ ] Summarize the Python Mini-Inzoi reward, observation, and action logic.
- [ ] Define the UE5 affordance taxonomy.
- [ ] Write the BT-Blackboard-Policy interface specification.
- [ ] Confirm Main and Stress scale targets.

### Phase 1: Continuous-Space Prototype ✅ Complete (2026-05-16)

- [x] Build a Medium district level (`Content/PCSP/Maps/Map_PCSPDistrict_M.umap`).
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
- [ ] Congestion handling — EQS or weighted zone scoring when multiple agents compete for the same zone (deferred to Phase 3 scaling work).
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
- [ ] Export reward and trajectory logs from `UPCSPTrajectoryLogComponent` (Phase 4).

### Phase 4: Scaling And Experiments

- [ ] Test 32 agents.
- [ ] Stress test 64 agents.
- [ ] Automate zero-shot persona evaluation.
- [ ] Collect Spearman rho, policy KL, latency, path failure, and congestion metrics.
- [ ] Compare BT-only, RL-only, Hybrid-PCSP, Hybrid-NoConsist, and Hybrid-NoPersona settings.

### Phase 5: Paper And Portfolio Artifacts

- [ ] Prepare implementation diagrams.
- [ ] Capture rich trajectory clips.
- [ ] Prepare UE5 screenshots, performance tables, and architecture figures.
- [ ] Draft the paper extension section: "Engine-Integrated Hybrid Persona Control".

## Working Rules

- Treat this file as the active UE5 task plan.
- Keep `PROPOSAL.md` aligned with the high-level research and product rationale.
- Record completed tasks, decisions, result paths, failed attempts, and retraining requirements in `DONE.md`.
- If a UE5 change alters the Python research API, observation schema, action ontology, or training/export contract, also update `../../research/PLAN.md`.
- Do not commit Unreal-generated build/cache directories unless explicitly required.
