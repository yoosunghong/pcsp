#include "PCSPSimGameMode.h"
#include "PCSPAgentCharacter.h"
#include "Agent/PCSPDemoPlayerController.h"

APCSPSimGameMode::APCSPSimGameMode()
{
	DefaultPawnClass = APCSPAgentCharacter::StaticClass();
	PlayerControllerClass = APCSPDemoPlayerController::StaticClass();
}
