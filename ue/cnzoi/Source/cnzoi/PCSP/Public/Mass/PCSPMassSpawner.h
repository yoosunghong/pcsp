#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Mass/EntityHandle.h"
#include "PCSPTypes.h"
#include "PCSPMassSpawner.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UPrimitiveComponent;
class UAnimToTextureDataAsset;

/** Read-only snapshot copied out of Mass storage for HUD and camera consumers. */
struct FPCSPMassAgentSnapshot
{
	int32 StableIndex = INDEX_NONE;
	int32 PersonaId = 0;
	float Needs[8] = {};
	EPCSPActionType Action = EPCSPActionType::IdleReflect;
	EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::Idle;
	FVector Location = FVector::ZeroVector;
	FRotator Rotation = FRotator::ZeroRotator;
	FVector Target = FVector::ZeroVector;
	int32 ZoneVisualizationIndex = INDEX_NONE;
	int32 ReservedSlotIndex = INDEX_NONE;
	bool bMoving = false;
	bool bInteracting = false;
	/** Target is a free-roam stroll point rather than a reserved interaction slot. */
	bool bWandering = false;
	TArray<EPCSPActionType> RecentActions;
	TArray<float> RecentActionTimes;
};

/** Programmatic Mass archetype with an instanced PCSP-character representation. */
UCLASS()
class CNZOI_API APCSPMassSpawner : public AActor
{
	GENERATED_BODY()

public:
	APCSPMassSpawner();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="PCSP|Mass")
	int32 SpawnMassEntities();

	UFUNCTION(BlueprintCallable, Category="PCSP|Mass")
	void DestroyMassEntities();

	bool GetAgentSnapshot(int32 StableIndex, FPCSPMassAgentSnapshot& OutSnapshot) const;
	int32 GetSpawnedEntityCount() const { return SpawnedEntities.Num(); }
	float GetRepresentationScale() const { return FMath::Max(0.1f, RepresentationScale); }
	void GetAllAgentSnapshots(TArray<FPCSPMassAgentSnapshot>& OutSnapshots) const;
	bool FindNearestAgent(const FVector& Origin, int32& OutStableIndex, float& OutDistanceSq) const;

	/**
	 * Crowd neighbourhood around one agent, read from the cached representation
	 * poses rather than Mass storage so the HUD can call it every refresh.
	 * OutSameActivity counts the neighbours whose affordance category matches.
	 */
	bool GetNeighborhoodSummary(int32 StableIndex, float Radius, int32& OutNearby,
		int32& OutSameActivity) const;
	bool GetStableIndexFromHit(const UPrimitiveComponent* Component, int32 InstanceIndex,
		int32& OutStableIndex) const;

	/** Draws the green selection shell over one agent; INDEX_NONE clears it. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Mass")
	void SetHighlightedAgent(int32 StableIndex);

	int32 GetHighlightedAgent() const { return HighlightedStableIndex; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="1", ClampMax="65536"))
	int32 EntityCount = 1024;

	/** Uniform size of all Mass bodies, including animation and selection. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.1"))
	float RepresentationScale = 3.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass")
	FVector2D SpawnExtent = FVector2D(2800.f, 2800.f);

	/**
	 * Prefer the loaded affordance slots as stratified start anchors. This is
	 * enabled by the Visual district's agent spawner so the crowd begins across
	 * all city blocks instead of as one hotel-courtyard cluster.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass")
	bool bDistributeAcrossAffordanceSlots = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass")
	int32 RandomSeed = 0;

	/**
	 * Range the eight starting needs are drawn from, per entity.
	 *
	 * Every entity used to spawn on the fragment default (0.8 across the board),
	 * so the first policy evaluation saw one observation for the whole crowd and
	 * the population collapsed onto its argmax. The band is deliberately away
	 * from zero: it breaks the tie without starting anyone in crisis.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="0.0", ClampMax="1.0"))
	float InitialNeedMin = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="0.0", ClampMax="1.0"))
	float InitialNeedMax = 0.95f;

	/**
	 * Seconds between representation passes. 0 refreshes every frame, which is what
	 * keeps nearby agents smooth; the per-tier intervals below throttle the rest.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass", meta=(ClampMin="0.0"))
	float RepresentationUpdateInterval = 0.f;

	/** Inside this camera distance agents are re-sampled from Mass every pass. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.0"))
	float RepresentationNearDistance = 4000.f;

	/** Beyond RepresentationNearDistance, the boundary to the cheapest tier. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.0"))
	float RepresentationFarDistance = 12000.f;

	/** Seconds between Mass samples for agents between near and far. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.0"))
	float RepresentationMidInterval = 0.06f;

	/** Seconds between Mass samples for agents past RepresentationFarDistance. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.0"))
	float RepresentationFarInterval = 0.15f;

	/** Stop submitting distant crowd instances. Zero keeps the legacy no-cull behaviour. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.0"))
	float RepresentationEndCullDistance = 30000.f;

	/** Emissive colour of the selection outline drawn around the inspected agent. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	FLinearColor SelectionHighlightColor = FLinearColor(0.10f, 1.f, 0.35f, 1.f);

	/** Emissive multiplier; over 1 so the outline blooms clear of the district lighting. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="1.0"))
	float SelectionHighlightIntensity = 12.f;

	/**
	 * Outline width in centimetres. The hull is widened along the vertex normal by
	 * the material, not by scaling the instance: the crowd's pose is written by the
	 * material's world position offset, so an inflated transform changes nothing.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0.1"))
	float SelectionOutlineThickness = 2.2f;

	/**
	 * Back-face-only unlit hull material authored by `-run=PCSPSelectionOutlineMaterial`.
	 * Without it the shell would re-draw the body's own lit material over itself, so
	 * the fallback below is used instead.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	TObjectPtr<UMaterialInterface> SelectionOutlineMaterial;

	/** Index into AnimationData->Animations played by agents holding still. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0"))
	int32 IdleAnimationIndex = 0;

	/** Index into AnimationData->Animations played by agents in transit. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation", meta=(ClampMin="0"))
	int32 WalkAnimationIndex = 2;

	/** GPU-skinned static mesh paired with AnimationData; static Manny is the fallback. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	TObjectPtr<UStaticMesh> RepresentationMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	TObjectPtr<UAnimToTextureDataAsset> AnimationData;

	/** Offset for the baked mesh relative to the Mass transform. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	FVector RepresentationLocationOffset = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Mass|Representation")
	FRotator RepresentationRotationOffset = FRotator(0.f, -90.f, 0.f);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Mass|Representation")
	TObjectPtr<UInstancedStaticMeshComponent> Representation;

	/** Single-instance overlay marking the agent the HUD is inspecting. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Mass|Representation")
	TObjectPtr<UInstancedStaticMeshComponent> SelectionHighlight;

	/** Body-tinted ISM groups, one idle/walk pair per affordance category. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Mass|Representation")
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> CategoryRepresentations;

	/** Compatibility-only; head indicators are no longer created or rendered. */
	UPROPERTY(Transient, meta=(DeprecatedProperty, DeprecationMessage="Mass bodies are tinted by category."))
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> GoalIndicators;

private:
	FTransform MakeRepresentationTransform(const FTransform& EntityTransform,
		int32 StableIndex, bool bMoving, float WorldTime) const;
	void UpdateRepresentation();
	void UpdateSelectionHighlight(float WorldTime);
	void SetupCategoryMaterials();

	/** Retained only for reproducible before/after profiling; Manny is the default. */
	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> CylinderBaselineMesh;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInterface> CategoryBaseMaterial;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInterface> VertexAnimationMaterial;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> CategoryMaterials;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SelectionHighlightMaterial;

	int32 HighlightedStableIndex = INDEX_NONE;

	/**
	 * True once the reverse-hull outline material is in use. While false the
	 * highlighted agent is drawn *only* by the shell, tinted solid; re-drawing a
	 * second lit copy over the body is what produced the mottled overlay.
	 */
	bool bUsingOutlineShell = false;

	/** Last pose sampled out of Mass, so distant agents can skip fragment reads. */
	struct FRepresentationSample
	{
		FTransform EntityTransform;
		int32 CategoryIndex = 0;
		float WalkPlayRate = 1.2f;
		float NextSampleTime = 0.f;
		bool bValid = false;
	};
	TArray<FRepresentationSample> RepresentationSamples;

	/** Stable index occupying each instance slot; guards redundant custom-data writes. */
	TArray<TArray<int32>> AutoPlayKeysByCategory;
	TArray<TArray<float>> AutoPlayRatesByCategory;

	TArray<TArray<int32>> StableIndicesByCategory;
	bool bLoggedCategoryVisualization = false;

	TArray<FMassEntityHandle> SpawnedEntities;
	bool bUsingCharacterRepresentation = true;
	bool bUsingVertexAnimation = false;
	float TimeUntilRepresentationUpdate = 0.f;
	float TimeUntilSpawnRetry = 0.f;
	bool bLoggedNavigationWait = false;
	bool bWaitingForSpawn = false;
};
