#include "PCSPMassSimulationProcessor.h"

#include "PCSPMassFragments.h"
#include "PCSPMassRuntime.h"
#include "PCSPPolicySubsystem.h"
#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPTrajectoryLogComponent.h"
#include "MassCommonFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

static TAutoConsoleVariable<int32> CVarPCSPMassMaxDecisionsPerFrame(
	TEXT("pcsp.MassMaxDecisionsPerFrame"), 32,
	TEXT("Maximum background Mass PCSP decisions evaluated per frame."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPInferenceBatchSize(
	TEXT("pcsp.InferenceBatchSize"), 32,
	TEXT("Maximum Mass ONNX requests copied into one asynchronous worker batch."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassDecisionInterval(
	TEXT("pcsp.MassDecisionInterval"), 1.0f,
	TEXT("Minimum seconds between background Mass-agent decisions."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassMoveSpeed(
	TEXT("pcsp.MassMoveSpeed"), 260.f,
	TEXT("Base movement speed at 1x body scale (UU/s); effective speed scales with body radius."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassInteractionDurationScale(
	TEXT("pcsp.MassInteractionDurationScale"), 0.35f,
	TEXT("Scale applied to authored interaction-slot durations for background Mass agents."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassWanderRadius(
	TEXT("pcsp.MassWanderRadius"), 900.f,
	TEXT("Stroll leg length (UU) for Mass agents that found no free interaction slot."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassWanderSpeed(
	TEXT("pcsp.MassWanderSpeed"), 150.f,
	TEXT("Base stroll speed at 1x body scale (UU/s); effective speed scales with body radius."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassWanderPause(
	TEXT("pcsp.MassWanderPause"), 0.5f,
	TEXT("Seconds a Mass agent waits after a stroll leg before deciding again."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPMassAgentCollision(
	TEXT("pcsp.MassAgentCollision"), 0,
	TEXT("Mass NPC-to-NPC collision/avoidance: 0=off (default), 1=local separation and swept-disc blocking."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPMassTrajectorySampleCount(
	TEXT("pcsp.MassTrajectorySampleCount"), 16,
	TEXT("Number of lowest stable-index Mass agents logged to mass_trajectories.jsonl (0 disables)."),
	ECVF_Default);

namespace
{
	struct FPCSPMassZoneTarget
	{
		EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;
		FVector Location = FVector::ZeroVector;
		TWeakObjectPtr<APCSPAffordanceZone> Zone;
		int32 VisualizationIndex = INDEX_NONE;
		TBitArray<> ClaimedSlots;
		int32 ClaimedCount = 0;
	};

	constexpr float NeedDecay[8] = {0.012f, 0.004f, 0.007f, 0.006f,
		0.008f, 0.003f, 0.009f, 0.005f};

	EPCSPActionType SelectNeedsFallback(const FPCSPMassNeedsFragment& Needs)
	{
		int32 MostUrgent = 0;
		for (int32 Index = 1; Index < 8; ++Index)
		{
			if (Needs.Values[Index] < Needs.Values[MostUrgent]) { MostUrgent = Index; }
		}
		switch (static_cast<EPCSPNeed>(MostUrgent))
		{
		case EPCSPNeed::Hunger: return EPCSPActionType::EatQuick;
		case EPCSPNeed::Sleep: return EPCSPActionType::RestAlone;
		case EPCSPNeed::Social: return EPCSPActionType::SocializeInitiate;
		case EPCSPNeed::Leisure: return EPCSPActionType::LeisureOutdoor;
		case EPCSPNeed::Hygiene: return EPCSPActionType::HygieneQuick;
		case EPCSPNeed::Fitness: return EPCSPActionType::ExerciseSolo;
		case EPCSPNeed::Work: return EPCSPActionType::FocusedWork;
		case EPCSPNeed::Learning: return EPCSPActionType::CasualLearning;
		default: return EPCSPActionType::IdleReflect;
		}
	}

	/**
	 * Maps district world space onto the unit square the policy was trained on.
	 *
	 * v3 observes position as row/col over a fixed 6x6 grid covering the whole
	 * world, so both the position observation and the neighbourhood that feeds
	 * obs[19] have to be expressed relative to the district's real extent. A
	 * literal half-size cannot do that. The 3000 uu constant that suited the first
	 * test district leaves obs[0] pinned at 1.0 for every agent on the visual city
	 * (which spans X 16k..74k), and shrinks the 3x3 neighbour block to ~0.3% of the
	 * map, so obs[19] reads ~0.003 against a training support of {0,.25,.50,.75}.
	 *
	 * Scaling the grid with the district instead puts a uniformly spread crowd at
	 * 3x3 of 6x6 cells = a quarter of the population, landing on 0.25 by
	 * construction and varying with local crowding either side of it.
	 */
	struct FPCSPMassDistrictFrame
	{
		static constexpr int32 GridSize = 6;             // MiniInzoiV3Env.grid_size
		static constexpr float LegacyHalfSize = 3000.f;

		/** Zone positions define the district; a map with none keeps the old frame. */
		void BuildFromZones(TConstArrayView<FPCSPMassZoneTarget> Zones)
		{
			FBox2D Bounds(ForceInit);
			for (const FPCSPMassZoneTarget& Zone : Zones)
			{
				Bounds += FVector2D(Zone.Location);
			}
			if (!Bounds.bIsValid) { return; }
			// A single zone, or zones in a line, would divide by zero on an axis.
			const FVector2D Size = Bounds.GetSize();
			Origin = Bounds.Min;
			Extent = FVector2D(
				Size.X > 1.f ? Size.X : 2.f * LegacyHalfSize,
				Size.Y > 1.f ? Size.Y : 2.f * LegacyHalfSize);
			if (Size.X <= 1.f) { Origin.X = Bounds.Min.X - LegacyHalfSize; }
			if (Size.Y <= 1.f) { Origin.Y = Bounds.Min.Y - LegacyHalfSize; }
		}

		/** Normalised district position in [0,1] per axis, as v3 reports row/col. */
		FVector2D ToUnit(const FVector& Location) const
		{
			return FVector2D(
				FMath::Clamp((Location.X - Origin.X) / Extent.X, 0.f, 1.f),
				FMath::Clamp((Location.Y - Origin.Y) / Extent.Y, 0.f, 1.f));
		}

		/**
		 * Grid cell, deliberately unclamped: an agent outside the district gets its
		 * own cells rather than being folded into the edge ones, which would invent
		 * neighbours for whoever is standing at the boundary.
		 */
		FIntPoint CellOf(const FVector& Location) const
		{
			return FIntPoint(
				FMath::FloorToInt((Location.X - Origin.X) / (Extent.X / GridSize)),
				FMath::FloorToInt((Location.Y - Origin.Y) / (Extent.Y / GridSize)));
		}

		FVector2D Origin = FVector2D(-LegacyHalfSize, -LegacyHalfSize);
		FVector2D Extent = FVector2D(2.f * LegacyHalfSize, 2.f * LegacyHalfSize);
	};

	/**
	 * Population-per-cell index over the district, rebuilt from entity transforms
	 * once per Execute.
	 *
	 * v3 measures social context as the share of the population standing within
	 * Chebyshev distance 1 of the agent on its 6x6 grid
	 * (`mini_inzoi_v3.py::_nearby_agents`). Reproducing that here needs only cell
	 * counts, not exact distances, so the query is nine map lookups.
	 */
	struct FPCSPMassNeighborGrid
	{
		explicit FPCSPMassNeighborGrid(const FPCSPMassDistrictFrame& InFrame) : Frame(InFrame) {}

		void Add(const FVector& Location) { ++CountsByCell.FindOrAdd(Frame.CellOf(Location)); }

		/** Population of the 3x3 cell block around Location, excluding the caller. */
		int32 CountNeighbors(const FVector& Location) const
		{
			const FIntPoint Cell = Frame.CellOf(Location);
			int32 Total = 0;
			for (int32 OffsetX = -1; OffsetX <= 1; ++OffsetX)
			{
				for (int32 OffsetY = -1; OffsetY <= 1; ++OffsetY)
				{
					if (const int32* Found =
						CountsByCell.Find(FIntPoint(Cell.X + OffsetX, Cell.Y + OffsetY)))
					{
						Total += *Found;
					}
				}
			}
			return FMath::Max(0, Total - 1);
		}

	private:
		FPCSPMassDistrictFrame Frame;
		TMap<FIntPoint, int32> CountsByCell;
	};

	void BuildMassObservation(const FVector& Location, float Now,
		const FPCSPMassNeedsFragment& Needs, const FPCSPMassIntentFragment& Intent,
		const FPCSPMassHistoryFragment& History, int32 NearbyCount, int32 Population,
		const FPCSPMassDistrictFrame& Frame, TArray<float>& OutObservation)
	{
		OutObservation.Init(0.f, 33);
		const FVector2D UnitPosition = Frame.ToUnit(Location);
		OutObservation[0] = UnitPosition.X;
		OutObservation[1] = UnitPosition.Y;
		OutObservation[2] = FMath::Fmod(Now, 600.f) / 600.f;
		for (int32 Index = 0; Index < 8; ++Index) { OutObservation[3 + Index] = Needs.Values[Index]; }

		const int32 CategoryIndex = static_cast<int32>(Intent.Category);
		if (CategoryIndex >= 0 && CategoryIndex <= 6) { OutObservation[11 + CategoryIndex] = 1.f; }
		else if (CategoryIndex >= 7 && CategoryIndex <= 10) { OutObservation[18] = 1.f; }

		// [19:22] social context, per `mini_inzoi_v3.py:96-104`: the nearby share of
		// the population, then two binary flags about the agent's OWN last action.
		// This slot used to carry `Population/1024` (a constant 1.0 at the default
		// crowd size) and a hardcoded 0.5, so it was both non-local and outside the
		// training support. Normalising the local count by the live population
		// reproduces the training ratio at any crowd size; v3 tops out at 3 of 4
		// neighbours, so clamp there rather than let a dense plaza exceed it.
		OutObservation[19] = Population > 0
			? FMath::Clamp(static_cast<float>(NearbyCount) / Population, 0.f, 0.75f)
			: 0.f;
		// v3 indices 6, 7 and 14 — socialize_initiate, socialize_respond,
		// rest_with_others. Intent still holds the previous decision here, because
		// the observation is always built before CompleteDecision overwrites it.
		OutObservation[20] = (Intent.Action == EPCSPActionType::SocializeInitiate
			|| Intent.Action == EPCSPActionType::SocializeRespond
			|| Intent.Action == EPCSPActionType::RestWithOthers) ? 1.f : 0.f;
		OutObservation[21] = Intent.Action == EPCSPActionType::SocializeRespond ? 1.f : 0.f;

		// [22:24] routine — repeat_count / MAX_REPEAT and novelty_steps /
		// MAX_NOVEL_STEPS. Both reset together in v3, so one run length drives both.
		// The previous sin/cos pair fed the model negative values, which the
		// training distribution never contains.
		OutObservation[22] = FMath::Min<float>(History.RepeatRun, 6.f) / 6.f;
		OutObservation[23] = FMath::Min<float>(History.RepeatRun,
			FPCSPMassHistoryFragment::MaxRepeatRun) / FPCSPMassHistoryFragment::MaxRepeatRun;
	}

	int32 NeedIndexForCategory(EPCSPAffordanceCategory Category)
	{
		switch (Category)
		{
		case EPCSPAffordanceCategory::Eat: return static_cast<int32>(EPCSPNeed::Hunger);
		case EPCSPAffordanceCategory::Rest: return static_cast<int32>(EPCSPNeed::Sleep);
		case EPCSPAffordanceCategory::Social: return static_cast<int32>(EPCSPNeed::Social);
		case EPCSPAffordanceCategory::Leisure:
		case EPCSPAffordanceCategory::Observe: return static_cast<int32>(EPCSPNeed::Leisure);
		case EPCSPAffordanceCategory::Hygiene: return static_cast<int32>(EPCSPNeed::Hygiene);
		case EPCSPAffordanceCategory::Exercise: return static_cast<int32>(EPCSPNeed::Fitness);
		case EPCSPAffordanceCategory::Work: return static_cast<int32>(EPCSPNeed::Work);
		case EPCSPAffordanceCategory::Study: return static_cast<int32>(EPCSPNeed::Learning);
		default: return INDEX_NONE;
		}
	}
}

UPCSPMassSimulationProcessor::UPCSPMassSimulationProcessor()
	: EntityQuery(*this)
{
	bAutoRegisterWithProcessingPhases = true;
	// Mass fragments and UObject subsystem snapshots/commits stay on GT. When
	// enabled, copied ONNX batches run on a worker and are committed next frame.
	bRequiresGameThreadExecution = true;
	ExecutionFlags = static_cast<uint8>(EProcessorExecutionFlags::AllNetModes);
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
}

void UPCSPMassSimulationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FPCSPMassPersonaFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FPCSPMassNeedsFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FPCSPMassIntentFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FPCSPMassMoveTargetFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FPCSPMassHistoryFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FPCSPMassAgentTag>(EMassFragmentPresence::All);
}

void UPCSPMassSimulationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Mass_Execute);

	UWorld* World = Context.GetWorld();
	if (!World || (World->WorldType != EWorldType::PIE && World->WorldType != EWorldType::Game)) { return; }

	UPCSPPolicySubsystem* Policy = World->GetSubsystem<UPCSPPolicySubsystem>();
	UPCSPAffordanceSubsystem* Affordances = World->GetSubsystem<UPCSPAffordanceSubsystem>();
	Navigation.BeginFrame(*World);
	Navigation.SetAgentCollisionEnabled(CVarPCSPMassAgentCollision.GetValueOnGameThread() != 0);
	TArray<FPCSPMassZoneTarget> ZoneTargets;
	TMap<int32, int32> ZoneIndexByVisualizationIndex;
	if (Affordances)
	{
		for (const TWeakObjectPtr<APCSPAffordanceZone>& WeakZone : Affordances->GetAllZones())
		{
			if (APCSPAffordanceZone* Zone = WeakZone.Get())
			{
				FPCSPMassZoneTarget& Target = ZoneTargets.AddDefaulted_GetRef();
				Target.Category = Zone->Category;
				Target.Location = Zone->GetActorLocation();
				Target.Zone = Zone;
				Target.VisualizationIndex = Zone->VisualizationIndex;
				Target.ClaimedSlots.Init(false, Zone->GetInteractionSlotCount());
				ZoneIndexByVisualizationIndex.Add(Zone->VisualizationIndex, ZoneTargets.Num() - 1);
			}
		}
	}

	const float Now = World->GetTimeSeconds();
	const float DeltaTime = FMath::Min(Context.GetDeltaTimeSeconds(), 0.1f);
	int32 DecisionsRemaining = FMath::Max(1, CVarPCSPMassMaxDecisionsPerFrame.GetValueOnGameThread());
	int32 Population = 0;
	TArray<float> Observation;
	Observation.Reserve(33);

	// Rebuild the transient reservation table from fragments before making any
	// decisions. This makes capacity deterministic even when entities span chunks.
	// The same sweep indexes crowd density, so the social observation reads a
	// whole-population snapshot taken before this frame's movement is applied.
	// Built from zone positions, which are gathered above and define the district.
	FPCSPMassDistrictFrame DistrictFrame;
	DistrictFrame.BuildFromZones(ZoneTargets);
	FPCSPMassNeighborGrid NeighborGrid(DistrictFrame);
	EntityQuery.ForEachEntityChunk(Context,
		[this, &ZoneTargets, &ZoneIndexByVisualizationIndex, &Population, &NeighborGrid]
		(FMassExecutionContext& ChunkContext)
	{
		Population += ChunkContext.GetNumEntities();
		const TArrayView<FPCSPMassMoveTargetFragment> MoveTargets =
			ChunkContext.GetMutableFragmentView<FPCSPMassMoveTargetFragment>();
		const TConstArrayView<FTransformFragment> Transforms =
			ChunkContext.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FPCSPMassPersonaFragment> Personas =
			ChunkContext.GetFragmentView<FPCSPMassPersonaFragment>();
		for (FMassExecutionContext::FEntityIterator It = ChunkContext.CreateEntityIterator(); It; ++It)
		{
			NeighborGrid.Add(Transforms[It].GetTransform().GetLocation());
			FPCSPMassMoveTargetFragment& MoveTarget = MoveTargets[It];
			if (Navigation.IsAgentCollisionEnabled())
			{
				Navigation.AddAgent(Personas[It].StableIndex,
					Transforms[It].GetTransform().GetLocation(), MoveTarget.AgentRadius);
			}
			const int32* ZoneIndex = ZoneIndexByVisualizationIndex.Find(
				MoveTarget.GoalZoneVisualizationIndex);
			if (!ZoneIndex || !ZoneTargets.IsValidIndex(*ZoneIndex)
				|| MoveTarget.ReservedSlotIndex < 0)
			{
				MoveTarget.ReservedSlotIndex = INDEX_NONE;
				continue;
			}
			FPCSPMassZoneTarget& Target = ZoneTargets[*ZoneIndex];
			APCSPAffordanceZone* Zone = Target.Zone.Get();
			const int32 SlotIndex = MoveTarget.ReservedSlotIndex;
			if (!Zone || !Target.ClaimedSlots.IsValidIndex(SlotIndex)
				|| Zone->IsInteractionSlotOccupiedByActor(SlotIndex)
				|| Target.ClaimedSlots[SlotIndex])
			{
				MoveTarget.ReservedSlotIndex = INDEX_NONE;
				MoveTarget.GoalZoneVisualizationIndex = INDEX_NONE;
				MoveTarget.bMoving = false;
				continue;
			}
			Target.ClaimedSlots[SlotIndex] = true;
			++Target.ClaimedCount;
		}
	});

	FPCSPAsyncInferenceBatchResult CompletedBatch;
	TMap<int32, FPCSPAsyncInferenceResult> CompletedByStableIndex;
	if (Policy && Policy->TryConsumeAsyncBatch(CompletedBatch))
	{
		for (const FPCSPAsyncInferenceResult& Result : CompletedBatch.Results)
		{
			CompletedByStableIndex.Add(Result.RequestId, Result);
		}
	}
	const bool bQueueAsync = Policy && Policy->CanDispatchAsyncBatch();
	const int32 AsyncBatchLimit = FMath::Max(1,
		CVarPCSPInferenceBatchSize.GetValueOnGameThread());
	if (bQueueAsync)
	{
		DecisionsRemaining = FMath::Min(DecisionsRemaining, AsyncBatchLimit);
	}
	// Rotate the admission window even if its agents are moving/not yet due.
	// Full-zone retries by low indices must not starve the rest of the population.
	const int32 DecisionWindowStart = Population > 0 ? DecisionCursor % Population : 0;
	const int32 DecisionWindowSize = FMath::Min(Population, DecisionsRemaining);
	TArray<FPCSPAsyncInferenceRequest> AsyncRequests;
	AsyncRequests.Reserve(FMath::Min(DecisionsRemaining, AsyncBatchLimit));
	const double AsyncMicrosPerResult = CompletedBatch.Results.Num() > 0
		? CompletedBatch.WorkerMicros / CompletedBatch.Results.Num()
		: 0.0;

	auto CompleteDecision = [this, &ZoneTargets, Now](
		const FPCSPMassPersonaFragment& Persona,
		FPCSPMassNeedsFragment& Needs,
		FPCSPMassIntentFragment& Intent,
		FPCSPMassMoveTargetFragment& MoveTarget,
		FPCSPMassHistoryFragment& History,
		FTransform& Transform,
		EPCSPActionType Action,
		int32 PolicyActionIndex,
		double PolicyMicros)
	{
		Intent.Action = Action;
		Intent.Category = UPCSPPolicySubsystem::ActionToCategory(Intent.Action);
		Intent.NextDecisionTime = Now +
			FMath::Max(0.1f, CVarPCSPMassDecisionInterval.GetValueOnGameThread());
		History.AddDecision(Action, Now);
		WindowPolicyMicros += PolicyMicros;
		++WindowDecisions;

		const int32 SampleCount = FMath::Max(0,
			CVarPCSPMassTrajectorySampleCount.GetValueOnGameThread());
		if (Persona.StableIndex < SampleCount)
		{
			FString NeedsJson = TEXT("[");
			for (int32 NeedIndex = 0; NeedIndex < 8; ++NeedIndex)
			{
				NeedsJson += FString::Printf(TEXT("%s%.4f"),
					NeedIndex == 0 ? TEXT("") : TEXT(","), Needs.Values[NeedIndex]);
			}
			NeedsJson += TEXT("]");
			const UEnum* ActionEnum = StaticEnum<EPCSPActionType>();
			const FString ActionName = ActionEnum
				? ActionEnum->GetNameStringByValue(static_cast<int64>(Intent.Action))
				: FString::FromInt(static_cast<int32>(Intent.Action));
			const FVector Location = Transform.GetLocation();
			PendingTrajectoryLines.Add(FString::Printf(
				TEXT("{\"t\":%.3f,\"tier\":\"mass\",\"stable_index\":%d,")
				TEXT("\"persona_id\":%d,\"policy_action_index\":%d,\"action\":\"%s\",")
				TEXT("\"pos\":[%.1f,%.1f],\"needs\":%s}"),
				Now, Persona.StableIndex, Persona.PersonaId, PolicyActionIndex,
				*ActionName, Location.X, Location.Y, *NeedsJson));
		}

		FPCSPMassZoneTarget* BestTarget = nullptr;
		int32 BestSlotIndex = INDEX_NONE;
		float BestScore = TNumericLimits<float>::Max();
		for (FPCSPMassZoneTarget& Candidate : ZoneTargets)
		{
			if (Candidate.Category != Intent.Category) { continue; }
			if (Candidate.VisualizationIndex == MoveTarget.FailedZoneVisualizationIndex
				&& Now < MoveTarget.FailedZoneRetryTime) { continue; }
			APCSPAffordanceZone* Zone = Candidate.Zone.Get();
			if (!Zone || Candidate.ClaimedCount + Zone->GetActorOccupancy() >= Zone->Capacity)
			{
				continue;
			}

			int32 CandidateSlot = INDEX_NONE;
			float CandidateSlotDistanceSq = TNumericLimits<float>::Max();
			for (int32 SlotIndex = 0; SlotIndex < Zone->GetInteractionSlotCount(); ++SlotIndex)
			{
				if (Candidate.ClaimedSlots[SlotIndex]
					|| Zone->IsInteractionSlotOccupiedByActor(SlotIndex))
				{
					continue;
				}
				const float SlotDistanceSq = FVector::DistSquared2D(
					Transform.GetLocation(), Zone->GetInteractionSlotWorldLocation(SlotIndex));
				if (SlotDistanceSq < CandidateSlotDistanceSq)
				{
					CandidateSlotDistanceSq = SlotDistanceSq;
					CandidateSlot = SlotIndex;
				}
			}
			if (CandidateSlot == INDEX_NONE) { continue; }

			const uint32 TieHash = HashCombineFast(GetTypeHash(Persona.StableIndex),
				GetTypeHash(Candidate.VisualizationIndex));
			const float Score = PCSPMassRuntime::ZoneScore(FMath::Sqrt(CandidateSlotDistanceSq),
				Candidate.ClaimedCount + Zone->GetActorOccupancy(), Zone->Capacity,
				static_cast<float>(TieHash % 101) * 0.1f)
				+ (Candidate.VisualizationIndex == MoveTarget.LastCompletedZoneVisualizationIndex ? 7500.f : 0.f);
			if (Score < BestScore)
			{
				BestScore = Score;
				BestTarget = &Candidate;
				BestSlotIndex = CandidateSlot;
			}
		}

		MoveTarget.GoalZoneVisualizationIndex = BestTarget
			? static_cast<int16>(BestTarget->VisualizationIndex) : INDEX_NONE;
		MoveTarget.ReservedSlotIndex = BestSlotIndex;
		Navigation.Forget(Persona.StableIndex);
		MoveTarget.bWandering = false;
		if (BestTarget && BestSlotIndex != INDEX_NONE)
		{
			BestTarget->ClaimedSlots[BestSlotIndex] = true;
			++BestTarget->ClaimedCount;
			MoveTarget.Target = BestTarget->Zone->GetInteractionSlotWorldLocation(BestSlotIndex);
			MoveTarget.Speed = PCSPMassRuntime::ScaledSpeed(
				CVarPCSPMassMoveSpeed.GetValueOnGameThread(), MoveTarget.AgentRadius);
			MoveTarget.bMoving = true;
		}
		else
		{
			// Waiting for capacity is a reachable NavMesh stroll, including in city maps.
			FVector Stroll;
			MoveTarget.bMoving = Navigation.FindStroll(Transform.GetLocation(),
				FMath::Max(200.f, CVarPCSPMassWanderRadius.GetValueOnGameThread()), Stroll);
			MoveTarget.bWandering = MoveTarget.bMoving;
			if (MoveTarget.bMoving)
			{
				MoveTarget.Target = Stroll;
				MoveTarget.Speed = PCSPMassRuntime::ScaledSpeed(
					CVarPCSPMassWanderSpeed.GetValueOnGameThread(), MoveTarget.AgentRadius);
			}
			else { Intent.NextDecisionTime = Now + 0.5f + (Persona.Cohort % 8) * 0.03f; }
		}
	};

	EntityQuery.ForEachEntityChunk(Context,
		[this, Policy, &ZoneTargets, Now, DeltaTime, &DecisionsRemaining,
		 &Population, &Observation, &NeighborGrid, &DistrictFrame,
		 &CompletedByStableIndex, CompletedBatch,
		 AsyncMicrosPerResult, bQueueAsync, AsyncBatchLimit, &AsyncRequests, &CompleteDecision,
		 DecisionWindowStart, DecisionWindowSize]
		(FMassExecutionContext& ChunkContext)
	{
		const TConstArrayView<FPCSPMassPersonaFragment> Personas =
			ChunkContext.GetFragmentView<FPCSPMassPersonaFragment>();
		const TArrayView<FPCSPMassNeedsFragment> NeedsList =
			ChunkContext.GetMutableFragmentView<FPCSPMassNeedsFragment>();
		const TArrayView<FPCSPMassIntentFragment> Intents =
			ChunkContext.GetMutableFragmentView<FPCSPMassIntentFragment>();
		const TArrayView<FPCSPMassMoveTargetFragment> MoveTargets =
			ChunkContext.GetMutableFragmentView<FPCSPMassMoveTargetFragment>();
		const TArrayView<FPCSPMassHistoryFragment> Histories =
			ChunkContext.GetMutableFragmentView<FPCSPMassHistoryFragment>();
		const TArrayView<FTransformFragment> Transforms =
			ChunkContext.GetMutableFragmentView<FTransformFragment>();

		WindowEntitiesProcessed += ChunkContext.GetNumEntities();

		for (FMassExecutionContext::FEntityIterator It = ChunkContext.CreateEntityIterator(); It; ++It)
		{
			const FPCSPMassPersonaFragment& Persona = Personas[It];
			FPCSPMassNeedsFragment& Needs = NeedsList[It];
			FPCSPMassIntentFragment& Intent = Intents[It];
			FPCSPMassMoveTargetFragment& MoveTarget = MoveTargets[It];
			FPCSPMassHistoryFragment& History = Histories[It];
			FTransform& Transform = Transforms[It].GetMutableTransform();
			if (FParse::Param(FCommandLine::Get(), TEXT("PCSP_CityRouteAudit"))
				&& Now - LastTelemetryTime >= 1.f)
			{
				const FVector Position = Transform.GetLocation();
				PendingRouteAuditLines.Add(FString::Printf(
					TEXT("{\"t\":%.3f,\"id\":%d,\"pos\":[%.2f,%.2f,%.2f],")
					TEXT("\"target\":[%.2f,%.2f,%.2f],\"zone\":%d,\"slot\":%d,")
					TEXT("\"speed\":%.1f,\"moving\":%s,\"interacting\":%s}"),
					Now, Persona.StableIndex, Position.X, Position.Y, Position.Z,
					MoveTarget.Target.X, MoveTarget.Target.Y, MoveTarget.Target.Z,
					MoveTarget.GoalZoneVisualizationIndex, MoveTarget.ReservedSlotIndex,
					MoveTarget.Speed,
					MoveTarget.bMoving ? TEXT("true") : TEXT("false"),
					Intent.InteractionEndTime > Now ? TEXT("true") : TEXT("false")));
			}

			for (int32 NeedIndex = 0; NeedIndex < 8; ++NeedIndex)
			{
				Needs.Values[NeedIndex] = FMath::Clamp(
					Needs.Values[NeedIndex] - NeedDecay[NeedIndex] * DeltaTime, 0.f, 1.f);
			}

			if (MoveTarget.bMoving)
			{
				const FPCSPMassNavigation::EMoveResult Result = Navigation.Move(Persona.StableIndex,
					Transform, MoveTarget.Target, MoveTarget.Speed, MoveTarget.AgentRadius, DeltaTime);
				if (Result == FPCSPMassNavigation::EMoveResult::Waiting) { continue; }
				if (Result == FPCSPMassNavigation::EMoveResult::Failed)
				{
					++WindowRouteBlocked;
					for (FPCSPMassZoneTarget& ZoneTarget : ZoneTargets)
					{
						if (ZoneTarget.VisualizationIndex == MoveTarget.GoalZoneVisualizationIndex
							&& ZoneTarget.ClaimedSlots.IsValidIndex(MoveTarget.ReservedSlotIndex)
							&& ZoneTarget.ClaimedSlots[MoveTarget.ReservedSlotIndex])
						{
							ZoneTarget.ClaimedSlots[MoveTarget.ReservedSlotIndex] = false;
							ZoneTarget.ClaimedCount = FMath::Max(0, ZoneTarget.ClaimedCount - 1);
						}
					}
					MoveTarget.FailedZoneVisualizationIndex = MoveTarget.GoalZoneVisualizationIndex;
					MoveTarget.FailedZoneRetryTime = Now + 10.f;
					MoveTarget.ReservedSlotIndex = INDEX_NONE;
					MoveTarget.GoalZoneVisualizationIndex = INDEX_NONE;
					MoveTarget.bMoving = false;
					MoveTarget.bWandering = false;
					Navigation.Forget(Persona.StableIndex);
					Intent.NextDecisionTime = Now + 0.25f + (Persona.Cohort % 8) * 0.03f;
					// An uncovered/unreachable slot must not cause a stationary retry
					// loop. Walk locally on this connected NavMesh while waiting.
					FVector Stroll;
					if (Navigation.FindStroll(Transform.GetLocation(),
						FMath::Max(200.f, CVarPCSPMassWanderRadius.GetValueOnGameThread()), Stroll))
					{
						MoveTarget.Target = Stroll;
						MoveTarget.Speed = PCSPMassRuntime::ScaledSpeed(
							CVarPCSPMassWanderSpeed.GetValueOnGameThread(), MoveTarget.AgentRadius);
						MoveTarget.bMoving = true;
						MoveTarget.bWandering = true;
					}
					continue;
				}
				++WindowRouteMoves;
				if (Result == FPCSPMassNavigation::EMoveResult::Arrived)
				{
					MoveTarget.bMoving = false;
					Navigation.Forget(Persona.StableIndex);
					if (MoveTarget.bWandering)
					{
						// No slot was claimed and no need is satisfied by strolling,
						// so skip the interaction/telemetry path entirely.
						MoveTarget.bWandering = false;
						Intent.NextDecisionTime = Now
							+ FMath::Max(0.f, CVarPCSPMassWanderPause.GetValueOnGameThread())
							+ (Persona.Cohort % 8) * 0.03f;
						continue;
					}
					float AuthoredDuration = 3.f;
					for (const FPCSPMassZoneTarget& ZoneTarget : ZoneTargets)
					{
						if (ZoneTarget.VisualizationIndex == MoveTarget.GoalZoneVisualizationIndex
							&& ZoneTarget.Zone.IsValid())
						{
							AuthoredDuration = ZoneTarget.Zone->GetInteractionSlotDuration(
								MoveTarget.ReservedSlotIndex);
							break;
						}
					}
					const float Duration = PCSPMassRuntime::InteractionDuration(AuthoredDuration,
						CVarPCSPMassInteractionDurationScale.GetValueOnGameThread(), Persona.StableIndex);
					Intent.InteractionEndTime = Now + Duration;
					++WindowArrivals;
				}
				continue;
			}

			if (Intent.InteractionEndTime > 0.f)
			{
				if (Now < Intent.InteractionEndTime) { continue; }
				const int32 NeedIndex = NeedIndexForCategory(Intent.Category);
				if (NeedIndex != INDEX_NONE)
				{
					Needs.Values[NeedIndex] = FMath::Min(1.f, Needs.Values[NeedIndex] + 0.35f);
				}
				Intent.InteractionEndTime = 0.f;
				for (FPCSPMassZoneTarget& ZoneTarget : ZoneTargets)
				{
					if (ZoneTarget.VisualizationIndex == MoveTarget.GoalZoneVisualizationIndex
						&& ZoneTarget.ClaimedSlots.IsValidIndex(MoveTarget.ReservedSlotIndex)
						&& ZoneTarget.ClaimedSlots[MoveTarget.ReservedSlotIndex])
					{
						ZoneTarget.ClaimedSlots[MoveTarget.ReservedSlotIndex] = false;
						ZoneTarget.ClaimedCount = FMath::Max(0, ZoneTarget.ClaimedCount - 1);
						break;
					}
				}
				MoveTarget.LastCompletedZoneVisualizationIndex = MoveTarget.GoalZoneVisualizationIndex;
				MoveTarget.ReservedSlotIndex = INDEX_NONE;
				MoveTarget.GoalZoneVisualizationIndex = INDEX_NONE;
				Intent.NextDecisionTime = Now + 0.2f + (Persona.Cohort % 8) * 0.03f;
			}

			if (Intent.bInferencePending)
			{
				if (const FPCSPAsyncInferenceResult* Result =
					CompletedByStableIndex.Find(Persona.StableIndex))
				{
					Intent.bInferencePending = false;
					const EPCSPActionType Action = CompletedBatch.bSuccess
						? Result->Action
						: SelectNeedsFallback(Needs);
					CompleteDecision(Persona, Needs, Intent, MoveTarget, History, Transform,
						Action,
						CompletedBatch.bSuccess ? Result->PolicyActionIndex : INDEX_NONE,
						CompletedBatch.bSuccess ? AsyncMicrosPerResult : 0.0);
				}
				continue;
			}

			if (Now < Intent.NextDecisionTime || DecisionsRemaining <= 0) { continue; }
			if (!PCSPMassRuntime::IsInDecisionWindow(Persona.StableIndex,
				DecisionWindowStart, DecisionWindowSize, Population)) { continue; }
			--DecisionsRemaining;
			BuildMassObservation(Transform.GetLocation(), Now, Needs, Intent, History,
				NeighborGrid.CountNeighbors(Transform.GetLocation()),
				FMath::Max(1, Population), DistrictFrame, Observation);

			// Stable per-agent, advancing per decision: two neighbours never draw the
			// same sample, and replaying the same decision sequence reproduces the run.
			const int32 DecisionSeed = static_cast<int32>(HashCombineFast(
				GetTypeHash(Persona.StableIndex), GetTypeHash(History.DecisionCount)));

			if (bQueueAsync && AsyncRequests.Num() < AsyncBatchLimit)
			{
				FPCSPAsyncInferenceRequest& Request = AsyncRequests.AddDefaulted_GetRef();
				Request.RequestId = Persona.StableIndex;
				Request.PersonaId = Persona.PersonaId;
				Request.DecisionSeed = DecisionSeed;
				Request.Observation = Observation;
				Intent.bInferencePending = true;
				continue;
			}

			const int32 SampleCount = FMath::Max(0,
				CVarPCSPMassTrajectorySampleCount.GetValueOnGameThread());
			const bool bRecordTrajectory = Persona.StableIndex < SampleCount;
			int32 PolicyActionIndex = INDEX_NONE;
			EPCSPActionType Action = EPCSPActionType::None;
			const double PolicyStart = FPlatformTime::Seconds();
			{
				TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_Mass_PolicyDecision_Sync);
				if (Policy && Policy->IsReady())
				{
					if (bRecordTrajectory)
					{
						TArray<float> Logits;
						double IgnoredInferenceMicros = 0.0;
						// Take the index the policy actually selected. Re-deriving argmax
						// here would mislabel every sampled decision that is not the mode.
						Action = Policy->RunInferenceWithLogits(
							Observation, Persona.PersonaId, Logits, IgnoredInferenceMicros,
							DecisionSeed, &PolicyActionIndex);
					}
					else
					{
						Action = Policy->RunInference(Observation, Persona.PersonaId, DecisionSeed);
					}
				}
				else
				{
					Action = SelectNeedsFallback(Needs);
				}
			}
			CompleteDecision(Persona, Needs, Intent, MoveTarget, History, Transform,
				Action, PolicyActionIndex, (FPlatformTime::Seconds() - PolicyStart) * 1e6);
		}
	});
	DecisionCursor = (DecisionWindowStart + DecisionWindowSize) % FMath::Max(1, Population);

	for (FPCSPMassZoneTarget& ZoneTarget : ZoneTargets)
	{
		if (APCSPAffordanceZone* Zone = ZoneTarget.Zone.Get())
		{
			Zone->SetMassOccupancy(ZoneTarget.ClaimedCount);
		}
	}

	if (AsyncRequests.Num() > 0)
	{
		Policy->DispatchAsyncBatch(MoveTemp(AsyncRequests));
	}

	if (Now - LastTelemetryTime >= 1.f)
	{
		FlushTelemetry(*World, Now, DistrictFrame.Origin, DistrictFrame.Extent);
		LastTelemetryTime = Now;
	}
}

void UPCSPMassSimulationProcessor::FlushTelemetry(UWorld& World, float NowSeconds,
	const FVector2D FrameOrigin, const FVector2D FrameExtent)
{
	const FString Path = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("mass_stats.jsonl");
	const double MeanPolicyMicros = WindowDecisions > 0
		? WindowPolicyMicros / WindowDecisions
		: 0.0;
	const FString Line = FString::Printf(
		TEXT("{\"t\":%.3f,\"entity_updates\":%lld,\"decisions\":%d,\"arrivals\":%d,")
		TEXT("\"policy_us_mean\":%.3f,\"decision_budget_per_frame\":%d,")
		TEXT("\"route_moves\":%d,\"route_blocked\":%d,")
		// Frame the position and neighbour observations are expressed in, so
		// offline analysis can reconstruct obs[0], obs[1] and obs[19] exactly
		// from the positions in mass_trajectories.jsonl.
		TEXT("\"district_frame\":[%.1f,%.1f,%.1f,%.1f]}\n"),
		NowSeconds, WindowEntitiesProcessed, WindowDecisions, WindowArrivals,
		MeanPolicyMicros, FMath::Max(1, CVarPCSPMassMaxDecisionsPerFrame.GetValueOnGameThread()),
		WindowRouteMoves, WindowRouteBlocked,
		FrameOrigin.X, FrameOrigin.Y, FrameExtent.X, FrameExtent.Y);
	FFileHelper::SaveStringToFile(Line, *Path,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead);

	if (PendingTrajectoryLines.Num() > 0)
	{
		FString TrajectoryBlob;
		for (const FString& TrajectoryLine : PendingTrajectoryLines)
		{
			TrajectoryBlob += TrajectoryLine;
			TrajectoryBlob += TEXT("\n");
		}
		const FString TrajectoryPath = UPCSPTrajectoryLogComponent::GetSessionDir()
			/ TEXT("mass_trajectories.jsonl");
		if (FFileHelper::SaveStringToFile(TrajectoryBlob, *TrajectoryPath,
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
			&IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead))
		{
			PendingTrajectoryLines.Reset();
		}
	}

	WindowEntitiesProcessed = 0;
	if (!PendingRouteAuditLines.IsEmpty())
	{
		const FString AuditPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("mass_routes.jsonl");
		const FString AuditText = FString::Join(PendingRouteAuditLines, TEXT("\n")) + TEXT("\n");
		FFileHelper::SaveStringToFile(AuditText, *AuditPath,
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
			&IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead);
		PendingRouteAuditLines.Reset();
	}
	WindowRouteMoves = 0;
	WindowRouteBlocked = 0;
	WindowDecisions = 0;
	WindowArrivals = 0;
	WindowPolicyMicros = 0.0;
}
