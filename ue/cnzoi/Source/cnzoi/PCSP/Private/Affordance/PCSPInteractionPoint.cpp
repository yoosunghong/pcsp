#include "PCSPInteractionPoint.h"
#include "PCSPAffordanceSubsystem.h"
#include "Engine/World.h"

APCSPInteractionPoint::APCSPInteractionPoint()
{
	PrimaryActorTick.bCanEverTick = false;
}

bool APCSPInteractionPoint::TryReserve(AActor* Requester)
{
	if (!Requester || Reserver.IsValid()) { return false; }
	Reserver = Requester;
	return true;
}

void APCSPInteractionPoint::Release(AActor* Requester)
{
	if (Reserver.Get() == Requester) { Reserver = nullptr; }
}
