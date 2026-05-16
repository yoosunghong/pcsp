#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "PCSPAgentCharacter.generated.h"

class UPCSPNeedsComponent;
class UPCSPSocialContextComponent;
class UPCSPObservationComponent;
class UPCSPPersonaComponent;
class UPCSPTrajectoryLogComponent;
class UPCSPPolicySubsystem;

UCLASS()
class CNZOI_API APCSPAgentCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	APCSPAgentCharacter();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UPCSPNeedsComponent> Needs;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UPCSPSocialContextComponent> Social;

	// v3 obs component — builds the 33-dim vector consumed by PCSPPolicySubsystem
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UPCSPObservationComponent> Observation;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UPCSPPersonaComponent> Persona;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP")
	TObjectPtr<UPCSPTrajectoryLogComponent> TrajectoryLog;
};
