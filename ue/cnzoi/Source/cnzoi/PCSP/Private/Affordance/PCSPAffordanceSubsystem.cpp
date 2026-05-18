#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"

FString FPCSPZoneSelectionDebug::ToCompactString() const
{
	const TCHAR* ReasonName = TEXT("Unknown");
	switch (Reason)
	{
	case EPCSPZoneRejection::Selected:            ReasonName = TEXT("Selected"); break;
	case EPCSPZoneRejection::NoZonesRegistered:   ReasonName = TEXT("NoZonesRegistered"); break;
	case EPCSPZoneRejection::AllInvalidWeakPtr:   ReasonName = TEXT("AllInvalidWeakPtr"); break;
	case EPCSPZoneRejection::AllCategoryMismatch: ReasonName = TEXT("AllCategoryMismatch"); break;
	case EPCSPZoneRejection::AllOverCapacity:     ReasonName = TEXT("AllOverCapacity"); break;
	case EPCSPZoneRejection::AllTooFar:           ReasonName = TEXT("AllTooFar"); break;
	}
	return FString::Printf(
		TEXT("%s(reg=%d,valid=%d,catMatch=%d,capOk=%d,inRange=%d,nearest=%.0f)"),
		ReasonName, RegisteredCount, ValidCount,
		CategoryMatchCount, CapacityOkCount, InRangeCount, NearestDistance);
}

void UPCSPAffordanceSubsystem::RegisterZone(APCSPAffordanceZone* Zone)
{
	if (Zone) { Zones.AddUnique(Zone); }
}

void UPCSPAffordanceSubsystem::UnregisterZone(APCSPAffordanceZone* Zone)
{
	Zones.RemoveAll([Zone](const TWeakObjectPtr<APCSPAffordanceZone>& W){ return !W.IsValid() || W.Get() == Zone; });
}

APCSPAffordanceZone* UPCSPAffordanceSubsystem::FindBestZone(const FPCSPAffordanceQuery& Query) const
{
	FPCSPZoneSelectionDebug Unused;
	return FindBestZone(Query, Unused);
}

APCSPAffordanceZone* UPCSPAffordanceSubsystem::FindBestZone(
	const FPCSPAffordanceQuery& Query, FPCSPZoneSelectionDebug& OutDebug) const
{
	OutDebug = FPCSPZoneSelectionDebug{};
	OutDebug.RegisteredCount = Zones.Num();

	if (Zones.Num() == 0)
	{
		OutDebug.Reason = EPCSPZoneRejection::NoZonesRegistered;
		UE_LOG(LogTemp, Warning,
			TEXT("PCSPAffordance: FindBestZone failed - no zones registered. "
			     "Likely cause: World Partition has not loaded any BP_AffordanceZone actors. "
			     "Mark zones Is Spatially Loaded=false, or add a streaming source."));
		return nullptr;
	}

	APCSPAffordanceZone* Best = nullptr;
	float BestScore = -TNumericLimits<float>::Max();
	float NearestDistOfCategory = TNumericLimits<float>::Max();

	for (const TWeakObjectPtr<APCSPAffordanceZone>& W : Zones)
	{
		APCSPAffordanceZone* Z = W.Get();
		if (!Z) { continue; }
		++OutDebug.ValidCount;

		if (Query.Category != EPCSPAffordanceCategory::None && Z->Category != Query.Category)
		{
			continue;
		}
		++OutDebug.CategoryMatchCount;

		const float Dist = FVector::Dist(Z->GetActorLocation(), Query.FromLocation);
		if (Dist < NearestDistOfCategory) { NearestDistOfCategory = Dist; }

		if (Query.bRequireCapacity && !Z->HasCapacity())
		{
			continue;
		}
		++OutDebug.CapacityOkCount;

		if (Dist > Query.MaxDistance)
		{
			continue;
		}
		++OutDebug.InRangeCount;

		float Score = -Dist;
		if (Query.PreferredTag.IsValid() && Z->ZoneTag == Query.PreferredTag) { Score += 5000.f; }
		if (Score > BestScore) { BestScore = Score; Best = Z; }
	}

	OutDebug.NearestDistance = (OutDebug.CategoryMatchCount > 0) ? NearestDistOfCategory : -1.f;

	if (Best)
	{
		OutDebug.Reason = EPCSPZoneRejection::Selected;
		return Best;
	}

	if (OutDebug.ValidCount == 0)
	{
		OutDebug.Reason = EPCSPZoneRejection::AllInvalidWeakPtr;
		UE_LOG(LogTemp, Warning,
			TEXT("PCSPAffordance: FindBestZone failed - all %d registered weak ptrs stale (destroyed/unstreamed)."),
			OutDebug.RegisteredCount);
		return nullptr;
	}

	const UEnum* CategoryEnum = StaticEnum<EPCSPAffordanceCategory>();
	const FString CategoryStr = CategoryEnum
		? CategoryEnum->GetNameStringByValue(static_cast<int64>(Query.Category))
		: FString::FromInt(static_cast<int32>(Query.Category));

	if (OutDebug.CategoryMatchCount == 0)
	{
		OutDebug.Reason = EPCSPZoneRejection::AllCategoryMismatch;
		UE_LOG(LogTemp, Warning,
			TEXT("PCSPAffordance: FindBestZone failed - no zone for category=%s "
			     "(registered=%d, valid=%d). Likely cause: zone actor not streamed in."),
			*CategoryStr, OutDebug.RegisteredCount, OutDebug.ValidCount);
	}
	else if (OutDebug.CapacityOkCount == 0)
	{
		OutDebug.Reason = EPCSPZoneRejection::AllOverCapacity;
		UE_LOG(LogTemp, Verbose,
			TEXT("PCSPAffordance: FindBestZone failed - all %d zones of category=%s at capacity."),
			OutDebug.CategoryMatchCount, *CategoryStr);
	}
	else
	{
		OutDebug.Reason = EPCSPZoneRejection::AllTooFar;
		UE_LOG(LogTemp, Verbose,
			TEXT("PCSPAffordance: FindBestZone failed - %d zones for %s in capacity but beyond MaxDistance=%.0f (nearest=%.0f)."),
			OutDebug.CapacityOkCount, *CategoryStr, Query.MaxDistance, OutDebug.NearestDistance);
	}
	return nullptr;
}

TArray<APCSPAffordanceZone*> UPCSPAffordanceSubsystem::GetZonesByCategory(EPCSPAffordanceCategory Category) const
{
	TArray<APCSPAffordanceZone*> Out;
	for (const TWeakObjectPtr<APCSPAffordanceZone>& W : Zones)
	{
		if (APCSPAffordanceZone* Z = W.Get())
		{
			if (Category == EPCSPAffordanceCategory::None || Z->Category == Category) { Out.Add(Z); }
		}
	}
	return Out;
}
