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
	static const FName UrgencyScore        = TEXT("UrgencyScore");
	static const FName RecentFailureCount  = TEXT("RecentFailureCount");
	static const FName SocialTargetActor   = TEXT("SocialTargetActor");
	static const FName CurrentZoneTag      = TEXT("CurrentZoneTag");
	static const FName AffordanceReserved  = TEXT("bAffordanceReserved");
}
