#include "PCSPAgentCharacter.h"
#include "PCSPNeedsComponent.h"
#include "PCSPSocialContextComponent.h"
#include "PCSPObservationComponent.h"
#include "PCSPPersonaComponent.h"
#include "PCSPTrajectoryLogComponent.h"
#include "PCSPDemoPlayerController.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Kismet/GameplayStatics.h"

APCSPAgentCharacter::APCSPAgentCharacter()
{
	PrimaryActorTick.bCanEverTick = false;

	Needs         = CreateDefaultSubobject<UPCSPNeedsComponent>(TEXT("Needs"));
	Social        = CreateDefaultSubobject<UPCSPSocialContextComponent>(TEXT("Social"));
	Observation   = CreateDefaultSubobject<UPCSPObservationComponent>(TEXT("Observation"));
	Persona       = CreateDefaultSubobject<UPCSPPersonaComponent>(TEXT("Persona"));
	TrajectoryLog = CreateDefaultSubobject<UPCSPTrajectoryLogComponent>(TEXT("TrajectoryLog"));

	DemoCameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("DemoCameraBoom"));
	DemoCameraBoom->SetupAttachment(GetRootComponent());
	DemoCameraBoom->TargetArmLength = 360.f;
	DemoCameraBoom->SetRelativeLocation(FVector(0.f, 0.f, 95.f));
	DemoCameraBoom->bUsePawnControlRotation = false;
	DemoCameraBoom->bEnableCameraLag = true;
	DemoCameraBoom->CameraLagSpeed = 8.f;
	DemoCameraBoom->bDoCollisionTest = true;

	DemoFollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("DemoFollowCamera"));
	DemoFollowCamera->SetupAttachment(DemoCameraBoom, USpringArmComponent::SocketName);
	DemoFollowCamera->bUsePawnControlRotation = false;
}

void APCSPAgentCharacter::NotifyActorOnClicked(FKey ButtonPressed)
{
	Super::NotifyActorOnClicked(ButtonPressed);
	if (ButtonPressed != EKeys::LeftMouseButton)
	{
		return;
	}

	if (APCSPDemoPlayerController* DemoController =
		Cast<APCSPDemoPlayerController>(UGameplayStatics::GetPlayerController(this, 0)))
	{
		DemoController->ObserveAgent(this, false);
	}
}
