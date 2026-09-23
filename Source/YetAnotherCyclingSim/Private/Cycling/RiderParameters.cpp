#include "Cycling/RiderParameters.h"

#include "Cycling/PhysicsValidation.h"

bool FRiderParameters::IsValid() const
{
	FString Error;
	return Validate(Error);
}

bool FRiderParameters::Validate(FString& OutError) const
{
	OutError.Reset();
	using namespace CyclingPhysicsValidation;

	if (!CheckPositive(RiderMassKg, TEXT("rider_mass_kg"), OutError))
	{
		return false;
	}
	if (!CheckPositive(BikeMassKg, TEXT("bike_mass_kg"), OutError))
	{
		return false;
	}
	if (!CheckPositive(CdaM2, TEXT("cda_m2"), OutError))
	{
		return false;
	}
	if (!CheckNonNegative(RollingResistanceCoefficient, TEXT("rolling_resistance_coefficient"), OutError))
	{
		return false;
	}
	if (!CheckOpenUpperUnitInterval(DrivetrainEfficiency, TEXT("drivetrain_efficiency"), OutError))
	{
		return false;
	}
	return true;
}
