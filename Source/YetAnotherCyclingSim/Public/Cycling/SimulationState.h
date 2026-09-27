#pragma once

#include "Containers/UnrealString.h"

// Simulation output state, in SI units and route-local coordinates.
//
// Speed, route distance and elapsed time are finite and non-negative.
// LateralPositionM is the signed route-local D coordinate and may be
// negative. A default-constructed record has all fields set to zero,
// which is valid.
struct YETANOTHERCYCLINGSIM_API FSimulationState
{
	// Forward ground speed in metres per second (m/s). Must not be negative;
	// zero is allowed.
	double SpeedMps = 0.0;

	// Distance travelled along the route in metres (m). Must not be negative;
	// zero is allowed.
	double DistanceM = 0.0;

	// Elapsed simulation time in seconds (s). Must not be negative; zero is
	// allowed.
	double ElapsedTimeS = 0.0;

	// Signed route-local lateral position D in metres (m). Negative values
	// point toward -D and positive values toward +D. Must be finite.
	double LateralPositionM = 0.0;

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;
};
