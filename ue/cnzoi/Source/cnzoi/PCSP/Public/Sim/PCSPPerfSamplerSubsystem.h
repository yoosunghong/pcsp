#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "PCSPPolicySubsystem.h"
#include "Sim/PCSPEvaluationSubsystem.h"
#include "PCSPPerfSamplerSubsystem.generated.h"

/** One wall-clock window, kept separate from research frame_stats.jsonl. */
struct FPCSPPerfPoint
{
	double Elapsed = 0.0;
	double Seconds = 0.0;
	int32 Frames = 0;
	float CPU = -1.f; // process CPU / logical cores; -1 means unavailable
	float FPS = 0.f;
	float FrameMs = 0.f;
};

struct FPCSPPerfRun
{
	int32 Id = 0;
	EPCSPPolicyMode Mode = EPCSPPolicyMode::HybridPCSP;
	TArray<FPCSPPerfPoint> Points;
	double RecordedSeconds = 0.0;
	double CPUSeconds = 0.0;
	double CPUIntegral = 0.0;
	int64 Frames = 0;
	float MeanCPU() const { return CPUSeconds > 0.0 ? CPUIntegral / CPUSeconds : -1.f; }
	float MeanFPS() const { return RecordedSeconds > 0.0 ? Frames / RecordedSeconds : 0.f; }
	float MeanFrameMs() const { return Frames > 0 ? RecordedSeconds * 1000.0 / Frames : 0.f; }
};

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

	/** Mode buttons and P-key transitions both create isolated recording runs. */
	void SelectMode(EPCSPPolicyMode Mode);
	const FPCSPPerfRun* LatestRun(EPCSPPolicyMode Mode) const;
	float WarmupRemaining() const;
	const FString& GetComparisonPath() const { return ComparisonPath; }
	bool HasWriteError() const { return bComparisonWriteError; }
	void RecordPolicyDecision(int32 PersonaId, EPCSPActionType Action, double ServiceMicros, double LatencyMicros, bool bWorker = false);
	const FPCSPEvaluationResult& GetEvaluationResult() const { return EvaluationResult; }
	void StopEvaluationForReplay() { FinishEvaluation(false); }
	int32 ActiveRunId() const { return NextRunId; }

	static FPCSPPerfPoint MakePoint(double Elapsed, double Seconds, int32 Frames,
		double CPUSeconds, int32 LogicalCores);

protected:
	void FlushWindow();
	void BeginComparisonRun(EPCSPPolicyMode Mode, double Now);
	void TickComparison(double Now);
	void FlushComparison(double Now);
	void AppendComparisonCSV(const FString& Line);
	static double ReadProcessCPUSeconds();
	void BeginEvaluation();
	void TickEvaluation(double Now);
	void FinishEvaluation(bool bComplete);
	void WriteEvaluationSummary();
	FPCSPEvaluationResult EvaluationResult;
	bool bEvaluationActive = false;
	bool bEvaluationStarted = false;
	bool bEvaluationCameraSet = false;
	double EvaluationReadyAt = 0;
	double EvaluationLastTick = 0;
	double EvaluationLastCPU = -1;
	double EvaluationWindowStart = 0;
	double EvaluationWindowCPU = -1;
	int64 EvaluationWindowFrames = 0;
	FIntPoint EvaluationResolution = FIntPoint::ZeroValue;
	int32 EvaluationVSync = 0;
	float EvaluationCap = 0;
	TWeakObjectPtr<AActor> EvaluationCamera;

	TArray<FPCSPPerfRun> ComparisonRuns;
	FString ComparisonPath;
	EPCSPPolicyMode RecordingMode = EPCSPPolicyMode::HybridPCSP;
	int32 NextRunId = 0;
	double WarmupUntil = 0.0;
	double ComparisonStart = 0.0;
	double WindowStart = 0.0;
	double WindowCPUStart = -1.0;
	int32 ComparisonFrames = 0;
	bool bComparisonWriteError = false;

	FTimerHandle FlushTimerHandle;
	FString      LogFilePath;

	TArray<float> WindowMs;  // last second of frame times in ms
	bool          bSampling = false;
};
