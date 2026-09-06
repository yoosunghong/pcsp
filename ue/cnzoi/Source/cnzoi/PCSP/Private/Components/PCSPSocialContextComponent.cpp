#include "PCSPSocialContextComponent.h"
#include "PCSPSpatialQuerySubsystem.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

UPCSPSocialContextComponent::UPCSPSocialContextComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.5f;
}

void UPCSPSocialContextComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	TimeSinceLastInteraction += DeltaTime;
	RefreshSummary();
}

void UPCSPSocialContextComponent::RegisterInteraction(AActor* Other)
{
	if (!Other) { return; }
	float& Value = Affinity.FindOrAdd(Other);
	Value = FMath::Clamp(Value + 0.05f, -1.f, 1.f);
	TimeSinceLastInteraction = 0.f;
}

void UPCSPSocialContextComponent::RefreshSummary()
{
	const AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	if (!Owner || !World) { return; }

	if (UPCSPSpatialQuerySubsystem::IsAsyncEnabled())
	{
		if (const UPCSPSpatialQuerySubsystem* Spatial =
			World->GetSubsystem<UPCSPSpatialQuerySubsystem>())
		{
			TArray<AActor*> Nearby;
			TArray<AActor*> Nearest;
			if (Spatial->GetQueryResult(Owner, Nearby, Nearest))
			{
				TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_SocialRefresh_AsyncApply);
				float SumAff = 0.f;
				float MaxComp = -TNumericLimits<float>::Max();
				float MinComp = TNumericLimits<float>::Max();
				for (AActor* Actor : Nearby)
				{
					const float Aff = Affinity.FindRef(Actor);
					SumAff += Aff;
					MaxComp = FMath::Max(MaxComp, Aff);
					MinComp = FMath::Min(MinComp, Aff);
				}
				const int32 Count = Nearby.Num();
				Summary.NearbyCount = Count;
				Summary.MeanAffinity = Count > 0 ? SumAff / Count : 0.f;
				Summary.MaxCompatibility = Count > 0 ? MaxComp : 0.f;
				Summary.MinCompatibility = Count > 0 ? MinComp : 0.f;
				Summary.RecentInteractionRecency = FMath::Exp(-TimeSinceLastInteraction / 60.f);
				return;
			}
		}
	}

	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Spatial_SocialRefresh_Legacy);

	const FVector OwnerLoc = Owner->GetActorLocation();
	const float R2 = PerceptionRadius * PerceptionRadius;

	int32 Count = 0;
	float SumAff = 0.f;
	float MaxComp = -TNumericLimits<float>::Max();
	float MinComp =  TNumericLimits<float>::Max();

	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* A = *It;
		if (!A || A == Owner) { continue; }
		if (!A->FindComponentByClass<UPCSPSocialContextComponent>()) { continue; }
		if (FVector::DistSquared(A->GetActorLocation(), OwnerLoc) > R2) { continue; }

		++Count;
		const float Aff = Affinity.Contains(A) ? Affinity[A] : 0.f;
		SumAff += Aff;
		MaxComp = FMath::Max(MaxComp, Aff);
		MinComp = FMath::Min(MinComp, Aff);
	}

	Summary.NearbyCount = Count;
	Summary.MeanAffinity = Count > 0 ? SumAff / Count : 0.f;
	Summary.MaxCompatibility = Count > 0 ? MaxComp : 0.f;
	Summary.MinCompatibility = Count > 0 ? MinComp : 0.f;
	Summary.RecentInteractionRecency = FMath::Exp(-TimeSinceLastInteraction / 60.f);
}
