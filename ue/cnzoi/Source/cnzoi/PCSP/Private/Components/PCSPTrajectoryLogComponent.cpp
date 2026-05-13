#include "PCSPTrajectoryLogComponent.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"

UPCSPTrajectoryLogComponent::UPCSPTrajectoryLogComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UPCSPTrajectoryLogComponent::RecordEntry(EPCSPActionType Action, FGameplayTag Affordance, float Reward)
{
	FPCSPTrajectoryEntry E;
	E.TimeSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	E.Location    = GetOwner() ? GetOwner()->GetActorLocation() : FVector::ZeroVector;
	E.Action      = Action;
	E.Affordance  = Affordance;
	E.Reward      = Reward;
	Entries.Add(MoveTemp(E));
}
