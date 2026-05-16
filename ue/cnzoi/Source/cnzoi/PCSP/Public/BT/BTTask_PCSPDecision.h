#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_PCSPDecision.generated.h"

/**
 * Writes DesiredActionType + UrgencyScore to the Blackboard each BT tick.
 * Decisions are driven entirely by PCSPPolicySubsystem's ONNX inference.
 * If the model is not ready, this task returns Failed — agents will not act
 * until pcsp_actor.onnx and persona_embeddings.json are present.
 *
 * The Emergency Branch decorator still fires on UrgencyScore > 0.85 but runs
 * the same ONNX inference; there is no heuristic surrogate path.
 */
UCLASS()
class CNZOI_API UBTTask_PCSPDecision : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_PCSPDecision();

	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;

	// Deprecated: retained for Blueprint/Asset compatibility, ignored at runtime.
	// All decisions now route through ONNX inference.
	UPROPERTY()
	bool bForceHeuristic = false;
};
