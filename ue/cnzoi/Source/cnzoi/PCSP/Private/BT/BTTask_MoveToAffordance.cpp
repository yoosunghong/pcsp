#include "BTTask_MoveToAffordance.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPInteractionPoint.h"
#include "PCSPAgentCharacter.h"

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
	return TryBeginMove(OwnerComp, NodeMemory);
}

// ---------------------------------------------------------------------------
// TryBeginMove  — also called on retry from TickTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_MoveToAffordance::TryBeginMove(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	AAIController* AI = OwnerComp.GetAIOwner();
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!AI || !BB) { return EBTNodeResult::Failed; }

	APCSPAgentCharacter* Agent = Cast<APCSPAgentCharacter>(AI->GetPawn());
	if (!Agent) { return EBTNodeResult::Failed; }

	UPCSPAffordanceSubsystem* Sub = AI->GetWorld()->GetSubsystem<UPCSPAffordanceSubsystem>();
	if (!Sub) { return EBTNodeResult::Failed; }

	const EPCSPActionType Action = static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType));
	const EPCSPAffordanceCategory Category = ActionToCategory(Action);

	FPCSPAffordanceQuery Query;
	Query.Category       = Category;
	Query.FromLocation   = Agent->GetActorLocation();
	Query.bRequireCapacity = true;

	APCSPAffordanceZone* Zone = Sub->FindBestZone(Query);
	if (!Zone) { return EBTNodeResult::Failed; }

	APCSPInteractionPoint* Point = Zone->FindFreeInteractionPoint();
	if (!Point || !Point->TryReserve(Agent)) { return EBTNodeResult::Failed; }

	Zone->RegisterOccupant(Agent);

	auto* Memory        = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);
	Memory->Zone        = Zone;
	Memory->Point       = Point;
	Memory->bMoveStarted = false;

	// Write Blackboard keys so Phase 2 tasks and decorators can read them
	BB->SetValueAsObject(PCSPBlackboard::TargetActor,    Point);
	BB->SetValueAsVector(PCSPBlackboard::TargetLocation, Point->GetActorLocation());
	BB->SetValueAsName  (PCSPBlackboard::CurrentZoneTag, Zone->ZoneTag.GetTagName());
	BB->SetValueAsBool  (PCSPBlackboard::AffordanceReserved, true);

	FAIMoveRequest MoveReq(Point);
	MoveReq.SetAcceptanceRadius(AcceptanceRadius);
	MoveReq.SetUsePathfinding(true);
	AI->MoveTo(MoveReq);

	return EBTNodeResult::InProgress;
}

// ---------------------------------------------------------------------------
// TickTask
// ---------------------------------------------------------------------------

void UBTTask_MoveToAffordance::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	auto* Memory = reinterpret_cast<FBTMoveToAffordanceMemory*>(NodeMemory);

	// Give the move request one tick to register before we start polling status
	if (!Memory->bMoveStarted)
	{
		Memory->bMoveStarted = true;
		return;
	}

	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI || !Memory->Point.IsValid())
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}

	APawn* Pawn = AI->GetPawn();
	// 2D distance only: Pawn location is at capsule center (z ~88cm) while
	// InteractionPoint sits on the ground, so a 3D check never satisfies an
	// 80cm acceptance radius even when the agent has clearly arrived.
	const float DistSq = FVector::DistSquaredXY(Pawn->GetActorLocation(), Memory->Point->GetActorLocation());

	if (DistSq <= FMath::Square(AcceptanceRadius))
	{
		// Arrived — clear failure counter on success
		UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
		if (BB) { BB->SetValueAsInt(PCSPBlackboard::RecentFailureCount, 0); }
		FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
		return;
	}

	if (AI->GetMoveStatus() == EPathFollowingStatus::Idle)
	{
		// Movement stopped without reaching the target
		AActor* Agent = AI->GetPawn();
		ReleaseReservation(NodeMemory, Agent);
		Memory->Zone.Reset();
		Memory->Point.Reset();
		Memory->RetryCount++;

		if (Memory->RetryCount <= MaxRetries)
		{
			Memory->bMoveStarted = false;
			EBTNodeResult::Type RetryResult = TryBeginMove(OwnerComp, NodeMemory);
			if (RetryResult == EBTNodeResult::Failed)
			{
				// No alternative zone available
				UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
				if (BB)
				{
					int32 Failures = BB->GetValueAsInt(PCSPBlackboard::RecentFailureCount);
					BB->SetValueAsInt(PCSPBlackboard::RecentFailureCount, Failures + 1);
					BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false);
				}
				FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
			}
			// else: TryBeginMove returned InProgress — keep ticking
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
	if (Memory->Point.IsValid()) { Memory->Point->Release(Agent); }
	if (Memory->Zone.IsValid())  { Memory->Zone->UnregisterOccupant(Agent); }
}

EPCSPAffordanceCategory UBTTask_MoveToAffordance::ActionToCategory(EPCSPActionType Action)
{
	switch (Action)
	{
	case EPCSPActionType::EatQuick:
	case EPCSPActionType::EatSlow:             return EPCSPAffordanceCategory::Eat;

	case EPCSPActionType::RestAlone:
	case EPCSPActionType::RestWithOthers:      return EPCSPAffordanceCategory::Rest;

	case EPCSPActionType::FocusedWork:
	case EPCSPActionType::PlanningWork:        return EPCSPAffordanceCategory::Work;

	case EPCSPActionType::DeepStudy:
	case EPCSPActionType::CasualLearning:      return EPCSPAffordanceCategory::Study;

	case EPCSPActionType::ExerciseSolo:
	case EPCSPActionType::ExerciseSocial:      return EPCSPAffordanceCategory::Exercise;

	case EPCSPActionType::HygieneQuick:
	case EPCSPActionType::HygieneCareful:      return EPCSPAffordanceCategory::Hygiene;

	case EPCSPActionType::SocializeInitiate:
	case EPCSPActionType::SocializeRespond:    return EPCSPAffordanceCategory::Social;

	case EPCSPActionType::LeisureIndoor:       return EPCSPAffordanceCategory::Leisure;
	case EPCSPActionType::LeisureOutdoor:      return EPCSPAffordanceCategory::Observe;

	case EPCSPActionType::ShopEssentials:
	case EPCSPActionType::BrowseArea:          return EPCSPAffordanceCategory::Shop;

	case EPCSPActionType::ObserveCrowd:        return EPCSPAffordanceCategory::Observe;

	default:                                   return EPCSPAffordanceCategory::Idle;
	}
}
