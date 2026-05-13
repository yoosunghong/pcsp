#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPSocialContextComponent.generated.h"

USTRUCT(BlueprintType)
struct FPCSPSocialSummary
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) int32 NearbyCount = 0;
	UPROPERTY(BlueprintReadOnly) float MeanAffinity = 0.f;
	UPROPERTY(BlueprintReadOnly) float MaxCompatibility = 0.f;
	UPROPERTY(BlueprintReadOnly) float MinCompatibility = 0.f;
	UPROPERTY(BlueprintReadOnly) float RecentInteractionRecency = 0.f;
};

UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPSocialContextComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPSocialContextComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category="PCSP|Social")
	const FPCSPSocialSummary& GetSummary() const { return Summary; }

	UFUNCTION(BlueprintCallable, Category="PCSP|Social")
	void RegisterInteraction(AActor* Other);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Social")
	float PerceptionRadius = 800.f;

protected:
	void RefreshSummary();

	UPROPERTY()
	TMap<TWeakObjectPtr<AActor>, float> Affinity;

	FPCSPSocialSummary Summary;
	float TimeSinceLastInteraction = TNumericLimits<float>::Max();
};
