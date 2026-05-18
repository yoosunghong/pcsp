#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "PCSPTypes.h"
#include "BTTask_PCSPDecision.generated.h"

/**
 * Writes DesiredActionType + UrgencyScore to the Blackboard.
 * Decisions are driven entirely by PCSPPolicySubsystem's ONNX inference.
 *
 * To avoid hot-looping on failed move/interaction branches, this task throttles
 * itself: it only runs new inference every MinDecisionInterval seconds; between
 * intervals it returns Succeeded with the previously chosen action so the BT
 * branch can proceed without re-inferring. UrgencyScore > 0.85 bypasses the
 * throttle so emergency-need spikes are handled immediately.
 *
 * If the model is not ready, this task returns Failed — agents will not act
 * until pcsp_actor.onnx and persona_embeddings.json are present.
 */
UCLASS()
class CNZOI_API UBTTask_PCSPDecision : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_PCSPDecision();

	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual uint16 GetInstanceMemorySize() const override;
	virtual void InitializeMemory(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, EBTMemoryInit::Type InitType) const override;
	virtual void CleanupMemory   (UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, EBTMemoryClear::Type CleanupType) const override;

	/** Minimum seconds between full ONNX inferences for a given agent. */
	UPROPERTY(EditAnywhere, Category="PCSP", meta=(ClampMin="0.0"))
	float MinDecisionInterval = 0.5f;

	/** UrgencyScore at or above this value bypasses the throttle. */
	UPROPERTY(EditAnywhere, Category="PCSP", meta=(ClampMin="0.0", ClampMax="1.0"))
	float EmergencyUrgencyThreshold = 0.85f;

	// Deprecated: retained for Blueprint/Asset compatibility, ignored at runtime.
	UPROPERTY()
	bool bForceHeuristic = false;
};

/** Per-instance scratch state for decision throttling. */
struct FBTPCSPDecisionMemory
{
	float LastDecisionTime = -1000.f;
	EPCSPActionType LastAction = EPCSPActionType::IdleReflect;
	float LastUrgency = 0.f;
};
