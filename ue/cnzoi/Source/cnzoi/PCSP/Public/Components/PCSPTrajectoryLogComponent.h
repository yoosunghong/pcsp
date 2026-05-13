#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPTypes.h"
#include "PCSPTrajectoryLogComponent.generated.h"

USTRUCT(BlueprintType)
struct FPCSPTrajectoryEntry
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) float TimeSeconds = 0.f;
	UPROPERTY(BlueprintReadOnly) FVector Location = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly) EPCSPActionType Action = EPCSPActionType::IdleReflect;
	UPROPERTY(BlueprintReadOnly) FGameplayTag Affordance;
	UPROPERTY(BlueprintReadOnly) float Reward = 0.f;
};

UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPTrajectoryLogComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPTrajectoryLogComponent();

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void RecordEntry(EPCSPActionType Action, FGameplayTag Affordance, float Reward);

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	const TArray<FPCSPTrajectoryEntry>& GetEntries() const { return Entries; }

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void ClearLog() { Entries.Reset(); }

protected:
	UPROPERTY() TArray<FPCSPTrajectoryEntry> Entries;
};
