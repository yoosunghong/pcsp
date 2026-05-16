#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NNE.h"
#include "NNERuntimeCPU.h"
#include "PCSPTypes.h"
#include "PCSPPolicySubsystem.generated.h"

class UPCSPPersonaCache;

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
	 * @param Observation  Flat obs vector (must be ObsDim floats).
	 * @param PersonaId    1-based persona index (matches persona_embeddings.json).
	 * @return The highest-probability action type.
	 */
	UFUNCTION(BlueprintCallable, Category="PCSP|Policy")
	EPCSPActionType RunInference(const TArray<float>& Observation, int32 PersonaId);

	/** Fallback heuristic used when the model is not loaded. */
	static EPCSPActionType NeedsHeuristic(const TArray<float>& NeedsValues);

private:
	bool LoadModel();

	TWeakInterfacePtr<INNERuntimeCPU>              NNERuntime;
	TSharedPtr<UE::NNE::IModelCPU>                Model;
	TSharedPtr<UE::NNE::IModelInstanceCPU>         ModelInstance;

	UPROPERTY()
	TObjectPtr<UPCSPPersonaCache>                  PersonaCache;

	// Reusable inference buffers (allocated once after model load)
	TArray<float> ObsBuffer;
	TArray<float> PersonaBuffer;
	TArray<float> LogitsBuffer;

	bool bReady = false;

	static constexpr int32 ObsDim      = 33;
	static constexpr int32 PersonaDim  = 64;
	static constexpr int32 NActions    = 20;
};
