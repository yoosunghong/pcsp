#include "PCSPSimGameMode.h"
#include "PCSPAgentCharacter.h"
#include "PCSPAIController.h"

APCSPSimGameMode::APCSPSimGameMode()
{
	DefaultPawnClass = APCSPAgentCharacter::StaticClass();
	PlayerControllerClass = APCSPAIController::StaticClass();
}
