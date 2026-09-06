#include "Misc/AutomationTest.h"
#include "Sim/PCSPPerfSamplerSubsystem.h"
#include "Engine/GameInstance.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPPerformanceWindowTest, "PCSP.Performance.WallClockAndCPU",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPPerformanceWindowTest::RunTest(const FString& Parameters)
{
	const FPCSPPerfPoint Point = UPCSPPerfSamplerSubsystem::MakePoint(2.0, 2.0, 120, 2.0, 8);
	TestEqual(TEXT("Frame count uses elapsed wall time"), Point.FPS, 60.f);
	TestEqual(TEXT("One fully busy logical core out of eight"), Point.CPU, 12.5f);
	TestTrue(TEXT("Frame duration"), FMath::IsNearlyEqual(Point.FrameMs, 1000.f / 60.f));
	TestEqual(TEXT("Missing OS reading stays unavailable"),
		UPCSPPerfSamplerSubsystem::MakePoint(1., 1., 60, -1., 8).CPU, -1.f);
	const FPCSPPerfPoint Empty = UPCSPPerfSamplerSubsystem::MakePoint(0., 0., 0, 0., 8);
	TestEqual(TEXT("Empty window has no fabricated FPS"), Empty.FPS, 0.f);
	FPCSPPerfRun Run;
	Run.RecordedSeconds = 3.0;
	Run.Frames = 150; // 1 s at 90 FPS, then 2 s at 30 FPS
	Run.CPUIntegral = 10.0 + 2.0 * 40.0;
	Run.CPUSeconds = 3.0;
	TestEqual(TEXT("Time-weighted FPS"), Run.MeanFPS(), 50.f);
	TestEqual(TEXT("Time-weighted CPU"), Run.MeanCPU(), 30.f);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPEvaluationContractTest, "PCSP.Performance.EvaluationAxes",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FPCSPEvaluationContractTest::RunTest(const FString& Parameters)
{
	auto* Eval = NewObject<UPCSPEvaluationSubsystem>(NewObject<UGameInstance>());
	Eval->Axis = 0; Eval->Variant = 1;
	TestTrue(TEXT("Persona baseline skips ONNX"), Eval->PolicyMode() == EPCSPPolicyMode::BTOnly);
	TestFalse(TEXT("Needs baseline is not Actor BT"), Eval->IsActorVariant());
	Eval->Axis = 1; Eval->Variant = 0;
	TestTrue(TEXT("Architecture A really selects Actor BT"), Eval->IsActorVariant());
	TestTrue(TEXT("Architecture keeps PCSP"), Eval->PolicyMode() == EPCSPPolicyMode::HybridPCSP);
	Eval->Variant = 1;
	TestFalse(TEXT("Architecture B selects Mass"), Eval->IsActorVariant());
	TestEqual(TEXT("Architecture never changes inference scheduling"), Eval->AsyncMode(), 0);
	Eval->Axis = 2;
	TestEqual(TEXT("Inference B enables worker batches"), Eval->AsyncMode(), 1);
	Eval->Series = TEXT("test");
	FPCSPEvaluationResult Result;
	Result.Series = Eval->Series; Result.Axis = 2; Result.Variant = 1; Result.Run = 1;
	for (int32 I = 1; I <= 100; ++I) { Result.FrameTimes.Add(I); }
	TestEqual(TEXT("p95 calculated from frames, not window averages"), Result.P95(), 95.f);
	Result.Actions.Add(1, 10); Result.Actions.Add(2, 10);
	TestEqual(TEXT("Balanced two-action entropy"), Result.Entropy(), 1.f);
	Eval->SaveResult(Result);
	TestNotNull(TEXT("Matching variant is retrieved"), Eval->Latest(1));
	TestNull(TEXT("Other variant stays unrecorded"), Eval->Latest(0));
	Eval->Series = TEXT("different context");
	TestNull(TEXT("Separate comparison series never mix"), Eval->Latest(1));
	Eval->Axis = 1; Eval->Count = 128; Eval->CycleCount();
	TestEqual(TEXT("Actor evaluation count wraps before expensive Mass-only sizes"), Eval->Count, 16);
	return true;
}
#endif
