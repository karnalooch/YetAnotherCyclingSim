#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include <limits>

#include "Cycling/SimulationStep.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace SimulationStepTest
{
	const double NaNValue = std::numeric_limits<double>::quiet_NaN();
	const double InfinityValue = std::numeric_limits<double>::infinity();
	const double Tolerance = 1e-9;

	void ExpectNearlyEqual(FAutomationTestBase& Test, double Actual, double Expected, double ToleranceValue = Tolerance)
	{
		Test.TestTrue(TEXT("expected values to be nearly equal"), FMath::Abs(Actual - Expected) <= ToleranceValue);
	}

	FRiderParameters MakeValidRider()
	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		return Rider;
	}

	FEnvironment MakeEnvironment(double GradeDecimal = 0.0, double WindSpeedMps = 0.0)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = WindSpeedMps;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FRiderInput MakeRiderInput(double PowerW, double CadenceRpm = 90.0)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = CadenceRpm;
		return Input;
	}

	FSimulationState MakeState(double SpeedMps, double DistanceM = 0.0, double ElapsedTimeS = 0.0)
	{
		FSimulationState State;
		State.SpeedMps = SpeedMps;
		State.DistanceM = DistanceM;
		State.ElapsedTimeS = ElapsedTimeS;
		return State;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSimulationStepTest, "CyclingPhysics.SimulationStep",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSimulationStepTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace SimulationStepTest;

	// --- Validation ---

	{
		const FRiderParameters InvalidRider;
		FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
		FString Error = TEXT("stale error");
		TestFalse(TEXT("invalid rider is rejected"), TryStepSimulation(InvalidRider, MakeEnvironment(), MakeRiderInput(250.0), MakeState(5.0), 1.0, OutState, Error));
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 0.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 0.0);
		TestTrue(TEXT("invalid rider error names rider_mass_kg"), Error.Contains(TEXT("rider_mass_kg")));
	}

	{
		const FEnvironment InvalidEnvironment;
		FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
		FString Error;
		TestFalse(TEXT("invalid environment is rejected"), TryStepSimulation(MakeValidRider(), InvalidEnvironment, MakeRiderInput(250.0), MakeState(5.0), 1.0, OutState, Error));
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
		TestTrue(TEXT("invalid environment error names air_density_kg_m3"), Error.Contains(TEXT("air_density_kg_m3")));
	}

	{
		const FRiderInput InvalidInput = MakeRiderInput(-1.0);
		FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
		FString Error;
		TestFalse(TEXT("negative power is rejected"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), InvalidInput, MakeState(5.0), 1.0, OutState, Error));
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
		TestTrue(TEXT("negative power error names power_w"), Error.Contains(TEXT("power_w")));
	}

	{
		const FSimulationState InvalidState = MakeState(-1.0);
		FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
		FString Error;
		TestFalse(TEXT("negative speed state is rejected"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), InvalidState, 1.0, OutState, Error));
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
		TestTrue(TEXT("negative speed state error names speed_mps"), Error.Contains(TEXT("speed_mps")));
	}

	{
		for (double DtS : { 0.0, -1.0, NaNValue, InfinityValue, -InfinityValue })
		{
			FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
			FString Error;
			TestFalse(TEXT("invalid dt is rejected"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), MakeState(5.0), DtS, OutState, Error));
			ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
			ExpectNearlyEqual(*this, OutState.DistanceM, 0.0);
			ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 0.0);
			TestTrue(TEXT("invalid dt error names dt_s"), Error.Contains(TEXT("dt_s")));
		}
	}

	{
		const FRiderParameters InvalidRider;
		const FEnvironment InvalidEnvironment;
		FSimulationState OutState;
		FString Error;
		TestFalse(TEXT("rider and environment are both rejected"), TryStepSimulation(InvalidRider, InvalidEnvironment, MakeRiderInput(250.0), MakeState(5.0), 1.0, OutState, Error));
		TestTrue(TEXT("first error is the rider error"), Error.Contains(TEXT("rider_mass_kg")));
		TestFalse(TEXT("environment error is not reported first"), Error.Contains(TEXT("air_density_kg_m3")));
	}

	// --- Behavior ---

	{
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("stopped bike on flat moves"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), MakeState(0.0), 1.0, OutState, Error));
		TestTrue(TEXT("stopped bike gains speed"), OutState.SpeedMps > 0.0);
		TestTrue(TEXT("stopped bike gains distance"), OutState.DistanceM > 0.0);
	}

	{
		FSimulationState Low;
		FSimulationState High;
		FString Error;
		TestTrue(TEXT("low power step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(100.0), MakeState(0.0), 5.0, Low, Error));
		TestTrue(TEXT("high power step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(500.0), MakeState(0.0), 5.0, High, Error));
		TestTrue(TEXT("more power gives more speed"), High.SpeedMps > Low.SpeedMps);
	}

	{
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("coasting step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(0.0), MakeState(10.0), 1.0, OutState, Error));
		TestTrue(TEXT("no power decelerates on flat road"), OutState.SpeedMps < 10.0);
		TestTrue(TEXT("coasting speed is non-negative"), OutState.SpeedMps >= 0.0);
	}

	{
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("descent coast step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(-0.1), MakeRiderInput(0.0), MakeState(10.0), 1.0, OutState, Error));
		TestTrue(TEXT("no power accelerates on descent"), OutState.SpeedMps > 10.0);
	}

	{
		FSimulationState Flat;
		FSimulationState Climb;
		FString Error;
		TestTrue(TEXT("flat step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(0.0), MakeRiderInput(250.0), MakeState(5.0), 1.0, Flat, Error));
		TestTrue(TEXT("climb step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(0.1), MakeRiderInput(250.0), MakeState(5.0), 1.0, Climb, Error));
		TestTrue(TEXT("climb gives less speed than flat"), Climb.SpeedMps < Flat.SpeedMps);
	}

	{
		struct FCase { double GradeDecimal; double PowerW; double StartSpeedMps; double DtS; };
		const FCase Cases[] = {
			{ 0.0,   0.0,   1.0, 20.0 },
			{ -0.2,  0.0,   0.0, 5.0  },
			{ 0.0,   0.0,   0.0, 1.0  },
			{ 0.0,   250.0, 0.0, 1.0  },
		};
		for (const FCase& Case : Cases)
		{
			FSimulationState OutState;
			FString Error;
			TestTrue(TEXT("speed case succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(Case.GradeDecimal), MakeRiderInput(Case.PowerW), MakeState(Case.StartSpeedMps), Case.DtS, OutState, Error));
			TestTrue(TEXT("speed is never negative"), OutState.SpeedMps >= 0.0);
		}
	}

	{
		const FSimulationState Start = MakeState(10.0, 100.0, 50.0);
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("distance and time step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(0.0), Start, 2.0, OutState, Error));
		TestTrue(TEXT("distance increases"), OutState.DistanceM > Start.DistanceM);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, Start.ElapsedTimeS + 2.0);
	}

	{
		const FSimulationState Start = MakeState(10.0, 100.0, 50.0);
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("mutation step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), Start, 1.0, OutState, Error));
		ExpectNearlyEqual(*this, Start.SpeedMps, 10.0);
		ExpectNearlyEqual(*this, Start.DistanceM, 100.0);
		ExpectNearlyEqual(*this, Start.ElapsedTimeS, 50.0);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FRiderInput Input = MakeRiderInput(250.0);
		const FSimulationState State = MakeState(5.0);
		FSimulationState First;
		FSimulationState Second;
		FString Error;
		TestTrue(TEXT("first identical step succeeds"), TryStepSimulation(Rider, Environment, Input, State, 1.0, First, Error));
		TestTrue(TEXT("second identical step succeeds"), TryStepSimulation(Rider, Environment, Input, State, 1.0, Second, Error));
		TestEqual(TEXT("identical inputs give identical speed"), First.SpeedMps, Second.SpeedMps);
		TestEqual(TEXT("identical inputs give identical distance"), First.DistanceM, Second.DistanceM);
		TestEqual(TEXT("identical inputs give identical time"), First.ElapsedTimeS, Second.ElapsedTimeS);
	}

	{
		FSimulationState OutState;
		FString Error;
		TestTrue(TEXT("finite fields step succeeds"), TryStepSimulation(MakeValidRider(), MakeEnvironment(0.05), MakeRiderInput(250.0), MakeState(5.0), 1.0, OutState, Error));
		TestTrue(TEXT("speed is finite"), FMath::IsFinite(OutState.SpeedMps));
		TestTrue(TEXT("distance is finite"), FMath::IsFinite(OutState.DistanceM));
		TestTrue(TEXT("time is finite"), FMath::IsFinite(OutState.ElapsedTimeS));
	}

	// --- State/OutState aliasing ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.05);
		const FRiderInput Input = MakeRiderInput(250.0);
		const FSimulationState State = MakeState(5.0, 100.0, 50.0);

		FSimulationState Expected;
		FString Error;
		TestTrue(TEXT("separate output step succeeds"), TryStepSimulation(Rider, Environment, Input, State, 1.0, Expected, Error));

		FSimulationState InPlace = State;
		TestTrue(TEXT("aliased step succeeds"), TryStepSimulation(Rider, Environment, Input, InPlace, 1.0, InPlace, Error));

		ExpectNearlyEqual(*this, InPlace.SpeedMps, Expected.SpeedMps);
		ExpectNearlyEqual(*this, InPlace.DistanceM, Expected.DistanceM);
		ExpectNearlyEqual(*this, InPlace.ElapsedTimeS, Expected.ElapsedTimeS);
	}

	// --- Finite inputs whose calculated output overflows ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FRiderInput Input = MakeRiderInput(0.0);
		const FSimulationState State = MakeState(10.0, 0.0, 0.0);
		const double DtS = std::numeric_limits<double>::max();

		FSimulationState OutState = MakeState(1.0, 1.0, 1.0);
		FString Error;
		TestFalse(TEXT("overflowing step is rejected"), TryStepSimulation(Rider, Environment, Input, State, DtS, OutState, Error));
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 0.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 0.0);
		TestTrue(TEXT("overflow error names the calculated field"), Error.Contains(TEXT("distance_m")));
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
