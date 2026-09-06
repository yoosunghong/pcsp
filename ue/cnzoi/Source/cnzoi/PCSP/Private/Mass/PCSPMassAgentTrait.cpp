#include "PCSPMassAgentTrait.h"

#include "PCSPMassFragments.h"
#include "MassCommonFragments.h"
#include "MassEntityTemplateRegistry.h"

void UPCSPMassAgentTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext,
	const UWorld& World) const
{
	BuildContext.AddFragment<FTransformFragment>();
	BuildContext.AddFragment<FPCSPMassPersonaFragment>();
	BuildContext.AddFragment<FPCSPMassNeedsFragment>();
	BuildContext.AddFragment<FPCSPMassIntentFragment>();
	BuildContext.AddFragment<FPCSPMassMoveTargetFragment>();
	BuildContext.AddFragment<FPCSPMassHistoryFragment>();
	BuildContext.AddTag<FPCSPMassAgentTag>();
}
