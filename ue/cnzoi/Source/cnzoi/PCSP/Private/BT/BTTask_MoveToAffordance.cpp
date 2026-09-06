#include "BTTask_MoveToAffordance.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPAgentCharacter.h"
#include "PCSPPolicySubsystem.h"
#include "PCSPTrajectoryLogComponent.h"
#include "PCSPPathRequestSchedulerSubsystem.h"
#include "BehaviorTree/BlackboardData.h"

UBTTask_MoveToAffordance::UBTTask_MoveToAffordance()
{
	NodeName       = TEXT("Move To Affordance");
	bNotifyTick    = true;
	bNotifyTaskFinished = true;
}

// ---------------------------------------------------------------------------
// ExecuteTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_MoveToAffordance::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	new(NodeMemory) FBTMoveToAffordanceMemory();
	const EBTNodeResult::Type Result = TryBeginMove(OwnerComp, NodeMemory);
	if (Result == EBTNodeResult::Failed)
	{
		// First attempt failed before pathfollowing even started; surface it
		// to the log so we don't lose the diagnostic that TryBeginMove captured.
		EmitFinalFailure(OwnerComp, NodeMemory);
	}
	return Result;
}

// ---------------------------------------------------------------------------
// TryBeginMove  - also called on retry from TickTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_MoveToAffordance::TryBeginMove(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	auto* Memory = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);

	AAIController* AI = OwnerComp.GetAIOwner();
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!AI || !BB)
	{
		Memory->LastFailureReason = TEXT("missing_controller_or_blackboard");
		return EBTNodeResult::Failed;
	}

	APCSPAgentCharacter* Agent = Cast<APCSPAgentCharacter>(AI->GetPawn());
	if (!Agent)
	{
		Memory->LastFailureReason = TEXT("agent_not_pcsp_character");
		return EBTNodeResult::Failed;
	}

	UPCSPAffordanceSubsystem* Sub = AI->GetWorld()->GetSubsystem<UPCSPAffordanceSubsystem>();
	if (!Sub)
	{
		Memory->LastFailureReason = TEXT("subsystem_missing");
		return EBTNodeResult::Failed;
	}

	// Do not reserve an interaction point until the navigation system has room
	// for this request. At 128+ actors, releasing only a bounded number of
	// MoveTo calls per frame prevents the Recast async query queue from bursting.
	if (UPCSPPathRequestSchedulerSubsystem* Scheduler =
		AI->GetWorld()->GetSubsystem<UPCSPPathRequestSchedulerSubsystem>())
	{
		const float Urgency = BB->GetValueAsFloat(PCSPBlackboard::UrgencyScore);
		if (!Scheduler->TryConsumePermit(Agent, Urgency))
		{
			Memory->bWaitingForPathPermit = true;
			Memory->LastFailureReason = TEXT("path_request_scheduled");
			return EBTNodeResult::InProgress;
		}
	}
	Memory->bWaitingForPathPermit = false;

	const EPCSPActionType Action = static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType));
	const EPCSPAffordanceCategory Category =
		(BB->GetKeyID(PCSPBlackboard::DesiredCategory) != FBlackboard::InvalidKey)
		? static_cast<EPCSPAffordanceCategory>(BB->GetValueAsEnum(PCSPBlackboard::DesiredCategory))
		: UPCSPPolicySubsystem::ActionToCategory(Action);

	FPCSPAffordanceQuery Query;
	Query.Category       = Category;
	Query.FromLocation   = Agent->GetActorLocation();
	Query.bRequireCapacity = true;

	FPCSPZoneSelectionDebug Debug;
	APCSPAffordanceZone* Zone = Sub->FindBestZone(Query, Debug);
	if (!Zone)
	{
		Memory->LastFailureReason = FString::Printf(
			TEXT("FindBestZone:%s"), *Debug.ToCompactString());
		Memory->LastIntendedZoneTag = FGameplayTag();
		Memory->LastDistanceToTarget = (Debug.NearestDistance >= 0.f) ? Debug.NearestDistance : -1.f;
		return EBTNodeResult::Failed;
	}

	// Always record the chosen zone tag — useful even if later steps fail.
	Memory->LastIntendedZoneTag = Zone->ZoneTag;

	const int32 SlotIndex = Zone->FindFreeInteractionSlot();
	if (SlotIndex == INDEX_NONE)
	{
		Memory->LastFailureReason = TEXT("zone_no_free_interaction_slot");
		return EBTNodeResult::Failed;
	}
	if (!Zone->TryReserveInteractionSlot(SlotIndex, Agent))
	{
		Memory->LastFailureReason = TEXT("interaction_slot_reserve_race_lost");
		return EBTNodeResult::Failed;
	}

	Memory->Zone        = Zone;
	Memory->SlotIndex   = SlotIndex;
	Memory->bMoveStarted = false;
	const FVector SlotLocation = Zone->GetInteractionSlotWorldLocation(SlotIndex);

	// Write Blackboard keys so Phase 2 tasks and decorators can read them
	BB->SetValueAsObject(PCSPBlackboard::TargetActor,    Zone);
	BB->SetValueAsVector(PCSPBlackboard::TargetLocation, SlotLocation);
	BB->SetValueAsName  (PCSPBlackboard::CurrentZoneTag, Zone->ZoneTag.GetTagName());
	BB->SetValueAsBool  (PCSPBlackboard::AffordanceReserved, true);

	FAIMoveRequest MoveReq;
	MoveReq.SetGoalLocation(SlotLocation);
	MoveReq.SetAcceptanceRadius(AcceptanceRadius);
	MoveReq.SetUsePathfinding(true);
	// Treat AcceptanceRadius as a pure geometric distance, not capsule-inflated.
	// Without this, pathfollowing stops at AcceptanceRadius + AgentRadius (~40cm)
	// and our 2D distance success check (DistSq <= AcceptanceRadius^2) fires too
	// late - logs show the stop clusters at 313-331cm for a 300cm radius.
	MoveReq.SetReachTestIncludesAgentRadius(false);
	const FPathFollowingRequestResult MoveResult = AI->MoveTo(MoveReq);

	if (MoveResult.Code == EPathFollowingRequestResult::Failed)
	{
		Memory->LastFailureReason = TEXT("pathfinding_request_failed");
		const float Dist = FVector::Dist(Agent->GetActorLocation(), SlotLocation);
		Memory->LastDistanceToTarget = Dist;
		// Release what we just took so other agents can try.
		ReleaseReservation(NodeMemory, Agent);
		Memory->Zone.Reset();
		Memory->SlotIndex = INDEX_NONE;
		return EBTNodeResult::Failed;
	}

	return EBTNodeResult::InProgress;
}

// ---------------------------------------------------------------------------
// TickTask
// ---------------------------------------------------------------------------

void UBTTask_MoveToAffordance::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	auto* Memory = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);

	if (Memory->bWaitingForPathPermit)
	{
		const EBTNodeResult::Type PermitResult = TryBeginMove(OwnerComp, NodeMemory);
		if (PermitResult == EBTNodeResult::Failed)
		{
			EmitFinalFailure(OwnerComp, NodeMemory);
			FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		}
		return;
	}

	// Give the move request one tick to register before we start polling status
	if (!Memory->bMoveStarted)
	{
		Memory->bMoveStarted = true;
		return;
	}

	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI || !Memory->Zone.IsValid() || Memory->SlotIndex == INDEX_NONE)
	{
		Memory->LastFailureReason = TEXT("controller_or_target_lost_midflight");
		EmitFinalFailure(OwnerComp, NodeMemory);
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}

	APawn* Pawn = AI->GetPawn();
	// 2D distance only: Pawn location is at capsule center (z ~88cm) while
	// InteractionPoint sits on the ground, so a 3D check never satisfies an
	// 80cm acceptance radius even when the agent has clearly arrived.
	const FVector SlotLocation = Memory->Zone->GetInteractionSlotWorldLocation(Memory->SlotIndex);
	const float DistSq = FVector::DistSquaredXY(Pawn->GetActorLocation(), SlotLocation);

	if (DistSq <= FMath::Square(AcceptanceRadius))
	{
		// Arrived - clear failure counter on success
		UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
		if (BB) { BB->SetValueAsInt(PCSPBlackboard::RecentFailureCount, 0); }
		FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
		return;
	}

	if (AI->GetMoveStatus() == EPathFollowingStatus::Idle)
	{
		// Movement stopped without reaching the target. Capture distance for
		// later log so we can tell apart "no path" from "path ended short".
		Memory->LastDistanceToTarget = FMath::Sqrt(DistSq);
		Memory->LastFailureReason = FString::Printf(
			TEXT("path_follow_idle_short:dist=%.0f"), Memory->LastDistanceToTarget);

		AActor* Agent = AI->GetPawn();
		ReleaseReservation(NodeMemory, Agent);
		Memory->Zone.Reset();
		Memory->SlotIndex = INDEX_NONE;
		Memory->RetryCount++;

		if (Memory->RetryCount <= MaxRetries)
		{
			Memory->bMoveStarted = false;
			EBTNodeResult::Type RetryResult = TryBeginMove(OwnerComp, NodeMemory);
			if (RetryResult == EBTNodeResult::Failed)
			{
				// Retry path also failed - LastFailureReason has been overwritten
				// by TryBeginMove with the precise sub-cause.
				UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
				if (BB)
				{
					int32 Failures = BB->GetValueAsInt(PCSPBlackboard::RecentFailureCount);
					BB->SetValueAsInt(PCSPBlackboard::RecentFailureCount, Failures + 1);
					BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false);
				}
				EmitFinalFailure(OwnerComp, NodeMemory);
				FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
			}
			// else: TryBeginMove returned InProgress - keep ticking
		}
		else
		{
			UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
			if (BB)
			{
				int32 Failures = BB->GetValueAsInt(PCSPBlackboard::RecentFailureCount);
				BB->SetValueAsInt(PCSPBlackboard::RecentFailureCount, Failures + 1);
				BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false);
			}
			EmitFinalFailure(OwnerComp, NodeMemory);
			FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		}
	}
}

// ---------------------------------------------------------------------------
// AbortTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_MoveToAffordance::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	AAIController* AI = OwnerComp.GetAIOwner();
	if (AI)
	{
		if (UPCSPPathRequestSchedulerSubsystem* Scheduler =
			AI->GetWorld()->GetSubsystem<UPCSPPathRequestSchedulerSubsystem>())
		{
			Scheduler->CancelRequest(AI->GetPawn());
		}
		AI->StopMovement();
		ReleaseReservation(NodeMemory, AI->GetPawn());
	}

	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (BB) { BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false); }

	return EBTNodeResult::Aborted;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

void UBTTask_MoveToAffordance::ReleaseReservation(uint8* NodeMemory, AActor* Agent) const
{
	auto* Memory = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);
	if (Memory->Zone.IsValid())
	{
		Memory->Zone->ReleaseInteractionSlot(Memory->SlotIndex, Agent);
	}
}

void UBTTask_MoveToAffordance::EmitFinalFailure(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) const
{
	auto* Memory = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);
	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI) { return; }

	APCSPAgentCharacter* Character = Cast<APCSPAgentCharacter>(AI->GetPawn());
	if (!Character || !Character->TrajectoryLog) { return; }

	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	const EPCSPActionType Action = BB
		? static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType))
		: EPCSPActionType::IdleReflect;

	const FString Reason = Memory->LastFailureReason.IsEmpty()
		? FString(TEXT("unspecified"))
		: Memory->LastFailureReason;

	Character->TrajectoryLog->RecordMoveFailed(
		Action, Memory->RetryCount, Reason, Memory->LastIntendedZoneTag, Memory->LastDistanceToTarget);
}
