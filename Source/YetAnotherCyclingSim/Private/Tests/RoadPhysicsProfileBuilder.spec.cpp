#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/AlpineJourneyRoadPhysics.h"
#include "Cycling/RoadPhysicsProfileBuilder.h"

#include <cmath>

namespace Stage3HRoadPhysicsBuilderTests
{
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return std::abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsAlpineBuilderTest,
	"CyclingPhysics.RoadPhysics.AlpineGeometryBuilder",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsAlpineBuilderTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace Stage3HRoadPhysicsBuilderTests;

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("Alpine road physics profile builds"),
		TryBuildAlpineJourneyRoadPhysicsProfile(Profile, Error));
	TestTrue(TEXT("Alpine road physics build clears error"), Error.IsEmpty());
	TestTrue(TEXT("Alpine road physics profile configured"), Profile.IsConfigured());
	TestEqual(TEXT("Alpine road physics length is 10 km"),
		Profile.GetTotalLengthM(), 10000.0);
	TestEqual(TEXT("Alpine road physics preserves 10 m geometry sampling"),
		Profile.GetSamples().Num(), 1001);

	FRouteGeometryProfile Geometry;
	TestTrue(TEXT("authoritative Alpine geometry builds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	for (const double DistanceM : { 0.0, 1000.0, 5350.0, 10000.0 })
	{
		FRoadPhysicsState State;
		TestTrue(TEXT("road physics state resolves at representative distance"),
			Profile.TryGetStateAt(DistanceM, 0.0, State, Error));

		FVector GeometryPositionM;
		TestTrue(TEXT("geometry position resolves at representative distance"),
			Geometry.TrySamplePosition(DistanceM, GeometryPositionM, Error));

		double ExpectedGrade = 0.0;
		TestTrue(TEXT("geometry grade resolves at representative distance"),
			Geometry.TryCalculateGrade(
				DistanceM,
				AlpineJourneyRoadPhysicsGradeHalfWindowM,
				ExpectedGrade,
				Error));

		TestTrue(TEXT("road physics elevation matches authoritative geometry"),
			NearlyEqual(State.ElevationM, GeometryPositionM.Z));
		TestTrue(TEXT("road physics grade matches authoritative geometry query"),
			NearlyEqual(State.GradeDecimal, ExpectedGrade));
		TestTrue(TEXT("road width uses explicit Alpine physical baseline"),
			NearlyEqual(State.RoadWidthM, AlpineJourneyRoadWidthM));
		TestTrue(TEXT("Stage 3H-C Alpine left cross-slope baseline is flat"),
			NearlyEqual(State.LeftCrossSlopeAngleRad, 0.0));
		TestTrue(TEXT("Stage 3H-C Alpine right cross-slope baseline is flat"),
			NearlyEqual(State.RightCrossSlopeAngleRad, 0.0));
		TestTrue(TEXT("Stage 3H-C local cross-slope baseline is flat"),
			NearlyEqual(State.CrossSlopeAngleRad, 0.0));
		TestEqual(TEXT("Stage 3H-B surface baseline is asphalt"),
			State.SurfaceId, FString(TEXT("asphalt")));
		TestTrue(TEXT("dynamic weather is not baked into route baseline"),
			NearlyEqual(State.Wetness, 0.0));
		TestTrue(TEXT("roughness physics remains neutral baseline"),
			NearlyEqual(State.Roughness, 0.0));
	}

	FRoadPhysicsState EdgeState;
	TestTrue(TEXT("exact right road edge is valid"),
		Profile.TryGetStateAt(5350.0, 3.0, EdgeState, Error));
	TestFalse(TEXT("position outside physical road width is rejected"),
		Profile.TryGetStateAt(5350.0, 3.001, EdgeState, Error));
	TestTrue(TEXT("road-bound failure is explicit"),
		Error.Contains(TEXT("outside road bounds")));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsAlpineCurvatureParityTest,
	"CyclingPhysics.RoadPhysics.AlpineCurvatureParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsAlpineCurvatureParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("Alpine road physics profile builds"),
		TryBuildAlpineJourneyRoadPhysicsProfile(Profile, Error));

	TArray<FAlpineCornerGeometryDefinition> Corners;
	BuildAlpineCornerGeometryDefinitions(Corners);
	TestEqual(TEXT("all eight authored Alpine corners remain present"),
		Corners.Num(), 8);

	for (const FAlpineCornerGeometryDefinition& Corner : Corners)
	{
		FRoadPhysicsState State;
		TestTrue(TEXT("corner-centre road state resolves"),
			Profile.TryGetStateAt(Corner.CenterDistanceM, 0.0, State, Error));

		const double ExpectedPeakCurvature =
			Corner.DirectionSign / Corner.RadiusM;
		const double Tolerance =
			std::abs(ExpectedPeakCurvature) * 0.05;

		TestTrue(
			*FString::Printf(
				TEXT("%s signed curvature follows authored corner direction/radius"),
				*Corner.Id),
			FMath::IsNearlyEqual(
				State.HorizontalCurvaturePerM,
				ExpectedPeakCurvature,
				Tolerance));
	}

	FRoadPhysicsState StraightState;
	TestTrue(TEXT("straight road state resolves"),
		Profile.TryGetStateAt(3000.0, 0.0, StraightState, Error));
	TestTrue(TEXT("non-corner plan-view curvature remains near zero"),
		FMath::Abs(StraightState.HorizontalCurvaturePerM) < 1e-9);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsVerticalCurvatureTest,
	"CyclingPhysics.RoadPhysics.VerticalCurvatureMetadata",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsVerticalCurvatureTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("Alpine road physics profile builds"),
		TryBuildAlpineJourneyRoadPhysicsProfile(Profile, Error));

	FRoadPhysicsState ConstantGradeState;
	TestTrue(TEXT("constant-grade state resolves"),
		Profile.TryGetStateAt(500.0, 0.0, ConstantGradeState, Error));
	TestTrue(TEXT("constant-grade vertical curvature is approximately zero"),
		FMath::Abs(ConstantGradeState.VerticalCurvaturePerM) < 1e-9);

	FRoadPhysicsState GradeTransitionState;
	TestTrue(TEXT("grade-transition state resolves"),
		Profile.TryGetStateAt(1000.0, 0.0, GradeTransitionState, Error));
	TestTrue(TEXT("grade transition preserves non-zero vertical curvature metadata"),
		GradeTransitionState.VerticalCurvaturePerM < -1e-5);
	TestTrue(TEXT("vertical curvature remains finite"),
		FMath::IsFinite(GradeTransitionState.VerticalCurvaturePerM));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsBuilderValidationTest,
	"CyclingPhysics.RoadPhysics.GeometryBuilderValidation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsBuilderValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;

	FRouteGeometryProfile UnconfiguredGeometry;
	FRoadPhysicsProfile Output;
	FString Error;
	FRoadPhysicsGeometryBuildSettings Settings;
	Settings.GradeHalfWindowM = 20.0;
	Settings.CurvatureHalfWindowM = 10.0;
	Settings.RoadWidthM = 6.0;
	Settings.SurfaceId = TEXT("asphalt");

	TestFalse(TEXT("unconfigured geometry is rejected"),
		TryBuildRoadPhysicsProfileFromGeometry(
			TEXT("bad"),
			UnconfiguredGeometry,
			Settings,
			Output,
			Error));
	TestTrue(TEXT("unconfigured geometry failure is explicit"),
		Error.Contains(TEXT("configured route geometry")));

	FRouteGeometryProfile Geometry;
	TestTrue(TEXT("Alpine geometry builds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	Settings.CurvatureHalfWindowM = 0.0;
	TestFalse(TEXT("zero curvature window is rejected"),
		TryBuildRoadPhysicsProfileFromGeometry(
			TEXT("bad"),
			Geometry,
			Settings,
			Output,
			Error));
	TestTrue(TEXT("zero curvature-window failure is explicit"),
		Error.Contains(TEXT("curvature half-window")));

	Settings.CurvatureHalfWindowM = 10.0;
	Settings.RoadWidthM = 0.0;
	TestFalse(TEXT("invalid route metadata is rejected by canonical profile validation"),
		TryBuildRoadPhysicsProfileFromGeometry(
			TEXT("bad"),
			Geometry,
			Settings,
			Output,
			Error));
	TestTrue(TEXT("metadata validation reports road width"),
		Error.Contains(TEXT("width")));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
