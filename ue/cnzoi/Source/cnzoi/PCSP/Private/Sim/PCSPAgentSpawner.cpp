#include "PCSPAgentSpawner.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAIController.h"
#include "PCSPPersonaComponent.h"
#include "PCSPTrajectoryLogComponent.h"
#include "Engine/World.h"
#include "NavigationSystem.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

// T1.3 sweep overrides — set from PIE/cmdline to vary per-run config without
// touching the placed spawner actor. Both default to -1 ("ignore, use UPROPERTY").
static TAutoConsoleVariable<int32> CVarPCSPSpawnSeed(
	TEXT("pcsp.SpawnSeed"), -1,
	TEXT("Override APCSPAgentSpawner::RandomSeed for this run (-1 = use actor value)."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPAgentCount(
	TEXT("pcsp.AgentCount"), -1,
	TEXT("Override APCSPAgentSpawner::AgentCount for this run (-1 = use actor value)."),
	ECVF_Default);

APCSPAgentSpawner::APCSPAgentSpawner()
{
	PrimaryActorTick.bCanEverTick = false;
}

void APCSPAgentSpawner::BeginPlay()
{
	Super::BeginPlay();

	// Apply overrides. Prefer cmdline switches (-PCSP_AgentCount=N / -PCSP_SpawnSeed=N)
	// because -ExecCmds CVars often run AFTER BeginPlay for the first map and would
	// be ignored here. Fall back to CVars for interactive PIE use.
	int32 SeedOverride  = CVarPCSPSpawnSeed.GetValueOnGameThread();
	int32 CountOverride = CVarPCSPAgentCount.GetValueOnGameThread();
	int32 CmdSeed = -1, CmdCount = -1;
	if (FParse::Value(FCommandLine::Get(), TEXT("PCSP_SpawnSeed="),  CmdSeed))  { SeedOverride  = CmdSeed; }
	if (FParse::Value(FCommandLine::Get(), TEXT("PCSP_AgentCount="), CmdCount)) { CountOverride = CmdCount; }
	if (SeedOverride  >= 0) { RandomSeed = SeedOverride; }
	if (CountOverride >= 1) { AgentCount = CountOverride; }

	// Seed the global FMath random stream once before any FMath::VRand /
	// GetRandomReachablePointInRadius call so the spawn pattern is reproducible.
	// Skipped when RandomSeed < 0 to preserve historical non-deterministic behavior.
	if (RandomSeed >= 0)
	{
		FMath::RandInit(RandomSeed);
	}

	UE_LOG(LogTemp, Log,
		TEXT("PCSPAgentSpawner: agents=%d seed=%d (CVars: spawn_seed=%d agent_count=%d)"),
		AgentCount, RandomSeed, SeedOverride, CountOverride);

	// One-shot run_config.json next to the per-agent jsonl files so the analyzer
	// can label each session by (agents, seed) without parsing PIE logs.
	const FString ConfigPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("run_config.json");
	const FString ConfigBlob = FString::Printf(
		TEXT("{\"n_agents\":%d,\"seed\":%d,\"spawn_radius\":%.1f,\"spawn_on_navmesh\":%s}\n"),
		AgentCount, RandomSeed, SpawnRadius,
		bSpawnOnNavMesh ? TEXT("true") : TEXT("false"));
	FFileHelper::SaveStringToFile(ConfigBlob, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_None);

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
