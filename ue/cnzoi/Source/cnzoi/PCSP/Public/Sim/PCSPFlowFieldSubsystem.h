#pragma once

#include "CoreMinimal.h"
#include "Async/Future.h"
#include "Subsystems/WorldSubsystem.h"
#include "PCSPFlowFieldSubsystem.generated.h"

/**
 * Shared, obstacle-aware route fields for the Mass background tier.
 *
 * Level actors tagged PCSP.City.Walkable supply traversable rectangles and
 * actors tagged PCSP.City.Obstacle carve inflated exclusions. One reverse
 * field is built per affordance zone, so every entity targeting that zone uses
 * the same O(1) lookup rather than issuing a NavMesh query.
 */
UCLASS()
class CNZOI_API UPCSPFlowFieldSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickable() const override;
	virtual bool IsTickableInEditor() const override { return false; }

	static bool IsEnabled();
	bool IsReady() const { return bReady; }
	bool HasAuthoredNavigation() const { return bHasAuthoredNavigation; }

	/** Next cell center, or the exact slot within the zone's clear finish area. */
	bool GetWaypointToZone(const FVector& WorldLocation, const FVector& ExactSlot,
		int32 ZoneVisualizationIndex, FVector& OutWaypoint) const;

private:
	struct FSource
	{
		int32 CellIndex = INDEX_NONE;
		FBox2D FinishBounds = FBox2D(ForceInit);
	};

	struct FBuildInput
	{
		FVector2f Origin = FVector2f::ZeroVector;
		float CellSize = 200.f;
		int32 Width = 0;
		int32 Height = 0;
		TArray<uint8> Walkable;
		TArray<float> GroundHeights;
		TArray<FBox2D> Surfaces;
		TArray<FBox2D> Obstacles;
		TMap<int32, FSource> SourcesByZone;
	};

	struct FField
	{
		TArray<FVector2f> Directions;
		FBox2D FinishBounds = FBox2D(ForceInit);
	};

	struct FBuildResult
	{
		FVector2f Origin = FVector2f::ZeroVector;
		float CellSize = 200.f;
		int32 Width = 0;
		int32 Height = 0;
		int32 WalkableCells = 0;
		TArray<float> GroundHeights;
		TArray<FBox2D> Surfaces;
		TArray<FBox2D> Obstacles;
		TMap<int32, FField> Fields;
		double WorkerMicros = 0.0;
	};

	void TryDispatchBuild();
	void ApplyCompletedBuild();
	static FBuildResult BuildFields(FBuildInput Input);

	bool bSampling = false;
	bool bBuildStarted = false;
	bool bReady = false;
	bool bHasAuthoredNavigation = false;
	float RetryDelay = 0.f;
	TFuture<FBuildResult> PendingBuild;
	FBuildResult BuiltData;

	friend class FPCSPCityRouteFieldTest;
};
