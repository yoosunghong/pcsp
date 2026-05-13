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

## Open Follow-ups

- Define the first UE5 affordance taxonomy.
- Write the BT-Blackboard-Policy interface contract.
- Decide the initial inference bridge: Python service, ONNX Runtime, or TorchScript.
- Confirm which Python artifacts are required for UE5 runtime loading.
