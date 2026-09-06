#include "PCSPSelectionOutlineMaterialCommandlet.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "FileHelpers.h"
#include "IAssetTools.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialExpressionAdd.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Materials/MaterialExpressionMultiply.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionSubtract.h"
#include "Materials/MaterialExpressionTwoSidedSign.h"
#include "Materials/MaterialExpressionGetMaterialAttributes.h"
#include "Materials/MaterialExpressionSetMaterialAttributes.h"
#include "Materials/MaterialExpressionVertexNormalWS.h"
#include "Materials/MaterialAttributeDefinitionMap.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "UObject/UObjectGlobals.h"

namespace PCSPSelectionOutline
{
	constexpr TCHAR SourceMaterialPath[] =
		TEXT("/AnimToTexture/Characters/Mannequin/Materials/BoneAnimation/M_Body_BoneAnimation.M_Body_BoneAnimation");
	constexpr TCHAR SourceInstancePath[] =
		TEXT("/AnimToTexture/Characters/Mannequin/Materials/BoneAnimation/MI_Body_BoneAnimation.MI_Body_BoneAnimation");
	constexpr TCHAR DestinationPath[] = TEXT("/Game/PCSP/Materials");
	constexpr TCHAR MaterialName[] = TEXT("M_PCSPSelectionOutline");
	constexpr TCHAR InstanceName[] = TEXT("MI_PCSPSelectionOutline");
	constexpr TCHAR ColorParameter[] = TEXT("OutlineColor");
	constexpr TCHAR IntensityParameter[] = TEXT("OutlineIntensity");
	constexpr TCHAR ThicknessParameter[] = TEXT("OutlineThickness");

	const FLinearColor DefaultOutlineColor(0.10f, 1.f, 0.35f, 1.f);
	constexpr float DefaultOutlineIntensity = 12.f;

	/**
	 * Outline width in centimetres, pushed along the vertex normal.
	 *
	 * It has to happen here rather than by scaling the hull's instance transform:
	 * the crowd's pose comes from this material's world position offset, so the
	 * animated vertices land in the same place whatever the instance scale is, and
	 * an inflated transform produced no visible outline at all.
	 */
	constexpr float DefaultOutlineThickness = 2.2f;

	/**
	 * Front faces evaluate to 1 - 1 = 0 and back faces to 1 - -1 = 2, so a clip
	 * value between the two keeps the hull's interior surfaces and discards the
	 * ones that would otherwise paint over the body.
	 */
	constexpr float BackFaceClipValue = 1.f;

	/**
	 * Resolved without loading anything. A half-authored outline from an earlier run
	 * can assert inside the material expression code the moment it is deserialised,
	 * so -Force has to be able to clear it without ever opening it.
	 */
	FString PackageFileName(const TCHAR* AssetName)
	{
		const FString PackageName = FString::Printf(TEXT("%s/%s"), DestinationPath, AssetName);
		FString FileName;
		return FPackageName::TryConvertLongPackageNameToFilename(
			PackageName, FileName, FPackageName::GetAssetPackageExtension())
			? FileName : FString();
	}
}

UPCSPSelectionOutlineMaterialCommandlet::UPCSPSelectionOutlineMaterialCommandlet()
{
	IsClient = false;
	IsEditor = true;
	IsServer = false;
	LogToConsole = true;
}

int32 UPCSPSelectionOutlineMaterialCommandlet::Main(const FString& Params)
{
	using namespace PCSPSelectionOutline;

	const bool bForce = FParse::Param(*Params, TEXT("Force"));

	if (FParse::Param(*Params, TEXT("Probe")))
	{
		// Diagnostic only: reports how the source material routes its outputs, which
		// decides where the outline's shading has to be injected.
		UMaterial* Probe = LoadObject<UMaterial>(nullptr, SourceMaterialPath);
		if (!Probe)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP outline probe: source material missing."));
			return 2;
		}
		UE_LOG(LogTemp, Display, TEXT("PCSP outline probe: use_material_attributes=%s blend=%d two_sided=%d"),
			Probe->bUseMaterialAttributes ? TEXT("true") : TEXT("false"),
			static_cast<int32>(Probe->BlendMode.GetValue()), Probe->TwoSided ? 1 : 0);
		const TPair<EMaterialProperty, const TCHAR*> Properties[] = {
			{ MP_MaterialAttributes,   TEXT("MaterialAttributes") },
			{ MP_WorldPositionOffset,  TEXT("WorldPositionOffset") },
			{ MP_EmissiveColor,        TEXT("EmissiveColor") },
			{ MP_OpacityMask,          TEXT("OpacityMask") },
			{ MP_BaseColor,            TEXT("BaseColor") },
			{ MP_Normal,               TEXT("Normal") },
		};
		for (const TPair<EMaterialProperty, const TCHAR*>& Property : Properties)
		{
			UMaterialExpression* Node =
				UMaterialEditingLibrary::GetMaterialPropertyInputNode(Probe, Property.Key);
			UE_LOG(LogTemp, Display, TEXT("PCSP outline probe:   %-22s -> %s (output '%s')"),
				Property.Value,
				Node ? *Node->GetClass()->GetName() : TEXT("<none>"),
				*UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(Probe, Property.Key));
		}
		UMaterial* Built = LoadObject<UMaterial>(nullptr,
			TEXT("/Game/PCSP/Materials/M_PCSPSelectionOutline.M_PCSPSelectionOutline"));
		if (Built)
		{
			const UMaterialEditorOnlyData* BuiltData = Built->GetEditorOnlyData();
			UE_LOG(LogTemp, Display,
				TEXT("PCSP outline probe: BUILT unlit=%d masked=%d two_sided=%d clip=%.2f attributes_from=%s"),
				Built->GetShadingModels().HasShadingModel(MSM_Unlit) ? 1 : 0,
				Built->BlendMode == BLEND_Masked ? 1 : 0, Built->TwoSided ? 1 : 0,
				Built->OpacityMaskClipValue,
				BuiltData && BuiltData->MaterialAttributes.Expression
					? *BuiltData->MaterialAttributes.Expression->GetClass()->GetName() : TEXT("<none>"));
			for (UMaterialExpression* Expression : UMaterialEditingLibrary::GetMaterialExpressions(Built))
			{
				UMaterialExpressionSetMaterialAttributes* SetNode =
					Cast<UMaterialExpressionSetMaterialAttributes>(Expression);
				if (!SetNode) { continue; }
				for (int32 Index = 0; Index < SetNode->Inputs.Num(); ++Index)
				{
					UE_LOG(LogTemp, Display, TEXT("PCSP outline probe: BUILT set input[%d] <- %s"),
						Index, SetNode->Inputs[Index].Expression
							? *SetNode->Inputs[Index].Expression->GetClass()->GetName() : TEXT("<none>"));
				}
			}
		}
		for (UMaterialExpression* Expression : UMaterialEditingLibrary::GetMaterialExpressions(Probe))
		{
			UE_LOG(LogTemp, Display, TEXT("PCSP outline probe:   expression %s"),
				Expression ? *Expression->GetClass()->GetName() : TEXT("<null>"));
		}
		return 0;
	}

	// Instance first, then the material it points at: removing the parent while a
	// child still references it would leave the child with a null parent.
	TArray<FString> Existing;
	for (const TCHAR* AssetName : { InstanceName, MaterialName })
	{
		const FString FileName = PackageFileName(AssetName);
		if (!FileName.IsEmpty() && IFileManager::Get().FileExists(*FileName))
		{
			Existing.Add(FileName);
		}
	}
	if (!Existing.IsEmpty())
	{
		if (!bForce)
		{
			UE_LOG(LogTemp, Display,
				TEXT("PCSP selection outline: %s already exists; pass -Force to rebuild it."),
				DestinationPath);
			return 0;
		}
		for (const FString& FileName : Existing)
		{
			if (!IFileManager::Get().Delete(*FileName, false, true, true))
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP selection outline: could not delete '%s'."), *FileName);
				return 1;
			}
		}
	}

	UMaterial* SourceMaterial = LoadObject<UMaterial>(nullptr, SourceMaterialPath);
	UMaterialInstanceConstant* SourceInstance =
		LoadObject<UMaterialInstanceConstant>(nullptr, SourceInstancePath);
	if (!SourceMaterial || !SourceInstance)
	{
		UE_LOG(LogTemp, Error,
			TEXT("PCSP selection outline: the AnimToTexture body material is missing. "
				"Enable the AnimToTexture plugin content before running this."));
		return 2;
	}

	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>(
		TEXT("AssetTools")).Get();
	UMaterial* Outline = Cast<UMaterial>(
		AssetTools.DuplicateAsset(MaterialName, DestinationPath, SourceMaterial));
	UMaterialInstanceConstant* OutlineInstance = Cast<UMaterialInstanceConstant>(
		AssetTools.DuplicateAsset(InstanceName, DestinationPath, SourceInstance));
	if (!Outline || !OutlineInstance)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP selection outline: asset duplication failed."));
		return 3;
	}

	// Keep the duplicated vertex-animation graph exactly as it is and rewrite only
	// the shading: the hull has to move with the agent it outlines.
	Outline->Modify();
	Outline->SetShadingModel(MSM_Unlit);
	Outline->BlendMode = BLEND_Masked;
	Outline->TwoSided = true;
	Outline->OpacityMaskClipValue = BackFaceClipValue;

	UMaterialExpressionVectorParameter* Color =
		Cast<UMaterialExpressionVectorParameter>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionVectorParameter::StaticClass(), -400, -600));
	UMaterialExpressionScalarParameter* Intensity =
		Cast<UMaterialExpressionScalarParameter>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionScalarParameter::StaticClass(), -400, -500));
	UMaterialExpressionMultiply* Emissive =
		Cast<UMaterialExpressionMultiply>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionMultiply::StaticClass(), -200, -560));
	UMaterialExpressionConstant* One =
		Cast<UMaterialExpressionConstant>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionConstant::StaticClass(), -400, -380));
	UMaterialExpressionTwoSidedSign* Sign =
		Cast<UMaterialExpressionTwoSidedSign>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionTwoSidedSign::StaticClass(), -400, -300));
	UMaterialExpressionSubtract* FrontFaceMask =
		Cast<UMaterialExpressionSubtract>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionSubtract::StaticClass(), -200, -340));
	UMaterialExpressionScalarParameter* Thickness =
		Cast<UMaterialExpressionScalarParameter>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionScalarParameter::StaticClass(), -400, -140));
	UMaterialExpressionVertexNormalWS* Normal =
		Cast<UMaterialExpressionVertexNormalWS>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionVertexNormalWS::StaticClass(), -400, -60));
	UMaterialExpressionMultiply* Inflate =
		Cast<UMaterialExpressionMultiply>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionMultiply::StaticClass(), -200, -100));
	UMaterialExpressionAdd* OffsetPosition =
		Cast<UMaterialExpressionAdd>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionAdd::StaticClass(), -40, -100));
	UMaterialExpressionGetMaterialAttributes* Get =
		Cast<UMaterialExpressionGetMaterialAttributes>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionGetMaterialAttributes::StaticClass(), -400, 60));
	UMaterialExpressionSetMaterialAttributes* Set =
		Cast<UMaterialExpressionSetMaterialAttributes>(UMaterialEditingLibrary::CreateMaterialExpression(
			Outline, UMaterialExpressionSetMaterialAttributes::StaticClass(), 120, -300));
	if (!Color || !Intensity || !Emissive || !One || !Sign || !FrontFaceMask
		|| !Thickness || !Normal || !Inflate || !OffsetPosition || !Get || !Set)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP selection outline: could not create the shading nodes."));
		return 4;
	}

	Color->ParameterName = ColorParameter;
	Color->DefaultValue = DefaultOutlineColor;
	Intensity->ParameterName = IntensityParameter;
	Intensity->DefaultValue = DefaultOutlineIntensity;
	Thickness->ParameterName = ThicknessParameter;
	Thickness->DefaultValue = DefaultOutlineThickness;
	One->R = 1.f;

	bool bConnected = true;
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(Color, FString(), Emissive, TEXT("A"));
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(Intensity, FString(), Emissive, TEXT("B"));
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(One, FString(), FrontFaceMask, TEXT("A"));
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(Sign, FString(), FrontFaceMask, TEXT("B"));
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(Normal, FString(), Inflate, TEXT("A"));
	bConnected &= UMaterialEditingLibrary::ConnectMaterialExpressions(Thickness, FString(), Inflate, TEXT("B"));
	if (!bConnected)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP selection outline: could not wire the shading nodes."));
		return 5;
	}

	// AnimToTexture's body material is authored against the single Material
	// Attributes pin, so the individual EmissiveColor / OpacityMask / WPO inputs are
	// dead - writing to them compiled a material that still looked like the body.
	// Everything has to be injected into the attribute stream instead.
	UMaterialEditorOnlyData* EditorData = Outline->GetEditorOnlyData();
	if (!EditorData || !Outline->bUseMaterialAttributes || !EditorData->MaterialAttributes.Expression)
	{
		UE_LOG(LogTemp, Error,
			TEXT("PCSP selection outline: expected the source material to drive its Material "
				"Attributes pin; the outline shading has nowhere to go."));
		return 5;
	}
	UMaterialExpression* const BodyAttributes = EditorData->MaterialAttributes.Expression;
	const int32 BodyAttributesOutput = EditorData->MaterialAttributes.OutputIndex;

	// Read the animation's own offset back out so the hull can be widened *after*
	// it, keeping a constant outline width in every pose rather than one that
	// scales with the agent's height.
	// The node asserts Outputs.Num() == AttributeGetTypes.Num() + 1, so the pin list
	// has to be rebuilt alongside the attribute list, not just alongside it.
	Get->AttributeGetTypes.Reset();
	Get->AttributeGetTypes.Add(FMaterialAttributeDefinitionMap::GetID(MP_WorldPositionOffset));
	Get->Outputs.Reset();
	Get->Outputs.Add(FExpressionOutput(FName(TEXT("MaterialAttributes"))));
	Get->Outputs.Add(FExpressionOutput(
		FName(*FMaterialAttributeDefinitionMap::GetAttributeName(MP_WorldPositionOffset))));
	Get->MaterialAttributes.Connect(BodyAttributesOutput, BodyAttributes);
	// Output 0 is the whole attribute set; the requested attributes follow it.
	OffsetPosition->A.Connect(1, Get);
	OffsetPosition->B.Connect(0, Inflate);

	Set->AttributeSetTypes.Reset();
	Set->AttributeSetTypes.Add(FMaterialAttributeDefinitionMap::GetID(MP_EmissiveColor));
	Set->AttributeSetTypes.Add(FMaterialAttributeDefinitionMap::GetID(MP_OpacityMask));
	Set->AttributeSetTypes.Add(FMaterialAttributeDefinitionMap::GetID(MP_WorldPositionOffset));
	Set->Inputs.SetNum(Set->AttributeSetTypes.Num() + 1);
	Set->Inputs[0].Connect(BodyAttributesOutput, BodyAttributes);
	Set->Inputs[1].Connect(0, Emissive);
	Set->Inputs[2].Connect(0, FrontFaceMask);
	Set->Inputs[3].Connect(0, OffsetPosition);
	EditorData->MaterialAttributes.Connect(0, Set);

	// The crowd draws through instanced static meshes, and an unlit pass on a
	// material that never declared that usage compiles to the default material.
	bool bNeedsRecompile = false;
	UMaterialEditingLibrary::SetMaterialUsage(Outline, MATUSAGE_InstancedStaticMeshes, bNeedsRecompile);
	Outline->PostEditChange();
	UMaterialEditingLibrary::RecompileMaterial(Outline);

	// The instance carries AnimToTexture's bone position/rotation/weight textures;
	// reparenting keeps every override whose name the new material still exposes.
	OutlineInstance->Modify();
	UMaterialEditingLibrary::SetMaterialInstanceParent(OutlineInstance, Outline);
	UMaterialEditingLibrary::SetMaterialInstanceVectorParameterValue(
		OutlineInstance, ColorParameter, DefaultOutlineColor);
	UMaterialEditingLibrary::SetMaterialInstanceScalarParameterValue(
		OutlineInstance, IntensityParameter, DefaultOutlineIntensity);
	UMaterialEditingLibrary::SetMaterialInstanceScalarParameterValue(
		OutlineInstance, ThicknessParameter, DefaultOutlineThickness);
	UMaterialEditingLibrary::UpdateMaterialInstance(OutlineInstance);
	OutlineInstance->PostEditChange();

	FAssetRegistryModule::AssetCreated(Outline);
	FAssetRegistryModule::AssetCreated(OutlineInstance);
	Outline->MarkPackageDirty();
	OutlineInstance->MarkPackageDirty();

	if (!UEditorLoadingAndSavingUtils::SaveDirtyPackages(false, true))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP selection outline: failed to save the outline packages."));
		return 6;
	}

	UE_LOG(LogTemp, Display,
		TEXT("PCSP selection outline authored: %s/%s (unlit, masked, two-sided, back faces only)."),
		DestinationPath, InstanceName);
	return 0;
}
