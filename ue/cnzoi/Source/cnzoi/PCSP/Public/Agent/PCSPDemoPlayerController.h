#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "PCSPDemoPlayerController.generated.h"

class APCSPAgentCharacter;
class UPCSPAgentDebugViewModel;

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

	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;

	/** Currently-observed agent (camera view target). Null = free spectator. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	APCSPAgentCharacter* GetObservedAgent() const { return ObservedAgent.Get(); }

	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	UPCSPAgentDebugViewModel* GetViewModel() const { return ViewModel; }

	/** Find the closest live agent to the current camera and blend to it. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void FocusNearestAgent();

	/** Step through agents sorted by PersonaId (ascending). */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void CycleAgent(int32 Delta);

	/** Return view target to the player pawn (free spectator). */
	UFUNCTION(BlueprintCallable, Category="PCSP|Demo")
	void ClearFocus();

	FOnPCSPObservedAgentChanged  OnObservedAgentChanged;
	FOnPCSPHudToggle             OnHudToggle;
	FOnPCSPZoneOverlayToggle     OnZoneOverlayToggle;

	/** Blend time used by SetViewTargetWithBlend. */
	UPROPERTY(EditAnywhere, Category="PCSP|Demo", meta=(ClampMin="0.0", ClampMax="2.0"))
	float ViewBlendTime = 0.35f;

protected:
	void HandleFocusKey();
	void HandleCycleNext();
	void HandleCyclePrev();
	void HandleToggleHud();
	void HandleToggleZoneOverlay();

	void SetObservedAgent(APCSPAgentCharacter* NewAgent);
	void GatherAgentsSortedByPersona(TArray<APCSPAgentCharacter*>& Out) const;

	UPROPERTY()
	TWeakObjectPtr<APCSPAgentCharacter> ObservedAgent;

	UPROPERTY()
	TObjectPtr<UPCSPAgentDebugViewModel> ViewModel = nullptr;
};
