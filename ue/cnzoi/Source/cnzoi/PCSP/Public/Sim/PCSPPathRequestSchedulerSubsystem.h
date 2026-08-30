#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "PCSPPathRequestSchedulerSubsystem.generated.h"

/**
 * Smooths bursts of AI MoveTo requests across frames.
 *
 * The 128-agent baseline submitted many path requests in the same frame and
 * saturated Recast's async query queue. BT tasks enqueue here, yield without
 * reserving an affordance, and consume a permit on a later frame. Requests are
 * ordered by urgency plus wait age so low-urgency agents cannot starve.
 */
UCLASS()
class CNZOI_API UPCSPPathRequestSchedulerSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickable() const override;
	virtual bool IsTickableInEditor() const override { return false; }

	/**
	 * Returns true exactly once when Agent may submit a MoveTo request.
	 * The first call normally queues the agent and returns false.
	 */
	bool TryConsumePermit(AActor* Agent, float UrgencyScore);

	/** Remove a queued/granted request when its BT task aborts. */
	void CancelRequest(AActor* Agent);

	UFUNCTION(BlueprintPure, Category="PCSP|Navigation")
	int32 GetQueuedRequestCount() const { return Requests.Num(); }

private:
	struct FRequestState
	{
		double EnqueuedAt = 0.0;
		float Urgency = 0.f;
		uint64 Serial = 0;
		bool bGranted = false;
	};

	void GrantFrameBudget();
	void FlushTelemetry();

	TMap<TWeakObjectPtr<AActor>, FRequestState> Requests;
	uint64 NextSerial = 1;
	bool bSampling = false;
	double LastFlushAt = 0.0;
	FString TelemetryPath;

	int32 WindowEnqueued = 0;
	int32 WindowGranted = 0;
	int32 WindowSubmitted = 0;
	int32 WindowCancelled = 0;
	int32 WindowPeakDepth = 0;
	TArray<float> WindowWaitMs;
};
