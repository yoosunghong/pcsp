#include "PCSPInteractionPoint.h"
#include "PCSPAffordanceSubsystem.h"
#include "Engine/World.h"

APCSPInteractionPoint::APCSPInteractionPoint()
{
	PrimaryActorTick.bCanEverTick = false;
	#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false; // always loaded; must be reachable from any streaming state
	#endif
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
