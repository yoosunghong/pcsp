#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceSubsystem.generated.h"

class APCSPAffordanceZone;

USTRUCT(BlueprintType)
struct FPCSPAffordanceQuery
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite) EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;
	UPROPERTY(BlueprintReadWrite) FGameplayTag PreferredTag;
	UPROPERTY(BlueprintReadWrite) FVector FromLocation = FVector::ZeroVector;
	UPROPERTY(BlueprintReadWrite) float MaxDistance = 50000.f;
	UPROPERTY(BlueprintReadWrite) bool bRequireCapacity = true;
};

UCLASS()
class CNZOI_API UPCSPAffordanceSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	void RegisterZone(APCSPAffordanceZone* Zone);
	void UnregisterZone(APCSPAffordanceZone* Zone);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	APCSPAffordanceZone* FindBestZone(const FPCSPAffordanceQuery& Query) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	TArray<APCSPAffordanceZone*> GetZonesByCategory(EPCSPAffordanceCategory Category) const;


	const TArray<TWeakObjectPtr<APCSPAffordanceZone>>& GetAllZones() const { return Zones; }

protected:
	UPROPERTY()
	TArray<TWeakObjectPtr<APCSPAffordanceZone>> Zones;
};
