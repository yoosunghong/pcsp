#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "PCSPTypes.h"
#include "Components/PCSPTrajectoryLogComponent.h"
#include "PCSPAgentDebugViewModel.generated.h"

class APCSPAgentCharacter;
class APCSPAffordanceZone;

/**
 * Read-only adapter between an observed `APCSPAgentCharacter` and UMG widgets.
 *
 * Owned by `APCSPDemoPlayerController`; rebound whenever the observed agent
 * changes. All getters are pure functions over component/Blackboard state —
 * the view model never mutates agent state, so binding it to a HUD that ticks
 * every frame is safe.
 */
USTRUCT(BlueprintType)
struct FPCSPHudAgentSnapshot
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) int32 PersonaId = 0;
	UPROPERTY(BlueprintReadOnly) FString PersonaText;
	UPROPERTY(BlueprintReadOnly) bool bEmbeddingActive = false;
	UPROPERTY(BlueprintReadOnly) EPCSPPolicyMode PolicyMode = EPCSPPolicyMode::HybridPCSP;
	UPROPERTY(BlueprintReadOnly) FString ActiveAblation;

	// Decision stack
	UPROPERTY(BlueprintReadOnly) EPCSPActionType DesiredAction = EPCSPActionType::IdleReflect;
	UPROPERTY(BlueprintReadOnly) EPCSPAffordanceCategory DesiredCategory = EPCSPAffordanceCategory::None;
	UPROPERTY(BlueprintReadOnly) FGameplayTag DesiredAffordance;
	UPROPERTY(BlueprintReadOnly) AActor* TargetActor = nullptr;
	UPROPERTY(BlueprintReadOnly) FVector TargetLocation = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly) float UrgencyScore = 0.f;
	UPROPERTY(BlueprintReadOnly) int32 RecentFailureCount = 0;
	UPROPERTY(BlueprintReadOnly) bool bAffordanceReserved = false;

	// Needs (8 floats, EPCSPNeed order)
	UPROPERTY(BlueprintReadOnly) TArray<float> Needs;

	// Social context
	UPROPERTY(BlueprintReadOnly) int32 NearbyCount = 0;
	UPROPERTY(BlueprintReadOnly) float MeanAffinity = 0.f;
	UPROPERTY(BlueprintReadOnly) AActor* SocialTarget = nullptr;

	// Zone occupancy panel (computed from the resolved target zone, if any)
	UPROPERTY(BlueprintReadOnly) FGameplayTag CurrentZoneTag;
	UPROPERTY(BlueprintReadOnly) EPCSPAffordanceCategory ZoneCategory = EPCSPAffordanceCategory::None;
	UPROPERTY(BlueprintReadOnly) int32 ZoneOccupancy = 0;
	UPROPERTY(BlueprintReadOnly) int32 ZoneCapacity = 0;
	UPROPERTY(BlueprintReadOnly) float DistanceToTarget = -1.f;

	// Trajectory strip (last N events from the in-memory ring buffer)
	UPROPERTY(BlueprintReadOnly) TArray<FPCSPTrajectoryEntry> RecentEvents;
};

UCLASS(BlueprintType)
class CNZOI_API UPCSPAgentDebugViewModel : public UObject
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void SetAgent(APCSPAgentCharacter* InAgent);

	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	APCSPAgentCharacter* GetAgent() const { return Agent.Get(); }

	/** Build a fresh snapshot — call from HUD Tick or a low-frequency timer. */
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	FPCSPHudAgentSnapshot BuildSnapshot(int32 RecentEventsToShow = 5) const;

	/** Stable display string for an action enum (UEnum DisplayName fallback). */
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	static FString ActionDisplayName(EPCSPActionType Action);

	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	static FString CategoryDisplayName(EPCSPAffordanceCategory Category);

	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	static FString EventDisplayName(EPCSPTrajectoryEvent Event);

protected:
	APCSPAffordanceZone* ResolveZoneByTag(FGameplayTag Tag) const;

	UPROPERTY()
	TWeakObjectPtr<APCSPAgentCharacter> Agent;
};
