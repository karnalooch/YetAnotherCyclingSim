#pragma once

#include "Containers/UnrealString.h"

// Rider control input for one simulation step.
//
// Power/cadence are stored as non-negative double precision values.
// BrakeRatio is a normalized braking command in [0, 1]. A default-constructed
// record has every field set to zero, which is valid. Stage 4C-B1 establishes
// the control contract; fixed-step braking force is integrated separately.
struct YETANOTHERCYCLINGSIM_API FRiderInput
{
	// Mechanical power delivered by the rider to the drivetrain in watts (W).
	// Must not be negative; zero is allowed.
	double PowerW = 0.0;

	// Pedalling cadence in revolutions per minute (rpm). Must not be
	// negative; zero is allowed.
	double CadenceRpm = 0.0;

	// Normalized braking command. 0.0 means released, 1.0 means full
	// requested braking. Stage 4C-B1 does not yet apply this command to the
	// fixed-step equation of motion.
	double BrakeRatio = 0.0;

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;
};
