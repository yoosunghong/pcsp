#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "PCSPDemoPlayerController.generated.h"

class APCSPAgentCharacter;
class UPCSPAgentDebugViewModel;
class UPCSPDemoHUDWidgetBase;
class UUserWidget;
class APCSPMassSpawner;
class ACameraActor;
class APawn;

/**
 * Spectator-style controller for portfolio demo capture.
 *
 * Camera follows a selected `APCSPAgentCharacter` via `SetViewTargetWithBlend`
 * (no Possess — AI controllers keep running). Designed to be set as the
 * `PlayerControllerClass` on the demo game mode (or the `Map_PCSPDistrict_Portfolio`
 * World Settings).
 *
 * Default key bindings (legacy InputComponent — no Enhanced Input asset needed):
 *   F           — focus nearest agent / clear focus (toggle)
 *   Tab         — cycle next agent (by PersonaId)
 *   Shift+Tab   — cycle previous agent
 *   H           — broadcast HUD-visibility toggle
 *   Z           — broadcast zone-overlay toggle
 */
DECLARE_MULTICAST_DELEGATE_OneParam(FOnPCSPObservedAgentChanged, APCSPAgentCharacter* /*NewAgent*/);
DECLARE_MULTICAST_DELEGATE(FOnPCSPHudToggle);
DECLARE_MULTICAST_DELEGATE(FOnPCSPZoneOverlayToggle);

UCLASS()
class CNZOI_API APCSPDemoPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	APCSPDemoPlayerController();
	virtual void OnPossess(APawn* InPawn) override;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void PlayerTick(float DeltaSeconds) override;
	virtual void SetupInputComponent() override;

	/** Agent selected for HUD inspection; it may be selected while the camera remains in overview. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	APCSPAgentCharacter* GetObservedAgent() const { return ObservedAgent.Get(); }

	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	UPCSPAgentDebugViewModel* GetViewModel() const;

	/** Find the closest live agent to the current camera and blend to it. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void FocusNearestAgent();

	/** Select an agent for HUD inspection. Camera activation is optional and never possesses it. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ObserveAgent(APCSPAgentCharacter* NewAgent, bool bActivateCamera = false);

	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ObserveMassAgent(APCSPMassSpawner* Spawner, int32 StableIndex, bool bActivateCamera = false);

	/** Toggle the third-person follow camera while preserving the selected agent. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ToggleThirdPersonCamera();

	UFUNCTION(BlueprintPure, Category="PCSP|Demo")
	bool IsThirdPersonCameraActive() const { return bThirdPersonCameraActive; }

	/** Uniform visual scale of the selected NPC; 1 when there is no selection. */
	UFUNCTION(BlueprintPure, Category="PCSP|Demo")
	float GetObservedAgentVisualScale() const;

	/** Step through agents sorted by PersonaId (ascending). */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void CycleAgent(int32 Delta);

	/** Return view target to the player pawn (free spectator). */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ClearFocus();

	/** Explicitly clear the HUD selection as well as camera focus. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ClearObservedAgent();

	/** Select the Actor or Mass NPC currently under the mouse cursor. */
	void SelectAgentUnderCursor();

	FOnPCSPObservedAgentChanged  OnObservedAgentChanged;
	FOnPCSPHudToggle             OnHudToggle;
	FOnPCSPZoneOverlayToggle     OnZoneOverlayToggle;

	/** Blend time used by SetViewTargetWithBlend. */
	UPROPERTY(EditAnywhere, Category="PCSP|Demo", meta=(ClampMin="0.0", ClampMax="2.0"))
	float ViewBlendTime = 0.35f;

	/** Third-person framing authored for a 1x Mass body; runtime applies its visual scale. */
	UPROPERTY(EditAnywhere, Category="PCSP|Demo|Camera", meta=(ClampMin="0.0"))
	float MassFollowDistance = 380.f;

	UPROPERTY(EditAnywhere, Category="PCSP|Demo|Camera", meta=(ClampMin="0.0"))
	float MassFollowHeight = 210.f;

	UPROPERTY(EditAnywhere, Category="PCSP|Demo|Camera", meta=(ClampMin="0.0"))
	float MassLookAtHeight = 120.f;

	/** Assign WBP_PCSPDemoHUD (parented to UPCSPDemoHUDWidgetBase). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="PCSP|Demo|HUD")
	TSubclassOf<UPCSPDemoHUDWidgetBase> DemoHudClass;

	UPROPERTY(BlueprintReadOnly, Category="PCSP|Demo|HUD")
	TObjectPtr<UPCSPDemoHUDWidgetBase> DemoHud = nullptr;

protected:
	void HandleFocusKey();
	void HandleCycleNext();
	void HandleCyclePrev();
	void HandleToggleHud();
	void HandleToggleZoneOverlay();
	/** `P` cycles the runtime policy ablation; see the CVar in PCSPPolicySubsystem. */
	void HandleCyclePolicyMode();
	void UpdateMassFollowCamera();
	void ConfigureFreeCameraPawn(APawn* InPawn) const;
	void RunMassDemoSmokeCheck();
	void CaptureMassDemoSmokeFrame();
	void RunPerformanceSmokeStep();

	void SetObservedAgent(APCSPAgentCharacter* NewAgent, bool bActivateCamera);
	void SetThirdPersonCameraActive(bool bActive);
	void GatherAgentsSortedByPersona(TArray<APCSPAgentCharacter*>& Out) const;

	UPROPERTY()
	TWeakObjectPtr<APCSPAgentCharacter> ObservedAgent;

	UPROPERTY()
	TWeakObjectPtr<APCSPMassSpawner> ObservedMassSpawner;

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> MassFollowCamera = nullptr;

	int32 ObservedMassStableIndex = INDEX_NONE;

	UPROPERTY()
	TObjectPtr<UPCSPAgentDebugViewModel> ViewModel = nullptr;

	bool bThirdPersonCameraActive = false;
	FTimerHandle DemoSmokeTimer;
	int32 DemoSmokeFrame = 0;
	int32 PerformanceSmokeStep = 0;
};
