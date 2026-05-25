#include "PCSPDemoPlayerController.h"

#include "EngineUtils.h"
#include "Components/InputComponent.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAgentDebugViewModel.h"
#include "PCSPPersonaComponent.h"
#include "InputCoreTypes.h"
#include "GameFramework/SpectatorPawn.h"

APCSPDemoPlayerController::APCSPDemoPlayerController()
{
	bShowMouseCursor = false;
	bAutoManageActiveCameraTarget = false;
}

void APCSPDemoPlayerController::BeginPlay()
{
	Super::BeginPlay();
	ViewModel = NewObject<UPCSPAgentDebugViewModel>(this, TEXT("PCSPDebugViewModel"));
}

void APCSPDemoPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();
	if (!InputComponent) { return; }

	// Legacy key bindings — no Enhanced Input asset authoring required for the demo.
	// Shift detection on Tab is done inside HandleCycleNext via IsInputKeyDown.
	InputComponent->BindKey(EKeys::F,   IE_Pressed, this, &APCSPDemoPlayerController::HandleFocusKey);
	InputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &APCSPDemoPlayerController::HandleCycleNext);
	InputComponent->BindKey(EKeys::H,   IE_Pressed, this, &APCSPDemoPlayerController::HandleToggleHud);
	InputComponent->BindKey(EKeys::Z,   IE_Pressed, this, &APCSPDemoPlayerController::HandleToggleZoneOverlay);
}

void APCSPDemoPlayerController::HandleFocusKey()
{
	if (ObservedAgent.IsValid()) { ClearFocus(); }
	else                          { FocusNearestAgent(); }
}

void APCSPDemoPlayerController::HandleCycleNext()
{
	const bool bShift = IsInputKeyDown(EKeys::LeftShift) || IsInputKeyDown(EKeys::RightShift);
	CycleAgent(bShift ? -1 : +1);
}
void APCSPDemoPlayerController::HandleCyclePrev() { CycleAgent(-1); }
void APCSPDemoPlayerController::HandleToggleHud()          { OnHudToggle.Broadcast(); }
void APCSPDemoPlayerController::HandleToggleZoneOverlay()  { OnZoneOverlayToggle.Broadcast(); }

void APCSPDemoPlayerController::GatherAgentsSortedByPersona(TArray<APCSPAgentCharacter*>& Out) const
{
	UWorld* World = GetWorld();
	if (!World) { return; }
	for (TActorIterator<APCSPAgentCharacter> It(World); It; ++It)
	{
		APCSPAgentCharacter* A = *It;
		if (!IsValid(A)) { continue; }
		if (!A->FindComponentByClass<UPCSPPersonaComponent>()) { continue; }
		Out.Add(A);
	}
	Out.Sort([](const APCSPAgentCharacter& Lhs, const APCSPAgentCharacter& Rhs)
	{
		const UPCSPPersonaComponent* L = Lhs.FindComponentByClass<UPCSPPersonaComponent>();
		const UPCSPPersonaComponent* R = Rhs.FindComponentByClass<UPCSPPersonaComponent>();
		const int32 Li = L ? L->GetPersonaId() : 0;
		const int32 Ri = R ? R->GetPersonaId() : 0;
		return Li < Ri;
	});
}

void APCSPDemoPlayerController::FocusNearestAgent()
{
	UWorld* World = GetWorld();
	if (!World) { return; }

	FVector Origin = FVector::ZeroVector;
	FRotator UnusedRot;
	GetPlayerViewPoint(Origin, UnusedRot);

	APCSPAgentCharacter* Best = nullptr;
	float BestDistSq = FLT_MAX;
	int32 BestId = TNumericLimits<int32>::Max();

	for (TActorIterator<APCSPAgentCharacter> It(World); It; ++It)
	{
		APCSPAgentCharacter* A = *It;
		if (!IsValid(A)) { continue; }
		const UPCSPPersonaComponent* P = A->FindComponentByClass<UPCSPPersonaComponent>();
		if (!P) { continue; }

		const float DistSq = FVector::DistSquared(Origin, A->GetActorLocation());
		const int32 Id = P->GetPersonaId();
		if (DistSq < BestDistSq || (FMath::IsNearlyEqual(DistSq, BestDistSq) && Id < BestId))
		{
			BestDistSq = DistSq;
			Best       = A;
			BestId     = Id;
		}
	}

	if (Best) { SetObservedAgent(Best); }
}

void APCSPDemoPlayerController::CycleAgent(int32 Delta)
{
	TArray<APCSPAgentCharacter*> Sorted;
	GatherAgentsSortedByPersona(Sorted);
	if (Sorted.Num() == 0) { return; }

	int32 Idx = Sorted.IndexOfByKey(ObservedAgent.Get());
	if (Idx == INDEX_NONE) { Idx = 0; }
	else
	{
		Idx = (Idx + Delta + Sorted.Num()) % Sorted.Num();
	}
	SetObservedAgent(Sorted[Idx]);
}

void APCSPDemoPlayerController::ClearFocus()
{
	APawn* P = GetPawn();
	if (!P) { P = GetSpectatorPawn(); }
	if (P)
	{
		SetViewTargetWithBlend(P, ViewBlendTime);
	}
	SetObservedAgent(nullptr);
}

void APCSPDemoPlayerController::SetObservedAgent(APCSPAgentCharacter* NewAgent)
{
	if (ObservedAgent.Get() == NewAgent) { return; }
	ObservedAgent = NewAgent;
	if (ViewModel) { ViewModel->SetAgent(NewAgent); }
	if (NewAgent)
	{
		SetViewTargetWithBlend(NewAgent, ViewBlendTime);
	}
	OnObservedAgentChanged.Broadcast(NewAgent);
}
