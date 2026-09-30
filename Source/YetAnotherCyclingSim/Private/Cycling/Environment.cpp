#include "Cycling/Environment.h"

#include "Cycling/PhysicsValidation.h"

bool FEnvironment::IsValid() const
{
	FString Error;
	return Validate(Error);
}

bool FEnvironment::Validate(FString& OutError) const
{
	OutError.Reset();
	using namespace CyclingPhysicsValidation;

	if (!CheckFinite(GradeDecimal, TEXT("grade_decimal"), OutError))
	{
		return false;
	}
	if (!CheckFinite(WindSpeedMps, TEXT("wind_speed_mps"), OutError))
	{
		return false;
	}
	if (!CheckPositive(AirDensityKgM3, TEXT("air_density_kg_m3"), OutError))
	{
		return false;
	}
	if (!CheckClosedUnitInterval(SurfaceWetness, TEXT("surface_wetness"), OutError))
	{
		return false;
	}
	if (!CheckPositive(RollingResistanceMultiplier, TEXT("rolling_resistance_multiplier"), OutError))
	{
		return false;
	}
	if (!CheckOpenUpperUnitInterval(GripMultiplier, TEXT("grip_multiplier"), OutError))
	{
		return false;
	}
	return true;
}
