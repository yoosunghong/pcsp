#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputCoreTypes.h"
#include "PCSPAgentCharacter.generated.h"

class UPCSPNeedsComponent;
class UPCSPSocialContextComponent;
class UPCSPObservationComponent;
class UPCSPPersonaComponent;
class UPCSPTrajectoryLogComponent;
class UPCSPPolicySubsystem;
class USpringArmComponent;
class UCameraComponent;

UCLASS()
class CNZOI_API APCSPAgentCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	APCSPAgentCharacter();

	virtual void NotifyActorOnClicked(FKey ButtonPressed = EKeys::LeftMouseButton) override;

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

	/** Portfolio-only observer camera. It never possesses the AI pawn. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Demo")
	TObjectPtr<USpringArmComponent> DemoCameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Demo")
	TObjectPtr<UCameraComponent> DemoFollowCamera;
};
