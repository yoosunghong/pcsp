#include "BTTask_PCSPDecision.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "Engine/World.h"
#include "PCSPTypes.h"
#include "PCSPNeedsComponent.h"
#include "PCSPAgentCharacter.h"
#include "PCSPPersonaComponent.h"
#include "PCSPObservationComponent.h"
#include "PCSPPolicySubsystem.h"
#include "PCSPTrajectoryLogComponent.h"
#include "BehaviorTree/BlackboardData.h"

UBTTask_PCSPDecision::UBTTask_PCSPDecision()
{
	NodeName = TEXT("PCSP Decision");
}

uint16 UBTTask_PCSPDecision::GetInstanceMemorySize() const
{
	return sizeof(FBTPCSPDecisionMemory);
}

void UBTTask_PCSPDecision::InitializeMemory(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory,
	EBTMemoryInit::Type InitType) const
{
	new (NodeMemory) FBTPCSPDecisionMemory();
}

void UBTTask_PCSPDecision::CleanupMemory(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory,
	EBTMemoryClear::Type CleanupType) const
{
	reinterpret_cast<FBTPCSPDecisionMemory*>(NodeMemory)->~FBTPCSPDecisionMemory();
}

EBTNodeResult::Type UBTTask_PCSPDecision::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	FBTPCSPDecisionMemory* Mem = reinterpret_cast<FBTPCSPDecisionMemory*>(NodeMemory);

	AAIController* AI = OwnerComp.GetAIOwner();
	if (!AI) { return EBTNodeResult::Failed; }

	APCSPAgentCharacter* Agent = Cast<APCSPAgentCharacter>(AI->GetPawn());
	UBlackboardComponent* BB   = OwnerComp.GetBlackboardComponent();
	if (!Agent || !BB || !Agent->Needs) { return EBTNodeResult::Failed; }

	const UWorld* World = AI->GetWorld();
	const float Now = World ? World->GetTimeSeconds() : 0.f;

	// Compute urgency once — cheap, and we need it for the emergency bypass.
	const EPCSPNeed Urgent = Agent->Needs->GetMostUrgentNeed();
	const float UrgencyScore = 1.f - Agent->Needs->GetNeed(Urgent);

	// Failure backoff: extend the throttle interval when the move branch has been
	// failing — the policy is deterministic for a given (obs, persona), so retrying
	// immediately just hot-loops. Waiting lets needs decay enough to shift argmax.
	const int32 FailureCount = BB->GetValueAsInt(PCSPBlackboard::RecentFailureCount);
	const float EffectiveInterval = MinDecisionInterval * (1.f + FMath::Min(FailureCount, 8));

	const bool bEmergency  = UrgencyScore >= EmergencyUrgencyThreshold;
	const bool bThrottled  = (Now - Mem->LastDecisionTime) < EffectiveInterval;

	// Throttle: reuse the last action so the BT can keep running the move/interaction
	// branch without thrashing the ONNX model. Skipped when an emergency hits.
	if (bThrottled && !bEmergency && Mem->LastAction != EPCSPActionType::None)
	{
		BB->SetValueAsEnum (PCSPBlackboard::DesiredActionType, static_cast<uint8>(Mem->LastAction));
		if (BB->GetKeyID(PCSPBlackboard::DesiredCategory) != FBlackboard::InvalidKey)
		{
			BB->SetValueAsEnum(PCSPBlackboard::DesiredCategory,
				static_cast<uint8>(UPCSPPolicySubsystem::ActionToCategory(Mem->LastAction)));
		}
		BB->SetValueAsFloat(PCSPBlackboard::UrgencyScore,      UrgencyScore);
		return EBTNodeResult::Succeeded;
	}

	UPCSPPolicySubsystem* Policy = World ? World->GetSubsystem<UPCSPPolicySubsystem>() : nullptr;
	if (!Policy)
	{
		UE_LOG(LogTemp, Error, TEXT("BTTask_PCSPDecision: PCSPPolicySubsystem is missing"));
		return EBTNodeResult::Failed;
	}
	if (!Policy->IsReady() && UPCSPPolicySubsystem::GetPolicyMode() != EPCSPPolicyMode::BTOnly)
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
	TArray<float> Logits;
	double InferenceMicros = -1.0;
	const EPCSPActionType Action = Policy->RunInferenceWithLogits(Obs, PersonaId, Logits, InferenceMicros);
	if (Action == EPCSPActionType::None)
	{
		UE_LOG(LogTemp, Error, TEXT("BTTask_PCSPDecision: ONNX inference failed"));
		return EBTNodeResult::Failed;
	}

	BB->SetValueAsEnum (PCSPBlackboard::DesiredActionType, static_cast<uint8>(Action));
	if (BB->GetKeyID(PCSPBlackboard::DesiredCategory) != FBlackboard::InvalidKey)
	{
		BB->SetValueAsEnum(PCSPBlackboard::DesiredCategory,
			static_cast<uint8>(UPCSPPolicySubsystem::ActionToCategory(Action)));
	}
	BB->SetValueAsFloat(PCSPBlackboard::UrgencyScore,      UrgencyScore);

	Mem->LastDecisionTime = Now;
	Mem->LastAction       = Action;
	Mem->LastUrgency      = UrgencyScore;

	if (Agent->TrajectoryLog)
	{
		Agent->TrajectoryLog->RecordDecisionWithLogits(Action, UrgencyScore, Logits, InferenceMicros);
	}
	return EBTNodeResult::Succeeded;
}
