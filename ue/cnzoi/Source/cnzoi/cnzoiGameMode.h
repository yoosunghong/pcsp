// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "cnzoiGameMode.generated.h"

/**
 *  Simple GameMode for a third person game
 */
UCLASS(abstract)
class AcnzoiGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	
	/** Constructor */
	AcnzoiGameMode();
};



