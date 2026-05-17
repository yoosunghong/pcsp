#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "PCSPTypes.h"
#include "BTTask_PerformInteraction.generated.h"

class APCSPAffordanceZone;
class APCSPInteractionPoint;

struct FBTPerformInteractionMemory
{
	TWeakObjectPtr<APCSPInteractionPoint> Point;
	TWeakObjectPtr<APCSPAffordanceZone>   Zone;
	float TimeRemaining = 0.f;
};

/**
 * Waits at the reserved InteractionPoint for its InteractionDuration, applies
 * a needs satisfaction delta, then releases the reservation and zone occupancy.
 * If the reservation is lost before completion, the task fails immediately.
 */
UCLASS()
class CNZOI_API UBTTask_PerformInteraction : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_PerformInteraction();

	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask (UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void                TickTask  (UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FBTPerformInteractionMemory); }

private:
	static APCSPAffordanceZone* FindZoneForPoint(UWorld* World, APCSPInteractionPoint* Point);
	// Returns the actual needs-satisfaction delta applied (0 if category had no mapping).
	static float ApplyNeedsSatisfaction(AActor* Agent, EPCSPAffordanceCategory Category);
	static void CleanupReservation(uint8* NodeMemory, AActor* Agent, UBlackboardComponent* BB);
};
