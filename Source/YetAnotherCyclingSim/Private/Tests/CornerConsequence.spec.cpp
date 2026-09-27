#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerConsequence.h"

#include <cmath>

namespace Stage4CCornerConsequenceTests
{
	using namespace CyclingCornerConsequence;
	using namespace CyclingCornerContext;
	using namespace CyclingCornerGrip;

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}

	FCornerContext MakeContext(
		ECornerDirection Direction = ECornerDirection::Right,
		double LateralPositionM = 0.0,
		double EffectiveRadiusM = 50.0,
		double LeftMarginM = 3.0,
		double RightMarginM = 3.0,
		CyclingCornering::ECornerPhase Phase = CyclingCornering::ECornerPhase::Apex)
	{
		FCornerContext Context;
		Context.DistanceM = 100.0;
		Context.LateralPositionM = LateralPositionM;
		Context.Phase = Phase;
		Context.bHasCorner = true;
		Context.CornerStartM = 80.0;
		Context.CornerEndM = 120.0;
		Context.ApexDistanceM = 100.0;
		Context.Direction = Direction;
		Context.SignedCurvaturePerM =
			Direction == ECornerDirection::Left
				? -1.0 / EffectiveRadiusM
				: 1.0 / EffectiveRadiusM;
		Context.CenterlineRadiusM = EffectiveRadiusM;
		Context.EffectiveRadiusM = EffectiveRadiusM;
		Context.RoadWidthM = LeftMarginM + RightMarginM;
		Context.LeftMarginM = LeftMarginM;
		Context.RightMarginM = RightMarginM;
		Context.SurfaceId = TEXT("asphalt");
		return Context;
	}

	FCornerGripDemand MakeDemand(double SpeedMps = 20.0, double LateralUsage = 1.0)
	{
		FCornerGripDemand Demand;
		Demand.SpeedMps = SpeedMps;
		Demand.LateralUsage = LateralUsage;
		return Demand;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerConsequenceCleanTest,
	"CyclingCornering.Consequence.Geometry.Clean",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerConsequenceCleanTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerConsequenceTests;

	FCornerGeometryConsequence Result;
	FString Error;
	TestTrue(TEXT("clean consequence resolves"),
		TryResolveCornerGeometryConsequence(
			MakeContext(),
			MakeDemand(20.0, 0.8),
			Result,
			Error));

	TestTrue(TEXT("within limit is clean"), Result.Outcome == ECornerGeometryOutcome::Clean);
	TestTrue(TEXT("no outward shift required"), NearlyEqual(Result.RequiredOutwardShiftM, 0.0));
	TestTrue(TEXT("no line deviation"), NearlyEqual(Result.LineDeviationRatio, 0.0));
	TestTrue(TEXT("lateral position unchanged"), NearlyEqual(Result.TargetLateralPositionM, 0.0));
	TestTrue(TEXT("speed unchanged"), NearlyEqual(Result.TargetSpeedMps, 20.0));
	TestTrue(TEXT("speed multiplier unchanged"), NearlyEqual(Result.ExitSpeedMultiplier, 1.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerConsequenceWideLineTest,
	"CyclingCornering.Consequence.Geometry.WideLine",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerConsequenceWideLineTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerConsequenceTests;

	FString Error;
	FCornerGeometryConsequence Right;
	TestTrue(TEXT("right-turn wide line resolves"),
		TryResolveCornerGeometryConsequence(
			MakeContext(ECornerDirection::Right),
			MakeDemand(20.0, 1.04),
			Right,
			Error));
	TestTrue(TEXT("right turn becomes wide line"),
		Right.Outcome == ECornerGeometryOutcome::WideLine);
	TestTrue(TEXT("minimum required radius is 52 m"),
		NearlyEqual(Right.MinimumRequiredRadiusM, 52.0));
	TestTrue(TEXT("required outward shift is 2 m"),
		NearlyEqual(Right.RequiredOutwardShiftM, 2.0));
	TestTrue(TEXT("right turn shifts toward left/outside"),
		NearlyEqual(Right.TargetLateralPositionM, -2.0));
	TestTrue(TEXT("two thirds outside margin used"),
		NearlyEqual(Right.LineDeviationRatio, 2.0 / 3.0));
	TestTrue(TEXT("wide line preserves speed"),
		NearlyEqual(Right.ExitSpeedMultiplier, 1.0));

	FCornerGeometryConsequence Left;
	TestTrue(TEXT("left-turn wide line resolves"),
		TryResolveCornerGeometryConsequence(
			MakeContext(ECornerDirection::Left),
			MakeDemand(20.0, 1.04),
			Left,
			Error));
	TestTrue(TEXT("left turn becomes wide line"),
		Left.Outcome == ECornerGeometryOutcome::WideLine);
	TestTrue(TEXT("left turn shifts toward right/outside"),
		NearlyEqual(Left.TargetLateralPositionM, 2.0));
	TestTrue(TEXT("left/right shift magnitude parity"),
		NearlyEqual(Left.AppliedOutwardShiftM, Right.AppliedOutwardShiftM));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerConsequenceControlledSlipTest,
	"CyclingCornering.Consequence.Geometry.ControlledSlip",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerConsequenceControlledSlipTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerConsequenceTests;

	FString Error;
	FCornerGeometryConsequence Result;
	TestTrue(TEXT("controlled-slip consequence resolves"),
		TryResolveCornerGeometryConsequence(
			MakeContext(ECornerDirection::Right, 0.0, 50.0, 3.0, 3.0),
			MakeDemand(20.0, 1.2),
			Result,
			Error));

	const double ExpectedMultiplier = std::sqrt(53.0 / 60.0);
	TestTrue(TEXT("insufficient width becomes controlled slip"),
		Result.Outcome == ECornerGeometryOutcome::ControlledSlip);
	TestTrue(TEXT("required radius is 60 m"), NearlyEqual(Result.MinimumRequiredRadiusM, 60.0));
	TestTrue(TEXT("maximum feasible radius is 53 m"), NearlyEqual(Result.MaximumFeasibleRadiusM, 53.0));
	TestTrue(TEXT("all 3 m outside margin is consumed"), NearlyEqual(Result.AppliedOutwardShiftM, 3.0));
	TestTrue(TEXT("line deviation consumes full available margin"), NearlyEqual(Result.LineDeviationRatio, 1.0));
	TestTrue(TEXT("target line is road edge"), NearlyEqual(Result.TargetLateralPositionM, -3.0));
	TestTrue(TEXT("speed multiplier is geometry-derived"),
		NearlyEqual(Result.ExitSpeedMultiplier, ExpectedMultiplier));
	TestTrue(TEXT("target speed is geometry-derived"),
		NearlyEqual(Result.TargetSpeedMps, 20.0 * ExpectedMultiplier));

	FCornerGeometryConsequence NoMargin;
	TestTrue(TEXT("zero-margin slip resolves"),
		TryResolveCornerGeometryConsequence(
			MakeContext(ECornerDirection::Right, 0.0, 50.0, 0.0, 6.0),
			MakeDemand(15.0, 1.44),
			NoMargin,
			Error));
	TestTrue(TEXT("zero margin still controlled slip"),
		NoMargin.Outcome == ECornerGeometryOutcome::ControlledSlip);
	TestTrue(TEXT("zero margin cannot shift line"), NearlyEqual(NoMargin.AppliedOutwardShiftM, 0.0));
	TestTrue(TEXT("zero margin keeps line deviation ratio zero"), NearlyEqual(NoMargin.LineDeviationRatio, 0.0));
	TestTrue(TEXT("1.44 usage requires reciprocal 1.2 speed factor"),
		NearlyEqual(NoMargin.ExitSpeedMultiplier, 1.0 / 1.2));
	TestTrue(TEXT("15 m/s becomes 12.5 m/s"), NearlyEqual(NoMargin.TargetSpeedMps, 12.5));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerConsequenceValidationTest,
	"CyclingCornering.Consequence.Geometry.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerConsequenceValidationTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerConsequenceTests;

	FString Error;
	FCornerGeometryConsequence Result;
	TestFalse(TEXT("approach consequence rejected"),
		TryResolveCornerGeometryConsequence(
			MakeContext(
				ECornerDirection::Right,
				0.0,
				50.0,
				3.0,
				3.0,
				CyclingCornering::ECornerPhase::Approach),
			MakeDemand(20.0, 1.1),
			Result,
			Error));
	TestTrue(TEXT("approach error names active phases"),
		Error.Contains(TEXT("entry, apex or exit")));

	FCornerContext InvalidDirection = MakeContext();
	InvalidDirection.Direction = ECornerDirection::Straight;
	TestFalse(TEXT("straight active corner rejected"),
		TryResolveCornerGeometryConsequence(
			InvalidDirection,
			MakeDemand(20.0, 1.1),
			Result,
			Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerConsequenceDeterminismTest,
	"CyclingCornering.Consequence.Geometry.Determinism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerConsequenceDeterminismTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerConsequenceTests;

	const FCornerContext Context =
		MakeContext(ECornerDirection::Right, -0.25, 50.25, 2.5, 3.5);
	const FCornerGripDemand Demand = MakeDemand(17.25, 1.12);

	FString Error;
	FCornerGeometryConsequence Reference;
	TestTrue(TEXT("reference consequence resolves"),
		TryResolveCornerGeometryConsequence(Context, Demand, Reference, Error));

	for (int32 Index = 0; Index < 20; ++Index)
	{
		FCornerGeometryConsequence Repeated;
		TestTrue(TEXT("repeated consequence resolves"),
			TryResolveCornerGeometryConsequence(Context, Demand, Repeated, Error));
		TestTrue(TEXT("outcome deterministic"), Repeated.Outcome == Reference.Outcome);
		TestTrue(TEXT("required radius deterministic"),
			Repeated.MinimumRequiredRadiusM == Reference.MinimumRequiredRadiusM);
		TestTrue(TEXT("target lateral deterministic"),
			Repeated.TargetLateralPositionM == Reference.TargetLateralPositionM);
		TestTrue(TEXT("target speed deterministic"),
			Repeated.TargetSpeedMps == Reference.TargetSpeedMps);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
