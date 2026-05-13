#include "BTTask_PCSPDecision.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "PCSPTypes.h"
#include "PCSPNeedsComponent.h"
#include "PCSPAgentCharacter.h"

UBTTask_PCSPDecision::UBTTask_PCSPDecision()
{
	NodeName = TEXT("PCSP Decision");
}

EBTNodeResult::Type UBTTask_PCSPDecision::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI) { return EBTNodeResult::Failed; }

	APCSPAgentCharacter* Agent = Cast<APCSPAgentCharacter>(AI->GetPawn());
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!Agent || !BB || !Agent->Needs) { return EBTNodeResult::Failed; }

	const EPCSPNeed Urgent = Agent->Needs->GetMostUrgentNeed();
	EPCSPActionType Action = EPCSPActionType::IdleReflect;
	switch (Urgent)
	{
	case EPCSPNeed::Hunger:   Action = EPCSPActionType::EatQuick; break;
	case EPCSPNeed::Sleep:    Action = EPCSPActionType::RestAlone; break;
	case EPCSPNeed::Social:   Action = EPCSPActionType::SocializeInitiate; break;
	case EPCSPNeed::Leisure:  Action = EPCSPActionType::LeisureIndoor; break;
	case EPCSPNeed::Hygiene:  Action = EPCSPActionType::HygieneQuick; break;
	case EPCSPNeed::Fitness:  Action = EPCSPActionType::ExerciseSolo; break;
	case EPCSPNeed::Work:     Action = EPCSPActionType::FocusedWork; break;
	case EPCSPNeed::Learning: Action = EPCSPActionType::CasualLearning; break;
	default: break;
	}

	BB->SetValueAsEnum(PCSPBlackboard::DesiredActionType, static_cast<uint8>(Action));
	BB->SetValueAsFloat(PCSPBlackboard::UrgencyScore, 1.f - Agent->Needs->GetNeed(Urgent));
	return EBTNodeResult::Succeeded;
}
