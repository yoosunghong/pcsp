#include "Misc/AutomationTest.h"
#include "Mass/PCSPMassNavigation.h"
#include "Mass/PCSPMassSpawner.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPMassSeparationTest, "PCSP.Mass.Navigation.Separation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPMassSeparationTest::RunTest(const FString& Parameters)
{
	FPCSPMassNavigation Nav;
	Nav.AddAgent(0, FVector(599, 0, 0), 105.f);
	Nav.AddAgent(1, FVector(601, 0, 0), 105.f);
	TestTrue(TEXT("Neighbors across hash-cell boundaries repel"),
		Nav.Separation(0, FVector(599, 0, 0), 105.f).X < 0);
	TestFalse(TEXT("Spawn cannot overlap a tripled body"), Nav.HasSpace(FVector(810, 0, 0), 105.f));
	TestTrue(TEXT("Authored 260 cm city-slot spacing fits tripled bodies"),
		Nav.HasSpace(FVector(861, 0, 0), 105.f));
	TestTrue(TEXT("Distant spawn remains available"), Nav.HasSpace(FVector(1200, 0, 0), 105.f));
	TestTrue(TEXT("Different floors do not repel"), Nav.Separation(9, FVector(600, 0, 1000), 105.f).IsZero());

	FPCSPMassNavigation Coincident;
	Coincident.AddAgent(2, FVector::ZeroVector, 105.f);
	Coincident.AddAgent(3, FVector::ZeroVector, 105.f);
	const FVector A = Coincident.Separation(2, FVector::ZeroVector, 105.f);
	const FVector B = Coincident.Separation(3, FVector::ZeroVector, 105.f);
	TestFalse(TEXT("Exact overlap has a nonzero escape direction"), A.IsNearlyZero());
	TestTrue(TEXT("Coincident agents escape in opposite directions"), A.Equals(-B));
	FPCSPMassNavigation Contact;
	Contact.AddAgent(1, FVector(400, 0, 0), 105.f);
	TestTrue(TEXT("A long step cannot tunnel through a stationary NPC"),
		Contact.ConstrainStep(0, FVector::ZeroVector, FVector(800, 0, 0), 105.f).X <= 190.f);
	TestTrue(TEXT("Moving away from contact remains possible"),
		Contact.ConstrainStep(0, FVector(200, 0, 0), FVector(100, 0, 0), 105.f).Equals(FVector(100, 0, 0)));
	Contact.SetAgentCollisionEnabled(false);
	TestTrue(TEXT("Collision-off movement passes through another Mass NPC"),
		Contact.ConstrainStep(0, FVector::ZeroVector, FVector(800, 0, 0), 105.f).Equals(FVector(800, 0, 0)));
	TestTrue(TEXT("Collision-off movement applies no separation force"),
		Contact.Separation(0, FVector::ZeroVector, 105.f).IsZero());
	TestTrue(TEXT("Mass bodies default to three times scale"),
		FMath::IsNearlyEqual(GetDefault<APCSPMassSpawner>()->RepresentationScale, 3.f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPCSPMassMissingNavTest, "PCSP.Mass.Navigation.MissingNav",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPCSPMassMissingNavTest::RunTest(const FString& Parameters)
{
	FPCSPMassNavigation Nav;
	FTransform Transform(FVector(12, 34, 56));
	const FTransform Before = Transform;
	TestTrue(TEXT("Missing NavMesh waits instead of walking through geometry"),
		Nav.Move(0, Transform, FVector(500, 600, 56), 260, 105, 0.1f)
		== FPCSPMassNavigation::EMoveResult::Waiting);
	TestTrue(TEXT("Missing NavMesh does not teleport the NPC"), Transform.Equals(Before));
	FVector Stroll;
	TestFalse(TEXT("No unvalidated straight-line stroll fallback"), Nav.FindStroll(FVector::ZeroVector, 900, Stroll));
	return true;
}
#endif
