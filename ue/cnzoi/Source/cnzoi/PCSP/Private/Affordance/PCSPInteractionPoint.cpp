#include "PCSPInteractionPoint.h"
#include "PCSPAffordanceSubsystem.h"
#include "Engine/World.h"

APCSPInteractionPoint::APCSPInteractionPoint()
{
	PrimaryActorTick.bCanEverTick = false;
	bIsSpatiallyLoaded = false; // always loaded; must be reachable from any streaming state
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
