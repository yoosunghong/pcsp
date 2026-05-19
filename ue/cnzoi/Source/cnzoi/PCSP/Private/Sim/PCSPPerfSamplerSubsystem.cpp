#include "PCSPPerfSamplerSubsystem.h"
#include "PCSPTrajectoryLogComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Stats/Stats.h"
#include "Containers/Ticker.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

// T1.3 sweep auto-quit. When set to a positive value, the engine requests a
// clean exit that many seconds after OnWorldBeginPlay. Lets a single batch
// script drive 18 unattended PIE/standalone runs end-to-end.
static TAutoConsoleVariable<float> CVarPCSPRunDurationSeconds(
	TEXT("pcsp.RunDurationSeconds"), -1.0f,
	TEXT("Auto-quit this many seconds after world begin play (-1 = never)."),
	ECVF_Default);

void UPCSPPerfSamplerSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	// Only sample in PIE / standalone game worlds — skip editor preview, asset thumbs, etc.
	const EWorldType::Type WT = InWorld.WorldType;
	if (WT != EWorldType::PIE && WT != EWorldType::Game) { return; }

	LogFilePath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("frame_stats.jsonl");
	WindowMs.Reserve(256);
	bSampling = true;

	InWorld.GetTimerManager().SetTimer(FlushTimerHandle, this,
		&UPCSPPerfSamplerSubsystem::FlushWindow,
		/*InRate=*/1.0f, /*InbLoop=*/true, /*InFirstDelay=*/1.0f);

	float Duration = CVarPCSPRunDurationSeconds.GetValueOnGameThread();
	// Cmdline switch wins (CVars set via -ExecCmds may arrive after BeginPlay).
	float CmdDuration = -1.0f;
	if (FParse::Value(FCommandLine::Get(), TEXT("PCSP_RunDurationSeconds="), CmdDuration))
	{
		Duration = CmdDuration;
	}
	if (Duration > 0.0f)
	{
		UE_LOG(LogTemp, Log,
			TEXT("PCSPPerfSampler: auto-quit scheduled in %.1f s (pcsp.RunDurationSeconds)"),
			Duration);
		// Use the core ticker (not world TimerManager) so auto-quit fires even if
		// the world is paused — e.g. the standalone game window starts unfocused
		// and pause-on-focus-loss kicks in, which freezes world timers.
		FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateLambda([](float /*DeltaTime*/) -> bool
			{
				UE_LOG(LogTemp, Log, TEXT("PCSPPerfSampler: requesting exit (auto-quit fired)"));
				FPlatformMisc::RequestExit(/*Force=*/false);
				return false; // one-shot
			}),
			Duration);
	}
}

void UPCSPPerfSamplerSubsystem::Deinitialize()
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(FlushTimerHandle);
	}
	bSampling = false;
	Super::Deinitialize();
}

void UPCSPPerfSamplerSubsystem::Tick(float DeltaTime)
{
	if (!bSampling) { return; }
	WindowMs.Add(DeltaTime * 1000.f);
}

TStatId UPCSPPerfSamplerSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UPCSPPerfSamplerSubsystem, STATGROUP_Tickables);
}

void UPCSPPerfSamplerSubsystem::FlushWindow()
{
	if (WindowMs.Num() == 0 || LogFilePath.IsEmpty()) { return; }

	TArray<float> Sorted = WindowMs;
	Sorted.Sort();
	const int32 N = Sorted.Num();
	const auto Percentile = [&](float P) -> float
	{
		const int32 Idx = FMath::Clamp(FMath::FloorToInt(P * N), 0, N - 1);
		return Sorted[Idx];
	};

	double SumMs = 0.0;
	for (float V : WindowMs) { SumMs += V; }
	const float MeanMs = static_cast<float>(SumMs / N);

	const float T = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	const FString Line = FString::Printf(
		TEXT("{\"t\":%.3f,\"n_samples\":%d,\"mean_ms\":%.3f,\"p50_ms\":%.3f,\"p95_ms\":%.3f,\"p99_ms\":%.3f}\n"),
		T, N, MeanMs, Percentile(0.50f), Percentile(0.95f), Percentile(0.99f));

	const uint32 Flags = FILEWRITE_Append | FILEWRITE_AllowRead;
	FFileHelper::SaveStringToFile(Line, *LogFilePath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), Flags);

	WindowMs.Reset();
}
