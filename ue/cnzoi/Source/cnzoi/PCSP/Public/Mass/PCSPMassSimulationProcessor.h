#pragma once

#include "CoreMinimal.h"
#include "MassEntityQuery.h"
#include "MassProcessor.h"
#include "PCSPMassSimulationProcessor.generated.h"

/**
 * Data-oriented PCSP background simulation.
 *
 * Decisions are cohort-staggered and capped per frame. Movement targets authored
 * affordance zones but follows a cheap zone-level straight-line approximation,
 * intentionally avoiding 1024 simultaneous Recast queries. Nearby/hero agents
 * continue to use the full Character + BT + NavMesh stack.
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
	void FlushTelemetry(UWorld& World, float NowSeconds);

	FMassEntityQuery EntityQuery;
	float LastTelemetryTime = 0.f;
	int64 WindowEntitiesProcessed = 0;
	int32 WindowDecisions = 0;
	int32 WindowArrivals = 0;
	double WindowPolicyMicros = 0.0;
};
