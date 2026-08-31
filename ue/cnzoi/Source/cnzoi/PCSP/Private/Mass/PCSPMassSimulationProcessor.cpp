#include "PCSPMassSimulationProcessor.h"

#include "PCSPMassFragments.h"
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

static TAutoConsoleVariable<int32> CVarPCSPMassMaxDecisionsPerFrame(
	TEXT("pcsp.MassMaxDecisionsPerFrame"), 32,
	TEXT("Maximum background Mass PCSP decisions evaluated per frame."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassDecisionInterval(
	TEXT("pcsp.MassDecisionInterval"), 1.0f,
	TEXT("Minimum seconds between background Mass-agent decisions."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPMassMoveSpeed(
	TEXT("pcsp.MassMoveSpeed"), 260.f,
	TEXT("Zone-level movement speed for background Mass agents (UU/s)."),
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

	void BuildMassObservation(const FVector& Location, float Now,
		const FPCSPMassNeedsFragment& Needs, EPCSPAffordanceCategory CurrentCategory,
		int32 Population, TArray<float>& OutObservation)
	{
		OutObservation.Init(0.f, 33);
		OutObservation[0] = FMath::Clamp((Location.X / 3000.f + 1.f) * 0.5f, 0.f, 1.f);
		OutObservation[1] = FMath::Clamp((Location.Y / 3000.f + 1.f) * 0.5f, 0.f, 1.f);
		OutObservation[2] = FMath::Fmod(Now, 600.f) / 600.f;
		for (int32 Index = 0; Index < 8; ++Index) { OutObservation[3 + Index] = Needs.Values[Index]; }

		const int32 CategoryIndex = static_cast<int32>(CurrentCategory);
		if (CategoryIndex >= 0 && CategoryIndex <= 6) { OutObservation[11 + CategoryIndex] = 1.f; }
		else if (CategoryIndex >= 7 && CategoryIndex <= 10) { OutObservation[18] = 1.f; }

		OutObservation[19] = FMath::Clamp(Population / 1024.f, 0.f, 1.f);
		OutObservation[20] = 0.5f;
		const float RoutineAngle = (FMath::Fmod(Now, 1800.f) / 1800.f) * 2.f * PI;
		OutObservation[22] = FMath::Sin(RoutineAngle);
		OutObservation[23] = FMath::Cos(RoutineAngle);
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
	bRequiresGameThreadExecution = true; // NNE model instance owns reusable buffers.
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
	EntityQuery.AddTagRequirement<FPCSPMassAgentTag>(EMassFragmentPresence::All);
}

void UPCSPMassSimulationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || (World->WorldType != EWorldType::PIE && World->WorldType != EWorldType::Game)) { return; }

	UPCSPPolicySubsystem* Policy = World->GetSubsystem<UPCSPPolicySubsystem>();
	UPCSPAffordanceSubsystem* Affordances = World->GetSubsystem<UPCSPAffordanceSubsystem>();
	TArray<FPCSPMassZoneTarget> ZoneTargets;
	if (Affordances)
	{
		for (const TWeakObjectPtr<APCSPAffordanceZone>& WeakZone : Affordances->GetAllZones())
		{
			if (const APCSPAffordanceZone* Zone = WeakZone.Get())
			{
				ZoneTargets.Add({Zone->Category, Zone->GetActorLocation()});
			}
		}
	}

	const float Now = World->GetTimeSeconds();
	const float DeltaTime = FMath::Min(Context.GetDeltaTimeSeconds(), 0.1f);
	int32 DecisionsRemaining = FMath::Max(1, CVarPCSPMassMaxDecisionsPerFrame.GetValueOnGameThread());
	int32 Population = 0;
	TArray<float> Observation;
	Observation.Reserve(33);

	EntityQuery.ForEachEntityChunk(Context,
		[this, Policy, &ZoneTargets, Now, DeltaTime, &DecisionsRemaining, &Population, &Observation]
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
		const TArrayView<FTransformFragment> Transforms =
			ChunkContext.GetMutableFragmentView<FTransformFragment>();

		Population += ChunkContext.GetNumEntities();
		WindowEntitiesProcessed += ChunkContext.GetNumEntities();

		for (FMassExecutionContext::FEntityIterator It = ChunkContext.CreateEntityIterator(); It; ++It)
		{
			const FPCSPMassPersonaFragment& Persona = Personas[It];
			FPCSPMassNeedsFragment& Needs = NeedsList[It];
			FPCSPMassIntentFragment& Intent = Intents[It];
			FPCSPMassMoveTargetFragment& MoveTarget = MoveTargets[It];
			FTransform& Transform = Transforms[It].GetMutableTransform();

			for (int32 NeedIndex = 0; NeedIndex < 8; ++NeedIndex)
			{
				Needs.Values[NeedIndex] = FMath::Clamp(
					Needs.Values[NeedIndex] - NeedDecay[NeedIndex] * DeltaTime, 0.f, 1.f);
			}

			if (MoveTarget.bMoving)
			{
				const FVector Current = Transform.GetLocation();
				const FVector Delta = MoveTarget.Target - Current;
				const float Distance = Delta.Size2D();
				const float Step = MoveTarget.Speed * DeltaTime;
				if (Distance <= FMath::Max(20.f, Step))
				{
					Transform.SetTranslation(MoveTarget.Target);
					MoveTarget.bMoving = false;
					Intent.InteractionEndTime = Now + 2.f + (Persona.StableIndex % 4) * 0.25f;
					++WindowArrivals;
				}
				else if (Distance > KINDA_SMALL_NUMBER)
				{
					Transform.SetTranslation(Current + Delta.GetSafeNormal2D() * Step);
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
				Intent.NextDecisionTime = Now + 0.2f + (Persona.Cohort % 8) * 0.03f;
			}

			if (Now < Intent.NextDecisionTime || DecisionsRemaining <= 0) { continue; }
			--DecisionsRemaining;

			BuildMassObservation(Transform.GetLocation(), Now, Needs, Intent.Category,
				FMath::Max(1, Population), Observation);
			const int32 SampleCount = FMath::Max(0,
				CVarPCSPMassTrajectorySampleCount.GetValueOnGameThread());
			const bool bRecordTrajectory = Persona.StableIndex < SampleCount;
			int32 PolicyActionIndex = INDEX_NONE;
			const double PolicyStart = FPlatformTime::Seconds();
			if (Policy && Policy->IsReady())
			{
				if (bRecordTrajectory)
				{
					TArray<float> Logits;
					double IgnoredInferenceMicros = 0.0;
					Intent.Action = Policy->RunInferenceWithLogits(
						Observation, Persona.PersonaId, Logits, IgnoredInferenceMicros);
					if (Logits.Num() > 0
						&& UPCSPPolicySubsystem::GetPolicyMode() != EPCSPPolicyMode::BTOnly)
					{
						PolicyActionIndex = 0;
						for (int32 Index = 1; Index < Logits.Num(); ++Index)
						{
							if (Logits[Index] > Logits[PolicyActionIndex]) { PolicyActionIndex = Index; }
						}
					}
				}
				else
				{
					Intent.Action = Policy->RunInference(Observation, Persona.PersonaId);
				}
			}
			else
			{
				Intent.Action = SelectNeedsFallback(Needs);
			}
			WindowPolicyMicros += (FPlatformTime::Seconds() - PolicyStart) * 1e6;
			Intent.Category = UPCSPPolicySubsystem::ActionToCategory(Intent.Action);
			Intent.NextDecisionTime = Now +
				FMath::Max(0.1f, CVarPCSPMassDecisionInterval.GetValueOnGameThread());
			++WindowDecisions;

			if (bRecordTrajectory)
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

			const FPCSPMassZoneTarget* BestTarget = nullptr;
			float BestDistanceSq = TNumericLimits<float>::Max();
			for (const FPCSPMassZoneTarget& Candidate : ZoneTargets)
			{
				if (Candidate.Category != Intent.Category) { continue; }
				const float DistanceSq = FVector::DistSquared2D(Transform.GetLocation(), Candidate.Location);
				if (DistanceSq < BestDistanceSq)
				{
					BestDistanceSq = DistanceSq;
					BestTarget = &Candidate;
				}
			}

			if (BestTarget)
			{
				const float Angle = Persona.StableIndex * 2.39996323f;
				const float Radius = 120.f + (Persona.StableIndex % 16) * 22.f;
				MoveTarget.Target = BestTarget->Location +
					FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, 0.f);
				MoveTarget.Target.Z = Transform.GetLocation().Z;
				MoveTarget.Speed = FMath::Max(10.f, CVarPCSPMassMoveSpeed.GetValueOnGameThread());
				MoveTarget.bMoving = true;
			}
		}
	});

	if (Now - LastTelemetryTime >= 1.f)
	{
		FlushTelemetry(*World, Now);
		LastTelemetryTime = Now;
	}
}

void UPCSPMassSimulationProcessor::FlushTelemetry(UWorld& World, float NowSeconds)
{
	const FString Path = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("mass_stats.jsonl");
	const double MeanPolicyMicros = WindowDecisions > 0
		? WindowPolicyMicros / WindowDecisions
		: 0.0;
	const FString Line = FString::Printf(
		TEXT("{\"t\":%.3f,\"entity_updates\":%lld,\"decisions\":%d,\"arrivals\":%d,")
		TEXT("\"policy_us_mean\":%.3f,\"decision_budget_per_frame\":%d}\n"),
		NowSeconds, WindowEntitiesProcessed, WindowDecisions, WindowArrivals,
		MeanPolicyMicros, FMath::Max(1, CVarPCSPMassMaxDecisionsPerFrame.GetValueOnGameThread()));
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
	WindowDecisions = 0;
	WindowArrivals = 0;
	WindowPolicyMicros = 0.0;
}
