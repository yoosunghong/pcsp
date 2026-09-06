#include "PCSPMassNavigation.h"

#include "NavigationSystem.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> CVarPCSPMassNavQueries(
	TEXT("pcsp.MassNavQueriesPerFrame"), 32,
	TEXT("Maximum new Mass Recast paths per frame; cached paths are followed every frame."));

FIntPoint FPCSPMassNavigation::Cell(const FVector& P)
{
	return FIntPoint(FMath::FloorToInt(P.X / CellSize), FMath::FloorToInt(P.Y / CellSize));
}

void FPCSPMassNavigation::BeginFrame(UWorld& World)
{
	NavSystem = FNavigationSystem::GetCurrent<UNavigationSystemV1>(&World);
	NavData = NavSystem ? NavSystem->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) : nullptr;
	Now = World.GetTimeSeconds();
	QueriesLeft = FMath::Max(1, CVarPCSPMassNavQueries.GetValueOnGameThread());
	Cells.Reset();
	MaxRadius = 1.f;
}

void FPCSPMassNavigation::AddAgent(int32 Id, const FVector& Position, float Radius)
{
	Cells.FindOrAdd(Cell(Position)).Add({Id, Position, Radius});
	MaxRadius = FMath::Max(MaxRadius, Radius);
}

bool FPCSPMassNavigation::HasSpace(const FVector& Position, float Radius) const
{
	const FIntPoint Center = Cell(Position);
	const int32 Range = FMath::CeilToInt((Radius + MaxRadius) / CellSize);
	for (int32 Y = -Range; Y <= Range; ++Y)
	{
		for (int32 X = -Range; X <= Range; ++X)
		{
			if (const TArray<FAgent>* Agents = Cells.Find(Center + FIntPoint(X, Y)))
			{
				for (const FAgent& Other : *Agents)
				{
					if (FMath::Abs(Position.Z - Other.Position.Z) < Radius + Other.Radius
						&& FVector::DistSquared2D(Position, Other.Position) < FMath::Square(Radius + Other.Radius))
					{ return false; }
				}
			}
		}
	}
	return true;
}

void FPCSPMassNavigation::UpdateAgent(int32 Id, const FVector& OldPosition, const FVector& Position, float Radius)
{
	if (!bAgentCollisionEnabled) { return; }
	if (TArray<FAgent>* Agents = Cells.Find(Cell(OldPosition)))
	{
		Agents->RemoveAllSwap([Id](const FAgent& Agent) { return Agent.Id == Id; });
	}
	AddAgent(Id, Position, Radius);
}

FVector FPCSPMassNavigation::ConstrainStep(int32 Id, const FVector& Start, const FVector& End, float Radius) const
{
	if (!bAgentCollisionEnabled) { return End; }
	const FVector Delta = FVector(End.X - Start.X, End.Y - Start.Y, 0.f);
	const double LengthSq = Delta.SizeSquared();
	if (LengthSq < UE_DOUBLE_SMALL_NUMBER) { return End; }
	double Fraction = 1.0;
	const FIntPoint Center = Cell(Start);
	const int32 Range = FMath::CeilToInt((Radius + MaxRadius + Delta.Size()) / CellSize);
	for (int32 Y = -Range; Y <= Range; ++Y)
	{
		for (int32 X = -Range; X <= Range; ++X)
		{
			if (const TArray<FAgent>* Agents = Cells.Find(Center + FIntPoint(X, Y)))
			{
				for (const FAgent& Other : *Agents)
				{
					if (Other.Id == Id || FMath::Abs(Start.Z - Other.Position.Z) > Radius + Other.Radius) { continue; }
					const FVector Offset(Start.X - Other.Position.X, Start.Y - Other.Position.Y, 0.f);
					const double B = FVector::DotProduct(Offset, Delta);
					if (B >= 0.0) { continue; } // Moving away also permits overlap recovery.
					const double C = Offset.SizeSquared() - FMath::Square(Radius + Other.Radius);
					if (C <= 0.0) { Fraction = 0.0; continue; }
					const double Disc = B * B - LengthSq * C;
					if (Disc < 0.0) { continue; }
					const double Contact = (-B - FMath::Sqrt(Disc)) / LengthSq;
					Fraction = FMath::Min(Fraction, FMath::Max(0.0, Contact - 0.001));
				}
			}
		}
	}
	return FMath::Lerp(Start, End, Fraction);
}

FVector FPCSPMassNavigation::Separation(int32 Id, const FVector& Position, float Radius) const
{
	if (!bAgentCollisionEnabled) { return FVector::ZeroVector; }
	FVector Force = FVector::ZeroVector;
	const FIntPoint Center = Cell(Position);
	const int32 Range = FMath::CeilToInt((Radius + MaxRadius) * 1.6f / CellSize);
	for (int32 Y = -Range; Y <= Range; ++Y)
	{
		for (int32 X = -Range; X <= Range; ++X)
		{
			if (const TArray<FAgent>* Agents = Cells.Find(Center + FIntPoint(X, Y)))
			{
				for (const FAgent& Other : *Agents)
				{
					if (Other.Id == Id || FMath::Abs(Position.Z - Other.Position.Z) > Radius + Other.Radius) { continue; }
					FVector Away = Position - Other.Position;
					Away.Z = 0.f;
					const float Distance = Away.Size();
					const float Spacing = (Radius + Other.Radius) * 1.6f;
					if (Distance >= Spacing) { continue; }
					if (Distance < 0.1f)
					{
						const uint32 Hash = HashCombineFast(GetTypeHash(FMath::Min(Id, Other.Id)),
							GetTypeHash(FMath::Max(Id, Other.Id)));
						const float Angle = (Hash % 65536) * (2.f * PI / 65536.f);
						Away = FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.f) * (Id < Other.Id ? 1.f : -1.f);
					}
					else { Away /= Distance; }
					Force += Away * (1.f - Distance / Spacing);
				}
			}
		}
	}
	return Force.GetClampedToMaxSize(2.f);
}

bool FPCSPMassNavigation::FindStroll(const FVector& Position, float Radius, FVector& OutTarget) const
{
	if (!IsReady()) { return false; }
	FNavLocation Start, End;
	if (!NavSystem->ProjectPointToNavigation(Position, Start, FVector(600.f, 600.f, 1000.f), NavData.Get())) { return false; }
	for (int32 Attempt = 0; Attempt < 4; ++Attempt)
	{
		if (NavSystem->GetRandomReachablePointInRadius(Start.Location, Radius, End, NavData.Get())
			&& FVector::DistSquared2D(Start.Location, End.Location) > FMath::Square(150.f))
		{
			OutTarget = End.Location;
			return true;
		}
	}
	return false;
}

FPCSPMassNavigation::EMoveResult FPCSPMassNavigation::Move(int32 Id, FTransform& Transform,
	const FVector& Target, float Speed, float Radius, float DeltaTime)
{
	if (!IsReady()) { return EMoveResult::Waiting; }
	FRoute& Route = Routes.FindOrAdd(Id);
	if (!Route.RequestedTarget.Equals(Target, 1.f))
	{
		Route = FRoute();
		Route.RequestedTarget = Target;
	}
	FVector Current = Transform.GetLocation();
	if (!Route.Path.IsValid() || !Route.Path->IsValid() || !Route.Path->IsUpToDate())
	{
		if (Now < Route.RetryTime || QueriesLeft <= 0) { return EMoveResult::Waiting; }
		--QueriesLeft;
		Route.RetryTime = Now + 0.5f + (Id % 17) * 0.03f;
		FNavLocation Start, End;
		// A bounded projection recovers starts created before dynamic tiles finished.
		// End projection stays local to the slot: never claim arrival across a wall.
		if (!NavSystem->ProjectPointToNavigation(Current, Start, FVector(600.f, 600.f, 1000.f), NavData.Get())
			|| !NavSystem->ProjectPointToNavigation(Target, End, FVector(100.f, 100.f, 500.f), NavData.Get()))
		{ return EMoveResult::Failed; }
		FPathFindingQuery Query(nullptr, *NavData.Get(), Start.Location, End.Location);
		Query.SetAllowPartialPaths(false);
		FPathFindingResult Result = NavSystem->FindPathSync(Query);
		if (!Result.IsSuccessful() || !Result.Path.IsValid() || Result.Path->IsPartial())
		{ return EMoveResult::Failed; }
		Route.Path = Result.Path;
		Route.Path->EnableRecalculationOnInvalidation(false);
		Route.NextPoint = 1;
		Current = Start.Location;
		Transform.SetLocation(Current);
		Route.ProgressPosition = Current;
		Route.LastProgressTime = Now;
	}

	const TArray<FNavPathPoint>& Points = Route.Path->GetPathPoints();
	if (Points.IsEmpty()) { return EMoveResult::Failed; }
	const float Step = Speed * DeltaTime;
	// Arrival must be both close and connected, never a teleport through a corner.
	FVector Hit;
	if (FVector::Dist2D(Current, Points.Last().Location) <= FMath::Max(20.f, Step)
		&& !NavData->Raycast(Current, Points.Last().Location, Hit, nullptr)
		&& ConstrainStep(Id, Current, Points.Last().Location, Radius).Equals(Points.Last().Location, 0.1f))
	{
		Transform.SetLocation(Points.Last().Location);
		UpdateAgent(Id, Current, Transform.GetLocation(), Radius);
		return EMoveResult::Arrived;
	}
	Route.NextPoint = FMath::Clamp(Route.NextPoint, 0, Points.Num() - 1);
	// Advance only when the next segment is visible on Recast. Separation can
	// displace an agent around a corner; it must not cut through the intervening wall.
	while (Route.NextPoint + 1 < Points.Num()
		&& FVector::Dist2D(Current, Points[Route.NextPoint].Location) < FMath::Max(80.f, Step)
		&& !NavData->Raycast(Current, Points[Route.NextPoint + 1].Location, Hit, nullptr))
	{ ++Route.NextPoint; }
	const FVector Goal = Points[Route.NextPoint].Location;
	FVector Desired = (Goal - Current).GetSafeNormal2D();
	const FVector Avoidance = Separation(Id, Current, Radius);
	// Sideways pressure breaks single-file convergence; the forward contribution
	// still slows close followers. Opposing pedestrians consistently pass right.
	const FVector Right(-Desired.Y, Desired.X, 0.f);
	const float Pressure = FMath::Max(0.f, -FVector::DotProduct(Avoidance, Desired));
	FVector Velocity = Desired * Speed + Avoidance * Speed * 1.5f
		+ Right * Speed * FMath::Min(Pressure, 0.8f);
	Velocity = Velocity.GetClampedToMaxSize(Speed * 1.2f);
	FNavLocation Start, Next;
	if (!NavSystem->ProjectPointToNavigation(Current, Start, FVector(50.f, 50.f, 250.f), NavData.Get())
		|| !NavData->FindMoveAlongSurface(Start, Current + Velocity * DeltaTime, Next))
	{
		Route.Path.Reset();
		return EMoveResult::Waiting;
	}
	Next.Location = ConstrainStep(Id, Current, Next.Location, Radius);
	const FVector ActualDelta = Next.Location - Current;
	if (ActualDelta.SizeSquared2D() > 0.01f)
	{
		Transform.SetLocation(Next.Location);
		Transform.SetRotation(ActualDelta.GetSafeNormal2D().Rotation().Quaternion());
		UpdateAgent(Id, Current, Next.Location, Radius);
	}
	if (FVector::DistSquared2D(Route.ProgressPosition, Next.Location) > FMath::Square(50.f))
	{
		Route.ProgressPosition = Next.Location;
		Route.LastProgressTime = Now;
	}
	else if (Now - Route.LastProgressTime > 5.f)
	{
		// Release the reservation and retry another target instead of freezing forever.
		return EMoveResult::Failed;
	}
	return EMoveResult::Moving;
}
