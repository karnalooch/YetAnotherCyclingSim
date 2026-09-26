#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerLateralLimit.h"
#include "Cycling/Cornering.h"

#include <cmath>
#include <limits>

namespace Stage4BCornerLateralLimitTests
{
	using namespace CyclingCornerContext;
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;

	FCornerContext MakeContext(
		double CurvaturePerM = 0.02,
		double EffectiveRadiusM = 50.0,
		double CrossSlopeAngleRad = 0.0,
		double Wetness = 0.0)
	{
		FCornerContext Context;
		Context.DistanceM = 100.0;
		Context.LateralPositionM = 0.0;
		Context.Phase = CyclingCornering::ECornerPhase::Apex;
		Context.bHasCorner = true;
		Context.CornerStartM = 50.0;
		Context.CornerEndM = 150.0;
		Context.ApexDistanceM = 100.0;
		Context.Direction = CurvaturePerM > 0.0
			? ECornerDirection::Right
			: ECornerDirection::Left;
		Context.SignedCurvaturePerM = CurvaturePerM;
		Context.CenterlineRadiusM = std::abs(1.0 / CurvaturePerM);
		Context.EffectiveRadiusM = EffectiveRadiusM;
		Context.RoadWidthM = 6.0;
		Context.LeftMarginM = 3.0;
		Context.RightMarginM = 3.0;
		Context.CrossSlopeAngleRad = CrossSlopeAngleRad;
		Context.SurfaceId = TEXT("asphalt");
		Context.Wetness = Wetness;
		Context.Roughness = 0.0;
		return Context;
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerLateralFlatParityTest,
	"CyclingCornering.LateralLimit.FlatParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerLateralFlatParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BCornerLateralLimitTests;

	FSurfaceGripPolicy Policy;
	FString Error;
	TestTrue(TEXT("Alpine grip policy builds"), TryBuildAlpineSurfaceGripPolicy(Policy, Error));

	FCornerLateralLimit Limit;
	const FCornerContext Context = MakeContext(0.02, 50.0, 0.0, 0.5);
	TestTrue(TEXT("flat lateral limit resolves"),
		TryCalculateCornerLateralLimit(Context, Policy, 0.8, Limit, Error));

	double ExistingFlatSpeedMps = 0.0;
	TestTrue(TEXT("existing flat formula resolves"),
		CyclingCornering::TryCalculateMaximumCornerSpeedMps(
			50.0,
			0.8,
			0.875,
			ExistingFlatSpeedMps,
			Error));
	TestTrue(TEXT("flat formula parity"),
		NearlyEqual(Limit.MaximumSpeedMps, ExistingFlatSpeedMps));
	TestTrue(TEXT("flat support angle is zero"),
		NearlyEqual(Limit.BankSupportAngleRad, 0.0));
	TestTrue(TEXT("half-wet Alpine grip is 0.875"),
		NearlyEqual(Limit.GripMultiplier, 0.875));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerLateralBankingTest,
	"CyclingCornering.LateralLimit.BankingAndOffCamber",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerLateralBankingTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BCornerLateralLimitTests;

	FSurfaceGripPolicy Policy;
	FString Error;
	TestTrue(TEXT("Alpine grip policy builds"), TryBuildAlpineSurfaceGripPolicy(Policy, Error));

	const double AngleRad = FMath::DegreesToRadians(5.0);
	FCornerLateralLimit Flat;
	FCornerLateralLimit Supportive;
	FCornerLateralLimit Adverse;

	TestTrue(TEXT("flat resolves"),
		TryCalculateCornerLateralLimit(MakeContext(), Policy, 0.8, Flat, Error));
	TestTrue(TEXT("supportive right bank resolves"),
		TryCalculateCornerLateralLimit(
			MakeContext(0.02, 50.0, -AngleRad),
			Policy,
			0.8,
			Supportive,
			Error));
	TestTrue(TEXT("off-camber right turn resolves"),
		TryCalculateCornerLateralLimit(
			MakeContext(0.02, 50.0, AngleRad),
			Policy,
			0.8,
			Adverse,
			Error));

	TestTrue(TEXT("supportive bank has positive support angle"),
		Supportive.BankSupportAngleRad > 0.0);
	TestTrue(TEXT("off-camber has negative support angle"),
		Adverse.BankSupportAngleRad < 0.0);
	TestTrue(TEXT("supportive bank raises limit"),
		Supportive.MaximumSpeedMps > Flat.MaximumSpeedMps);
	TestTrue(TEXT("off-camber lowers limit"),
		Adverse.MaximumSpeedMps < Flat.MaximumSpeedMps);

	FCornerLateralLimit LeftSupportive;
	TestTrue(TEXT("supportive left bank resolves"),
		TryCalculateCornerLateralLimit(
			MakeContext(-0.02, 50.0, AngleRad),
			Policy,
			0.8,
			LeftSupportive,
			Error));
	TestTrue(TEXT("left/right supportive support-angle parity"),
		NearlyEqual(LeftSupportive.BankSupportAngleRad, Supportive.BankSupportAngleRad));
	TestTrue(TEXT("left/right supportive speed parity"),
		NearlyEqual(LeftSupportive.MaximumSpeedMps, Supportive.MaximumSpeedMps));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerLateralWetnessAndRadiusTest,
	"CyclingCornering.LateralLimit.WetnessAndRacingLine",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerLateralWetnessAndRadiusTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BCornerLateralLimitTests;

	FSurfaceGripPolicy Policy;
	FString Error;
	TestTrue(TEXT("Alpine grip policy builds"), TryBuildAlpineSurfaceGripPolicy(Policy, Error));

	FCornerLateralLimit Dry;
	FCornerLateralLimit Wet;
	TestTrue(TEXT("dry limit resolves"),
		TryCalculateCornerLateralLimit(MakeContext(0.02, 50.0, 0.0, 0.0), Policy, 0.8, Dry, Error));
	TestTrue(TEXT("wet limit resolves"),
		TryCalculateCornerLateralLimit(MakeContext(0.02, 50.0, 0.0, 1.0), Policy, 0.8, Wet, Error));
	TestTrue(TEXT("fully wet Alpine grip is 0.75"), NearlyEqual(Wet.GripMultiplier, 0.75));
	TestTrue(TEXT("wet road lowers lateral speed limit"), Wet.MaximumSpeedMps < Dry.MaximumSpeedMps);

	FCornerLateralLimit Outer;
	FCornerLateralLimit Inner;
	TestTrue(TEXT("outer radius resolves"),
		TryCalculateCornerLateralLimit(MakeContext(0.02, 52.0), Policy, 0.8, Outer, Error));
	TestTrue(TEXT("inner radius resolves"),
		TryCalculateCornerLateralLimit(MakeContext(0.02, 48.0), Policy, 0.8, Inner, Error));
	TestTrue(TEXT("larger effective radius raises speed limit"),
		Outer.MaximumSpeedMps > Inner.MaximumSpeedMps);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BCornerLateralValidationTest,
	"CyclingCornering.LateralLimit.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BCornerLateralValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BCornerLateralLimitTests;

	FSurfaceGripPolicy Policy;
	FString Error;
	TestTrue(TEXT("Alpine grip policy builds"), TryBuildAlpineSurfaceGripPolicy(Policy, Error));

	FCornerLateralLimit Limit;
	FCornerContext NoCorner = MakeContext();
	NoCorner.bHasCorner = false;
	TestFalse(TEXT("no-corner context rejected"),
		TryCalculateCornerLateralLimit(NoCorner, Policy, 0.8, Limit, Error));

	TestFalse(TEXT("zero base friction rejected"),
		TryCalculateCornerLateralLimit(MakeContext(), Policy, 0.0, Limit, Error));

	FCornerContext UnknownSurface = MakeContext();
	UnknownSurface.SurfaceId = TEXT("gravel");
	TestFalse(TEXT("unknown surface fails closed"),
		TryCalculateCornerLateralLimit(UnknownSurface, Policy, 0.8, Limit, Error));

	FCornerContext Pathological = MakeContext(
		0.02,
		50.0,
		FMath::DegreesToRadians(80.0));
	TestFalse(TEXT("pathological off-camber combination rejected"),
		TryCalculateCornerLateralLimit(Pathological, Policy, 0.8, Limit, Error));
	TestTrue(TEXT("pathological bank reports supported-model boundary"),
		Error.Contains(TEXT("outside the supported")));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
