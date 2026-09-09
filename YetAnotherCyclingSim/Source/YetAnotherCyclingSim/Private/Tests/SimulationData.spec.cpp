#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include "Math/NumericLimits.h"

#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace SimulationDataTest
{
	const double NaNValue = TNumericLimits<double>::NaN();
	const double InfinityValue = TNumericLimits<double>::Infinity();

	void ExpectNearlyEqual(FAutomationTestBase& Test, double Actual, double Expected, double Tolerance = 1e-9)
	{
		Test.TestTrue(TEXT("expected values to be nearly equal"), FMath::Abs(Actual - Expected) <= Tolerance);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSimulationDataTest, "CyclingPhysics.SimulationData",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSimulationDataTest::RunTest(const FString& Parameters)
{
	using namespace SimulationDataTest;

	// --- Defaults ---

	{
		FEnvironment DefaultEnvironment;
		ExpectNearlyEqual(*this, DefaultEnvironment.SurfaceWetness, 0.0);
		ExpectNearlyEqual(*this, DefaultEnvironment.RollingResistanceMultiplier, 1.0);
		ExpectNearlyEqual(*this, DefaultEnvironment.GripMultiplier, 1.0);

		FString Error;
		TestFalse(TEXT("default environment is invalid (zero air density)"), DefaultEnvironment.IsValid());
		TestFalse(TEXT("default environment validate reports air density"), DefaultEnvironment.Validate(Error));
		TestTrue(TEXT("default environment error names air_density_kg_m3"), Error.Contains(TEXT("air_density_kg_m3")));
	}

	{
		FRiderInput DefaultInput;
		ExpectNearlyEqual(*this, DefaultInput.PowerW, 0.0);
		ExpectNearlyEqual(*this, DefaultInput.CadenceRpm, 0.0);
		TestTrue(TEXT("default rider input is valid"), DefaultInput.IsValid());
	}

	{
		FSimulationState DefaultState;
		ExpectNearlyEqual(*this, DefaultState.SpeedMps, 0.0);
		ExpectNearlyEqual(*this, DefaultState.DistanceM, 0.0);
		ExpectNearlyEqual(*this, DefaultState.ElapsedTimeS, 0.0);
		TestTrue(TEXT("default simulation state is valid"), DefaultState.IsValid());
	}

	{
		FRiderParameters DefaultRider;
		FString Error;
		TestFalse(TEXT("default rider parameters are invalid (zero masses)"), DefaultRider.IsValid());
		TestFalse(TEXT("default rider parameters validate reports the first field"), DefaultRider.Validate(Error));
		TestTrue(TEXT("default rider parameters error names rider_mass_kg"), Error.Contains(TEXT("rider_mass_kg")));
	}

	// --- Valid values ---

	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		TestTrue(TEXT("valid rider parameters are valid"), Rider.IsValid());
		FString Error;
		TestTrue(TEXT("valid rider parameters validate returns true"), Rider.Validate(Error));
		TestTrue(TEXT("valid rider parameters clear the error"), Error.IsEmpty());
		ExpectNearlyEqual(*this, Rider.GetTotalMassKg(), 83.5);
	}

	{
		FEnvironment Environment;
		Environment.GradeDecimal = -0.08;
		Environment.WindSpeedMps = -2.0;
		Environment.AirDensityKgM3 = 1.2;
		Environment.SurfaceWetness = 0.5;
		Environment.RollingResistanceMultiplier = 1.1;
		Environment.GripMultiplier = 0.8;
		TestTrue(TEXT("valid environment with negative grade and tailwind is valid"), Environment.IsValid());
	}

	{
		FRiderInput Input;
		Input.PowerW = 250.0;
		Input.CadenceRpm = 90.0;
		TestTrue(TEXT("valid rider input is valid"), Input.IsValid());
	}

	{
		FSimulationState State;
		State.SpeedMps = 10.0;
		State.DistanceM = 1200.0;
		State.ElapsedTimeS = 120.0;
		TestTrue(TEXT("valid simulation state is valid"), State.IsValid());
	}

	// --- Invalid boundaries ---

	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;

		FString Error;

		Rider.RiderMassKg = 0.0;
		TestFalse(TEXT("zero rider mass is invalid"), Rider.Validate(Error));
		TestTrue(TEXT("zero rider mass error names the field"), Error.Contains(TEXT("rider_mass_kg")));
		Rider.RiderMassKg = 75.0;

		Rider.BikeMassKg = -1.0;
		TestFalse(TEXT("negative bike mass is invalid"), Rider.Validate(Error));
		TestTrue(TEXT("negative bike mass error names the field"), Error.Contains(TEXT("bike_mass_kg")));
		Rider.BikeMassKg = 8.5;

		Rider.CdaM2 = 0.0;
		TestFalse(TEXT("zero drag area is invalid"), Rider.Validate(Error));
		Rider.CdaM2 = 0.32;

		Rider.RollingResistanceCoefficient = -0.001;
		TestFalse(TEXT("negative rolling resistance is invalid"), Rider.Validate(Error));
		TestTrue(TEXT("negative rolling resistance error names the field"), Error.Contains(TEXT("rolling_resistance_coefficient")));
		Rider.RollingResistanceCoefficient = 0.004;

		Rider.DrivetrainEfficiency = 0.0;
		TestFalse(TEXT("zero drivetrain efficiency is invalid"), Rider.Validate(Error));
		Rider.DrivetrainEfficiency = 1.0001;
		TestFalse(TEXT("drivetrain efficiency above one is invalid"), Rider.Validate(Error));
		Rider.DrivetrainEfficiency = 0.97;
	}

	{
		// First error ordering: rider_mass_kg is reported before bike_mass_kg.
		FRiderParameters Rider;
		Rider.RiderMassKg = 0.0;
		Rider.BikeMassKg = -1.0;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		FString Error;
		TestFalse(TEXT("two invalid rider fields are rejected"), Rider.Validate(Error));
		TestTrue(TEXT("first invalid rider field is reported"), Error.Contains(TEXT("rider_mass_kg")));
		TestFalse(TEXT("later invalid field is not reported first"), Error.Contains(TEXT("bike_mass_kg")));
	}

	{
		FEnvironment Environment;
		Environment.GradeDecimal = 0.0;
		Environment.WindSpeedMps = 0.0;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		FString Error;

		Environment.AirDensityKgM3 = 0.0;
		TestFalse(TEXT("zero air density is invalid"), Environment.Validate(Error));
		Environment.AirDensityKgM3 = 1.225;

		Environment.SurfaceWetness = -0.1;
		TestFalse(TEXT("negative surface wetness is invalid"), Environment.Validate(Error));
		Environment.SurfaceWetness = 1.1;
		TestFalse(TEXT("surface wetness above one is invalid"), Environment.Validate(Error));
		Environment.SurfaceWetness = 0.0;

		Environment.RollingResistanceMultiplier = 0.0;
		TestFalse(TEXT("zero rolling resistance multiplier is invalid"), Environment.Validate(Error));
		Environment.RollingResistanceMultiplier = 1.0;

		Environment.GripMultiplier = 0.0;
		TestFalse(TEXT("zero grip multiplier is invalid"), Environment.Validate(Error));
		Environment.GripMultiplier = 1.0001;
		TestFalse(TEXT("grip multiplier above one is invalid"), Environment.Validate(Error));
		Environment.GripMultiplier = 1.0;

		Environment.GradeDecimal = NaNValue;
		TestFalse(TEXT("NaN grade is invalid"), Environment.Validate(Error));
		Environment.GradeDecimal = 0.0;

		Environment.WindSpeedMps = InfinityValue;
		TestFalse(TEXT("infinite wind speed is invalid"), Environment.Validate(Error));
		Environment.WindSpeedMps = 0.0;
	}

	{
		FRiderInput Input;
		Input.PowerW = 250.0;
		Input.CadenceRpm = 90.0;
		FString Error;

		Input.PowerW = -1.0;
		TestFalse(TEXT("negative power is invalid"), Input.Validate(Error));
		TestTrue(TEXT("negative power error names the field"), Error.Contains(TEXT("power_w")));
		Input.PowerW = 250.0;

		Input.CadenceRpm = NaNValue;
		TestFalse(TEXT("NaN cadence is invalid"), Input.Validate(Error));
		Input.CadenceRpm = 90.0;
	}

	{
		FSimulationState State;
		State.SpeedMps = 10.0;
		State.DistanceM = 1200.0;
		State.ElapsedTimeS = 120.0;
		FString Error;

		State.SpeedMps = -0.001;
		TestFalse(TEXT("negative speed is invalid"), State.Validate(Error));
		State.SpeedMps = 10.0;

		State.DistanceM = -1.0;
		TestFalse(TEXT("negative distance is invalid"), State.Validate(Error));
		State.DistanceM = 1200.0;

		State.ElapsedTimeS = InfinityValue;
		TestFalse(TEXT("infinite elapsed time is invalid"), State.Validate(Error));
		State.ElapsedTimeS = 120.0;
	}

	// --- Determinism: repeated validation returns the same result. ---

	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 0.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		FString FirstError;
		FString SecondError;
		const bool FirstResult = Rider.Validate(FirstError);
		const bool SecondResult = Rider.Validate(SecondError);
		TestEqual(TEXT("repeated validation has equal result"), FirstResult, SecondResult);
		TestEqual(TEXT("repeated validation has equal error text"), FirstError, SecondError);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
