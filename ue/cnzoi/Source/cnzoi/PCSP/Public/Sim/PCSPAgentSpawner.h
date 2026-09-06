#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PCSPAgentSpawner.generated.h"

class APCSPAgentCharacter;
class APCSPAIController;
class APCSPMassSpawner;
class UWorldPartitionStreamingSourceComponent;


UCLASS()
class CNZOI_API APCSPAgentSpawner : public AActor
{
	GENERATED_BODY()

public:
	APCSPAgentSpawner();

	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	TSubclassOf<APCSPAgentCharacter> AgentClass;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	TSubclassOf<APCSPAIController> AIControllerClass;

	/** Actor/BT debug agents. Must be zero whenever MassEntityCount is non-zero. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn", meta=(ClampMin="0", ClampMax="128"))
	int32 AgentCount = 0;

	/** Mass simulation population. Any non-zero value selects all-Mass mode;
	 *  configured Actor agents are folded into this count to prevent mixed tiers. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn", meta=(ClampMin="0", ClampMax="65536"))
	int32 MassEntityCount = 1024;

	/** Per-run RNG seed for reproducible spawn placement (T1.3 sweep).
	 *  -1 = non-deterministic (use ambient global stream).
	 *  Overridden by CVar `pcsp.SpawnSeed` when that CVar is >= 0. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	int32 RandomSeed = -1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	float SpawnRadius = 1500.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	bool bSpawnOnNavMesh = true;

	/** Radius (UU) of the WP streaming source centred on this spawner.
	 *  Set large enough to cover the entire district so all affordance zones
	 *  are guaranteed loaded in standalone -game mode (WP only streams cells
	 *  near active sources; PIE does this automatically, -game does not). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	float StreamingSourceRadius = 50000.f;

	/** Max seconds to wait for NavMesh to finish building before spawning anyway.
	 *  In PIE this resolves in <0.5s (editor NavMesh already built). In standalone
	 *  -game the NavMesh rebuilds per WP cell and takes several seconds for zones
	 *  beyond the immediate spawn area. 30s covers the worst case. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	float SpawnDelay = 30.f;

	UFUNCTION(BlueprintCallable, Category="PCSP|Spawn")
	int32 SpawnAgents();

protected:
	bool FindSpawnLocation(FVector& OutLocation) const;

	UPROPERTY()
	TObjectPtr<UWorldPartitionStreamingSourceComponent> StreamingSource;

	UPROPERTY()
	TArray<TObjectPtr<APCSPAgentCharacter>> SpawnedAgents;

	UPROPERTY()
	TObjectPtr<APCSPMassSpawner> SpawnedMassSpawner;

	/** Explicit persona IDs to cycle across spawned agents, resolved in
	 *  BeginPlay from `pcsp.PersonaIds` / `-PCSP_PersonaIds`. Empty = default
	 *  (i % 300) + 1 assignment. */
	TArray<int32> PersonaIdOverride;

	FTimerHandle SpawnDelayHandle;
	float        SpawnWaitElapsed = 0.f;

	void PollNavMeshAndSpawn();
};
