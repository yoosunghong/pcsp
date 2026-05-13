#include "PCSPAffordanceSubsystem.h"
#include "PCSPAffordanceZone.h"

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
	APCSPAffordanceZone* Best = nullptr;
	float BestScore = -TNumericLimits<float>::Max();

	for (const TWeakObjectPtr<APCSPAffordanceZone>& W : Zones)
	{
		APCSPAffordanceZone* Z = W.Get();
		if (!Z) { continue; }
		if (Query.Category != EPCSPAffordanceCategory::None && Z->Category != Query.Category) { continue; }
		if (Query.bRequireCapacity && !Z->HasCapacity()) { continue; }

		const float Dist = FVector::Dist(Z->GetActorLocation(), Query.FromLocation);
		if (Dist > Query.MaxDistance) { continue; }

		float Score = -Dist;
		if (Query.PreferredTag.IsValid() && Z->ZoneTag == Query.PreferredTag) { Score += 5000.f; }
		if (Score > BestScore) { BestScore = Score; Best = Z; }
	}
	return Best;
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
