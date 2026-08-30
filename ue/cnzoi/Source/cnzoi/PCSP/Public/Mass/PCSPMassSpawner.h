#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MassEntityHandle.h"
#include "PCSPMassSpawner.generated.h"

class UHierarchicalInstancedStaticMeshComponent;

/** Programmatic Mass archetype + HISM representation for 1024-agent tests. */
UCLASS()
class CNZOI_API APCSPMassSpawner : public AActor
{
	GENERATED_BODY()

public:
	APCSPMassSpawner();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="PCSP|Mass")
	int32 SpawnMassEntities();

	UFUNCTION(BlueprintCallable, Category="PCSP|Mass")
	void DestroyMassEntities();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="1", ClampMax="65536"))
	int32 EntityCount = 1024;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass")
	FVector2D SpawnExtent = FVector2D(2800.f, 2800.f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass")
	int32 RandomSeed = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="0.05"))
	float RepresentationUpdateInterval = 0.2f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Mass")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Representation;

private:
	void UpdateRepresentation();

	TArray<FMassEntityHandle> SpawnedEntities;
	float TimeUntilRepresentationUpdate = 0.f;
};
