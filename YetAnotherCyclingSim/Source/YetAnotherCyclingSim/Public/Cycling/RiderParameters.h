#pragma once

#include "Containers/UnrealString.h"

// Rider and bicycle parameters used by the cycling physics model.
//
// All fields are stored as double precision values in SI units and must be
// finite. Masses, drag area and efficiency bounds are validated by
// Validate(). A default-constructed record has zeroed required fields and is
// intentionally invalid until the fields are set explicitly.
struct YETANOTHERCYCLINGSIM_API FRiderParameters
{
	// Total mass of the rider in kilograms (kg). Must be greater than zero.
	double RiderMassKg = 0.0;

	// Total mass of the bicycle in kilograms (kg). Must be greater than zero.
	double BikeMassKg = 0.0;

	// Aerodynamic drag area (CdA, C_d times frontal area A) in square metres
	// (m^2). Must be greater than zero.
	double CdaM2 = 0.0;

	// Dimensionless rolling resistance coefficient (Crr). Must not be
	// negative; zero is allowed.
	double RollingResistanceCoefficient = 0.0;

	// Dimensionless drivetrain efficiency fraction. Must be in the interval
	// (0, 1].
	double DrivetrainEfficiency = 0.0;

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;

	// Combined mass of the rider and the bicycle in kilograms (kg).
	double GetTotalMassKg() const
	{
		return RiderMassKg + BikeMassKg;
	}
};
