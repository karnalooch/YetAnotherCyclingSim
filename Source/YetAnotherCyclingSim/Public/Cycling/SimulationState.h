#pragma once

#include "Containers/UnrealString.h"

// Simulation output state, in SI units.
//
// All fields are stored as double precision values and must be finite and
// non-negative. A default-constructed record has all fields set to zero,
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

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;
};
