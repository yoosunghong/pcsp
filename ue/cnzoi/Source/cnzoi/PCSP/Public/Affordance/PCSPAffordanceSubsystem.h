#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "GameplayTagContainer.h"
#include "PCSPTypes.h"
#include "PCSPAffordanceSubsystem.generated.h"

class APCSPAffordanceZone;

UENUM(BlueprintType)
enum class EPCSPZoneRejection : uint8
{
	Selected             UMETA(DisplayName="Selected"),
	NoZonesRegistered    UMETA(DisplayName="NoZonesRegistered"),
	AllInvalidWeakPtr    UMETA(DisplayName="AllInvalidWeakPtr"),
	AllCategoryMismatch  UMETA(DisplayName="AllCategoryMismatch"),
	AllOverCapacity      UMETA(DisplayName="AllOverCapacity"),
	AllTooFar            UMETA(DisplayName="AllTooFar"),
};

USTRUCT(BlueprintType)
struct FPCSPZoneSelectionDebug
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly) EPCSPZoneRejection Reason = EPCSPZoneRejection::NoZonesRegistered;
	UPROPERTY(BlueprintReadOnly) int32 RegisteredCount   = 0;  // entries in Zones[]
	UPROPERTY(BlueprintReadOnly) int32 ValidCount        = 0;  // weak-ptr resolved
	UPROPERTY(BlueprintReadOnly) int32 CategoryMatchCount= 0;
	UPROPERTY(BlueprintReadOnly) int32 CapacityOkCount   = 0;
	UPROPERTY(BlueprintReadOnly) int32 InRangeCount      = 0;
	UPROPERTY(BlueprintReadOnly) float NearestDistance   = -1.f;  // among category matches; -1 if none

	FString ToCompactString() const;
};

USTRUCT(BlueprintType)
struct FPCSPAffordanceQuery
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite) EPCSPAffordanceCategory Category = EPCSPAffordanceCategory::None;
	UPROPERTY(BlueprintReadWrite) FGameplayTag PreferredTag;
	UPROPERTY(BlueprintReadWrite) FVector FromLocation = FVector::ZeroVector;
	UPROPERTY(BlueprintReadWrite) float MaxDistance = 50000.f;
	UPROPERTY(BlueprintReadWrite) bool bRequireCapacity = true;
};

UCLASS()
class CNZOI_API UPCSPAffordanceSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	void RegisterZone(APCSPAffordanceZone* Zone);
	void UnregisterZone(APCSPAffordanceZone* Zone);

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	APCSPAffordanceZone* FindBestZone(const FPCSPAffordanceQuery& Query) const;

	/** Diagnostic overload — populates OutDebug with rejection reason + counts. */
	APCSPAffordanceZone* FindBestZone(const FPCSPAffordanceQuery& Query,
	                                  FPCSPZoneSelectionDebug& OutDebug) const;

	UFUNCTION(BlueprintCallable, Category="PCSP|Affordance")
	TArray<APCSPAffordanceZone*> GetZonesByCategory(EPCSPAffordanceCategory Category) const;


	const TArray<TWeakObjectPtr<APCSPAffordanceZone>>& GetAllZones() const { return Zones; }

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

protected:
	UPROPERTY()
	TArray<TWeakObjectPtr<APCSPAffordanceZone>> Zones;

	/** T1.5 contention telemetry — 1 Hz dump of {t, zone_tag, category, occupants, capacity}
	 *  to <session>/zone_occupancy.jsonl. */
	void SampleOccupancy();

	FTimerHandle OccupancySampleTimerHandle;
	FString      OccupancyLogPath;
};
