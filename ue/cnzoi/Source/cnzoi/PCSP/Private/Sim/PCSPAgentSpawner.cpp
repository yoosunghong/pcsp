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
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"
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

	// Register a WP streaming source so standalone -game streams in every cell
	// within StreamingSourceRadius. PIE does this automatically; -game does not,
	// leaving most affordance zones unloaded and causing ~95% pathfind failures.
	StreamingSource = CreateDefaultSubobject<UWorldPartitionStreamingSourceComponent>(
		TEXT("WPStreamingSource"));
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

	// Push a single fixed-radius sphere shape so the WP source covers the whole
	// district regardless of the grid's default loading range.
	if (StreamingSource)
	{
		FStreamingSourceShape Shape;
		Shape.bUseGridLoadingRange = false;
		Shape.Radius = StreamingSourceRadius;
		StreamingSource->Shapes.Add(Shape);
	}

	UE_LOG(LogTemp, Log,
		TEXT("PCSPAgentSpawner: agents=%d seed=%d wp_radius=%.0f spawn_delay=%.1fs (CVars: spawn_seed=%d agent_count=%d)"),
		AgentCount, RandomSeed, StreamingSourceRadius, SpawnDelay, SeedOverride, CountOverride);

	// Write run_config.json immediately (not inside SpawnAgents) so the session
	// dir is labelled before the delayed spawn fires.
	const FString ConfigPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("run_config.json");
	const FString ConfigBlob = FString::Printf(
		TEXT("{\"n_agents\":%d,\"seed\":%d,\"spawn_radius\":%.1f,\"spawn_on_navmesh\":%s}\n"),
		AgentCount, RandomSeed, SpawnRadius,
		bSpawnOnNavMesh ? TEXT("true") : TEXT("false"));
	FFileHelper::SaveStringToFile(ConfigBlob, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_None);

	// In standalone -game the pre-baked NavMesh tiles for distant WP cells may
	// not be loaded when play begins — only geometry near active streaming
	// sources is present at startup. Trigger a full NavMesh rebuild so tiles
	// are generated from whatever geometry IS loaded, then poll until the build
	// finishes before spawning agents.
	// In PIE this is a no-op (IsNavigationBuilt returns true immediately because
	// the editor's pre-built navmesh is already in memory).
	if (UNavigationSystemV1* NavSys = UNavigationSystemV1::GetCurrent(GetWorld()))
	{
		UE_LOG(LogTemp, Log, TEXT("PCSPAgentSpawner: triggering NavMesh rebuild for standalone game"));
		NavSys->Build();
	}

	SpawnWaitElapsed = 0.f;
	GetWorldTimerManager().SetTimer(SpawnDelayHandle,
		FTimerDelegate::CreateWeakLambda(this, [this]() { PollNavMeshAndSpawn(); }),
		0.5f, /*bLoop=*/true);
}

void APCSPAgentSpawner::PollNavMeshAndSpawn()
{
	SpawnWaitElapsed += 0.5f;

	UNavigationSystemV1* NavSys = UNavigationSystemV1::GetCurrent(GetWorld());
	const bool bNavReady = !NavSys || !NavSys->IsNavigationBuildInProgress();

	if (bNavReady || SpawnWaitElapsed >= SpawnDelay)
	{
		GetWorldTimerManager().ClearTimer(SpawnDelayHandle);
		UE_LOG(LogTemp, Log,
			TEXT("PCSPAgentSpawner: NavMesh %s after %.1fs — spawning %d agents"),
			bNavReady ? TEXT("ready") : TEXT("timed out"), SpawnWaitElapsed, AgentCount);
		SpawnAgents();
	}
	else
	{
		UE_LOG(LogTemp, Verbose,
			TEXT("PCSPAgentSpawner: waiting for NavMesh (%.1fs / %.1fs)"),
			SpawnWaitElapsed, SpawnDelay);
	}
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
