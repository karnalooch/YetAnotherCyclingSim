#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/Braking.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/SimulationState.h"
#include "Cycling/SimulationStep.h"

#include <limits>

namespace Stage4CBrakeForceStepTests
{
	FRiderParameters MakeRider()
	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		return Rider;
	}

	FEnvironment MakeEnvironment(double GradeDecimal = 0.0)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = 0.0;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FRiderInput MakeInput(double PowerW = 0.0, double BrakeRatio = 0.0)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = 90.0;
		Input.BrakeRatio = BrakeRatio;
		return Input;
	}

	FSimulationState MakeState(double SpeedMps)
	{
		FSimulationState State;
		State.SpeedMps = SpeedMps;
		State.DistanceM = 0.0;
		State.ElapsedTimeS = 0.0;
		return State;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakeForceZeroParityTest,
	"CyclingPhysics.BrakingStep.ZeroForceParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakeForceZeroParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage4CBrakeForceStepTests;

	const FRiderParameters Rider = MakeRider();
	const FEnvironment Environment = MakeEnvironment();
	const FRiderInput Input = MakeInput(250.0);
	const FSimulationState Start = MakeState(10.0);

	FSimulationState Legacy;
	FSimulationState ExplicitZero;
	FString Error;
	TestTrue(TEXT("legacy step succeeds"),
		TryStepSimulation(
			Rider, Environment, Input, Start, 0.05, Legacy, Error));
	TestTrue(TEXT("explicit zero brake step succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider,
			Environment,
			Input,
			Start,
			0.05,
			0.0,
			ExplicitZero,
			Error));

	TestEqual(TEXT("zero brake speed is exact regression parity"),
		ExplicitZero.SpeedMps, Legacy.SpeedMps);
	TestEqual(TEXT("zero brake distance is exact regression parity"),
		ExplicitZero.DistanceM, Legacy.DistanceM);
	TestEqual(TEXT("zero brake time is exact regression parity"),
		ExplicitZero.ElapsedTimeS, Legacy.ElapsedTimeS);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakeForceBehaviorTest,
	"CyclingPhysics.BrakingStep.Behavior",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakeForceBehaviorTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage4CBrakeForceStepTests;

	const FRiderParameters Rider = MakeRider();
	const FEnvironment Environment = MakeEnvironment();
	const FRiderInput Input = MakeInput();
	const FSimulationState Start = MakeState(10.0);

	FString Error;
	FSimulationState Coast;
	FSimulationState LowBrake;
	FSimulationState HighBrake;

	TestTrue(TEXT("coast succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider, Environment, Input, Start, 0.05, 0.0, Coast, Error));
	TestTrue(TEXT("low brake succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider, Environment, Input, Start, 0.05, 100.0, LowBrake, Error));
	TestTrue(TEXT("high brake succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider, Environment, Input, Start, 0.05, 500.0, HighBrake, Error));

	TestTrue(TEXT("braking lowers speed relative to coast"),
		LowBrake.SpeedMps < Coast.SpeedMps);
	TestTrue(TEXT("more braking lowers speed further"),
		HighBrake.SpeedMps < LowBrake.SpeedMps);
	TestTrue(TEXT("braking lowers distance relative to coast"),
		HighBrake.DistanceM < Coast.DistanceM);

	FSimulationState Stopped;
	TestTrue(TEXT("very large finite brake force succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider,
			Environment,
			Input,
			MakeState(1.0),
			1.0,
			100000.0,
			Stopped,
			Error));
	TestEqual(TEXT("braking never makes speed negative"),
		Stopped.SpeedMps, 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CResolvedBrakeForceStepTest,
	"CyclingPhysics.BrakingStep.ResolvedForceIntegration",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CResolvedBrakeForceStepTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace CyclingSimulation;
	using namespace Stage4CBrakeForceStepTests;

	const FRiderParameters Rider = MakeRider();
	const FEnvironment Environment = MakeEnvironment();
	const FRiderInput Input = MakeInput(0.0, 0.5);
	const FSimulationState Start = MakeState(12.0);

	FBrakingForceDemand BrakeDemand;
	FString Error;
	TestTrue(TEXT("brake force demand resolves"),
		TryCalculateBrakingForceDemand(
			Rider,
			0.0,
			0.0,
			0.8,
			0.5,
			0.0,
			BrakeDemand,
			Error));
	TestTrue(TEXT("resolved brake force is positive"),
		BrakeDemand.AppliedBrakeForceN > 0.0);

	FSimulationState Coast;
	FSimulationState Braking;
	TestTrue(TEXT("coast step succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider, Environment, Input, Start, 0.05, 0.0, Coast, Error));
	TestTrue(TEXT("resolved-brake step succeeds"),
		TryStepSimulationWithBrakeForce(
			Rider,
			Environment,
			Input,
			Start,
			0.05,
			BrakeDemand.AppliedBrakeForceN,
			Braking,
			Error));
	TestTrue(TEXT("resolved tyre force reduces speed"),
		Braking.SpeedMps < Coast.SpeedMps);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakeForceStepValidationTest,
	"CyclingPhysics.BrakingStep.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakeForceStepValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage4CBrakeForceStepTests;

	FSimulationState OutState;
	FString Error;
	TestFalse(TEXT("negative brake force rejected"),
		TryStepSimulationWithBrakeForce(
			MakeRider(),
			MakeEnvironment(),
			MakeInput(),
			MakeState(10.0),
			0.05,
			-0.01,
			OutState,
			Error));
	TestTrue(TEXT("negative brake error names brake_force_n"),
		Error.Contains(TEXT("brake_force_n")));

	TestFalse(TEXT("NaN brake force rejected"),
		TryStepSimulationWithBrakeForce(
			MakeRider(),
			MakeEnvironment(),
			MakeInput(),
			MakeState(10.0),
			0.05,
			std::numeric_limits<double>::quiet_NaN(),
			OutState,
			Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
