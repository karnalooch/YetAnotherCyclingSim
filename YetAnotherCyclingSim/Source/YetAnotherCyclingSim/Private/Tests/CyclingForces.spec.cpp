#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include <limits>
#include <cmath>

#include "Cycling/CyclingForces.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"

namespace CyclingForcesTest
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

	FEnvironment MakeEnvironment(double GradeDecimal = 0.0, double WindSpeedMps = 0.0, double AirDensityKgM3 = 1.225)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = WindSpeedMps;
		Environment.AirDensityKgM3 = AirDensityKgM3;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingForcesTest, "CyclingPhysics.Forces",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingForcesTest::RunTest(const FString& Parameters)
{
	using namespace CyclingForces;
	using namespace CyclingForcesTest;

	// --- Constant ---

	{
		ExpectNearlyEqual(*this, StandardGravityMps2, 9.80665);
	}

	// --- Road angle ---

	{
		double AngleRad = 0.0;
		FString Error;
		TestTrue(TEXT("flat road angle succeeds"), TryCalculateRoadAngleRad(0.0, AngleRad, Error));
		ExpectNearlyEqual(*this, AngleRad, 0.0);
	}

	{
		double AngleRad = 0.0;
		FString Error;
		TestTrue(TEXT("climb road angle succeeds"), TryCalculateRoadAngleRad(0.1, AngleRad, Error));
		ExpectNearlyEqual(*this, AngleRad, std::atan(0.1));
	}

	{
		double AngleRad = 0.0;
		FString Error;
		TestTrue(TEXT("descent road angle succeeds"), TryCalculateRoadAngleRad(-0.1, AngleRad, Error));
		ExpectNearlyEqual(*this, AngleRad, std::atan(-0.1));
	}

	// --- Gravitational force ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("gravitational force on flat road succeeds"), TryCalculateGravitationalForceN(Rider, Environment, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 0.0);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.1);
		const double Expected = Rider.GetTotalMassKg() * StandardGravityMps2 * std::sin(std::atan(0.1));
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("gravitational force on climb succeeds"), TryCalculateGravitationalForceN(Rider, Environment, ForceN, Error));
		TestTrue(TEXT("gravitational force resists motion on climb"), ForceN > 0.0);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(-0.1);
		const double Expected = Rider.GetTotalMassKg() * StandardGravityMps2 * std::sin(std::atan(-0.1));
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("gravitational force on descent succeeds"), TryCalculateGravitationalForceN(Rider, Environment, ForceN, Error));
		TestTrue(TEXT("gravitational force assists motion on descent"), ForceN < 0.0);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	// --- Rolling resistance force ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const double Expected = Rider.RollingResistanceCoefficient * Rider.GetTotalMassKg() * StandardGravityMps2;
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("rolling resistance on flat road succeeds"), TryCalculateRollingResistanceForceN(Rider, Environment, ForceN, Error));
		TestTrue(TEXT("rolling resistance is positive on flat road"), ForceN > 0.0);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		for (double Grade : { 0.1, -0.1 })
		{
			const FEnvironment Environment = MakeEnvironment(Grade);
			const double Expected = 0.004 * Rider.GetTotalMassKg() * StandardGravityMps2 * std::cos(std::atan(Grade));
			double ForceN = 0.0;
			FString Error;
			TestTrue(TEXT("rolling resistance on grade succeeds"), TryCalculateRollingResistanceForceN(Rider, Environment, ForceN, Error));
			TestTrue(TEXT("rolling resistance is non-negative on grade"), ForceN >= 0.0);
			ExpectNearlyEqual(*this, ForceN, Expected);
		}
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Base = MakeEnvironment(0.0);
		double BaseForceN = 0.0;
		FString Error;
		TestTrue(TEXT("base rolling resistance succeeds"), TryCalculateRollingResistanceForceN(Rider, Base, BaseForceN, Error));

		FEnvironment Scaled = MakeEnvironment(0.0);
		Scaled.RollingResistanceMultiplier = 1.25;
		double ScaledForceN = 0.0;
		TestTrue(TEXT("scaled rolling resistance succeeds"), TryCalculateRollingResistanceForceN(Rider, Scaled, ScaledForceN, Error));
		ExpectNearlyEqual(*this, ScaledForceN, BaseForceN * 1.25);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		FEnvironment Dry = MakeEnvironment(0.0);
		Dry.SurfaceWetness = 0.0;
		FEnvironment Wet = MakeEnvironment(0.0);
		Wet.SurfaceWetness = 1.0;
		double DryForceN = 0.0;
		double WetForceN = 0.0;
		FString Error;
		TestTrue(TEXT("dry rolling resistance succeeds"), TryCalculateRollingResistanceForceN(Rider, Dry, DryForceN, Error));
		TestTrue(TEXT("wet rolling resistance succeeds"), TryCalculateRollingResistanceForceN(Rider, Wet, WetForceN, Error));
		ExpectNearlyEqual(*this, WetForceN, DryForceN);
	}

	// --- Aerodynamic force ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("aerodynamic force at zero wind succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 19.6);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("aerodynamic force at rest succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 0.0, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 0.0);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0, 5.0);
		const double Expected = 0.5 * 1.225 * 0.32 * (10.0 + 5.0) * (10.0 + 5.0);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("aerodynamic force with headwind succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, ForceN, Error));
		TestTrue(TEXT("headwind increases aerodynamic force"), ForceN > 19.6);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0, -4.0);
		const double Expected = 0.5 * 1.225 * 0.32 * (10.0 - 4.0) * (10.0 - 4.0);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("aerodynamic force with weak tailwind succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, ForceN, Error));
		TestTrue(TEXT("weak tailwind keeps aerodynamic force positive"), ForceN > 0.0);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0, -15.0);
		const double Relative = 10.0 - 15.0;
		const double Expected = 0.5 * 1.225 * 0.32 * Relative * std::fabs(Relative);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("aerodynamic force with strong tailwind succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, ForceN, Error));
		TestTrue(TEXT("strong tailwind makes aerodynamic force negative"), ForceN < 0.0);
		ExpectNearlyEqual(*this, ForceN, Expected);
	}

	// --- Total resistance force ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		double RollingN = 0.0;
		double AeroN = 0.0;
		double TotalN = 0.0;
		FString Error;
		TestTrue(TEXT("rolling component succeeds"), TryCalculateRollingResistanceForceN(Rider, Environment, RollingN, Error));
		TestTrue(TEXT("aerodynamic component succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, AeroN, Error));
		TestTrue(TEXT("total resistance on flat road succeeds"), TryCalculateTotalResistanceForceN(Rider, Environment, 10.0, TotalN, Error));
		TestTrue(TEXT("total resistance is positive on flat road"), TotalN > 0.0);
		ExpectNearlyEqual(*this, TotalN, RollingN + AeroN);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.05);
		double GravN = 0.0;
		double RollingN = 0.0;
		double AeroN = 0.0;
		double TotalN = 0.0;
		FString Error;
		TestTrue(TEXT("gravitational component succeeds"), TryCalculateGravitationalForceN(Rider, Environment, GravN, Error));
		TestTrue(TEXT("rolling component succeeds"), TryCalculateRollingResistanceForceN(Rider, Environment, RollingN, Error));
		TestTrue(TEXT("aerodynamic component succeeds"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, AeroN, Error));
		TestTrue(TEXT("total resistance on grade succeeds"), TryCalculateTotalResistanceForceN(Rider, Environment, 10.0, TotalN, Error));
		ExpectNearlyEqual(*this, TotalN, GravN + RollingN + AeroN);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Flat = MakeEnvironment(0.0);
		const FEnvironment Climb = MakeEnvironment(0.1);
		double FlatN = 0.0;
		double ClimbN = 0.0;
		FString Error;
		TestTrue(TEXT("total resistance on flat road succeeds"), TryCalculateTotalResistanceForceN(Rider, Flat, 10.0, FlatN, Error));
		TestTrue(TEXT("total resistance on climb succeeds"), TryCalculateTotalResistanceForceN(Rider, Climb, 10.0, ClimbN, Error));
		TestTrue(TEXT("climb has greater total resistance than flat road"), ClimbN > FlatN);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Descent = MakeEnvironment(-0.15);
		double ForceN = 0.0;
		FString Error;
		TestTrue(TEXT("total resistance on steep descent succeeds"), TryCalculateTotalResistanceForceN(Rider, Descent, 5.0, ForceN, Error));
		TestTrue(TEXT("steep descent gives negative total resistance"), ForceN < 0.0);
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Calm = MakeEnvironment(0.0, 0.0);
		const FEnvironment Tailwind = MakeEnvironment(0.0, -20.0);
		double CalmN = 0.0;
		double TailwindN = 0.0;
		FString Error;
		TestTrue(TEXT("total resistance in calm wind succeeds"), TryCalculateTotalResistanceForceN(Rider, Calm, 10.0, CalmN, Error));
		TestTrue(TEXT("total resistance with strong tailwind succeeds"), TryCalculateTotalResistanceForceN(Rider, Tailwind, 10.0, TailwindN, Error));
		TestTrue(TEXT("strong tailwind reduces total resistance"), TailwindN < CalmN);
		TestTrue(TEXT("strong tailwind makes total resistance negative"), TailwindN < 0.0);
	}

	// --- Validation: rider, environment and speed ---

	{
		const FRiderParameters InvalidRider;
		const FEnvironment Environment = MakeEnvironment(0.0);
		double ForceN = 123.0;
		FString Error;
		TestFalse(TEXT("invalid rider is rejected"), TryCalculateGravitationalForceN(InvalidRider, Environment, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 0.0);
		TestTrue(TEXT("invalid rider error names rider_mass_kg"), Error.Contains(TEXT("rider_mass_kg")));
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment InvalidEnvironment;
		double ForceN = 123.0;
		FString Error;
		TestFalse(TEXT("invalid environment is rejected"), TryCalculateGravitationalForceN(Rider, InvalidEnvironment, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 0.0);
		TestTrue(TEXT("invalid environment error names air_density_kg_m3"), Error.Contains(TEXT("air_density_kg_m3")));
	}

	{
		const FRiderParameters InvalidRider;
		const FEnvironment InvalidEnvironment;
		double ForceN = 0.0;
		FString Error;
		TestFalse(TEXT("rider and environment are both rejected"), TryCalculateTotalResistanceForceN(InvalidRider, InvalidEnvironment, 10.0, ForceN, Error));
		TestTrue(TEXT("first error is the rider error"), Error.Contains(TEXT("rider_mass_kg")));
		TestFalse(TEXT("environment error is not reported first"), Error.Contains(TEXT("air_density_kg_m3")));
	}

	{
		for (double Grade : { NaNValue, InfinityValue, -InfinityValue })
		{
			double AngleRad = 123.0;
			FString Error;
			TestFalse(TEXT("non-finite grade is rejected"), TryCalculateRoadAngleRad(Grade, AngleRad, Error));
			ExpectNearlyEqual(*this, AngleRad, 0.0);
			TestTrue(TEXT("non-finite grade error names grade_decimal"), Error.Contains(TEXT("grade_decimal")));
		}
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		for (double Speed : { -1.0, NaNValue, InfinityValue, -InfinityValue })
		{
			double ForceN = 123.0;
			FString Error;
			TestFalse(TEXT("invalid speed is rejected by aerodynamic force"), TryCalculateAerodynamicForceN(Rider, Environment, Speed, ForceN, Error));
			ExpectNearlyEqual(*this, ForceN, 0.0);
			TestTrue(TEXT("invalid speed error names speed_mps"), Error.Contains(TEXT("speed_mps")));
		}
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		for (double Speed : { -1.0, NaNValue, InfinityValue, -InfinityValue })
		{
			double ForceN = 123.0;
			FString Error;
			TestFalse(TEXT("invalid speed is rejected by total resistance"), TryCalculateTotalResistanceForceN(Rider, Environment, Speed, ForceN, Error));
			ExpectNearlyEqual(*this, ForceN, 0.0);
			TestTrue(TEXT("invalid speed error names speed_mps"), Error.Contains(TEXT("speed_mps")));
		}
	}

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		double ForceN = 123.0;
		FString Error;
		TestFalse(TEXT("valid inputs with invalid speed still reject speed"), TryCalculateAerodynamicForceN(Rider, Environment, -1.0, ForceN, Error));
		ExpectNearlyEqual(*this, ForceN, 0.0);
		TestTrue(TEXT("speed error is reported last"), Error.Contains(TEXT("speed_mps")));
	}

	// --- Repeatability ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.05);
		double First = 0.0;
		double Second = 0.0;
		FString Error;
		TestTrue(TEXT("first total resistance calculation succeeds"), TryCalculateTotalResistanceForceN(Rider, Environment, 10.0, First, Error));
		TestTrue(TEXT("second total resistance calculation succeeds"), TryCalculateTotalResistanceForceN(Rider, Environment, 10.0, Second, Error));
		ExpectNearlyEqual(*this, First, Second);
	}

	// --- Successful calls clear a pre-populated error ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FString StaleError = TEXT("stale error");

		double AngleRad = 0.0;
		FString AngleError = StaleError;
		TestTrue(TEXT("road angle success clears a pre-populated error"), TryCalculateRoadAngleRad(0.0, AngleRad, AngleError));
		TestTrue(TEXT("road angle error is empty on success"), AngleError.IsEmpty());

		double GravN = 0.0;
		FString GravError = StaleError;
		TestTrue(TEXT("gravitational force success clears a pre-populated error"), TryCalculateGravitationalForceN(Rider, Environment, GravN, GravError));
		TestTrue(TEXT("gravitational force error is empty on success"), GravError.IsEmpty());

		double RollingN = 0.0;
		FString RollingError = StaleError;
		TestTrue(TEXT("rolling resistance success clears a pre-populated error"), TryCalculateRollingResistanceForceN(Rider, Environment, RollingN, RollingError));
		TestTrue(TEXT("rolling resistance error is empty on success"), RollingError.IsEmpty());

		double AeroN = 0.0;
		FString AeroError = StaleError;
		TestTrue(TEXT("aerodynamic force success clears a pre-populated error"), TryCalculateAerodynamicForceN(Rider, Environment, 10.0, AeroN, AeroError));
		TestTrue(TEXT("aerodynamic force error is empty on success"), AeroError.IsEmpty());

		double TotalN = 0.0;
		FString TotalError = StaleError;
		TestTrue(TEXT("total resistance success clears a pre-populated error"), TryCalculateTotalResistanceForceN(Rider, Environment, 10.0, TotalN, TotalError));
		TestTrue(TEXT("total resistance error is empty on success"), TotalError.IsEmpty());
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
