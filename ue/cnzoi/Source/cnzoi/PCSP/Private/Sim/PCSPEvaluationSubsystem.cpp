#include "Sim/PCSPEvaluationSubsystem.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

float FPCSPEvaluationResult::P95() const
{
	if (FrameTimes.IsEmpty()) { return 0.f; }
	if (CachedP95Count == FrameTimes.Num()) { return CachedP95; }
	TArray<float> Sorted = FrameTimes;
	Sorted.Sort();
	CachedP95Count = FrameTimes.Num();
	CachedP95 = Sorted[FMath::Clamp(FMath::CeilToInt(Sorted.Num() * 0.95f) - 1, 0, Sorted.Num() - 1)];
	return CachedP95;
}

float FPCSPEvaluationResult::Entropy() const
{
	double Total = 0, H = 0;
	for (const auto& Entry : Actions) { Total += Entry.Value; }
	if (Total <= 0) { return 0; }
	for (const auto& Entry : Actions)
	{
		const double P = Entry.Value / Total;
		if (P > 0) { H -= P * FMath::Log2(P); }
	}
	return H;
}

void UPCSPEvaluationSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	NewSeries();
	int32 RequestedAxis = -1;
	if (FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalAxis="), RequestedAxis))
	{
		Axis = FMath::Clamp(RequestedAxis, 0, 2);
		FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalVariant="), Variant);
		Variant = FMath::Clamp(Variant, 0, VariantCount() - 1);
		Count = Axis == 1 ? 64 : 1024;
		FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalCount="), Count);
		Count = FMath::Clamp(Count, 1, Axis == 1 ? 128 : 4096);
		FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalSeed="), Seed);
		FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalSeconds="), DurationSeconds);
		DurationSeconds = FMath::Clamp(DurationSeconds, 2.f, 600.f);
		FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalWarmup="), WarmupSeconds);
		WarmupSeconds = FMath::Clamp(WarmupSeconds, 1.f, 120.f);
		bConfigured = bShowHUD = true;
		FString RequestedSeries;
		if (FParse::Value(FCommandLine::Get(), TEXT("PCSP_EvalSeries="), RequestedSeries))
		{
			FGuid Parsed;
			if (FGuid::ParseExact(RequestedSeries, EGuidFormats::Digits, Parsed)) { Series = RequestedSeries; }
		}
		ApplyPolicySettings();
	}
}

FString UPCSPEvaluationSubsystem::AxisName(int32 Value)
{
	return Value == 0 ? TEXT("1. Persona effect") : Value == 1 ? TEXT("2. Execution architecture") : TEXT("3. Inference optimization");
}

FString UPCSPEvaluationSubsystem::VariantName(int32 InAxis, int32 InVariant)
{
	if (InAxis == 0) { return InVariant == 0 ? TEXT("PCSP / Persona") : InVariant == 1 ? TEXT("Needs heuristic") : TEXT("No Persona"); }
	if (InAxis == 1) { return InVariant == 0 ? TEXT("Actor + BT") : TEXT("Mass"); }
	return InVariant == 0 ? TEXT("Individual sync") : TEXT("Batch / async");
}

EPCSPPolicyMode UPCSPEvaluationSubsystem::PolicyMode() const
{
	return Axis == 0 && Variant == 1 ? EPCSPPolicyMode::BTOnly
		: Axis == 0 && Variant == 2 ? EPCSPPolicyMode::HybridNoPersona : EPCSPPolicyMode::HybridPCSP;
}

void UPCSPEvaluationSubsystem::ApplyPolicySettings() const
{
	if (!bConfigured) { return; }
	IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.PolicyMode"))->Set(static_cast<int32>(PolicyMode()), ECVF_SetByConsole);
	IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.AsyncInference"))->Set(AsyncMode(), ECVF_SetByConsole);
}

void UPCSPEvaluationSubsystem::NewSeries()
{
	Series = FGuid::NewGuid().ToString(EGuidFormats::Digits);
	AxisSeries.Add(Axis, Series);
	AxisCameras.Remove(Axis);
	bHasCamera = false;
}

void UPCSPEvaluationSubsystem::SelectAxis(int32 NewAxis)
{
	if (Axis == NewAxis) { return; }
	AxisSeries.Add(Axis, Series);
	AxisCounts.Add(Axis, Count);
	AxisSeeds.Add(Axis, Seed);
	if (bHasCamera) { AxisCameras.Add(Axis, FTransform(CameraRotation, CameraLocation)); AxisFOVs.Add(Axis, CameraFOV); }
	Axis = FMath::Clamp(NewAxis, 0, 2);
	Variant = 0;
	Count = AxisCounts.Contains(Axis) ? AxisCounts[Axis] : Axis == 1 ? 64 : 1024;
	Seed = AxisSeeds.Contains(Axis) ? AxisSeeds[Axis] : 17;
	// Selecting a tab never mutates the running policy or world.
	bConfigured = false;
	if (AxisSeries.Contains(Axis)) { Series = AxisSeries[Axis]; } else { NewSeries(); }
	bHasCamera = AxisCameras.Contains(Axis);
	if (bHasCamera) { CameraLocation = AxisCameras[Axis].GetLocation(); CameraRotation = AxisCameras[Axis].Rotator(); CameraFOV = AxisFOVs[Axis]; }
	Status = TEXT("Choose a variant to restart and record.");
}

void UPCSPEvaluationSubsystem::CycleCount()
{
	const int32 Values[] = {16, 64, 128, 256, 1024};
	int32 Next = 16;
	for (int32 Value : Values) { if (Value > Count && (Axis != 1 || Value <= 128)) { Next = Value; break; } }
	Count = Next;
	bConfigured = false;
	NewSeries();
	Status = TEXT("Population changed. Choose a variant to start a new comparison.");
}

void UPCSPEvaluationSubsystem::CycleSeed()
{
	Seed = (Seed + 1) % 1000;
	bConfigured = false;
	NewSeries();
	Status = TEXT("Seed changed. Choose a variant to start a new comparison.");
}

void UPCSPEvaluationSubsystem::StartVariant(int32 NewVariant)
{
	if (!GetWorld() || NewVariant < 0 || NewVariant >= VariantCount()) { return; }
	if (!bHasCamera)
	{
		if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
		{
			PC->GetPlayerViewPoint(CameraLocation, CameraRotation);
			CameraFOV = PC->PlayerCameraManager ? PC->PlayerCameraManager->GetFOVAngle() : 90.f;
			bHasCamera = true;
		}
	}
	Variant = NewVariant;
	bConfigured = bShowHUD = true;
	Status = TEXT("Restarting world...");
	// Apply only in the destination world's OnWorldBeginPlay, after the old run closes.
	UGameplayStatics::OpenLevel(GetWorld(), FName(*UGameplayStatics::GetCurrentLevelName(GetWorld(), true)));
}

const FPCSPEvaluationResult* UPCSPEvaluationSubsystem::Latest(int32 ForVariant) const
{
	for (int32 I = Results.Num() - 1; I >= 0; --I)
	{
		if (Results[I].Series == Series && Results[I].Axis == Axis && Results[I].Variant == ForVariant) { return &Results[I]; }
	}
	return nullptr;
}

void UPCSPEvaluationSubsystem::SaveResult(const FPCSPEvaluationResult& Result)
{
	for (FPCSPEvaluationResult& Existing : Results)
	{
		if (Existing.Run == Result.Run) { Existing = Result; return; }
	}
	if (Results.Num() >= 30) { Results.RemoveAt(0); }
	Results.Add(Result);
}
