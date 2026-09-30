#pragma once

#include "Containers/UnrealString.h"

// Environmental conditions along the route, in SI units.
//
// All fields are stored as double precision values and must be finite.
// Grade and wind may be negative; air density must be greater than zero.
// SurfaceWetness lies in [0, 1], RollingResistanceMultiplier must be greater
// than zero and GripMultiplier lies in (0, 1]. The default values for the
// optional fields match the Python reference. A default-constructed record
// has zeroed required fields (GradeDecimal, WindSpeedMps, AirDensityKgM3) and
// is intentionally invalid until those fields are set explicitly.
struct YETANOTHERCYCLINGSIM_API FEnvironment
{
	// Road grade as a decimal fraction of the slope (unitless), e.g. 0.08
	// means 8 %. Positive values are ascents; negative values are descents.
	// Must be finite.
	double GradeDecimal = 0.0;

	// Wind speed in metres per second (m/s) relative to the ground along the
	// direction of travel. Positive values are headwinds (oppose motion);
	// negative values are tailwinds (assist motion). Must be finite.
	double WindSpeedMps = 0.0;

	// Air density in kilograms per cubic metre (kg/m^3). Must be greater
	// than zero.
	double AirDensityKgM3 = 0.0;

	// Road wetness (unitless): 0.0 is a completely dry road, 1.0 a completely
	// wet road. Must be in the interval [0, 1].
	double SurfaceWetness = 0.0;

	// Dimensionless multiplier applied to the base rolling resistance
	// coefficient Crr. Must be greater than zero.
	double RollingResistanceMultiplier = 1.0;

	// Dimensionless grip multiplier (unitless): 1.0 is base grip, smaller
	// values mean limited grip. Must be in the interval (0, 1].
	double GripMultiplier = 1.0;

	// Returns true when all fields satisfy the validation rules.
	bool IsValid() const;

	// Validates every field in declaration order and returns the first error
	// in OutError. On success OutError is cleared and true is returned.
	bool Validate(FString& OutError) const;
};
