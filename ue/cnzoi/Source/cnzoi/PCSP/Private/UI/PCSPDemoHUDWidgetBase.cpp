#include "UI/PCSPDemoHUDWidgetBase.h"

#include "Agent/PCSPAgentCharacter.h"
#include "Agent/PCSPDemoPlayerController.h"
#include "Affordance/PCSPAffordanceZone.h"
#include "Components/PCSPTrajectoryLogComponent.h"
#include "Inference/PCSPPolicySubsystem.h"
#include "Blueprint/WidgetLayoutLibrary.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/PanelWidget.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/ScrollBox.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"
#include "Rendering/DrawElements.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "TimerManager.h"
#include "Mass/PCSPMassSpawner.h"
#include "UObject/UnrealType.h"
#include "Sim/PCSPPerfSamplerSubsystem.h"
#include "Styling/CoreStyle.h"
#include "HAL/IConsoleManager.h"

namespace
{
	constexpr int32 ActionCount = static_cast<int32>(EPCSPActionType::None);

	FLinearColor ActionColor(const EPCSPActionType Action)
	{
		return PCSPVisualization::CategoryColor(UPCSPPolicySubsystem::ActionToCategory(Action));
	}

	/** `PCSP.Zone.Social.Hub03` reads as `Hub03` in a card this narrow. */
	FString ZoneTagLeaf(const FGameplayTag& Tag)
	{
		const FString Full = Tag.ToString();
		int32 LastDot = INDEX_NONE;
		return Full.FindLastChar(TEXT('.'), LastDot) ? Full.RightChop(LastDot + 1) : Full;
	}

	/** Trims to a word boundary so a wrapped paragraph cannot outgrow its card. */
	FString ElideAtWord(const FString& Text, const int32 MaxLength)
	{
		if (Text.Len() <= MaxLength) { return Text; }
		FString Clipped = Text.Left(MaxLength);
		int32 LastSpace = INDEX_NONE;
		if (Clipped.FindLastChar(TEXT(' '), LastSpace) && LastSpace > MaxLength / 2)
		{
			Clipped = Clipped.Left(LastSpace);
		}
		return Clipped.TrimEnd() + TEXT("...");
	}

	void SetTextIfPresent(const UPCSPDemoHUDWidgetBase* Hud, const FName Name, const FString& Value)
	{
		if (UTextBlock* Text = Cast<UTextBlock>(Hud->FindWidget(Name)))
		{
			Text->SetText(FText::FromString(Value));
		}
	}

	// One place for the HUD's visual language. The authored WBP assets keep their
	// structure and child names; the native view owns colour, type scale, chrome,
	// and placement so the eight cards read as a single system.
	namespace HudStyle
	{
		const FLinearColor PanelFill(0.030f, 0.038f, 0.055f, 0.88f);
		const FLinearColor PanelOutline(0.55f, 0.70f, 0.85f, 0.20f);
		const FLinearColor Accent(0.18f, 0.72f, 1.00f, 1.f);
		const FLinearColor TextPrimary(0.90f, 0.93f, 0.96f, 1.f);
		const FLinearColor TextSecondary(0.58f, 0.64f, 0.72f, 1.f);
		const FLinearColor BarTrack(1.f, 1.f, 1.f, 0.09f);

		constexpr float CornerRadius = 6.f;
		constexpr int32 TitleSize = 15;
		constexpr int32 LabelSize = 14;
		constexpr int32 ValueSize = 16;
		constexpr int32 RowSize = 15;
		constexpr float BarHeight = 10.f;
		constexpr int32 ButtonLabelSize = 12;

		FSlateBrush MakePanelBrush()
		{
			FSlateBrush Brush;
			Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
			Brush.TintColor = FSlateColor(PanelFill);
			Brush.OutlineSettings = FSlateBrushOutlineSettings(
				CornerRadius, FSlateColor(PanelOutline), 1.f);
			return Brush;
		}

		/** Flat black chip; the stock grey button read as a dialog control here. */
		FSlateBrush MakeButtonBrush(const FLinearColor& Fill)
		{
			FSlateBrush Brush;
			Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
			Brush.TintColor = FSlateColor(Fill);
			Brush.OutlineSettings = FSlateBrushOutlineSettings(
				4.f, FSlateColor(PanelOutline), 1.f);
			return Brush;
		}

		FSlateBrush MakeBarBrush(const FLinearColor& Color)
		{
			FSlateBrush Brush;
			Brush.DrawAs = ESlateBrushDrawType::RoundedBox;
			Brush.TintColor = FSlateColor(Color);
			Brush.OutlineSettings = FSlateBrushOutlineSettings(BarHeight * 0.5f);
			return Brush;
		}

		/** Dark track plus a saturated fill; the stock style washed out at this size. */
		void StyleBar(UProgressBar& Bar, const FLinearColor& FillColor)
		{
			FProgressBarStyle Style = Bar.GetWidgetStyle();
			Style.BackgroundImage = MakeBarBrush(BarTrack);
			Style.FillImage = MakeBarBrush(FLinearColor::White);
			Bar.SetWidgetStyle(Style);
			Bar.SetFillColorAndOpacity(FillColor);
		}

		void SetFontSize(UTextBlock& Text, const int32 Size)
		{
			FSlateFontInfo Font = Text.GetFont();
			Font.Size = Size;
			Text.SetFont(Font);
		}

		/** Uppercase headings are the authored convention, so they identify titles. */
		bool LooksLikeTitle(const FString& Label)
		{
			return Label.Len() > 3 && Label == Label.ToUpper() && Label != Label.ToLower();
		}
	}

	void SetCompactFont(UTextBlock* Text, const int32 Size = HudStyle::LabelSize)
	{
		HudStyle::SetFontSize(*Text, Size);
	}

	/** Where each authored card sits. Designed against 1920x1080; anchors carry it. */
	struct FHudPanelPlacement
	{
		const TCHAR* ClassName;
		FVector2D Anchor;
		FVector2D Alignment;
		FVector2D Position;
		FVector2D Size;
	};

	const FHudPanelPlacement HudPanelPlacements[] = {
		// Left rail, top to bottom: the decision pipeline, then the two list-shaped
		// cards stacked underneath, then the selected NPC filling the bottom.
		{TEXT("WBP_PCSPDecisionStack_C"),   {0.f, 0.f}, {0.f, 0.f}, {20.f, 20.f},   {430.f, 210.f}},
		{TEXT("WBP_PCSPNeedsBars_C"),       {0.f, 0.f}, {0.f, 0.f}, {20.f, 242.f},  {430.f, 240.f}},
		{TEXT("WBP_PCSPTrajectoryStrip_C"), {0.f, 0.f}, {0.f, 0.f}, {20.f, 494.f},  {430.f, 240.f}},
		// Right rail: population-level readouts, never per-agent.
		{TEXT("WBP_PCSPZoneLegend_C"),      {1.f, 0.f}, {1.f, 0.f}, {-20.f, 20.f},  {470.f, 268.f}},
		{TEXT("WBP_PCSPAffordancePanel_C"), {1.f, 0.f}, {1.f, 0.f}, {-20.f, 300.f}, {470.f, 148.f}},
		{TEXT("WBP_PCSPSocialPanel_C"),     {1.f, 0.f}, {1.f, 0.f}, {-20.f, 460.f}, {470.f, 104.f}},
		// Persona card takes the bottom-left corner the retired run badge freed up,
		// flush with the rail above it. It keeps its width because the description is
		// a paragraph of prose: at rail width it would wrap to six lines.
		{TEXT("WBP_PCSPAgnetCard_C"),       {0.f, 1.f}, {0.f, 1.f}, {20.f, -20.f},  {940.f, 322.f}},
	};

	/**
	 * Cards the native view no longer places. The run badge repeated the population
	 * counts already on the zone legend and the pipeline caption already on the
	 * decision stack, and cost the left rail its top 76 px to do it.
	 */
	const TCHAR* RetiredHudPanels[] = { TEXT("WBP_PCSPSmallRunBadge_C") };

	/**
	 * Places the authored cards on a two-rail grid. The assets were laid out
	 * independently of one another, which left the screen scattered with no reading
	 * order; this rewrites only their canvas slots, never their contents.
	 */
	void ApplyHudLayout(UWidgetTree* Tree)
	{
		if (!Tree) { return; }
		TArray<UWidget*> Widgets;
		Tree->GetAllWidgets(Widgets);
		for (UWidget* Widget : Widgets)
		{
			UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(Widget->Slot);
			if (!CanvasSlot || !Widget->IsA<UUserWidget>()) { continue; }
			const FString ClassName = Widget->GetClass()->GetName();
			bool bRetired = false;
			for (const TCHAR* Retired : RetiredHudPanels)
			{
				bRetired |= ClassName == Retired;
			}
			if (bRetired)
			{
				Widget->SetVisibility(ESlateVisibility::Collapsed);
				continue;
			}
			for (const FHudPanelPlacement& Placement : HudPanelPlacements)
			{
				if (ClassName != Placement.ClassName) { continue; }
				CanvasSlot->SetAutoSize(false);
				CanvasSlot->SetAnchors(FAnchors(Placement.Anchor.X, Placement.Anchor.Y));
				CanvasSlot->SetAlignment(Placement.Alignment);
				CanvasSlot->SetOffsets(FMargin(Placement.Position.X, Placement.Position.Y,
					Placement.Size.X, Placement.Size.Y));
				break;
			}
		}
	}

	/**
	 * The authored persona card weights its rows by fill, so as soon as the
	 * description wraps to a second line it overruns its slot and paints across the
	 * zone row beneath it. Auto-sizing every row makes each one exactly as tall as
	 * its own content; only the decision list absorbs whatever height is left.
	 */
	void ApplyPersonaCardLayout(const UPCSPDemoHUDWidgetBase& Hud)
	{
		UWidget* PersonaText = Hud.FindWidget(TEXT("T_PersonaText"));
		UPanelWidget* Column = PersonaText ? PersonaText->GetParent() : nullptr;
		if (!Column) { return; }
		for (UWidget* Child : Column->GetAllChildren())
		{
			UVerticalBoxSlot* Slot = Child ? Cast<UVerticalBoxSlot>(Child->Slot) : nullptr;
			if (!Slot) { continue; }
			const bool bStretches = Child->GetName().StartsWith(TEXT("VB_"));
			Slot->SetSize(FSlateChildSize(bStretches
				? ESlateSizeRule::Fill : ESlateSizeRule::Automatic));
			// Left-align the button so it shrinks to its label instead of spanning
			// the card; everything else is text that should use the full width.
			Slot->SetHorizontalAlignment(Child->IsA<UButton>() ? HAlign_Left : HAlign_Fill);
			Slot->SetPadding(FMargin(0.f, 0.f, 0.f, 5.f));
		}
	}

	/**
	 * The authored follow toggle is a full-width stock button, which at card width
	 * reads as the card's primary content rather than one control on it. Black chip,
	 * content-width, smaller label.
	 */
	void StyleCameraButton(UButton& Button)
	{
		FButtonStyle Style = Button.GetStyle();
		Style.Normal = HudStyle::MakeButtonBrush(FLinearColor(0.f, 0.f, 0.f, 0.92f));
		Style.Hovered = HudStyle::MakeButtonBrush(FLinearColor(0.10f, 0.11f, 0.13f, 0.96f));
		Style.Pressed = HudStyle::MakeButtonBrush(FLinearColor(0.03f, 0.03f, 0.04f, 1.f));
		Style.Disabled = HudStyle::MakeButtonBrush(FLinearColor(0.f, 0.f, 0.f, 0.45f));
		// The stock 8 px vertical padding is most of the button's height at this
		// label size, so it has to come down with the font.
		Style.NormalPadding = FMargin(12.f, 3.f);
		Style.PressedPadding = FMargin(12.f, 3.f);
		Button.SetStyle(Style);

		for (UWidget* Child : Button.GetAllChildren())
		{
			if (UTextBlock* Label = Cast<UTextBlock>(Child))
			{
				HudStyle::SetFontSize(*Label, HudStyle::ButtonLabelSize);
				Label->SetColorAndOpacity(FSlateColor(HudStyle::TextPrimary));
			}
		}
	}

	void StyleHudTree(UWidgetTree* Tree, const bool bMassPopulation)
	{
		if (!Tree) { return; }
		const UUserWidget* Owner = Cast<UUserWidget>(Tree->GetOuter());
		const bool bDecisionStack = Owner
			&& Owner->GetClass()->GetName() == TEXT("WBP_PCSPDecisionStack_C");
		TArray<UWidget*> Widgets;
		Tree->GetAllWidgets(Widgets);
		for (UWidget* Widget : Widgets)
		{
			if (UTextBlock* Text = Cast<UTextBlock>(Widget))
			{
				// The stock 24-point text overflows the authored cards even at 1080p.
				// Size by role rather than uniformly, so titles, labels, and values are
				// distinguishable instead of one undifferentiated block.
				const FString Label = Text->GetText().ToString();
				const bool bTitle = HudStyle::LooksLikeTitle(Label);
				const bool bNarrow = bDecisionStack && Text->GetName().EndsWith(TEXT("State"));
				HudStyle::SetFontSize(*Text, bTitle ? HudStyle::TitleSize
					: bNarrow ? HudStyle::LabelSize : HudStyle::ValueSize);
				Text->SetColorAndOpacity(FSlateColor(bTitle ? HudStyle::Accent
					: Text->GetName().EndsWith(TEXT("Label")) ? HudStyle::TextSecondary
					: HudStyle::TextPrimary));
				if (bDecisionStack && Label == TEXT("AffordanceTarget"))
				{
					Text->SetText(FText::FromString(TEXT("Target")));
				}
				// The crowd runs the policy directly rather than through a Behavior
				// Tree, and keeps a bounded decision ring rather than mirroring the
				// JSONL log. Both authored captions would otherwise be wrong - but
				// neither replacement names the backend, which the viewer cannot act
				// on and does not need.
				if (bMassPopulation && Label.Contains(TEXT("BEHAVIOR TREE")))
				{
					Text->SetText(FText::FromString(TEXT("PERSONA POLICY  >  DECISION  >  AFFORDANCE")));
				}
				if (bMassPopulation && Label.Contains(TEXT("LIVE JSONL MIRROR")))
				{
					Text->SetText(FText::FromString(TEXT("RECENT DECISIONS")));
				}
				if (Label.Contains(TEXT("AFFORDANCE TARGET")))
				{
					Text->SetText(FText::FromString(TEXT("WHERE THIS NPC IS HEADING")));
				}
				if (Label.Contains(TEXT("SOCIAL CONTEXT")))
				{
					Text->SetText(FText::FromString(TEXT("WHO IS AROUND THIS NPC")));
				}
			}
			if (UBorder* Border = Cast<UBorder>(Widget))
			{
				// Authored cards are flat, borderless, fully opaque fills. Give every
				// one the same translucent rounded box so they read as panels and the
				// district stays visible behind them.
				if (!Border->Background.GetResourceObject())
				{
					Border->SetBrush(HudStyle::MakePanelBrush());
				}
			}
			if (UImage* Image = Cast<UImage>(Widget))
			{
				if (Image->GetBrush().GetResourceObject()) { continue; }
				// Only a layered container stacks a background behind its content. In
				// a box, child 0 is the first item in the row - the decision stack's
				// unassigned step icons live there, and painting them turned them into
				// visible squares.
				const UPanelWidget* Parent = Image->GetParent();
				const bool bBackgroundLayer = Parent
					&& (Parent->IsA<UOverlay>() || Parent->IsA<UCanvasPanel>())
					&& Parent->GetChildrenCount() > 1
					&& Parent->GetChildIndex(Image) == 0;
				if (bBackgroundLayer)
				{
					Image->SetBrush(HudStyle::MakePanelBrush());
				}
				else
				{
					// Unassigned icons and the legacy flow card's diagram placeholder.
					// Do not draw their fallback rectangles.
					Image->SetVisibility(ESlateVisibility::Collapsed);
				}
			}
			if (UProgressBar* Bar = Cast<UProgressBar>(Widget))
			{
				HudStyle::StyleBar(*Bar, HudStyle::Accent);
			}
			if (UUserWidget* Child = Cast<UUserWidget>(Widget))
			{
				StyleHudTree(Child->WidgetTree, bMassPopulation);
			}
		}
	}
}

void UPCSPDemoHUDWidgetBase::NativeConstruct()
{
	// The authored WBP fills the viewport. If the UserWidget/root canvas remain
	// Visible, Slate registers that empty canvas as a hit-test target and packaged
	// GameAndUI input can consume world clicks before the PlayerController sees
	// LeftMouseButton. Keep real children (buttons/scroll boxes) interactive while
	// allowing clicks through every unoccupied HUD region to select NPCs.
	SetVisibility(ESlateVisibility::SelfHitTestInvisible);
	if (UWidget* RootWidget = GetRootWidget())
	{
		RootWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
	}

	DemoController = Cast<APCSPDemoPlayerController>(GetOwningPlayer());
	if (!DemoController && GetWorld())
	{
		DemoController = Cast<APCSPDemoPlayerController>(GetWorld()->GetFirstPlayerController());
		if (DemoController) { SetOwningPlayer(DemoController); }
	}
	if (DemoController) { DemoController->DemoHud = this; }
	if (!FallbackViewModel) { FallbackViewModel = NewObject<UPCSPAgentDebugViewModel>(this); }
	UPCSPAgentDebugViewModel* BoundViewModel = DemoController
		? DemoController->GetViewModel() : FallbackViewModel.Get();
	// Legacy WBP_PCSPDemoHUD owns a Blueprint-local ViewModel variable and a
	// RefreshSnapshot timer. Bind it before Super invokes Blueprint Construct.
	FObjectPropertyBase* LegacyProperty = FindFProperty<FObjectPropertyBase>(GetClass(), TEXT("ViewModel"));
	if (LegacyProperty && BoundViewModel->IsA(LegacyProperty->PropertyClass))
	{
		LegacyProperty->SetObjectPropertyValue_InContainer(this, BoundViewModel);
	}
	Super::NativeConstruct();
	if (LegacyProperty && BoundViewModel->IsA(LegacyProperty->PropertyClass))
	{
		LegacyProperty->SetObjectPropertyValue_InContainer(this, BoundViewModel);
	}
	UE_LOG(LogTemp, Log, TEXT("PCSPDemoHUD: native construct controller=%s legacy_viewmodel=%s"),
		*GetNameSafe(DemoController), *GetNameSafe(BoundViewModel));
	if (DemoController)
	{
		DemoController->OnObservedAgentChanged.AddUObject(this, &UPCSPDemoHUDWidgetBase::HandleObservedAgentChanged);
		DemoController->OnHudToggle.AddUObject(this, &UPCSPDemoHUDWidgetBase::HandleHudToggle);
	}
	if (UButton* CameraButton = FindTypedWidget<UButton>(TEXT("Btn_ToggleCamera")))
	{
		CameraButton->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::HandleCameraButtonClicked);
		StyleCameraButton(*CameraButton);
	}
	const bool bMassPopulation = GetWorld() && TActorIterator<APCSPMassSpawner>(GetWorld());
	ApplyHudLayout(WidgetTree);
	StyleHudTree(WidgetTree, bMassPopulation);
	for (const FName Retired : { FName(TEXT("T_CameraMode")), FName(TEXT("T_SelectionHint")) })
	{
		if (UWidget* Widget = FindWidgetRecursive(Retired))
		{
			Widget->SetVisibility(ESlateVisibility::Collapsed);
		}
	}
	BuildPolicyBadge();
	BuildPortfolioView();
	if (const auto* Eval = GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()) { bShowPerformance = Eval->bShowHUD; }
	// The persona description is authored prose, not a label; without wrapping it
	// runs past the card no matter how wide the card is.
	if (UTextBlock* PersonaText = FindTypedWidget<UTextBlock>(TEXT("T_PersonaText")))
	{
		PersonaText->SetAutoWrapText(true);
	}
	ApplyPersonaCardLayout(*this);

	RefreshHud();
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(RefreshTimer, this,
			&UPCSPDemoHUDWidgetBase::RefreshHud, 1.f / FMath::Max(1.f, RefreshHz), true);
	}
}

void UPCSPDemoHUDWidgetBase::NativeDestruct()
{
	if (UWorld* World = GetWorld())
	{
		// Also clear Blueprint-owned SetTimerByFunctionName delegates. Clearing
		// only RefreshTimer left RefreshSnapshot running during PIE teardown.
		World->GetTimerManager().ClearAllTimersForObject(this);
	}
	if (DemoController)
	{
		DemoController->OnObservedAgentChanged.RemoveAll(this);
		DemoController->OnHudToggle.RemoveAll(this);
	}
	Super::NativeDestruct();
}

void UPCSPDemoHUDWidgetBase::RefreshHud()
{
	if (!DemoController)
	{
		DemoController = Cast<APCSPDemoPlayerController>(GetOwningPlayer());
	}
	if (DemoController && DemoController->GetViewModel())
	{
		AgentSnapshot = DemoController->GetViewModel()->BuildSnapshot(32);
	}
	GatherRunSnapshot();
	ApplyDefaultPresentation();
	ReceiveHudDataUpdated(AgentSnapshot, RunSnapshot);
	RefreshPortfolioView();
}

void UPCSPDemoHUDWidgetBase::PinComparison()
{
	if (AgentSnapshot.PersonaId <= 0) { return; }
	PinnedSnapshot = AgentSnapshot;
	PinnedAtSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	RefreshPortfolioView();
}

void UPCSPDemoHUDWidgetBase::ClearComparison()
{
	PinnedSnapshot = FPCSPHudAgentSnapshot();
	RefreshPortfolioView();
}

void UPCSPDemoHUDWidgetBase::ToggleDetails()
{
	bShowPerformance = false;
	bShowDetails = !bShowDetails;
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::TogglePerformance()
{
	bShowPerformance = !bShowPerformance;
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::EvaluatePersona()
{
	GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->SelectAxis(0); RefreshHud();
}
void UPCSPDemoHUDWidgetBase::EvaluateArchitecture()
{
	GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->SelectAxis(1); RefreshHud();
}
void UPCSPDemoHUDWidgetBase::EvaluateInference()
{
	GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->SelectAxis(2); RefreshHud();
}
void UPCSPDemoHUDWidgetBase::EvaluationCount()
{
	GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->CycleCount(); RefreshHud();
}
void UPCSPDemoHUDWidgetBase::EvaluationSeed()
{
	GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->CycleSeed(); RefreshHud();
}
void UPCSPDemoHUDWidgetBase::EvaluationVariant0() { GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->StartVariant(0); }
void UPCSPDemoHUDWidgetBase::EvaluationVariant1() { GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->StartVariant(1); }
void UPCSPDemoHUDWidgetBase::EvaluationVariant2()
{
	auto* Eval = GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
	if (Eval->Axis == 2)
	{
		GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>()->StopEvaluationForReplay();
		Eval->ReplayStatus = GetWorld()->GetSubsystem<UPCSPPolicySubsystem>()->RunFixedInputReplay();
		RefreshHud();
	}
	else { Eval->StartVariant(2); }
}

void UPCSPDemoHUDWidgetBase::RecordPCSP()
{
	if (auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>()) { Perf->SelectMode(EPCSPPolicyMode::HybridPCSP); }
	bShowPerformance = true;
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::RecordBTOnly()
{
	if (auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>()) { Perf->SelectMode(EPCSPPolicyMode::BTOnly); }
	bShowPerformance = true;
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::RecordNoPersona()
{
	if (auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>()) { Perf->SelectMode(EPCSPPolicyMode::HybridNoPersona); }
	bShowPerformance = true;
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::BuildPortfolioView()
{
	UCanvasPanel* Root = Cast<UCanvasPanel>(GetRootWidget());
	if (!Root || PortfolioCanvas) { return; }
	PortfolioCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("PortfolioCanvas"));
	PortfolioCanvas->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
	UCanvasPanelSlot* CanvasSlot = Root->AddChildToCanvas(PortfolioCanvas);
	CanvasSlot->SetZOrder(20);
	PortfolioCanvas->SetRenderTransformPivot(FVector2D::ZeroVector);

	// GameAndUI gives Slate the first chance to handle a mouse press. In a
	// packaged build the viewport-sized WBP still owns the pointer route even
	// when its empty canvas is self-hit-test-invisible, so the controller's
	// legacy LeftMouse binding is not guaranteed to fire. This transparent,
	// lowest-Z button deliberately handles empty HUD space and forwards the
	// current cursor position to the same world/Mass picking implementation.
	// Real HUD controls are added later at Z=0 and remain above this surface.
	UButton* WorldClickSurface = WidgetTree->ConstructWidget<UButton>(
		UButton::StaticClass(), TEXT("WorldClickSurface"));
	WorldClickSurface->SetBackgroundColor(FLinearColor::Transparent);
	WorldClickSurface->OnClicked.AddUniqueDynamic(
		this, &UPCSPDemoHUDWidgetBase::HandleWorldClickSurfaceClicked);
	if (UCanvasPanelSlot* ClickSlot = PortfolioCanvas->AddChildToCanvas(WorldClickSurface))
	{
		ClickSlot->SetAnchors(FAnchors(0.f, 0.f, 1.f, 1.f));
		ClickSlot->SetOffsets(FMargin(0.f));
		ClickSlot->SetZOrder(-100);
	}

	auto AddCard = [this](const FName Name, UTextBlock*& Text)
	{
		UBorder* Card = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), Name);
		Card->SetBrush(HudStyle::MakePanelBrush());
		Card->SetPadding(FMargin(18.f));
		UScrollBox* Scroll = WidgetTree->ConstructWidget<UScrollBox>();
		Scroll->SetScrollBarVisibility(ESlateVisibility::Collapsed);
		Text = WidgetTree->ConstructWidget<UTextBlock>();
		SetCompactFont(Text, 15);
		FSlateFontInfo Font = Text->GetFont();
		Font.TypefaceFontName = TEXT("Regular");
		Text->SetFont(Font);
		Text->SetAutoWrapText(true);
		Text->SetColorAndOpacity(FSlateColor(HudStyle::TextPrimary));
		Scroll->AddChild(Text);
		Card->AddChild(Scroll);
		PortfolioCanvas->AddChildToCanvas(Card);
	};
	UTextBlock* Text = nullptr;
	AddCard(TEXT("SelectedEvidenceCard"), Text);
	SelectedEvidence = Text;
	AddCard(TEXT("PinnedEvidenceCard"), Text);
	PinnedEvidence = Text;
	PortfolioStatus = WidgetTree->ConstructWidget<UTextBlock>();
	SetCompactFont(PortfolioStatus, 16);
	PortfolioStatus->SetColorAndOpacity(FSlateColor(HudStyle::Accent));
	PortfolioCanvas->AddChildToCanvas(PortfolioStatus);
	UBorder* PerformanceBackground = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("PerformanceBackground"));
	PerformanceBackground->SetBrush(HudStyle::MakePanelBrush());
	PortfolioCanvas->AddChildToCanvas(PerformanceBackground);

	auto AddButton = [this](const FName Name, const TCHAR* Label)
	{
		UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), Name);
		UTextBlock* Caption = WidgetTree->ConstructWidget<UTextBlock>();
		Caption->SetText(FText::FromString(Label));
		Button->AddChild(Caption);
		StyleCameraButton(*Button);
		HudStyle::SetFontSize(*Caption, 13);
		PortfolioCanvas->AddChildToCanvas(Button);
		return Button;
	};
	AddButton(TEXT("PortfolioPin"), TEXT("Pin comparison"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::PinComparison);
	AddButton(TEXT("PortfolioClear"), TEXT("Clear pin"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::ClearComparison);
	AddButton(TEXT("PortfolioDetails"), TEXT("Details / Back"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::ToggleDetails);
	AddButton(TEXT("PortfolioCamera"), TEXT("Follow / Free"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::ToggleThirdPersonCamera);
	AddButton(TEXT("PortfolioPerformance"), TEXT("Performance"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::TogglePerformance);
	AddButton(TEXT("EvalPersona"), TEXT("1. Persona effect"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluatePersona);
	AddButton(TEXT("EvalArchitecture"), TEXT("2. Execution"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluateArchitecture);
	AddButton(TEXT("EvalInference"), TEXT("3. Inference"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluateInference);
	AddButton(TEXT("EvalCount"), TEXT("NPCs"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluationCount);
	AddButton(TEXT("EvalSeed"), TEXT("Seed"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluationSeed);
	AddButton(TEXT("PerfPCSP"), TEXT("PCSP / Persona"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluationVariant0);
	AddButton(TEXT("PerfBT"), TEXT("Needs heuristic"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluationVariant1);
	AddButton(TEXT("PerfNoPersona"), TEXT("No Persona"))->OnClicked.AddUniqueDynamic(this, &UPCSPDemoHUDWidgetBase::EvaluationVariant2);
}

void UPCSPDemoHUDWidgetBase::HandleWorldClickSurfaceClicked()
{
	if (DemoController)
	{
		DemoController->SelectAgentUnderCursor();
	}
}

void UPCSPDemoHUDWidgetBase::RefreshPortfolioView()
{
	if (!PortfolioCanvas) { return; }
	// Work in physical pixels. The old 1920-wide authored canvas reduced 15 pt
	// labels to ~8 pixels in a 1024-wide viewport. Preserve legible type on resize.
	const float DPI = FMath::Max(0.1f, UWidgetLayoutLibrary::GetViewportScale(this));
	const FVector2D Pixels = UWidgetLayoutLibrary::GetViewportSize(this);
	CastChecked<UCanvasPanelSlot>(PortfolioCanvas->Slot)->SetSize(Pixels / DPI);
	HudStyle::SetFontSize(*SelectedEvidence, FMath::RoundToInt(15.f / DPI));
	HudStyle::SetFontSize(*PinnedEvidence, FMath::RoundToInt(15.f / DPI));
	HudStyle::SetFontSize(*PortfolioStatus, FMath::RoundToInt(16.f / DPI));
	const float Width = FMath::Clamp(Pixels.X * 0.29f, 280.f, 370.f);
	const float Height = FMath::Clamp(Pixels.Y - 136.f, 180.f, 680.f);
	const float PerfWidth = FMath::Min(Pixels.X - 40.f, 1100.f);
	const float PerfX = (Pixels.X - PerfWidth) * 0.5f;
	const auto* Eval = GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
	auto Place = [DPI](UWidget* Widget, const FVector2D Position, const FVector2D Size)
	{
		if (UCanvasPanelSlot* Slot = Cast<UCanvasPanelSlot>(Widget->Slot))
		{
			Slot->SetPosition(Position / DPI);
			Slot->SetSize(Size / DPI);
		}
	};
	Place(PortfolioStatus, {20.f, 18.f}, {Pixels.X - 40.f, 30.f});
	for (UWidget* Widget : PortfolioCanvas->GetAllChildren())
	{
		const FName Name = Widget->GetFName();
		if (UBorder* Card = Cast<UBorder>(Widget)) { Card->SetPadding(FMargin(18.f / DPI)); }
		if (UButton* Button = Cast<UButton>(Widget))
		{
			if (UTextBlock* Caption = Cast<UTextBlock>(Button->GetContent()))
			{
				HudStyle::SetFontSize(*Caption, FMath::RoundToInt(13.f / DPI));
			}
		}
		if (Name == TEXT("SelectedEvidenceCard") || Name == TEXT("PinnedEvidenceCard"))
		{
			const bool bPinned = Name == TEXT("PinnedEvidenceCard");
			const float RightHeight = bShowDetails ? Height : FMath::Min(Height, Pixels.Y - 336.f);
			Place(Widget, {bPinned ? Pixels.X - Width - 20.f : 20.f, 64.f},
				{Width, bPinned ? (!HasPinnedComparison() && !bShowDetails ? FMath::Min(RightHeight, 250.f) : RightHeight) : Height});
			Widget->SetVisibility(bShowPerformance ? ESlateVisibility::Collapsed : ESlateVisibility::Visible);
		}
		if (Name == TEXT("PerformanceBackground"))
		{
			Place(Widget, {PerfX, 64.f}, {PerfWidth, Pixels.Y - 136.f});
			Widget->SetVisibility(bShowPerformance ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
		}
		const TCHAR* ModeButtons[] = {TEXT("PerfPCSP"), TEXT("PerfBT"), TEXT("PerfNoPersona")};
		for (int32 Index = 0; Index < 3; ++Index)
		{
			if (Name == ModeButtons[Index])
			{
				const float ButtonWidth = (PerfWidth - 60.f) / 3.f;
				Place(Widget, {PerfX + 20.f + Index * (ButtonWidth + 10.f), 124.f}, {ButtonWidth, 32.f});
				Widget->SetVisibility(bShowPerformance && (Index < Eval->VariantCount() || Eval->Axis == 2) ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
				if (auto* Button = Cast<UButton>(Widget))
				{
					CastChecked<UTextBlock>(Button->GetContent())->SetText(FText::FromString(Eval->Axis == 2 && Index == 2
						? TEXT("Stop & replay fixed inputs") : TEXT("Restart: ") + UPCSPEvaluationSubsystem::VariantName(Eval->Axis, Index)));
				}
			}
		}
		const TCHAR* EvalButtons[] = {TEXT("EvalPersona"), TEXT("EvalArchitecture"), TEXT("EvalInference"), TEXT("EvalCount"), TEXT("EvalSeed")};
		for (int32 Index = 0; Index < 5; ++Index)
		{
			if (Name == EvalButtons[Index])
			{
				const float ButtonWidth = (PerfWidth - 60.f) / 5.f;
				Place(Widget, {PerfX + 20.f + Index * (ButtonWidth + 5.f), 80.f}, {ButtonWidth, 32.f});
				Widget->SetVisibility(bShowPerformance ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
				if (Index >= 3)
				{
					auto* Caption = CastChecked<UTextBlock>(CastChecked<UButton>(Widget)->GetContent());
					Caption->SetText(FText::FromString(FString::Printf(TEXT("%s: %d"), Index == 3 ? TEXT("NPCs") : TEXT("Seed"), Index == 3 ? Eval->Count : Eval->Seed)));
				}
			}
		}
		const TCHAR* Buttons[] = {TEXT("PortfolioPin"), TEXT("PortfolioClear"), TEXT("PortfolioCamera"), TEXT("PortfolioDetails"), TEXT("PortfolioPerformance")};
		for (int32 Index = 0; Index < 5; ++Index)
		{
			if (Name == Buttons[Index]) { Place(Widget, {20.f + Index * 145.f, Pixels.Y - 52.f}, {135.f, 34.f}); }
		}
	}
	// Keep legacy Blueprint bindings alive, but use one responsive presentation
	// for both the comparison and diagnostics views.
	for (UWidget* Widget : CastChecked<UCanvasPanel>(GetRootWidget())->GetAllChildren())
	{
		if (Widget == PortfolioCanvas) { continue; }
		Widget->SetVisibility(ESlateVisibility::Collapsed);
		for (const TCHAR* Retired : RetiredHudPanels)
		{
			if (Widget->GetClass()->GetName() == Retired) { Widget->SetVisibility(ESlateVisibility::Collapsed); }
		}
	}
	const FString Mode = UPCSPPolicySubsystem::GetPolicyMode() == EPCSPPolicyMode::BTOnly
		? TEXT("Needs heuristic / ONNX off") : UPCSPPolicySubsystem::PolicyModeName(UPCSPPolicySubsystem::GetPolicyMode());
	PortfolioStatus->SetText(FText::FromString(FString::Printf(
		TEXT("PCSP  /  PERSONA & BEHAVIOR     %d NPCs  |  %s"), RunSnapshot.AgentCount, *Mode)));
	auto Evidence = [](const FPCSPHudAgentSnapshot& Snapshot, const FString& Heading)
	{
		if (Snapshot.PersonaId <= 0)
		{
			return Heading + TEXT("\n\nSelect an NPC with a click or Tab.\n\nPin its evidence, then select another NPC to compare persona and decision history.\n\nPinned evidence is a frozen snapshot.");
		}
		const FString Phase = Snapshot.bMassEntity
			? Snapshot.bMoving ? TEXT("Walking") : Snapshot.bInteracting ? TEXT("Interacting") : TEXT("Choosing a target")
			: Snapshot.bAffordanceReserved ? TEXT("Reserved / executing") : TEXT("Choosing a target");
		FString Result = FString::Printf(TEXT("%s\nNPC #%04d  /  PERSONA #%03d\n\n%s\n\nNOW  /  %s\n%s"),
			*Heading, Snapshot.StableIndex, Snapshot.PersonaId, *Snapshot.PersonaText,
			*UPCSPAgentDebugViewModel::ActionDisplayName(Snapshot.DesiredAction), *Phase);
		if (Snapshot.DistanceToTarget >= 0.f) { Result += FString::Printf(TEXT("  /  %.1f m remaining"), Snapshot.DistanceToTarget / 100.f); }
		if (Snapshot.CurrentZoneTag.IsValid()) { Result += TEXT("\nTarget  ") + ZoneTagLeaf(Snapshot.CurrentZoneTag); }
		Result += TEXT("\n\nRECENT HISTORY  /  oldest to newest\n");
		if (Snapshot.RecentEvents.IsEmpty()) { Result += TEXT("Waiting for the first recorded decision.\n"); }
		// Collapse consecutive repeats, retaining their time range and count. Do
		// not mislabel a Mass decision as a completed interaction.
		TArray<FString> Rows;
		for (int32 First = 0; First < Snapshot.RecentEvents.Num();)
		{
			int32 Last = First;
			const FPCSPTrajectoryEntry& Entry = Snapshot.RecentEvents[First];
			while (Last + 1 < Snapshot.RecentEvents.Num()
				&& Snapshot.RecentEvents[Last + 1].Action == Entry.Action
				&& Snapshot.RecentEvents[Last + 1].EventType == Entry.EventType) { ++Last; }
			FString Row = FString::Printf(TEXT("%.1fs"), Entry.TimeSeconds);
			if (Last > First) { Row += FString::Printf(TEXT(" - %.1fs  (x%d)"), Snapshot.RecentEvents[Last].TimeSeconds, Last - First + 1); }
			Row += TEXT("\n") + UPCSPAgentDebugViewModel::ActionDisplayName(Entry.Action);
			if (!Snapshot.bMassEntity) { Row += TEXT(" / ") + UPCSPAgentDebugViewModel::EventDisplayName(Entry.EventType); }
			Rows.Add(Row);
			First = Last + 1;
		}
		for (int32 Index = FMath::Max(0, Rows.Num() - 6); Index < Rows.Num(); ++Index) { Result += TEXT("\n") + Rows[Index] + TEXT("\n"); }
		Result += Snapshot.bMassEntity ? TEXT("\nDecision samples; completion is shown in NOW.") : TEXT("\nRecorded decision and interaction events.");
		Result += TEXT("\nScroll for the full visible record.");
		return Result;
	};
	SelectedEvidence->SetText(FText::FromString(Evidence(AgentSnapshot, TEXT("SELECTED  /  LIVE"))));
	PinnedEvidence->SetText(FText::FromString(Evidence(PinnedSnapshot, HasPinnedComparison()
		? FString::Printf(TEXT("PINNED  /  at %.1fs"), PinnedAtSeconds) : FString(TEXT("COMPARE PERSONAS")))));
	if (bShowDetails)
	{
		FString Needs = TEXT("SELECTED / NEEDS & TARGET\n\n");
		const TCHAR* Labels[] = {TEXT("Hunger"), TEXT("Sleep"), TEXT("Social"), TEXT("Leisure"),
			TEXT("Hygiene"), TEXT("Fitness"), TEXT("Work"), TEXT("Learning")};
		for (int32 Index = 0; Index < FMath::Min(8, AgentSnapshot.Needs.Num()); ++Index)
		{
			Needs += FString::Printf(TEXT("%s   %.0f%%\n"), Labels[Index], AgentSnapshot.Needs[Index] * 100.f);
		}
		Needs += TEXT("\nLower values indicate greater need.\n\n");
		Needs += FString::Printf(TEXT("Target slots   %d / %d\nNearby NPCs   %d\n\n"),
			AgentSnapshot.ZoneOccupancy, AgentSnapshot.ZoneCapacity, AgentSnapshot.NearbyCount);
		SelectedEvidence->SetText(FText::FromString(Needs + Evidence(AgentSnapshot, TEXT("PERSONA & HISTORY"))));
		FString Population = FString::Printf(TEXT("POPULATION / LIVE\n%d NPCs  /  %d zones\n\nCURRENT ACTIONS\n"), RunSnapshot.AgentCount, RunSnapshot.ZoneCount);
		for (const FPCSPHudDistributionEntry& Entry : RunSnapshot.CurrentActionDistribution)
		{
			Population += FString::Printf(TEXT("\n%s\n%d NPCs  /  %.0f%%\n"), *Entry.Label, Entry.Count, Entry.Fraction * 100.f);
		}
		Population += TEXT("\nDetails / Back returns to your comparison.");
		PinnedEvidence->SetText(FText::FromString(Population));
	}
	// Detailed population bars are painted in the right card, using all actions.
	PinnedEvidence->SetVisibility(bShowDetails ? ESlateVisibility::Collapsed : ESlateVisibility::Visible);
}

void UPCSPDemoHUDWidgetBase::ToggleThirdPersonCamera()
{
	if (DemoController)
	{
		DemoController->ToggleThirdPersonCamera();
		RefreshHud();
	}
}

void UPCSPDemoHUDWidgetBase::HandleCameraButtonClicked()
{
	ToggleThirdPersonCamera();
}

void UPCSPDemoHUDWidgetBase::HandleObservedAgentChanged(APCSPAgentCharacter*)
{
	RefreshHud();
}

void UPCSPDemoHUDWidgetBase::HandleHudToggle()
{
	SetVisibility(GetVisibility() == ESlateVisibility::Collapsed
		? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
}

void UPCSPDemoHUDWidgetBase::GatherRunSnapshot()
{
	RunSnapshot = FPCSPHudRunSnapshot();
	UWorld* World = GetWorld();
	if (!World) { return; }

	TArray<int32> CurrentCounts;
	TArray<int32> SelectedCounts;
	CurrentCounts.Init(0, ActionCount);
	SelectedCounts.Init(0, ActionCount);
	float UrgencySum = 0.f;
	int32 UrgencySamples = 0;

	for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
	{
		++RunSnapshot.ZoneCount;
	}

	for (TActorIterator<APCSPAgentCharacter> It(World); It; ++It)
	{
		APCSPAgentCharacter* Agent = *It;
		if (!IsValid(Agent)) { continue; }
		++RunSnapshot.AgentCount;

		EPCSPActionType CurrentAction = EPCSPActionType::IdleReflect;
		float CurrentUrgency = 0.f;
		if (const AAIController* AI = Cast<AAIController>(Agent->GetController()))
		{
			if (const UBlackboardComponent* BB = AI->GetBlackboardComponent())
			{
				if (BB->GetKeyID(PCSPBlackboard::DesiredActionType) != FBlackboard::InvalidKey)
				{
					CurrentAction = static_cast<EPCSPActionType>(BB->GetValueAsEnum(PCSPBlackboard::DesiredActionType));
				}
				if (BB->GetKeyID(PCSPBlackboard::UrgencyScore) != FBlackboard::InvalidKey)
				{
					CurrentUrgency = BB->GetValueAsFloat(PCSPBlackboard::UrgencyScore);
				}
			}
		}
		const int32 CurrentIndex = static_cast<int32>(CurrentAction);
		if (CurrentCounts.IsValidIndex(CurrentIndex)) { ++CurrentCounts[CurrentIndex]; }
		UrgencySum += CurrentUrgency;
		++UrgencySamples;

		if (const UPCSPTrajectoryLogComponent* Log = Agent->FindComponentByClass<UPCSPTrajectoryLogComponent>())
		{
			for (const FPCSPTrajectoryEntry& Entry : Log->GetRecentEvents(64))
			{
				if (Entry.EventType == EPCSPTrajectoryEvent::Decision)
				{
					++RunSnapshot.RecentDecisionCount;
				}
				else if (Entry.EventType == EPCSPTrajectoryEvent::MoveFailed
					|| Entry.EventType == EPCSPTrajectoryEvent::InteractionFailed)
				{
					++RunSnapshot.RecentFailureCount;
				}
			}
		}
	}
	for (TActorIterator<APCSPMassSpawner> It(World); It; ++It)
	{
		TArray<FPCSPMassAgentSnapshot> Snapshots;
		It->GetAllAgentSnapshots(Snapshots);
		RunSnapshot.AgentCount += Snapshots.Num();
		for (const FPCSPMassAgentSnapshot& Snapshot : Snapshots)
		{
			const int32 ActionIndex = static_cast<int32>(Snapshot.Action);
			if (CurrentCounts.IsValidIndex(ActionIndex)) { ++CurrentCounts[ActionIndex]; }
			float MinimumNeed = 1.f;
			for (const float Need : Snapshot.Needs) { MinimumNeed = FMath::Min(MinimumNeed, Need); }
			UrgencySum += 1.f - MinimumNeed;
			++UrgencySamples;
			RunSnapshot.RecentDecisionCount += Snapshot.RecentActions.Num();
		}
	}
	RunSnapshot.MeanUrgency = UrgencySamples > 0 ? UrgencySum / UrgencySamples : 0.f;

	if (AgentSnapshot.bMassEntity)
	{
		for (const FPCSPTrajectoryEntry& Entry : AgentSnapshot.RecentEvents)
		{
			const int32 Index = static_cast<int32>(Entry.Action);
			if (SelectedCounts.IsValidIndex(Index)) { ++SelectedCounts[Index]; }
		}
	}
	else if (DemoController && DemoController->GetObservedAgent())
	{
		if (const UPCSPTrajectoryLogComponent* Log =
			DemoController->GetObservedAgent()->FindComponentByClass<UPCSPTrajectoryLogComponent>())
		{
			for (const FPCSPTrajectoryEntry& Entry : Log->GetRecentEvents(64))
			{
				if (Entry.EventType != EPCSPTrajectoryEvent::Decision) { continue; }
				const int32 Index = static_cast<int32>(Entry.Action);
				if (SelectedCounts.IsValidIndex(Index)) { ++SelectedCounts[Index]; }
			}
		}
	}

	auto BuildDistribution = [](const TArray<int32>& Counts, TArray<FPCSPHudDistributionEntry>& Out)
	{
		int32 Total = 0;
		for (const int32 Count : Counts) { Total += Count; }
		for (int32 Index = 0; Index < Counts.Num(); ++Index)
		{
			if (Counts[Index] <= 0) { continue; }
			FPCSPHudDistributionEntry& Entry = Out.AddDefaulted_GetRef();
			Entry.Action = static_cast<EPCSPActionType>(Index);
			Entry.Label = UPCSPAgentDebugViewModel::ActionDisplayName(Entry.Action);
			Entry.Count = Counts[Index];
			Entry.Fraction = Total > 0 ? static_cast<float>(Entry.Count) / Total : 0.f;
			Entry.Color = ActionColor(Entry.Action);
		}
		Out.Sort([](const FPCSPHudDistributionEntry& Left, const FPCSPHudDistributionEntry& Right)
		{
			return Left.Count == Right.Count ? Left.Label < Right.Label : Left.Count > Right.Count;
		});
	};
	BuildDistribution(CurrentCounts, RunSnapshot.CurrentActionDistribution);
	BuildDistribution(SelectedCounts, RunSnapshot.SelectedActionDistribution);
}

void UPCSPDemoHUDWidgetBase::ApplyDefaultPresentation()
{
	const bool bMassPopulation = GetWorld() && TActorIterator<APCSPMassSpawner>(GetWorld());
	const FString FailureSummary = bMassPopulation ? TEXT("n/a")
		: FString::FromInt(RunSnapshot.RecentFailureCount);
	SetTextIfPresent(this, TEXT("T_RunSummary"), FString::Printf(
		TEXT("PCSP LIVE  |  %d agents  |  %d zones  |  urgency %.2f  |  failures %s"),
		RunSnapshot.AgentCount, RunSnapshot.ZoneCount, RunSnapshot.MeanUrgency,
		*FailureSummary));
	// The policy mode is the one run-level fact a viewer cannot infer from the
	// world: HybridPCSP and HybridNoPersona drive the same crowd from the same
	// model, and only the badge says which one is producing what is on screen.
	// Colour carries it at a glance — accent while personas are conditioning the
	// policy, warm while an ablation is running.
	if (PolicyBadgeText)
	{
		const bool bPersonaActive = AgentSnapshot.PolicyMode == EPCSPPolicyMode::HybridPCSP;
		const TCHAR* ModeLabel =
			AgentSnapshot.PolicyMode == EPCSPPolicyMode::BTOnly ? TEXT("BT ONLY  (no policy, no persona)")
			: AgentSnapshot.PolicyMode == EPCSPPolicyMode::HybridNoPersona ? TEXT("PERSONA OFF  (ablation)")
			: TEXT("PERSONA ON");
		// The ablation tag names the exported checkpoint, so a captured frame is
		// traceable back to the model that produced it.
		PolicyBadgeText->SetText(FText::FromString(FString::Printf(TEXT("%s   |   %s   |   P to cycle"),
			ModeLabel, *AgentSnapshot.ActiveAblation)));
		PolicyBadgeText->SetColorAndOpacity(FSlateColor(bPersonaActive
			? HudStyle::Accent : FLinearColor(1.f, 0.62f, 0.16f)));
	}
	// T_CameraMode and T_SelectionHint are collapsed in NativeConstruct: the camera
	// state is already on the follow button, and the shortcut list is static text
	// that only crowded the run badge.
	SetTextIfPresent(this, TEXT("T_CameraButtonLabel"), DemoController && DemoController->IsThirdPersonCameraActive()
		? TEXT("Exit Third Person") : TEXT("Follow in Third Person"));

	const bool bHasSelection = AgentSnapshot.PersonaId > 0;
	SetTextIfPresent(this, TEXT("T_PersonaID"), bHasSelection
		? (AgentSnapshot.bMassEntity
			? FString::Printf(TEXT("NPC #%04d  |  PERSONA #%03d"), AgentSnapshot.StableIndex, AgentSnapshot.PersonaId)
			: FString::Printf(TEXT("PERSONA #%03d"), AgentSnapshot.PersonaId))
		: TEXT("NO NPC SELECTED"));
	// The card is a fixed height, so an unbounded paragraph is what pushed the
	// description into the row below it. Trim on a word boundary instead.
	SetTextIfPresent(this, TEXT("T_PersonaText"), bHasSelection
		? ElideAtWord(AgentSnapshot.PersonaText, 260)
		: FString(TEXT("Click an NPC in the world.")));
	SetTextIfPresent(this, TEXT("T_ZoneTag"), AgentSnapshot.CurrentZoneTag.IsValid()
		? FString::Printf(TEXT("Zone  %s"), *ZoneTagLeaf(AgentSnapshot.CurrentZoneTag))
		: TEXT("Zone  -"));

	static const FName NeedBars[] = { TEXT("PB_Hunger"), TEXT("PB_Sleep"), TEXT("PB_Social"),
		TEXT("PB_Leisure"), TEXT("PB_Hygiene"), TEXT("PB_Fitness"), TEXT("PB_Work"), TEXT("PB_Learning") };
	static const FName NeedLabels[] = { TEXT("T_HungerLabel"), TEXT("T_SleepLabel"),
		TEXT("T_SocialLabel"), TEXT("T_LeisureLabel"), TEXT("T_HygieneLabel"),
		TEXT("T_FitnessLabel"), TEXT("T_WorkLabel"), TEXT("T_LearningLabel") };
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(NeedBars); ++Index)
	{
		if (UProgressBar* Bar = FindTypedWidget<UProgressBar>(NeedBars[Index]))
		{
			const float Value = AgentSnapshot.Needs.IsValidIndex(Index) ? AgentSnapshot.Needs[Index] : 0.f;
			Bar->SetPercent(FMath::Clamp(Value, 0.f, 1.f));
			HudStyle::StyleBar(*Bar, Value <= 0.2f ? FLinearColor(1.f, 0.28f, 0.20f)
				: Value <= 0.45f ? FLinearColor(1.f, 0.72f, 0.20f) : HudStyle::Accent);
			if (UHorizontalBoxSlot* BarSlot = Cast<UHorizontalBoxSlot>(Bar->Slot))
			{
				BarSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
				BarSlot->SetVerticalAlignment(VAlign_Center);
				BarSlot->SetPadding(FMargin(0.f, 3.f, 0.f, 3.f));
			}
		}
		// The authored need labels sit in the same row as their bar and were
		// overlapping it; pin them to their own auto-sized column.
		if (UWidget* NeedLabel = FindWidget(NeedLabels[Index]))
		{
			if (UHorizontalBoxSlot* LabelSlot = Cast<UHorizontalBoxSlot>(NeedLabel->Slot))
			{
				LabelSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
				LabelSlot->SetVerticalAlignment(VAlign_Center);
				LabelSlot->SetPadding(FMargin(0.f, 0.f, 10.f, 0.f));
			}
		}
	}

	SetTextIfPresent(this, TEXT("T_ObserveState"), bHasSelection
		? FString::Printf(TEXT("persona %03d / obs[33]"), AgentSnapshot.PersonaId) : TEXT("waiting"));
	SetTextIfPresent(this, TEXT("T_DecisionState"), UPCSPAgentDebugViewModel::ActionDisplayName(AgentSnapshot.DesiredAction));
	SetTextIfPresent(this, TEXT("T_AffordanceState"), FString::Printf(TEXT("%s / %.0f cm"),
		*UPCSPAgentDebugViewModel::CategoryDisplayName(AgentSnapshot.DesiredCategory), AgentSnapshot.DistanceToTarget));
	SetTextIfPresent(this, TEXT("T_InteractionState"), AgentSnapshot.bMassEntity
		? (AgentSnapshot.bMoving ? TEXT("moving / reserved")
			: AgentSnapshot.bInteracting ? TEXT("interacting") : TEXT("seeking free slot"))
		: AgentSnapshot.bAffordanceReserved ? TEXT("reserved / executing") : TEXT("seeking slot"));

	// Affordance panel: the place this NPC picked to satisfy its most urgent need,
	// how contested that place is, and how far it still has to walk. Every row now
	// names the state it is actually in, so "-" means "nothing chosen", not
	// "not implemented".
	const bool bHasZone = AgentSnapshot.CurrentZoneTag.IsValid();
	SetTextIfPresent(this, TEXT("T_AffordanceSummary"), !bHasSelection
		? TEXT("Target  -")
		: bHasZone
			? FString::Printf(TEXT("Target  %s  %s"),
				*UPCSPAgentDebugViewModel::CategoryDisplayName(AgentSnapshot.ZoneCategory),
				*ZoneTagLeaf(AgentSnapshot.CurrentZoneTag))
			: AgentSnapshot.bWanderingTarget ? TEXT("Target  strolling, no zone claimed")
			: TEXT("Target  choosing next affordance"));
	SetTextIfPresent(this, TEXT("T_Occupancy"), bHasZone && AgentSnapshot.ZoneCapacity > 0
		? FString::Printf(TEXT("Slots in use  %d / %d"),
			AgentSnapshot.ZoneOccupancy, AgentSnapshot.ZoneCapacity)
		: TEXT("Slots in use  -"));
	SetTextIfPresent(this, TEXT("T_Distance"), AgentSnapshot.DistanceToTarget >= 0.f
		? FString::Printf(TEXT("Distance  %.1f m  (%s)"), AgentSnapshot.DistanceToTarget / 100.f,
			AgentSnapshot.bInteracting ? TEXT("arrived")
			: AgentSnapshot.bMoving ? TEXT("walking") : TEXT("waiting"))
		: TEXT("Distance  -"));

	// Social panel: who else is inside this NPC's perception radius. Actor agents
	// carry a per-pair affinity ledger; crowd entities do not, so report the shared
	// activity that the crowd simulation does model rather than a placeholder.
	SetTextIfPresent(this, TEXT("T_SocialSummary"), !bHasSelection
		? TEXT("Nobody selected")
		: AgentSnapshot.bNearbyAffinityTracked
			? FString::Printf(TEXT("%d within %.0f m  |  affinity %+.2f"),
				AgentSnapshot.NearbyCount, AgentSnapshot.NearbyRadius / 100.f,
				AgentSnapshot.MeanAffinity)
			: FString::Printf(TEXT("%d within %.0f m  |  %d doing the same thing"),
				AgentSnapshot.NearbyCount, AgentSnapshot.NearbyRadius / 100.f,
				AgentSnapshot.NearbySameActivityCount));

	if (!PortfolioCanvas)
	{
	RebuildDistributionPanel(FindTypedWidget<UPanelWidget>(TEXT("VB_GlobalDistribution")),
		RunSnapshot.CurrentActionDistribution, 8);
	RebuildDistributionPanel(FindTypedWidget<UPanelWidget>(TEXT("VB_SelectedDistribution")),
		RunSnapshot.SelectedActionDistribution, 4);
	RebuildTrajectoryPanel(FindTypedWidget<UPanelWidget>(TEXT("VB_TrajectoryRows")));
	}
}

/**
 * Builds the policy badge on the HUD's own root canvas.
 *
 * It cannot live in an authored card: the only run-level card, WBP_PCSPSmallRunBadge,
 * is retired in RetiredHudPanels and collapsed wholesale, so any child of it is
 * invisible no matter what this class sets on it. Top-centre is the one region the
 * two rails leave free, and a mode banner is what belongs there.
 */
bool UPCSPDemoHUDWidgetBase::IsPolicyBadgeVisible() const
{
	if (PortfolioStatus && PortfolioCanvas && PortfolioCanvas->IsVisible())
	{
		return !PortfolioStatus->GetText().IsEmpty();
	}
	// The chip is the text block's parent border; both must be visible for the
	// badge to actually reach the screen.
	return PolicyBadgeText != nullptr
		&& PolicyBadgeText->GetParent() != nullptr
		&& PolicyBadgeText->GetParent()->IsVisible()
		&& !PolicyBadgeText->GetText().IsEmpty();
}

void UPCSPDemoHUDWidgetBase::BuildPolicyBadge()
{
	if (PolicyBadgeText) { return; }
	UCanvasPanel* Root = Cast<UCanvasPanel>(GetRootWidget());
	if (!Root) { return; }

	UBorder* Chip = WidgetTree->ConstructWidget<UBorder>();
	Chip->SetBrush(HudStyle::MakePanelBrush());
	Chip->SetPadding(FMargin(16.f, 7.f));
	Chip->SetVisibility(ESlateVisibility::HitTestInvisible);

	PolicyBadgeText = WidgetTree->ConstructWidget<UTextBlock>();
	SetCompactFont(PolicyBadgeText, HudStyle::TitleSize);
	PolicyBadgeText->SetColorAndOpacity(FSlateColor(HudStyle::Accent));
	PolicyBadgeText->SetJustification(ETextJustify::Center);
	Chip->AddChild(PolicyBadgeText);

	if (UCanvasPanelSlot* ChipSlot = Cast<UCanvasPanelSlot>(Root->AddChild(Chip)))
	{
		ChipSlot->SetAutoSize(true);
		ChipSlot->SetAnchors(FAnchors(0.5f, 0.f));
		ChipSlot->SetAlignment(FVector2D(0.5f, 0.f));
		ChipSlot->SetPosition(FVector2D(0.f, 20.f));
	}
}

void UPCSPDemoHUDWidgetBase::RebuildDistributionPanel(UPanelWidget* Panel,
	const TArray<FPCSPHudDistributionEntry>& Entries, int32 MaxRows)
{
	if (!Panel) { return; }
	Panel->ClearChildren();
	for (int32 Index = 0; Index < FMath::Min(MaxRows, Entries.Num()); ++Index)
	{
		const FPCSPHudDistributionEntry& Entry = Entries[Index];
		UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>();

		UTextBlock* Label = WidgetTree->ConstructWidget<UTextBlock>();
		SetCompactFont(Label, HudStyle::RowSize);
		Label->SetText(FText::FromString(Entry.Label.Left(20)));
		Label->SetColorAndOpacity(FSlateColor(HudStyle::TextPrimary));

		UProgressBar* Bar = WidgetTree->ConstructWidget<UProgressBar>();
		HudStyle::StyleBar(*Bar, Entry.Color);
		Bar->SetPercent(Entry.Fraction);
		USizeBox* BarBox = WidgetTree->ConstructWidget<USizeBox>();
		BarBox->SetHeightOverride(HudStyle::BarHeight);
		BarBox->AddChild(Bar);

		UTextBlock* Value = WidgetTree->ConstructWidget<UTextBlock>();
		SetCompactFont(Value, HudStyle::RowSize);
		Value->SetText(FText::FromString(FString::Printf(TEXT("%d   %.0f%%"),
			Entry.Count, Entry.Fraction * 100.f)));
		Value->SetColorAndOpacity(FSlateColor(HudStyle::TextSecondary));
		Value->SetJustification(ETextJustify::Right);

		// Proportional columns keep label, bar, and count aligned down the list. The
		// previous single "%-18s %2d" string padded a proportional font, so nothing
		// lined up and the count crowded the label.
		FSlateChildSize LabelSize(ESlateSizeRule::Fill);
		LabelSize.Value = 0.46f;
		FSlateChildSize BarSize(ESlateSizeRule::Fill);
		BarSize.Value = 0.36f;
		FSlateChildSize ValueSize(ESlateSizeRule::Fill);
		ValueSize.Value = 0.18f;

		UHorizontalBoxSlot* LabelSlot = Row->AddChildToHorizontalBox(Label);
		LabelSlot->SetSize(LabelSize);
		LabelSlot->SetVerticalAlignment(VAlign_Center);
		UHorizontalBoxSlot* BarSlot = Row->AddChildToHorizontalBox(BarBox);
		BarSlot->SetSize(BarSize);
		BarSlot->SetVerticalAlignment(VAlign_Center);
		BarSlot->SetPadding(FMargin(8.f, 0.f, 8.f, 0.f));
		UHorizontalBoxSlot* ValueSlot = Row->AddChildToHorizontalBox(Value);
		ValueSlot->SetSize(ValueSize);
		ValueSlot->SetVerticalAlignment(VAlign_Center);

		if (UPanelSlot* RowSlot = Panel->AddChild(Row))
		{
			if (UVerticalBoxSlot* VerticalSlot = Cast<UVerticalBoxSlot>(RowSlot))
			{
				VerticalSlot->SetPadding(FMargin(0.f, 2.f, 0.f, 2.f));
			}
		}
	}
}

void UPCSPDemoHUDWidgetBase::RebuildTrajectoryPanel(UPanelWidget* Panel)
{
	if (!Panel) { return; }
	Panel->ClearChildren();
	if (AgentSnapshot.RecentEvents.IsEmpty())
	{
		// An empty card reads as broken rather than as "nothing selected yet".
		UTextBlock* Empty = WidgetTree->ConstructWidget<UTextBlock>();
		SetCompactFont(Empty, HudStyle::RowSize);
		Empty->SetText(FText::FromString(AgentSnapshot.PersonaId > 0
			? TEXT("No decisions recorded yet.")
			: TEXT("Select an NPC to see its decisions.")));
		Empty->SetColorAndOpacity(FSlateColor(HudStyle::TextSecondary));
		Panel->AddChild(Empty);
		return;
	}
	for (const FPCSPTrajectoryEntry& Entry : AgentSnapshot.RecentEvents)
	{
		UTextBlock* Text = WidgetTree->ConstructWidget<UTextBlock>();
		SetCompactFont(Text, HudStyle::RowSize);
		const FString EventText = AgentSnapshot.bMassEntity
			? FString::Printf(TEXT("%6.1fs  %s"), Entry.TimeSeconds,
				*UPCSPAgentDebugViewModel::ActionDisplayName(Entry.Action))
			: FString::Printf(TEXT("%6.1fs  %s  %s  r=%+.2f"), Entry.TimeSeconds,
				*UPCSPAgentDebugViewModel::EventDisplayName(Entry.EventType),
				*UPCSPAgentDebugViewModel::ActionDisplayName(Entry.Action), Entry.Reward);
		Text->SetText(FText::FromString(EventText));
		Text->SetColorAndOpacity(FSlateColor(Entry.EventType == EPCSPTrajectoryEvent::InteractionComplete
			? FLinearColor(0.2f, 1.f, 0.45f) : Entry.EventType == EPCSPTrajectoryEvent::Decision
			? FLinearColor(1.f, 0.75f, 0.2f) : FLinearColor(1.f, 0.25f, 0.2f)));
		Panel->AddChild(Text);
	}
}

bool UPCSPDemoHUDWidgetBase::GetSelectionMarkerAnchor(FVector2D& OutLocalPosition) const
{
	if (AgentSnapshot.PersonaId <= 0 || !DemoController) { return false; }
	const float VisualScale = DemoController->GetObservedAgentVisualScale();
	const FVector Above = AgentSnapshot.AgentLocation
		+ FVector(0.f, 0.f, FMath::Max(0.f, SelectionMarkerHeight) * VisualScale);
	FVector2D Screen;
	// bPlayerViewportRelative=false keeps this in viewport pixels, which the DPI
	// scale converts to the widget-local space the paint geometry expects.
	if (!UGameplayStatics::ProjectWorldToScreen(DemoController, Above, Screen, false))
	{
		return false;
	}
	const float ViewportScale = UWidgetLayoutLibrary::GetViewportScale(this);
	OutLocalPosition = Screen / FMath::Max(KINDA_SMALL_NUMBER, ViewportScale);
	return true;
}

/**
 * Draws the selection arrow over the inspected NPC. It is painted rather than
 * built from widgets because it has to follow a projected world position every
 * frame; a widget in a canvas slot would only move at the 10 Hz refresh.
 */
int32 UPCSPDemoHUDWidgetBase::NativePaint(const FPaintArgs& Args,
	const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
	FSlateWindowElementList& OutDrawElements, int32 LayerId,
	const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	int32 MaxLayer = Super::NativePaint(Args, AllottedGeometry, MyCullingRect,
		OutDrawElements, LayerId, InWidgetStyle, bParentEnabled);
	MaxLayer = PaintAnalytics(AllottedGeometry, OutDrawElements, MaxLayer);
	if (bShowPerformance) { return MaxLayer; }

	FVector2D Anchor;
	if (!GetSelectionMarkerAnchor(Anchor)) { return MaxLayer; }

	// A slow bob reads as "this one" against a crowd that is itself moving; a
	// pinned glyph reads as a UI artifact stuck to the screen.
	const UWorld* World = GetWorld();
	const float Time = World ? World->GetTimeSeconds() : 0.f;
	Anchor.Y -= 4.f + FMath::Sin(Time * 3.2f) * 4.f;

	const FPaintGeometry Geometry = AllottedGeometry.ToPaintGeometry();
	const TArray<FVector2D> Head = {
		Anchor + FVector2D(-13.f, -18.f), Anchor, Anchor + FVector2D(13.f, -18.f) };
	const TArray<FVector2D> Shaft = {
		Anchor + FVector2D(0.f, -44.f), Anchor + FVector2D(0.f, -8.f) };

	// Dark pass underneath: the district has both bright plazas and dark interiors,
	// and a single green stroke disappears into one of them.
	const FLinearColor Shadow(0.f, 0.f, 0.f, 0.55f);
	FSlateDrawElement::MakeLines(OutDrawElements, MaxLayer + 1, Geometry, Head,
		ESlateDrawEffect::None, Shadow, true, 9.f);
	FSlateDrawElement::MakeLines(OutDrawElements, MaxLayer + 1, Geometry, Shaft,
		ESlateDrawEffect::None, Shadow, true, 8.f);
	FSlateDrawElement::MakeLines(OutDrawElements, MaxLayer + 2, Geometry, Head,
		ESlateDrawEffect::None, SelectionMarkerColor, true, 5.f);
	FSlateDrawElement::MakeLines(OutDrawElements, MaxLayer + 2, Geometry, Shaft,
		ESlateDrawEffect::None, SelectionMarkerColor, true, 4.f);
	return MaxLayer + 2;
}

UWidget* UPCSPDemoHUDWidgetBase::FindWidgetRecursive(FName Name) const
{
	if (!WidgetTree) { return nullptr; }
	if (UWidget* Direct = WidgetTree->FindWidget(Name)) { return Direct; }

	TArray<UWidget*> Widgets;
	WidgetTree->GetAllWidgets(Widgets);
	for (UWidget* Widget : Widgets)
	{
		if (UUserWidget* Child = Cast<UUserWidget>(Widget))
		{
			if (Child->WidgetTree)
			{
				if (UWidget* Nested = Child->WidgetTree->FindWidget(Name)) { return Nested; }
			}
		}
	}
	return nullptr;
}
