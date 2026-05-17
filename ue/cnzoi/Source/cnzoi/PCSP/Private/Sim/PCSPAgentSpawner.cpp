#include "PCSPAgentSpawner.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAIController.h"
#include "PCSPPersonaComponent.h"
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

	for (int32 i = 0; i < AgentCount; ++i)
	{
		FVector Location;
		if (!FindSpawnLocation(Location)) { continue; }

		// Deferred spawn so PersonaId is set BEFORE BeginPlay fires.
		// The world has already begun play (we're in our own BeginPlay), which means
		// SpawnActor would dispatch BeginPlay synchronously — components reading
		// PersonaId at that point would see an empty string (parses to default 1)
		// and would name their log files incorrectly.
		const FTransform SpawnXform(FRotator::ZeroRotator, Location);
		APCSPAgentCharacter* Agent = World->SpawnActorDeferred<APCSPAgentCharacter>(
			AgentClass, SpawnXform, /*Owner=*/nullptr, /*Instigator=*/nullptr,
			ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
		if (!Agent) { continue; }

		if (AIControllerClass) { Agent->AIControllerClass = AIControllerClass; }

		// Assign a unique 1-based persona ID so each agent uses a different embedding.
		// IDs cycle through 1..300 (the full persona set).
		if (Agent->Persona)
		{
			Agent->Persona->PersonaId = FString::FromInt((i % 300) + 1);
		}

		Agent->FinishSpawning(SpawnXform);

		// SpawnDefaultController must run after FinishSpawning so the pawn is fully
		// initialized when the AI controller possesses it.
		if (AIControllerClass) { Agent->SpawnDefaultController(); }

		SpawnedAgents.Add(Agent);
		++Spawned;
	}
	return Spawned;
}
