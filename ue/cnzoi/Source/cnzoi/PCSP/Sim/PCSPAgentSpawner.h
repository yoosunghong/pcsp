#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PCSPAgentSpawner.generated.h"

class APCSPAgentCharacter;
class APCSPAIController;

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn", meta=(ClampMin="1", ClampMax="128"))
	int32 AgentCount = 16;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	float SpawnRadius = 1500.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Spawn")
	bool bSpawnOnNavMesh = true;

	UFUNCTION(BlueprintCallable, Category="PCSP|Spawn")
	int32 SpawnAgents();

protected:
	bool FindSpawnLocation(FVector& OutLocation) const;

	UPROPERTY()
	TArray<TObjectPtr<APCSPAgentCharacter>> SpawnedAgents;
};
