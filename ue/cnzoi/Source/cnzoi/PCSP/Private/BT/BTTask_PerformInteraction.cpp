#include "BTTask_PerformInteraction.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPAgentCharacter.h"
#include "PCSPNeedsComponent.h"
#include "PCSPTrajectoryLogComponent.h"

UBTTask_PerformInteraction::UBTTask_PerformInteraction()
{
	NodeName    = TEXT("Perform Interaction");
	bNotifyTick = true;
}

// ---------------------------------------------------------------------------
// ExecuteTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_PerformInteraction::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	new(NodeMemory) FBTPerformInteractionMemory();

	AAIController* AI = OwnerComp.GetAIOwner();
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!AI || !BB) { return EBTNodeResult::Failed; }

	APCSPAffordanceZone* Zone = Cast<APCSPAffordanceZone>(
		BB->GetValueAsObject(PCSPBlackboard::TargetActor));
	const int32 SlotIndex = Zone ? Zone->FindReservedInteractionSlot(AI->GetPawn()) : INDEX_NONE;
	if (!Zone || SlotIndex == INDEX_NONE
		|| !Zone->IsInteractionSlotReservedBy(SlotIndex, AI->GetPawn()))
	{
		// Reservation was lost or never set (e.g., BT was interrupted and restarted)
		if (APCSPAgentCharacter* Character = Cast<APCSPAgentCharacter>(AI->GetPawn()))
		{
			if (Character->TrajectoryLog)
			{
				const EPCSPActionType Action =
					static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType));
				Character->TrajectoryLog->RecordInteractionFailed(Action, FGameplayTag(),
					TEXT("reservation_lost_on_entry"));
			}
		}
		return EBTNodeResult::Failed;
	}

	auto* Memory       = reinterpret_cast<FBTPerformInteractionMemory*>(NodeMemory);
	Memory->Zone       = Zone;
	Memory->SlotIndex  = SlotIndex;
	Memory->TimeRemaining = Zone->GetInteractionSlotDuration(SlotIndex);

	return EBTNodeResult::InProgress;
}

// ---------------------------------------------------------------------------
// TickTask
// ---------------------------------------------------------------------------

void UBTTask_PerformInteraction::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	auto* Memory = reinterpret_cast<FBTPerformInteractionMemory*>(NodeMemory);

	if (!Memory->Zone.IsValid() || Memory->SlotIndex == INDEX_NONE)
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}

	AAIController* AI = OwnerComp.GetAIOwner();
	AActor* Agent = AI ? AI->GetPawn() : nullptr;

	// Abort early if someone else stole our reservation (edge case: actor destroyed)
	if (!Memory->Zone->IsInteractionSlotReservedBy(Memory->SlotIndex, Agent))
	{
		if (Memory->Zone.IsValid() && Agent) { Memory->Zone->UnregisterOccupant(Agent); }
		UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
		if (BB) { BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false); }
		if (APCSPAgentCharacter* Character = Cast<APCSPAgentCharacter>(Agent))
		{
			if (Character->TrajectoryLog)
			{
				const EPCSPActionType Action = BB
					? static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType))
					: EPCSPActionType::IdleReflect;
				const FGameplayTag ZoneTag = Memory->Zone.IsValid() ? Memory->Zone->ZoneTag : FGameplayTag();
				Character->TrajectoryLog->RecordInteractionFailed(Action, ZoneTag,
					TEXT("reservation_stolen_mid_interaction"));
			}
		}
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}

	Memory->TimeRemaining -= DeltaSeconds;
	if (Memory->TimeRemaining > 0.f) { return; }

	// Interaction complete
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (Agent)
	{
		EPCSPAffordanceCategory Category = Memory->Zone.IsValid()
			? Memory->Zone->Category
			: EPCSPAffordanceCategory::None;
		const float Reward = ApplyNeedsSatisfaction(Agent, Category);

		if (APCSPAgentCharacter* Character = Cast<APCSPAgentCharacter>(Agent))
		{
			if (Character->TrajectoryLog)
			{
				const EPCSPActionType Action = BB
					? static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType))
					: EPCSPActionType::IdleReflect;
				const FGameplayTag ZoneTag = Memory->Zone.IsValid() ? Memory->Zone->ZoneTag : FGameplayTag();
				Character->TrajectoryLog->RecordInteractionComplete(Action, ZoneTag, Category, Reward);
			}
		}
	}

	CleanupReservation(NodeMemory, Agent, BB);
	FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
}

// ---------------------------------------------------------------------------
// AbortTask
// ---------------------------------------------------------------------------

EBTNodeResult::Type UBTTask_PerformInteraction::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	AAIController* AI = OwnerComp.GetAIOwner();
	AActor* Agent = AI ? AI->GetPawn() : nullptr;
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	CleanupReservation(NodeMemory, Agent, BB);
	return EBTNodeResult::Aborted;
}

// ---------------------------------------------------------------------------
// Static helpers
// ---------------------------------------------------------------------------

float UBTTask_PerformInteraction::ApplyNeedsSatisfaction(AActor* Agent, EPCSPAffordanceCategory Category)
{
	APCSPAgentCharacter* Character = Cast<APCSPAgentCharacter>(Agent);
	if (!Character || !Character->Needs) { return 0.f; }

	// (Need, RestoreDelta) pairs per affordance category
	EPCSPNeed Need  = EPCSPNeed::Leisure;
	float     Delta = 0.f;

	switch (Category)
	{
	case EPCSPAffordanceCategory::Eat:      Need = EPCSPNeed::Hunger;  Delta = 0.35f; break;
	case EPCSPAffordanceCategory::Rest:     Need = EPCSPNeed::Sleep;   Delta = 0.40f; break;
	case EPCSPAffordanceCategory::Work:     Need = EPCSPNeed::Work;    Delta = 0.30f; break;
	case EPCSPAffordanceCategory::Study:    Need = EPCSPNeed::Learning;Delta = 0.30f; break;
	case EPCSPAffordanceCategory::Exercise: Need = EPCSPNeed::Fitness; Delta = 0.35f; break;
	case EPCSPAffordanceCategory::Hygiene:  Need = EPCSPNeed::Hygiene; Delta = 0.50f; break;
	case EPCSPAffordanceCategory::Social:   Need = EPCSPNeed::Social;  Delta = 0.30f; break;
	case EPCSPAffordanceCategory::Leisure:  Need = EPCSPNeed::Leisure; Delta = 0.25f; break;
	case EPCSPAffordanceCategory::Shop:     Need = EPCSPNeed::Leisure; Delta = 0.10f; break;
	case EPCSPAffordanceCategory::Observe:  Need = EPCSPNeed::Leisure; Delta = 0.15f; break;
	default:                                                            Delta = 0.f;   break;
	}

	if (Delta > 0.f) { Character->Needs->AdjustNeed(Need, Delta); }
	return Delta;
}

void UBTTask_PerformInteraction::CleanupReservation(uint8* NodeMemory, AActor* Agent, UBlackboardComponent* BB)
{
	auto* Memory = reinterpret_cast<FBTPerformInteractionMemory*>(NodeMemory);
	if (Memory->Zone.IsValid() && Agent)
	{
		Memory->Zone->ReleaseInteractionSlot(Memory->SlotIndex, Agent);
	}
	if (BB) { BB->SetValueAsBool(PCSPBlackboard::AffordanceReserved, false); }
}
