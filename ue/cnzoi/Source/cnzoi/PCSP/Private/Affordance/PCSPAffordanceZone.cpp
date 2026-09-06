#include "PCSPAffordanceZone.h"

#include "PCSPInteractionPoint.h"
#include "PCSPAffordanceSubsystem.h"
#include "Components/BoxComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

APCSPAffordanceZone::APCSPAffordanceZone()
{
	PrimaryActorTick.bCanEverTick = false;
	Bounds = CreateDefaultSubobject<UBoxComponent>(TEXT("Bounds"));
	Bounds->SetBoxExtent(FVector(400.f, 400.f, 200.f));
	Bounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RootComponent = Bounds;

	SlotMarkers = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("InteractionSlotMarkers"));
	SlotMarkers->SetupAttachment(Bounds);
	SlotMarkers->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SlotMarkers->SetGenerateOverlapEvents(false);
	SlotMarkers->SetCanEverAffectNavigation(false);
	SlotMarkers->SetCastShadow(false);
	SlotMarkers->bCastDynamicShadow = false;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		SlotMarkers->SetStaticMesh(CylinderMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MarkerMaterial(
		TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (MarkerMaterial.Succeeded())
	{
		SlotMarkerBaseMaterial = MarkerMaterial.Object;
	}

	#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false;
	#endif
}

void APCSPAffordanceZone::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (InteractionSlots.IsEmpty() && !InteractionPoints.IsEmpty())
	{
		ImportLegacyInteractionPointDefinitions(false);
	}
	else if (bAutoGenerateGrid)
	{
		GenerateInteractionGrid();
	}
	RefreshDerivedState();
}

void APCSPAffordanceZone::BeginPlay()
{
	Super::BeginPlay();
	if (InteractionSlots.IsEmpty() && !InteractionPoints.IsEmpty())
	{
		ImportLegacyInteractionPointDefinitions(false);
	}
	else if (bAutoGenerateGrid)
	{
		GenerateInteractionGrid();
	}
	RefreshDerivedState();
	if (VisualizationIndex < 0)
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPAffordanceZone '%s' has no VisualizationIndex; using neutral marker color."), *GetName());
	}
	if (UWorld* World = GetWorld())
	{
		if (UPCSPAffordanceSubsystem* Sub = World->GetSubsystem<UPCSPAffordanceSubsystem>())
		{
			Sub->RegisterZone(this);
		}
	}
}

void APCSPAffordanceZone::EndPlay(const EEndPlayReason::Type Reason)
{
	if (UWorld* World = GetWorld())
	{
		if (UPCSPAffordanceSubsystem* Sub = World->GetSubsystem<UPCSPAffordanceSubsystem>())
		{
			Sub->UnregisterZone(this);
		}
	}
	Super::EndPlay(Reason);
}

void APCSPAffordanceZone::GenerateInteractionGrid()
{
	const int32 Count = FMath::Max(1, InteractionPointCount);
	InteractionSlots.SetNum(Count);
	const int32 Columns = FMath::CeilToInt(FMath::Sqrt(static_cast<float>(Count)));
	const int32 Rows = FMath::DivideAndRoundUp(Count, Columns);
	for (int32 Index = 0; Index < Count; ++Index)
	{
		const int32 Column = Index % Columns;
		const int32 Row = Index / Columns;
		InteractionSlots[Index].RelativeLocation = FVector(
			(static_cast<float>(Column) - (static_cast<float>(Columns) - 1.f) * 0.5f) * InteractionPointSpacing,
			(static_cast<float>(Row) - (static_cast<float>(Rows) - 1.f) * 0.5f) * InteractionPointSpacing,
			0.f);
	}
}

int32 APCSPAffordanceZone::ImportLegacyInteractionPointDefinitions(const bool bClearReferences)
{
	TArray<FPCSPInteractionSlot> Imported;
	for (APCSPInteractionPoint* Point : InteractionPoints)
	{
		if (!Point) { continue; }
		FPCSPInteractionSlot& Slot = Imported.AddDefaulted_GetRef();
		Slot.RelativeLocation = GetActorTransform().InverseTransformPosition(Point->GetActorLocation());
		Slot.InteractionDuration = Point->InteractionDuration;
	}
	if (!Imported.IsEmpty())
	{
		InteractionSlots = MoveTemp(Imported);
		InteractionPointCount = InteractionSlots.Num();
		bAutoGenerateGrid = false;
	}
	if (bClearReferences)
	{
		InteractionPoints.Reset();
	}
	return InteractionSlots.Num();
}

int32 APCSPAffordanceZone::MigrateLegacyInteractionPoints()
{
	const int32 Result = ImportLegacyInteractionPointDefinitions(true);
	RefreshDerivedState();
	return Result;
}

void APCSPAffordanceZone::RefreshDerivedState()
{
	Capacity = InteractionSlots.Num();
	InteractionPointCount = FMath::Max(1, Capacity);
	SlotReservers.SetNum(Capacity);

	float MaxAbsX = 0.f;
	float MaxAbsY = 0.f;
	for (const FPCSPInteractionSlot& Slot : InteractionSlots)
	{
		MaxAbsX = FMath::Max(MaxAbsX, FMath::Abs(Slot.RelativeLocation.X));
		MaxAbsY = FMath::Max(MaxAbsY, FMath::Abs(Slot.RelativeLocation.Y));
	}
	Bounds->SetBoxExtent(FVector(
		FMath::Max(100.f, MaxAbsX + BoundsPadding),
		FMath::Max(100.f, MaxAbsY + BoundsPadding),
		200.f));
	RefreshSlotMarkers();
}

void APCSPAffordanceZone::RefreshSlotMarkers()
{
	if (!SlotMarkers) { return; }
	if (SlotMarkerBaseMaterial)
	{
		SlotMarkerMaterial = UMaterialInstanceDynamic::Create(SlotMarkerBaseMaterial, this);
		if (SlotMarkerMaterial)
		{
			const FLinearColor Color = GetVisualizationColor();
			SlotMarkerMaterial->SetVectorParameterValue(TEXT("Color"), Color);
			SlotMarkerMaterial->SetVectorParameterValue(TEXT("BaseColor"), Color);
			SlotMarkerMaterial->SetVectorParameterValue(TEXT("EmissiveColor"), Color * 2.f);
			SlotMarkers->SetMaterial(0, SlotMarkerMaterial);
		}
	}
	SlotMarkers->ClearInstances();
	const FVector MarkerScale(SlotMarkerRadius / 50.f, SlotMarkerRadius / 50.f,
		SlotMarkerHeight / 100.f);
	for (const FPCSPInteractionSlot& Slot : InteractionSlots)
	{
		const FTransform MarkerTransform(FRotator::ZeroRotator,
			Slot.RelativeLocation + FVector(0.f, 0.f, SlotMarkerHeight * 0.5f), MarkerScale);
		SlotMarkers->AddInstance(MarkerTransform, false);
	}
}

int32 APCSPAffordanceZone::GetCurrentOccupancy() const
{
	return FMath::Min(Capacity, GetActorOccupancy() + MassOccupancy);
}

int32 APCSPAffordanceZone::GetActorOccupancy() const
{
	int32 Count = 0;
	for (const TWeakObjectPtr<AActor>& Reserver : SlotReservers)
	{
		if (Reserver.IsValid()) { ++Count; }
	}
	return Count;
}

bool APCSPAffordanceZone::IsInteractionSlotOccupiedByActor(const int32 SlotIndex) const
{
	return SlotReservers.IsValidIndex(SlotIndex) && SlotReservers[SlotIndex].IsValid();
}

void APCSPAffordanceZone::RegisterOccupant(AActor* Actor)
{
	if (Actor) { CurrentOccupants.Add(Actor); }
}

void APCSPAffordanceZone::UnregisterOccupant(AActor* Actor)
{
	if (Actor) { CurrentOccupants.Remove(Actor); }
}

int32 APCSPAffordanceZone::FindFreeInteractionSlot() const
{
	for (int32 Index = 0; Index < InteractionSlots.Num(); ++Index)
	{
		if (!SlotReservers.IsValidIndex(Index) || !SlotReservers[Index].IsValid()) { return Index; }
	}
	return INDEX_NONE;
}

int32 APCSPAffordanceZone::FindReservedInteractionSlot(AActor* Requester) const
{
	if (!Requester) { return INDEX_NONE; }
	for (int32 Index = 0; Index < SlotReservers.Num(); ++Index)
	{
		if (SlotReservers[Index].Get() == Requester) { return Index; }
	}
	return INDEX_NONE;
}

bool APCSPAffordanceZone::TryReserveInteractionSlot(const int32 SlotIndex, AActor* Requester)
{
	if (!Requester || !InteractionSlots.IsValidIndex(SlotIndex)) { return false; }
	if (!SlotReservers.IsValidIndex(SlotIndex)) { SlotReservers.SetNum(InteractionSlots.Num()); }
	if (SlotReservers[SlotIndex].IsValid()) { return false; }
	SlotReservers[SlotIndex] = Requester;
	CurrentOccupants.Add(Requester);
	return true;
}

void APCSPAffordanceZone::ReleaseInteractionSlot(const int32 SlotIndex, AActor* Requester)
{
	if (SlotReservers.IsValidIndex(SlotIndex) && SlotReservers[SlotIndex].Get() == Requester)
	{
		SlotReservers[SlotIndex].Reset();
	}
	if (Requester) { CurrentOccupants.Remove(Requester); }
}

bool APCSPAffordanceZone::IsInteractionSlotReservedBy(const int32 SlotIndex, AActor* Requester) const
{
	return Requester && SlotReservers.IsValidIndex(SlotIndex)
		&& SlotReservers[SlotIndex].Get() == Requester;
}

FVector APCSPAffordanceZone::GetInteractionSlotWorldLocation(const int32 SlotIndex) const
{
	return InteractionSlots.IsValidIndex(SlotIndex)
		? GetActorTransform().TransformPosition(InteractionSlots[SlotIndex].RelativeLocation)
		: GetActorLocation();
}

float APCSPAffordanceZone::GetInteractionSlotDuration(const int32 SlotIndex) const
{
	return InteractionSlots.IsValidIndex(SlotIndex)
		? InteractionSlots[SlotIndex].InteractionDuration : 3.f;
}
