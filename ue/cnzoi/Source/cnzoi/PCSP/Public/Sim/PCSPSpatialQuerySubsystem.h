#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "Subsystems/WorldSubsystem.h"
#include "PCSPSpatialQuerySubsystem.generated.h"

class AActor;

/**
 * POD-snapshot spatial query service for Actor-tier PCSP agents.
 *
 * The game thread only gathers immutable positions/radii and applies completed
 * index results. A worker builds a uniform grid, evaluates perception ranges,
 * and finds the three nearest neighbours without touching UObjects.
 */
UCLASS()
class CNZOI_API UPCSPSpatialQuerySubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickable() const override;
	virtual bool IsTickableInEditor() const override { return false; }

	static bool IsAsyncEnabled();

	/** Returns the last completed snapshot result. False means use legacy fallback. */
	bool GetQueryResult(const AActor* Owner, TArray<AActor*>& OutNearby,
		TArray<AActor*>& OutNearest) const;

private:
	struct FSnapshotEntry
	{
		FVector3f Position = FVector3f::ZeroVector;
		float Radius = 0.f;
	};

	struct FIndexResult
	{
		TArray<int32> Nearby;
		TArray<int32> Nearest;
	};

	struct FJobResult
	{
		TArray<FIndexResult> PerActor;
		double WorkerMicros = 0.0;
	};

	struct FActorResult
	{
		TArray<TWeakObjectPtr<AActor>> Nearby;
		TArray<TWeakObjectPtr<AActor>> Nearest;
	};

	void ApplyCompletedJob();
	void DispatchSnapshot();
	static FJobResult BuildGridResults(TArray<FSnapshotEntry> Snapshot, float CellSize);

	bool bSampling = false;
	float SecondsUntilDispatch = 0.f;
	TFuture<FJobResult> PendingFuture;
	TArray<TWeakObjectPtr<AActor>> PendingActors;
	TMap<TWeakObjectPtr<AActor>, FActorResult> CurrentResults;
};
