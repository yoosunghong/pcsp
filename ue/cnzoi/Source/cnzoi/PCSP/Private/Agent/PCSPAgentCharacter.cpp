#include "PCSPAgentCharacter.h"
#include "PCSPNeedsComponent.h"
#include "PCSPSocialContextComponent.h"
#include "PCSPObservationComponent.h"
#include "PCSPPersonaComponent.h"
#include "PCSPTrajectoryLogComponent.h"

APCSPAgentCharacter::APCSPAgentCharacter()
{
	PrimaryActorTick.bCanEverTick = false;

	Needs         = CreateDefaultSubobject<UPCSPNeedsComponent>(TEXT("Needs"));
	Social        = CreateDefaultSubobject<UPCSPSocialContextComponent>(TEXT("Social"));
	Observation   = CreateDefaultSubobject<UPCSPObservationComponent>(TEXT("Observation"));
	Persona       = CreateDefaultSubobject<UPCSPPersonaComponent>(TEXT("Persona"));
	TrajectoryLog = CreateDefaultSubobject<UPCSPTrajectoryLogComponent>(TEXT("TrajectoryLog"));
}
