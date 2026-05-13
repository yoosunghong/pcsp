#include "PCSPAgentSpawner.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAIController.h"
#include "Engine/World.h"
#include "NavigationSystem.h"

APCSPAgentSpawner::APCSPAgentSpawner()
{
	PrimaryActorTick.bCanEverTick = false;
}

void APCSPAgentSpawner::BeginPlay()
{
	Super::BeginPlay();
	SpawnAgents();
}

bool APCSPAgentSpawner::FindSpawnLocation(FVector& OutLocation) const
{
	const FVector Origin = GetActorLocation();
	if (bSpawnOnNavMesh)
	{
		if (UNavigationSystemV1* Nav = UNavigationSystemV1::GetCurrent(GetWorld()))
		{
			FNavLocation Loc;
			if (Nav->GetRandomReachablePointInRadius(Origin, SpawnRadius, Loc))
			{
				OutLocation = Loc.Location;
				return true;
			}
		}
	}
	const FVector Offset = FMath::VRand() * FMath::FRandRange(0.f, SpawnRadius);
	OutLocation = Origin + FVector(Offset.X, Offset.Y, 0.f);
	return true;
}

int32 APCSPAgentSpawner::SpawnAgents()
{
	if (!AgentClass) { return 0; }

	UWorld* World = GetWorld();
	if (!World) { return 0; }

	int32 Spawned = 0;
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

	for (int32 i = 0; i < AgentCount; ++i)
	{
		FVector Location;
		if (!FindSpawnLocation(Location)) { continue; }

		APCSPAgentCharacter* Agent = World->SpawnActor<APCSPAgentCharacter>(AgentClass, Location, FRotator::ZeroRotator, Params);
		if (!Agent) { continue; }

		if (AIControllerClass)
		{
			Agent->AIControllerClass = AIControllerClass;
			Agent->SpawnDefaultController();
		}

		SpawnedAgents.Add(Agent);
		++Spawned;
	}
	return Spawned;
}
