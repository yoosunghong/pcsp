#include "PCSPDemoPlayerController.h"

#include "EngineUtils.h"
#include "Components/InputComponent.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAgentDebugViewModel.h"
#include "PCSPPersonaComponent.h"
#include "UI/PCSPDemoHUDWidgetBase.h"
#include "Inference/PCSPPolicySubsystem.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "GameFramework/SpectatorPawn.h"
#include "GameFramework/FloatingPawnMovement.h"
#include "Blueprint/UserWidget.h"
#include "PCSPMassSpawner.h"
#include "Camera/CameraActor.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "Sim/PCSPPerfSamplerSubsystem.h"

APCSPDemoPlayerController::APCSPDemoPlayerController()
{
	bShowMouseCursor = true;
	bEnableClickEvents = true;
	bEnableMouseOverEvents = true;
	bAutoManageActiveCameraTarget = false;
}

void APCSPDemoPlayerController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	ConfigureFreeCameraPawn(InPawn);
}

void APCSPDemoPlayerController::ConfigureFreeCameraPawn(APawn* InPawn) const
{
	constexpr float PortfolioFreeCameraMaxSpeed = 8000.f;
	constexpr float PortfolioFreeCameraAcceleration = 24000.f;
	constexpr float PortfolioFreeCameraDeceleration = 32000.f;
	if (!InPawn || Cast<APCSPAgentCharacter>(InPawn)) { return; }
	if (UFloatingPawnMovement* Movement = InPawn->FindComponentByClass<UFloatingPawnMovement>())
	{
		Movement->MaxSpeed = PortfolioFreeCameraMaxSpeed;
		Movement->Acceleration = PortfolioFreeCameraAcceleration;
		Movement->Deceleration = PortfolioFreeCameraDeceleration;
	}
}

void APCSPDemoPlayerController::BeginPlay()
{
	// Super invokes the Blueprint BeginPlay graph, which may create the legacy
	// HUD immediately. The read-only adapter must already exist at that point.
	GetViewModel();
	Super::BeginPlay();
	ConfigureFreeCameraPawn(GetPawn() ? GetPawn() : GetSpectatorPawn());

	FInputModeGameAndUI InputMode;
	InputMode.SetHideCursorDuringCapture(false);
	InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	SetInputMode(InputMode);

	if (DemoHudClass && !DemoHud)
	{
		DemoHud = CreateWidget<UPCSPDemoHUDWidgetBase>(this, DemoHudClass);
		if (DemoHud)
		{
			DemoHud->AddToPlayerScreen(10);
		}
	}
	if (FParse::Param(FCommandLine::Get(), TEXT("PCSP_DemoSmoke")))
	{
		GetWorld()->GetTimerManager().SetTimer(DemoSmokeTimer, this,
			&APCSPDemoPlayerController::RunMassDemoSmokeCheck, 6.f, false);
	}
	if (FParse::Param(FCommandLine::Get(), TEXT("PCSP_PerformanceSmoke")))
	{
		GetWorld()->GetTimerManager().SetTimer(DemoSmokeTimer, this,
			&APCSPDemoPlayerController::RunPerformanceSmokeStep, 6.f, false);
	}
}

void APCSPDemoPlayerController::RunPerformanceSmokeStep()
{
	if (!DemoHud) { UE_LOG(LogTemp, Error, TEXT("PCSPPerformanceSmoke: missing HUD")); return; }
	if (PerformanceSmokeStep == 0) { FocusNearestAgent(); DemoHud->RecordBTOnly(); }
	else if (PerformanceSmokeStep == 1) { DemoHud->RecordPCSP(); }
	else if (PerformanceSmokeStep == 2) { DemoHud->RecordNoPersona(); }
	else if (PerformanceSmokeStep == 3)
	{
		const auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>();
		bool bPassed = Perf != nullptr && !Perf->HasWriteError();
		for (const EPCSPPolicyMode Mode : {EPCSPPolicyMode::HybridPCSP, EPCSPPolicyMode::BTOnly, EPCSPPolicyMode::HybridNoPersona})
		{
			const FPCSPPerfRun* Run = Perf ? Perf->LatestRun(Mode) : nullptr;
			bPassed &= Run && Run->Points.Num() >= 2 && Run->MeanFPS() > 0.f && Run->MeanCPU() >= 0.f && Run->MeanCPU() <= 100.f;
			if (Run) { UE_LOG(LogTemp, Display, TEXT("PCSPPerformanceSmoke: mode=%s points=%d seconds=%.2f cpu=%.2f fps=%.2f"),
				*UPCSPPolicySubsystem::PolicyModeName(Mode), Run->Points.Num(), Run->RecordedSeconds, Run->MeanCPU(), Run->MeanFPS()); }
		}
		UE_LOG(LogTemp, Display, TEXT("PCSPPerformanceSmoke: result=%s"), bPassed ? TEXT("PASS") : TEXT("FAIL"));
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / TEXT("PCSP/Validation/performance_comparison.png"), true, false);
	}
	else
	{
		DemoHud->TogglePerformance();
		FScreenshotRequest::RequestScreenshot(FPaths::ProjectSavedDir() / TEXT("PCSP/Validation/distribution_widget.png"), true, false);
		return;
	}
	++PerformanceSmokeStep;
	GetWorld()->GetTimerManager().SetTimer(DemoSmokeTimer, this,
		&APCSPDemoPlayerController::RunPerformanceSmokeStep, PerformanceSmokeStep == 4 ? 2.f : 12.f, false);
}

UPCSPAgentDebugViewModel* APCSPDemoPlayerController::GetViewModel() const
{
	// HUD creation can precede native BeginPlay (e.g. level/Blueprint startup).
	// This is a lazy cache, not a mutation of observed simulation state.
	if (!ViewModel)
	{
		APCSPDemoPlayerController* MutableThis = const_cast<APCSPDemoPlayerController*>(this);
		MutableThis->ViewModel = NewObject<UPCSPAgentDebugViewModel>(MutableThis, TEXT("PCSPDebugViewModel"));
	}
	return ViewModel;
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
	InputComponent->BindKey(EKeys::P,   IE_Pressed, this, &APCSPDemoPlayerController::HandleCyclePolicyMode);
	InputComponent->BindKey(EKeys::LeftMouseButton, IE_Pressed, this,
		&APCSPDemoPlayerController::SelectAgentUnderCursor);
}

/**
 * Cycles `pcsp.PolicyMode` 0 -> 1 -> 2 -> 0 live.
 *
 * The CVar is read per decision, so the crowd changes over within one decision
 * interval and no restart is needed. This is the demo's sharpest moment: the
 * same model driving the same crowd collapses to a single behaviour once the
 * persona vector is zeroed, so the switch has to be reachable while watching.
 */
void APCSPDemoPlayerController::HandleCyclePolicyMode()
{
	static IConsoleVariable* PolicyModeVar =
		IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.PolicyMode"));
	if (!PolicyModeVar) { return; }

	const int32 Next = (PolicyModeVar->GetInt() + 1) % 3;
	PolicyModeVar->Set(Next, ECVF_SetByConsole);
	UE_LOG(LogTemp, Log, TEXT("PCSPDemo: policy mode -> %s"),
		*UPCSPPolicySubsystem::PolicyModeName(static_cast<EPCSPPolicyMode>(Next)));
	// Repaint now rather than waiting up to 100 ms for the HUD's own timer, so the
	// badge changes on the same frame as the keypress.
	if (DemoHud) { DemoHud->RefreshHud(); }
}

void APCSPDemoPlayerController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (GetWorld()) { GetWorld()->GetTimerManager().ClearTimer(DemoSmokeTimer); }
	if (DemoHud) { DemoHud->RemoveFromParent(); }
	Super::EndPlay(EndPlayReason);
}

void APCSPDemoPlayerController::RunMassDemoSmokeCheck()
{
	FocusNearestAgent();
	for (TActorIterator<APCSPMassSpawner> It(GetWorld()); It; ++It)
	{
		TArray<FPCSPMassAgentSnapshot> Snapshots;
		It->GetAllAgentSnapshots(Snapshots);
		for (const FPCSPMassAgentSnapshot& Snapshot : Snapshots)
		{
			if (Snapshot.bMoving)
			{
				ObserveMassAgent(*It, Snapshot.StableIndex, true);
				break;
			}
		}
		break;
	}
	if (DemoHud) { DemoHud->RefreshHud(); }
	const FPCSPHudAgentSnapshot Snapshot = GetViewModel()->BuildSnapshot(8);
	const int32 HudAgentCount = DemoHud ? DemoHud->GetRunSnapshot().AgentCount : 0;
	const float VisualScale = GetObservedAgentVisualScale();
	const float MarkerHeight = DemoHud ? DemoHud->SelectionMarkerHeight * VisualScale : 0.f;
	// The policy badge is built natively rather than authored, so nothing in the
	// WBP asset would catch it regressing. Assert it exists and is visible here.
	const bool bBadgeVisible = DemoHud && DemoHud->IsPolicyBadgeVisible();
	if (DemoHud)
	{
		DemoHud->PinComparison();
		const bool bPinned = DemoHud->HasPinnedComparison();
		CycleAgent(1);
		DemoHud->RefreshHud();
		const bool bSurvivedSelection = DemoHud->HasPinnedComparison();
		DemoHud->ToggleDetails();
		DemoHud->ToggleDetails();
		DemoHud->ClearComparison();
		const bool bCleared = !DemoHud->HasPinnedComparison();
		DemoHud->PinComparison();
		CycleAgent(1);
		DemoHud->RefreshHud();
		UE_LOG(LogTemp, Display, TEXT("PCSPPortfolioSmoke: pin=%s selection=%s clear=%s"),
			bPinned ? TEXT("PASS") : TEXT("FAIL"), bSurvivedSelection ? TEXT("PASS") : TEXT("FAIL"),
			bCleared ? TEXT("PASS") : TEXT("FAIL"));
	}
	const bool bPassed = Snapshot.bMassEntity && Snapshot.Needs.Num() == 8
		&& HudAgentCount > 0 && IsThirdPersonCameraActive() && bBadgeVisible;
	UE_LOG(LogTemp, Display,
		TEXT("PCSPMassDemoSmoke: result=%s selected_mass=%s stable_index=%d needs=%d history=%d hud_agents=%d follow_camera=%s policy_badge=%s policy_mode=%s visual_scale=%.2f marker_height=%.1f camera_distance=%.1f camera_height=%.1f look_at_height=%.1f"),
		bPassed ? TEXT("PASS") : TEXT("FAIL"), Snapshot.bMassEntity ? TEXT("true") : TEXT("false"),
		Snapshot.StableIndex, Snapshot.Needs.Num(), Snapshot.RecentEvents.Num(), HudAgentCount,
		IsThirdPersonCameraActive() ? TEXT("true") : TEXT("false"),
		bBadgeVisible ? TEXT("visible") : TEXT("MISSING"),
		*UPCSPPolicySubsystem::PolicyModeName(UPCSPPolicySubsystem::GetPolicyMode()), VisualScale,
		MarkerHeight, MassFollowDistance * VisualScale, MassFollowHeight * VisualScale,
		MassLookAtHeight * VisualScale);
	GetWorld()->GetTimerManager().SetTimer(DemoSmokeTimer, this,
		&APCSPDemoPlayerController::CaptureMassDemoSmokeFrame, 0.6f, false);
}

void APCSPDemoPlayerController::CaptureMassDemoSmokeFrame()
{
	if (DemoSmokeFrame == 2 && DemoHud) { DemoHud->ToggleDetails(); }
	++DemoSmokeFrame;
	const FString Path = FPaths::ProjectSavedDir() / TEXT("PCSP/Validation")
		/ FString::Printf(TEXT("mass_demo_frame_%02d.png"), DemoSmokeFrame);
	FScreenshotRequest::RequestScreenshot(Path, true, false);
	if (DemoSmokeFrame < 3)
	{
		GetWorld()->GetTimerManager().SetTimer(DemoSmokeTimer, this,
			&APCSPDemoPlayerController::CaptureMassDemoSmokeFrame, 0.4f, false);
	}
}

void APCSPDemoPlayerController::PlayerTick(const float DeltaSeconds)
{
	Super::PlayerTick(DeltaSeconds);
	if (bThirdPersonCameraActive && ObservedMassSpawner.IsValid()
		&& !(DemoHud && DemoHud->IsPerformanceOpen()))
	{
		UpdateMassFollowCamera();
	}
}

void APCSPDemoPlayerController::UpdateMassFollowCamera()
{
	APCSPMassSpawner* Spawner = ObservedMassSpawner.Get();
	FPCSPMassAgentSnapshot Snapshot;
	if (!Spawner || !MassFollowCamera
		|| !Spawner->GetAgentSnapshot(ObservedMassStableIndex, Snapshot)) { return; }
	const float VisualScale = Spawner->GetRepresentationScale();
	const FVector LookAt = Snapshot.Location
		+ FVector(0.f, 0.f, MassLookAtHeight * VisualScale);
	const FVector CameraLocation = Snapshot.Location
		- Snapshot.Rotation.Vector() * (MassFollowDistance * VisualScale)
		+ FVector(0.f, 0.f, MassFollowHeight * VisualScale);
	MassFollowCamera->SetActorLocationAndRotation(CameraLocation, (LookAt - CameraLocation).Rotation());
}

float APCSPDemoPlayerController::GetObservedAgentVisualScale() const
{
	if (const APCSPMassSpawner* Spawner = ObservedMassSpawner.Get())
	{
		return Spawner->GetRepresentationScale();
	}
	if (const APCSPAgentCharacter* Agent = ObservedAgent.Get())
	{
		return FMath::Max(0.1f, Agent->GetActorScale3D().GetAbsMax());
	}
	return 1.f;
}

void APCSPDemoPlayerController::SelectAgentUnderCursor()
{
	FHitResult Hit;
	if (GetHitResultUnderCursor(ECC_Visibility, false, Hit))
	{
		if (APCSPMassSpawner* Spawner = Cast<APCSPMassSpawner>(Hit.GetActor()))
		{
			int32 StableIndex = INDEX_NONE;
			if (Spawner->GetStableIndexFromHit(Hit.GetComponent(), Hit.Item, StableIndex))
			{
				ObserveMassAgent(Spawner, StableIndex, bThirdPersonCameraActive);
				return;
			}
		}
	}

	// Static crowd bakes may intentionally omit physics collision. Pick against
	// the Mass body centers as a fallback, without creating per-entity actors.
	FVector RayOrigin;
	FVector RayDirection;
	if (!DeprojectMousePositionToWorld(RayOrigin, RayDirection)) { return; }
	APCSPMassSpawner* BestSpawner = nullptr;
	int32 BestStableIndex = INDEX_NONE;
	float BestDepth = TNumericLimits<float>::Max();
	for (TActorIterator<APCSPMassSpawner> It(GetWorld()); It; ++It)
	{
		const float VisualScale = It->GetRepresentationScale();
		TArray<FPCSPMassAgentSnapshot> Snapshots;
		It->GetAllAgentSnapshots(Snapshots);
		for (const FPCSPMassAgentSnapshot& Snapshot : Snapshots)
		{
			const FVector Center = Snapshot.Location + FVector(0.f, 0.f, 95.f * VisualScale);
			const float Depth = FVector::DotProduct(Center - RayOrigin, RayDirection);
			if (Depth <= 0.f || Depth >= BestDepth) { continue; }
			const float DistanceSq = FVector::DistSquared(Center, RayOrigin + RayDirection * Depth);
			if (DistanceSq > FMath::Square(85.f * VisualScale)) { continue; }
			BestDepth = Depth;
			BestSpawner = *It;
			BestStableIndex = Snapshot.StableIndex;
		}
	}
	if (BestSpawner) { ObserveMassAgent(BestSpawner, BestStableIndex, bThirdPersonCameraActive); }
}

void APCSPDemoPlayerController::HandleFocusKey()
{
	if (bThirdPersonCameraActive) { ClearFocus(); }
	else if (ObservedAgent.IsValid() || ObservedMassSpawner.IsValid()) { SetThirdPersonCameraActive(true); }
	else { FocusNearestAgent(); }
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

	// Mass is the primary population. Prefer it whenever a live Mass spawner exists.
	APCSPMassSpawner* BestMassSpawner = nullptr;
	int32 BestMassIndex = INDEX_NONE;
	float BestMassDistance = TNumericLimits<float>::Max();
	for (TActorIterator<APCSPMassSpawner> It(World); It; ++It)
	{
		int32 StableIndex;
		float DistanceSq;
		if (It->FindNearestAgent(Origin, StableIndex, DistanceSq) && DistanceSq < BestMassDistance)
		{
			BestMassDistance = DistanceSq;
			BestMassSpawner = *It;
			BestMassIndex = StableIndex;
		}
	}
	if (BestMassSpawner)
	{
		ObserveMassAgent(BestMassSpawner, BestMassIndex, true);
		return;
	}

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

	if (Best) { SetObservedAgent(Best, true); }
}

void APCSPDemoPlayerController::ObserveAgent(APCSPAgentCharacter* NewAgent, bool bActivateCamera)
{
	SetObservedAgent(NewAgent, bActivateCamera);
}

void APCSPDemoPlayerController::ObserveMassAgent(APCSPMassSpawner* Spawner,
	const int32 StableIndex, const bool bActivateCamera)
{
	FPCSPMassAgentSnapshot Snapshot;
	if (!Spawner || !Spawner->GetAgentSnapshot(StableIndex, Snapshot)) { return; }
	ObservedAgent.Reset();
	if (APCSPMassSpawner* Previous = ObservedMassSpawner.Get(); Previous && Previous != Spawner)
	{
		Previous->SetHighlightedAgent(INDEX_NONE);
	}
	ObservedMassSpawner = Spawner;
	ObservedMassStableIndex = StableIndex;
	Spawner->SetHighlightedAgent(StableIndex);
	if (ViewModel) { ViewModel->SetMassAgent(Spawner, StableIndex); }
	SetThirdPersonCameraActive(bActivateCamera);
	OnObservedAgentChanged.Broadcast(nullptr);
}

void APCSPDemoPlayerController::ToggleThirdPersonCamera()
{
	if (!ObservedAgent.IsValid() && !ObservedMassSpawner.IsValid())
	{
		FocusNearestAgent();
		return;
	}
	SetThirdPersonCameraActive(!bThirdPersonCameraActive);
}

void APCSPDemoPlayerController::CycleAgent(int32 Delta)
{
	for (TActorIterator<APCSPMassSpawner> It(GetWorld()); It; ++It)
	{
		const int32 Count = It->GetSpawnedEntityCount();
		if (Count <= 0) { continue; }
		const int32 Current = ObservedMassSpawner.Get() == *It ? ObservedMassStableIndex : INDEX_NONE;
		const int32 Next = Current == INDEX_NONE ? 0 : ((Current + Delta) % Count + Count) % Count;
		ObserveMassAgent(*It, Next, bThirdPersonCameraActive);
		return;
	}
	TArray<APCSPAgentCharacter*> Sorted;
	GatherAgentsSortedByPersona(Sorted);
	if (Sorted.Num() == 0) { return; }

	int32 Idx = Sorted.IndexOfByKey(ObservedAgent.Get());
	if (Idx == INDEX_NONE) { Idx = 0; }
	else
	{
		Idx = (Idx + Delta + Sorted.Num()) % Sorted.Num();
	}
	SetObservedAgent(Sorted[Idx], bThirdPersonCameraActive);
}

void APCSPDemoPlayerController::ClearFocus()
{
	APawn* P = GetPawn();
	if (!P) { P = GetSpectatorPawn(); }
	if (P)
	{
		SetViewTargetWithBlend(P, ViewBlendTime);
	}
	bThirdPersonCameraActive = false;
}

void APCSPDemoPlayerController::ClearObservedAgent()
{
	ClearFocus();
	SetObservedAgent(nullptr, false);
}

void APCSPDemoPlayerController::SetThirdPersonCameraActive(bool bActive)
{
	if (bActive && ObservedMassSpawner.IsValid())
	{
		if (!MassFollowCamera && GetWorld())
		{
			MassFollowCamera = GetWorld()->SpawnActor<ACameraActor>();
		}
		if (MassFollowCamera)
		{
			UpdateMassFollowCamera();
			SetViewTargetWithBlend(MassFollowCamera, ViewBlendTime);
			bThirdPersonCameraActive = true;
			return;
		}
	}
	APCSPAgentCharacter* Agent = ObservedAgent.Get();
	if (bActive && Agent)
	{
		SetViewTargetWithBlend(Agent, ViewBlendTime);
		bThirdPersonCameraActive = true;
		return;
	}

	APawn* P = GetPawn();
	if (!P) { P = GetSpectatorPawn(); }
	if (P)
	{
		SetViewTargetWithBlend(P, ViewBlendTime);
	}
	bThirdPersonCameraActive = false;
}

void APCSPDemoPlayerController::SetObservedAgent(APCSPAgentCharacter* NewAgent, bool bActivateCamera)
{
	if (ObservedAgent.Get() == NewAgent && !ObservedMassSpawner.IsValid())
	{
		if (bActivateCamera)
		{
			SetThirdPersonCameraActive(true);
		}
		return;
	}
	ObservedAgent = NewAgent;
	ObservedMassSpawner.Reset();
	ObservedMassStableIndex = INDEX_NONE;
	if (ViewModel) { ViewModel->SetAgent(NewAgent); }
	SetThirdPersonCameraActive(bActivateCamera && NewAgent != nullptr);
	OnObservedAgentChanged.Broadcast(NewAgent);
}
