#include "Cycling/SimulationState.h"

#include "Cycling/PhysicsValidation.h"

bool FSimulationState::IsValid() const
{
	FString Error;
	return Validate(Error);
}

bool FSimulationState::Validate(FString& OutError) const
{
	OutError.Reset();
	using namespace CyclingPhysicsValidation;

	if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
	{
		return false;
	}
	if (!CheckNonNegative(DistanceM, TEXT("distance_m"), OutError))
	{
		return false;
	}
	if (!CheckNonNegative(ElapsedTimeS, TEXT("elapsed_time_s"), OutError))
	{
		return false;
	}
	return true;
}
