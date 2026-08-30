#include "PCSPPathRequestSchedulerSubsystem.h"

#include "PCSPTrajectoryLogComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Stats/Stats.h"

static TAutoConsoleVariable<int32> CVarPCSPPathSchedulingEnabled(
	TEXT("pcsp.PathSchedulingEnabled"), 1,
	TEXT("Spread PCSP actor MoveTo requests across frames (0=off, 1=on)."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPPathRequestsPerFrame(
	TEXT("pcsp.PathRequestsPerFrame"), 8,
	TEXT("Maximum PCSP actor MoveTo requests released per frame."),
	ECVF_Default);

void UPCSPPathRequestSchedulerSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	const EWorldType::Type WorldType = InWorld.WorldType;
	bSampling = WorldType == EWorldType::PIE || WorldType == EWorldType::Game;
	if (bSampling)
	{
		TelemetryPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("path_scheduler.jsonl");
		LastFlushAt = InWorld.GetTimeSeconds();
		WindowWaitMs.Reserve(256);
	}
}

void UPCSPPathRequestSchedulerSubsystem::Deinitialize()
{
	if (bSampling)
	{
		FlushTelemetry();
	}
	Requests.Reset();
	bSampling = false;
	Super::Deinitialize();
}

bool UPCSPPathRequestSchedulerSubsystem::IsTickable() const
{
	return bSampling && !IsTemplate();
}

TStatId UPCSPPathRequestSchedulerSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UPCSPPathRequestSchedulerSubsystem, STATGROUP_Tickables);
}

bool UPCSPPathRequestSchedulerSubsystem::TryConsumePermit(AActor* Agent, float UrgencyScore)
{
	if (!Agent || CVarPCSPPathSchedulingEnabled.GetValueOnGameThread() == 0)
	{
		return true;
	}

	const TWeakObjectPtr<AActor> Key(Agent);
	if (FRequestState* Existing = Requests.Find(Key))
	{
		Existing->Urgency = FMath::Max(Existing->Urgency, FMath::Clamp(UrgencyScore, 0.f, 1.f));
		if (Existing->bGranted)
		{
			const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : Existing->EnqueuedAt;
			WindowWaitMs.Add(static_cast<float>(FMath::Max(0.0, Now - Existing->EnqueuedAt) * 1000.0));
			++WindowSubmitted;
			Requests.Remove(Key);
			return true;
		}
		return false;
	}

	FRequestState& Added = Requests.Add(Key);
	Added.EnqueuedAt = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	Added.Urgency = FMath::Clamp(UrgencyScore, 0.f, 1.f);
	Added.Serial = NextSerial++;
	++WindowEnqueued;
	WindowPeakDepth = FMath::Max(WindowPeakDepth, Requests.Num());
	return false;
}

void UPCSPPathRequestSchedulerSubsystem::CancelRequest(AActor* Agent)
{
	if (Agent && Requests.Remove(TWeakObjectPtr<AActor>(Agent)) > 0)
	{
		++WindowCancelled;
	}
}

void UPCSPPathRequestSchedulerSubsystem::Tick(float DeltaTime)
{
	for (auto It = Requests.CreateIterator(); It; ++It)
	{
		if (!It.Key().IsValid()) { It.RemoveCurrent(); }
	}

	GrantFrameBudget();
	WindowPeakDepth = FMath::Max(WindowPeakDepth, Requests.Num());

	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Now - LastFlushAt >= 1.0)
	{
		FlushTelemetry();
		LastFlushAt = Now;
	}
}

void UPCSPPathRequestSchedulerSubsystem::GrantFrameBudget()
{
	if (CVarPCSPPathSchedulingEnabled.GetValueOnGameThread() == 0 || Requests.IsEmpty())
	{
		return;
	}

	struct FCandidate
	{
		TWeakObjectPtr<AActor> Agent;
		double Score = 0.0;
		uint64 Serial = 0;
	};

	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	TArray<FCandidate> Candidates;
	Candidates.Reserve(Requests.Num());
	for (const TPair<TWeakObjectPtr<AActor>, FRequestState>& Pair : Requests)
	{
		if (!Pair.Value.bGranted)
		{
			const double WaitSeconds = FMath::Max(0.0, Now - Pair.Value.EnqueuedAt);
			Candidates.Add({Pair.Key, Pair.Value.Urgency * 10.0 + WaitSeconds, Pair.Value.Serial});
		}
	}

	Candidates.Sort([](const FCandidate& A, const FCandidate& B)
	{
		if (!FMath::IsNearlyEqual(A.Score, B.Score)) { return A.Score > B.Score; }
		return A.Serial < B.Serial;
	});

	const int32 Budget = FMath::Max(1, CVarPCSPPathRequestsPerFrame.GetValueOnGameThread());
	const int32 NumToGrant = FMath::Min(Budget, Candidates.Num());
	for (int32 Index = 0; Index < NumToGrant; ++Index)
	{
		if (FRequestState* State = Requests.Find(Candidates[Index].Agent))
		{
			State->bGranted = true;
			++WindowGranted;
		}
	}
}

void UPCSPPathRequestSchedulerSubsystem::FlushTelemetry()
{
	if (TelemetryPath.IsEmpty()) { return; }

	WindowWaitMs.Sort();
	double SumWaitMs = 0.0;
	for (const float Value : WindowWaitMs) { SumWaitMs += Value; }
	const float MeanWaitMs = WindowWaitMs.IsEmpty()
		? 0.f
		: static_cast<float>(SumWaitMs / WindowWaitMs.Num());
	const int32 P95Index = WindowWaitMs.IsEmpty()
		? 0
		: FMath::Clamp(FMath::FloorToInt(WindowWaitMs.Num() * 0.95f), 0, WindowWaitMs.Num() - 1);
	const float P95WaitMs = WindowWaitMs.IsEmpty() ? 0.f : WindowWaitMs[P95Index];
	const float T = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;

	const FString Line = FString::Printf(
		TEXT("{\"t\":%.3f,\"enabled\":%s,\"budget_per_frame\":%d,\"queue_depth\":%d,")
		TEXT("\"peak_depth\":%d,\"enqueued\":%d,\"granted\":%d,\"submitted\":%d,")
		TEXT("\"cancelled\":%d,\"wait_ms_mean\":%.3f,\"wait_ms_p95\":%.3f}\n"),
		T,
		CVarPCSPPathSchedulingEnabled.GetValueOnGameThread() != 0 ? TEXT("true") : TEXT("false"),
		FMath::Max(1, CVarPCSPPathRequestsPerFrame.GetValueOnGameThread()),
		Requests.Num(), WindowPeakDepth, WindowEnqueued, WindowGranted,
		WindowSubmitted, WindowCancelled, MeanWaitMs, P95WaitMs);

	FFileHelper::SaveStringToFile(Line, *TelemetryPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead);

	WindowEnqueued = 0;
	WindowGranted = 0;
	WindowSubmitted = 0;
	WindowCancelled = 0;
	WindowPeakDepth = Requests.Num();
	WindowWaitMs.Reset();
}
