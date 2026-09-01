#include "PCSPZoneLayoutCommandlet.h"

#include "Affordance/PCSPAffordanceZone.h"
#include "Affordance/PCSPInteractionPoint.h"
#include "Editor.h"
#include "EngineUtils.h"
#include "FileHelpers.h"
#include "Misc/PackageName.h"
#include "UObject/SavePackage.h"

namespace PCSPZoneLayout
{
	constexpr TCHAR MapPath[] = TEXT("/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio");
	constexpr TCHAR ZoneClassPath[] = TEXT("/Game/PCSP/Blueprints/Actors/BP_AffordanceZone.BP_AffordanceZone_C");
	constexpr TCHAR PointClassPath[] = TEXT("/Game/PCSP/Blueprints/Actors/BP_InteractionPoint.BP_InteractionPoint_C");

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
	UClass* PointClass = LoadClass<APCSPInteractionPoint>(nullptr, PointClassPath);
	if (!World || !ZoneClass || !PointClass)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: world or Blueprint classes unavailable."));
		return 4;
	}

	TArray<APCSPAffordanceZone*> ExistingZones;
	for (TActorIterator<APCSPAffordanceZone> It(World); It; ++It)
	{
		ExistingZones.Add(*It);
	}
	const bool bRepair = FParse::Param(*Params, TEXT("Repair"));
	if (ExistingZones.Num() == 96 && bRepair)
	{
		int32 RepairedPoints = 0;
		for (APCSPAffordanceZone* Zone : ExistingZones)
		{
			if (!Zone || !Zone->ZoneTag.IsValid() || Zone->Category == EPCSPAffordanceCategory::None)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: invalid zone metadata encountered."));
				return 5;
			}
			Zone->Modify();
			Zone->Capacity = Zone->InteractionPoints.Num();
			Zone->SetIsSpatiallyLoaded(false);
			RepairedPoints += ConfigureZonePoints(*Zone);
			CommitActor(Zone);
		}
		World->PersistentLevel->MarkPackageDirty();
		if (!UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true))
		{
			UE_LOG(LogTemp, Error, TEXT("PCSP zone repair: failed to save dirty World Partition packages."));
			return 6;
		}
		UE_LOG(LogTemp, Display, TEXT("PCSP zone repair complete: normalized %d interaction points."), RepairedPoints);
		return RepairedPoints == 592 ? 0 : 7;
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

	int32 AddedPoints = 0;
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
		Zone->Capacity = Pending.Capacity;
		Zone->SetIsSpatiallyLoaded(false);
		Zone->SetActorLabel(SpawnParameters.Name.ToString());

		for (int32 PointIndex = 0; PointIndex < Pending.Capacity; ++PointIndex)
		{
			FActorSpawnParameters PointSpawnParameters;
			PointSpawnParameters.OverrideLevel = World->PersistentLevel;
			PointSpawnParameters.Name = FName(*FString::Printf(TEXT("%s_Point_%02d"), *SpawnParameters.Name.ToString(), PointIndex + 1));
			APCSPInteractionPoint* Point = World->SpawnActor<APCSPInteractionPoint>(PointClass, MakePointLocation(ZoneLocation, PointIndex, Pending.Capacity), FRotator::ZeroRotator, PointSpawnParameters);
			if (!Point)
			{
				UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: failed to spawn point %d for %s."), PointIndex + 1, *Tag.ToString());
				return 14;
			}
			ConfigurePoint(*Point, Tag, Pending.Plan->Category);
			Point->SetActorLabel(PointSpawnParameters.Name.ToString());
			Zone->InteractionPoints.Add(Point);
			++AddedPoints;
		}
		Zone->Capacity = Zone->InteractionPoints.Num();
		CommitActor(Zone);
	}

	World->PersistentLevel->MarkPackageDirty();
	const bool bSaved = UEditorLoadingAndSavingUtils::SaveDirtyPackages(true, true);
	if (!bSaved)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSP zone layout: failed to save dirty World Partition packages."));
		return 15;
	}

	UE_LOG(LogTemp, Display, TEXT("PCSP zone layout complete: 96 zones, 592 interaction points (%d added)."), AddedPoints);
	return AddedPoints == 382 ? 0 : 16;
}
