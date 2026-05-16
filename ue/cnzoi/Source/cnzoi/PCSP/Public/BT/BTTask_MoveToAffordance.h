#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "PCSPTypes.h"
#include "BTTask_MoveToAffordance.generated.h"

class APCSPAffordanceZone;
class APCSPInteractionPoint;

struct FBTMoveToAffordanceMemory
{
	TWeakObjectPtr<APCSPAffordanceZone>    Zone;
	TWeakObjectPtr<APCSPInteractionPoint>  Point;
	int32  RetryCount    = 0;
	bool   bMoveStarted  = false;
};

/**
 * Queries the AffordanceSubsystem for the best zone matching the current
 * DesiredActionType, reserves an InteractionPoint, and moves the agent there.
 * On arrival writes TargetActor / TargetLocation / bAffordanceReserved to BB.
 * Retries up to MaxRetries times before failing to the Idle branch.
 */
UCLASS()
class CNZOI_API UBTTask_MoveToAffordance : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_MoveToAffordance();

	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask (UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void                TickTask  (UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FBTMoveToAffordanceMemory); }

	UPROPERTY(EditAnywhere, Category="PCSP", meta=(ClampMin="10"))
	float AcceptanceRadius = 80.f;

	UPROPERTY(EditAnywhere, Category="PCSP", meta=(ClampMin="0"))
	int32 MaxRetries = 2;

private:
	EBTNodeResult::Type TryBeginMove(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory);
	void                ReleaseReservation(uint8* NodeMemory, AActor* Agent) const;

	static EPCSPAffordanceCategory ActionToCategory(EPCSPActionType Action);
};
