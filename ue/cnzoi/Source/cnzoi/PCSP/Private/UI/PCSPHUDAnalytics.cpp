#include "UI/PCSPDemoHUDWidgetBase.h"
#include "Sim/PCSPPerfSamplerSubsystem.h"
#include "Blueprint/WidgetLayoutLibrary.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"

int32 UPCSPDemoHUDWidgetBase::PaintAnalytics(const FGeometry& Geometry,
	FSlateWindowElementList& Elements, int32 Layer) const
{
	if (!PortfolioCanvas || !GetWorld()) { return Layer; }
	const FVector2D Pixels = UWidgetLayoutLibrary::GetViewportSize(this);
	const float DPI = FMath::Max(0.1f, UWidgetLayoutLibrary::GetViewportScale(this));
	const FLinearColor White(0.90f, 0.94f, 0.98f);
	const FLinearColor Muted(0.60f, 0.68f, 0.76f);
	const FSlateBrush* Brush = FCoreStyle::Get().GetBrush(TEXT("WhiteBrush"));
	auto Box = [&](float X, float Y, float W, float H, FLinearColor Color)
	{
		FSlateDrawElement::MakeBox(Elements, Layer + 1,
			Geometry.ToPaintGeometry(FVector2D(W, H) / DPI, FSlateLayoutTransform(FVector2D(X, Y) / DPI)),
			Brush, ESlateDrawEffect::None, Color);
	};
	auto Text = [&](float X, float Y, const FString& Value, FLinearColor Color, int32 Size = 12)
	{
		const FSlateFontInfo Font = FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), FMath::RoundToInt(Size / DPI));
		FSlateDrawElement::MakeText(Elements, Layer + 2,
			Geometry.ToPaintGeometry(FVector2D(1.f, 1.f), FSlateLayoutTransform(FVector2D(X, Y) / DPI)),
			Value, Font, ESlateDrawEffect::None, Color);
	};
	if (!bShowPerformance)
	{
		const float W = FMath::Clamp(Pixels.X * 0.29f, 280.f, 370.f);
		const float X = Pixels.X - W - 20.f;
		const float Y = bShowDetails ? 64.f : Pixels.Y - 264.f;
		const float H = bShowDetails ? FMath::Clamp(Pixels.Y - 136.f, 180.f, 680.f) : 192.f;
		Box(X, Y, W, H, FLinearColor(0.018f, 0.025f, 0.04f, 0.95f));
		Text(X + 12.f, Y + 10.f, bShowDetails ? TEXT("ALL NPC ACTIONS / expanded") : TEXT("ALL NPC ACTIONS / live"), White);
		const int32 Count = RunSnapshot.CurrentActionDistribution.Num();
		const int32 Visible = bShowDetails ? Count : FMath::Min(5, Count);
		const float RowHeight = bShowDetails ? FMath::Min(27.f, (H - 57.f) / FMath::Max(1, Count)) : 22.f;
		auto Row = [&](int32 Index, const FString& Label, int32 N, float Fraction, FLinearColor Color)
		{
			const float RowY = Y + 38.f + Index * RowHeight;
			Text(X + 12.f, RowY, Label, White, 10);
			const float BarX = X + 146.f;
			const float BarW = FMath::Max(20.f, W - 207.f);
			Box(BarX, RowY + 4.f, BarW, 8.f, FLinearColor(0.12f, 0.15f, 0.19f));
			Box(BarX, RowY + 4.f, BarW * FMath::Clamp(Fraction, 0.f, 1.f), 8.f, Color);
			Text(X + W - 54.f, RowY, FString::Printf(TEXT("%.0f%%"), Fraction * 100.f), Color, 10);
		};
		int32 Shown = 0;
		for (int32 Index = 0; Index < Visible; ++Index)
		{
			const FPCSPHudDistributionEntry& Entry = RunSnapshot.CurrentActionDistribution[Index];
			Row(Index, Entry.Label, Entry.Count, Entry.Fraction, Entry.Color);
			Shown += Entry.Count;
		}
		if (!bShowDetails && Count > Visible)
		{
			const int32 Others = RunSnapshot.AgentCount - Shown;
			Row(Visible, TEXT("Other actions"), Others,
				RunSnapshot.AgentCount > 0 ? static_cast<float>(Others) / RunSnapshot.AgentCount : 0.f, Muted);
		}
		if (Count == 0) { Text(X + 12.f, Y + 43.f, TEXT("Waiting for NPCs..."), Muted); }
		Text(X + 12.f, Y + H - 20.f, FString::Printf(TEXT("%d NPCs  |  100%% scale  |  Details expands"), RunSnapshot.AgentCount), Muted, 10);
		return Layer + 2;
	}

	const UPCSPPerfSamplerSubsystem* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>();
	if (!Perf) { return Layer; }
	const float W = FMath::Min(Pixels.X - 40.f, 1100.f);
	const float X = (Pixels.X - W) * 0.5f;
	const auto* Eval = GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
	if (!Eval) { return Layer; }
	const FLinearColor Colors[] = {FLinearColor(0.15f, 0.80f, 1.f), FLinearColor(1.f, 0.68f, 0.16f), FLinearColor(0.85f, 0.4f, 1.f)};
	Text(X + 20.f, 168.f, UPCSPEvaluationSubsystem::AxisName(Eval->Axis) + TEXT("  |  ")
		+ (Eval->Status.IsEmpty() ? TEXT("Choose a variant; each button restarts the world.") : Eval->Status), White, 11);
	const TCHAR* Purpose = Eval->Axis == 0 ? TEXT("Mass fixed / compare persona-conditioned decisions and added cost")
		: Eval->Axis == 1 ? TEXT("PCSP sync fixed / compare complete Actor+BT and Mass execution stacks")
		: TEXT("Mass + PCSP fixed / compare individual sync and batched worker inference");
	Text(X + 20.f, 189.f, Purpose, Muted, 11);
	const float Col[] = {20.f, W * 0.23f, W * 0.36f, W * 0.47f, W * 0.59f, W * 0.71f, W * 0.85f};
	const TCHAR* Headers[] = {TEXT("Variant"), TEXT("Status"), TEXT("Seconds"), TEXT("CPU avg"), TEXT("FPS avg"), TEXT("p95 frame ms"), TEXT("Policy us/dec")};
	for (int32 Column = 0; Column < 7; ++Column) { Text(X + Col[Column], 215.f, Headers[Column], Muted, 10); }
	double MaxElapsed = 10.0;
	float MaxFPS = 60.f;
	for (int32 Index = 0; Index < Eval->VariantCount(); ++Index)
	{
		const float Y = 241.f + Index * 42.f;
		Text(X + Col[0], Y, UPCSPEvaluationSubsystem::VariantName(Eval->Axis, Index), Colors[Index], 11);
		const FPCSPEvaluationResult* Run = Eval->Latest(Index);
		if (!Run || Run->Seconds <= 0.0)
		{
			Text(X + Col[1], Y, Run ? TEXT("Waiting") : TEXT("Not recorded"), Muted, 10);
			continue;
		}
		Text(X + Col[1], Y, Run->bComplete ? TEXT("Complete") : !Run->InvalidReason.IsEmpty() ? TEXT("Incomplete") : TEXT("Recording"), White, 10);
		Text(X + Col[2], Y, FString::Printf(TEXT("%.1f"), Run->Seconds), White, 11);
		Text(X + Col[3], Y, Run->CPU() >= 0.f ? FString::Printf(TEXT("%.1f%%"), Run->CPU()) : TEXT("N/A"), White, 11);
		Text(X + Col[4], Y, FString::Printf(TEXT("%.1f"), Run->FPS()), White, 11);
		Text(X + Col[5], Y, FString::Printf(TEXT("%.2f"), Run->P95()), White, 11);
		Text(X + Col[6], Y, Run->Decisions > 0 ? FString::Printf(TEXT("%.1f"), Run->PolicyMicros / Run->Decisions) : TEXT("N/A"), White, 11);
		Text(X + 20.f, Y + 19.f, Eval->Axis == 2
			? FString::Printf(TEXT("%.1f decisions/s | sync %lld / worker %lld | result latency %.2f ms | inference failures %lld"),
				Run->Decisions / Run->Seconds, Run->Decisions - Run->WorkerDecisions, Run->WorkerDecisions,
				Run->Decisions > 0 ? Run->LatencyMicros / Run->Decisions / 1000.0 : 0, Run->Failures)
			: FString::Printf(TEXT("%.1f decisions/s | action entropy %.2f bits | result latency %.2f ms | inference failures %lld"),
				Run->Decisions / Run->Seconds, Run->Entropy(), Run->Decisions > 0 ? Run->LatencyMicros / Run->Decisions / 1000.0 : 0, Run->Failures), Muted, 9);
		for (const FVector& Point : Run->Plot)
		{
			MaxElapsed = FMath::Max(MaxElapsed, Point.X);
			MaxFPS = FMath::Max(MaxFPS, static_cast<float>(Point.Z));
		}
	}
	MaxElapsed = FMath::CeilToDouble(MaxElapsed / 10.0) * 10.0;
	MaxFPS = FMath::CeilToFloat(MaxFPS / 30.f) * 30.f;
	const float ChartHeight = FMath::Max(60.f, (Pixels.Y - 555.f) * 0.5f);
	auto Chart = [&](float Top, bool bCPU)
	{
		Text(X + 20.f, Top, bCPU ? TEXT("PROCESS CPU % / all logical cores = 100%") : TEXT("FPS / wall-clock frames per second"), White);
		const float Left = X + 56.f, Right = X + W - 28.f;
		const float PlotTop = Top + 26.f, PlotBottom = PlotTop + ChartHeight - 30.f;
		const float Ceiling = bCPU ? 100.f : MaxFPS;
		Box(Left, PlotTop, Right - Left, PlotBottom - PlotTop, FLinearColor(0.01f, 0.015f, 0.024f, 1.f));
		for (int32 Grid = 0; Grid <= 2; ++Grid)
		{
			const float Y = FMath::Lerp(PlotBottom, PlotTop, Grid * 0.5f);
			Box(Left, Y, Right - Left, 1.f, FLinearColor(0.16f, 0.20f, 0.25f, 1.f));
			Text(X + 14.f, Y - 8.f, FString::Printf(TEXT("%.0f"), Ceiling * Grid * 0.5f), Muted, 10);
		}
		for (int32 Index = 0; Index < Eval->VariantCount(); ++Index)
		{
			const FPCSPEvaluationResult* Run = Eval->Latest(Index);
			if (!Run) { continue; }
			TArray<FVector2D> Points;
			for (const FVector& Point : Run->Plot)
			{
				const float Value = bCPU ? Point.Y : Point.Z;
				if (Value < 0.f) { continue; }
				Points.Add(FVector2D(FMath::Lerp(Left, Right, Point.X / MaxElapsed),
					FMath::Lerp(PlotBottom, PlotTop, FMath::Clamp(Value / Ceiling, 0.f, 1.f))) / DPI);
			}
			if (Points.Num() >= 2) { FSlateDrawElement::MakeLines(Elements, Layer + 2, Geometry.ToPaintGeometry(), Points, ESlateDrawEffect::None, Colors[Index], true, 2.f); }
			if (!Points.IsEmpty()) { const FVector2D Last = Points.Last() * DPI; Box(Last.X - 2.f, Last.Y - 2.f, 4.f, 4.f, Colors[Index]); }
		}
		Text(Left, PlotBottom + 5.f, TEXT("0s"), Muted, 10);
		Text((Left + Right) * 0.5f - 115.f, PlotBottom + 5.f, TEXT("Elapsed seconds after warm-up"), Muted, 10);
		Text(Right - 42.f, PlotBottom + 5.f, FString::Printf(TEXT("%.0fs"), MaxElapsed), Muted, 10);
	};
	if (Pixels.Y >= 690.f) { Chart(373.f, true); Chart(373.f + ChartHeight + 28.f, false); }
	const float FooterY = Pixels.Y - 133.f;
	Text(X + 20.f, FooterY, Eval->Axis == 0 ? TEXT("Entropy describes choices, not persona fidelity. Per-persona counts exported; inspect trajectories for quality.")
		: Eval->Axis == 1 ? TEXT("Whole stacks differ in spawn, rendering and movement. This does not isolate BT overhead.")
		: TEXT("Policy time: sync call or amortized worker batch. Latency includes result wait; live inputs can diverge."), Muted, 10);
	const IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync"));
	const IConsoleVariable* Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"));
	Text(X + 20.f, FooterY + 19.f, FString::Printf(TEXT("%s | VSync %s | FPS cap %.0f | %s"),
		GetWorld()->WorldType == EWorldType::PIE ? TEXT("CPU includes Editor") : TEXT("Whole game process"),
		VSync && VSync->GetInt() != 0 ? TEXT("on") : TEXT("off"), Cap ? Cap->GetFloat() : 0.f,
		Perf->HasWriteError() ? TEXT("CSV WRITE FAILED") : TEXT("CSV + JSON: Saved/PCSP/Evaluation/<series>/")),
		Perf->HasWriteError() ? Colors[1] : Muted, 10);
	Text(X + 20.f, FooterY + 38.f, TEXT("Fresh world per variant. Same seed / count / camera; repeat seeds for claims. No automatic FPS speedup claim."), Muted, 10);
	if (Eval->Axis == 2 && !Eval->ReplayStatus.IsEmpty()) { Text(X + 20.f, 335.f, Eval->ReplayStatus, Colors[0], 10); }
	return Layer + 2;
}
