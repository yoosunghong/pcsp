#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "PCSPAIController.generated.h"

class UBehaviorTree;

UCLASS()
class CNZOI_API APCSPAIController : public AAIController
{
	GENERATED_BODY()

public:
	APCSPAIController();

	virtual void OnPossess(APawn* InPawn) override;

	// Assign in Blueprint subclass or via spawner.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UBehaviorTree> BehaviorTreeAsset;
};
