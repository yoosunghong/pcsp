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
#include "HAL/PlatformTime.h"
#include "Mass/PCSPMassSpawner.h"
#include "Agent/PCSPAgentCharacter.h"
#include "EngineUtils.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

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

	BeginEvaluation();
	LogFilePath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("frame_stats.jsonl");
	WindowMs.Reserve(256);
	bSampling = true;
	ComparisonPath = UPCSPTrajectoryLogComponent::GetSessionDir()
		/ FString::Printf(TEXT("mode_performance_%s.csv"), *FGuid::NewGuid().ToString(EGuidFormats::Digits));
	AppendComparisonCSV(TEXT("run,mode,elapsed_s,window_s,frames,process_cpu_pct,fps,mean_frame_ms,world_type,npc_count,width,height,vsync,fps_cap\n"));
	BeginComparisonRun(UPCSPPolicySubsystem::GetPolicyMode(), FPlatformTime::Seconds());

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
	FinishEvaluation(false);
	if (bSampling && WarmupRemaining() <= 0.f) { FlushComparison(FPlatformTime::Seconds()); }
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
	TickEvaluation(FPlatformTime::Seconds());
	TickComparison(FPlatformTime::Seconds());
}

double UPCSPPerfSamplerSubsystem::ReadProcessCPUSeconds()
{
#if PLATFORM_WINDOWS
	FILETIME Created, Exited, Kernel, User;
	if (::GetProcessTimes(::GetCurrentProcess(), &Created, &Exited, &Kernel, &User))
	{
		const uint64 K = (static_cast<uint64>(Kernel.dwHighDateTime) << 32) | Kernel.dwLowDateTime;
		const uint64 U = (static_cast<uint64>(User.dwHighDateTime) << 32) | User.dwLowDateTime;
		return static_cast<double>(K + U) * 1.e-7;
	}
#endif
	return -1.0;
}

FPCSPPerfPoint UPCSPPerfSamplerSubsystem::MakePoint(double Elapsed, double Seconds,
	int32 Frames, double CPUSeconds, int32 LogicalCores)
{
	FPCSPPerfPoint Point;
	Point.Elapsed = Elapsed;
	Point.Seconds = Seconds;
	Point.Frames = Frames;
	if (Seconds <= 0.0 || Frames <= 0) { return Point; }
	Point.FPS = Frames / Seconds;
	Point.FrameMs = Seconds * 1000.0 / Frames;
	if (CPUSeconds >= 0.0 && LogicalCores > 0)
	{
		Point.CPU = FMath::Clamp(static_cast<float>(100.0 * CPUSeconds / Seconds / LogicalCores), 0.f, 100.f);
	}
	return Point;
}

void UPCSPPerfSamplerSubsystem::SelectMode(EPCSPPolicyMode Mode)
{
	IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.PolicyMode"));
	if (!Variable) { return; }
	Variable->Set(static_cast<int32>(Mode), ECVF_SetByConsole);
	BeginComparisonRun(UPCSPPolicySubsystem::GetPolicyMode(), FPlatformTime::Seconds());
}

void UPCSPPerfSamplerSubsystem::BeginComparisonRun(EPCSPPolicyMode Mode, double Now)
{
	// Finalize only the old mode's complete frames before resetting its counters.
	if (NextRunId > 0 && Now >= WarmupUntil) { FlushComparison(Now); }
	RecordingMode = Mode;
	WarmupUntil = Now + 5.0;
	ComparisonStart = WarmupUntil;
	WindowStart = 0.0;
	WindowCPUStart = -1.0;
	ComparisonFrames = 0;
	// Latest three modes remain available; complete history is streamed to CSV.
	if (ComparisonRuns.Num() >= 30)
	{
		for (int32 Index = 0; Index < ComparisonRuns.Num(); ++Index)
		{
			if (LatestRun(ComparisonRuns[Index].Mode) != &ComparisonRuns[Index])
			{
				ComparisonRuns.RemoveAt(Index);
				break;
			}
		}
	}
	FPCSPPerfRun& Run = ComparisonRuns.AddDefaulted_GetRef();
	Run.Id = ++NextRunId;
	Run.Mode = Mode;
	UE_LOG(LogTemp, Display, TEXT("PCSPPerformance: run=%d mode=%s warmup=5s csv=%s"),
		Run.Id, *UPCSPPolicySubsystem::PolicyModeName(Mode), *ComparisonPath);
}

const FPCSPPerfRun* UPCSPPerfSamplerSubsystem::LatestRun(EPCSPPolicyMode Mode) const
{
	for (int32 Index = ComparisonRuns.Num() - 1; Index >= 0; --Index)
	{
		if (ComparisonRuns[Index].Mode == Mode) { return &ComparisonRuns[Index]; }
	}
	return nullptr;
}

float UPCSPPerfSamplerSubsystem::WarmupRemaining() const
{
	return FMath::Max(0.0, WarmupUntil - FPlatformTime::Seconds());
}

void UPCSPPerfSamplerSubsystem::TickComparison(double Now)
{
	const EPCSPPolicyMode Mode = UPCSPPolicySubsystem::GetPolicyMode();
	if (Mode != RecordingMode) { BeginComparisonRun(Mode, Now); return; }
	if (Now < WarmupUntil) { return; }
	if (WindowStart <= 0.0)
	{
		WindowStart = ComparisonStart = Now;
		WindowCPUStart = ReadProcessCPUSeconds();
		return;
	}
	++ComparisonFrames;
	if (Now - WindowStart >= 1.0) { FlushComparison(Now); }
}

void UPCSPPerfSamplerSubsystem::FlushComparison(double Now)
{
	if (ComparisonRuns.IsEmpty() || ComparisonFrames <= 0 || WindowStart <= 0.0) { return; }
	const double CPU = ReadProcessCPUSeconds();
	const double CPUDelta = CPU >= 0.0 && WindowCPUStart >= 0.0 ? CPU - WindowCPUStart : -1.0;
	const FPCSPPerfPoint Point = MakePoint(Now - ComparisonStart, Now - WindowStart,
		ComparisonFrames, CPUDelta, FPlatformMisc::NumberOfCoresIncludingHyperthreads());
	FPCSPPerfRun& Run = ComparisonRuns.Last();
	Run.RecordedSeconds += Point.Seconds;
	Run.Frames += Point.Frames;
	if (Point.CPU >= 0.f) { Run.CPUIntegral += Point.CPU * Point.Seconds; Run.CPUSeconds += Point.Seconds; }
	// Thin older plotting points while preserving the time axis and run onset.
	// Summary totals and the CSV keep every original one-second window.
	if (Run.Points.Num() >= 600)
	{
		for (int32 Index = 0; Index < 300; ++Index) { Run.Points[Index] = Run.Points[Index * 2]; }
		Run.Points.SetNum(300);
	}
	Run.Points.Add(Point);
	int32 NPCCount = 0;
	for (TActorIterator<APCSPMassSpawner> It(GetWorld()); It; ++It) { NPCCount += It->GetSpawnedEntityCount(); }
	for (TActorIterator<APCSPAgentCharacter> It(GetWorld()); It; ++It) { ++NPCCount; }
	FIntPoint Size = FIntPoint::ZeroValue;
	if (UGameViewportClient* Viewport = GetWorld()->GetGameViewport())
	{
		if (Viewport->Viewport) { Size = Viewport->Viewport->GetSizeXY(); }
	}
	const IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync"));
	const IConsoleVariable* Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"));
	AppendComparisonCSV(FString::Printf(TEXT("%d,%s,%.3f,%.3f,%d,%.3f,%.3f,%.3f,%s,%d,%d,%d,%d,%.1f\n"),
		Run.Id, *UPCSPPolicySubsystem::PolicyModeName(Run.Mode), Point.Elapsed, Point.Seconds,
		Point.Frames, Point.CPU, Point.FPS, Point.FrameMs,
		GetWorld()->WorldType == EWorldType::PIE ? TEXT("PIE") : TEXT("Game"),
		NPCCount, Size.X, Size.Y, VSync ? VSync->GetInt() : -1, Cap ? Cap->GetFloat() : -1.f));
	WindowStart = Now;
	WindowCPUStart = CPU;
	ComparisonFrames = 0;
}

void UPCSPPerfSamplerSubsystem::AppendComparisonCSV(const FString& Line)
{
	if (ComparisonPath.IsEmpty()) { return; }
	if (!FFileHelper::SaveStringToFile(Line, *ComparisonPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead))
	{
		if (!bComparisonWriteError) { UE_LOG(LogTemp, Error, TEXT("PCSPPerformance: cannot write %s"), *ComparisonPath); }
		bComparisonWriteError = true;
	}
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
