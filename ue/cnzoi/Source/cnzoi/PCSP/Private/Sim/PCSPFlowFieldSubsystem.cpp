#include "PCSPFlowFieldSubsystem.h"

#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "Async/Async.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "Stats/Stats.h"

static TAutoConsoleVariable<int32> CVarPCSPMassFlowFieldEnabled(
	TEXT("pcsp.MassFlowFieldEnabled"), 0,
	TEXT("Build legacy authored-city route fields for comparison; Mass movement uses Recast."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPFlowFieldCellSize(
	TEXT("pcsp.FlowFieldCellSize"), 200.f,
	TEXT("PCSP Mass route-field tile size in UU."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPFlowFieldObstaclePadding(
	TEXT("pcsp.FlowFieldObstaclePadding"), 230.f,
	TEXT("XY padding around PCSP.City.Obstacle bounds in UU."),
	ECVF_Default);

namespace
{
	const FName WalkableTag(TEXT("PCSP.City.Walkable"));
	const FName ObstacleTag(TEXT("PCSP.City.Obstacle"));

	struct FTaggedBounds
	{
		FBox Bounds = FBox(ForceInit);
	};

	bool ContainsXY(const FBox& Bounds, const FVector2f Point, const float Padding)
	{
		return Point.X >= Bounds.Min.X - Padding && Point.X <= Bounds.Max.X + Padding
			&& Point.Y >= Bounds.Min.Y - Padding && Point.Y <= Bounds.Max.Y + Padding;
	}

	bool SegmentHitsBox(const FVector2D A, const FVector2D B, const FBox2D& Box)
	{
		double Enter = 0.0;
		double Exit = 1.0;
		for (int32 Axis = 0; Axis < 2; ++Axis)
		{
			const double Delta = B[Axis] - A[Axis];
			if (FMath::Abs(Delta) < UE_DOUBLE_SMALL_NUMBER)
			{
				if (A[Axis] < Box.Min[Axis] || A[Axis] > Box.Max[Axis]) { return false; }
				continue;
			}
			double Near = (Box.Min[Axis] - A[Axis]) / Delta;
			double Far = (Box.Max[Axis] - A[Axis]) / Delta;
			if (Near > Far) { Swap(Near, Far); }
			Enter = FMath::Max(Enter, Near);
			Exit = FMath::Min(Exit, Far);
			if (Enter > Exit) { return false; }
		}
		return true;
	}

	bool ClearLocalConnector(const FVector2D A, const FVector2D B,
		const TArray<FBox2D>& Obstacles, const TArray<FBox2D>& Surfaces)
	{
		for (const FBox2D& Obstacle : Obstacles)
		{
			if (SegmentHitsBox(A, B, Obstacle.ExpandBy(80.f))) { return false; }
		}
		const int32 Steps = FMath::Max(1, FMath::CeilToInt(FVector2D::Distance(A, B) / 50.f));
		for (int32 Step = 0; Step <= Steps; ++Step)
		{
			const FVector2D Point = FMath::Lerp(A, B, static_cast<double>(Step) / Steps);
			if (!Surfaces.ContainsByPredicate([Point](const FBox2D& Surface)
				{ return Surface.IsInsideOrOn(Point); })) { return false; }
		}
		return true;
	}
}

void UPCSPFlowFieldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	bSampling = InWorld.WorldType == EWorldType::PIE || InWorld.WorldType == EWorldType::Game;
	RetryDelay = 0.f;
	for (TActorIterator<AActor> It(&InWorld); It; ++It)
	{
		if (It->ActorHasTag(WalkableTag)) { bHasAuthoredNavigation = true; break; }
	}
}

void UPCSPFlowFieldSubsystem::Deinitialize()
{
	if (PendingBuild.IsValid())
	{
		PendingBuild.Wait();
		PendingBuild.Get();
	}
	BuiltData = FBuildResult();
	bReady = false;
	bBuildStarted = false;
	bHasAuthoredNavigation = false;
	bSampling = false;
	Super::Deinitialize();
}

void UPCSPFlowFieldSubsystem::Tick(float DeltaTime)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_FlowField_Tick);
	ApplyCompletedBuild();
	if (!IsEnabled() || bReady || bBuildStarted) { return; }

	RetryDelay -= DeltaTime;
	if (RetryDelay <= 0.f)
	{
		TryDispatchBuild();
		RetryDelay = 0.5f;
	}
}

TStatId UPCSPFlowFieldSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UPCSPFlowFieldSubsystem, STATGROUP_Tickables);
}

bool UPCSPFlowFieldSubsystem::IsTickable() const
{
	return bSampling && !IsTemplate();
}

bool UPCSPFlowFieldSubsystem::IsEnabled()
{
	return CVarPCSPMassFlowFieldEnabled.GetValueOnAnyThread() != 0;
}

bool UPCSPFlowFieldSubsystem::GetWaypointToZone(const FVector& WorldLocation,
	const FVector& ExactSlot, const int32 ZoneVisualizationIndex, FVector& OutWaypoint) const
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_FlowField_Query);
	if (!bReady || !IsEnabled() || BuiltData.Width <= 0 || BuiltData.Height <= 0)
	{
		return false;
	}

	const int32 CellX = FMath::FloorToInt((WorldLocation.X - BuiltData.Origin.X) / BuiltData.CellSize);
	const int32 CellY = FMath::FloorToInt((WorldLocation.Y - BuiltData.Origin.Y) / BuiltData.CellSize);
	if (CellX < 0 || CellY < 0 || CellX >= BuiltData.Width || CellY >= BuiltData.Height)
	{
		return false;
	}

	const FField* Field = BuiltData.Fields.Find(ZoneVisualizationIndex);
	const int32 CellIndex = CellY * BuiltData.Width + CellX;
	if (!Field || !Field->Directions.IsValidIndex(CellIndex)
		|| !BuiltData.GroundHeights.IsValidIndex(CellIndex))
	{
		return false;
	}
	// All slots were authored inside a clear rectangle. Once in that rectangle,
	// stop following the center field and finish at the reserved slot itself.
	if (Field->FinishBounds.IsInside(FVector2D(WorldLocation.X, WorldLocation.Y))
		&& Field->FinishBounds.IsInside(FVector2D(ExactSlot.X, ExactSlot.Y)))
	{
		OutWaypoint = ExactSlot;
		return true;
	}

	const FVector2f Direction = Field->Directions[CellIndex];
	if (Direction.IsNearlyZero())
	{
		// A safe exact slot or spawn can lie inside a conservatively excluded
		// grid cell. Connect it to a nearby reachable cell using real geometry,
		// without teleporting or crossing buildings/water to recover.
		float BestDistanceSq = TNumericLimits<float>::Max();
		bool bFound = false;
		for (int32 Y = FMath::Max(0, CellY - 4); Y <= FMath::Min(BuiltData.Height - 1, CellY + 4); ++Y)
		{
			for (int32 X = FMath::Max(0, CellX - 4); X <= FMath::Min(BuiltData.Width - 1, CellX + 4); ++X)
			{
				const int32 Candidate = Y * BuiltData.Width + X;
				if (Field->Directions[Candidate].IsNearlyZero()) { continue; }
				const FVector Center(BuiltData.Origin.X + (X + 0.5f) * BuiltData.CellSize,
					BuiltData.Origin.Y + (Y + 0.5f) * BuiltData.CellSize,
					BuiltData.GroundHeights[Candidate] + 1.f);
				const float DistanceSq = FVector::DistSquared2D(WorldLocation, Center);
				if (DistanceSq >= BestDistanceSq) { continue; }
				if (!ClearLocalConnector(FVector2D(WorldLocation.X, WorldLocation.Y),
					FVector2D(Center.X, Center.Y), BuiltData.Obstacles, BuiltData.Surfaces)) { continue; }
				OutWaypoint = Center;
				BestDistanceSq = DistanceSq;
				bFound = true;
			}
		}
		return bFound;
	}
	const int32 NextX = CellX + FMath::RoundToInt(Direction.X);
	const int32 NextY = CellY + FMath::RoundToInt(Direction.Y);
	const int32 NextIndex = NextY * BuiltData.Width + NextX;
	if (!BuiltData.GroundHeights.IsValidIndex(NextIndex)) { return false; }
	OutWaypoint = FVector(BuiltData.Origin.X + (NextX + 0.5f) * BuiltData.CellSize,
		BuiltData.Origin.Y + (NextY + 0.5f) * BuiltData.CellSize,
		BuiltData.GroundHeights[NextIndex] + 1.f);
	return true;
}

void UPCSPFlowFieldSubsystem::TryDispatchBuild()
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_FlowField_GameThreadSnapshot);
	UWorld* World = GetWorld();
	UPCSPAffordanceSubsystem* Affordances = World ? World->GetSubsystem<UPCSPAffordanceSubsystem>() : nullptr;
	if (!World || !Affordances || Affordances->GetAllZones().IsEmpty()) { return; }

	TArray<FTaggedBounds> Surfaces;
	TArray<FTaggedBounds> Obstacles;
	FBox2D NavigationBounds(ForceInit);
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		const bool bWalkable = Actor && Actor->ActorHasTag(WalkableTag);
		const bool bObstacle = Actor && Actor->ActorHasTag(ObstacleTag);
		if (!bWalkable && !bObstacle) { continue; }
		FVector Origin;
		FVector Extent;
		Actor->GetActorBounds(false, Origin, Extent);
		const FBox Bounds(Origin - Extent, Origin + Extent);
		if (!Bounds.IsValid) { continue; }
		if (bWalkable)
		{
			Surfaces.Add({Bounds});
			NavigationBounds += FVector2D(Bounds.Min.X, Bounds.Min.Y);
			NavigationBounds += FVector2D(Bounds.Max.X, Bounds.Max.Y);
		}
		if (bObstacle) { Obstacles.Add({Bounds}); }
	}
	if (Surfaces.IsEmpty() || !NavigationBounds.bIsValid) { return; }
	bHasAuthoredNavigation = true;

	FBuildInput Input;
	for (const FTaggedBounds& Surface : Surfaces)
	{
		Input.Surfaces.Add(FBox2D(FVector2D(Surface.Bounds.Min.X, Surface.Bounds.Min.Y),
			FVector2D(Surface.Bounds.Max.X, Surface.Bounds.Max.Y)));
	}
	for (const FTaggedBounds& Obstacle : Obstacles)
	{
		Input.Obstacles.Add(FBox2D(FVector2D(Obstacle.Bounds.Min.X, Obstacle.Bounds.Min.Y),
			FVector2D(Obstacle.Bounds.Max.X, Obstacle.Bounds.Max.Y)));
	}
	Input.CellSize = FMath::Max(100.f, CVarPCSPFlowFieldCellSize.GetValueOnGameThread());
	const float Border = Input.CellSize;
	Input.Origin = FVector2f(
		FMath::FloorToFloat((NavigationBounds.Min.X - Border) / Input.CellSize) * Input.CellSize,
		FMath::FloorToFloat((NavigationBounds.Min.Y - Border) / Input.CellSize) * Input.CellSize);
	Input.Width = FMath::CeilToInt((NavigationBounds.Max.X + Border - Input.Origin.X) / Input.CellSize);
	Input.Height = FMath::CeilToInt((NavigationBounds.Max.Y + Border - Input.Origin.Y) / Input.CellSize);
	Input.Walkable.Init(0, Input.Width * Input.Height);
	Input.GroundHeights.Init(0.f, Input.Width * Input.Height);
	const float ObstaclePadding = FMath::Max(0.f, CVarPCSPFlowFieldObstaclePadding.GetValueOnGameThread());

	for (int32 CellY = 0; CellY < Input.Height; ++CellY)
	{
		for (int32 CellX = 0; CellX < Input.Width; ++CellX)
		{
			const FVector2f Point(Input.Origin.X + (CellX + 0.5f) * Input.CellSize,
				Input.Origin.Y + (CellY + 0.5f) * Input.CellSize);
			float GroundZ = -TNumericLimits<float>::Max();
			for (const FTaggedBounds& Surface : Surfaces)
			{
				if (ContainsXY(Surface.Bounds, Point, 0.f))
				{
					GroundZ = FMath::Max(GroundZ, static_cast<float>(Surface.Bounds.Max.Z));
				}
			}
			if (GroundZ == -TNumericLimits<float>::Max()) { continue; }
			bool bBlocked = false;
			for (const FTaggedBounds& Obstacle : Obstacles)
			{
				if (ContainsXY(Obstacle.Bounds, Point, ObstaclePadding))
				{
					bBlocked = true;
					break;
				}
			}
			if (bBlocked) { continue; }
			const int32 CellIndex = CellY * Input.Width + CellX;
			Input.Walkable[CellIndex] = 1;
			Input.GroundHeights[CellIndex] = GroundZ;
		}
	}

	for (const TWeakObjectPtr<APCSPAffordanceZone>& WeakZone : Affordances->GetAllZones())
	{
		const APCSPAffordanceZone* Zone = WeakZone.Get();
		if (!Zone) { continue; }
		const FVector Goal = Zone->GetActorLocation();
		const int32 GoalX = FMath::FloorToInt((Goal.X - Input.Origin.X) / Input.CellSize);
		const int32 GoalY = FMath::FloorToInt((Goal.Y - Input.Origin.Y) / Input.CellSize);
		int32 BestCell = INDEX_NONE;
		float BestDistanceSq = TNumericLimits<float>::Max();
		for (int32 Radius = 0; Radius <= 4 && BestCell == INDEX_NONE; ++Radius)
		{
			for (int32 Y = GoalY - Radius; Y <= GoalY + Radius; ++Y)
			{
				for (int32 X = GoalX - Radius; X <= GoalX + Radius; ++X)
				{
					if (X < 0 || Y < 0 || X >= Input.Width || Y >= Input.Height) { continue; }
					const int32 Cell = Y * Input.Width + X;
					if (!Input.Walkable[Cell]) { continue; }
					const FVector2f Center(Input.Origin.X + (X + 0.5f) * Input.CellSize,
						Input.Origin.Y + (Y + 0.5f) * Input.CellSize);
					const float DistanceSq = FVector2f::DistSquared(Center, FVector2f(Goal.X, Goal.Y));
					if (DistanceSq < BestDistanceSq) { BestDistanceSq = DistanceSq; BestCell = Cell; }
				}
			}
		}
		if (BestCell != INDEX_NONE)
		{
			FSource Source;
			Source.CellIndex = BestCell;
			for (int32 Slot = 0; Slot < Zone->GetInteractionSlotCount(); ++Slot)
			{
				const FVector Location = Zone->GetInteractionSlotWorldLocation(Slot);
				Source.FinishBounds += FVector2D(Location.X, Location.Y);
			}
			// Stay inside the authoring clearance, including single-row zones.
			Source.FinishBounds = Source.FinishBounds.ExpandBy(100.f);
			Input.SourcesByZone.Add(Zone->VisualizationIndex, Source);
		}
	}

	if (Input.SourcesByZone.IsEmpty()) { return; }
	bBuildStarted = true;
	UE_LOG(LogTemp, Log, TEXT("PCSPCityRoutes: snapshot surfaces=%d obstacles=%d zones=%d grid=%dx%d"),
		Surfaces.Num(), Obstacles.Num(), Input.SourcesByZone.Num(), Input.Width, Input.Height);
	PendingBuild = Async(EAsyncExecution::ThreadPool, [Input = MoveTemp(Input)]() mutable
	{
		return BuildFields(MoveTemp(Input));
	});
}

void UPCSPFlowFieldSubsystem::ApplyCompletedBuild()
{
	if (!PendingBuild.IsValid() || !PendingBuild.IsReady()) { return; }
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_FlowField_GameThreadApply);
	BuiltData = PendingBuild.Get();
	PendingBuild = TFuture<FBuildResult>();
	bReady = !BuiltData.Fields.IsEmpty();
	UE_LOG(LogTemp, Log,
		TEXT("PCSPCityRoutes: %s (%dx%d, cell=%.0f, walkable=%d, zone_fields=%d, worker=%.2f ms)"),
		bReady ? TEXT("ready") : TEXT("failed"), BuiltData.Width, BuiltData.Height,
		BuiltData.CellSize, BuiltData.WalkableCells, BuiltData.Fields.Num(),
		BuiltData.WorkerMicros / 1000.0);
}

UPCSPFlowFieldSubsystem::FBuildResult UPCSPFlowFieldSubsystem::BuildFields(FBuildInput Input)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_FlowField_WorkerBuild);
	const double StartSeconds = FPlatformTime::Seconds();
	FBuildResult Result;
	Result.Origin = Input.Origin;
	Result.CellSize = Input.CellSize;
	Result.Width = Input.Width;
	Result.Height = Input.Height;
	Result.GroundHeights = MoveTemp(Input.GroundHeights);
	Result.Surfaces = MoveTemp(Input.Surfaces);
	Result.Obstacles = MoveTemp(Input.Obstacles);
	for (const uint8 Cell : Input.Walkable) { Result.WalkableCells += Cell != 0 ? 1 : 0; }
	const int32 CellCount = Input.Width * Input.Height;
	static constexpr int32 DX[8] = {1, -1, 0, 0, 1, 1, -1, -1};
	static constexpr int32 DY[8] = {0, 0, 1, -1, 1, -1, 1, -1};

	for (const TPair<int32, FSource>& ZoneSource : Input.SourcesByZone)
	{
		FField& Field = Result.Fields.Add(ZoneSource.Key);
		Field.FinishBounds = ZoneSource.Value.FinishBounds;
		Field.Directions.Init(FVector2f::ZeroVector, CellCount);
		TArray<int32> Distance;
		Distance.Init(MAX_int32, CellCount);
		TArray<int32> Queue;
		Queue.Reserve(CellCount);
		Distance[ZoneSource.Value.CellIndex] = 0;
		Queue.Add(ZoneSource.Value.CellIndex);

		for (int32 Head = 0; Head < Queue.Num(); ++Head)
		{
			const int32 CurrentIndex = Queue[Head];
			const int32 CurrentX = CurrentIndex % Input.Width;
			const int32 CurrentY = CurrentIndex / Input.Width;
			for (int32 DirectionIndex = 0; DirectionIndex < 8; ++DirectionIndex)
			{
				const int32 NextX = CurrentX + DX[DirectionIndex];
				const int32 NextY = CurrentY + DY[DirectionIndex];
				if (NextX < 0 || NextY < 0 || NextX >= Input.Width || NextY >= Input.Height) { continue; }
				const int32 NextIndex = NextY * Input.Width + NextX;
				if (!Input.Walkable[NextIndex] || Distance[NextIndex] != MAX_int32) { continue; }
				if (DirectionIndex >= 4)
				{
					const int32 SideA = CurrentY * Input.Width + NextX;
					const int32 SideB = NextY * Input.Width + CurrentX;
					if (!Input.Walkable[SideA] || !Input.Walkable[SideB]) { continue; }
				}
				Distance[NextIndex] = Distance[CurrentIndex] + 1;
				Queue.Add(NextIndex);
			}
		}

		for (int32 CellIndex = 0; CellIndex < CellCount; ++CellIndex)
		{
			if (Distance[CellIndex] == MAX_int32 || Distance[CellIndex] == 0) { continue; }
			const int32 CellX = CellIndex % Input.Width;
			const int32 CellY = CellIndex / Input.Width;
			int32 BestIndex = CellIndex;
			for (int32 DirectionIndex = 0; DirectionIndex < 8; ++DirectionIndex)
			{
				const int32 NextX = CellX + DX[DirectionIndex];
				const int32 NextY = CellY + DY[DirectionIndex];
				if (NextX < 0 || NextY < 0 || NextX >= Input.Width || NextY >= Input.Height) { continue; }
				const int32 NextIndex = NextY * Input.Width + NextX;
				if (DirectionIndex >= 4
					&& (!Input.Walkable[CellY * Input.Width + NextX]
						|| !Input.Walkable[NextY * Input.Width + CellX])) { continue; }
				if (Distance[NextIndex] < Distance[BestIndex]) { BestIndex = NextIndex; }
			}
			if (BestIndex != CellIndex)
			{
				Field.Directions[CellIndex] = FVector2f(
					static_cast<float>((BestIndex % Input.Width) - CellX),
					static_cast<float>((BestIndex / Input.Width) - CellY));
			}
		}
	}

	Result.WorkerMicros = (FPlatformTime::Seconds() - StartSeconds) * 1.0e6;
	return Result;
}
