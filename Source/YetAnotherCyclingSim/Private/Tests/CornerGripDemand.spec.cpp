#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerGripDemand.h"
#include "Cycling/CornerLateralLimit.h"
#include "Cycling/SurfaceGripPolicy.h"

#include <cmath>
#include <limits>

namespace Stage4CCornerGripDemandTests
{
	using namespace CyclingCornerContext;
	using namespace CyclingCornerLimit;
	using namespace CyclingSurfaceGrip;

	FCornerContext MakeContext(
		double RadiusM = 50.0,
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
		Context.DistanceToCornerStartM = 0.0;
		Context.ApexDistanceM = 100.0;
		Context.Direction = ECornerDirection::Right;
		Context.SignedCurvaturePerM = 1.0 / RadiusM;
		Context.CenterlineRadiusM = RadiusM;
		Context.EffectiveRadiusM = RadiusM;
		Context.RoadWidthM = 6.0;
		Context.LeftMarginM = 3.0;
		Context.RightMarginM = 3.0;
		Context.CrossSlopeAngleRad = CrossSlopeAngleRad;
		Context.SurfaceId = TEXT("asphalt");
		Context.Wetness = Wetness;
		Context.Roughness = 0.0;
		return Context;
	}

	bool BuildLimit(
		const FCornerContext& Context,
		FCornerLateralLimit& OutLimit,
		FString& OutError)
	{
		FSurfaceGripPolicy Policy;
		if (!TryBuildAlpineSurfaceGripPolicy(Policy, OutError))
		{
			return false;
		}
		return TryCalculateCornerLateralLimit(
			Context,
			Policy,
			0.8,
			OutLimit,
			OutError);
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-10)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerGripDemandZeroTest,
	"CyclingCornering.CornerGripDemand.ZeroDemand",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerGripDemandZeroTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerGrip;
	using namespace Stage4CCornerGripDemandTests;

	const FCornerContext Context = MakeContext();
	CyclingCornerLimit::FCornerLateralLimit Limit;
	FString Error;
	TestTrue(TEXT("lateral limit builds"), BuildLimit(Context, Limit, Error));

	FCornerGripDemand Demand;
	TestTrue(TEXT("zero demand resolves"),
		TryCalculateCornerGripDemand(Context, Limit, 0.0, 0.0, Demand, Error));
	TestTrue(TEXT("zero lateral acceleration"),
		NearlyEqual(Demand.LateralAccelerationDemandMps2, 0.0));
	TestTrue(TEXT("zero longitudinal usage"),
		NearlyEqual(Demand.LongitudinalUsage, 0.0));
	TestTrue(TEXT("zero lateral usage"),
		NearlyEqual(Demand.LateralUsage, 0.0));
	TestTrue(TEXT("zero combined usage"),
		NearlyEqual(Demand.Budget.CombinedUsage, 0.0));
	TestFalse(TEXT("zero demand is not exceeded"), Demand.Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerGripDemandLimitTest,
	"CyclingCornering.CornerGripDemand.LateralLimit",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerGripDemandLimitTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerGrip;
	using namespace Stage4CCornerGripDemandTests;

	const FCornerContext Context = MakeContext();
	CyclingCornerLimit::FCornerLateralLimit Limit;
	FString Error;
	TestTrue(TEXT("lateral limit builds"), BuildLimit(Context, Limit, Error));

	FCornerGripDemand LateralOnly;
	TestTrue(TEXT("lateral-limit demand resolves"),
		TryCalculateCornerGripDemand(
			Context,
			Limit,
			Limit.MaximumSpeedMps,
			0.0,
			LateralOnly,
			Error));
	TestTrue(TEXT("maximum lateral speed uses full lateral budget"),
		NearlyEqual(LateralOnly.LateralUsage, 1.0));

	FCornerGripDemand WithBrake;
	TestTrue(TEXT("lateral-limit plus brake resolves"),
		TryCalculateCornerGripDemand(
			Context,
			Limit,
			Limit.MaximumSpeedMps,
			0.2,
			WithBrake,
			Error));
	TestTrue(TEXT("brake ratio becomes longitudinal usage"),
		NearlyEqual(WithBrake.LongitudinalUsage, 0.2));
	TestTrue(TEXT("combined demand exceeds shared circle"),
		WithBrake.Budget.CombinedUsage > 1.0);
	TestTrue(TEXT("shared budget marks exceed"), WithBrake.Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerGripDemandBoundaryTest,
	"CyclingCornering.CornerGripDemand.CircleBoundary",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerGripDemandBoundaryTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerGrip;
	using namespace Stage4CCornerGripDemandTests;

	const FCornerContext Context = MakeContext();
	CyclingCornerLimit::FCornerLateralLimit Limit;
	FString Error;
	TestTrue(TEXT("lateral limit builds"), BuildLimit(Context, Limit, Error));

	const double TargetLateralUsage = 0.8;
	const double SpeedMps = std::sqrt(
		TargetLateralUsage
		* Limit.LateralAccelerationLimitMps2
		* Context.EffectiveRadiusM);

	FCornerGripDemand Demand;
	TestTrue(TEXT("3-4-5 demand resolves"),
		TryCalculateCornerGripDemand(
			Context,
			Limit,
			SpeedMps,
			0.6,
			Demand,
			Error));
	TestTrue(TEXT("longitudinal usage is 0.6"),
		NearlyEqual(Demand.LongitudinalUsage, 0.6));
	TestTrue(TEXT("lateral usage is 0.8"),
		NearlyEqual(Demand.LateralUsage, 0.8));
	TestTrue(TEXT("combined usage is the circle boundary"),
		NearlyEqual(Demand.Budget.CombinedUsage, 1.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerGripDemandSurfaceBankTest,
	"CyclingCornering.CornerGripDemand.SurfaceAndBank",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerGripDemandSurfaceBankTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerGrip;
	using namespace Stage4CCornerGripDemandTests;

	const double SpeedMps = 12.0;
	FString Error;

	const FCornerContext DryContext = MakeContext(50.0, 0.0, 0.0);
	const FCornerContext WetContext = MakeContext(50.0, 0.0, 1.0);
	CyclingCornerLimit::FCornerLateralLimit DryLimit;
	CyclingCornerLimit::FCornerLateralLimit WetLimit;
	TestTrue(TEXT("dry limit builds"), BuildLimit(DryContext, DryLimit, Error));
	TestTrue(TEXT("wet limit builds"), BuildLimit(WetContext, WetLimit, Error));

	FCornerGripDemand DryDemand;
	FCornerGripDemand WetDemand;
	TestTrue(TEXT("dry demand resolves"),
		TryCalculateCornerGripDemand(
			DryContext, DryLimit, SpeedMps, 0.0, DryDemand, Error));
	TestTrue(TEXT("wet demand resolves"),
		TryCalculateCornerGripDemand(
			WetContext, WetLimit, SpeedMps, 0.0, WetDemand, Error));
	TestTrue(TEXT("wet asphalt has lower lateral capacity"),
		WetLimit.LateralAccelerationLimitMps2 < DryLimit.LateralAccelerationLimitMps2);
	TestTrue(TEXT("wet asphalt uses more grip at same speed"),
		WetDemand.LateralUsage > DryDemand.LateralUsage);

	const double AngleRad = FMath::DegreesToRadians(5.0);
	const FCornerContext SupportiveContext = MakeContext(50.0, -AngleRad, 0.0);
	CyclingCornerLimit::FCornerLateralLimit SupportiveLimit;
	TestTrue(TEXT("supportive-bank limit builds"),
		BuildLimit(SupportiveContext, SupportiveLimit, Error));

	FCornerGripDemand SupportiveDemand;
	TestTrue(TEXT("supportive-bank demand resolves"),
		TryCalculateCornerGripDemand(
			SupportiveContext,
			SupportiveLimit,
			SpeedMps,
			0.0,
			SupportiveDemand,
			Error));
	TestTrue(TEXT("supportive bank increases lateral capacity"),
		SupportiveLimit.LateralAccelerationLimitMps2 > DryLimit.LateralAccelerationLimitMps2);
	TestTrue(TEXT("supportive bank reduces usage at same speed"),
		SupportiveDemand.LateralUsage < DryDemand.LateralUsage);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerGripDemandValidationTest,
	"CyclingCornering.CornerGripDemand.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerGripDemandValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornerGrip;
	using namespace Stage4CCornerGripDemandTests;

	const FCornerContext Context = MakeContext();
	CyclingCornerLimit::FCornerLateralLimit Limit;
	FString Error;
	TestTrue(TEXT("lateral limit builds"), BuildLimit(Context, Limit, Error));

	FCornerGripDemand Demand;
	TestFalse(TEXT("negative speed rejected"),
		TryCalculateCornerGripDemand(Context, Limit, -0.01, 0.0, Demand, Error));
	TestFalse(TEXT("brake above one rejected"),
		TryCalculateCornerGripDemand(Context, Limit, 10.0, 1.01, Demand, Error));
	TestFalse(TEXT("NaN brake rejected"),
		TryCalculateCornerGripDemand(
			Context,
			Limit,
			10.0,
			std::numeric_limits<double>::quiet_NaN(),
			Demand,
			Error));

	CyclingCornerLimit::FCornerLateralLimit WrongSurface = Limit;
	WrongSurface.SurfaceId = TEXT("paint");
	TestFalse(TEXT("surface mismatch rejected"),
		TryCalculateCornerGripDemand(
			Context, WrongSurface, 10.0, 0.0, Demand, Error));

	CyclingCornerLimit::FCornerLateralLimit WrongWetness = Limit;
	WrongWetness.Wetness = 0.5;
	TestFalse(TEXT("wetness mismatch rejected"),
		TryCalculateCornerGripDemand(
			Context, WrongWetness, 10.0, 0.0, Demand, Error));

	CyclingCornerLimit::FCornerLateralLimit WrongBank = Limit;
	WrongBank.BankSupportAngleRad = 0.1;
	TestFalse(TEXT("bank-support mismatch rejected"),
		TryCalculateCornerGripDemand(
			Context, WrongBank, 10.0, 0.0, Demand, Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
