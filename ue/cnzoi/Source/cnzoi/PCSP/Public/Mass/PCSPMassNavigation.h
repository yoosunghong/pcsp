#pragma once

#include "CoreMinimal.h"
#include "NavigationData.h"

class UNavigationSystemV1;

/** Per-processor Recast paths and a frame snapshot for local crowd separation. */
class CNZOI_API FPCSPMassNavigation
{
public:
	enum class EMoveResult : uint8 { Waiting, Moving, Arrived, Failed };
	void BeginFrame(UWorld& World);
	void AddAgent(int32 Id, const FVector& Position, float Radius);
	void SetAgentCollisionEnabled(bool bEnabled) { bAgentCollisionEnabled = bEnabled; }
	bool IsAgentCollisionEnabled() const { return bAgentCollisionEnabled; }
	bool FindStroll(const FVector& Position, float Radius, FVector& OutTarget) const;
	EMoveResult Move(int32 Id, FTransform& Transform, const FVector& Target,
		float Speed, float Radius, float DeltaTime);
	void Forget(int32 Id) { Routes.Remove(Id); }
	bool IsReady() const { return NavSystem && NavData.IsValid(); }

	/** Equal/opposite even for exactly coincident agents. Also used at spawn. */
	FVector Separation(int32 Id, const FVector& Position, float Radius) const;
	bool HasSpace(const FVector& Position, float Radius) const;
	/** Swept-disc contact constraint; no tunneling through stationary neighbors. */
	FVector ConstrainStep(int32 Id, const FVector& Start, const FVector& End, float Radius) const;

private:
	struct FAgent { int32 Id; FVector Position; float Radius; };
	struct FRoute
	{
		FNavPathSharedPtr Path;
		FVector RequestedTarget = FVector::ZeroVector;
		FVector ProgressPosition = FVector::ZeroVector;
		float LastProgressTime = 0.f;
		float RetryTime = 0.f;
		int32 NextPoint = 1;
	};
	static constexpr float CellSize = 600.f;
	static FIntPoint Cell(const FVector& P);
	void UpdateAgent(int32 Id, const FVector& OldPosition, const FVector& Position, float Radius);
	TMap<FIntPoint, TArray<FAgent>> Cells;
	TMap<int32, FRoute> Routes;
	UNavigationSystemV1* NavSystem = nullptr;
	TWeakObjectPtr<ANavigationData> NavData;
	float Now = 0.f;
	int32 QueriesLeft = 0;
	float MaxRadius = 1.f;
	bool bAgentCollisionEnabled = true;
};
