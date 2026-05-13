#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPTypes.h"
#include "PCSPNeedsComponent.generated.h"

USTRUCT(BlueprintType)
struct FPCSPNeedConfig
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	float DecayPerSecond = 0.01f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	float CriticalThreshold = 0.15f;
};

UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPNeedsComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPNeedsComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category="PCSP|Needs")
	float GetNeed(EPCSPNeed Need) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Needs")
	void SetNeed(EPCSPNeed Need, float Value);

	UFUNCTION(BlueprintCallable, Category="PCSP|Needs")
	void AdjustNeed(EPCSPNeed Need, float Delta);

	UFUNCTION(BlueprintCallable, Category="PCSP|Needs")
	bool IsCritical(EPCSPNeed Need) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Needs")
	EPCSPNeed GetMostUrgentNeed() const;

	// Index by EPCSPNeed.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Needs")
	TArray<float> Values;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Needs")
	TArray<FPCSPNeedConfig> Configs;
};
