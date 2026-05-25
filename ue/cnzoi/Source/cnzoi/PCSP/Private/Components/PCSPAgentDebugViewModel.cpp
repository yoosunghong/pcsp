#include "PCSPAgentDebugViewModel.h"

#include "EngineUtils.h"
#include "PCSPAgentCharacter.h"
#include "PCSPNeedsComponent.h"
#include "PCSPPersonaComponent.h"
#include "PCSPSocialContextComponent.h"
#include "PCSPTrajectoryLogComponent.h"
#include "PCSPAffordanceZone.h"
#include "PCSPInteractionPoint.h"
#include "PCSPPolicySubsystem.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BlackboardData.h"
#include "Engine/World.h"
#include "UObject/UnrealType.h"

void UPCSPAgentDebugViewModel::SetAgent(APCSPAgentCharacter* InAgent)
{
	Agent = InAgent;
}

namespace
{
	UBlackboardComponent* GetBlackboard(APCSPAgentCharacter* C)
	{
		if (!C) { return nullptr; }
		AAIController* AI = Cast<AAIController>(C->GetController());
		return AI ? AI->GetBlackboardComponent() : nullptr;
	}

	float SafeFloat(const UBlackboardComponent* BB, FName Key)
	{
		if (!BB || BB->GetKeyID(Key) == FBlackboard::InvalidKey) { return 0.f; }
		return BB->GetValueAsFloat(Key);
	}

	int32 SafeInt(const UBlackboardComponent* BB, FName Key)
	{
		if (!BB || BB->GetKeyID(Key) == FBlackboard::InvalidKey) { return 0; }
		return BB->GetValueAsInt(Key);
	}

	bool SafeBool(const UBlackboardComponent* BB, FName Key)
	{
		if (!BB || BB->GetKeyID(Key) == FBlackboard::InvalidKey) { return false; }
		return BB->GetValueAsBool(Key);
	}

	uint8 SafeEnum(const UBlackboardComponent* BB, FName Key)
	{
		if (!BB || BB->GetKeyID(Key) == FBlackboard::InvalidKey) { return 0; }
		return BB->GetValueAsEnum(Key);
	}
}

APCSPAffordanceZone* UPCSPAgentDebugViewModel::ResolveZoneByTag(FGameplayTag Tag) const
{
	APCSPAgentCharacter* A = Agent.Get();
	if (!A || !Tag.IsValid()) { return nullptr; }
	UWorld* World = A->GetWorld();
	if (!World) { return nullptr; }
	for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
	{
		if (It->ZoneTag == Tag) { return *It; }
	}
	return nullptr;
}

FPCSPHudAgentSnapshot UPCSPAgentDebugViewModel::BuildSnapshot(int32 RecentEventsToShow) const
{
	FPCSPHudAgentSnapshot S;
	APCSPAgentCharacter* A = Agent.Get();
	if (!A) { return S; }

	S.PolicyMode     = UPCSPPolicySubsystem::GetPolicyMode();
	S.ActiveAblation = UPCSPPolicySubsystem::GetActiveAblationTag();

	if (const UPCSPPersonaComponent* P = A->FindComponentByClass<UPCSPPersonaComponent>())
	{
		S.PersonaId        = P->GetPersonaId();
		S.PersonaText      = P->PersonaText;
		S.bEmbeddingActive = P->HasEmbedding();
	}

	if (const UPCSPNeedsComponent* N = A->FindComponentByClass<UPCSPNeedsComponent>())
	{
		S.Needs = N->Values;
	}

	if (const UPCSPSocialContextComponent* SC = A->FindComponentByClass<UPCSPSocialContextComponent>())
	{
		const FPCSPSocialSummary& Sum = SC->GetSummary();
		S.NearbyCount  = Sum.NearbyCount;
		S.MeanAffinity = Sum.MeanAffinity;
	}

	const UBlackboardComponent* BB = GetBlackboard(A);
	if (BB)
	{
		S.DesiredAction        = static_cast<EPCSPActionType>(SafeEnum(BB, PCSPBlackboard::DesiredActionType));
		S.DesiredCategory      = static_cast<EPCSPAffordanceCategory>(SafeEnum(BB, PCSPBlackboard::DesiredCategory));
		if (S.DesiredCategory == EPCSPAffordanceCategory::None)
		{
			S.DesiredCategory = UPCSPPolicySubsystem::ActionToCategory(S.DesiredAction);
		}
		S.UrgencyScore         = SafeFloat(BB, PCSPBlackboard::UrgencyScore);
		S.RecentFailureCount   = SafeInt  (BB, PCSPBlackboard::RecentFailureCount);
		S.bAffordanceReserved  = SafeBool (BB, PCSPBlackboard::AffordanceReserved);

		if (BB->GetKeyID(PCSPBlackboard::DesiredAffordance) != FBlackboard::InvalidKey)
		{
			// Blackboard key type FBlackboardKeyType_GameplayTag — fall back via name
			S.DesiredAffordance = FGameplayTag::EmptyTag;
		}
		if (BB->GetKeyID(PCSPBlackboard::CurrentZoneTag) != FBlackboard::InvalidKey)
		{
			S.CurrentZoneTag = FGameplayTag::EmptyTag;
		}
		if (BB->GetKeyID(PCSPBlackboard::TargetActor) != FBlackboard::InvalidKey)
		{
			S.TargetActor = Cast<AActor>(BB->GetValueAsObject(PCSPBlackboard::TargetActor));
		}
		if (BB->GetKeyID(PCSPBlackboard::TargetLocation) != FBlackboard::InvalidKey)
		{
			S.TargetLocation = BB->GetValueAsVector(PCSPBlackboard::TargetLocation);
		}
		if (BB->GetKeyID(PCSPBlackboard::SocialTargetActor) != FBlackboard::InvalidKey)
		{
			S.SocialTarget = Cast<AActor>(BB->GetValueAsObject(PCSPBlackboard::SocialTargetActor));
		}
	}

	// Resolve target zone occupancy via the target actor. InteractionPoints are
	// independent actors in the level (not outered to the zone), so we do a
	// short linear scan over zones to find the parent.
	if (S.TargetActor)
	{
		S.DistanceToTarget = FVector::Dist2D(A->GetActorLocation(), S.TargetActor->GetActorLocation());
		if (UWorld* World = A->GetWorld())
		{
			for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
			{
				APCSPAffordanceZone* Z = *It;
				if (!Z) { continue; }
				bool bFound = false;
				for (const TObjectPtr<APCSPInteractionPoint>& IP : Z->InteractionPoints)
				{
					if (IP.Get() == S.TargetActor) { bFound = true; break; }
				}
				if (bFound)
				{
					S.CurrentZoneTag = Z->ZoneTag;
					S.ZoneCategory   = Z->Category;
					S.ZoneOccupancy  = Z->GetCurrentOccupancy();
					S.ZoneCapacity   = Z->Capacity;
					break;
				}
			}
		}
	}

	if (const UPCSPTrajectoryLogComponent* TL = A->FindComponentByClass<UPCSPTrajectoryLogComponent>())
	{
		S.RecentEvents = TL->GetRecentEvents(RecentEventsToShow);
	}

	return S;
}

FString UPCSPAgentDebugViewModel::ActionDisplayName(EPCSPActionType Action)
{
	const UEnum* E = StaticEnum<EPCSPActionType>();
	return E ? E->GetNameStringByValue(static_cast<int64>(Action)) : FString::FromInt((int32)Action);
}

FString UPCSPAgentDebugViewModel::CategoryDisplayName(EPCSPAffordanceCategory Category)
{
	const UEnum* E = StaticEnum<EPCSPAffordanceCategory>();
	return E ? E->GetNameStringByValue(static_cast<int64>(Category)) : FString::FromInt((int32)Category);
}

FString UPCSPAgentDebugViewModel::EventDisplayName(EPCSPTrajectoryEvent Event)
{
	switch (Event)
	{
	case EPCSPTrajectoryEvent::Decision:            return TEXT("decision");
	case EPCSPTrajectoryEvent::InteractionComplete: return TEXT("interaction_complete");
	case EPCSPTrajectoryEvent::InteractionFailed:   return TEXT("interaction_failed");
	case EPCSPTrajectoryEvent::MoveFailed:          return TEXT("move_failed");
	}
	return TEXT("unknown");
}
