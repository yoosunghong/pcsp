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
	bool bInferencePending = false;
};

/** Reserved semantic target; per-entity Recast paths live in the processor. */
USTRUCT()
struct FPCSPMassMoveTargetFragment : public FMassFragment
{
	GENERATED_BODY()

	FVector Target = FVector::ZeroVector;
	float Speed = 250.f;
	/** Physical separation radius, scaled with the representation at spawn. */
	float AgentRadius = 105.f;
	int16 GoalZoneVisualizationIndex = INDEX_NONE;
	int16 ReservedSlotIndex = INDEX_NONE;
	int16 LastCompletedZoneVisualizationIndex = INDEX_NONE;
	int16 FailedZoneVisualizationIndex = INDEX_NONE;
	float FailedZoneRetryTime = 0.f;
	bool bMoving = false;
	/** Target is a free-roam stroll point, not a reserved interaction slot. */
	bool bWandering = false;
};

/** Small in-chunk decision history used by the Mass-aware demo HUD. */
USTRUCT()
struct FPCSPMassHistoryFragment : public FMassFragment
{
	GENERATED_BODY()

	static constexpr int32 Capacity = 8;
	/** v3 `MAX_NOVEL_STEPS`; the widest window either routine observation needs. */
	static constexpr int32 MaxRepeatRun = 20;

	EPCSPActionType Actions[Capacity] = {};
	float Times[Capacity] = {};
	uint8 Count = 0;
	uint8 WriteIndex = 0;
	/** Consecutive repeats of the newest action, feeding obs[22:24]. */
	uint8 RepeatRun = 0;
	/** Monotonic decision count; seeds this agent's softmax draws. */
	uint32 DecisionCount = 0;

	void AddDecision(const EPCSPActionType Action, const float Time)
	{
		const bool bRepeat = Count > 0
			&& Actions[(WriteIndex + Capacity - 1) % Capacity] == Action;
		RepeatRun = bRepeat
			? static_cast<uint8>(FMath::Min<int32>(RepeatRun + 1, MaxRepeatRun)) : 0;

		++DecisionCount;
		Actions[WriteIndex] = Action;
		Times[WriteIndex] = Time;
		WriteIndex = static_cast<uint8>((WriteIndex + 1) % Capacity);
		Count = static_cast<uint8>(FMath::Min<int32>(Count + 1, Capacity));
	}
};
