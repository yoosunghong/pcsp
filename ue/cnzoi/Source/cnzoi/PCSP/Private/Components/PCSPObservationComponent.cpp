#include "PCSPObservationComponent.h"
#include "PCSPNeedsComponent.h"
#include "PCSPSocialContextComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"

UPCSPObservationComponent::UPCSPObservationComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UPCSPObservationComponent::BeginPlay()
{
	Super::BeginPlay();
	if (AActor* Owner = GetOwner())
	{
		Needs  = Owner->FindComponentByClass<UPCSPNeedsComponent>();
		Social = Owner->FindComponentByClass<UPCSPSocialContextComponent>();
	}
	LastObservation.Init(0.f, ObservationDim);
}

const TArray<float>& UPCSPObservationComponent::BuildObservation()
{
	LastObservation.Reset();
	LastObservation.Reserve(ObservationDim);

	// Needs (8)
	if (Needs)
	{
		for (int32 i = 0; i < static_cast<int32>(EPCSPNeed::Count); ++i)
		{
			LastObservation.Add(Needs->GetNeed(static_cast<EPCSPNeed>(i)));
		}
	}

	// Time (2)
	if (UWorld* World = GetWorld())
	{
		const float T = World->GetTimeSeconds();
		const float DayLen = 60.f * 10.f; // 10-min synthetic day
		const float Phase = FMath::Fmod(T, DayLen) / DayLen;
		LastObservation.Add(FMath::Sin(Phase * 2.f * PI));
		LastObservation.Add(FMath::Cos(Phase * 2.f * PI));
	}

	// Social (5)
	if (Social)
	{
		const FPCSPSocialSummary& S = Social->GetSummary();
		LastObservation.Add(FMath::Clamp(S.NearbyCount / 10.f, 0.f, 1.f));
		LastObservation.Add(S.MeanAffinity);
		LastObservation.Add(S.MaxCompatibility);
		LastObservation.Add(S.MinCompatibility);
		LastObservation.Add(S.RecentInteractionRecency);
	}

	// Pad remaining slots reserved for zone occupancy, affordance availability,
	// routine signals, and persona memory hooks (filled in Phase 2/3).
	while (LastObservation.Num() < ObservationDim)
	{
		LastObservation.Add(0.f);
	}
	LastObservation.SetNum(ObservationDim);
	return LastObservation;
}
