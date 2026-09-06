#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NNE.h"
#include "NNERuntimeCPU.h"
#include "Async/Future.h"
#include "PCSPTypes.h"
#include "PCSPPolicySubsystem.generated.h"

class UPCSPPersonaCache;

/** Fully-owned POD-like request copied on the game thread before dispatch. */
struct FPCSPAsyncInferenceRequest
{
	int32 RequestId = INDEX_NONE;
	int32 PersonaId = 1;
	/** Seeds this decision's softmax draw; see UPCSPPolicySubsystem::SelectActionIndex. */
	int32 DecisionSeed = 0;
	TArray<float> Observation;
};

/** Worker result. Mass entities are matched by their stable request id next frame. */
struct FPCSPAsyncInferenceResult
{
	int32 RequestId = INDEX_NONE;
	int32 PolicyActionIndex = INDEX_NONE;
	EPCSPActionType Action = EPCSPActionType::None;
};

struct FPCSPAsyncInferenceBatchResult
{
	bool bSuccess = false;
	double WorkerMicros = 0.0;
	TArray<FPCSPAsyncInferenceResult> Results;
};

/**
 * World subsystem that owns the ONNX actor model and runs per-agent inference.
 *
 * Model contract (set by export_pcsp_onnx.py):
 *   Input 0  "obs"           float32 (1, ObsDim)     — normalized observation
 *   Input 1  "persona_proj"  float32 (1, PersonaDim)  — pre-projected embedding
 *   Output   "logits"        float32 (1, N_Actions)   — raw action logits
 */
UCLASS()
class CNZOI_API UPCSPPolicySubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	bool IsReady() const { return bReady; }

	/**
	 * Run actor inference for one agent.
	 * @param Observation   Flat obs vector (must be ObsDim floats).
	 * @param PersonaId     1-based persona index (matches persona_embeddings.json).
	 * @param DecisionSeed  Seeds the softmax draw. Pass a value that is stable for
	 *                      this decision but differs between agents and over time,
	 *                      so a run is reproducible and neighbours do not correlate.
	 * @return The selected action type.
	 */
	UFUNCTION(BlueprintCallable, Category="PCSP|Policy")
	EPCSPActionType RunInference(const TArray<float>& Observation, int32 PersonaId,
	                             int32 DecisionSeed = 0);

	/**
	 * Run actor inference and also return the raw logits.
	 * OutLogits is resized to NActions; identical action selection as RunInference.
	 * OutActionIndex receives the index actually selected — under sampling that is
	 * not the argmax, so trajectory logs must record this rather than re-deriving.
	 * Used for trajectory-log policy-KL export.
	 */
	EPCSPActionType RunInferenceWithLogits(const TArray<float>& Observation, int32 PersonaId,
	                                       TArray<float>& OutLogits, double& OutInferenceMicros,
	                                       int32 DecisionSeed = 0, int32* OutActionIndex = nullptr);

	/**
	 * Maps a logit row to an action index.
	 *
	 * Default is a draw from the softmax, which is how the policy was trained and
	 * optimised; `pcsp.PolicySampling 0` restores argmax. Argmax discards the
	 * policy's own uncertainty, and the full checkpoint carries markedly more of it
	 * than the ablations do, so argmax understates its behavioural range.
	 * Pure function of (Logits, DecisionSeed, CVars) — safe on any thread.
	 */
	static int32 SelectActionIndex(TConstArrayView<float> Logits, int32 DecisionSeed);

	/** Whether action selection draws from the softmax rather than taking argmax. */
	static bool IsSamplingEnabled();

	int32 GetNumActions() const { return NActions; }

	/** Human-readable selection rule for run configs and the HUD. */
	static FString ActionSelectionName();

	/** Whether the Mass tier should use the next-frame asynchronous batch path. */
	bool IsAsyncInferenceEnabled() const;

	/** True when no worker batch is currently in flight. Game-thread only. */
	bool CanDispatchAsyncBatch() const;

	/** Copy persona inputs and dispatch one dynamic-batch ORT job. Game-thread only. */
	bool DispatchAsyncBatch(TArray<FPCSPAsyncInferenceRequest>&& Requests);

	/** Consume a completed batch without blocking. Game-thread only. */
	bool TryConsumeAsyncBatch(FPCSPAsyncInferenceBatchResult& OutResult);

	/** Model action index -> UE semantic action mapping shared by sync/async paths. */
	static EPCSPActionType ActionFromModelIndex(int32 ActionIndex);

	/** Fallback heuristic used when the model is not loaded. */
	static EPCSPActionType NeedsHeuristic(const TArray<float>& NeedsValues);

	/** Canonical semantic action -> authored affordance category routing. */
	static EPCSPAffordanceCategory ActionToCategory(EPCSPActionType Action);

	/** Current ablation mode (read from `pcsp.PolicyMode` CVar at each inference). */
	static EPCSPPolicyMode GetPolicyMode();

	/** Stable string used in trajectory `session_start` rows + analyzer summaries. */
	static FString PolicyModeName(EPCSPPolicyMode Mode);

	/** Active ONNX ablation tag written by swap_ue5_onnx.py, or "unknown". */
	static FString GetActiveAblationTag();
	/** Bounded replay of captured live inputs through individual and worker-batch paths. */
	FString RunFixedInputReplay();

public:
	/** Read-only access for HUD presentation; null until Initialize succeeds. */
	const UPCSPPersonaCache* GetPersonaCache() const { return PersonaCache; }

private:
	bool LoadModel();

	TWeakInterfacePtr<INNERuntimeCPU>              NNERuntime;
	TSharedPtr<UE::NNE::IModelCPU>                Model;
	TSharedPtr<UE::NNE::IModelInstanceCPU>         ModelInstance;
	TSharedPtr<UE::NNE::IModelInstanceCPU>         AsyncModelInstance;
	TFuture<FPCSPAsyncInferenceBatchResult>        AsyncBatchFuture;
	TMap<int32, int32> EvaluationBatchPersonas;
	double EvaluationBatchStart = 0;
	TArray<FPCSPAsyncInferenceRequest> ReplayInputs;

	UPROPERTY()
	TObjectPtr<UPCSPPersonaCache>                  PersonaCache;

	// Reusable inference buffers (allocated once after model load)
	TArray<float> ObsBuffer;
	TArray<float> PersonaBuffer;
	TArray<float> LogitsBuffer;

	bool bReady = false;
	/** Index chosen by the last sync RunInference; INDEX_NONE when ONNX was skipped. */
	int32 LastSelectedActionIndex = INDEX_NONE;

	static constexpr int32 ObsDim      = 33;
	static constexpr int32 PersonaDim  = 64;
	static constexpr int32 NActions    = 20;
};
