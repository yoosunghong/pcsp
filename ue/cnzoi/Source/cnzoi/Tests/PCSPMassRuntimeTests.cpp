#include "Misc/AutomationTest.h"
#include "Mass/PCSPMassFragments.h"
#include "Mass/PCSPMassRuntime.h"
#include "Affordance/PCSPZoneLayoutMix.h"
#include "Inference/PCSPPolicySubsystem.h"
#include "HAL/IConsoleManager.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPMassCapacityTest, "PCSP.Mass.CapacityAndDuration",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPMassCapacityTest::RunTest(const FString& Parameters)
{
	TestEqual(TEXT("Three-times body gets three-times normal movement speed"),
		PCSPMassRuntime::ScaledSpeed(260.f, 105.f), 780.f);
	TestEqual(TEXT("Three-times body gets three-times stroll speed"),
		PCSPMassRuntime::ScaledSpeed(150.f, 105.f), 450.f);
	TestEqual(TEXT("One-times body preserves authored base speed"),
		PCSPMassRuntime::ScaledSpeed(260.f, 35.f), 260.f);
	TestEqual(TEXT("Three-times body does not triple walking cadence"),
		PCSPMassRuntime::WalkAnimationPlayRate(780.f, 105.f), 1.2f);
	TestTrue(TEXT("A stroll animates more slowly than normal movement"),
		PCSPMassRuntime::WalkAnimationPlayRate(450.f, 105.f)
			< PCSPMassRuntime::WalkAnimationPlayRate(780.f, 105.f));
	TestEqual(TEXT("Full nearest zone is excluded"), PCSPMassRuntime::ZoneScore(10.f, 4, 4),
		TNumericLimits<float>::Max());
	TestTrue(TEXT("Available alternative beats full nearest zone"),
		PCSPMassRuntime::ZoneScore(2500.f, 0, 4) < PCSPMassRuntime::ZoneScore(10.f, 4, 4));
	TestTrue(TEXT("Congestion can favor a slightly farther empty zone"),
		PCSPMassRuntime::ZoneScore(1500.f, 0, 4) < PCSPMassRuntime::ZoneScore(1000.f, 3, 4));
	TestEqual(TEXT("Default authored 3 second interaction becomes 1.05 seconds"),
		PCSPMassRuntime::InteractionDuration(3.f, 0.35f, 0), 1.05f);
	TestTrue(TEXT("Long authored interactions remain bounded"),
		PCSPMassRuntime::InteractionDuration(100.f, 1.f, 4) <= 1.6f);
	TArray<int32> AdmissionCounts;
	AdmissionCounts.Init(0, 1024);
	for (int32 Start = 0; Start < 1024; Start += 32)
	{
		for (int32 Index = 0; Index < 1024; ++Index)
		{
			if (PCSPMassRuntime::IsInDecisionWindow(Index, Start, 32, 1024)) { ++AdmissionCounts[Index]; }
		}
	}
	for (const int32 Count : AdmissionCounts)
	{
		TestEqual(TEXT("Every stable index receives one admission per rotation"), Count, 1);
	}
	TestTrue(TEXT("Window wraps at end of population"),
		PCSPMassRuntime::IsInDecisionWindow(0, 1008, 32, 1024));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPMassHistoryTest, "PCSP.Mass.HudHistoryRing",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPMassHistoryTest::RunTest(const FString& Parameters)
{
	FPCSPMassHistoryFragment History;
	for (int32 Index = 0; Index < 12; ++Index)
	{
		History.AddDecision(EPCSPActionType::EatQuick, static_cast<float>(Index));
	}
	TestEqual(TEXT("History remains bounded"), static_cast<int32>(History.Count), 8);
	TestEqual(TEXT("Oldest retained decision"), History.Times[History.WriteIndex], 4.f);
	TestEqual(TEXT("Newest retained decision"), History.Times[(History.WriteIndex + 7) % 8], 11.f);

	// The repeat run drives obs[22:24], so it counts consecutive repeats across
	// the whole session rather than only the eight decisions the ring retains.
	TestEqual(TEXT("Repeat run counts every repeat, not just retained ones"),
		static_cast<int32>(History.RepeatRun), 11);
	History.AddDecision(EPCSPActionType::FocusedWork, 12.f);
	TestEqual(TEXT("A different action resets the repeat run"),
		static_cast<int32>(History.RepeatRun), 0);

	FPCSPMassHistoryFragment Saturated;
	for (int32 Index = 0; Index < 40; ++Index)
	{
		Saturated.AddDecision(EPCSPActionType::RestAlone, static_cast<float>(Index));
	}
	TestEqual(TEXT("Repeat run saturates at MAX_NOVEL_STEPS"),
		static_cast<int32>(Saturated.RepeatRun), FPCSPMassHistoryFragment::MaxRepeatRun);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPPolicySamplingTest, "PCSP.Policy.ActionSelection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPPolicySamplingTest::RunTest(const FString& Parameters)
{
	IConsoleVariable* Sampling = IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.PolicySampling"));
	IConsoleVariable* Temperature = IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.PolicyTemperature"));
	if (!Sampling || !Temperature)
	{
		AddError(TEXT("pcsp.PolicySampling / pcsp.PolicyTemperature are not registered"));
		return false;
	}
	const int32 PriorSampling = Sampling->GetInt();
	const float PriorTemperature = Temperature->GetFloat();
	Temperature->Set(1.0f, ECVF_SetByCode);

	// Index 2 is the mode; the rest are far enough down to be rare but reachable.
	const TArray<float> Peaked = {0.1f, 0.2f, 5.0f, 0.3f, 0.4f};
	const TArray<float> Uniform = {1.f, 1.f, 1.f, 1.f, 1.f};

	Sampling->Set(0, ECVF_SetByCode);
	TestEqual(TEXT("Argmax mode ignores the seed"),
		UPCSPPolicySubsystem::SelectActionIndex(Peaked, 12345), 2);
	TestEqual(TEXT("Argmax mode is seed-independent"),
		UPCSPPolicySubsystem::SelectActionIndex(Peaked, 999), 2);
	TestEqual(TEXT("Argmax over a flat row takes the first index"),
		UPCSPPolicySubsystem::SelectActionIndex(Uniform, 7), 0);

	Sampling->Set(1, ECVF_SetByCode);
	TestEqual(TEXT("Sampling is a pure function of the seed"),
		UPCSPPolicySubsystem::SelectActionIndex(Peaked, 4242),
		UPCSPPolicySubsystem::SelectActionIndex(Peaked, 4242));

	// A flat row must reach every action; a peaked row must still mostly pick its
	// mode. Together these catch an inverted CDF or an off-by-one walk.
	TSet<int32> UniformSeen;
	int32 PeakedModeHits = 0;
	int32 OutOfRange = 0;
	for (int32 Seed = 0; Seed < 400; ++Seed)
	{
		const int32 U = UPCSPPolicySubsystem::SelectActionIndex(Uniform, Seed);
		const int32 P = UPCSPPolicySubsystem::SelectActionIndex(Peaked, Seed);
		UniformSeen.Add(U);
		if (P == 2) { ++PeakedModeHits; }
		if (U < 0 || U >= 5 || P < 0 || P >= 5) { ++OutOfRange; }
	}
	TestEqual(TEXT("No selection escapes the logit row"), OutOfRange, 0);
	TestEqual(TEXT("A flat distribution reaches every action"), UniformSeen.Num(), 5);
	TestTrue(TEXT("A peaked distribution still favours its mode"), PeakedModeHits > 240);
	TestTrue(TEXT("A peaked distribution is not collapsed to its mode"), PeakedModeHits < 400);

	// BTOnly emits a zeroed logit row to keep the trajectory schema uniform; that
	// is a flat distribution, not a degenerate one, and must not produce garbage.
	const TArray<float> Zeroed = {0.f, 0.f, 0.f, 0.f};
	const int32 FromZeroed = UPCSPPolicySubsystem::SelectActionIndex(Zeroed, 3);
	TestTrue(TEXT("A zeroed logit row still yields a valid index"),
		FromZeroed >= 0 && FromZeroed < 4);
	TestEqual(TEXT("An empty logit row reports no selection"),
		UPCSPPolicySubsystem::SelectActionIndex(TArray<float>(), 3), int32(INDEX_NONE));

	// Temperature must move the distribution monotonically toward its mode.
	Temperature->Set(0.05f, ECVF_SetByCode);
	int32 ColdModeHits = 0;
	for (int32 Seed = 0; Seed < 400; ++Seed)
	{
		if (UPCSPPolicySubsystem::SelectActionIndex(Peaked, Seed) == 2) { ++ColdModeHits; }
	}
	TestTrue(TEXT("A low temperature sharpens toward argmax"), ColdModeHits >= PeakedModeHits);

	Sampling->Set(PriorSampling, ECVF_SetByCode);
	Temperature->Set(PriorTemperature, ECVF_SetByCode);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPMixedLayoutTest, "PCSP.Layout.SeededCategoryMix",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPMixedLayoutTest::RunTest(const FString& Parameters)
{
	const int32 Counts[] = {16, 14, 12, 10, 10, 10, 8, 8, 8};
	TArray<int32> Categories;
	for (int32 Category = 0; Category < UE_ARRAY_COUNT(Counts); ++Category)
	{
		for (int32 Index = 0; Index < Counts[Category]; ++Index) { Categories.Add(Category); }
	}
	const TArray<int32> Order = PCSPZoneLayoutMix::BuildOrder(Categories, 12, 17);
	TestTrue(TEXT("Same seed is reproducible"), Order == PCSPZoneLayoutMix::BuildOrder(Categories, 12, 17));
	TestTrue(TEXT("Different seed changes layout"), Order != PCSPZoneLayoutMix::BuildOrder(Categories, 12, 18));
	TSet<int32> Unique;
	for (const int32 Index : Order) { Unique.Add(Index); }
	TestEqual(TEXT("Every authored zone is retained exactly once"), Unique.Num(), Categories.Num());
	TestEqual(TEXT("No horizontal or vertical same-category neighbors"),
		PCSPZoneLayoutMix::NeighborPenalty(Order, Categories, 12), 0);
	return true;
}

#endif
