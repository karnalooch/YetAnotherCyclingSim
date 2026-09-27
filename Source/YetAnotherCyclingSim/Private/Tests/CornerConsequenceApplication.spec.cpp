#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include <limits>

#include "Cycling/CornerConsequenceApplication.h"

namespace Stage4CConsequenceApplicationTests
{
	using namespace CyclingCornerApplication;
	using namespace CyclingCornerConsequence;
	using namespace CyclingCornerContext;
	using namespace CyclingCornering;

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}

	FSimulationState MakeState(
		double SpeedMps,
		double DistanceM,
		double ElapsedTimeS,
		double LateralPositionM = 0.0)
	{
		FSimulationState State;
		State.SpeedMps = SpeedMps;
		State.DistanceM = DistanceM;
		State.ElapsedTimeS = ElapsedTimeS;
		State.LateralPositionM = LateralPositionM;
		return State;
	}

	FCornerContext MakeContext(
		double LateralPositionM = 0.0,
		double CornerEndM = 130.0)
	{
		FCornerContext Context;
		Context.DistanceM = 110.0;
		Context.LateralPositionM = LateralPositionM;
		Context.Phase = ECornerPhase::Entry;
		Context.bHasCorner = true;
		Context.CornerStartM = 100.0;
		Context.CornerEndM = CornerEndM;
		Context.DistanceToCornerStartM = 0.0;
		Context.ApexDistanceM = 115.0;
		Context.Direction = ECornerDirection::Right;
		Context.SignedCurvaturePerM = 0.02;
		Context.CenterlineRadiusM = 50.0;
		Context.EffectiveRadiusM = 50.0 - LateralPositionM;
		Context.RoadWidthM = 6.0;
		Context.LeftMarginM = 3.0 + LateralPositionM;
		Context.RightMarginM = 3.0 - LateralPositionM;
		Context.SurfaceId = TEXT("asphalt");
		return Context;
	}

	FCornerGeometryConsequence MakeConsequence(
		ECornerGeometryOutcome Outcome,
		double TargetLateralPositionM,
		double TargetSpeedMps,
		double ExitSpeedMultiplier = 1.0,
		double LineDeviationRatio = 0.0)
	{
		FCornerGeometryConsequence Consequence;
		Consequence.Outcome = Outcome;
		Consequence.MinimumRequiredRadiusM = 50.0;
		Consequence.MaximumFeasibleRadiusM = 53.0;
		Consequence.RequiredOutwardShiftM = FMath::Abs(TargetLateralPositionM);
		Consequence.AppliedOutwardShiftM = FMath::Abs(TargetLateralPositionM);
		Consequence.LineDeviationRatio = LineDeviationRatio;
		Consequence.TargetLateralPositionM = TargetLateralPositionM;
		Consequence.TargetSpeedMps = TargetSpeedMps;
		Consequence.ExitSpeedMultiplier = ExitSpeedMultiplier;
		return Consequence;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceCleanParityTest,
	"CyclingCornering.ConsequenceApplication.CleanParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceCleanParityTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	const FSimulationState Pre = MakeState(10.0, 110.0, 1.0);
	const FSimulationState Integrated = MakeState(10.6, 111.03, 1.1);
	const FCornerGeometryConsequence Consequence =
		MakeConsequence(ECornerGeometryOutcome::Clean, 0.0, 10.0);

	FCornerConsequenceApplication Application;
	FString Error;
	TestTrue(TEXT("clean consequence applies"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			MakeContext(),
			Consequence,
			Application,
			Error));
	TestEqual(TEXT("clean preserves integrated speed"),
		Application.State.SpeedMps, Integrated.SpeedMps);
	TestEqual(TEXT("clean preserves integrated distance"),
		Application.State.DistanceM, Integrated.DistanceM);
	TestEqual(TEXT("clean preserves integrated elapsed time"),
		Application.State.ElapsedTimeS, Integrated.ElapsedTimeS);
	TestEqual(TEXT("clean preserves D"), Application.State.LateralPositionM, 0.0);
	TestEqual(TEXT("clean speed loss is zero"), Application.AppliedSpeedLossMps, 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceWideLineTest,
	"CyclingCornering.ConsequenceApplication.WideLine",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceWideLineTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	const FSimulationState Pre = MakeState(10.0, 110.0, 1.0);
	const FSimulationState Integrated = MakeState(10.6, 111.0, 1.1);
	const FCornerGeometryConsequence Consequence =
		MakeConsequence(
			ECornerGeometryOutcome::WideLine,
			-2.0,
			10.0,
			1.0,
			2.0 / 3.0);

	FCornerConsequenceApplication Application;
	FString Error;
	TestTrue(TEXT("wide-line consequence applies"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			MakeContext(),
			Consequence,
			Application,
			Error));
	TestEqual(TEXT("wide line preserves acceleration"),
		Application.State.SpeedMps, 10.6);
	TestEqual(TEXT("wide line preserves distance"),
		Application.State.DistanceM, 111.0);
	TestTrue(TEXT("wide line moves outward"),
		Application.State.LateralPositionM < 0.0);
	TestTrue(TEXT("wide line does not teleport"),
		Application.State.LateralPositionM > -2.0);
	TestTrue(TEXT("remaining-distance projection parity"),
		NearlyEqual(Application.State.LateralPositionM, -0.1));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceSlipTest,
	"CyclingCornering.ConsequenceApplication.ControlledSlip",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceSlipTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	const FSimulationState Pre = MakeState(10.0, 110.0, 1.0);
	const FSimulationState Integrated = MakeState(10.0, 111.0, 1.1);
	const FCornerGeometryConsequence Consequence =
		MakeConsequence(
			ECornerGeometryOutcome::ControlledSlip,
			-3.0,
			8.0,
			0.8,
			1.0);

	FCornerConsequenceApplication Application;
	FString Error;
	TestTrue(TEXT("controlled slip applies"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			MakeContext(),
			Consequence,
			Application,
			Error));
	TestEqual(TEXT("slip projects speed down"), Application.State.SpeedMps, 8.0);
	TestTrue(TEXT("slip distance uses projected speed"),
		NearlyEqual(Application.State.DistanceM, 110.9));
	TestEqual(TEXT("slip speed loss"), Application.AppliedSpeedLossMps, 2.0);
	TestTrue(TEXT("slip D uses projected distance"),
		NearlyEqual(
			Application.State.LateralPositionM,
			-3.0 * (0.9 / 20.0)));

	const FSimulationState AlreadySlower = MakeState(7.5, 110.875, 1.1);
	TestTrue(TEXT("already slower slip applies"),
		TryApplyCornerGeometryConsequence(
			Pre,
			AlreadySlower,
			MakeContext(),
			Consequence,
			Application,
			Error));
	TestEqual(TEXT("slip never increases speed"), Application.State.SpeedMps, 7.5);
	TestEqual(TEXT("already slower distance preserved"),
		Application.State.DistanceM, 110.875);
	TestEqual(TEXT("already slower has no added speed loss"),
		Application.AppliedSpeedLossMps, 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceSignedDTest,
	"CyclingCornering.ConsequenceApplication.SignedD",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceSignedDTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	const FSimulationState Pre = MakeState(10.0, 110.0, 1.0, -0.5);
	const FSimulationState Integrated = MakeState(10.0, 111.0, 1.1, -0.5);
	const FCornerGeometryConsequence Consequence =
		MakeConsequence(ECornerGeometryOutcome::Clean, -0.5, 10.0);

	FCornerConsequenceApplication Application;
	FString Error;
	TestTrue(TEXT("signed D applies"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			MakeContext(-0.5),
			Consequence,
			Application,
			Error));
	TestEqual(TEXT("negative D is preserved"),
		Application.State.LateralPositionM, -0.5);

	FSimulationState Invalid = Pre;
	Invalid.LateralPositionM = std::numeric_limits<double>::quiet_NaN();
	TestFalse(TEXT("non-finite D is rejected"), Invalid.Validate(Error));
	TestTrue(TEXT("D validation names field"),
		Error.Contains(TEXT("lateral_position_m")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceValidationTest,
	"CyclingCornering.ConsequenceApplication.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceValidationTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	FCornerConsequenceApplication Application;
	FString Error;
	const FSimulationState Pre = MakeState(10.0, 110.0, 1.0);
	const FSimulationState Integrated = MakeState(10.0, 111.0, 1.1);

	FCornerContext Mismatched = MakeContext(0.25);
	TestFalse(TEXT("mismatched context D is rejected"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			Mismatched,
			MakeConsequence(ECornerGeometryOutcome::Clean, 0.25, 10.0),
			Application,
			Error));

	FCornerGeometryConsequence Outside =
		MakeConsequence(ECornerGeometryOutcome::WideLine, -3.1, 10.0);
	TestFalse(TEXT("target outside road is rejected"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			MakeContext(),
			Outside,
			Application,
			Error));

	const FSimulationState NoProgress = MakeState(0.0, 110.0, 1.0);
	const FSimulationState NoProgressIntegrated = MakeState(0.0, 110.0, 1.1);
	TestTrue(TEXT("zero longitudinal movement applies"),
		TryApplyCornerGeometryConsequence(
			NoProgress,
			NoProgressIntegrated,
			MakeContext(),
			MakeConsequence(ECornerGeometryOutcome::WideLine, -2.0, 0.0),
			Application,
			Error));
	TestEqual(TEXT("zero longitudinal movement means zero D movement"),
		Application.State.LateralPositionM, 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceDeterminismTest,
	"CyclingCornering.ConsequenceApplication.Determinism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceDeterminismTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CConsequenceApplicationTests;

	const FSimulationState Pre = MakeState(14.0, 110.0, 1.0);
	const FSimulationState Integrated = MakeState(13.5, 111.375, 1.1);
	const FCornerContext Context = MakeContext();
	const FCornerGeometryConsequence Consequence =
		MakeConsequence(
			ECornerGeometryOutcome::ControlledSlip,
			-2.5,
			12.0,
			12.0 / 14.0,
			0.9);

	FString Error;
	FCornerConsequenceApplication Reference;
	TestTrue(TEXT("reference application resolves"),
		TryApplyCornerGeometryConsequence(
			Pre,
			Integrated,
			Context,
			Consequence,
			Reference,
			Error));

	for (int32 Index = 0; Index < 20; ++Index)
	{
		FCornerConsequenceApplication Repeated;
		TestTrue(TEXT("repeated application resolves"),
			TryApplyCornerGeometryConsequence(
				Pre,
				Integrated,
				Context,
				Consequence,
				Repeated,
				Error));
		TestEqual(TEXT("speed is deterministic"),
			Repeated.State.SpeedMps, Reference.State.SpeedMps);
		TestEqual(TEXT("distance is deterministic"),
			Repeated.State.DistanceM, Reference.State.DistanceM);
		TestEqual(TEXT("D is deterministic"),
			Repeated.State.LateralPositionM,
			Reference.State.LateralPositionM);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
