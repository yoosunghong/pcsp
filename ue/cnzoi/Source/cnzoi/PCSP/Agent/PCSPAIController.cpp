#include "PCSPAIController.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BlackboardComponent.h"

APCSPAIController::APCSPAIController()
{
	bWantsPlayerState = false;
}

void APCSPAIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	if (BehaviorTreeAsset)
	{
		if (UBlackboardData* BBAsset = BehaviorTreeAsset->BlackboardAsset)
		{
			UBlackboardComponent* BB = nullptr;
			UseBlackboard(BBAsset, BB);
		}
		RunBehaviorTree(BehaviorTreeAsset);
	}
}
