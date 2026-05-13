#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPObservationComponent.generated.h"

class UPCSPNeedsComponent;
class UPCSPSocialContextComponent;

UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPObservationComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPObservationComponent();

	virtual void BeginPlay() override;

	// Assemble a fixed-length, normalized observation vector.
	UFUNCTION(BlueprintCallable, Category="PCSP|Observation")
	const TArray<float>& BuildObservation();

	UFUNCTION(BlueprintCallable, Category="PCSP|Observation")
	const TArray<float>& GetLastObservation() const { return LastObservation; }

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Observation")
	int32 ObservationDim = 40;

protected:
	UPROPERTY() TObjectPtr<UPCSPNeedsComponent> Needs;
	UPROPERTY() TObjectPtr<UPCSPSocialContextComponent> Social;

	TArray<float> LastObservation;
};
