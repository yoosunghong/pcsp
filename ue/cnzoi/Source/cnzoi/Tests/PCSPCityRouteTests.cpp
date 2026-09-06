#include "Misc/AutomationTest.h"
#include "Sim/PCSPFlowFieldSubsystem.h"
#include "HAL/IConsoleManager.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPCityRouteFieldTest, "PCSP.Navigation.CityRouteFields",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPCityRouteFieldTest::RunTest(const FString& Parameters)
{
	using FInput = UPCSPFlowFieldSubsystem::FBuildInput;
	FInput Input;
	Input.Width = 9;
	Input.Height = 7;
	Input.CellSize = 200.f;
	Input.Walkable.Init(1, 63);
	Input.GroundHeights.Init(0.f, 63);
	Input.Surfaces.Add(FBox2D(FVector2D(0, 0), FVector2D(1800, 1400)));
	Input.Obstacles.Add(FBox2D(FVector2D(800, 400), FVector2D(1000, 1400)));
	// A canal can be crossed only at row 1. A diagonal beside its bank must not
	// bypass the water cell, even when it is closer to the requested zone.
	for (int32 Y = 0; Y < 7; ++Y) { Input.Walkable[Y * 9 + 4] = Y == 1 ? 1 : 0; }
	UPCSPFlowFieldSubsystem::FSource Source;
	Source.CellIndex = 5 * 9 + 7;
	Source.FinishBounds = FBox2D(FVector2D(1250, 850), FVector2D(1750, 1350));
	Input.SourcesByZone.Add(17, Source);
	auto Result = UPCSPFlowFieldSubsystem::BuildFields(Input);
	TestEqual(TEXT("One field per exact zone identifier"), Result.Fields.Num(), 1);
	int32 Cell = 5 * 9 + 1;
	bool bCrossedBridge = false;
	for (int32 Step = 0; Step < 63 && Cell != Source.CellIndex; ++Step)
	{
		const FVector2f Direction = Result.Fields[17].Directions[Cell];
		TestFalse(TEXT("A reachable cell has a successor"), Direction.IsNearlyZero());
		if (Direction.IsNearlyZero()) { break; }
		const int32 X = Cell % 9;
		const int32 Y = Cell / 9;
		const int32 NX = X + FMath::RoundToInt(Direction.X);
		const int32 NY = Y + FMath::RoundToInt(Direction.Y);
		TestTrue(TEXT("Every successor stays out of water"), Input.Walkable[NY * 9 + NX] != 0);
		if (NX != X && NY != Y)
		{
			TestTrue(TEXT("Diagonal cannot cut blocked horizontal corner"), Input.Walkable[Y * 9 + NX] != 0);
			TestTrue(TEXT("Diagonal cannot cut blocked vertical corner"), Input.Walkable[NY * 9 + X] != 0);
		}
		if (NX == 4) { bCrossedBridge = NY == 1; }
		Cell = NY * 9 + NX;
	}
	TestEqual(TEXT("Route reaches the intended zone"), Cell, Source.CellIndex);
	TestTrue(TEXT("Route uses the bridge"), bCrossedBridge);

	Input.Walkable[1 * 9 + 4] = 0;
	auto Disconnected = UPCSPFlowFieldSubsystem::BuildFields(Input);
	TestTrue(TEXT("No bridge means no route, not a straight fallback"),
		Disconnected.Fields[17].Directions[5 * 9 + 1].IsNearlyZero());

	UPCSPFlowFieldSubsystem* Routes = NewObject<UPCSPFlowFieldSubsystem>();
	Routes->BuiltData = MoveTemp(Result);
	Routes->bReady = true;
	IConsoleVariable* Enabled = IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.MassFlowFieldEnabled"));
	const int32 Previous = Enabled->GetInt();
	Enabled->Set(1, ECVF_SetByCode);
	FVector Waypoint;
	const FVector ExactSlot(1700, 1300, 1);
	TestTrue(TEXT("Finish area routes to the reserved slot"),
		Routes->GetWaypointToZone(FVector(1500, 1100, 1), ExactSlot, 17, Waypoint));
	TestTrue(TEXT("The final waypoint is exact, not the zone center"), Waypoint.Equals(ExactSlot));
	TestFalse(TEXT("A different zone cannot steal this field"),
		Routes->GetWaypointToZone(FVector(1500, 1100, 1), ExactSlot, 18, Waypoint));
	Routes->BuiltData.Fields[17].Directions[5 * 9 + 1] = FVector2f::ZeroVector;
	TestTrue(TEXT("A safe position in an excluded cell connects to nearby route"),
		Routes->GetWaypointToZone(FVector(300, 1100, 1), ExactSlot, 17, Waypoint));
	TestFalse(TEXT("Recovery connector cannot start inside a water obstacle"),
		Routes->GetWaypointToZone(FVector(900, 1100, 1), ExactSlot, 17, Waypoint));
	Enabled->Set(Previous, ECVF_SetByCode);
	return true;
}

#endif
