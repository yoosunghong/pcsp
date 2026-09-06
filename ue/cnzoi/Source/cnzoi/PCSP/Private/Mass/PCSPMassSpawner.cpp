#include "PCSPMassSpawner.h"

#include "PCSPMassFragments.h"
#include "PCSPMassNavigation.h"
#include "PCSPMassRuntime.h"
#include "NavigationSystem.h"
#include "PCSPAffordanceZone.h"
#include "PCSPTrajectoryLogComponent.h"
#include "PCSPPolicySubsystem.h"
#include "MassEntitySubsystem.h"
#include "MassEntityManager.h"
#include "MassCommonFragments.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "AnimToTextureDataAsset.h"
#include "AnimToTextureInstancePlaybackHelpers.h"

namespace
{
	static TAutoConsoleVariable<int32> CVarPCSPSelectionShell(
		TEXT("pcsp.SelectionShell"), 0,
		TEXT("Optional duplicate animated selection hull. Default 0 uses only the HUD arrow to avoid silhouette artifacts."),
		ECVF_Default);
	static TAutoConsoleVariable<int32> CVarPCSPMassCharacterRepresentation(
		TEXT("pcsp.MassCharacterRepresentation"), 1,
		TEXT("Mass visual: 1=GPU-animated category-tinted ISM (default), 0=legacy cylinder baseline."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarPCSPMassRepresentationLOD(
		TEXT("pcsp.MassRepresentationLOD"), 1,
		TEXT("Camera-distance tiering of the Mass representation refresh: 1=on, 0=every agent every update."),
		ECVF_Default);

	const FVector LegacyCylinderScale(0.22f, 0.22f, 1.65f);
	constexpr int32 CategoryComponentCount = static_cast<int32>(EPCSPAffordanceCategory::None) + 1;
	constexpr int32 RepresentationGroupCount = CategoryComponentCount * 2;

	int32 CategoryComponentIndex(const EPCSPAffordanceCategory Category, const bool bMoving)
	{
		return FMath::Clamp(static_cast<int32>(Category), 0, CategoryComponentCount - 1) * 2
			+ (bMoving ? 1 : 0);
	}

	void ConfigureRepresentationComponent(UInstancedStaticMeshComponent& Component)
	{
		// Crowd instances move and change category continuously. Ordinary ISM
		// avoids HISM's asynchronous tree rebuild / transient visibility gaps.
		Component.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
		Component.SetCollisionResponseToAllChannels(ECR_Ignore);
		Component.SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
		Component.SetGenerateOverlapEvents(false);
		Component.SetCanEverAffectNavigation(false);
		Component.SetCastShadow(false);
		Component.bCastDynamicShadow = false;
		Component.bAffectDistanceFieldLighting = false;
		Component.SetReceivesDecals(false);
	}

	TArray<FVector> BuildAffordanceSpawnAnchors(UWorld& World, const int32 Seed)
	{
		TArray<APCSPAffordanceZone*> Zones;
		for (TActorIterator<APCSPAffordanceZone> It(&World); It; ++It)
		{
			if (It->GetInteractionSlotCount() > 0) { Zones.Add(*It); }
		}
		Zones.Sort([](const APCSPAffordanceZone& A, const APCSPAffordanceZone& B)
		{
			if (A.VisualizationIndex != B.VisualizationIndex)
			{
				return A.VisualizationIndex < B.VisualizationIndex;
			}
			return A.GetPathName() < B.GetPathName();
		});

		TArray<TArray<FVector>> SlotsByZone;
		SlotsByZone.SetNum(Zones.Num());
		int32 MaxSlots = 0;
		for (int32 ZoneIndex = 0; ZoneIndex < Zones.Num(); ++ZoneIndex)
		{
			APCSPAffordanceZone* Zone = Zones[ZoneIndex];
			TArray<FVector>& Slots = SlotsByZone[ZoneIndex];
			Slots.Reserve(Zone->GetInteractionSlotCount());
			for (int32 SlotIndex = 0; SlotIndex < Zone->GetInteractionSlotCount(); ++SlotIndex)
			{
				Slots.Add(Zone->GetInteractionSlotWorldLocation(SlotIndex));
			}
			MaxSlots = FMath::Max(MaxSlots, Slots.Num());
		}

		// Round-robin by Zone before taking a second slot from any Zone. A seeded
		// rotation keeps runs reproducible without concentrating low stable indices
		// in the same city block.
		TArray<FVector> ZoneRoundRobinAnchors;
		const int32 ZoneOffset = Zones.IsEmpty() ? 0 : FMath::Abs(Seed) % Zones.Num();
		for (int32 Round = 0; Round < MaxSlots; ++Round)
		{
			for (int32 Ordinal = 0; Ordinal < Zones.Num(); ++Ordinal)
			{
				const int32 ZoneIndex = (Ordinal + ZoneOffset) % Zones.Num();
				const TArray<FVector>& Slots = SlotsByZone[ZoneIndex];
				if (Slots.IsValidIndex(Round)) { ZoneRoundRobinAnchors.Add(Slots[Round]); }
			}
		}

		return ZoneRoundRobinAnchors;
	}

	TArray<FVector> SpatiallyStratifyAnchors(const TArray<FVector>& InAnchors, const int32 Seed)
	{
		if (InAnchors.Num() < 16) { return InAnchors; }
		FBox2D Bounds(ForceInit);
		for (const FVector& Anchor : InAnchors)
		{
			Bounds += FVector2D(Anchor.X, Anchor.Y);
		}
		const FVector2D Size = Bounds.GetSize();
		if (Size.X < 1.f || Size.Y < 1.f) { return InAnchors; }

		constexpr int32 DistrictColumns = 4;
		constexpr int32 DistrictRows = 4;
		constexpr int32 DistrictCount = DistrictColumns * DistrictRows;
		TArray<TArray<FVector>> AnchorsByDistrict;
		AnchorsByDistrict.SetNum(DistrictCount);
		int32 MaxDistrictAnchors = 0;
		for (const FVector& Anchor : InAnchors)
		{
			const int32 X = FMath::Clamp(FMath::FloorToInt(
				(Anchor.X - Bounds.Min.X) / Size.X * DistrictColumns), 0, DistrictColumns - 1);
			const int32 Y = FMath::Clamp(FMath::FloorToInt(
				(Anchor.Y - Bounds.Min.Y) / Size.Y * DistrictRows), 0, DistrictRows - 1);
			TArray<FVector>& District = AnchorsByDistrict[Y * DistrictColumns + X];
			District.Add(Anchor);
			MaxDistrictAnchors = FMath::Max(MaxDistrictAnchors, District.Num());
		}

		// The first population-sized prefix now visits every spatial district
		// before taking another start from the same one. Ordering inside each
		// district retains the Zone round-robin above.
		TArray<FVector> SpatialAnchors;
		SpatialAnchors.Reserve(InAnchors.Num());
		const int32 DistrictOffset = FMath::Abs(Seed * 17) % DistrictCount;
		for (int32 Round = 0; Round < MaxDistrictAnchors; ++Round)
		{
			for (int32 Ordinal = 0; Ordinal < DistrictCount; ++Ordinal)
			{
				const int32 DistrictIndex = (Ordinal + DistrictOffset) % DistrictCount;
				const TArray<FVector>& District = AnchorsByDistrict[DistrictIndex];
				if (District.IsValidIndex(Round)) { SpatialAnchors.Add(District[Round]); }
			}
		}
		return SpatialAnchors;
	}
}

APCSPMassSpawner::APCSPMassSpawner()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
	// The Mass simulation runs in PrePhysics and owns the fragment store while it
	// executes. UpdateRepresentation deliberately refuses to read fragments during
	// that window. Running the renderer in PostPhysics gives it a stable snapshot;
	// otherwise packaged builds can repeatedly hit EntityManager::IsProcessing()
	// and leave the ISMs at their uncoloured spawn poses while the HUD keeps reading
	// live policy intents.
	PrimaryActorTick.TickGroup = TG_PostPhysics;

	Representation = CreateDefaultSubobject<UInstancedStaticMeshComponent>(
		TEXT("MassCharacterRepresentation"));
	SetRootComponent(Representation);
	ConfigureRepresentationComponent(*Representation);
	CategoryRepresentations.Add(Representation);
	for (int32 CategoryIndex = 1; CategoryIndex < RepresentationGroupCount; ++CategoryIndex)
	{
		const FName ComponentName(*FString::Printf(TEXT("MassCategory_%02d"), CategoryIndex));
		UInstancedStaticMeshComponent* CategoryComponent =
			CreateDefaultSubobject<UInstancedStaticMeshComponent>(ComponentName);
		CategoryComponent->SetupAttachment(Representation);
		ConfigureRepresentationComponent(*CategoryComponent);
		CategoryRepresentations.Add(CategoryComponent);
	}

	SelectionHighlight = CreateDefaultSubobject<UInstancedStaticMeshComponent>(
		TEXT("MassSelectionHighlight"));
	SelectionHighlight->SetupAttachment(Representation);
	ConfigureRepresentationComponent(*SelectionHighlight);
	SelectionHighlight->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> MannyMesh(
		TEXT("/Game/PCSP/Mass/SM_Manny_Mass.SM_Manny_Mass"));
	if (MannyMesh.Succeeded())
	{
		RepresentationMesh = MannyMesh.Object;
	}
	static ConstructorHelpers::FObjectFinder<UAnimToTextureDataAsset> AnimationDataAsset(
		TEXT("/AnimToTexture/Characters/Mannequin/Data/DA_BoneAnimation.DA_BoneAnimation"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> AnimatedMesh(
		TEXT("/AnimToTexture/Characters/Mannequin/SM_Mannequin_BoneAnimation.SM_Mannequin_BoneAnimation"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> AnimatedMaterial(
		TEXT("/AnimToTexture/Characters/Mannequin/Materials/BoneAnimation/MI_Body_BoneAnimation.MI_Body_BoneAnimation"));
	if (AnimationDataAsset.Succeeded() && AnimatedMesh.Succeeded() && AnimatedMaterial.Succeeded())
	{
		AnimationData = AnimationDataAsset.Object;
		RepresentationMesh = AnimatedMesh.Object;
		VertexAnimationMaterial = AnimatedMaterial.Object;
	}
	for (UInstancedStaticMeshComponent* Component : CategoryRepresentations)
	{
		Component->SetStaticMesh(RepresentationMesh);
		// ForcedLodModel is 1-based: 0 means auto-select. AnimToTexture bakes its
		// vertex lookup into one LOD only, so the animated mesh must pin LOD 0.
		Component->SetForcedLodModel(AnimationData ? 1 : 2);
		Component->NumCustomDataFloats = 4;
	}
	SelectionHighlight->SetStaticMesh(RepresentationMesh);
	SelectionHighlight->SetForcedLodModel(AnimationData ? 1 : 2);
	SelectionHighlight->NumCustomDataFloats = 4;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded()) { CylinderBaselineMesh = CylinderMesh.Object; }

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> CategoryMaterial(
		TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (CategoryMaterial.Succeeded()) { CategoryBaseMaterial = CategoryMaterial.Object; }
}

void APCSPMassSpawner::BeginPlay()
{
	Super::BeginPlay();
	// A placed Blueprint may have serialized an older tick-enabled default. The
	// runtime renderer is required for position, category tint, and animation.
	SetActorTickEnabled(true);
	bWaitingForSpawn = true;
	SpawnMassEntities();
}

void APCSPMassSpawner::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	DestroyMassEntities();
	Super::EndPlay(EndPlayReason);
}

int32 APCSPMassSpawner::SpawnMassEntities()
{
	if (!SpawnedEntities.IsEmpty()) { return SpawnedEntities.Num(); }
	UWorld* World = GetWorld();
	UMassEntitySubsystem* MassSubsystem = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
	if (!MassSubsystem || !Representation || !RepresentationMesh) { return 0; }
	UNavigationSystemV1* NavSystem = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
	FNavLocation SpawnOrigin;
	if (!NavSystem || NavSystem->IsNavigationBuildInProgress()
		|| !NavSystem->ProjectPointToNavigation(GetActorLocation(), SpawnOrigin, FVector(1000.f, 1000.f, 1000.f)))
	{
		if (!bLoggedNavigationWait)
		{
			UE_LOG(LogTemp, Warning, TEXT("PCSPMassSpawner: waiting for built NavMesh at spawner; cover the district with NavMeshBoundsVolume. Retrying automatically."));
			bLoggedNavigationWait = true;
		}
		return 0;
	}

	int32 RepresentationMode = CVarPCSPMassCharacterRepresentation.GetValueOnGameThread();
	FParse::Value(FCommandLine::Get(), TEXT("PCSP_MassCharacterRepresentation="),
		RepresentationMode);
	bUsingCharacterRepresentation = RepresentationMode != 0 || !CylinderBaselineMesh;
	bUsingVertexAnimation = bUsingCharacterRepresentation && AnimationData && VertexAnimationMaterial
		&& RepresentationMesh == AnimationData->GetStaticMesh();
	for (UInstancedStaticMeshComponent* Component : CategoryRepresentations)
	{
		if (!Component) { continue; }
		Component->SetStaticMesh(
			bUsingCharacterRepresentation ? RepresentationMesh : CylinderBaselineMesh);
		Component->SetForcedLodModel(bUsingVertexAnimation ? 1
			: bUsingCharacterRepresentation ? 2 : 0);
		Component->SetCullDistances(0, FMath::RoundToInt(
			FMath::Max(0.f, RepresentationEndCullDistance)));
	}
	if (SelectionHighlight)
	{
		SelectionHighlight->SetStaticMesh(
			bUsingCharacterRepresentation ? RepresentationMesh : CylinderBaselineMesh);
		SelectionHighlight->SetForcedLodModel(bUsingVertexAnimation ? 1
			: bUsingCharacterRepresentation ? 2 : 0);
		SelectionHighlight->ClearInstances();
	}
	SetupCategoryMaterials();

	FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
	TArray<const UScriptStruct*> Composition;
	Composition.Add(FTransformFragment::StaticStruct());
	Composition.Add(FPCSPMassPersonaFragment::StaticStruct());
	Composition.Add(FPCSPMassNeedsFragment::StaticStruct());
	Composition.Add(FPCSPMassIntentFragment::StaticStruct());
	Composition.Add(FPCSPMassMoveTargetFragment::StaticStruct());
	Composition.Add(FPCSPMassHistoryFragment::StaticStruct());
	Composition.Add(FPCSPMassAgentTag::StaticStruct());

	const FMassArchetypeHandle Archetype = EntityManager.CreateArchetype(
		Composition, FMassArchetypeCreationParams(TEXT("PCSPBackgroundAgent")));
	const int32 SpawnCount = FMath::Max(1, EntityCount);

	FRandomStream Stream(RandomSeed);
	// Needs use a separate stream so NavMesh placement retries do not change them.
	FRandomStream NeedsStream(RandomSeed ^ 0x5f3759df);
	const float NeedMin = FMath::Min(InitialNeedMin, InitialNeedMax);
	const float NeedMax = FMath::Max(InitialNeedMin, InitialNeedMax);
	for (UInstancedStaticMeshComponent* Component : CategoryRepresentations)
	{
		if (Component) { Component->ClearInstances(); }
	}
	StableIndicesByCategory.SetNum(RepresentationGroupCount);
	const float BodyScale = FMath::Max(0.1f, RepresentationScale);
	const float BodyRadius = 35.f * BodyScale;
	const int32 GridWidth = FMath::CeilToInt(FMath::Sqrt(static_cast<float>(SpawnCount)));
	// Leave a whole body-width passage between neighbors. Merely avoiding
	// initial overlap traps interior agents in a tightly packed stationary grid.
	const float Spacing = BodyRadius * 5.f;
	const FVector2D Extent(FMath::Max(SpawnExtent.X, GridWidth * Spacing * 0.5f),
		FMath::Max(SpawnExtent.Y, GridWidth * Spacing * 0.5f));
	const ANavigationData* NavData =
		NavSystem->GetDefaultNavDataInstance(FNavigationSystem::DontCreate);
	const TArray<FVector> RawDistrictAnchors = bDistributeAcrossAffordanceSlots
		? BuildAffordanceSpawnAnchors(*World, RandomSeed) : TArray<FVector>();
	TArray<FVector> ProjectedDistrictAnchors;
	if (!RawDistrictAnchors.IsEmpty() && NavData)
	{
		// Project before spatial binning. Large indoor slots can project onto a
		// different street block; binning their authored coordinates was the source
		// of the visible 4x4 imbalance in the first validation run.
		FPCSPMassNavigation AnchorSpace;
		AnchorSpace.BeginFrame(*World);
		ProjectedDistrictAnchors.Reserve(RawDistrictAnchors.Num());
		for (const FVector& RawAnchor : RawDistrictAnchors)
		{
			FNavLocation Projected;
			if (!NavSystem->ProjectPointToNavigation(RawAnchor, Projected,
				FVector(600.f, 600.f, 1000.f)))
			{
				continue;
			}
			FPathFindingQuery Reachable(this, *NavData, SpawnOrigin.Location, Projected.Location);
			Reachable.SetAllowPartialPaths(false);
			if (!NavSystem->TestPathSync(Reachable)
				|| !AnchorSpace.HasSpace(Projected.Location, BodyRadius))
			{
				continue;
			}
			ProjectedDistrictAnchors.Add(Projected.Location);
			AnchorSpace.AddAgent(ProjectedDistrictAnchors.Num() - 1,
				Projected.Location, BodyRadius);
		}

		// Some indoor authored slots project onto the same narrow street and are
		// removed by the non-overlap filter. Fill only the resulting sparse 4x4
		// districts with deterministic reachable NavMesh samples so the first 1,024
		// starts can remain balanced without reintroducing a central spawn cluster.
		if (ProjectedDistrictAnchors.Num() >= 16)
		{
			FBox2D AnchorBounds(ForceInit);
			for (const FVector& Anchor : ProjectedDistrictAnchors)
			{
				AnchorBounds += FVector2D(Anchor.X, Anchor.Y);
			}
			const FVector2D AnchorSize = AnchorBounds.GetSize();
			TArray<int32> DistrictCounts;
			DistrictCounts.Init(0, 16);
			auto DistrictOf = [&AnchorBounds, &AnchorSize](const FVector& Position)
			{
				const int32 X = FMath::Clamp(FMath::FloorToInt(
					(Position.X - AnchorBounds.Min.X) / FMath::Max(1.f, AnchorSize.X) * 4.f), 0, 3);
				const int32 Y = FMath::Clamp(FMath::FloorToInt(
					(Position.Y - AnchorBounds.Min.Y) / FMath::Max(1.f, AnchorSize.Y) * 4.f), 0, 3);
				return Y * 4 + X;
			};
			for (const FVector& Anchor : ProjectedDistrictAnchors)
			{
				++DistrictCounts[DistrictOf(Anchor)];
			}
			const int32 MinimumPerDistrict = FMath::DivideAndRoundUp(SpawnCount, 16);
			FRandomStream FillStream(RandomSeed ^ 0x6a09e667);
			for (int32 DistrictIndex = 0; DistrictIndex < 16; ++DistrictIndex)
			{
				const int32 DistrictX = DistrictIndex % 4;
				const int32 DistrictY = DistrictIndex / 4;
				const FVector2D CellMin = AnchorBounds.Min + FVector2D(
					AnchorSize.X * DistrictX / 4.f, AnchorSize.Y * DistrictY / 4.f);
				const FVector2D CellMax = AnchorBounds.Min + FVector2D(
					AnchorSize.X * (DistrictX + 1) / 4.f, AnchorSize.Y * (DistrictY + 1) / 4.f);
				for (int32 Attempt = 0;
					DistrictCounts[DistrictIndex] < MinimumPerDistrict && Attempt < 8192;
					++Attempt)
				{
					const FVector Candidate(FillStream.FRandRange(CellMin.X, CellMax.X),
						FillStream.FRandRange(CellMin.Y, CellMax.Y), SpawnOrigin.Location.Z);
					FNavLocation Projected;
					if (!NavSystem->ProjectPointToNavigation(Candidate, Projected,
						FVector(300.f, 300.f, 1000.f))
						|| DistrictOf(Projected.Location) != DistrictIndex
						|| !AnchorSpace.HasSpace(Projected.Location, BodyRadius))
					{
						continue;
					}
					FPathFindingQuery Reachable(this, *NavData,
						SpawnOrigin.Location, Projected.Location);
					Reachable.SetAllowPartialPaths(false);
					if (!NavSystem->TestPathSync(Reachable)) { continue; }
					ProjectedDistrictAnchors.Add(Projected.Location);
					AnchorSpace.AddAgent(ProjectedDistrictAnchors.Num() - 1,
						Projected.Location, BodyRadius);
					++DistrictCounts[DistrictIndex];
				}
			}
		}
	}
	const TArray<FVector> DistrictAnchors =
		SpatiallyStratifyAnchors(ProjectedDistrictAnchors, RandomSeed);
	const bool bUsingDistrictAnchors = DistrictAnchors.Num() >= SpawnCount;
	if (bDistributeAcrossAffordanceSlots && !bUsingDistrictAnchors)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("PCSPMassSpawner: district distribution requested but only %d anchors are loaded for %d agents; using expanded local stratification."),
			DistrictAnchors.Num(), SpawnCount);
	}
	FPCSPMassNavigation SpawnPositions;
	SpawnPositions.BeginFrame(*World);
	TArray<FVector> Locations;
	Locations.Reserve(SpawnCount);
	for (int32 Index = 0; Index < SpawnCount; ++Index)
	{
		bool bPlaced = false;
		// Stratified starts keep enlarged bodies apart before avoidance begins.
		FVector Location = bUsingDistrictAnchors ? DistrictAnchors[Index]
			: GetActorLocation() + FVector(
				((Index % GridWidth + 0.5f) / GridWidth * 2.f - 1.f) * Extent.X,
				((Index / GridWidth + 0.5f) / GridWidth * 2.f - 1.f) * Extent.Y, 0.f);
		if (NavSystem && SpawnPositions.IsReady())
		{
			for (int32 Attempt = 0; Attempt < 128; ++Attempt)
			{
				const float Expansion = 1.f + Attempt / 32;
				const FVector Candidate = Attempt == 0 ? Location
					: bUsingDistrictAnchors
						? DistrictAnchors[Stream.RandRange(0, DistrictAnchors.Num() - 1)]
						: GetActorLocation() + FVector(
							Stream.FRandRange(-Extent.X, Extent.X) * Expansion,
							Stream.FRandRange(-Extent.Y, Extent.Y) * Expansion, 0.f);
				FNavLocation Projected;
				if (NavSystem->ProjectPointToNavigation(Candidate, Projected, FVector(600.f, 600.f, 1000.f))
					&& SpawnPositions.HasSpace(Projected.Location, BodyRadius))
				{
					FPathFindingQuery Reachable(this, *NavData, SpawnOrigin.Location, Projected.Location);
					Reachable.SetAllowPartialPaths(false);
					if (!NavSystem->TestPathSync(Reachable)) { continue; }
					Location = Projected.Location;
					bPlaced = true;
					break;
				}
			}
		}
		if (!bPlaced)
		{
			UE_LOG(LogTemp, Warning, TEXT("PCSPMassSpawner: insufficient NavMesh space for %d enlarged agents (%d valid starts); retrying."), SpawnCount, Locations.Num());
			return 0;
		}
		// HasSpace sums this radius with the stored neighbour radius, so passing
		// BodyRadius already enforces one full body diameter (210 cm at 3x).
		SpawnPositions.AddAgent(Index, Location, BodyRadius);
		Locations.Add(Location);
	}
	EntityManager.BatchCreateEntities(Archetype, SpawnCount, SpawnedEntities);
	for (int32 Index = 0; Index < SpawnedEntities.Num(); ++Index)
	{
		const FVector Location = Locations[Index];
		FTransformFragment& Transform =
			EntityManager.GetFragmentDataChecked<FTransformFragment>(SpawnedEntities[Index]);
		Transform.GetMutableTransform().SetTranslation(Location);

		FPCSPMassPersonaFragment& Persona =
			EntityManager.GetFragmentDataChecked<FPCSPMassPersonaFragment>(SpawnedEntities[Index]);
		Persona.PersonaId = (Index % 300) + 1;
		Persona.StableIndex = Index;
		Persona.Cohort = static_cast<uint16>(Index % 32);

		FPCSPMassNeedsFragment& Needs =
			EntityManager.GetFragmentDataChecked<FPCSPMassNeedsFragment>(SpawnedEntities[Index]);
		for (float& NeedValue : Needs.Values)
		{
			NeedValue = FMath::Clamp(NeedsStream.FRandRange(NeedMin, NeedMax), 0.f, 1.f);
		}

		FPCSPMassIntentFragment& Intent =
			EntityManager.GetFragmentDataChecked<FPCSPMassIntentFragment>(SpawnedEntities[Index]);
		// Admission already rotates across the population; a second startup delay
		// made cohorts miss their first window and remain idle for another sweep.
		Intent.NextDecisionTime = World->GetTimeSeconds();

		FPCSPMassMoveTargetFragment& MoveTarget =
			EntityManager.GetFragmentDataChecked<FPCSPMassMoveTargetFragment>(SpawnedEntities[Index]);
		MoveTarget.Speed = PCSPMassRuntime::ScaledSpeed(260.f, BodyRadius);
		MoveTarget.AgentRadius = BodyRadius;

		const int32 CategoryIndex = CategoryComponentIndex(Intent.Category, false);
		const int32 InstanceIndex = CategoryRepresentations[CategoryIndex]->AddInstance(
			MakeRepresentationTransform(Transform.GetTransform(), Index, false,
				World->GetTimeSeconds()), true);
		if (bUsingVertexAnimation)
		{
			FAnimToTextureAutoPlayData Playback;
			UAnimToTextureInstancePlaybackLibrary::GetAutoPlayDataFromDataAsset(
				AnimationData, IdleAnimationIndex, Playback, Index * 0.037f, 1.f);
			UAnimToTextureInstancePlaybackLibrary::UpdateInstanceAutoPlayData(
				CategoryRepresentations[CategoryIndex], InstanceIndex, Playback, true);
		}
		StableIndicesByCategory[CategoryIndex].Add(Index);
	}

	const FString ConfigPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("mass_run_config.json");
	const TCHAR* RepresentationName = bUsingVertexAnimation ? TEXT("anim_to_texture_category_ism")
		: bUsingCharacterRepresentation ? TEXT("manny_category_ism_procedural_fallback")
		: TEXT("legacy_cylinder_ism");
	const FString RepresentationPath = bUsingCharacterRepresentation
		? RepresentationMesh->GetPathName() : TEXT("/Engine/BasicShapes/Cylinder");
	const IConsoleVariable* AgentCollisionCVar =
		IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.MassAgentCollision"));
	const bool bAgentCollision = AgentCollisionCVar && AgentCollisionCVar->GetInt() != 0;
	FBox2D SpawnBounds(ForceInit);
	for (const FVector& Location : Locations)
	{
		SpawnBounds += FVector2D(Location.X, Location.Y);
	}
	TArray<int32> SpawnDistrictCounts;
	SpawnDistrictCounts.Init(0, 16);
	const FVector2D SpawnSize = SpawnBounds.GetSize();
	if (SpawnSize.X > 0.f && SpawnSize.Y > 0.f)
	{
		for (const FVector& Location : Locations)
		{
			const int32 X = FMath::Clamp(FMath::FloorToInt(
				(Location.X - SpawnBounds.Min.X) / SpawnSize.X * 4.f), 0, 3);
			const int32 Y = FMath::Clamp(FMath::FloorToInt(
				(Location.Y - SpawnBounds.Min.Y) / SpawnSize.Y * 4.f), 0, 3);
			++SpawnDistrictCounts[Y * 4 + X];
		}
	}
	TArray<FString> SpawnDistrictCountStrings;
	for (const int32 Count : SpawnDistrictCounts)
	{
		SpawnDistrictCountStrings.Add(FString::FromInt(Count));
	}
	const FString SpawnDistrictCountsJson = FString::Printf(TEXT("[%s]"),
		*FString::Join(SpawnDistrictCountStrings, TEXT(",")));
	// The Actor tier stamps policy_mode into its session_start row, but the
	// portfolio map runs all-Mass, so without these fields every trajectory file
	// in Saved/PCSP/Logs is unlabelled and no analysis can tell an ablation run
	// from a full one. The mode is captured at spawn; `P` can cycle it afterwards.
	const FString Config = FString::Printf(
		TEXT("{\"mass_entities\":%d,\"seed\":%d,\"movement\":\"%s\",")
		TEXT("\"representation_scale\":%.3f,\"agent_radius\":%.1f,")
		TEXT("\"spawn_distribution\":\"%s\",\"spawn_anchor_count\":%d,")
		TEXT("\"spawn_bounds_xy\":[%.1f,%.1f,%.1f,%.1f],")
		TEXT("\"spawn_district_counts_4x4\":%s,")
		TEXT("\"agent_collision\":\"%s\",\"selection_collision\":\"visibility_query_only\",")
		TEXT("\"cohorts\":32,\"representation\":\"%s\",")
		TEXT("\"representation_mesh\":\"%s\",")
		TEXT("\"policy_mode_at_spawn\":\"%s\",\"active_ablation\":\"%s\",")
		TEXT("\"action_selection\":\"%s\",")
		TEXT("\"initial_need_range\":[%.3f,%.3f],")
		TEXT("\"trajectory_schema\":\"pcsp_ue_behavior_v1\"}\n"),
		SpawnedEntities.Num(), RandomSeed,
		bAgentCollision ? TEXT("recast_paths_local_separation") : TEXT("recast_paths_no_agent_collision"),
		BodyScale, BodyRadius,
		bUsingDistrictAnchors ? TEXT("affordance_slots_spatial_4x4") : TEXT("local_navmesh_stratified"),
		DistrictAnchors.Num(),
		SpawnBounds.Min.X, SpawnBounds.Min.Y, SpawnBounds.Max.X, SpawnBounds.Max.Y,
		*SpawnDistrictCountsJson,
		bAgentCollision ? TEXT("on") : TEXT("off"),
		RepresentationName, *RepresentationPath,
		*UPCSPPolicySubsystem::PolicyModeName(UPCSPPolicySubsystem::GetPolicyMode()),
		*UPCSPPolicySubsystem::GetActiveAblationTag(),
		*UPCSPPolicySubsystem::ActionSelectionName(),
		NeedMin, NeedMax);
	FFileHelper::SaveStringToFile(Config, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_None);

	UE_LOG(LogTemp, Log, TEXT("PCSPMassSpawner: spawned %d background entities (%s)"),
		SpawnedEntities.Num(), RepresentationName);
	bWaitingForSpawn = false;
	return SpawnedEntities.Num();
}

void APCSPMassSpawner::DestroyMassEntities()
{
	bWaitingForSpawn = false;
	UWorld* World = GetWorld();
	UMassEntitySubsystem* MassSubsystem = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
	if (MassSubsystem && !SpawnedEntities.IsEmpty())
	{
		FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
		if (!EntityManager.IsProcessing())
		{
			EntityManager.BatchDestroyEntities(SpawnedEntities);
		}
	}
	SpawnedEntities.Reset();
	for (UInstancedStaticMeshComponent* Component : CategoryRepresentations)
	{
		if (Component) { Component->ClearInstances(); }
	}
	StableIndicesByCategory.Reset();
	RepresentationSamples.Reset();
	AutoPlayKeysByCategory.Reset();
	HighlightedStableIndex = INDEX_NONE;
	if (SelectionHighlight) { SelectionHighlight->ClearInstances(); }
}

bool APCSPMassSpawner::GetAgentSnapshot(const int32 StableIndex,
	FPCSPMassAgentSnapshot& OutSnapshot) const
{
	if (!SpawnedEntities.IsValidIndex(StableIndex)) { return false; }
	UWorld* World = GetWorld();
	UMassEntitySubsystem* MassSubsystem = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
	if (!MassSubsystem) { return false; }
	FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
	if (EntityManager.IsProcessing()) { return false; }
	const FMassEntityHandle Entity = SpawnedEntities[StableIndex];
	if (!EntityManager.IsEntityValid(Entity)) { return false; }

	const FPCSPMassPersonaFragment& Persona =
		EntityManager.GetFragmentDataChecked<FPCSPMassPersonaFragment>(Entity);
	const FPCSPMassNeedsFragment& Needs =
		EntityManager.GetFragmentDataChecked<FPCSPMassNeedsFragment>(Entity);
	const FPCSPMassIntentFragment& Intent =
		EntityManager.GetFragmentDataChecked<FPCSPMassIntentFragment>(Entity);
	const FPCSPMassMoveTargetFragment& MoveTarget =
		EntityManager.GetFragmentDataChecked<FPCSPMassMoveTargetFragment>(Entity);
	const FPCSPMassHistoryFragment& History =
		EntityManager.GetFragmentDataChecked<FPCSPMassHistoryFragment>(Entity);
	const FTransform& Transform =
		EntityManager.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform();

	OutSnapshot = FPCSPMassAgentSnapshot();
	OutSnapshot.StableIndex = Persona.StableIndex;
	OutSnapshot.PersonaId = Persona.PersonaId;
	FMemory::Memcpy(OutSnapshot.Needs, Needs.Values, sizeof(Needs.Values));
	OutSnapshot.Action = Intent.Action;
	OutSnapshot.Category = Intent.Category;
	OutSnapshot.Location = Transform.GetLocation();
	OutSnapshot.Rotation = Transform.Rotator();
	OutSnapshot.Target = MoveTarget.Target;
	OutSnapshot.ZoneVisualizationIndex = MoveTarget.GoalZoneVisualizationIndex;
	OutSnapshot.ReservedSlotIndex = MoveTarget.ReservedSlotIndex;
	OutSnapshot.bMoving = MoveTarget.bMoving;
	OutSnapshot.bWandering = MoveTarget.bWandering;
	OutSnapshot.bInteracting = Intent.InteractionEndTime > 0.f
		&& World->GetTimeSeconds() < Intent.InteractionEndTime;
	for (int32 Offset = 0; Offset < History.Count; ++Offset)
	{
		const int32 Index = (History.WriteIndex + FPCSPMassHistoryFragment::Capacity
			- History.Count + Offset) % FPCSPMassHistoryFragment::Capacity;
		OutSnapshot.RecentActions.Add(History.Actions[Index]);
		OutSnapshot.RecentActionTimes.Add(History.Times[Index]);
	}
	return true;
}

void APCSPMassSpawner::GetAllAgentSnapshots(TArray<FPCSPMassAgentSnapshot>& OutSnapshots) const
{
	OutSnapshots.Reset();
	OutSnapshots.Reserve(SpawnedEntities.Num());
	for (int32 StableIndex = 0; StableIndex < SpawnedEntities.Num(); ++StableIndex)
	{
		FPCSPMassAgentSnapshot Snapshot;
		if (GetAgentSnapshot(StableIndex, Snapshot))
		{
			OutSnapshots.Add(MoveTemp(Snapshot));
		}
	}
}

bool APCSPMassSpawner::GetNeighborhoodSummary(const int32 StableIndex, const float Radius,
	int32& OutNearby, int32& OutSameActivity) const
{
	OutNearby = 0;
	OutSameActivity = 0;
	if (!RepresentationSamples.IsValidIndex(StableIndex)) { return false; }
	const FRepresentationSample& Self = RepresentationSamples[StableIndex];
	if (!Self.bValid) { return false; }

	// The representation pass already caches every agent's pose and category, so one
	// linear sweep is enough at HUD refresh rates: no Mass fragment reads and no
	// spatial structure to keep in sync with a crowd that moves every frame.
	const FVector Origin = Self.EntityTransform.GetLocation();
	const float RadiusSq = FMath::Square(FMath::Max(0.f, Radius));
	const int32 SelfCategory = Self.CategoryIndex / 2;
	for (int32 Index = 0; Index < RepresentationSamples.Num(); ++Index)
	{
		if (Index == StableIndex) { continue; }
		const FRepresentationSample& Other = RepresentationSamples[Index];
		if (!Other.bValid) { continue; }
		if (FVector::DistSquared(Origin, Other.EntityTransform.GetLocation()) > RadiusSq) { continue; }
		++OutNearby;
		if (Other.CategoryIndex / 2 == SelfCategory) { ++OutSameActivity; }
	}
	return true;
}

bool APCSPMassSpawner::FindNearestAgent(const FVector& Origin, int32& OutStableIndex,
	float& OutDistanceSq) const
{
	OutStableIndex = INDEX_NONE;
	OutDistanceSq = TNumericLimits<float>::Max();
	for (int32 StableIndex = 0; StableIndex < SpawnedEntities.Num(); ++StableIndex)
	{
		FPCSPMassAgentSnapshot Snapshot;
		if (!GetAgentSnapshot(StableIndex, Snapshot)) { continue; }
		const float DistanceSq = FVector::DistSquared(Origin, Snapshot.Location);
		if (DistanceSq < OutDistanceSq)
		{
			OutDistanceSq = DistanceSq;
			OutStableIndex = StableIndex;
		}
	}
	return OutStableIndex != INDEX_NONE;
}

bool APCSPMassSpawner::GetStableIndexFromHit(const UPrimitiveComponent* Component,
	const int32 InstanceIndex, int32& OutStableIndex) const
{
	OutStableIndex = INDEX_NONE;
	const int32 CategoryIndex = CategoryRepresentations.IndexOfByKey(
		Cast<UInstancedStaticMeshComponent>(Component));
	if (!StableIndicesByCategory.IsValidIndex(CategoryIndex)
		|| !StableIndicesByCategory[CategoryIndex].IsValidIndex(InstanceIndex))
	{
		return false;
	}
	OutStableIndex = StableIndicesByCategory[CategoryIndex][InstanceIndex];
	return true;
}

void APCSPMassSpawner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bWaitingForSpawn && SpawnedEntities.IsEmpty())
	{
		TimeUntilSpawnRetry -= DeltaSeconds;
		if (TimeUntilSpawnRetry <= 0.f)
		{
			SpawnMassEntities();
			TimeUntilSpawnRetry = 0.5f;
		}
		return;
	}
	TimeUntilRepresentationUpdate -= DeltaSeconds;
	if (TimeUntilRepresentationUpdate <= 0.f)
	{
		UpdateRepresentation();
		TimeUntilRepresentationUpdate = FMath::Max(0.f, RepresentationUpdateInterval);
	}
}

void APCSPMassSpawner::UpdateRepresentation()
{
	if (CategoryRepresentations.IsEmpty() || SpawnedEntities.IsEmpty()) { return; }
	UWorld* World = GetWorld();
	UMassEntitySubsystem* MassSubsystem = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
	if (!MassSubsystem) { return; }

	FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
	if (EntityManager.IsProcessing()) { return; }

	const float WorldTime = World->GetTimeSeconds();
	const bool bDistanceLOD = CVarPCSPMassRepresentationLOD.GetValueOnGameThread() != 0;
	FVector ViewLocation = GetActorLocation();
	if (APlayerController* Controller = World->GetFirstPlayerController())
	{
		FRotator ViewRotation;
		Controller->GetPlayerViewPoint(ViewLocation, ViewRotation);
	}
	const float NearDistanceSq = FMath::Square(FMath::Max(0.f, RepresentationNearDistance));
	const float FarDistanceSq = FMath::Square(
		FMath::Max(RepresentationNearDistance, RepresentationFarDistance));

	TArray<TArray<FTransform>> TransformsByCategory;
	TransformsByCategory.SetNum(RepresentationGroupCount);
	TArray<TArray<float>> PlaybackRatesByCategory;
	PlaybackRatesByCategory.SetNum(RepresentationGroupCount);
	StableIndicesByCategory.SetNum(RepresentationGroupCount);
	for (TArray<int32>& StableIndices : StableIndicesByCategory) { StableIndices.Reset(); }
	RepresentationSamples.SetNum(SpawnedEntities.Num());

	for (int32 StableIndex = 0; StableIndex < SpawnedEntities.Num(); ++StableIndex)
	{
		const FMassEntityHandle Entity = SpawnedEntities[StableIndex];
		if (!EntityManager.IsEntityValid(Entity)) { continue; }
		FRepresentationSample& Sample = RepresentationSamples[StableIndex];

		// Agents far from the camera reuse their last sampled pose, which skips
		// three fragment lookups each. That saving is what pays for keeping every
		// instance GPU-animated instead of dropping distant NPCs to a static pose.
		if (!Sample.bValid || !bDistanceLOD || StableIndex == HighlightedStableIndex
			|| WorldTime >= Sample.NextSampleTime)
		{
			const FTransformFragment& Transform =
				EntityManager.GetFragmentDataChecked<FTransformFragment>(Entity);
			const FPCSPMassIntentFragment& Intent =
				EntityManager.GetFragmentDataChecked<FPCSPMassIntentFragment>(Entity);
			const FPCSPMassMoveTargetFragment& MoveTarget =
				EntityManager.GetFragmentDataChecked<FPCSPMassMoveTargetFragment>(Entity);
			Sample.EntityTransform = Transform.GetTransform();
			Sample.CategoryIndex = CategoryComponentIndex(Intent.Category, MoveTarget.bMoving);
			Sample.WalkPlayRate = PCSPMassRuntime::WalkAnimationPlayRate(
				MoveTarget.Speed, MoveTarget.AgentRadius);
			Sample.bValid = true;

			// Near agents resample every pass so their motion stays frame-smooth;
			// only distance buys back the budget. Sampling at a fixed 10 Hz for
			// everyone is what made the crowd look choppy up close.
			const float DistanceSq =
				FVector::DistSquared(ViewLocation, Sample.EntityTransform.GetLocation());
			const float TierInterval = DistanceSq <= NearDistanceSq ? 0.f
				: DistanceSq <= FarDistanceSq ? FMath::Max(0.f, RepresentationMidInterval)
				: FMath::Max(0.f, RepresentationFarInterval);
			Sample.NextSampleTime = WorldTime + TierInterval;
		}

		// Without the outline material the shell is a second lit copy of the body in
		// the same pose. Drawing only one of the two is what keeps the selection
		// readable instead of a z-fighting mix of both materials.
		if (CVarPCSPSelectionShell.GetValueOnGameThread() != 0
			&& !bUsingOutlineShell && StableIndex == HighlightedStableIndex) { continue; }

		TransformsByCategory[Sample.CategoryIndex].Add(MakeRepresentationTransform(
			Sample.EntityTransform, StableIndex, Sample.CategoryIndex % 2 != 0, WorldTime));
		PlaybackRatesByCategory[Sample.CategoryIndex].Add(Sample.WalkPlayRate);
		StableIndicesByCategory[Sample.CategoryIndex].Add(StableIndex);
	}

	AutoPlayKeysByCategory.SetNum(RepresentationGroupCount);
	AutoPlayRatesByCategory.SetNum(RepresentationGroupCount);
	for (int32 CategoryIndex = 0; CategoryIndex < CategoryRepresentations.Num(); ++CategoryIndex)
	{
		UInstancedStaticMeshComponent* Component = CategoryRepresentations[CategoryIndex];
		if (!Component) { continue; }
		const TArray<FTransform>& Transforms = TransformsByCategory[CategoryIndex];
		const TArray<int32>& StableIndices = StableIndicesByCategory[CategoryIndex];
		const TArray<float>& PlaybackRates = PlaybackRatesByCategory[CategoryIndex];
		TArray<int32>& AutoPlayKeys = AutoPlayKeysByCategory[CategoryIndex];
		TArray<float>& AutoPlayRates = AutoPlayRatesByCategory[CategoryIndex];

		bool bCustomDataLost = false;
		if (Component->GetInstanceCount() == Transforms.Num())
		{
			if (!Transforms.IsEmpty())
			{
				Component->BatchUpdateInstancesTransforms(0, Transforms, true, true, true);
			}
		}
		else
		{
			// ClearInstances drops per-instance custom data, so every surviving
			// slot has to be re-authored on this pass.
			Component->ClearInstances();
			Component->AddInstances(Transforms, false, true, false);
			bCustomDataLost = true;
		}

		if (!bUsingVertexAnimation)
		{
			AutoPlayKeys.Reset();
			AutoPlayRates.Reset();
			continue;
		}
		if (bCustomDataLost)
		{
			AutoPlayKeys.Reset();
			AutoPlayRates.Reset();
		}
		const int32 KnownKeyCount = AutoPlayKeys.Num();
		AutoPlayKeys.SetNum(Transforms.Num());
		AutoPlayRates.SetNum(Transforms.Num());
		for (int32 Index = KnownKeyCount; Index < AutoPlayKeys.Num(); ++Index)
		{
			AutoPlayKeys[Index] = INDEX_NONE;
			AutoPlayRates[Index] = -1.f;
		}

		// Autoplay data is constant for a given (instance slot, occupant) pair, so
		// rewrite it only where an agent actually entered or left the slot. Rewriting
		// all of them every update was the bulk of the representation cost.
		int32 LastChangedIndex = INDEX_NONE;
		for (int32 InstanceIndex = 0; InstanceIndex < Transforms.Num(); ++InstanceIndex)
		{
			const float DesiredPlayRate = CategoryIndex % 2 != 0
				? PlaybackRates[InstanceIndex] : 1.f;
			if (AutoPlayKeys[InstanceIndex] != StableIndices[InstanceIndex]
				|| !FMath::IsNearlyEqual(AutoPlayRates[InstanceIndex],
					DesiredPlayRate, 0.01f))
			{
				LastChangedIndex = InstanceIndex;
			}
		}
		if (LastChangedIndex == INDEX_NONE) { continue; }

		const bool bWalking = CategoryIndex % 2 != 0;
		const int32 AnimationIndex = bWalking ? WalkAnimationIndex : IdleAnimationIndex;
		for (int32 InstanceIndex = 0; InstanceIndex <= LastChangedIndex; ++InstanceIndex)
		{
			const int32 StableIndex = StableIndices[InstanceIndex];
			const float PlayRate = bWalking ? PlaybackRates[InstanceIndex] : 1.f;
			if (AutoPlayKeys[InstanceIndex] == StableIndex
				&& FMath::IsNearlyEqual(AutoPlayRates[InstanceIndex], PlayRate, 0.01f))
			{
				continue;
			}
			FAnimToTextureAutoPlayData Playback;
			UAnimToTextureInstancePlaybackLibrary::GetAutoPlayDataFromDataAsset(
				AnimationData, AnimationIndex, Playback, StableIndex * 0.037f,
				PlayRate);
			UAnimToTextureInstancePlaybackLibrary::UpdateInstanceAutoPlayData(
				Component, InstanceIndex, Playback, InstanceIndex == LastChangedIndex);
			AutoPlayKeys[InstanceIndex] = StableIndex;
			AutoPlayRates[InstanceIndex] = PlayRate;
		}
	}

	UpdateSelectionHighlight(WorldTime);

	if (!bLoggedCategoryVisualization && WorldTime >= 6.f)
	{
		int32 VisibleAgents = 0;
		int32 ActiveGroups = 0;
		for (UInstancedStaticMeshComponent* Component : CategoryRepresentations)
		{
			const int32 InstanceCount = Component ? Component->GetInstanceCount() : 0;
			VisibleAgents += InstanceCount;
			ActiveGroups += InstanceCount > 0 ? 1 : 0;
		}
		UE_LOG(LogTemp, Display,
			TEXT("PCSPMassSpawner: category-tinted bodies=%d active_groups=%d head_indicators=0 gpu_animation=%s"),
			VisibleAgents, ActiveGroups, bUsingVertexAnimation ? TEXT("true") : TEXT("false"));
		bLoggedCategoryVisualization = true;
	}
}

void APCSPMassSpawner::SetupCategoryMaterials()
{
	CategoryMaterials.Reset();
	CategoryMaterials.SetNum(CategoryRepresentations.Num());
	UMaterialInterface* BaseMaterial = bUsingVertexAnimation ? VertexAnimationMaterial : CategoryBaseMaterial;
	if (!BaseMaterial) { return; }
	// Resolved here rather than by a constructor finder: the asset is generated by
	// -run=PCSPSelectionOutlineMaterial, so on a clone that has not run it yet a hard
	// CDO reference would log a load error on every editor start.
	if (!SelectionOutlineMaterial)
	{
		SelectionOutlineMaterial = LoadObject<UMaterialInterface>(nullptr,
			TEXT("/Game/PCSP/Materials/MI_PCSPSelectionOutline.MI_PCSPSelectionOutline"),
			nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
	// The outline hull is a copy of the body material forced to unlit + masked and
	// clipped to back faces, so it inherits the same vertex animation and is only
	// correct on the GPU-animated mesh it was derived from.
	bUsingOutlineShell = SelectionOutlineMaterial != nullptr && bUsingVertexAnimation;
	if (SelectionOutlineMaterial && !bUsingOutlineShell)
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPMassSpawner: selection outline material ignored - this "
			"crowd is not running the AnimToTexture representation it was derived from."));
	}
	else if (!bUsingOutlineShell)
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPMassSpawner: no outline material at "
			"/Game/PCSP/Materials/MI_PCSPSelectionOutline. Author it with "
			"-run=PCSPSelectionOutlineMaterial; until then the selected agent is drawn "
			"as a solid tinted body."));
	}
	if (SelectionHighlight)
	{
		SelectionHighlightMaterial = UMaterialInstanceDynamic::Create(
			bUsingOutlineShell ? SelectionOutlineMaterial.Get() : BaseMaterial, this);
		if (SelectionHighlightMaterial)
		{
			const float Intensity = FMath::Max(1.f, SelectionHighlightIntensity);
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("OutlineColor"), SelectionHighlightColor);
			SelectionHighlightMaterial->SetScalarParameterValue(TEXT("OutlineIntensity"), Intensity);
			SelectionHighlightMaterial->SetScalarParameterValue(TEXT("OutlineThickness"),
				FMath::Max(0.1f, SelectionOutlineThickness));
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("BodyColor"), SelectionHighlightColor);
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("LogoColor"), SelectionHighlightColor);
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("Color"), SelectionHighlightColor);
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("BaseColor"), SelectionHighlightColor);
			SelectionHighlightMaterial->SetVectorParameterValue(TEXT("EmissiveColor"),
				SelectionHighlightColor * Intensity);
			if (bUsingVertexAnimation && AnimationData)
			{
				SelectionHighlightMaterial->SetScalarParameterValue(
					TEXT("SampleRate"), AnimationData->SampleRate);
			}
			const int32 MaterialCount = FMath::Max(1, SelectionHighlight->GetNumMaterials());
			for (int32 MaterialIndex = 0; MaterialIndex < MaterialCount; ++MaterialIndex)
			{
				SelectionHighlight->SetMaterial(MaterialIndex, SelectionHighlightMaterial);
			}
		}
	}
	for (int32 CategoryIndex = 0; CategoryIndex < CategoryRepresentations.Num(); ++CategoryIndex)
	{
		UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(
			BaseMaterial, this);
		CategoryMaterials[CategoryIndex] = Material;
		if (!Material || !CategoryRepresentations[CategoryIndex]) { continue; }
		const FLinearColor Color = PCSPVisualization::CategoryColor(
			static_cast<EPCSPAffordanceCategory>(CategoryIndex / 2));
		Material->SetVectorParameterValue(TEXT("BodyColor"), Color);
		Material->SetVectorParameterValue(TEXT("Color"), Color);
		Material->SetVectorParameterValue(TEXT("BaseColor"), Color);
		Material->SetVectorParameterValue(TEXT("EmissiveColor"), Color * 0.15f);
		if (bUsingVertexAnimation)
		{
			FAnimToTextureAutoPlayData Playback;
			const bool bWalking = CategoryIndex % 2 != 0;
			UAnimToTextureInstancePlaybackLibrary::GetAutoPlayDataFromDataAsset(
				AnimationData, bWalking ? WalkAnimationIndex : IdleAnimationIndex,
				Playback, CategoryIndex * 0.13f, bWalking ? 1.2f : 1.f);
			Material->SetScalarParameterValue(TEXT("StartFrame"), Playback.StartFrame);
			Material->SetScalarParameterValue(TEXT("EndFrame"), Playback.EndFrame);
			Material->SetScalarParameterValue(TEXT("TimeOffset"), Playback.TimeOffset);
			Material->SetScalarParameterValue(TEXT("Playrate"), Playback.PlayRate);
			Material->SetScalarParameterValue(TEXT("SampleRate"), AnimationData->SampleRate);
		}
		const int32 MaterialCount = FMath::Max(1,
			CategoryRepresentations[CategoryIndex]->GetNumMaterials());
		for (int32 MaterialIndex = 0; MaterialIndex < MaterialCount; ++MaterialIndex)
		{
			CategoryRepresentations[CategoryIndex]->SetMaterial(MaterialIndex, Material);
		}
	}
}

void APCSPMassSpawner::SetHighlightedAgent(const int32 StableIndex)
{
	const int32 PreviousIndex = HighlightedStableIndex;
	HighlightedStableIndex = SpawnedEntities.IsValidIndex(StableIndex) ? StableIndex : INDEX_NONE;
	if (HighlightedStableIndex == INDEX_NONE && SelectionHighlight)
	{
		SelectionHighlight->ClearInstances();
	}
	// In fallback mode the highlighted agent is removed from its category group, so
	// the swap has to happen on the click rather than on the next throttled pass.
	if (PreviousIndex != HighlightedStableIndex && !bUsingOutlineShell)
	{
		UpdateRepresentation();
	}
}

void APCSPMassSpawner::UpdateSelectionHighlight(const float WorldTime)
{
	if (!SelectionHighlight) { return; }
	// The shell is a second copy of the same mesh sharing the agent's autoplay data,
	// so the two hold one pose. The outline material widens it along the vertex
	// normal and draws back faces only, leaving a bright rim at the silhouette;
	// without that material it stands in for the body instead.
	const bool bVisible = CVarPCSPSelectionShell.GetValueOnGameThread() != 0
		&& RepresentationSamples.IsValidIndex(HighlightedStableIndex)
		&& RepresentationSamples[HighlightedStableIndex].bValid;
	if (!bVisible)
	{
		if (SelectionHighlight->GetInstanceCount() > 0) { SelectionHighlight->ClearInstances(); }
		return;
	}

	const FRepresentationSample& Sample = RepresentationSamples[HighlightedStableIndex];
	FTransform Shell = MakeRepresentationTransform(Sample.EntityTransform,
		HighlightedStableIndex, Sample.CategoryIndex % 2 != 0, WorldTime);
	if (SelectionHighlight->GetInstanceCount() != 1)
	{
		SelectionHighlight->ClearInstances();
		SelectionHighlight->AddInstance(Shell, true);
	}
	else
	{
		SelectionHighlight->UpdateInstanceTransform(0, Shell, true, true, true);
	}

	if (bUsingVertexAnimation)
	{
		FAnimToTextureAutoPlayData Playback;
		const bool bWalking = Sample.CategoryIndex % 2 != 0;
		UAnimToTextureInstancePlaybackLibrary::GetAutoPlayDataFromDataAsset(
			AnimationData, bWalking ? WalkAnimationIndex : IdleAnimationIndex, Playback,
			HighlightedStableIndex * 0.037f,
			bWalking ? Sample.WalkPlayRate : 1.f);
		UAnimToTextureInstancePlaybackLibrary::UpdateInstanceAutoPlayData(
			SelectionHighlight, 0, Playback, true);
	}
}

FTransform APCSPMassSpawner::MakeRepresentationTransform(const FTransform& EntityTransform,
	const int32 StableIndex, const bool bMoving, const float WorldTime) const
{
	const float Scale = FMath::Max(0.1f, RepresentationScale);
	if (!bUsingCharacterRepresentation)
	{
		return FTransform(EntityTransform.GetRotation(), EntityTransform.GetLocation(),
			LegacyCylinderScale * Scale);
	}
	const FQuat EntityRotation = EntityTransform.GetRotation();
	if (bUsingVertexAnimation)
	{
		return FTransform(EntityRotation * RepresentationRotationOffset.Quaternion(),
			EntityTransform.GetLocation() + EntityRotation.RotateVector(RepresentationLocationOffset * Scale),
			FVector(Scale));
	}
	const float Phase = WorldTime * (bMoving ? 8.f : 2.f) + StableIndex * 0.731f;
	const float Bob = bMoving ? FMath::Abs(FMath::Sin(Phase)) * 5.f : FMath::Sin(Phase) * 1.2f;
	const FRotator MotionOffset(bMoving ? 3.5f : 0.f, 0.f,
		bMoving ? FMath::Sin(Phase) * 2.2f : FMath::Sin(Phase) * 0.35f);
	const FVector MotionScale(1.f, 1.f, bMoving ? 1.f : 1.f + FMath::Sin(Phase) * 0.006f);
	return FTransform(
		EntityRotation * MotionOffset.Quaternion() * RepresentationRotationOffset.Quaternion(),
		EntityTransform.GetLocation() + EntityRotation.RotateVector(RepresentationLocationOffset * Scale)
			+ FVector(0.f, 0.f, Bob * Scale), MotionScale * Scale);
}
