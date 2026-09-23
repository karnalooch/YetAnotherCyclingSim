#pragma once

#include "Containers/UnrealString.h"

// Rider control input for one simulation step.
//
// Both fields are stored as double precision values and must be finite and
// non-negative. A default-constructed record has both fields set to zero,
// which is valid.
struct YETANOTHERCYCLINGSIM_API FRiderInput
{
	// Mechanical power delivered by the rider to the drivetrain in watts (W).
	// Must not be negative; zero is allowed.
	double PowerW = 0.0;

	// Pedalling cadence in revolutions per minute (rpm). Must not be
	// negative; zero is allowed.
	double CadenceRpm = 0.0;

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;
};
