#include "PCSPObservationComponent.h"
#include "PCSPNeedsComponent.h"
#include "PCSPSocialContextComponent.h"
#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPTypes.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/BoxComponent.h"
#include "Kismet/GameplayStatics.h"

// ---------------------------------------------------------------------------
// v3 observation layout (33 floats, 4-agent training format)
//
//  [0:2]   position_xy   — normalized to [0,1] over a 6000 UU district
//  [2]     time          — fraction of synthetic day [0,1]
//  [3:11]  needs         — 8 need values [0,1]
//  [11:19] zone_onehot   — 8 affordance categories (current zone, or all-zero)
//  [19:22] social        — (nearby_norm, mean_affinity, recency)
//  [22:24] routine       — sin/cos of a 24-h behavioural cycle
//  [24:33] neighbors     — 3 nearest agents × (rel_x, rel_y, action_norm)
// ---------------------------------------------------------------------------

static constexpr int32 V3_OBS_DIM      = 33;
static constexpr float WORLD_HALF_SIZE = 3000.f;  // district half-extent in UU
static constexpr float DAY_SECONDS     = 600.f;   // 10-min synthetic day

UPCSPObservationComponent::UPCSPObservationComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	ObservationDim = V3_OBS_DIM;
}

void UPCSPObservationComponent::BeginPlay()
{
	Super::BeginPlay();
	if (AActor* Owner = GetOwner())
	{
		Needs  = Owner->FindComponentByClass<UPCSPNeedsComponent>();
		Social = Owner->FindComponentByClass<UPCSPSocialContextComponent>();
	}
	LastObservation.Init(0.f, V3_OBS_DIM);
}

const TArray<float>& UPCSPObservationComponent::BuildObservation()
{
	LastObservation.Reset();
	LastObservation.Reserve(V3_OBS_DIM);

	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();

	// [0:2] position — normalized to [-1,1] then mapped to [0,1]
	if (Owner)
	{
		const FVector Loc = Owner->GetActorLocation();
		LastObservation.Add(FMath::Clamp((Loc.X / WORLD_HALF_SIZE + 1.f) * 0.5f, 0.f, 1.f));
		LastObservation.Add(FMath::Clamp((Loc.Y / WORLD_HALF_SIZE + 1.f) * 0.5f, 0.f, 1.f));
	}
	else
	{
		LastObservation.Add(0.5f);
		LastObservation.Add(0.5f);
	}

	// [2] time — fraction of synthetic day
	if (World)
	{
		const float T     = World->GetTimeSeconds();
		const float Phase = FMath::Fmod(T, DAY_SECONDS) / DAY_SECONDS;
		LastObservation.Add(Phase);
	}
	else
	{
		LastObservation.Add(0.f);
	}

	// [3:11] needs (8)
	if (Needs)
	{
		for (int32 i = 0; i < static_cast<int32>(EPCSPNeed::Count); ++i)
		{
			LastObservation.Add(Needs->GetNeed(static_cast<EPCSPNeed>(i)));
		}
	}
	else
	{
		for (int32 i = 0; i < 8; ++i) { LastObservation.Add(1.f); }
	}

	// [11:19] zone one-hot (8 affordance categories)
	// Which of the 8 categories does the agent's current zone belong to?
	{
		float ZoneHot[8] = {};
		if (Owner && World)
		{
			UPCSPAffordanceSubsystem* Sub = World->GetSubsystem<UPCSPAffordanceSubsystem>();
			if (Sub)
			{
				const FVector Loc = Owner->GetActorLocation();
				for (const TWeakObjectPtr<APCSPAffordanceZone>& Weak : Sub->GetAllZones())
				{
					APCSPAffordanceZone* Zone = Weak.Get();
					if (!Zone) { continue; }
					// Check if owner is inside this zone's box
					UBoxComponent* Box = Zone->Bounds;
					if (Box && Box->IsOverlappingActor(Owner))
					{
						const int32 Cat = static_cast<int32>(Zone->Category);
						// Map 11 categories → 8 slots:
						//   Eat=0, Rest=1, Work=2, Study=3, Exercise=4, Hygiene=5, Social=6
						//   Leisure/Shop/Observe/Idle → slot 7
						if (Cat >= 0 && Cat <= 6)      { ZoneHot[Cat] = 1.f; }
						else if (Cat >= 7 && Cat <= 10) { ZoneHot[7]   = 1.f; }
						break;
					}
				}
			}
		}
		for (float v : ZoneHot) { LastObservation.Add(v); }
	}

	// [19:22] social (3): nearby_count_norm, mean_affinity, recency
	if (Social)
	{
		const FPCSPSocialSummary& S = Social->GetSummary();
		LastObservation.Add(FMath::Clamp(S.NearbyCount / 10.f, 0.f, 1.f));
		LastObservation.Add(S.MeanAffinity);
		LastObservation.Add(S.RecentInteractionRecency);
	}
	else
	{
		LastObservation.Add(0.f);
		LastObservation.Add(0.f);
		LastObservation.Add(0.f);
	}

	// [22:24] routine — sin/cos of a slower 24-h behavioural cycle (3x slower than day)
	if (World)
	{
		const float T         = World->GetTimeSeconds();
		const float CycleLen  = DAY_SECONDS * 3.f;
		const float Phase2PI  = (FMath::Fmod(T, CycleLen) / CycleLen) * 2.f * PI;
		LastObservation.Add(FMath::Sin(Phase2PI));
		LastObservation.Add(FMath::Cos(Phase2PI));
	}
	else
	{
		LastObservation.Add(0.f);
		LastObservation.Add(0.f);
	}

	// [24:33] 3 nearest neighbors × 3 features (rel_x, rel_y, action_norm)
	// Collect all PCSP characters in the world, sort by distance, take closest 3.
	{
		TArray<AActor*> Others;
		if (Owner && World)
		{
			UGameplayStatics::GetAllActorsOfClass(World, ACharacter::StaticClass(), Others);
			Others.Remove(Owner);
			const FVector SelfLoc = Owner->GetActorLocation();
			Others.Sort([&](const AActor& A, const AActor& B) {
				return FVector::DistSquared(SelfLoc, A.GetActorLocation())
				     < FVector::DistSquared(SelfLoc, B.GetActorLocation());
			});
		}

		constexpr int32 MaxNeighbors = 3;
		for (int32 n = 0; n < MaxNeighbors; ++n)
		{
			if (Owner && Others.IsValidIndex(n))
			{
				const FVector RelXY = (Others[n]->GetActorLocation() - Owner->GetActorLocation());
				// Normalize by world half-size → roughly [-1,1]
				LastObservation.Add(FMath::Clamp(RelXY.X / WORLD_HALF_SIZE, -1.f, 1.f));
				LastObservation.Add(FMath::Clamp(RelXY.Y / WORLD_HALF_SIZE, -1.f, 1.f));
				// Placeholder action_norm — will be filled from BB in Phase 3+
				LastObservation.Add(0.f);
			}
			else
			{
				LastObservation.Add(0.f);
				LastObservation.Add(0.f);
				LastObservation.Add(0.f);
			}
		}
	}

	LastObservation.SetNum(V3_OBS_DIM);
	return LastObservation;
}
