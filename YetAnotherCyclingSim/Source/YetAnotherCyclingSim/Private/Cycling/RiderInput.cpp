#include "Cycling/RiderInput.h"

#include "Cycling/PhysicsValidation.h"

bool FRiderInput::IsValid() const
{
	FString Error;
	return Validate(Error);
}

bool FRiderInput::Validate(FString& OutError) const
{
	OutError.Reset();
	using namespace CyclingPhysicsValidation;

	if (!CheckNonNegative(PowerW, TEXT("power_w"), OutError))
	{
		return false;
	}
	if (!CheckNonNegative(CadenceRpm, TEXT("cadence_rpm"), OutError))
	{
		return false;
	}
	return true;
}
