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

### Phase 1: Continuous-Space Prototype

- [ ] Build a Medium district level (editor: BP_PCSP_District map under `Content/PCSP/Maps/`).
- [x] Spawn and schedule 16 agents (C++ `APCSPAgentSpawner`, configurable `AgentCount`).
- [ ] Create NavMesh, affordance zones, and interaction points
      (C++ `APCSPAffordanceZone`, `APCSPInteractionPoint`, and `UPCSPAffordanceSubsystem` are in place;
      editor work: place `RecastNavMeshBoundsVolume` + zone instances in the map).
- [x] Implement needs, social, and observation components
      (`UPCSPNeedsComponent`, `UPCSPSocialContextComponent`, `UPCSPObservationComponent`,
       plus `UPCSPPersonaComponent` and `UPCSPTrajectoryLogComponent` skeletons).
- [ ] Build the baseline Blackboard-driven Behavior Tree skeleton
      (C++ `UBTTask_PCSPDecision` stub + `PCSPBlackboard::*` key names are in place;
       editor work: author BT_PCSPAgent + BB_PCSPAgent assets matching those keys).

### Phase 2: Hybrid Behavior Tree Implementation

- [ ] Implement `UBTTask_PCSPDecision` or `UBTService_PCSPDecision`.
- [ ] Implement `UBTTask_MoveToAffordance`.
- [ ] Implement `UBTTask_PerformInteraction`.
- [ ] Add retry, reservation conflict handling, congestion handling, and fallback behavior.
- [ ] Add an emergency branch for critical needs.

### Phase 3: PCSP Policy Integration

- [ ] Implement persona embedding cache loading.
- [ ] Load projected persona vectors.
- [ ] Connect Python inference, ONNX Runtime, or TorchScript inference.
- [ ] Add batch and async inference.
- [ ] Export reward and trajectory logs.

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
