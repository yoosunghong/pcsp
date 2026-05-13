#include "PCSPNeedsComponent.h"

UPCSPNeedsComponent::UPCSPNeedsComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.5f;

	const int32 N = static_cast<int32>(EPCSPNeed::Count);
	Values.Init(0.8f, N);
	Configs.Init(FPCSPNeedConfig(), N);
}

void UPCSPNeedsComponent::BeginPlay()
{
	Super::BeginPlay();

	const int32 N = static_cast<int32>(EPCSPNeed::Count);
	if (Values.Num() != N) { Values.Init(0.8f, N); }
	if (Configs.Num() != N) { Configs.Init(FPCSPNeedConfig(), N); }
}

void UPCSPNeedsComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	for (int32 i = 0; i < Values.Num() && i < Configs.Num(); ++i)
	{
		Values[i] = FMath::Clamp(Values[i] - Configs[i].DecayPerSecond * DeltaTime, 0.f, 1.f);
	}
}

float UPCSPNeedsComponent::GetNeed(EPCSPNeed Need) const
{
	const int32 Idx = static_cast<int32>(Need);
	return Values.IsValidIndex(Idx) ? Values[Idx] : 0.f;
}

void UPCSPNeedsComponent::SetNeed(EPCSPNeed Need, float Value)
{
	const int32 Idx = static_cast<int32>(Need);
	if (Values.IsValidIndex(Idx)) { Values[Idx] = FMath::Clamp(Value, 0.f, 1.f); }
}

void UPCSPNeedsComponent::AdjustNeed(EPCSPNeed Need, float Delta)
{
	const int32 Idx = static_cast<int32>(Need);
	if (Values.IsValidIndex(Idx)) { Values[Idx] = FMath::Clamp(Values[Idx] + Delta, 0.f, 1.f); }
}

bool UPCSPNeedsComponent::IsCritical(EPCSPNeed Need) const
{
	const int32 Idx = static_cast<int32>(Need);
	return Values.IsValidIndex(Idx) && Configs.IsValidIndex(Idx)
		&& Values[Idx] <= Configs[Idx].CriticalThreshold;
}

EPCSPNeed UPCSPNeedsComponent::GetMostUrgentNeed() const
{
	int32 Best = 0;
	float Lowest = TNumericLimits<float>::Max();
	for (int32 i = 0; i < Values.Num(); ++i)
	{
		if (Values[i] < Lowest) { Lowest = Values[i]; Best = i; }
	}
	return static_cast<EPCSPNeed>(Best);
}
