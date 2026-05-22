#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "PCSPPerfSamplerSubsystem.generated.h"

/**
 * Per-frame DeltaTime sampler for T1.3 scaling-curve telemetry.
 *
 * Ticks every frame, captures DeltaTime into a rolling buffer, and on a 1 Hz timer
 * dumps {t, n_samples, mean_ms, p50_ms, p95_ms, p99_ms} as one JSONL row to
 * <session>/frame_stats.jsonl. Single writer; per-frame cost is one float append.
 */
UCLASS()
class CNZOI_API UPCSPPerfSamplerSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	// UTickableWorldSubsystem
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickable() const override { return bSampling; }
	virtual bool IsTickableInEditor() const override { return false; }

protected:
	void FlushWindow();

	FTimerHandle FlushTimerHandle;
	FString      LogFilePath;

	TArray<float> WindowMs;  // last second of frame times in ms
	bool          bSampling = false;
};
