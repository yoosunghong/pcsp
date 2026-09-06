#include "PCSPZoneLayoutCommandlet.h"

#include "Affordance/PCSPAffordanceZone.h"
#include "Affordance/PCSPInteractionPoint.h"
#include "Affordance/PCSPZoneLayoutMix.h"
#include "Editor.h"
#include "EngineUtils.h"
#include "FileHelpers.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "UObject/SavePackage.h"
#include "WorldPartition/WorldPartition.h"

namespace PCSPZoneLayout
{
	constexpr TCHAR MapPath[] = TEXT("/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio");
	constexpr TCHAR ZoneClassPath[] = TEXT("/Game/PCSP/Blueprints/Actors/BP_AffordanceZone.BP_AffordanceZone_C");
	constexpr TCHAR PointClassPath[] = TEXT("/Game/PCSP/Blueprints/Actors/BP_InteractionPoint.BP_InteractionPoint_C");
	constexpr int32 WideLayoutColumns = 12;
	// Compact portfolio district: neighboring zone footprints remain disjoint,
	// while cross-category travel is short enough to read well in a live demo.
	// The legacy "Wide" symbol/CLI names are retained for runbook compatibility.
	constexpr float WideLayoutSpacingX = 2500.f;
	constexpr float WideLayoutSpacingY = 2000.f;
	constexpr float WideSlotSpacing = 420.f;
	constexpr float WideBoundsPadding = 320.f;
	constexpr float WideSlotMarkerRadius = 72.f;
	constexpr float MinimumSlotClearance = WideSlotMarkerRadius * 2.f + 20.f;

	// Capacity expansion. The original district authored 592 slots for a 1,024
	// entity crowd and no Idle zones at all, so IdleReflect - roughly half of all
	// policy decisions - could never match a zone and Social was ~4x oversubscribed.
	// These targets are demand-weighted against the observed action distribution
	// and total 1,704 slots, ~1.66 slots per entity.
	constexpr float ExpandedSlotSpacing = 280.f;
	constexpr int32 ExpandedZoneCount = 118;
	constexpr int32 ExpandedSlotCount = 1704;

	struct FCapacityTarget
	{
		EPCSPAffordanceCategory Category;
		const TCHAR* DisplayName;
		const TCHAR* TagStem;
		int32 ZoneCount;
		int32 SlotsPerZone;
	};

	static TArray<FCapacityTarget> BuildCapacityTargets()
	{
		// MakeGridRelativeLocation lays slots out as a near-square grid, so at
		// ExpandedSlotSpacing the per-zone ceiling is 30 slots (6x5) before a zone
		// footprint would exceed the 2000 cm row pitch. Nothing here approaches it.
		return {
			{ EPCSPAffordanceCategory::Idle, TEXT("Idle"), TEXT("Plaza"), 20, 28 },
			{ EPCSPAffordanceCategory::Social, TEXT("Social"), TEXT("Hub"), 16, 28 },
			{ EPCSPAffordanceCategory::Rest, TEXT("Rest"), TEXT("Apt"), 16, 12 },
			{ EPCSPAffordanceCategory::Observe, TEXT("Observe"), TEXT("View"), 10, 14 },
			{ EPCSPAffordanceCategory::Work, TEXT("Work"), TEXT("Office"), 12, 8 },
			{ EPCSPAffordanceCategory::Eat, TEXT("Eat"), TEXT("Venue"), 10, 8 },
			{ EPCSPAffordanceCategory::Study, TEXT("Study"), TEXT("Bay"), 10, 6 },
			{ EPCSPAffordanceCategory::Shop, TEXT("Shop"), TEXT("Stall"), 8, 6 },
			{ EPCSPAffordanceCategory::Exercise, TEXT("Exercise"), TEXT("Bay"), 8, 6 },
			{ EPCSPAffordanceCategory::Hygiene, TEXT("Hygiene"), TEXT("Wash"), 8, 4 },
		};
	}

	struct FCategoryPlan
	{
		EPCSPAffordanceCategory Category;
		const TCHAR* DisplayName;
		const TCHAR* TagStem;
		int32 ExistingCount;
		TArray<int32> NewCapacities;
	};

	static TArray<FCategoryPlan> BuildPlans()
	{
		return {
			{ EPCSPAffordanceCategory::Rest, TEXT("Rest"), TEXT("Apt"), 1, { 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4 } },
			{ EPCSPAffordanceCategory::Social, TEXT("Social"), TEXT("Hub"), 1, { 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5 } },
			{ EPCSPAffordanceCategory::Work, TEXT("Work"), TEXT("Office"), 1, { 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4 } },
			{ EPCSPAffordanceCategory::Eat, TEXT("Eat"), TEXT("Venue"), 1, { 5, 5, 5, 5, 5, 5, 5, 5, 4 } },
			{ EPCSPAffordanceCategory::Study, TEXT("Study"), TEXT("Bay"), 1, { 5, 5, 5, 5, 4, 4, 4, 4, 4 } },
			{ EPCSPAffordanceCategory::Observe, TEXT("Observe"), TEXT("View"), 2, { 6, 6, 6, 6, 6, 6, 6, 6 } },
			{ EPCSPAffordanceCategory::Exercise, TEXT("Exercise"), TEXT("Bay"), 1, { 6, 5, 5, 5, 5, 5, 5 } },
			{ EPCSPAffordanceCategory::Hygiene, TEXT("Hygiene"), TEXT("Wash"), 1, { 3, 3, 2, 2, 2, 2, 2 } },
			{ EPCSPAffordanceCategory::Shop, TEXT("Shop"), TEXT("Stall"), 1, { 4, 4, 3, 3, 3, 3, 3 } },
		};
	}

	static FGameplayTag MakeTag(const FCapacityTarget& Target, const int32 OneBasedIndex)
	{
		const FString TagName = FString::Printf(TEXT("PCSP.Zone.%s.%s_%02d"),
			Target.DisplayName, Target.TagStem, OneBasedIndex);
		return FGameplayTag::RequestGameplayTag(FName(*TagName), true);
	}

	static FGameplayTag MakeTag(const FCategoryPlan& Plan, const int32 OneBasedIndex)
	{
		const FString TagName = FString::Printf(TEXT("PCSP.Zone.%s.%s_%02d"), Plan.DisplayName, Plan.TagStem, OneBasedIndex);
		return FGameplayTag::RequestGameplayTag(FName(*TagName), true);
	}

	static void CommitActor(AActor* Actor)
	{
		Actor->PostEditChange();
		Actor->MarkPackageDirty();
	}

	static FVector MakeZoneLocation(const int32 PlacementIndex)
	{
		static const FVector2D SectorCenters[] = {
			{ -5200.f, -5200.f }, { 0.f, -5200.f }, { 5200.f, -5200.f },
			{ -5200.f, -470.f }, { 0.f, -470.f }, { 5200.f, -470.f },
			{ -5200.f, 4300.f }, { 0.f, 4300.f }, { 5200.f, 4300.f },
		};

		const int32 SectorIndex = PlacementIndex % UE_ARRAY_COUNT(SectorCenters);
		const int32 LocalIndex = PlacementIndex / UE_ARRAY_COUNT(SectorCenters);
		const FVector2D LocalOffset(
			(static_cast<float>(LocalIndex % 3) - 1.f) * 1200.f,
			(static_cast<float>(LocalIndex / 3) - 1.f) * 1100.f);
		return FVector(SectorCenters[SectorIndex] + LocalOffset, 20.f);
	}

	static FVector MakePointLocation(const FVector& ZoneLocation, const int32 PointIndex, const int32 PointCount)
	{
		const int32 Columns = PointCount > 4 ? 3 : 2;
		const int32 Row = PointIndex / Columns;
		const int32 Column = PointIndex % Columns;
		const float CenteredX = (static_cast<float>(Column) - (static_cast<float>(Columns) - 1.f) * 0.5f) * 260.f;
		const int32 Rows = FMath::DivideAndRoundUp(PointCount, Columns);
		const float CenteredY = (static_cast<float>(Row) - (static_cast<float>(Rows) - 1.f) * 0.5f) * 260.f;
		return ZoneLocation + FVector(CenteredX, CenteredY, 0.f);
	}

	static FVector MakeWideZoneLocation(const int32 PlacementIndex, const int32 ZoneCount)
	{
		const int32 Rows = FMath::DivideAndRoundUp(ZoneCount, WideLayoutColumns);
		const int32 Column = PlacementIndex % WideLayoutColumns;
		const int32 Row = PlacementIndex / WideLayoutColumns;
		return FVector(
			(static_cast<float>(Column) - (static_cast<float>(WideLayoutColumns) - 1.f) * 0.5f) * WideLayoutSpacingX,
			(static_cast<float>(Row) - (static_cast<float>(Rows) - 1.f) * 0.5f) * WideLayoutSpacingY,
			20.f);
	}

	static FVector MakeGridRelativeLocation(const int32 SlotIndex, const int32 SlotCount, const float Spacing)
	{
		const int32 Columns = FMath::CeilToInt(FMath::Sqrt(static_cast<float>(FMath::Max(1, SlotCount))));
		const int32 Rows = FMath::DivideAndRoundUp(FMath::Max(1, SlotCount), Columns);
		const int32 Column = SlotIndex % Columns;
		const int32 Row = SlotIndex / Columns;
		return FVector(
			(static_cast<float>(Column) - (static_cast<float>(Columns) - 1.f) * 0.5f) * Spacing,
			(static_cast<float>(Row) - (static_cast<float>(Rows) - 1.f) * 0.5f) * Spacing,
			0.f);
	}

	struct FLayoutMetrics
	{
		FVector2D Min = FVector2D(TNumericLimits<float>::Max());
		FVector2D Max = FVector2D(TNumericLimits<float>::Lowest());
		float MinimumSlotDistance = TNumericLimits<float>::Max();
		int32 ZoneOverlapPairs = 0;
		int32 SlotOverlapPairs = 0;
		int32 SlotCount = 0;
	};

	static FLayoutMetrics MeasureLayout(
		const TArray<APCSPAffordanceZone*>& Zones,
		const bool bProposedWideLayout)
	{
		struct FZoneFootprint
		{
			FVector2D Center = FVector2D::ZeroVector;
			FVector2D Extent = FVector2D::ZeroVector;
		};

		FLayoutMetrics Metrics;
		TArray<FZoneFootprint> Footprints;
		TArray<FVector2D> SlotLocations;
		Footprints.Reserve(Zones.Num());

		for (int32 ZoneIndex = 0; ZoneIndex < Zones.Num(); ++ZoneIndex)
		{
			const APCSPAffordanceZone* Zone = Zones[ZoneIndex];
			if (!Zone) { continue; }
			const FVector ZoneLocation = bProposedWideLayout
				? MakeWideZoneLocation(ZoneIndex, Zones.Num())
				: Zone->GetActorLocation();
			const int32 SlotCount = Zone->GetInteractionSlotCount();
			float MaxAbsX = 0.f;
			float MaxAbsY = 0.f;
			for (int32 SlotIndex = 0; SlotIndex < SlotCount; ++SlotIndex)
			{
				const FVector Relative = bProposedWideLayout
					? MakeGridRelativeLocation(SlotIndex, SlotCount, WideSlotSpacing)
					: Zone->InteractionSlots[SlotIndex].RelativeLocation;
				MaxAbsX = FMath::Max(MaxAbsX, FMath::Abs(Relative.X));
				MaxAbsY = FMath::Max(MaxAbsY, FMath::Abs(Relative.Y));
				SlotLocations.Add(FVector2D(ZoneLocation + Relative));
			}
			const float Padding = bProposedWideLayout ? WideBoundsPadding : Zone->BoundsPadding;
			FZoneFootprint& Footprint = Footprints.AddDefaulted_GetRef();
			Footprint.Center = FVector2D(ZoneLocation);
			Footprint.Extent = FVector2D(
				FMath::Max(100.f, MaxAbsX + Padding),
				FMath::Max(100.f, MaxAbsY + Padding));
			Metrics.Min.X = FMath::Min(Metrics.Min.X, Footprint.Center.X - Footprint.Extent.X);
			Metrics.Min.Y = FMath::Min(Metrics.Min.Y, Footprint.Center.Y - Footprint.Extent.Y);
			Metrics.Max.X = FMath::Max(Metrics.Max.X, Footprint.Center.X + Footprint.Extent.X);
			Metrics.Max.Y = FMath::Max(Metrics.Max.Y, Footprint.Center.Y + Footprint.Extent.Y);
			Metrics.SlotCount += SlotCount;
		}

		for (int32 LeftIndex = 0; LeftIndex < Footprints.Num(); ++LeftIndex)
		{
			for (int32 RightIndex = LeftIndex + 1; RightIndex < Footprints.Num(); ++RightIndex)
			{
				const FZoneFootprint& Left = Footprints[LeftIndex];
				const FZoneFootprint& Right = Footprints[RightIndex];
				if (FMath::Abs(Left.Center.X - Right.Center.X) < Left.Extent.X + Right.Extent.X
					&& FMath::Abs(Left.Center.Y - Right.Center.Y) < Left.Extent.Y + Right.Extent.Y)
				{
					++Metrics.ZoneOverlapPairs;
				}
			}
		}

		for (int32 LeftIndex = 0; LeftIndex < SlotLocations.Num(); ++LeftIndex)
		{
			for (int32 RightIndex = LeftIndex + 1; RightIndex < SlotLocations.Num(); ++RightIndex)
			{
				const float Distance = FVector2D::Distance(SlotLocations[LeftIndex], SlotLocations[RightIndex]);
				Metrics.MinimumSlotDistance = FMath::Min(Metrics.MinimumSlotDistance, Distance);
				if (Distance < MinimumSlotClearance)
				{
					++Metrics.SlotOverlapPairs;
				}
			}
		}
		return Metrics;
	}

	static void LogLayoutMetrics(const TCHAR* Label, const FLayoutMetrics& Metrics)
	{
		UE_LOG(LogTemp, Display,
			TEXT("PCSP compact layout %s: extent %.0f x %.0f cm, slots=%d, zone_overlap_pairs=%d, slot_overlap_pairs=%d, minimum_slot_distance=%.1f cm."),
			Label,
			Metrics.Max.X - Metrics.Min.X,
			Metrics.Max.Y - Metrics.Min.Y,
			Metrics.SlotCount,
			Metrics.ZoneOverlapPairs,
			Metrics.SlotOverlapPairs,
			Metrics.MinimumSlotDistance);
	}

	static void ConfigurePoint(APCSPInteractionPoint& Point, const FGameplayTag Tag, const EPCSPAffordanceCategory Category)
	{
		Point.Modify();
		Point.AffordanceTag = Tag;
		Point.Category = Category;
		Point.SetIsSpatiallyLoaded(false);
		Point.InteractionDuration = 3.f;
		CommitActor(&Point);
	}

	static int32 ConfigureZonePoints(APCSPAffordanceZone& Zone)
	{
		int32 Count = 0;
		for (APCSPInteractionPoint* Point : Zone.InteractionPoints)
		{
			if (Point)
			{
				ConfigurePoint(*Point, Zone.ZoneTag, Zone.Category);
				++Count;
			}
		}
		return Count;
	}
}

UPCSPZoneLayoutCommandlet::UPCSPZoneLayoutCommandlet()
{
	IsClient = false;
	IsEditor = true;
	IsServer = false;
	LogToConsole = true;
}

int32 UPCSPZoneLayoutCommandlet::Main(const FString& Params)
{
	using namespace PCSPZoneLayout;

	FString RequestedMap;
	FParse::Value(*Params, TEXT("Map="), RequestedMap);
	const FString LongMapPath = RequestedMap.IsEmpty() ? FString(MapPath) : RequestedMap;
	FString MapFilename;
	if (!FPackageName::TryConvertLongPackageNameToFilename(LongMapPath, MapFilename, FPackageName::GetMapPackageExtension()))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: invalid map path '%s'."), *LongMapPath);
		return 2;
	}

	if (!FEditorFileUtils::LoadMap(MapFilename, false, false))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: failed to load '%s'."), *LongMapPath);
		return 3;
	}

	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	UClass* ZoneClass = LoadClass<APCSPAffordanceZone>(nullptr, ZoneClassPath);
	if (!World || !ZoneClass)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: world or Blueprint classes unavailable."));
		return 4;
	}

	TArray<APCSPAffordanceZone*> ExistingZones;
	for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
	{
		ExistingZones.Add(*It);
	}
	const bool bRelayoutWide = FParse::Param(*Params, TEXT("RelayoutWide"))
		|| FParse::Param(*Params, TEXT("RelayoutCompact"));
	const bool bDryRun = FParse::Param(*Params, TEXT("DryRun"));
	if (FParse::Param(*Params, TEXT("ExpandCapacity")))
	{
		if (LongMapPath != MapPath)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP capacity: refusing to modify non-Portfolio map '%s'."), *LongMapPath);
			return 30;
		}
		for (TActorIterator<APCSPInteractionPoint> It(World); It; ++It)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP capacity: legacy point actors remain; run -Repair first."));
			return 31;
		}

		const TArray<FCapacityTarget> Targets = BuildCapacityTargets();
		TMap<EPCSPAffordanceCategory, TArray<APCSPAffordanceZone*>> ZonesByCategory;
		for (APCSPAffordanceZone* Zone : ExistingZones)
		{
			// ZoneTag is reassigned from the target table below, so an empty tag left
			// by an interrupted run is repairable here. Only Category is required,
			// because it is what the zones are grouped by.
			if (!Zone || Zone->Category == EPCSPAffordanceCategory::None)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP capacity: zone with no affordance category encountered."));
				return 32;
			}
			ZonesByCategory.FindOrAdd(Zone->Category).Add(Zone);
		}

		// Re-running must converge on the same district rather than duplicating it,
		// so surplus zones are an error instead of something to silently delete.
		int32 PlannedZoneCount = 0;
		for (const FCapacityTarget& Target : Targets)
		{
			const int32 Found = ZonesByCategory.FindRef(Target.Category).Num();
			if (Found > Target.ZoneCount)
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP capacity: %s has %d zones but the target is %d; refusing to delete."),
					Target.DisplayName, Found, Target.ZoneCount);
				return 33;
			}
			PlannedZoneCount += Target.ZoneCount;
		}
		if (PlannedZoneCount != ExpandedZoneCount)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP capacity: target table sums to %d zones, expected %d."),
				PlannedZoneCount, ExpandedZoneCount);
			return 34;
		}
		if (bDryRun)
		{
			int32 ProjectedSlots = 0;
			for (const FCapacityTarget& Target : Targets)
			{
				const int32 Found = ZonesByCategory.FindRef(Target.Category).Num();
				ProjectedSlots += Target.ZoneCount * Target.SlotsPerZone;
				UE_LOG(LogTemp, Display,
					TEXT("PCSP capacity dry-run: %-9s zones %2d -> %2d, slots %2d each, %4d total."),
					Target.DisplayName, Found, Target.ZoneCount,
					Target.SlotsPerZone, Target.ZoneCount * Target.SlotsPerZone);
			}
			UE_LOG(LogTemp, Display,
				TEXT("PCSP capacity dry-run complete: %d zones / %d slots; no packages modified."),
				PlannedZoneCount, ProjectedSlots);
			return ProjectedSlots == ExpandedSlotCount ? 0 : 35;
		}

		TArray<APCSPAffordanceZone*> PlannedZones;
		PlannedZones.Reserve(ExpandedZoneCount);
		for (const FCapacityTarget& Target : Targets)
		{
			TArray<APCSPAffordanceZone*> CategoryZones = ZonesByCategory.FindRef(Target.Category);
			// Zones repaired by an earlier run may carry an empty tag, so fall back
			// to the actor name to keep the assignment order deterministic.
			CategoryZones.Sort([](const APCSPAffordanceZone& Left, const APCSPAffordanceZone& Right)
			{
				const FString LeftTag = Left.ZoneTag.ToString();
				const FString RightTag = Right.ZoneTag.ToString();
				return LeftTag == RightTag ? Left.GetName() < Right.GetName() : LeftTag < RightTag;
			});
			for (int32 Index = 0; Index < Target.ZoneCount; ++Index)
			{
				APCSPAffordanceZone* Zone = CategoryZones.IsValidIndex(Index)
					? CategoryZones[Index] : nullptr;
				if (!Zone)
				{
					const FName ActorName(*FString::Printf(TEXT("PCSP_%s_%s_%02d"),
						Target.DisplayName, Target.TagStem, Index + 1));
					FActorSpawnParameters SpawnParameters;
					SpawnParameters.OverrideLevel = World->PersistentLevel;
					SpawnParameters.Name = ActorName;
					Zone = World->SpawnActor<APCSPAffordanceZone>(
						ZoneClass, FVector::ZeroVector, FRotator::ZeroRotator, SpawnParameters);
					if (!Zone)
					{
						UE_LOG(LogTemp, Error,
							TEXT("PCSP capacity: failed to spawn %s."), *ActorName.ToString());
						return 36;
					}
					Zone->Modify();
					Zone->SetActorLabel(ActorName.ToString());
				}
				Zone->Modify();
				// Assign identity on every pass, not just on spawn, so a re-run also
				// repairs zones left untagged by a previous one.
				Zone->ZoneTag = MakeTag(Target, Index + 1);
				Zone->Category = Target.Category;
				if (!Zone->ZoneTag.IsValid())
				{
					// RequestGameplayTag returns an empty tag for unregistered names.
					UE_LOG(LogTemp, Error,
						TEXT("PCSP capacity: gameplay tag PCSP.Zone.%s.%s_%02d is not registered; ")
						TEXT("add it to Config/DefaultGameplayTags.ini before running."),
						Target.DisplayName, Target.TagStem, Index + 1);
					return 42;
				}
				Zone->InteractionPointCount = Target.SlotsPerZone;
				Zone->bAutoGenerateGrid = true;
				Zone->InteractionPoints.Reset();
				Zone->InteractionPointSpacing = ExpandedSlotSpacing;
				Zone->BoundsPadding = WideBoundsPadding;
				Zone->SlotMarkerRadius = WideSlotMarkerRadius;
				Zone->SlotMarkerHeight = 5.f;
				Zone->SetIsSpatiallyLoaded(false);
				PlannedZones.Add(Zone);
			}
		}

		// Interleave categories before placement so 18 consecutive Idle plazas do
		// not land as one block; the seeded permutation keeps runs reproducible.
		int32 LayoutSeed = 17;
		FParse::Value(*Params, TEXT("LayoutSeed="), LayoutSeed);
		TArray<int32> Categories;
		for (const APCSPAffordanceZone* Zone : PlannedZones)
		{
			Categories.Add(static_cast<int32>(Zone->Category));
		}
		const TArray<int32> MixedOrder = PCSPZoneLayoutMix::BuildOrder(
			Categories, WideLayoutColumns, LayoutSeed);
		TArray<APCSPAffordanceZone*> OrderedZones;
		OrderedZones.Reserve(PlannedZones.Num());
		for (const int32 ZoneIndex : MixedOrder)
		{
			OrderedZones.Add(PlannedZones[ZoneIndex]);
		}
		if (OrderedZones.Num() != PlannedZones.Num())
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP capacity: category interleave lost zone entries."));
			return 37;
		}

		int32 AppliedSlots = 0;
		for (int32 ZoneIndex = 0; ZoneIndex < OrderedZones.Num(); ++ZoneIndex)
		{
			APCSPAffordanceZone* Zone = OrderedZones[ZoneIndex];
			Zone->SetActorLocation(MakeWideZoneLocation(ZoneIndex, OrderedZones.Num()),
				false, nullptr, ETeleportType::TeleportPhysics);
			Zone->VisualizationIndex = ZoneIndex;
			Zone->RerunConstructionScripts();
			if (Zone->GetInteractionSlotCount() != Zone->Capacity)
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP capacity: zone '%s' capacity %d does not match slot count %d."),
					*Zone->GetName(), Zone->Capacity, Zone->GetInteractionSlotCount());
				return 38;
			}
			AppliedSlots += Zone->GetInteractionSlotCount();
			CommitActor(Zone);
		}

		const FLayoutMetrics AppliedMetrics = MeasureLayout(OrderedZones, false);
		LogLayoutMetrics(TEXT("expanded"), AppliedMetrics);
		if (AppliedSlots != ExpandedSlotCount)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP capacity: expected %d slots, applied %d."),
				ExpandedSlotCount, AppliedSlots);
			return 39;
		}
		if (AppliedMetrics.ZoneOverlapPairs != 0 || AppliedMetrics.SlotOverlapPairs != 0
			|| AppliedMetrics.MinimumSlotDistance < MinimumSlotClearance)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP capacity: expanded layout failed non-overlap validation; refusing to save."));
			return 40;
		}

		World->PersistentLevel->MarkPackageDirty();
		if (!UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true))
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP capacity: failed to save World Partition packages."));
			return 41;
		}
		UE_LOG(LogTemp, Display,
			TEXT("PCSP capacity expansion complete: %d zones and %d slots (was 96 / 592), Idle now served."),
			OrderedZones.Num(), AppliedSlots);
		return 0;
	}
	if (bRelayoutWide)
	{
		if (LongMapPath != MapPath)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP wide layout: refusing to modify non-Portfolio map '%s'."), *LongMapPath);
			return 20;
		}
		if (ExistingZones.Num() != 96 && ExistingZones.Num() != ExpandedZoneCount)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP wide layout: expected 96 or %d zones, found %d."),
				ExpandedZoneCount, ExistingZones.Num());
			return 21;
		}

		TArray<APCSPInteractionPoint*> LegacyPoints;
		for (TActorIterator<APCSPInteractionPoint> It(World); It; ++It)
		{
			LegacyPoints.Add(*It);
		}
		if (!LegacyPoints.IsEmpty())
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP wide layout: %d legacy point actors remain; run -Repair first."), LegacyPoints.Num());
			return 22;
		}

		ExistingZones.Sort([](const APCSPAffordanceZone& Left, const APCSPAffordanceZone& Right)
		{
			if (Left.Category != Right.Category)
			{
				return static_cast<uint8>(Left.Category) < static_cast<uint8>(Right.Category);
			}
			return Left.ZoneTag.ToString() < Right.ZoneTag.ToString();
		});

		// Unity PCSP scaling uses seeded, spatially interleaved venues. Start from
		// a seeded permutation, then repair adjacent same-category pairs instead
		// of repeating a fixed category cycle along every row.
		int32 LayoutSeed = 17;
		FParse::Value(*Params, TEXT("LayoutSeed="), LayoutSeed);
		TArray<int32> Categories;
		for (APCSPAffordanceZone* Zone : ExistingZones)
		{
			Categories.Add(static_cast<int32>(Zone->Category));
		}
		const TArray<int32> MixedOrder = PCSPZoneLayoutMix::BuildOrder(
			Categories, WideLayoutColumns, LayoutSeed);
		TArray<APCSPAffordanceZone*> InterleavedZones;
		InterleavedZones.Reserve(ExistingZones.Num());
		for (const int32 ZoneIndex : MixedOrder)
		{
			InterleavedZones.Add(ExistingZones[ZoneIndex]);
		}
		UE_LOG(LogTemp, Display, TEXT("PCSP compact layout: seed=%d same_category_neighbor_pairs=%d"),
			LayoutSeed, PCSPZoneLayoutMix::NeighborPenalty(MixedOrder, Categories, WideLayoutColumns));
		if (InterleavedZones.Num() != ExistingZones.Num())
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP compact layout: category interleave lost zone entries."));
			return 28;
		}
		ExistingZones = MoveTemp(InterleavedZones);

		TSet<FGameplayTag> ZoneTags;
		int32 PersistedSlots = 0;
		for (const APCSPAffordanceZone* Zone : ExistingZones)
		{
			if (!Zone || !Zone->ZoneTag.IsValid() || ZoneTags.Contains(Zone->ZoneTag)
				|| Zone->Category == EPCSPAffordanceCategory::None
				|| !Zone->InteractionPoints.IsEmpty()
				|| Zone->Capacity != Zone->GetInteractionSlotCount())
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP wide layout: invalid metadata, duplicate tag, legacy reference, or capacity mismatch."));
				return 23;
			}
			ZoneTags.Add(Zone->ZoneTag);
			PersistedSlots += Zone->GetInteractionSlotCount();
		}
		if (PersistedSlots != 592 && PersistedSlots != ExpandedSlotCount)
		{
			UE_LOG(LogTemp, Error,
				TEXT("PCSP wide layout: expected 592 or %d slots, found %d."),
				ExpandedSlotCount, PersistedSlots);
			return 24;
		}

		const FLayoutMetrics CurrentMetrics = MeasureLayout(ExistingZones, false);
		const FLayoutMetrics ProposedMetrics = MeasureLayout(ExistingZones, true);
		LogLayoutMetrics(TEXT("current"), CurrentMetrics);
		LogLayoutMetrics(TEXT("proposed"), ProposedMetrics);
		if (ProposedMetrics.ZoneOverlapPairs != 0 || ProposedMetrics.SlotOverlapPairs != 0
			|| ProposedMetrics.MinimumSlotDistance < MinimumSlotClearance)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP wide layout: proposed layout failed non-overlap validation."));
			return 25;
		}
		if (bDryRun)
		{
			UE_LOG(LogTemp, Display,
				TEXT("PCSP compact layout dry-run complete: no packages modified; execute with -RelayoutCompact."));
			return 0;
		}

		for (int32 ZoneIndex = 0; ZoneIndex < ExistingZones.Num(); ++ZoneIndex)
		{
			APCSPAffordanceZone* Zone = ExistingZones[ZoneIndex];
			Zone->Modify();
			Zone->SetActorLocation(MakeWideZoneLocation(ZoneIndex, ExistingZones.Num()), false, nullptr, ETeleportType::TeleportPhysics);
			Zone->VisualizationIndex = ZoneIndex;
			Zone->InteractionPointCount = Zone->GetInteractionSlotCount();
			Zone->bAutoGenerateGrid = true;
			Zone->InteractionPointSpacing = WideSlotSpacing;
			Zone->BoundsPadding = WideBoundsPadding;
			Zone->SlotMarkerRadius = WideSlotMarkerRadius;
			Zone->SlotMarkerHeight = 5.f;
			Zone->SetIsSpatiallyLoaded(false);
			Zone->RerunConstructionScripts();
			CommitActor(Zone);
		}

		const FLayoutMetrics AppliedMetrics = MeasureLayout(ExistingZones, false);
		LogLayoutMetrics(TEXT("applied"), AppliedMetrics);
		if (AppliedMetrics.ZoneOverlapPairs != 0 || AppliedMetrics.SlotOverlapPairs != 0
			|| AppliedMetrics.MinimumSlotDistance < MinimumSlotClearance)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP wide layout: applied layout failed validation; refusing to save."));
			return 26;
		}

		World->PersistentLevel->MarkPackageDirty();
		if (!UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true))
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP wide layout: failed to save World Partition packages."));
			return 27;
		}
		UE_LOG(LogTemp, Display,
			TEXT("PCSP compact layout complete: 96 interleaved zones and 592 slots arranged in a 12 x 8 district, with zero overlaps."));
		return 0;
	}
	const bool bRepair = FParse::Param(*Params, TEXT("Repair"));
	if (bRepair && !ExistingZones.IsEmpty())
	{
		ExistingZones.Sort([](const APCSPAffordanceZone& Left, const APCSPAffordanceZone& Right)
		{
			return Left.ZoneTag.ToString() < Right.ZoneTag.ToString();
		});
		bool bVisualizationIndicesChanged = false;
		for (int32 ZoneIndex = 0; ZoneIndex < ExistingZones.Num(); ++ZoneIndex)
		{
			APCSPAffordanceZone* Zone = ExistingZones[ZoneIndex];
			if (Zone && Zone->VisualizationIndex != ZoneIndex)
			{
				Zone->Modify();
				Zone->VisualizationIndex = ZoneIndex;
				CommitActor(Zone);
				bVisualizationIndicesChanged = true;
			}
		}

		TArray<APCSPInteractionPoint*> AllPoints;
		for (TActorIterator<APCSPInteractionPoint> It(World); It; ++It)
		{
			AllPoints.Add(*It);
		}

		if (AllPoints.IsEmpty())
		{
			int32 PersistedSlots = 0;
			TSet<int32> VisualizationIndices;
			for (const APCSPAffordanceZone* Zone : ExistingZones)
			{
				if (!Zone || !Zone->ZoneTag.IsValid() || Zone->Category == EPCSPAffordanceCategory::None)
				{
					UE_LOG(LogTemp, Error, TEXT("PCSP zone audit: invalid zone metadata encountered."));
					return 5;
				}
				if (!Zone->InteractionPoints.IsEmpty())
				{
					UE_LOG(LogTemp, Error, TEXT("PCSP zone audit: zone '%s' still has legacy point references."), *Zone->GetName());
					return 6;
				}
				if (Zone->Capacity != Zone->GetInteractionSlotCount())
				{
					UE_LOG(LogTemp, Error,
						TEXT("PCSP zone audit: zone '%s' capacity %d does not match slot count %d."),
						*Zone->GetName(), Zone->Capacity, Zone->GetInteractionSlotCount());
					return 7;
				}
				if (Zone->VisualizationIndex < 0 || VisualizationIndices.Contains(Zone->VisualizationIndex))
				{
					UE_LOG(LogTemp, Error,
						TEXT("PCSP zone audit: zone '%s' has invalid or duplicate visualization index %d."),
						*Zone->GetName(), Zone->VisualizationIndex);
					return 8;
				}
				VisualizationIndices.Add(Zone->VisualizationIndex);
				PersistedSlots += Zone->GetInteractionSlotCount();
			}
			if (bVisualizationIndicesChanged
				&& !UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true))
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone audit: failed to save visualization indices."));
				return 9;
			}
			UE_LOG(LogTemp, Display,
				TEXT("PCSP zone integration audit complete: %d uniquely colored zones, %d persisted slots, 0 legacy point actors, palette_reassigned=%s."),
				ExistingZones.Num(), PersistedSlots, bVisualizationIndicesChanged ? TEXT("true") : TEXT("false"));
			const bool bExpectedSlotCount = LongMapPath == MapPath
				? (PersistedSlots == 592 || PersistedSlots == ExpandedSlotCount)
				: PersistedSlots > 0;
			return bExpectedSlotCount ? 0 : 10;
		}

		TSet<APCSPInteractionPoint*> AssignedPoints;
		for (APCSPAffordanceZone* Zone : ExistingZones)
		{
			if (!Zone || !Zone->ZoneTag.IsValid() || Zone->Category == EPCSPAffordanceCategory::None)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: invalid zone metadata encountered."));
				return 5;
			}
			Zone->Modify();
			Zone->InteractionPoints.RemoveAll([&AssignedPoints](APCSPInteractionPoint* Point)
			{
				if (!Point || AssignedPoints.Contains(Point))
				{
					return true;
				}
				AssignedPoints.Add(Point);
				return false;
			});
		}

		for (APCSPInteractionPoint* Point : AllPoints)
		{
			if (!Point || AssignedPoints.Contains(Point))
			{
				continue;
			}

			APCSPAffordanceZone* NearestZone = nullptr;
			float NearestDistanceSquared = TNumericLimits<float>::Max();
			for (APCSPAffordanceZone* Zone : ExistingZones)
			{
				const float DistanceSquared = FVector::DistSquared2D(Point->GetActorLocation(), Zone->GetActorLocation());
				if (DistanceSquared < NearestDistanceSquared)
				{
					NearestDistanceSquared = DistanceSquared;
					NearestZone = Zone;
				}
			}
			if (!NearestZone)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: could not select an owner for an orphan interaction point."));
				return 6;
			}

			NearestZone->Modify();
			NearestZone->InteractionPoints.Add(Point);
			AssignedPoints.Add(Point);
		}

		if (AssignedPoints.Num() != AllPoints.Num())
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: expected every point to have one owner, found %d total and %d assigned."), AllPoints.Num(), AssignedPoints.Num());
			return 7;
		}

		TArray<TPair<UPackage*, FString>> LegacyPointPackages;
		LegacyPointPackages.Reserve(AllPoints.Num());
		FString RelativeMapPath = LongMapPath;
		RelativeMapPath.RemoveFromStart(TEXT("/Game/"));
		const FString ExpectedExternalPackagePrefix = FString(TEXT("/Game/__ExternalActors__/"))
			+ RelativeMapPath + TEXT("/");
		for (APCSPInteractionPoint* Point : AllPoints)
		{
			UPackage* ExternalPackage = Point ? Point->GetPackage() : nullptr;
			FString PackageFilename;
			if (!Point || !Point->IsPackageExternal() || !ExternalPackage
				|| !ExternalPackage->GetName().StartsWith(ExpectedExternalPackagePrefix)
				|| !FPackageName::DoesPackageExist(ExternalPackage->GetName(), &PackageFilename))
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP zone repair: refusing to delete an unexpected interaction-point package for '%s'."),
					Point ? *Point->GetName() : TEXT("null"));
				return 8;
			}
			LegacyPointPackages.Emplace(ExternalPackage, MoveTemp(PackageFilename));
		}

		int32 MigratedSlots = 0;
		for (APCSPAffordanceZone* Zone : ExistingZones)
		{
			MigratedSlots += Zone->MigrateLegacyInteractionPoints();
			Zone->SetIsSpatiallyLoaded(false);
			CommitActor(Zone);
		}
		for (APCSPInteractionPoint* Point : AllPoints)
		{
			if (Point)
			{
				Point->Modify();
				World->EditorDestroyActor(Point, true);
			}
		}
		World->PersistentLevel->MarkPackageDirty();
		if (!UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true))
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: failed to save dirty World Partition packages."));
			return 10;
		}

		int32 DeletedPointPackages = 0;
		for (const TPair<UPackage*, FString>& PackageAndFilename : LegacyPointPackages)
		{
			if (!IFileManager::Get().Delete(*PackageAndFilename.Value, true, false, true))
			{
				UE_LOG(LogTemp, Error,
					TEXT("PCSP zone repair: failed to delete legacy point package '%s'."),
					*PackageAndFilename.Value);
				return 11;
			}
			if (UWorldPartition* WorldPartition = World->GetWorldPartition())
			{
				WorldPartition->OnPackageDeleted(PackageAndFilename.Key);
			}
			++DeletedPointPackages;
		}
		UE_LOG(LogTemp, Display,
			TEXT("PCSP zone integration complete: migrated %d slots into %d uniquely colored zones and removed %d legacy point actors."),
			MigratedSlots, ExistingZones.Num(), DeletedPointPackages);
		return MigratedSlots == AllPoints.Num() && DeletedPointPackages == AllPoints.Num() ? 0 : 12;
	}
	if (ExistingZones.Num() != 10)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: expected 10 baseline zones, found %d. Refusing to create duplicates."), ExistingZones.Num());
		return 8;
	}

	APCSPAffordanceZone* LegacyLeisure = nullptr;
	TMap<EPCSPAffordanceCategory, TArray<APCSPAffordanceZone*>> ExistingByCategory;
	for (APCSPAffordanceZone* Zone : ExistingZones)
	{
		if (Zone->Category == EPCSPAffordanceCategory::Leisure)
		{
			if (LegacyLeisure)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: more than one legacy Leisure zone exists."));
			return 9;
			}
			LegacyLeisure = Zone;
		}
		else
		{
			ExistingByCategory.FindOrAdd(Zone->Category).Add(Zone);
		}
	}
	if (!LegacyLeisure)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: the expected legacy Leisure zone is missing."));
		return 10;
	}

	const TArray<FCategoryPlan> Plans = BuildPlans();
	for (const FCategoryPlan& Plan : Plans)
	{
		const int32 ExistingCount = ExistingByCategory.FindRef(Plan.Category).Num() + (Plan.Category == EPCSPAffordanceCategory::Observe ? 1 : 0);
		if (ExistingCount != Plan.ExistingCount)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: %s expected %d existing zones but found %d."), Plan.DisplayName, Plan.ExistingCount, ExistingCount);
			return 11;
		}
	}

	// The legacy authoring used Leisure for Observe. Preserve its points and make it Observe.View_01.
	const FCategoryPlan& ObservePlan = Plans[5];
	LegacyLeisure->Modify();
	LegacyLeisure->Category = EPCSPAffordanceCategory::Observe;
	LegacyLeisure->ZoneTag = MakeTag(ObservePlan, 1);
	LegacyLeisure->Capacity = LegacyLeisure->InteractionPoints.Num();
	LegacyLeisure->SetIsSpatiallyLoaded(false);
	CommitActor(LegacyLeisure);

	for (const FCategoryPlan& Plan : Plans)
	{
		TArray<APCSPAffordanceZone*> CategoryZones = ExistingByCategory.FindRef(Plan.Category);
		CategoryZones.Sort([](const APCSPAffordanceZone& A, const APCSPAffordanceZone& B)
		{
			return A.GetActorLabel() < B.GetActorLabel();
		});
		for (int32 ExistingIndex = 0; ExistingIndex < CategoryZones.Num(); ++ExistingIndex)
		{
			APCSPAffordanceZone* Zone = CategoryZones[ExistingIndex];
			Zone->Modify();
			Zone->ZoneTag = MakeTag(Plan, ExistingIndex + 1 + (Plan.Category == EPCSPAffordanceCategory::Observe ? 1 : 0));
			Zone->Capacity = Zone->InteractionPoints.Num();
			Zone->SetIsSpatiallyLoaded(false);
			CommitActor(Zone);
		}
	}
	for (APCSPAffordanceZone* Zone : ExistingZones)
	{
		ConfigureZonePoints(*Zone);
	}

	struct FPendingZone
	{
		const FCategoryPlan* Plan;
		int32 TagIndex;
		int32 Capacity;
	};
	TArray<FPendingZone> PendingZones;
	int32 Round = 0;
	while (true)
	{
		bool bAddedThisRound = false;
		for (const FCategoryPlan& Plan : Plans)
		{
			if (Plan.NewCapacities.IsValidIndex(Round))
			{
				PendingZones.Add({ &Plan, Plan.ExistingCount + Round + 1, Plan.NewCapacities[Round] });
				bAddedThisRound = true;
			}
		}
		if (!bAddedThisRound)
		{
			break;
		}
		++Round;
	}
	if (PendingZones.Num() != 86)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: internal plan expected 86 new zones but created %d tasks."), PendingZones.Num());
		return 12;
	}

	int32 AddedSlots = 0;
	for (int32 ZoneIndex = 0; ZoneIndex < PendingZones.Num(); ++ZoneIndex)
	{
		const FPendingZone& Pending = PendingZones[ZoneIndex];
		const FGameplayTag Tag = MakeTag(*Pending.Plan, Pending.TagIndex);
		const FVector ZoneLocation = MakeZoneLocation(ZoneIndex);
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.OverrideLevel = World->PersistentLevel;
		SpawnParameters.Name = FName(*FString::Printf(TEXT("PCSP_%s_%s_%02d"), Pending.Plan->DisplayName, Pending.Plan->TagStem, Pending.TagIndex));
		APCSPAffordanceZone* Zone = World->SpawnActor<APCSPAffordanceZone>(ZoneClass, ZoneLocation, FRotator::ZeroRotator, SpawnParameters);
		if (!Zone)
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: failed to spawn zone %s."), *Tag.ToString());
			return 13;
		}

		Zone->Modify();
		Zone->ZoneTag = Tag;
		Zone->Category = Pending.Plan->Category;
		Zone->InteractionPointCount = Pending.Capacity;
		Zone->bAutoGenerateGrid = true;
		Zone->InteractionPoints.Reset();
		Zone->SetIsSpatiallyLoaded(false);
		Zone->SetActorLabel(SpawnParameters.Name.ToString());
		Zone->RerunConstructionScripts();
		AddedSlots += Zone->GetInteractionSlotCount();
		CommitActor(Zone);
	}

	World->PersistentLevel->MarkPackageDirty();
	const bool bSaved = UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true);
	if (!bSaved)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: failed to save dirty World Partition packages."));
		return 15;
	}

	UE_LOG(LogTemp, Display, TEXT("PCSP zone layout complete: 96 zones with integrated interaction slots (%d added)."), AddedSlots);
	return AddedSlots == 382 ? 0 : 16;
}
