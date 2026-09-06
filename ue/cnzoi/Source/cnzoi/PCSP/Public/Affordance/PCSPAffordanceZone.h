#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceZone.generated.h"

class APCSPInteractionPoint;
class UBoxComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

USTRUCT(BlueprintType)
struct FPCSPInteractionSlot
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance")
	FVector RelativeLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance", meta=(ClampMin="0.0"))
	float InteractionDuration = 3.f;
};

UCLASS()
class CNZOI_API APCSPAffordanceZone : public AActor
{
	GENERATED_BODY()

public:
	APCSPAffordanceZone();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	FGameplayTag ZoneTag;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;

	/** Stable map-assigned palette index. Slots and targeting NPCs share this color. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Affordance|Visualization")
	int32 VisualizationIndex = INDEX_NONE;

	/** Derived from InteractionSlots. Retained as a visible compatibility field. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	int32 Capacity = 4;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Affordance")
	TObjectPtr<UBoxComponent> Bounds;

	/** Integrated interaction capacity owned and serialized by this Zone. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance")
	TArray<FPCSPInteractionSlot> InteractionSlots;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Generation", meta=(ClampMin="1", ClampMax="256"))
	int32 InteractionPointCount = 4;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Generation")
	bool bAutoGenerateGrid = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Generation", meta=(ClampMin="50.0"))
	float InteractionPointSpacing = 260.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Generation", meta=(ClampMin="0.0"))
	float BoundsPadding = 140.f;

	/** Legacy map input only. Run MigrateLegacyInteractionPoints, then remove the actors. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="PCSP|Affordance|Legacy",
		meta=(DeprecatedProperty, DeprecationMessage="Interaction points are integrated into InteractionSlots."))
	TArray<TObjectPtr<APCSPInteractionPoint>> InteractionPoints;

	/** One circular floor marker per integrated slot, tinted with this Zone's unique color. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="PCSP|Affordance|Visualization")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> SlotMarkers;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Visualization", meta=(ClampMin="10.0"))
	float SlotMarkerRadius = 58.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Affordance|Visualization", meta=(ClampMin="1.0"))
	float SlotMarkerHeight = 4.f;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	int32 GetCurrentOccupancy() const;

	UFUNCTION(BlueprintPure, Category="PCSP|Affordance")
	int32 GetActorOccupancy() const;

	UFUNCTION(BlueprintPure, Category="PCSP|Affordance")
	int32 GetMassOccupancy() const { return MassOccupancy; }

	/** Updated once per Mass simulation frame from the entities' slot claims. */
	void SetMassOccupancy(int32 InOccupancy)
	{
		MassOccupancy = FMath::Clamp(InOccupancy, 0, Capacity);
	}

	bool IsInteractionSlotOccupiedByActor(int32 SlotIndex) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool HasCapacity() const { return FindFreeInteractionSlot() != INDEX_NONE; }

	/** Fraction of the authored zone capacity currently claimed by Hero Actors.
	 *  A claim starts with interaction-point reservation, so this includes agents
	 *  walking toward the zone as well as agents currently interacting. */
	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	float GetOccupancyRatio() const
	{
		return Capacity > 0
			? FMath::Clamp(static_cast<float>(GetCurrentOccupancy()) / static_cast<float>(Capacity), 0.f, 1.f)
			: 1.f;
	}

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void RegisterOccupant(AActor* Actor);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void UnregisterOccupant(AActor* Actor);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	int32 FindFreeInteractionSlot() const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	int32 FindReservedInteractionSlot(AActor* Requester) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool TryReserveInteractionSlot(int32 SlotIndex, AActor* Requester);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	void ReleaseInteractionSlot(int32 SlotIndex, AActor* Requester);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	bool IsInteractionSlotReservedBy(int32 SlotIndex, AActor* Requester) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	FVector GetInteractionSlotWorldLocation(int32 SlotIndex) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	float GetInteractionSlotDuration(int32 SlotIndex) const;

	UFUNCTION(BlueprintPure, Category="PCSP|Affordance|Visualization")
	FLinearColor GetVisualizationColor() const
	{
		return PCSPVisualization::CategoryColor(Category);
	}

	UFUNCTION(BlueprintCallable, CallInEditor, Category="PCSP|Affordance|Migration")
	int32 MigrateLegacyInteractionPoints();

	int32 GetInteractionSlotCount() const { return InteractionSlots.Num(); }

protected:
	UPROPERTY()
	TSet<TWeakObjectPtr<AActor>> CurrentOccupants;

	UPROPERTY(Transient)
	TArray<TWeakObjectPtr<AActor>> SlotReservers;

	UPROPERTY(Transient)
	int32 MassOccupancy = 0;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInterface> SlotMarkerBaseMaterial;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SlotMarkerMaterial;

	void GenerateInteractionGrid();
	int32 ImportLegacyInteractionPointDefinitions(bool bClearReferences);
	void RefreshDerivedState();
	void RefreshSlotMarkers();
};
