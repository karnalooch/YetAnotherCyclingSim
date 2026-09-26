#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/RoadPhysicsProfile.h"

#include <cmath>
#include <limits>

namespace Stage3HRoadPhysicsTests
{
	using namespace CyclingRoadPhysics;

	constexpr double Pi = 3.14159265358979323846;

	FRoadPhysicsSampleDefinition MakeSample(
		double DistanceM,
		double ElevationM = 100.0,
		double GradeDecimal = 0.0,
		double HorizontalCurvaturePerM = 0.0,
		double VerticalCurvaturePerM = 0.0,
		double RoadWidthM = 6.0,
		double CrossSlopeAngleRad = 0.0,
		const TCHAR* SurfaceId = TEXT("asphalt"),
		double Wetness = 0.0,
		double Roughness = 0.0)
	{
		FRoadPhysicsSampleDefinition Sample;
		Sample.DistanceM = DistanceM;
		Sample.ElevationM = ElevationM;
		Sample.GradeDecimal = GradeDecimal;
		Sample.HorizontalCurvaturePerM = HorizontalCurvaturePerM;
		Sample.VerticalCurvaturePerM = VerticalCurvaturePerM;
		Sample.RoadWidthM = RoadWidthM;
		Sample.LeftCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.RightCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.SurfaceId = SurfaceId;
		Sample.Wetness = Wetness;
		Sample.Roughness = Roughness;
		return Sample;
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return std::abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsInterpolationTest,
	"CyclingPhysics.RoadPhysics.ProfileInterpolation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsInterpolationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace Stage3HRoadPhysicsTests;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0));
	Samples.Add(MakeSample(
		100.0,
		110.0,
		0.10,
		0.02,
		0.001,
		8.0,
		8.0 * Pi / 180.0,
		TEXT("paint"),
		0.4,
		0.2));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("profile config succeeds"),
		Profile.TryConfigure(TEXT("  Test road  "), Samples, Error));
	TestEqual(TEXT("profile name trimmed"), Profile.GetName(), FString(TEXT("Test road")));
	TestTrue(TEXT("profile total length"), NearlyEqual(Profile.GetTotalLengthM(), 100.0));

	FRoadPhysicsState State;
	TestTrue(TEXT("midpoint state resolves"),
		Profile.TryGetStateAt(50.0, 2.0, State, Error));
	TestTrue(TEXT("midpoint S"), NearlyEqual(State.DistanceM, 50.0));
	TestTrue(TEXT("midpoint D"), NearlyEqual(State.LateralPositionM, 2.0));
	TestTrue(TEXT("elevation interpolates"), NearlyEqual(State.ElevationM, 105.0));
	TestTrue(TEXT("grade interpolates"), NearlyEqual(State.GradeDecimal, 0.05));
	TestTrue(TEXT("horizontal curvature interpolates"),
		NearlyEqual(State.HorizontalCurvaturePerM, 0.01));
	TestTrue(TEXT("vertical curvature interpolates"),
		NearlyEqual(State.VerticalCurvaturePerM, 0.0005));
	TestTrue(TEXT("road width interpolates"), NearlyEqual(State.RoadWidthM, 7.0));
	TestTrue(TEXT("bank interpolates"),
		NearlyEqual(State.CrossSlopeAngleRad, 4.0 * Pi / 180.0));
	TestTrue(TEXT("wetness interpolates"), NearlyEqual(State.Wetness, 0.2));
	TestTrue(TEXT("roughness interpolates"), NearlyEqual(State.Roughness, 0.1));
	TestEqual(TEXT("surface is left-interval value"), State.SurfaceId, FString(TEXT("asphalt")));
	TestTrue(TEXT("left edge derived"), NearlyEqual(State.GetLeftEdgeM(), -3.5));
	TestTrue(TEXT("right edge derived"), NearlyEqual(State.GetRightEdgeM(), 3.5));

	TestTrue(TEXT("exact next sample resolves"),
		Profile.TryGetStateAt(100.0, 0.0, State, Error));
	TestEqual(TEXT("exact sample switches surface"), State.SurfaceId, FString(TEXT("paint")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsCrossSlopeTest,
	"CyclingPhysics.RoadPhysics.CrossSlope",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsCrossSlopeTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace Stage3HRoadPhysicsTests;

	TArray<FRoadPhysicsSampleDefinition> PlanarSamples;
	PlanarSamples.Add(MakeSample(0.0));
	PlanarSamples.Add(MakeSample(100.0));
	for (FRoadPhysicsSampleDefinition& Sample : PlanarSamples)
	{
		Sample.LeftCrossSlopeAngleRad = 6.0 * Pi / 180.0;
		Sample.RightCrossSlopeAngleRad = 6.0 * Pi / 180.0;
	}

	FRoadPhysicsProfile PlanarProfile;
	FString Error;
	TestTrue(TEXT("planar bank config succeeds"),
		PlanarProfile.TryConfigure(TEXT("banked"), PlanarSamples, Error));

	FRoadPhysicsState State;
	TestTrue(TEXT("left half resolves planar bank"),
		PlanarProfile.TryGetStateAt(50.0, -2.0, State, Error));
	TestTrue(TEXT("left planar bank uses same cross-slope"),
		NearlyEqual(State.CrossSlopeAngleRad, 6.0 * Pi / 180.0));
	TestTrue(TEXT("right half resolves planar bank"),
		PlanarProfile.TryGetStateAt(50.0, 2.0, State, Error));
	TestTrue(TEXT("right planar bank uses same cross-slope"),
		NearlyEqual(State.CrossSlopeAngleRad, 6.0 * Pi / 180.0));

	TArray<FRoadPhysicsSampleDefinition> CrownSamples;
	CrownSamples.Add(MakeSample(0.0));
	CrownSamples.Add(MakeSample(100.0));
	for (FRoadPhysicsSampleDefinition& Sample : CrownSamples)
	{
		Sample.LeftCrossSlopeAngleRad = 2.0 * Pi / 180.0;
		Sample.RightCrossSlopeAngleRad = -2.0 * Pi / 180.0;
	}

	FRoadPhysicsProfile CrownProfile;
	TestTrue(TEXT("crowned road config succeeds"),
		CrownProfile.TryConfigure(TEXT("crowned"), CrownSamples, Error));
	TestTrue(TEXT("crown left half resolves"),
		CrownProfile.TryGetStateAt(50.0, -1.0, State, Error));
	TestTrue(TEXT("crown left side rises toward centre"),
		NearlyEqual(State.CrossSlopeAngleRad, 2.0 * Pi / 180.0));
	TestTrue(TEXT("crown right half resolves"),
		CrownProfile.TryGetStateAt(50.0, 1.0, State, Error));
	TestTrue(TEXT("crown right side falls from centre"),
		NearlyEqual(State.CrossSlopeAngleRad, -2.0 * Pi / 180.0));
	TestTrue(TEXT("crown centre resolves deterministically"),
		CrownProfile.TryGetStateAt(50.0, 0.0, State, Error));
	TestTrue(TEXT("symmetric crown centre averages to flat"),
		NearlyEqual(State.CrossSlopeAngleRad, 0.0));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsLateralAndLookAheadTest,
	"CyclingPhysics.RoadPhysics.LateralAndLookAhead",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsLateralAndLookAheadTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace Stage3HRoadPhysicsTests;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0, 100.0, 0.0, 0.0, 0.0, 4.0));
	Samples.Add(MakeSample(100.0, 100.0, 0.0, 0.02, 0.0, 8.0));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("profile config succeeds"),
		Profile.TryConfigure(TEXT("lateral"), Samples, Error));

	FRoadPhysicsState State;
	TestTrue(TEXT("exact interpolated road edge is accepted"),
		Profile.TryGetStateAt(50.0, 3.0, State, Error));
	TestFalse(TEXT("outside interpolated road width is rejected"),
		Profile.TryGetStateAt(50.0, 3.001, State, Error));
	TestTrue(TEXT("lateral rejection explains road bounds"),
		Error.Contains(TEXT("outside road bounds")));

	TestTrue(TEXT("look-ahead state resolves"),
		Profile.TryGetStateAhead(25.0, 25.0, 0.0, State, Error));
	TestTrue(TEXT("look-ahead target is deterministic"),
		NearlyEqual(State.DistanceM, 50.0));

	TestTrue(TEXT("look-ahead clamps at route end"),
		Profile.TryGetStateAhead(90.0, 50.0, 0.0, State, Error));
	TestTrue(TEXT("clamped target is route end"),
		NearlyEqual(State.DistanceM, 100.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsTransitionValidationTest,
	"CyclingPhysics.RoadPhysics.TransitionValidation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsTransitionValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace Stage3HRoadPhysicsTests;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0));
	Samples.Add(MakeSample(
		10.0,
		101.0,
		0.10,
		0.02,
		0.0,
		6.0,
		10.0 * Pi / 180.0));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("profile config succeeds"),
		Profile.TryConfigure(TEXT("transitions"), Samples, Error));

	FRoadPhysicsTransitionLimits Passing;
	Passing.MaxAbsGradeChangePerM = 0.011;
	Passing.MaxAbsHorizontalCurvatureChangePerM2 = 0.0021;
	Passing.MaxAbsCrossSlopeAngleChangeRadPerM = 0.018;
	TestTrue(TEXT("explicit transition limits pass"),
		Profile.TryValidateTransitionRates(Passing, Error));

	FRoadPhysicsTransitionLimits Failing = Passing;
	Failing.MaxAbsGradeChangePerM = 0.009;
	TestFalse(TEXT("excessive grade rate is rejected"),
		Profile.TryValidateTransitionRates(Failing, Error));
	TestTrue(TEXT("transition error identifies grade"),
		Error.Contains(TEXT("grade change rate")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3HRoadPhysicsValidationTest,
	"CyclingPhysics.RoadPhysics.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3HRoadPhysicsValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRoadPhysics;
	using namespace Stage3HRoadPhysicsTests;

	FRoadPhysicsProfile Profile;
	FString Error;

	TArray<FRoadPhysicsSampleDefinition> InvalidStart;
	InvalidStart.Add(MakeSample(1.0));
	InvalidStart.Add(MakeSample(2.0));
	TestFalse(TEXT("first sample must start at zero"),
		Profile.TryConfigure(TEXT("bad"), InvalidStart, Error));

	TArray<FRoadPhysicsSampleDefinition> Valid;
	Valid.Add(MakeSample(0.0));
	Valid.Add(MakeSample(100.0));
	TestTrue(TEXT("valid profile config succeeds"),
		Profile.TryConfigure(TEXT("valid"), Valid, Error));
	const FString PreservedName = Profile.GetName();

	TArray<FRoadPhysicsSampleDefinition> InvalidWidth = Valid;
	InvalidWidth[1].RoadWidthM = 0.0;
	TestFalse(TEXT("zero road width rejected"),
		Profile.TryConfigure(TEXT("invalid width"), InvalidWidth, Error));
	TestEqual(TEXT("failed reconfigure preserves previous profile"),
		Profile.GetName(), PreservedName);

	TArray<FRoadPhysicsSampleDefinition> InvalidCrossSlope = Valid;
	InvalidCrossSlope[1].LeftCrossSlopeAngleRad = 0.5 * Pi;
	TestFalse(TEXT("pi/2 cross-slope rejected"),
		Profile.TryConfigure(TEXT("invalid cross-slope"), InvalidCrossSlope, Error));

	TArray<FRoadPhysicsSampleDefinition> InvalidWetness = Valid;
	InvalidWetness[1].Wetness = 1.01;
	TestFalse(TEXT("wetness above one rejected"),
		Profile.TryConfigure(TEXT("invalid wetness"), InvalidWetness, Error));

	TArray<FRoadPhysicsSampleDefinition> InvalidFinite = Valid;
	InvalidFinite[1].HorizontalCurvaturePerM =
		std::numeric_limits<double>::quiet_NaN();
	TestFalse(TEXT("non-finite curvature rejected"),
		Profile.TryConfigure(TEXT("invalid finite"), InvalidFinite, Error));

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
