#pragma once

#include "Commandlets/Commandlet.h"
#include "PCSPZoneLayoutCommandlet.generated.h"

/**
 * Authors the reproducible 96-zone / 592-point portfolio layout in a World
 * Partition map.  It runs outside the live MCP property serializer so every
 * external actor package is marked dirty and written through UnrealEd.
 */
UCLASS()
class CNZOIEDITOR_API UPCSPZoneLayoutCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UPCSPZoneLayoutCommandlet();
	virtual int32 Main(const FString& Params) override;
};
