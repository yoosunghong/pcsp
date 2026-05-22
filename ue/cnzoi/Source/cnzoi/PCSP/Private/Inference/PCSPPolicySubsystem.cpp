#include "PCSPPolicySubsystem.h"
#include "PCSPPersonaCache.h"
#include "NNERuntimeCPU.h"
#include "NNEModelData.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/IConsoleManager.h"

// `pcsp.PolicyMode` selects the Phase 4 runtime ablation at inference time.
// 0=HybridPCSP (default), 1=BTOnly, 2=HybridNoPersona.
// Switch between runs from PIE console (`pcsp.PolicyMode 1`) — no rebuild needed.
static TAutoConsoleVariable<int32> CVarPCSPPolicyMode(
	TEXT("pcsp.PolicyMode"),
	0,
	TEXT("PCSP policy ablation mode: 0=HybridPCSP, 1=BTOnly, 2=HybridNoPersona"),
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

	// Bind static input shapes (batch = 1)
	TArray<UE::NNE::FTensorShape> InShapes;
	InShapes.Add(UE::NNE::FTensorShape::Make({1, ObsDim}));
	InShapes.Add(UE::NNE::FTensorShape::Make({1, PersonaDim}));
	if (ModelInstance->SetInputTensorShapes(InShapes) != UE::NNE::EResultStatus::Ok)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: SetInputTensorShapes failed"));
		return false;
	}

	// Pre-allocate inference buffers
	ObsBuffer.SetNumZeroed(ObsDim);
	PersonaBuffer.SetNumZeroed(PersonaDim);
	LogitsBuffer.SetNumZeroed(NActions);

	return true;
}

// ---------------------------------------------------------------------------
// RunInference
// ---------------------------------------------------------------------------

EPCSPActionType UPCSPPolicySubsystem::RunInferenceWithLogits(const TArray<float>& Observation,
	int32 PersonaId, TArray<float>& OutLogits, double& OutInferenceMicros)
{
	const double StartSec = FPlatformTime::Seconds();
	const EPCSPActionType Action = RunInference(Observation, PersonaId);
	OutInferenceMicros = (FPlatformTime::Seconds() - StartSec) * 1.0e6;

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

EPCSPActionType UPCSPPolicySubsystem::RunInference(const TArray<float>& Observation, int32 PersonaId)
{
	const EPCSPPolicyMode Mode = GetPolicyMode();

	// BTOnly bypasses ONNX entirely — uses the static needs heuristic so this
	// branch works even if pcsp_actor.onnx never loaded.
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

	// Argmax over logits
	int32 BestIdx = 0;
	float BestVal = LogitsBuffer[0];
	for (int32 i = 1; i < NActions; ++i)
	{
		if (LogitsBuffer[i] > BestVal)
		{
			BestVal = LogitsBuffer[i];
			BestIdx = i;
		}
	}

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

	if (BestIdx >= 0 && BestIdx < NActions)
	{
		return V3ToUE[BestIdx];
	}
	UE_LOG(LogTemp, Error, TEXT("PCSPPolicySubsystem: argmax out of range (idx=%d, NActions=%d)"),
		BestIdx, NActions);
	return EPCSPActionType::None;
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
	case EPCSPNeed::Leisure:  return EPCSPActionType::LeisureIndoor;
	case EPCSPNeed::Hygiene:  return EPCSPActionType::HygieneQuick;
	case EPCSPNeed::Fitness:  return EPCSPActionType::ExerciseSolo;
	case EPCSPNeed::Work:     return EPCSPActionType::FocusedWork;
	case EPCSPNeed::Learning: return EPCSPActionType::CasualLearning;
	default:                  return EPCSPActionType::IdleReflect;
	}
}
