#pragma once

#include "CoreMinimal.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.generated.h"

UENUM(BlueprintType)
enum class EPCSPActionType : uint8
{
	EatQuick,
	EatSlow,
	RestAlone,
	RestWithOthers,
	FocusedWork,
	PlanningWork,
	DeepStudy,
	CasualLearning,
	ExerciseSolo,
	ExerciseSocial,
	HygieneQuick,
	HygieneCareful,
	SocializeInitiate,
	SocializeRespond,
	LeisureIndoor,
	LeisureOutdoor,
	ShopEssentials,
	BrowseArea,
	ObserveCrowd,
	IdleReflect,
	None UMETA(Hidden)
};

UENUM(BlueprintType)
enum class EPCSPAffordanceCategory : uint8
{
	Eat,
	Rest,
	Work,
	Study,
	Exercise,
	Hygiene,
	Social,
	Leisure,
	Shop,
	Observe,
	Idle,
	None UMETA(Hidden)
};

/** Shared visualization palette for NPC goal markers and affordance slots. */
namespace PCSPVisualization
{
	/** Deterministic high-contrast palette entry shared by a Zone and its targeting NPCs. */
	inline FLinearColor ZoneColor(const int32 VisualizationIndex)
	{
		if (VisualizationIndex < 0)
		{
			return FLinearColor(0.55f, 0.55f, 0.55f);
		}
		FLinearColor Base;
		switch (VisualizationIndex % 12)
		{
		case 0:  Base = FLinearColor(1.00f, 0.08f, 0.45f); break;
		case 1:  Base = FLinearColor(0.05f, 0.85f, 1.00f); break;
		case 2:  Base = FLinearColor(1.00f, 0.55f, 0.04f); break;
		case 3:  Base = FLinearColor(0.32f, 1.00f, 0.10f); break;
		case 4:  Base = FLinearColor(0.55f, 0.18f, 1.00f); break;
		case 5:  Base = FLinearColor(1.00f, 0.92f, 0.08f); break;
		case 6:  Base = FLinearColor(0.05f, 1.00f, 0.58f); break;
		case 7:  Base = FLinearColor(1.00f, 0.16f, 0.12f); break;
		case 8:  Base = FLinearColor(0.18f, 0.35f, 1.00f); break;
		case 9:  Base = FLinearColor(1.00f, 0.25f, 0.88f); break;
		case 10: Base = FLinearColor(0.08f, 0.75f, 0.62f); break;
		default: Base = FLinearColor(0.72f, 0.38f, 0.06f); break;
		}
		const float Brightness = 0.65f + 0.05f * ((VisualizationIndex / 12) % 8);
		Base.R *= Brightness;
		Base.G *= Brightness;
		Base.B *= Brightness;
		Base.A = 1.f;
		return Base;
	}

	inline FLinearColor CategoryColor(const EPCSPAffordanceCategory Category)
	{
		switch (Category)
		{
		case EPCSPAffordanceCategory::Eat:      return FLinearColor(1.00f, 0.35f, 0.08f);
		case EPCSPAffordanceCategory::Rest:     return FLinearColor(0.28f, 0.45f, 1.00f);
		case EPCSPAffordanceCategory::Work:     return FLinearColor(1.00f, 0.78f, 0.12f);
		case EPCSPAffordanceCategory::Study:    return FLinearColor(0.62f, 0.32f, 1.00f);
		case EPCSPAffordanceCategory::Exercise: return FLinearColor(1.00f, 0.12f, 0.22f);
		case EPCSPAffordanceCategory::Hygiene:  return FLinearColor(0.10f, 0.85f, 1.00f);
		case EPCSPAffordanceCategory::Social:   return FLinearColor(1.00f, 0.18f, 0.68f);
		case EPCSPAffordanceCategory::Leisure:  return FLinearColor(0.25f, 1.00f, 0.50f);
		case EPCSPAffordanceCategory::Shop:     return FLinearColor(0.72f, 0.42f, 0.16f);
		case EPCSPAffordanceCategory::Observe:  return FLinearColor(0.12f, 0.92f, 0.38f);
		case EPCSPAffordanceCategory::Idle:     return FLinearColor(0.55f, 0.55f, 0.55f);
		default:                                return FLinearColor::White;
		}
	}
}

/**
 * Phase 4 ablation modes — selected at runtime via the `pcsp.PolicyMode` CVar.
 * Logged in the trajectory `session_start` row so analysis tooling can label runs.
 *
 * HybridPCSP    : full PCSP policy (ONNX + projected persona embedding). Default.
 * BTOnly        : skip ONNX entirely, use UPCSPPolicySubsystem::NeedsHeuristic.
 *                  Tests the BT scaffold without persona conditioning.
 * HybridNoPersona: run ONNX with a zeroed persona vector. Tests how much of
 *                  per-persona behavior comes from the embedding vs. the obs.
 *
 * (HybridNoConsist and RLOnly are training-side ablations and require
 *  separately-exported ONNX models — not selectable at runtime.)
 */
UENUM(BlueprintType)
enum class EPCSPPolicyMode : uint8
{
	HybridPCSP     = 0,
	BTOnly         = 1,
	HybridNoPersona = 2,
};

UENUM(BlueprintType)
enum class EPCSPNeed : uint8
{
	Hunger,
	Sleep,
	Social,
	Leisure,
	Hygiene,
	Fitness,
	Work,
	Learning,
	Count UMETA(Hidden)
};

USTRUCT(BlueprintType)
struct FPCSPDecision
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	EPCSPActionType ActionType = EPCSPActionType::IdleReflect;

	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	FGameplayTag AffordanceTag;

	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	uint8 InteractionStyle = 0;

	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	TWeakObjectPtr<AActor> TargetAgent;

	UPROPERTY(BlueprintReadWrite, EditAnywhere)
	float UrgencyScore = 0.f;
};

namespace PCSPBlackboard
{
	// Canonical Blackboard key names. Author the Blackboard asset to match.
	static const FName DesiredActionType   = TEXT("DesiredActionType");
	static const FName DesiredAffordance   = TEXT("DesiredAffordanceTag");
	static const FName TargetActor         = TEXT("TargetActor");
	static const FName TargetLocation      = TEXT("TargetLocation");
	static const FName InteractionStyle    = TEXT("InteractionStyle");
	static const FName DesiredCategory     = TEXT("DesiredCategory");
	static const FName UrgencyScore        = TEXT("UrgencyScore");
	static const FName RecentFailureCount  = TEXT("RecentFailureCount");
	static const FName SocialTargetActor   = TEXT("SocialTargetActor");
	static const FName CurrentZoneTag      = TEXT("CurrentZoneTag");
	static const FName AffordanceReserved  = TEXT("bAffordanceReserved");
}
