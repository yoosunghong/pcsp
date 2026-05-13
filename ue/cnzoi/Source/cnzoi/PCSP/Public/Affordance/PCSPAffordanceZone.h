#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceZone.generated.h"

class APCSPInteractionPoint;
class UBoxComponent;

UCLASS()
class CNZOI_API APCSPAffordanceZone : public AActor
{
	GENERATED_BODY()

public:
	APCSPAffordanceZone();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	FGameplayTag ZoneTag;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	int32 Capacity = 4;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	TObjectPtr<UBoxComponent> Bounds;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	TArray<TObjectPtr<APCSPInteractionPoint>> InteractionPoints;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	int32 GetCurrentOccupancy() const { return CurrentOccupants.Num(); }

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool HasCapacity() const { return CurrentOccupants.Num() < Capacity; }

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void RegisterOccupant(AActor* Actor);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void UnregisterOccupant(AActor* Actor);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	APCSPInteractionPoint* FindFreeInteractionPoint() const;

protected:
	UPROPERTY()
	TSet<TWeakObjectPtr<AActor>> CurrentOccupants;
};
