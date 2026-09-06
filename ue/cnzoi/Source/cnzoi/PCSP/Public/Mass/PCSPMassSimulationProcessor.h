#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"
#include "PCSPMassNavigation.h"
#include "PCSPMassSimulationProcessor.generated.h"

/**
 * Data-oriented PCSP background simulation.
 *
 * Decisions and new Recast paths are capped per frame. Each entity follows its
 * own cached NavMesh path with spatially indexed local crowd separation.
 */
UCLASS()
class CNZOI_API UPCSPMassSimulationProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UPCSPMassSimulationProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	void FlushTelemetry(UWorld& World, float NowSeconds,
		FVector2D FrameOrigin, FVector2D FrameExtent);

	FMassEntityQuery EntityQuery;
	FPCSPMassNavigation Navigation;
	int32 DecisionCursor = 0;
	float LastTelemetryTime = 0.f;
	int64 WindowEntitiesProcessed = 0;
	int32 WindowDecisions = 0;
	int32 WindowArrivals = 0;
	int32 WindowRouteMoves = 0;
	int32 WindowRouteBlocked = 0;
	double WindowPolicyMicros = 0.0;
	TArray<FString> PendingTrajectoryLines;
	TArray<FString> PendingRouteAuditLines;
};
