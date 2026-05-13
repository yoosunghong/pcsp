# CNZOI UE5 Proposal

## Summary

CNZOI is the Unreal Engine 5 implementation track for PCSP: Persona-Conditioned Shared Policy for scalable NPC control. The goal is to move beyond the Python Mini-Inzoi grid benchmark and demonstrate persona-conditioned NPC behavior in a continuous-space UE5 sandbox.

The proposed system combines a shared learned policy with Unreal-native AI execution. PCSP selects high-level intent from persona and observation inputs; Behavior Trees, Blackboard keys, EQS, AIController, and NavMesh execute that intent in the world.

## Motivation

The current research implementation validates PCSP in controlled Python environments, but the paper framing identifies two important extension needs:

- Engine integration: show that the approach can operate inside a real-time simulation engine.
- Richer observability: expose persona-conditioned behavior through trajectory traces, spatial context, social context, congestion, and interaction outcomes.

UE5 is a natural next step because it provides continuous navigation, behavior authoring tools, world objects, animation hooks, and scalable visual demonstration assets.

## Proposed System

### High-Level Flow

```text
Persona Text
  -> Persona Embedding / Projection
  -> PCSP Shared Policy
  -> Behavior Tree Decision Node
  -> Blackboard Goal State
  -> Affordance Selection, Movement, Interaction, Recovery
  -> Trajectory Logging And Evaluation
```

### Core UE5 Modules

- `ASimWorldManager`: episode flow, spawning, time, and evaluation coordination.
- `ANPCCharacter`: NPC body, animation hooks, and owned components.
- `UPersonaComponent`: persona text, embedding, and projected vector storage.
- `UNeedsComponent`: need decay and restoration.
- `USocialContextComponent`: relationships, compatibility, and recent interactions.
- `UObservationComponent`: fixed-length observation vector generation.
- `UAffordanceManager`: affordance zone and interaction point registration/query.
- `UBTTask_PCSPDecision`: high-level action selection.
- `UBTTask_MoveToAffordance`: target lookup, reservation, and NavMesh movement.
- `UBTTask_PerformInteraction`: semantic interaction execution.
- `UTrajectoryRecorder`: rich trajectory export.
- `UPCSPBridge`: Python/ONNX/TorchScript inference integration.

## Action Ontology

The first UE5 policy-facing action set should be semantic rather than movement-based. Candidate actions:

- `EatQuick`
- `EatSlow`
- `RestAlone`
- `RestWithOthers`
- `FocusedWork`
- `PlanningWork`
- `DeepStudy`
- `CasualLearning`
- `ExerciseSolo`
- `ExerciseSocial`
- `HygieneQuick`
- `HygieneCareful`
- `SocializeInitiate`
- `SocializeRespond`
- `LeisureIndoor`
- `LeisureOutdoor`
- `ShopEssentials`
- `BrowseArea`
- `ObserveCrowd`
- `IdleReflect`

## Observation Direction

The first UE5 observation vector should remain fixed-length and debuggable, roughly 32-48 dimensions. It should prioritize:

- Self needs.
- Time context.
- Current zone and crowding context.
- Nearby social context.
- Target affordance availability.
- Routine and recent repetition signals.
- Minimal persona memory hooks.

Multimodal inputs, heatmaps, graph embeddings, and memory retrieval can be added later after the fixed-vector version is stable.

## Evaluation

The UE5 track should preserve the research metrics where possible and add engine-specific metrics:

- Zero-shot persona identification accuracy.
- Semantic-behavioral alignment, including Spearman rho.
- Mean policy KL divergence.
- Batch inference latency.
- Task completion under congestion.
- Path efficiency and failed interaction rate.
- Human readability of rich trajectory clips.

## Expected Deliverables

- UE5 life-simulation sandbox with 16-64 NPCs.
- Hybrid PCSP + Behavior Tree NPC control framework.
- Persona-conditioned NPC demonstration clips.
- Python/UE5 comparison experiments.
- Architecture diagrams and performance tables.
- Paper extension material for "Engine-Integrated Hybrid Persona Control".
