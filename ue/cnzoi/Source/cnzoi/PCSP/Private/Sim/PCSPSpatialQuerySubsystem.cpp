#include "PCSPSpatialQuerySubsystem.h"

#include "PCSPSocialContextComponent.h"
#include "Async/Async.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "Stats/Stats.h"

static TAutoConsoleVariable<int32> CVarPCSPAsyncSpatialQueries(
	TEXT("pcsp.AsyncSpatialQueries"), 0,
	TEXT("Use POD snapshot + worker-grid spatial queries (0=legacy per-agent scans, 1=async grid)."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPSpatialSnapshotInterval(
	TEXT("pcsp.SpatialSnapshotInterval"), 0.25f,
	TEXT("Seconds between Actor-tier spatial snapshots."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPSpatialCellSize(
	TEXT("pcsp.SpatialCellSize"), 800.f,
	TEXT("Uniform-grid cell size used by async PCSP spatial queries (UU)."),
	ECVF_Default);

void UPCSPSpatialQuerySubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	bSampling = InWorld.WorldType == EWorldType::PIE || InWorld.WorldType == EWorldType::Game;
	SecondsUntilDispatch = 0.f;
}

void UPCSPSpatialQuerySubsystem::Deinitialize()
{
	if (PendingFuture.IsValid())
	{
		PendingFuture.Wait();
		PendingFuture.Get();
	}
	PendingActors.Reset();
	CurrentResults.Reset();
	bSampling = false;
	Super::Deinitialize();
}

void UPCSPSpatialQuerySubsystem::Tick(float DeltaTime)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_AsyncSubsystemTick);
	ApplyCompletedJob();

	if (!IsAsyncEnabled())
	{
		CurrentResults.Reset();
		return;
	}

	SecondsUntilDispatch -= DeltaTime;
	if (!PendingFuture.IsValid() && SecondsUntilDispatch <= 0.f)
	{
		DispatchSnapshot();
		SecondsUntilDispatch = FMath::Max(
			0.05f, CVarPCSPSpatialSnapshotInterval.GetValueOnGameThread());
	}
}

TStatId UPCSPSpatialQuerySubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UPCSPSpatialQuerySubsystem, STATGROUP_Tickables);
}

bool UPCSPSpatialQuerySubsystem::IsTickable() const
{
	return bSampling && !IsTemplate();
}

bool UPCSPSpatialQuerySubsystem::IsAsyncEnabled()
{
	return CVarPCSPAsyncSpatialQueries.GetValueOnAnyThread() != 0;
}

bool UPCSPSpatialQuerySubsystem::GetQueryResult(const AActor* Owner,
	TArray<AActor*>& OutNearby, TArray<AActor*>& OutNearest) const
{
	OutNearby.Reset();
	OutNearest.Reset();
	if (!Owner || !IsAsyncEnabled())
	{
		return false;
	}

	const FActorResult* Result = CurrentResults.Find(TWeakObjectPtr<AActor>(const_cast<AActor*>(Owner)));
	if (!Result)
	{
		return false;
	}

	for (const TWeakObjectPtr<AActor>& Weak : Result->Nearby)
	{
		if (AActor* Actor = Weak.Get()) { OutNearby.Add(Actor); }
	}
	for (const TWeakObjectPtr<AActor>& Weak : Result->Nearest)
	{
		if (AActor* Actor = Weak.Get()) { OutNearest.Add(Actor); }
	}
	return true;
}

void UPCSPSpatialQuerySubsystem::ApplyCompletedJob()
{
	if (!PendingFuture.IsValid() || !PendingFuture.IsReady())
	{
		return;
	}

	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_AsyncApply);
	FJobResult JobResult = PendingFuture.Get();
	PendingFuture = TFuture<FJobResult>();
	TMap<TWeakObjectPtr<AActor>, FActorResult> NewResults;
	const int32 Count = FMath::Min(PendingActors.Num(), JobResult.PerActor.Num());
	NewResults.Reserve(Count);

	for (int32 OwnerIndex = 0; OwnerIndex < Count; ++OwnerIndex)
	{
		if (!PendingActors[OwnerIndex].IsValid()) { continue; }
		FActorResult& ActorResult = NewResults.Add(PendingActors[OwnerIndex]);
		for (const int32 NeighborIndex : JobResult.PerActor[OwnerIndex].Nearby)
		{
			if (PendingActors.IsValidIndex(NeighborIndex) && PendingActors[NeighborIndex].IsValid())
			{
				ActorResult.Nearby.Add(PendingActors[NeighborIndex]);
			}
		}
		for (const int32 NeighborIndex : JobResult.PerActor[OwnerIndex].Nearest)
		{
			if (PendingActors.IsValidIndex(NeighborIndex) && PendingActors[NeighborIndex].IsValid())
			{
				ActorResult.Nearest.Add(PendingActors[NeighborIndex]);
			}
		}
	}

	CurrentResults = MoveTemp(NewResults);
	PendingActors.Reset();
}

void UPCSPSpatialQuerySubsystem::DispatchSnapshot()
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_AsyncSnapshot);
	UWorld* World = GetWorld();
	if (!World) { return; }

	TArray<FSnapshotEntry> Snapshot;
	PendingActors.Reset();
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor) { continue; }
		const UPCSPSocialContextComponent* Social =
			Actor->FindComponentByClass<UPCSPSocialContextComponent>();
		if (!Social) { continue; }

		PendingActors.Add(Actor);
		Snapshot.Add({FVector3f(Actor->GetActorLocation()), FMath::Max(0.f, Social->PerceptionRadius)});
	}

	if (Snapshot.IsEmpty())
	{
		CurrentResults.Reset();
		return;
	}

	const float CellSize = FMath::Max(100.f, CVarPCSPSpatialCellSize.GetValueOnGameThread());
	PendingFuture = Async(EAsyncExecution::ThreadPool,
		[Snapshot = MoveTemp(Snapshot), CellSize]() mutable
		{
			return BuildGridResults(MoveTemp(Snapshot), CellSize);
		});
}

UPCSPSpatialQuerySubsystem::FJobResult UPCSPSpatialQuerySubsystem::BuildGridResults(
	TArray<FSnapshotEntry> Snapshot, float CellSize)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_WorkerGrid);
	const double StartSeconds = FPlatformTime::Seconds();
	FJobResult Result;
	Result.PerActor.SetNum(Snapshot.Num());

	TMap<FIntPoint, TArray<int32>> Grid;
	Grid.Reserve(Snapshot.Num());
	for (int32 Index = 0; Index < Snapshot.Num(); ++Index)
	{
		const FVector3f& Position = Snapshot[Index].Position;
		const FIntPoint Cell(FMath::FloorToInt(Position.X / CellSize),
			FMath::FloorToInt(Position.Y / CellSize));
		Grid.FindOrAdd(Cell).Add(Index);
	}

	struct FCandidate
	{
		int32 Index = INDEX_NONE;
		float DistanceSq = 0.f;
	};

	for (int32 OwnerIndex = 0; OwnerIndex < Snapshot.Num(); ++OwnerIndex)
	{
		const FSnapshotEntry& Owner = Snapshot[OwnerIndex];
		const float RadiusSq = FMath::Square(Owner.Radius);
		const int32 CellRadius = FMath::Max(1, FMath::CeilToInt(Owner.Radius / CellSize));
		const FIntPoint OwnerCell(FMath::FloorToInt(Owner.Position.X / CellSize),
			FMath::FloorToInt(Owner.Position.Y / CellSize));
		TArray<FCandidate> Candidates;

		for (int32 CellY = OwnerCell.Y - CellRadius; CellY <= OwnerCell.Y + CellRadius; ++CellY)
		{
			for (int32 CellX = OwnerCell.X - CellRadius; CellX <= OwnerCell.X + CellRadius; ++CellX)
			{
				const TArray<int32>* Bucket = Grid.Find(FIntPoint(CellX, CellY));
				if (!Bucket) { continue; }
				for (const int32 CandidateIndex : *Bucket)
				{
					if (CandidateIndex == OwnerIndex) { continue; }
					const float DistanceSq = FVector3f::DistSquared(
						Owner.Position, Snapshot[CandidateIndex].Position);
					Candidates.Add({CandidateIndex, DistanceSq});
					if (DistanceSq <= RadiusSq)
					{
						Result.PerActor[OwnerIndex].Nearby.Add(CandidateIndex);
					}
				}
			}
		}

		Candidates.Sort([](const FCandidate& A, const FCandidate& B)
		{
			return A.DistanceSq < B.DistanceSq;
		});
		const int32 NearestCount = FMath::Min(3, Candidates.Num());
		for (int32 Index = 0; Index < NearestCount; ++Index)
		{
			Result.PerActor[OwnerIndex].Nearest.Add(Candidates[Index].Index);
		}
	}

	Result.WorkerMicros = (FPlatformTime::Seconds() - StartSeconds) * 1.0e6;
	return Result;
}
