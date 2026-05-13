#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.h"
#include "PCSPInteractionPoint.generated.h"

UCLASS()
class CNZOI_API APCSPInteractionPoint : public AActor
{
	GENERATED_BODY()

public:
	APCSPInteractionPoint();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	FGameplayTag AffordanceTag;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	float InteractionDuration = 3.f;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool TryReserve(AActor* Requester);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void Release(AActor* Requester);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool IsReserved() const { return Reserver.IsValid(); }

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	AActor* GetReserver() const { return Reserver.Get(); }

protected:
	UPROPERTY()
	TWeakObjectPtr<AActor> Reserver;
};
