#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPTypes.h"
#include "PCSPTrajectoryLogComponent.generated.h"

class UPCSPNeedsComponent;
class UPCSPPersonaComponent;

UENUM(BlueprintType)
enum class EPCSPTrajectoryEvent : uint8
{
	Decision,             // PCSPDecision selected an action (pre-execution)
	InteractionComplete,  // PerformInteraction succeeded — needs delta applied
	InteractionFailed,    // PerformInteraction aborted (lost reservation, etc.)
	MoveFailed            // MoveToAffordance exhausted retries
};

USTRUCT(BlueprintType)
struct FPCSPTrajectoryEntry
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) float TimeSeconds = 0.f;
	UPROPERTY(BlueprintReadOnly) FVector Location = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly) EPCSPTrajectoryEvent EventType = EPCSPTrajectoryEvent::Decision;
	UPROPERTY(BlueprintReadOnly) EPCSPActionType Action = EPCSPActionType::IdleReflect;
	UPROPERTY(BlueprintReadOnly) EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;
	UPROPERTY(BlueprintReadOnly) FGameplayTag Affordance;
	UPROPERTY(BlueprintReadOnly) float Reward = 0.f;
	UPROPERTY(BlueprintReadOnly) float UrgencyScore = 0.f;
};

/**
 * Per-agent behavioral logger. One JSONL file per agent under
 * <Project>/Saved/PCSP/Logs/<session_timestamp>/agent_<persona>_<actor>.jsonl.
 *
 * The session directory is shared across all agents in a single PIE run
 * (lazy-initialized on first use). On EndPlay, pending entries are flushed
 * to disk; a periodic timer also flushes every PeriodicFlushSeconds.
 *
 * Call sites (Phase 4 wiring):
 *   - BTTask_PCSPDecision        -> RecordDecision()
 *   - BTTask_PerformInteraction  -> RecordInteractionComplete() / Failed()
 *   - BTTask_MoveToAffordance    -> RecordMoveFailed()
 */
UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPTrajectoryLogComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPTrajectoryLogComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void RecordDecision(EPCSPActionType Action, float UrgencyScore);

	/** Decision variant that also records raw policy logits for offline KL computation.
	 *  InferenceMicros is the wall-time of the ONNX RunInference call (microseconds);
	 *  pass <0 to omit. Used for T1.3 latency-budget telemetry. */
	void RecordDecisionWithLogits(EPCSPActionType Action, float UrgencyScore,
	                              TArrayView<const float> Logits,
	                              double InferenceMicros = -1.0);

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void RecordInteractionComplete(EPCSPActionType Action, FGameplayTag Affordance,
	                               EPCSPAffordanceCategory Category, float Reward);

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void RecordInteractionFailed(EPCSPActionType Action, FGameplayTag Affordance,
	                             const FString& Reason);

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void RecordMoveFailed(EPCSPActionType Action, int32 RetryCount,
	                      const FString& FailureReason = TEXT("unspecified"),
	                      FGameplayTag IntendedZoneTag = FGameplayTag(),
	                      float DistanceToTarget = -1.f);

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	const TArray<FPCSPTrajectoryEntry>& GetEntries() const { return Entries; }

	/** Most-recent N events from the in-memory ring buffer, newest last. HUD trajectory strip. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	TArray<FPCSPTrajectoryEntry> GetRecentEvents(int32 MaxCount = 5) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void ClearLog() { Entries.Reset(); PendingLines.Reset(); }

	UFUNCTION(BlueprintCallable, Category="PCSP|Trajectory")
	void Flush();

	/** Session directory shared by all agents in this PIE process. */
	static FString GetSessionDir();
	static void SetEvaluationSessionDir(const FString& Directory);

	UPROPERTY(EditAnywhere, Category="PCSP|Trajectory", meta=(ClampMin="1.0"))
	float PeriodicFlushSeconds = 5.f;

	/** Cap on the in-memory `Entries` ring buffer. Older entries are dropped FIFO. */
	UPROPERTY(EditAnywhere, Category="PCSP|Trajectory", meta=(ClampMin="8", ClampMax="2048"))
	int32 MaxRecentEntries = 64;

protected:
	void AppendLine(const FString& JsonLine);
	void EmitEvent(EPCSPTrajectoryEvent Event, EPCSPActionType Action,
	               FGameplayTag Affordance, float Reward,
	               EPCSPAffordanceCategory Category, float UrgencyScore,
	               const FString& ExtraField);

	UPCSPNeedsComponent*   GetNeeds() const;
	UPCSPPersonaComponent* GetPersona() const;

	UPROPERTY() TArray<FPCSPTrajectoryEntry> Entries;

	TArray<FString> PendingLines;
	FString LogFilePath;
	FTimerHandle FlushTimerHandle;
};
