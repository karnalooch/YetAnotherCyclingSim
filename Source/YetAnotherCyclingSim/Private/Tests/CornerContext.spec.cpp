#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerContext.h"

#include <cmath>

namespace Stage4BCornerContextTests
{
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	FRoadPhysicsSampleDefinition MakeSample(
		double DistanceM,
		double CurvaturePerM,
		double WidthM = 6.0,
		double CrossSlopeAngleRad = 0.0,
		const TCHAR* SurfaceId = TEXT("asphalt"),
		double Wetness = 0.0,
		double Roughness = 0.0)
	{
		FRoadPhysicsSampleDefinition Sample;
		Sample.DistanceM = DistanceM;
		Sample.ElevationM = 0.0;
		Sample.GradeDecimal = 0.0;
		Sample.HorizontalCurvaturePerM = CurvaturePerM;
		Sample.VerticalCurvaturePerM = 0.0;
		Sample.RoadWidthM = WidthM;
		Sample.LeftCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.RightCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.SurfaceId = SurfaceId;
		Sample.Wetness = Wetness;
		Sample.Roughness = Roughness;
		return Sample;
	}

	bool BuildProfile(
		const TArray<FRoadPhysicsSampleDefinition>& Samples,
		FRoadPhysicsProfile& OutProfile,
		FString& OutError)
	{
		return OutProfile.TryConfigure(TEXT("Stage 4B fixture"), Samples, OutError);
	}

	FCornerContextSettings Settings(
		double Threshold = 0.01,
		double ScanStepM = 10.0,
		double LookAheadM = 100.0,
		double ApproachLengthM = 50.0)
	{
		FCornerContextSettings Value;
		Value.MinAbsCurvaturePerM = Threshold;
		Value.ScanStepM = ScanStepM;
		Value.LookAheadM = LookAheadM;
		Value.ApproachLengthM = ApproachLengthM;
		return Value;
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerContextStraightTest,
	"CyclingCornering.Context.Straight",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerContextStraightTest::RunTest(const FString& Parameters)
{
	using namespace Stage4BCornerContextTests;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0, 0.0));
	Samples.Add(MakeSample(200.0, 0.0));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("straight profile configures"), BuildProfile(Samples, Profile, Error));

	FCornerContext Context;
	TestTrue(TEXT("straight context resolves"),
		TryBuildCornerContext(Profile, 50.0, 1.0, Settings(), Context, Error));
	TestFalse(TEXT("straight road has no classified corner"), Context.bHasCorner);
	TestTrue(TEXT("straight phase is outside"),
		Context.Phase == CyclingCornering::ECornerPhase::Outside);
	TestTrue(TEXT("straight direction"), Context.Direction == ECornerDirection::Straight);
	TestTrue(TEXT("straight centerline radius is infinite"), std::isinf(Context.CenterlineRadiusM));
	TestTrue(TEXT("straight effective radius is infinite"), std::isinf(Context.EffectiveRadiusM));
	TestTrue(TEXT("left road margin"), NearlyEqual(Context.LeftMarginM, 4.0));
	TestTrue(TEXT("right road margin"), NearlyEqual(Context.RightMarginM, 2.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerContextRadiusTest,
	"CyclingCornering.Context.RadiusAndLateralPosition",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerContextRadiusTest::RunTest(const FString& Parameters)
{
	using namespace Stage4BCornerContextTests;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	FString Error;

	TArray<FRoadPhysicsSampleDefinition> RightSamples;
	RightSamples.Add(MakeSample(0.0, 0.02));
	RightSamples.Add(MakeSample(200.0, 0.02));
	FRoadPhysicsProfile RightProfile;
	TestTrue(TEXT("right profile configures"),
		BuildProfile(RightSamples, RightProfile, Error));

	FCornerContext Center;
	FCornerContext Inside;
	TestTrue(TEXT("right center context resolves"),
		TryBuildCornerContext(RightProfile, 25.0, 0.0, Settings(), Center, Error));
	TestTrue(TEXT("right inside context resolves"),
		TryBuildCornerContext(RightProfile, 25.0, 2.0, Settings(), Inside, Error));
	TestTrue(TEXT("positive curvature maps to right"),
		Center.Direction == ECornerDirection::Right);
	TestTrue(TEXT("centerline radius is 50 m"),
		NearlyEqual(Center.CenterlineRadiusM, 50.0));
	TestTrue(TEXT("center effective radius is 50 m"),
		NearlyEqual(Center.EffectiveRadiusM, 50.0));
	TestTrue(TEXT("positive D tightens right turn"),
		NearlyEqual(Inside.EffectiveRadiusM, 48.0));
	TestTrue(TEXT("first quarter is entry"),
		Inside.Phase == CyclingCornering::ECornerPhase::Entry);

	TArray<FRoadPhysicsSampleDefinition> LeftSamples;
	LeftSamples.Add(MakeSample(0.0, -0.025));
	LeftSamples.Add(MakeSample(200.0, -0.025));
	FRoadPhysicsProfile LeftProfile;
	TestTrue(TEXT("left profile configures"),
		BuildProfile(LeftSamples, LeftProfile, Error));

	FCornerContext LeftInside;
	TestTrue(TEXT("left inside context resolves"),
		TryBuildCornerContext(LeftProfile, 25.0, -2.0, Settings(), LeftInside, Error));
	TestTrue(TEXT("negative curvature maps to left"),
		LeftInside.Direction == ECornerDirection::Left);
	TestTrue(TEXT("left centerline radius is 40 m"),
		NearlyEqual(LeftInside.CenterlineRadiusM, 40.0));
	TestTrue(TEXT("negative D tightens left turn"),
		NearlyEqual(LeftInside.EffectiveRadiusM, 38.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerContextLookAheadTest,
	"CyclingCornering.Context.LookAheadMetadata",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerContextLookAheadTest::RunTest(const FString& Parameters)
{
	using namespace Stage4BCornerContextTests;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	const double BankRad = FMath::DegreesToRadians(4.0);
	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0, 0.0));
	Samples.Add(MakeSample(100.0, 0.0));
	Samples.Add(MakeSample(110.0, 0.02, 6.0, BankRad, TEXT("paint"), 0.5, 0.2));
	Samples.Add(MakeSample(170.0, 0.02, 6.0, BankRad, TEXT("paint"), 0.5, 0.2));
	Samples.Add(MakeSample(180.0, 0.0));
	Samples.Add(MakeSample(250.0, 0.0));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("look-ahead profile configures"), BuildProfile(Samples, Profile, Error));

	FCornerContext Context;
	TestTrue(TEXT("look-ahead context resolves"),
		TryBuildCornerContext(Profile, 70.0, 1.0, Settings(), Context, Error));
	TestTrue(TEXT("upcoming corner found"), Context.bHasCorner);
	TestTrue(TEXT("upcoming corner is approach"),
		Context.Phase == CyclingCornering::ECornerPhase::Approach);
	TestTrue(TEXT("corner start is deterministic"), NearlyEqual(Context.CornerStartM, 110.0));
	TestTrue(TEXT("corner end is deterministic"), NearlyEqual(Context.CornerEndM, 180.0));
	TestTrue(TEXT("distance to start"), NearlyEqual(Context.DistanceToCornerStartM, 40.0));
	TestTrue(TEXT("apex distance"), NearlyEqual(Context.ApexDistanceM, 145.0));
	TestTrue(TEXT("upcoming corner direction"),
		Context.Direction == ECornerDirection::Right);
	TestTrue(TEXT("cross-slope passes through"), NearlyEqual(Context.CrossSlopeAngleRad, BankRad));
	TestEqual(TEXT("surface passes through"), Context.SurfaceId, FString(TEXT("paint")));
	TestTrue(TEXT("wetness passes through"), NearlyEqual(Context.Wetness, 0.5));
	TestTrue(TEXT("roughness passes through"), NearlyEqual(Context.Roughness, 0.2));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerContextStableIntervalTest,
	"CyclingCornering.Context.StableRouteAnchoredInterval",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerContextStableIntervalTest::RunTest(const FString& Parameters)
{
	using namespace Stage4BCornerContextTests;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0, 0.0));
	Samples.Add(MakeSample(100.0, 0.0));
	Samples.Add(MakeSample(110.0, 0.02));
	Samples.Add(MakeSample(170.0, 0.02));
	Samples.Add(MakeSample(180.0, 0.0));
	Samples.Add(MakeSample(250.0, 0.0));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("stable interval profile configures"),
		BuildProfile(Samples, Profile, Error));

	for (const double DistanceM : { 70.0, 70.05, 79.99, 115.0, 115.05, 119.99 })
	{
		FCornerContext Context;
		TestTrue(TEXT("stable interval context resolves"),
			TryBuildCornerContext(
				Profile,
				DistanceM,
				0.0,
				Settings(),
				Context,
				Error));
		TestTrue(TEXT("stable interval finds corner"), Context.bHasCorner);
		TestTrue(TEXT("corner start stays globally anchored"),
			NearlyEqual(Context.CornerStartM, 110.0));
		TestTrue(TEXT("corner end stays globally anchored"),
			NearlyEqual(Context.CornerEndM, 180.0));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerContextPolicyAndValidationTest,
	"CyclingCornering.Context.PolicyAndValidation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerContextPolicyAndValidationTest::RunTest(const FString& Parameters)
{
	using namespace Stage4BCornerContextTests;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;

	TArray<FRoadPhysicsSampleDefinition> Samples;
	Samples.Add(MakeSample(0.0, 0.005));
	Samples.Add(MakeSample(100.0, 0.005));

	FRoadPhysicsProfile Profile;
	FString Error;
	TestTrue(TEXT("threshold profile configures"), BuildProfile(Samples, Profile, Error));

	FCornerContext Context;
	TestTrue(TEXT("default threshold context resolves"),
		TryBuildCornerContext(Profile, 50.0, 0.0, Settings(), Context, Error));
	TestFalse(TEXT("caller threshold keeps shallow curve outside"), Context.bHasCorner);

	TestTrue(TEXT("lower threshold context resolves"),
		TryBuildCornerContext(
			Profile,
			50.0,
			0.0,
			Settings(0.001),
			Context,
			Error));
	TestTrue(TEXT("caller can classify shallow curve"), Context.bHasCorner);

	FCornerContextSettings Invalid = Settings();
	Invalid.ScanStepM = 0.0;
	TestFalse(TEXT("zero scan step rejected"),
		TryBuildCornerContext(Profile, 50.0, 0.0, Invalid, Context, Error));
	TestTrue(TEXT("validation error is reported"), !Error.IsEmpty());

	Invalid = Settings();
	Invalid.LookAheadM = -1.0;
	TestFalse(TEXT("negative look-ahead rejected"),
		TryBuildCornerContext(Profile, 50.0, 0.0, Invalid, Context, Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
