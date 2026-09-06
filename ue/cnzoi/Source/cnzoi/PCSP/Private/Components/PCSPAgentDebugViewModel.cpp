#include "PCSPAgentDebugViewModel.h"

#include "EngineUtils.h"
#include "PCSPAgentCharacter.h"
#include "PCSPNeedsComponent.h"
#include "PCSPPersonaCache.h"
#include "PCSPPersonaComponent.h"
#include "PCSPSocialContextComponent.h"
#include "PCSPTrajectoryLogComponent.h"
#include "PCSPAffordanceZone.h"
#include "PCSPPolicySubsystem.h"
#include "PCSPMassSpawner.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BlackboardData.h"
#include "Engine/World.h"
#include "UObject/UnrealType.h"

void UPCSPAgentDebugViewModel::SetAgent(APCSPAgentCharacter* InAgent)
{
	Agent = InAgent;
	MassSpawner.Reset();
	MassStableIndex = INDEX_NONE;
}

void UPCSPAgentDebugViewModel::SetMassAgent(APCSPMassSpawner* InSpawner, const int32 InStableIndex)
{
	Agent.Reset();
	MassSpawner = InSpawner;
	MassStableIndex = InSpawner ? InStableIndex : INDEX_NONE;
}

namespace
{
	/**
	 * Neighbourhood radius reported for Mass agents. Matched to the Actor agents'
	 * default social perception radius so the panel means the same thing in both
	 * populations.
	 */
	constexpr float MassNeighborhoodRadius = 800.f;

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
	S.PolicyMode     = UPCSPPolicySubsystem::GetPolicyMode();
	S.ActiveAblation = UPCSPPolicySubsystem::GetActiveAblationTag();
	if (APCSPMassSpawner* Spawner = MassSpawner.Get())
	{
		FPCSPMassAgentSnapshot Mass;
		if (!Spawner->GetAgentSnapshot(MassStableIndex, Mass)) { return S; }
		S.bMassEntity = true;
		S.StableIndex = Mass.StableIndex;
		S.PersonaId = Mass.PersonaId;
		S.bMoving = Mass.bMoving;
		S.bInteracting = Mass.bInteracting;
		S.DesiredAction = Mass.Action;
		S.DesiredCategory = Mass.Category;
		S.TargetLocation = Mass.Target;
		S.AgentLocation = Mass.Location;
		S.bAffordanceReserved = Mass.ReservedSlotIndex != INDEX_NONE;
		S.bWanderingTarget = Mass.bWandering;
		// Distance is meaningful for any agent in transit, not only one holding a
		// reservation; gating it on the reservation left the panel showing "-" for
		// every agent that was still walking towards a zone.
		S.DistanceToTarget = Mass.bMoving || S.bAffordanceReserved
			? FVector::Dist2D(Mass.Location, Mass.Target) : -1.f;
		S.Needs.Append(Mass.Needs, UE_ARRAY_COUNT(Mass.Needs));
		float MinimumNeed = 1.f;
		for (const float Need : Mass.Needs) { MinimumNeed = FMath::Min(MinimumNeed, Need); }
		S.UrgencyScore = 1.f - MinimumNeed;
		UWorld* World = Spawner->GetWorld();
		const UPCSPPolicySubsystem* Policy = World ? World->GetSubsystem<UPCSPPolicySubsystem>() : nullptr;
		S.bEmbeddingActive = Policy && Policy->IsReady() && S.PolicyMode == EPCSPPolicyMode::HybridPCSP;
		// Mass entities carry only a persona ID, so resolve the authored description
		// through the same cache the policy conditions on. Lead with the current
		// action so the card answers "who is this and what are they doing".
		const UPCSPPersonaCache* Cache = Policy ? Policy->GetPersonaCache() : nullptr;
		const FString PersonaBody = Cache ? Cache->GetPersonaText(Mass.PersonaId) : FString();
		const FString Subtitle = Cache ? Cache->GetPersonaSubtitle(Mass.PersonaId) : FString();
		S.PersonaText = PersonaBody.IsEmpty()
			? FString::Printf(TEXT("%s  |  persona #%d (no text loaded)"),
				*ActionDisplayName(Mass.Action), Mass.PersonaId)
			: Subtitle.IsEmpty()
				? FString::Printf(TEXT("%s  |  %s"), *ActionDisplayName(Mass.Action), *PersonaBody)
				: FString::Printf(TEXT("%s  |  %s\n%s"),
					*ActionDisplayName(Mass.Action), *Subtitle, *PersonaBody);
		// Resolve the goal zone whether or not a slot is reserved yet. The zone is
		// chosen when the decision is made, so waiting for the reservation is what
		// kept the affordance panel empty for most of each agent's cycle.
		if (World && Mass.ZoneVisualizationIndex != INDEX_NONE)
		{
			for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
			{
				if (It->VisualizationIndex != Mass.ZoneVisualizationIndex) { continue; }
				S.TargetActor = *It;
				S.CurrentZoneTag = It->ZoneTag;
				S.ZoneCategory = It->Category;
				S.ZoneOccupancy = It->GetCurrentOccupancy();
				S.ZoneCapacity = It->Capacity;
				break;
			}
		}
		// Mass keeps no per-pair affinity ledger, so report the neighbourhood that is
		// actually simulated: how many agents are within earshot and how many of them
		// chose the same affordance category.
		S.NearbyRadius = MassNeighborhoodRadius;
		Spawner->GetNeighborhoodSummary(Mass.StableIndex, MassNeighborhoodRadius,
			S.NearbyCount, S.NearbySameActivityCount);

		const int32 FirstEvent = FMath::Max(0, Mass.RecentActions.Num() - FMath::Max(0, RecentEventsToShow));
		for (int32 Index = FirstEvent; Index < Mass.RecentActions.Num(); ++Index)
		{
			FPCSPTrajectoryEntry& Entry = S.RecentEvents.AddDefaulted_GetRef();
			Entry.TimeSeconds = Mass.RecentActionTimes[Index];
			Entry.EventType = EPCSPTrajectoryEvent::Decision;
			Entry.Action = Mass.RecentActions[Index];
			Entry.Category = UPCSPPolicySubsystem::ActionToCategory(Entry.Action);
		}
		return S;
	}

	APCSPAgentCharacter* A = Agent.Get();
	if (!A) { return S; }
	S.AgentLocation = A->GetActorLocation();

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
		S.NearbyRadius = SC->PerceptionRadius;
		S.bNearbyAffinityTracked = true;
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

	// The target actor is now the Zone itself; the exact integrated slot is in
	// TargetLocation, so no world scan or independent point actor is required.
	if (S.TargetActor)
	{
		S.DistanceToTarget = FVector::Dist2D(A->GetActorLocation(), S.TargetLocation);
		if (APCSPAffordanceZone* Z = Cast<APCSPAffordanceZone>(S.TargetActor))
		{
			S.CurrentZoneTag = Z->ZoneTag;
			S.ZoneCategory   = Z->Category;
			S.ZoneOccupancy  = Z->GetCurrentOccupancy();
			S.ZoneCapacity   = Z->Capacity;
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
