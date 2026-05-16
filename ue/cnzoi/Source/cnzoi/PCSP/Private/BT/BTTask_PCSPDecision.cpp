#include "BTTask_PCSPDecision.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "PCSPTypes.h"
#include "PCSPNeedsComponent.h"
#include "PCSPAgentCharacter.h"
#include "PCSPPersonaComponent.h"
#include "PCSPObservationComponent.h"
#include "PCSPPolicySubsystem.h"

UBTTask_PCSPDecision::UBTTask_PCSPDecision()
{
	NodeName = TEXT("PCSP Decision");
}

EBTNodeResult::Type UBTTask_PCSPDecision::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI) { return EBTNodeResult::Failed; }

	APCSPAgentCharacter* Agent = Cast<APCSPAgentCharacter>(AI->GetPawn());
	UBlackboardComponent* BB   = OwnerComp.GetBlackboardComponent();
	if (!Agent || !BB || !Agent->Needs) { return EBTNodeResult::Failed; }

	// ONNX-only: this task drives decisions entirely from the PCSP policy.
	// If the model is not loaded, fail the task so the agent does not move
	// rather than fall back to a heuristic surrogate.
	UPCSPPolicySubsystem* Policy = AI->GetWorld()->GetSubsystem<UPCSPPolicySubsystem>();
	if (!Policy || !Policy->IsReady())
	{
		UE_LOG(LogTemp, Error,
			TEXT("BTTask_PCSPDecision: PCSPPolicySubsystem is not ready (ONNX model missing or load failed). "
			     "Agent will not act until pcsp_actor.onnx + persona_embeddings.json are available."));
		return EBTNodeResult::Failed;
	}
	if (!Agent->Observation)
	{
		UE_LOG(LogTemp, Error, TEXT("BTTask_PCSPDecision: agent has no ObservationComponent"));
		return EBTNodeResult::Failed;
	}

	const TArray<float>& Obs = Agent->Observation->BuildObservation();
	const int32 PersonaId = Agent->Persona ? Agent->Persona->GetPersonaId() : 1;
	const EPCSPActionType Action = Policy->RunInference(Obs, PersonaId);
	if (Action == EPCSPActionType::None)
	{
		UE_LOG(LogTemp, Error, TEXT("BTTask_PCSPDecision: ONNX inference failed"));
		return EBTNodeResult::Failed;
	}

	// UrgencyScore: how depleted is the most-urgent need (drives emergency branch)
	const EPCSPNeed Urgent = Agent->Needs->GetMostUrgentNeed();
	const float UrgencyScore = 1.f - Agent->Needs->GetNeed(Urgent);

	BB->SetValueAsEnum(PCSPBlackboard::DesiredActionType, static_cast<uint8>(Action));
	BB->SetValueAsFloat(PCSPBlackboard::UrgencyScore, UrgencyScore);
	return EBTNodeResult::Succeeded;
}
