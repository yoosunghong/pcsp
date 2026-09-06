#include "PCSPPolicySubsystem.h"
#include "PCSPPersonaCache.h"
#include "NNERuntimeCPU.h"
#include "NNEModelData.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/IConsoleManager.h"
#include "Math/RandomStream.h"
#include "Async/Async.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "Sim/PCSPPerfSamplerSubsystem.h"
#include "Misc/ScopeExit.h"

// `pcsp.PolicyMode` selects the Phase 4 runtime ablation at inference time.
// 0=HybridPCSP (default), 1=BTOnly, 2=HybridNoPersona.
// Switch between runs from PIE console (`pcsp.PolicyMode 1`) — no rebuild needed.
static TAutoConsoleVariable<int32> CVarPCSPPolicyMode(
	TEXT("pcsp.PolicyMode"),
	0,
	TEXT("PCSP policy ablation mode: 0=HybridPCSP, 1=BTOnly, 2=HybridNoPersona"),
	ECVF_Default);

// The policy is trained as a stochastic categorical, and its optimisation target
// is the sampled distribution, not its mode. Taking argmax at runtime is a
// silent change of policy: it costs the full checkpoint ~0.51 nats of action
// entropy versus ~0.26 for the ablations, because the full model is deliberately
// less certain per decision. Sampling is therefore the faithful default.
static TAutoConsoleVariable<int32> CVarPCSPPolicySampling(
	TEXT("pcsp.PolicySampling"),
	1,
	TEXT("Action selection from policy logits: 1=draw from the softmax (as trained), 0=argmax."),
	ECVF_Default);

static TAutoConsoleVariable<float> CVarPCSPPolicyTemperature(
	TEXT("pcsp.PolicyTemperature"),
	1.0f,
	TEXT("Softmax temperature used when pcsp.PolicySampling is 1. "
	     "Below 1 sharpens toward argmax; above 1 flattens toward uniform."),
	ECVF_Default);

static TAutoConsoleVariable<int32> CVarPCSPAsyncInference(
	TEXT("pcsp.AsyncInference"),
	0,
	TEXT("Run Mass-tier ONNX inference as a dynamic batch on a worker thread (0=sync, 1=async)."),
	ECVF_Default);

EPCSPPolicyMode UPCSPPolicySubsystem::GetPolicyMode()
{
	const int32 V = CVarPCSPPolicyMode.GetValueOnAnyThread();
	if (V == 1) return EPCSPPolicyMode::BTOnly;
	if (V == 2) return EPCSPPolicyMode::HybridNoPersona;
	return EPCSPPolicyMode::HybridPCSP;
}

FString UPCSPPolicySubsystem::PolicyModeName(EPCSPPolicyMode Mode)
{
	switch (Mode)
	{
	case EPCSPPolicyMode::BTOnly:          return TEXT("BTOnly");
	case EPCSPPolicyMode::HybridNoPersona: return TEXT("HybridNoPersona");
	case EPCSPPolicyMode::HybridPCSP:
	default:                                return TEXT("HybridPCSP");
	}
}

bool UPCSPPolicySubsystem::IsSamplingEnabled()
{
	return CVarPCSPPolicySampling.GetValueOnAnyThread() != 0;
}

FString UPCSPPolicySubsystem::ActionSelectionName()
{
	if (!IsSamplingEnabled()) { return TEXT("argmax"); }
	return FString::Printf(TEXT("softmax_sample@T%.2f"),
		CVarPCSPPolicyTemperature.GetValueOnAnyThread());
}

int32 UPCSPPolicySubsystem::SelectActionIndex(const TConstArrayView<float> Logits,
	const int32 DecisionSeed)
{
	if (Logits.IsEmpty()) { return INDEX_NONE; }

	int32 BestIndex = 0;
	for (int32 Index = 1; Index < Logits.Num(); ++Index)
	{
		if (Logits[Index] > Logits[BestIndex]) { BestIndex = Index; }
	}
	if (!IsSamplingEnabled()) { return BestIndex; }

	// Shift by the max before exponentiating; raw logits overflow expf otherwise.
	const float Temperature = FMath::Max(KINDA_SMALL_NUMBER,
		CVarPCSPPolicyTemperature.GetValueOnAnyThread());
	const float MaxLogit = Logits[BestIndex];
	TArray<float, TInlineAllocator<32>> Cumulative;
	Cumulative.SetNumUninitialized(Logits.Num());
	float Total = 0.f;
	for (int32 Index = 0; Index < Logits.Num(); ++Index)
	{
		Total += FMath::Exp((Logits[Index] - MaxLogit) / Temperature);
		Cumulative[Index] = Total;
	}
	// A zeroed logit row (BTOnly's placeholder) or a non-finite sum has no
	// distribution to draw from; fall back rather than returning a bogus index.
	if (!(Total > 0.f) || !FMath::IsFinite(Total)) { return BestIndex; }

	// A local stream keeps this a pure function of the seed, so the worker thread
	// and the game thread agree and a run stays reproducible.
	FRandomStream Stream(DecisionSeed);
	const float Draw = Stream.FRand() * Total;
	for (int32 Index = 0; Index < Logits.Num(); ++Index)
	{
		if (Draw <= Cumulative[Index]) { return Index; }
	}
	return Logits.Num() - 1;
}

FString UPCSPPolicySubsystem::GetActiveAblationTag()
{
	const FString TagPath = FPaths::ProjectContentDir() / TEXT("PCSP/Models/active_ablation.txt");
	FString Tag;
	if (!FFileHelper::LoadFileToString(Tag, *TagPath))
	{
		return TEXT("unknown");
	}
	Tag.TrimStartAndEndInline();
	return Tag.IsEmpty() ? FString(TEXT("unknown")) : Tag;
}

// ---------------------------------------------------------------------------
// Initialize / Deinitialize
// ---------------------------------------------------------------------------

void UPCSPPolicySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	PersonaCache = NewObject<UPCSPPersonaCache>(this);

	const FString DataDir  = FPaths::ProjectContentDir() / TEXT("PCSP/Data");
	const FString ModelDir = FPaths::ProjectContentDir() / TEXT("PCSP/Models");

	const FString EmbPath   = DataDir  / TEXT("persona_embeddings.json");
	const FString ModelPath = ModelDir / TEXT("pcsp_actor.onnx");

	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists(*EmbPath))
	{
		UE_LOG(LogTemp, Error,
			TEXT("PCSPPolicySubsystem: %s not found — run export_pcsp_onnx.py first. "
			     "Agents will not act until the file is present."), *EmbPath);
		return;
	}

	if (!PersonaCache->LoadFromFile(EmbPath))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: persona cache load failed."));
		return;
	}

	// Presentation-only; a missing file logs and leaves the HUD showing IDs.
	PersonaCache->LoadTextsFromFile(DataDir / TEXT("persona_texts.json"));

	if (!FPlatformFileManager::Get().GetPlatformFile().FileExists(*ModelPath))
	{
		UE_LOG(LogTemp, Error,
			TEXT("PCSPPolicySubsystem: %s not found — run export_pcsp_onnx.py first. "
			     "Agents will not act until the file is present."), *ModelPath);
		return;
	}

	if (!LoadModel())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: ONNX model load failed."));
		return;
	}

	bReady = true;
	UE_LOG(LogTemp, Log, TEXT("PCSPPolicySubsystem: ready (obs=%d, persona_dim=%d, n_actions=%d)"),
		ObsDim, PersonaDim, NActions);
}

void UPCSPPolicySubsystem::Deinitialize()
{
	bReady = false;
	if (AsyncBatchFuture.IsValid())
	{
		// The worker captures the model instance. Join before releasing NNE state.
		AsyncBatchFuture.Wait();
		AsyncBatchFuture.Get();
		AsyncBatchFuture = TFuture<FPCSPAsyncInferenceBatchResult>();
	}
	AsyncModelInstance.Reset();
	ModelInstance.Reset();
	Model.Reset();
	Super::Deinitialize();
}

// ---------------------------------------------------------------------------
// LoadModel
// ---------------------------------------------------------------------------

bool UPCSPPolicySubsystem::LoadModel()
{
	NNERuntime = UE::NNE::GetRuntime<INNERuntimeCPU>(TEXT("NNERuntimeORTCpu"));
	if (!NNERuntime.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: NNERuntimeORTCpu not available. "
			"Is the NNERuntimeORT plugin enabled?"));
		return false;
	}

	const FString ModelPath = FPaths::ProjectContentDir() / TEXT("PCSP/Models/pcsp_actor.onnx");
	TArray<uint8> ModelBytes;
	if (!FFileHelper::LoadFileToArray(ModelBytes, *ModelPath))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: failed to read %s"), *ModelPath);
		return false;
	}

	UNNEModelData* ModelData = NewObject<UNNEModelData>(GetTransientPackage(), NAME_None, RF_Transient); 
	ModelData->Init(TEXT("onnx"), TConstArrayView64<uint8>(ModelBytes.GetData(), ModelBytes.Num()));
	Model = NNERuntime->CreateModelCPU(ModelData);
	if (!Model.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: CreateModelCPU failed"));
		return false;
	}

	ModelInstance = Model->CreateModelInstanceCPU();
	if (!ModelInstance.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: CreateModelInstanceCPU failed"));
		return false;
	}
	AsyncModelInstance = Model->CreateModelInstanceCPU();
	if (!AsyncModelInstance.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: async CreateModelInstanceCPU failed"));
		return false;
	}

	// Bind static input shapes (batch = 1)
	TArray<UE::NNE::FTensorShape> InShapes;
	InShapes.Add(UE::NNE::FTensorShape::Make({1, ObsDim}));
	InShapes.Add(UE::NNE::FTensorShape::Make({1, PersonaDim}));
	if (ModelInstance->SetInputTensorShapes(InShapes) != UE::NNE::EResultStatus::Ok)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: SetInputTensorShapes failed"));
		return false;
	}
	if (AsyncModelInstance->SetInputTensorShapes(InShapes) != UE::NNE::EResultStatus::Ok)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: async SetInputTensorShapes failed"));
		return false;
	}

	// Pre-allocate inference buffers
	ObsBuffer.SetNumZeroed(ObsDim);
	PersonaBuffer.SetNumZeroed(PersonaDim);
	LogitsBuffer.SetNumZeroed(NActions);

	return true;
}

bool UPCSPPolicySubsystem::IsAsyncInferenceEnabled() const
{
	return bReady
		&& CVarPCSPAsyncInference.GetValueOnGameThread() != 0
		&& GetPolicyMode() != EPCSPPolicyMode::BTOnly;
}

bool UPCSPPolicySubsystem::CanDispatchAsyncBatch() const
{
	return IsAsyncInferenceEnabled() && !AsyncBatchFuture.IsValid();
}

bool UPCSPPolicySubsystem::DispatchAsyncBatch(TArray<FPCSPAsyncInferenceRequest>&& Requests)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_ONNX_AsyncDispatch);
	check(IsInGameThread());
	if (!CanDispatchAsyncBatch() || Requests.IsEmpty() || !PersonaCache)
	{
		return false;
	}

	const int32 BatchSize = Requests.Num();
	for (const auto& Request : Requests) { if (ReplayInputs.Num() < 32) { ReplayInputs.Add(Request); } }
	EvaluationBatchStart = FPlatformTime::Seconds();
	EvaluationBatchPersonas.Reset();
	for (const auto& Request : Requests) { EvaluationBatchPersonas.Add(Request.RequestId, Request.PersonaId); }
	TArray<float> BatchedObservations;
	TArray<float> BatchedPersonas;
	TArray<int32> RequestIds;
	TArray<int32> RequestSeeds;
	BatchedObservations.SetNumZeroed(BatchSize * ObsDim);
	BatchedPersonas.SetNumZeroed(BatchSize * PersonaDim);
	RequestIds.SetNumUninitialized(BatchSize);
	RequestSeeds.SetNumUninitialized(BatchSize);
	const bool bZeroPersona = GetPolicyMode() == EPCSPPolicyMode::HybridNoPersona;

	for (int32 BatchIndex = 0; BatchIndex < BatchSize; ++BatchIndex)
	{
		const FPCSPAsyncInferenceRequest& Request = Requests[BatchIndex];
		RequestIds[BatchIndex] = Request.RequestId;
		RequestSeeds[BatchIndex] = Request.DecisionSeed;
		const int32 CopyLen = FMath::Min(Request.Observation.Num(), ObsDim);
		if (CopyLen > 0)
		{
			FMemory::Memcpy(BatchedObservations.GetData() + BatchIndex * ObsDim,
				Request.Observation.GetData(), CopyLen * sizeof(float));
		}
		if (!bZeroPersona)
		{
			const TConstArrayView<float> Embedding = PersonaCache->GetEmbedding(Request.PersonaId);
			if (Embedding.Num() != PersonaDim)
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSPPolicySubsystem: async invalid persona_id=%d; using zero embedding"),
					Request.PersonaId);
				continue;
			}
			FMemory::Memcpy(BatchedPersonas.GetData() + BatchIndex * PersonaDim,
				Embedding.GetData(), PersonaDim * sizeof(float));
		}
	}

	const TSharedPtr<UE::NNE::IModelInstanceCPU> WorkerInstance = AsyncModelInstance;
	AsyncBatchFuture = Async(EAsyncExecution::ThreadPool,
		[WorkerInstance, BatchSize,
		 Observations = MoveTemp(BatchedObservations),
		 Personas = MoveTemp(BatchedPersonas),
		 Ids = MoveTemp(RequestIds),
		 Seeds = MoveTemp(RequestSeeds)]() mutable
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_ONNX_AsyncBatchWorker);
		FPCSPAsyncInferenceBatchResult BatchResult;
		BatchResult.Results.SetNum(BatchSize);
		for (int32 BatchIndex = 0; BatchIndex < BatchSize; ++BatchIndex)
		{
			BatchResult.Results[BatchIndex].RequestId = Ids[BatchIndex];
		}
		const double StartSec = FPlatformTime::Seconds();
		if (!WorkerInstance.IsValid())
		{
			return BatchResult;
		}

		TArray<UE::NNE::FTensorShape> InputShapes;
		InputShapes.Add(UE::NNE::FTensorShape::Make(
			{static_cast<uint32>(BatchSize), static_cast<uint32>(ObsDim)}));
		InputShapes.Add(UE::NNE::FTensorShape::Make(
			{static_cast<uint32>(BatchSize), static_cast<uint32>(PersonaDim)}));
		if (WorkerInstance->SetInputTensorShapes(InputShapes) != UE::NNE::EResultStatus::Ok)
		{
			return BatchResult;
		}

		TArray<float> Logits;
		Logits.SetNumZeroed(BatchSize * NActions);
		TArray<UE::NNE::FTensorBindingCPU> Inputs;
		TArray<UE::NNE::FTensorBindingCPU> Outputs;
		Inputs.Add({Observations.GetData(), static_cast<uint64>(Observations.Num() * sizeof(float))});
		Inputs.Add({Personas.GetData(), static_cast<uint64>(Personas.Num() * sizeof(float))});
		Outputs.Add({Logits.GetData(), static_cast<uint64>(Logits.Num() * sizeof(float))});
		if (WorkerInstance->RunSync(Inputs, Outputs) != UE::NNE::EResultStatus::Ok)
		{
			return BatchResult;
		}

		for (int32 BatchIndex = 0; BatchIndex < BatchSize; ++BatchIndex)
		{
			const TConstArrayView<float> Row(Logits.GetData() + BatchIndex * NActions, NActions);
			const int32 SelectedIndex = SelectActionIndex(Row, Seeds[BatchIndex]);
			FPCSPAsyncInferenceResult& Result = BatchResult.Results[BatchIndex];
			Result.PolicyActionIndex = SelectedIndex;
			Result.Action = ActionFromModelIndex(SelectedIndex);
		}
		BatchResult.bSuccess = true;
		BatchResult.WorkerMicros = (FPlatformTime::Seconds() - StartSec) * 1.0e6;
		return BatchResult;
	});
	return true;
}

bool UPCSPPolicySubsystem::TryConsumeAsyncBatch(FPCSPAsyncInferenceBatchResult& OutResult)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_ONNX_AsyncConsume);
	check(IsInGameThread());
	if (!AsyncBatchFuture.IsValid() || !AsyncBatchFuture.IsReady())
	{
		return false;
	}
	OutResult = AsyncBatchFuture.Get();
	if (auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>())
	{
		const double Latency = (FPlatformTime::Seconds() - EvaluationBatchStart) * 1.e6;
		const double Service = OutResult.WorkerMicros / FMath::Max(1, OutResult.Results.Num());
		for (const auto& Result : OutResult.Results)
		{
			Perf->RecordPolicyDecision(EvaluationBatchPersonas.FindRef(Result.RequestId),
				OutResult.bSuccess ? Result.Action : EPCSPActionType::None, Service, Latency, true);
		}
	}
	EvaluationBatchPersonas.Reset();
	AsyncBatchFuture = TFuture<FPCSPAsyncInferenceBatchResult>();
	return true;
}

// ---------------------------------------------------------------------------
// RunInference
// ---------------------------------------------------------------------------

EPCSPActionType UPCSPPolicySubsystem::RunInferenceWithLogits(const TArray<float>& Observation,
	int32 PersonaId, TArray<float>& OutLogits, double& OutInferenceMicros,
	int32 DecisionSeed, int32* OutActionIndex)
{
	const double StartSec = FPlatformTime::Seconds();
	const EPCSPActionType Action = RunInference(Observation, PersonaId, DecisionSeed);
	OutInferenceMicros = (FPlatformTime::Seconds() - StartSec) * 1.0e6;
	if (OutActionIndex) { *OutActionIndex = LastSelectedActionIndex; }

	// In BTOnly the ONNX path is skipped; emit a zeroed logit vector so the
	// trajectory schema stays uniform and analyzer KL math doesn't NaN out.
	OutLogits.SetNumUninitialized(NActions);
	if (GetPolicyMode() == EPCSPPolicyMode::BTOnly)
	{
		FMemory::Memzero(OutLogits.GetData(), NActions * sizeof(float));
	}
	else
	{
		FMemory::Memcpy(OutLogits.GetData(), LogitsBuffer.GetData(), NActions * sizeof(float));
	}
	return Action;
}

EPCSPActionType UPCSPPolicySubsystem::RunInference(const TArray<float>& Observation, int32 PersonaId,
	int32 DecisionSeed)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(PCSP_ONNX_RunInference_Sync);

	const EPCSPPolicyMode Mode = GetPolicyMode();
	const double EvaluationStart = FPlatformTime::Seconds();
	if (ReplayInputs.Num() < 32 && Mode == EPCSPPolicyMode::HybridPCSP)
	{
		auto& Input = ReplayInputs.AddDefaulted_GetRef();
		Input.Observation = Observation;
		Input.PersonaId = PersonaId;
		Input.DecisionSeed = DecisionSeed;
	}
	ON_SCOPE_EXIT
	{
		if (auto* Perf = GetWorld()->GetSubsystem<UPCSPPerfSamplerSubsystem>())
		{
			const double Micros = (FPlatformTime::Seconds() - EvaluationStart) * 1.e6;
			const EPCSPActionType Result = Mode == EPCSPPolicyMode::BTOnly ? NeedsHeuristic(Observation)
				: LastSelectedActionIndex != INDEX_NONE ? ActionFromModelIndex(LastSelectedActionIndex) : EPCSPActionType::None;
			Perf->RecordPolicyDecision(PersonaId, Result, Micros, Micros);
		}
	};

	// BTOnly bypasses ONNX entirely — uses the static needs heuristic so this
	// branch works even if pcsp_actor.onnx never loaded.
	// Every early return below skips the ONNX path, so there is no selected index
	// to report; clear it rather than let the previous decision's value leak out.
	LastSelectedActionIndex = INDEX_NONE;

	if (Mode == EPCSPPolicyMode::BTOnly)
	{
		return NeedsHeuristic(Observation);
	}

	if (!bReady)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem::RunInference called before model is ready"));
		return EPCSPActionType::None;
	}

	// Copy obs — clamp to model dim (obs may be larger if padded)
	const int32 CopyLen = FMath::Min(Observation.Num(), ObsDim);
	FMemory::Memzero(ObsBuffer.GetData(), ObsDim * sizeof(float));
	FMemory::Memcpy(ObsBuffer.GetData(), Observation.GetData(), CopyLen * sizeof(float));

	// Copy persona embedding
	TConstArrayView<float> Emb = PersonaCache->GetEmbedding(PersonaId);
	if (Emb.Num() != PersonaDim)
	{
		UE_LOG(LogTemp, Error,
			TEXT("PCSPPolicySubsystem: invalid persona_id=%d (cache has %d-dim embedding, model expects %d)"),
			PersonaId, Emb.Num(), PersonaDim);
		return EPCSPActionType::None;
	}
	if (Mode == EPCSPPolicyMode::HybridNoPersona)
	{
		// Ablation: same architecture, but the persona slot is zeroed. Any
		// persona-specific behavior the model expresses now must be coming
		// from observation features, not the embedding.
		FMemory::Memzero(PersonaBuffer.GetData(), PersonaDim * sizeof(float));
	}
	else
	{
		FMemory::Memcpy(PersonaBuffer.GetData(), Emb.GetData(), PersonaDim * sizeof(float));
	}

	// Bind and run
	TArray<UE::NNE::FTensorBindingCPU> Inputs, Outputs;
	Inputs.Add({ObsBuffer.GetData(),     (uint64)(ObsDim     * sizeof(float))});
	Inputs.Add({PersonaBuffer.GetData(), (uint64)(PersonaDim * sizeof(float))});
	Outputs.Add({LogitsBuffer.GetData(), (uint64)(NActions   * sizeof(float))});

	if (ModelInstance->RunSync(Inputs, Outputs) != UE::NNE::EResultStatus::Ok)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: RunSync failed"));
		return EPCSPActionType::None;
	}

	LastSelectedActionIndex = SelectActionIndex(
		TConstArrayView<float>(LogitsBuffer.GetData(), NActions), DecisionSeed);
	return ActionFromModelIndex(LastSelectedActionIndex);
}

EPCSPActionType UPCSPPolicySubsystem::ActionFromModelIndex(int32 ActionIndex)
{
	// v3 action index → EPCSPActionType
	// v3 order: focused_work(0), planning_work(1), eat_quick(2), eat_slow(3),
	//           sleep(4), nap(5), socialize_initiate(6), socialize_respond(7),
	//           exercise_intense(8), exercise_light(9), read_deep(10), read_casual(11),
	//           clean(12), rest_alone(13), rest_with_others(14), explore(15),
	//           move_up(16), move_down(17), move_left(18), move_right(19)
	// Movement indices 16-19 carry no semantic meaning in UE (engine handles
	// pathing). Remap them to outdoor/observe actions so the Park/Observe zone
	// has a reachable producer; otherwise the Observe category is dead.
	static constexpr EPCSPActionType V3ToUE[20] = {
		EPCSPActionType::FocusedWork,         // 0  focused_work
		EPCSPActionType::PlanningWork,        // 1  planning_work
		EPCSPActionType::EatQuick,            // 2  eat_quick
		EPCSPActionType::EatSlow,             // 3  eat_slow
		EPCSPActionType::RestAlone,           // 4  sleep
		EPCSPActionType::RestWithOthers,      // 5  nap
		EPCSPActionType::SocializeInitiate,   // 6  socialize_initiate
		EPCSPActionType::SocializeRespond,    // 7  socialize_respond
		EPCSPActionType::ExerciseSolo,        // 8  exercise_intense
		EPCSPActionType::ExerciseSocial,      // 9  exercise_light
		EPCSPActionType::DeepStudy,           // 10 read_deep
		EPCSPActionType::CasualLearning,      // 11 read_casual
		EPCSPActionType::HygieneQuick,        // 12 clean
		EPCSPActionType::RestAlone,           // 13 rest_alone
		EPCSPActionType::RestWithOthers,      // 14 rest_with_others
		EPCSPActionType::BrowseArea,          // 15 explore
		EPCSPActionType::LeisureOutdoor,      // 16 move_up    → outdoor leisure (Park)
		EPCSPActionType::ObserveCrowd,        // 17 move_down  → observe crowd  (Park)
		EPCSPActionType::LeisureOutdoor,      // 18 move_left  → outdoor leisure (Park)
		EPCSPActionType::ObserveCrowd,        // 19 move_right → observe crowd  (Park)
	};

	if (ActionIndex >= 0 && ActionIndex < NActions)
	{
		return V3ToUE[ActionIndex];
	}
	UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: argmax out of range (idx=%d, NActions=%d)"),
		ActionIndex, NActions);
	return EPCSPActionType::None;
}

EPCSPAffordanceCategory UPCSPPolicySubsystem::ActionToCategory(EPCSPActionType Action)
{
	switch (Action)
	{
	case EPCSPActionType::EatQuick:
	case EPCSPActionType::EatSlow:
		return EPCSPAffordanceCategory::Eat;

	case EPCSPActionType::RestAlone:
	case EPCSPActionType::RestWithOthers:
		return EPCSPAffordanceCategory::Rest;

	case EPCSPActionType::FocusedWork:
	case EPCSPActionType::PlanningWork:
		return EPCSPAffordanceCategory::Work;

	case EPCSPActionType::DeepStudy:
	case EPCSPActionType::CasualLearning:
		return EPCSPAffordanceCategory::Study;

	case EPCSPActionType::ExerciseSolo:
	case EPCSPActionType::ExerciseSocial:
		return EPCSPAffordanceCategory::Exercise;

	case EPCSPActionType::HygieneQuick:
	case EPCSPActionType::HygieneCareful:
		return EPCSPAffordanceCategory::Hygiene;

	case EPCSPActionType::SocializeInitiate:
	case EPCSPActionType::SocializeRespond:
		return EPCSPAffordanceCategory::Social;

	case EPCSPActionType::LeisureIndoor:
	case EPCSPActionType::LeisureOutdoor:
	case EPCSPActionType::ObserveCrowd:
		return EPCSPAffordanceCategory::Observe;

	case EPCSPActionType::ShopEssentials:
	case EPCSPActionType::BrowseArea:
		return EPCSPAffordanceCategory::Shop;

	case EPCSPActionType::IdleReflect:
		return EPCSPAffordanceCategory::Idle;

	default:
		return EPCSPAffordanceCategory::None;
	}
}

// ---------------------------------------------------------------------------
// Needs heuristic (used when model not loaded)
// ---------------------------------------------------------------------------

EPCSPActionType UPCSPPolicySubsystem::NeedsHeuristic(const TArray<float>& NeedsValues)
{
	// Obs layout (v3): [pos(2), time(1), needs(8), ...]
	// needs start at index 3
	constexpr int32 NeedsOffset = 3;
	if (NeedsValues.Num() < NeedsOffset + 8)
	{
		return EPCSPActionType::IdleReflect;
	}

	int32 MostUrgent = 0;
	float LowestVal  = NeedsValues[NeedsOffset];
	for (int32 i = 1; i < 8; ++i)
	{
		if (NeedsValues[NeedsOffset + i] < LowestVal)
		{
			LowestVal  = NeedsValues[NeedsOffset + i];
			MostUrgent = i;
		}
	}

	// Maps EPCSPNeed index → EPCSPActionType (same mapping as BTTask_PCSPDecision)
	switch (static_cast<EPCSPNeed>(MostUrgent))
	{
	case EPCSPNeed::Hunger:   return EPCSPActionType::EatQuick;
	case EPCSPNeed::Sleep:    return EPCSPActionType::RestAlone;
	case EPCSPNeed::Social:   return EPCSPActionType::SocializeInitiate;
	case EPCSPNeed::Leisure:  return EPCSPActionType::LeisureOutdoor;
	case EPCSPNeed::Hygiene:  return EPCSPActionType::HygieneQuick;
	case EPCSPNeed::Fitness:  return EPCSPActionType::ExerciseSolo;
	case EPCSPNeed::Work:     return EPCSPActionType::FocusedWork;
	case EPCSPNeed::Learning: return EPCSPActionType::CasualLearning;
	default:                  return EPCSPActionType::IdleReflect;
	}
}
