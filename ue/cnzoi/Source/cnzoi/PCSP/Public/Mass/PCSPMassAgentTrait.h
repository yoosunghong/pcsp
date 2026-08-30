#pragma once

#include "CoreMinimal.h"
#include "MassEntityTraitBase.h"
#include "PCSPMassAgentTrait.generated.h"

/**
 * Editor-facing trait for the same fragments used by APCSPMassSpawner.
 * It allows the PCSP background archetype to be reused in a Mass Entity Config.
 */
UCLASS(meta=(DisplayName="PCSP Background Agent"))
class CNZOI_API UPCSPMassAgentTrait : public UMassEntityTraitBase
{
	GENERATED_BODY()

protected:
	virtual void BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
	                           const UWorld& World) const override;
};
