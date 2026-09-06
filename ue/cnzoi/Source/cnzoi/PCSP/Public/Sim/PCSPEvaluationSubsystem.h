#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "PCSPTypes.h"
#include "PCSPEvaluationSubsystem.generated.h"

struct FPCSPEvaluationResult
{
	int32 Axis = 0;
	int32 Variant = 0;
	int32 Count = 0;
	int32 Seed = 17;
	int32 Run = 0;
	FString Series;
	FString CSV;
	FString Context;
	double Seconds = 0;
	double CPUIntegral = 0;
	double CPUSeconds = 0;
	int64 Frames = 0;
	int64 Decisions = 0;
	int64 WorkerDecisions = 0;
	double PolicyMicros = 0;
	double LatencyMicros = 0;
	int64 Failures = 0;
	TArray<float> FrameTimes;
	TMap<int32, int64> Actions;
	TMap<int32, TMap<int32, int64>> PersonaActions;
	TArray<FVector> Plot; // elapsed, CPU %, FPS
	bool bComplete = false;
	FString InvalidReason;
	mutable int32 CachedP95Count = -1;
	mutable float CachedP95 = 0;
	float CPU() const { return CPUSeconds > 0 ? CPUIntegral / CPUSeconds : -1.f; }
	float FPS() const { return Seconds > 0 ? Frames / Seconds : 0.f; }
	float P95() const;
	float Entropy() const;
};

/** Survives map restarts so comparison variants start in fresh worlds. */
UCLASS()
class CNZOI_API UPCSPEvaluationSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	void SelectAxis(int32 NewAxis);
	void CycleCount();
	void CycleSeed();
	void StartVariant(int32 NewVariant);
	void ApplyPolicySettings() const;
	bool IsActorVariant() const { return Axis == 1 && Variant == 0; }
	EPCSPPolicyMode PolicyMode() const;
	int32 AsyncMode() const { return Axis == 2 && Variant == 1 ? 1 : 0; }
	int32 VariantCount() const { return Axis == 0 ? 3 : 2; }
	static FString AxisName(int32 Value);
	static FString VariantName(int32 Axis, int32 Variant);
	const FPCSPEvaluationResult* Latest(int32 ForVariant) const;
	void SaveResult(const FPCSPEvaluationResult& Result);

	int32 Axis = 0;
	int32 Variant = 0;
	int32 Count = 1024;
	int32 Seed = 17;
	float WarmupSeconds = 5.f;
	float DurationSeconds = 30.f;
	bool bConfigured = false;
	bool bShowHUD = false;
	bool bHasCamera = false;
	FVector CameraLocation = FVector::ZeroVector;
	FRotator CameraRotation = FRotator::ZeroRotator;
	float CameraFOV = 90.f;
	FString Series;
	FString Status;
	FString ReplayStatus;
	TArray<FPCSPEvaluationResult> Results;
	int32 NextRun = 0;
private:
	void NewSeries();
	TMap<int32, FString> AxisSeries;
	TMap<int32, int32> AxisCounts;
	TMap<int32, int32> AxisSeeds;
	TMap<int32, FTransform> AxisCameras;
	TMap<int32, float> AxisFOVs;
};
