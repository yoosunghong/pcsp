#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "PCSPAgentDebugViewModel.h"
#include "PCSPDemoHUDWidgetBase.generated.h"

class APCSPDemoPlayerController;
class UButton;
class UPanelWidget;
class UTextBlock;
class UWidget;
class UCanvasPanel;

USTRUCT(BlueprintType)
struct FPCSPHudDistributionEntry
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) EPCSPActionType Action = EPCSPActionType::IdleReflect;
	UPROPERTY(BlueprintReadOnly) FString Label;
	UPROPERTY(BlueprintReadOnly) int32 Count = 0;
	UPROPERTY(BlueprintReadOnly) float Fraction = 0.f;
	UPROPERTY(BlueprintReadOnly) FLinearColor Color = FLinearColor::White;
};

USTRUCT(BlueprintType)
struct FPCSPHudRunSnapshot
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) int32 AgentCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 ZoneCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 RecentDecisionCount = 0;
	UPROPERTY(BlueprintReadOnly) int32 RecentFailureCount = 0;
	UPROPERTY(BlueprintReadOnly) float MeanUrgency = 0.f;
	UPROPERTY(BlueprintReadOnly) TArray<FPCSPHudDistributionEntry> CurrentActionDistribution;
	UPROPERTY(BlueprintReadOnly) TArray<FPCSPHudDistributionEntry> SelectedActionDistribution;
};

/**
 * Native base for the portfolio HUD. It owns refresh timing, observer bindings,
 * distribution aggregation, button wiring, and the default data-driven view.
 * Blueprint children only author layout and optional presentation overrides.
 */
UCLASS(Abstract, Blueprintable)
class CNZOI_API UPCSPDemoHUDWidgetBase : public UUserWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void RefreshHud();

	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void ToggleThirdPersonCamera();

	/** Freeze the observed evidence for a side-by-side comparison; never changes policy. */
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void PinComparison();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void ClearComparison();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD")
	void ToggleDetails();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void TogglePerformance();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void RecordPCSP();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void RecordBTOnly();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void RecordNoPersona();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluatePersona();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluateArchitecture();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluateInference();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluationCount();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluationSeed();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluationVariant0();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluationVariant1();
	UFUNCTION(BlueprintCallable, Category="PCSP|HUD") void EvaluationVariant2();
	bool IsPerformanceOpen() const { return bShowPerformance; }

	UFUNCTION(BlueprintPure, Category="PCSP|HUD")
	bool HasPinnedComparison() const { return PinnedSnapshot.PersonaId > 0; }

	UFUNCTION(BlueprintPure, Category="PCSP|HUD")
	FPCSPHudAgentSnapshot GetAgentSnapshot() const { return AgentSnapshot; }

	UFUNCTION(BlueprintPure, Category="PCSP|HUD")
	FPCSPHudRunSnapshot GetRunSnapshot() const { return RunSnapshot; }

	/** True once the native policy-mode chip exists and is actually on screen. */
	UFUNCTION(BlueprintPure, Category="PCSP|HUD")
	bool IsPolicyBadgeVisible() const;

	/** Finds a named widget across this WBP and its nested child WBPs. */
	UFUNCTION(BlueprintPure, Category="PCSP|HUD")
	UWidget* FindWidget(FName Name) const { return FindWidgetRecursive(Name); }

	UFUNCTION(BlueprintImplementableEvent, Category="PCSP|HUD", meta=(DisplayName="On HUD Data Updated"))
	void ReceiveHudDataUpdated(const FPCSPHudAgentSnapshot& NewAgentSnapshot,
		const FPCSPHudRunSnapshot& NewRunSnapshot);

	/** Colour of the screen-space arrow drawn over the inspected NPC. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|HUD")
	FLinearColor SelectionMarkerColor = FLinearColor(0.10f, 1.f, 0.35f, 1.f);

	/**
	 * Height above the agent's feet at 1x scale. Runtime multiplies this by the
	 * selected NPC's visual scale, so it continues to clear an enlarged head.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|HUD", meta=(ClampMin="0.0"))
	float SelectionMarkerHeight = 205.f;

	/** Refresh cadence; 10 Hz keeps UI cost out of frame-time evidence. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|HUD", meta=(ClampMin="1.0", ClampMax="30.0"))
	float RefreshHz = 10.f;

	UPROPERTY(BlueprintReadOnly, Category="PCSP|HUD")
	FPCSPHudAgentSnapshot AgentSnapshot;

	UPROPERTY(BlueprintReadOnly, Category="PCSP|HUD")
	FPCSPHudRunSnapshot RunSnapshot;

protected:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
		int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

	UFUNCTION()
	void HandleCameraButtonClicked();

	/** Forwards clicks on the transparent background surface to world selection. */
	UFUNCTION()
	void HandleWorldClickSurfaceClicked();

	void HandleObservedAgentChanged(APCSPAgentCharacter* NewAgent);
	void HandleHudToggle();
	void GatherRunSnapshot();
	/** Creates the top-centre policy-mode chip; no-op once it exists. */
	void BuildPolicyBadge();
	void BuildPortfolioView();
	void RefreshPortfolioView();
	int32 PaintAnalytics(const FGeometry& Geometry, FSlateWindowElementList& Elements, int32 Layer) const;
	void ApplyDefaultPresentation();
	void RebuildDistributionPanel(UPanelWidget* Panel,
		const TArray<FPCSPHudDistributionEntry>& Entries, int32 MaxRows);
	void RebuildTrajectoryPanel(UPanelWidget* Panel);

	/** Projects the inspected agent to widget-local space; false when off screen. */
	bool GetSelectionMarkerAnchor(FVector2D& OutLocalPosition) const;

	UWidget* FindWidgetRecursive(FName Name) const;
	template<typename WidgetType> WidgetType* FindTypedWidget(FName Name) const
	{
		return Cast<WidgetType>(FindWidgetRecursive(Name));
	}

	UPROPERTY(Transient)
	TObjectPtr<APCSPDemoPlayerController> DemoController = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UPCSPAgentDebugViewModel> FallbackViewModel = nullptr;

	/** Native policy-mode chip; the authored cards have no run-level slot for it. */
	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> PolicyBadgeText = nullptr;

	UPROPERTY(Transient) TObjectPtr<UCanvasPanel> PortfolioCanvas;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> PortfolioStatus;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> SelectedEvidence;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> PinnedEvidence;
	UPROPERTY(Transient) FPCSPHudAgentSnapshot PinnedSnapshot;
	float PinnedAtSeconds = 0.f;
	bool bShowDetails = false;
	bool bShowPerformance = false;

	FTimerHandle RefreshTimer;
};
