#include "PCSPAffordanceZone.h"
#include "PCSPInteractionPoint.h"
#include "PCSPAffordanceSubsystem.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"

APCSPAffordanceZone::APCSPAffordanceZone()
{
	PrimaryActorTick.bCanEverTick = false;
	Bounds = CreateDefaultSubobject<UBoxComponent>(TEXT("Bounds"));
	Bounds->SetBoxExtent(FVector(400.f, 400.f, 200.f));
	Bounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RootComponent = Bounds;
}

void APCSPAffordanceZone::BeginPlay()
{
	Super::BeginPlay();
	if (UWorld* World = GetWorld())
	{
		if (UPCSPAffordanceSubsystem* Sub = World->GetSubsystem<UPCSPAffordanceSubsystem>())
		{
			Sub->RegisterZone(this);
		}
	}
}

void APCSPAffordanceZone::EndPlay(const EEndPlayReason::Type Reason)
{
	if (UWorld* World = GetWorld())
	{
		if (UPCSPAffordanceSubsystem* Sub = World->GetSubsystem<UPCSPAffordanceSubsystem>())
		{
			Sub->UnregisterZone(this);
		}
	}
	Super::EndPlay(Reason);
}

void APCSPAffordanceZone::RegisterOccupant(AActor* Actor)
{
	if (Actor) { CurrentOccupants.Add(Actor); }
}

void APCSPAffordanceZone::UnregisterOccupant(AActor* Actor)
{
	if (Actor) { CurrentOccupants.Remove(Actor); }
}

APCSPInteractionPoint* APCSPAffordanceZone::FindFreeInteractionPoint() const
{
	for (APCSPInteractionPoint* P : InteractionPoints)
	{
		if (P && !P->IsReserved()) { return P; }
	}
	return nullptr;
}
