#pragma once

#include "Commandlets/Commandlet.h"
#include "PCSPSelectionOutlineMaterialCommandlet.generated.h"

/**
 * Authors `/Game/PCSP/Materials/M_PCSPSelectionOutline` and its instance, the
 * back-face-only hull the Mass spawner draws around the inspected agent.
 *
 * The crowd is GPU-animated: its pose lives in the body material's world
 * position offset, so an outline that does not share that graph would stand
 * still while the agent walked. The material is therefore duplicated from
 * AnimToTexture's `M_Body_BoneAnimation` and only its shading is rewritten -
 * unlit, masked, two-sided, with the opacity mask clipping every front face.
 * What survives is the sliver of the inflated hull that pokes past the body
 * silhouette: an outline, not an overlay.
 *
 * Run once per clone:
 *   UnrealEditor-Cmd cnzoi.uproject -run=PCSPSelectionOutlineMaterial
 * Add -Force to rebuild assets that already exist.
 */
UCLASS()
class CNZOIEDITOR_API UPCSPSelectionOutlineMaterialCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UPCSPSelectionOutlineMaterialCommandlet();
	virtual int32 Main(const FString& Params) override;
};
