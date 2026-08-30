#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "PCSPTypes.h"
#include "PCSPMassFragments.generated.h"

/** Marker for the lightweight PCSP background-crowd archetype. */
USTRUCT()
struct FPCSPMassAgentTag : public FMassTag
{
	GENERATED_BODY()
};

/** Stable identity used for persona lookup, deterministic staggering, and LOD. */
USTRUCT()
struct FPCSPMassPersonaFragment : public FMassFragment
{
	GENERATED_BODY()

	int32 PersonaId = 1;
	int32 StableIndex = 0;
	uint16 Cohort = 0;
};

/** Eight Mini-Inzoi-v3 needs stored inline to keep Mass chunks contiguous. */
USTRUCT()
struct FPCSPMassNeedsFragment : public FMassFragment
{
	GENERATED_BODY()

	float Values[8] = {0.8f, 0.8f, 0.8f, 0.8f, 0.8f, 0.8f, 0.8f, 0.8f};
};

/** Current PCSP semantic decision and interaction timing. */
USTRUCT()
struct FPCSPMassIntentFragment : public FMassFragment
{
	GENERATED_BODY()

	EPCSPActionType Action = EPCSPActionType::IdleReflect;
	EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::Idle;
	float NextDecisionTime = 0.f;
	float InteractionEndTime = 0.f;
};

/** Zone-level movement target for background agents; no per-entity NavMesh query. */
USTRUCT()
struct FPCSPMassMoveTargetFragment : public FMassFragment
{
	GENERATED_BODY()

	FVector Target = FVector::ZeroVector;
	float Speed = 250.f;
	bool bMoving = false;
};
