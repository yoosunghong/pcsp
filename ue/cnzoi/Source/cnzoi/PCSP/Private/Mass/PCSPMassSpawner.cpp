#include "PCSPMassSpawner.h"

#include "PCSPMassFragments.h"
#include "PCSPTrajectoryLogComponent.h"
#include "MassEntitySubsystem.h"
#include "MassEntityManager.h"
#include "MassCommonFragments.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"

namespace
{
	const FVector MassRepresentationScale(0.22f, 0.22f, 1.65f);
}

APCSPMassSpawner::APCSPMassSpawner()
{
	PrimaryActorTick.bCanEverTick = true;

	Representation = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("MassRepresentation"));
	SetRootComponent(Representation);
	Representation->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Representation->SetCanEverAffectNavigation(false);
	Representation->SetCastShadow(false);
	Representation->bCastDynamicShadow = false;
	Representation->bAffectDistanceFieldLighting = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded()) { Representation->SetStaticMesh(CylinderMesh.Object); }
}

void APCSPMassSpawner::BeginPlay()
{
	Super::BeginPlay();
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
	if (!MassSubsystem) { return 0; }

	FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
	TArray<const UScriptStruct*> Composition;
	Composition.Add(FTransformFragment::StaticStruct());
	Composition.Add(FPCSPMassPersonaFragment::StaticStruct());
	Composition.Add(FPCSPMassNeedsFragment::StaticStruct());
	Composition.Add(FPCSPMassIntentFragment::StaticStruct());
	Composition.Add(FPCSPMassMoveTargetFragment::StaticStruct());
	Composition.Add(FPCSPMassAgentTag::StaticStruct());

	const FMassArchetypeHandle Archetype = EntityManager.CreateArchetype(
		Composition, FMassArchetypeCreationParams(TEXT("PCSPBackgroundAgent")));
	EntityManager.BatchCreateEntities(Archetype, FMath::Max(1, EntityCount), SpawnedEntities);

	FRandomStream Stream(RandomSeed);
	Representation->ClearInstances();
	for (int32 Index = 0; Index < SpawnedEntities.Num(); ++Index)
	{
		const FVector Location = GetActorLocation() + FVector(
			Stream.FRandRange(-SpawnExtent.X, SpawnExtent.X),
			Stream.FRandRange(-SpawnExtent.Y, SpawnExtent.Y), 0.f);

		FTransformFragment& Transform =
			EntityManager.GetFragmentDataChecked<FTransformFragment>(SpawnedEntities[Index]);
		Transform.GetMutableTransform().SetTranslation(Location);

		FPCSPMassPersonaFragment& Persona =
			EntityManager.GetFragmentDataChecked<FPCSPMassPersonaFragment>(SpawnedEntities[Index]);
		Persona.PersonaId = (Index % 300) + 1;
		Persona.StableIndex = Index;
		Persona.Cohort = static_cast<uint16>(Index % 32);

		FPCSPMassIntentFragment& Intent =
			EntityManager.GetFragmentDataChecked<FPCSPMassIntentFragment>(SpawnedEntities[Index]);
		Intent.NextDecisionTime = World->GetTimeSeconds() + Persona.Cohort * 0.035f;

		FPCSPMassMoveTargetFragment& MoveTarget =
			EntityManager.GetFragmentDataChecked<FPCSPMassMoveTargetFragment>(SpawnedEntities[Index]);
		MoveTarget.Speed = 260.f;

		Representation->AddInstance(
			FTransform(FRotator::ZeroRotator, Location, MassRepresentationScale),
			/*bWorldSpace=*/true);
	}

	const FString ConfigPath = UPCSPTrajectoryLogComponent::GetSessionDir() / TEXT("mass_run_config.json");
	const FString Config = FString::Printf(
		TEXT("{\"mass_entities\":%d,\"seed\":%d,\"movement\":\"zone_level_no_navmesh\",")
		TEXT("\"cohorts\":32,\"representation\":\"HISM\",")
		TEXT("\"trajectory_schema\":\"pcsp_ue_behavior_v1\"}\n"),
		SpawnedEntities.Num(), RandomSeed);
	FFileHelper::SaveStringToFile(Config, *ConfigPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), FILEWRITE_None);

	UE_LOG(LogTemp, Log,
		TEXT("PCSPMassSpawner: spawned %d background entities (Mass + zone-level movement + HISM)"),
		SpawnedEntities.Num());
	return SpawnedEntities.Num();
}

void APCSPMassSpawner::DestroyMassEntities()
{
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
	if (Representation) { Representation->ClearInstances(); }
}

void APCSPMassSpawner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	TimeUntilRepresentationUpdate -= DeltaSeconds;
	if (TimeUntilRepresentationUpdate <= 0.f)
	{
		UpdateRepresentation();
		TimeUntilRepresentationUpdate = FMath::Max(0.05f, RepresentationUpdateInterval);
	}
}

void APCSPMassSpawner::UpdateRepresentation()
{
	if (!Representation || SpawnedEntities.IsEmpty()) { return; }
	UWorld* World = GetWorld();
	UMassEntitySubsystem* MassSubsystem = World ? World->GetSubsystem<UMassEntitySubsystem>() : nullptr;
	if (!MassSubsystem) { return; }

	FMassEntityManager& EntityManager = MassSubsystem->GetMutableEntityManager();
	if (EntityManager.IsProcessing()) { return; }

	TArray<FTransform> InstanceTransforms;
	InstanceTransforms.Reserve(SpawnedEntities.Num());
	for (const FMassEntityHandle Entity : SpawnedEntities)
	{
		if (!EntityManager.IsEntityValid(Entity)) { continue; }
		const FTransformFragment& Transform = EntityManager.GetFragmentDataChecked<FTransformFragment>(Entity);
		InstanceTransforms.Add(FTransform(
			Transform.GetTransform().GetRotation(), Transform.GetTransform().GetLocation(),
			MassRepresentationScale));
	}
	if (InstanceTransforms.Num() == Representation->GetInstanceCount())
	{
		Representation->BatchUpdateInstancesTransforms(0, InstanceTransforms,
			/*bWorldSpace=*/true, /*bMarkRenderStateDirty=*/true, /*bTeleport=*/true);
	}
}
