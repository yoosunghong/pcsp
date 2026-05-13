#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_PCSPDecision.generated.h"

/**
 * Phase 1 stub: writes a baseline DesiredActionType / DesiredAffordanceTag
 * based on the most urgent need. Phase 2/3 will replace the body with the
 * PCSP shared policy inference call.
 */
UCLASS()
class CNZOI_API UBTTask_PCSPDecision : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_PCSPDecision();

	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
};
