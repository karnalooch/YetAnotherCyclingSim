#include "Cycling/CyclingForces.h"

#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingForces
{
	bool TryCalculateRoadAngleRad(double GradeDecimal, double& OutAngleRad, FString& OutError)
	{
		OutAngleRad = 0.0;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckFinite(GradeDecimal, TEXT("grade_decimal"), OutError))
		{
			return false;
		}

		OutAngleRad = std::atan(GradeDecimal);
		return true;
	}

	bool TryCalculateGravitationalForceN(const FRiderParameters& Rider, const FEnvironment& Environment, double& OutForceN, FString& OutError)
	{
		OutForceN = 0.0;
		OutError.Reset();

		if (!Rider.Validate(OutError))
		{
			return false;
		}
		if (!Environment.Validate(OutError))
		{
			return false;
		}

		const double AngleRad = std::atan(Environment.GradeDecimal);
		OutForceN = Rider.GetTotalMassKg() * StandardGravityMps2 * std::sin(AngleRad);
		return true;
	}

	bool TryCalculateRollingResistanceForceN(const FRiderParameters& Rider, const FEnvironment& Environment, double& OutForceN, FString& OutError)
	{
		OutForceN = 0.0;
		OutError.Reset();

		if (!Rider.Validate(OutError))
		{
			return false;
		}
		if (!Environment.Validate(OutError))
		{
			return false;
		}

		const double AngleRad = std::atan(Environment.GradeDecimal);
		const double NormalLoadN = Rider.GetTotalMassKg() * StandardGravityMps2 * std::cos(AngleRad);
		const double EffectiveCrr = Rider.RollingResistanceCoefficient * Environment.RollingResistanceMultiplier;
		OutForceN = EffectiveCrr * NormalLoadN;
		return true;
	}

	bool TryCalculateAerodynamicForceN(const FRiderParameters& Rider, const FEnvironment& Environment, double SpeedMps, double& OutForceN, FString& OutError)
	{
		OutForceN = 0.0;
		OutError.Reset();

		if (!Rider.Validate(OutError))
		{
			return false;
		}
		if (!Environment.Validate(OutError))
		{
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
		{
			return false;
		}

		const double RelativeAirSpeedMps = SpeedMps + Environment.WindSpeedMps;
		OutForceN = 0.5 * Environment.AirDensityKgM3 * Rider.CdaM2 * RelativeAirSpeedMps * std::fabs(RelativeAirSpeedMps);
		return true;
	}

	bool TryCalculateTotalResistanceForceN(const FRiderParameters& Rider, const FEnvironment& Environment, double SpeedMps, double& OutForceN, FString& OutError)
	{
		OutForceN = 0.0;
		OutError.Reset();

		if (!Rider.Validate(OutError))
		{
			return false;
		}
		if (!Environment.Validate(OutError))
		{
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
		{
			return false;
		}

		const double AngleRad = std::atan(Environment.GradeDecimal);
		const double GravitationalN = Rider.GetTotalMassKg() * StandardGravityMps2 * std::sin(AngleRad);

		const double NormalLoadN = Rider.GetTotalMassKg() * StandardGravityMps2 * std::cos(AngleRad);
		const double EffectiveCrr = Rider.RollingResistanceCoefficient * Environment.RollingResistanceMultiplier;
		const double RollingN = EffectiveCrr * NormalLoadN;

		const double RelativeAirSpeedMps = SpeedMps + Environment.WindSpeedMps;
		const double AerodynamicN = 0.5 * Environment.AirDensityKgM3 * Rider.CdaM2 * RelativeAirSpeedMps * std::fabs(RelativeAirSpeedMps);

		OutForceN = GravitationalN + RollingN + AerodynamicN;
		return true;
	}
}
