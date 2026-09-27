#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/Stage3GForestLayout.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GForestLayoutTest,
	"CyclingStage3World.ForestLayout.TargetDensity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GForestLayoutTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace CyclingStage3G;

	FRouteGeometryProfile Geometry;
	FString Error;
	TestTrue(TEXT("Alpine geometry builds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	const FStage3GForestLayoutConfig Config =
		MakeTargetDensityForestConfig();
	TArray<FStage3GForestCandidate> First;
	TArray<FStage3GForestCandidate> Second;
	FStage3GForestLayoutStats FirstStats;
	FStage3GForestLayoutStats SecondStats;

	TestTrue(TEXT("first target-density layout generates"),
		TryGenerateForestLayout(
			Geometry, Config, First, FirstStats, Error));
	TestTrue(TEXT("second target-density layout generates"),
		TryGenerateForestLayout(
			Geometry, Config, Second, SecondStats, Error));

	TestTrue(TEXT("configured expected candidate mean >= 1850"),
		FirstStats.ExpectedCandidateMean >= 1850.0);
	TestTrue(TEXT("configured expected candidate mean <= 2150"),
		FirstStats.ExpectedCandidateMean <= 2150.0);
	TestTrue(TEXT("generated candidate count >= 1700"),
		First.Num() >= 1700);
	TestTrue(TEXT("generated candidate count <= 2300"),
		First.Num() <= 2300);
	TestTrue(TEXT("primary layer is populated"),
		FirstStats.PrimaryCount > 0);
	TestTrue(TEXT("background layer is populated"),
		FirstStats.BackgroundCount > 0);
	TestTrue(TEXT("understory layer is populated"),
		FirstStats.UnderstoryCount > 0);

	TestEqual(TEXT("deterministic candidate count"),
		First.Num(), Second.Num());
	for (int32 Index = 0; Index < First.Num() && Index < Second.Num(); ++Index)
	{
		const FStage3GForestCandidate& A = First[Index];
		const FStage3GForestCandidate& B = Second[Index];
		TestTrue(TEXT("deterministic layer"), A.Layer == B.Layer);
		TestTrue(TEXT("deterministic route distance"),
			FMath::IsNearlyEqual(A.RouteDistanceM, B.RouteDistanceM, 1e-9));
		TestTrue(TEXT("deterministic lateral offset"),
			FMath::IsNearlyEqual(
				A.SignedLateralOffsetM,
				B.SignedLateralOffsetM,
				1e-9));
		TestTrue(TEXT("deterministic position"),
			A.PositionM.Equals(B.PositionM, 1e-9));
		TestTrue(TEXT("deterministic scale"),
			FMath::IsNearlyEqual(A.UniformScale, B.UniformScale, 1e-9));
		TestTrue(TEXT("deterministic yaw"),
			FMath::IsNearlyEqual(A.YawDeg, B.YawDeg, 1e-9));
		TestEqual(TEXT("deterministic seed"), A.Seed, B.Seed);
		TestTrue(TEXT("candidate stays outside nominal route corridor"),
			FMath::Abs(A.SignedLateralOffsetM)
				> Config.ProtectedRouteHalfWidthM);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
