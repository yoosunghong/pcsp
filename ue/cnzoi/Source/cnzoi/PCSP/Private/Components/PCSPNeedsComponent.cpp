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

	// Per-need decay so the eight needs don't cross the urgency threshold in
	// lockstep. Uniform decay leaves UrgencyScore latched at ~1.0 because
	// satisfying one need leaves all the others at the floor.
	auto ApplyIfDefault = [&](EPCSPNeed Need, float DecayPerSecond)
	{
		const int32 Idx = static_cast<int32>(Need);
		if (Configs.IsValidIndex(Idx) && FMath::IsNearlyEqual(Configs[Idx].DecayPerSecond, 0.01f))
		{
			Configs[Idx].DecayPerSecond = DecayPerSecond;
		}
	};
	ApplyIfDefault(EPCSPNeed::Hunger,   0.012f);
	ApplyIfDefault(EPCSPNeed::Sleep,    0.004f);
	ApplyIfDefault(EPCSPNeed::Social,   0.007f);
	ApplyIfDefault(EPCSPNeed::Leisure,  0.006f);
	ApplyIfDefault(EPCSPNeed::Hygiene,  0.008f);
	ApplyIfDefault(EPCSPNeed::Fitness,  0.003f);
	ApplyIfDefault(EPCSPNeed::Work,     0.009f);
	ApplyIfDefault(EPCSPNeed::Learning, 0.005f);
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
