#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"

// Deterministic cycling resistance force calculations, ported from the Python
// reference model (physics_reference/src/cycling_physics/model.py).
//
// Every function follows the TryCalculate convention: it resets the output to
// 0.0, validates the inputs in a fixed order, returns false with the first
// validation error in OutError on failure, and writes the result only on
// success. No exceptions are thrown.
namespace CyclingForces
{
	// Standard gravitational acceleration on Earth in metres per second squared
	// (m/s^2).
	inline constexpr double StandardGravityMps2 = 9.80665;

	// Converts a road grade (decimal slope, unitless) to the road angle in
	// radians. Rejects a non-finite grade. Positive angles are ascents,
	// negative angles are descents.
	YETANOTHERCYCLINGSIM_API bool TryCalculateRoadAngleRad(
		double GradeDecimal,
		double& OutAngleRad,
		FString& OutError);

	// Gravitational force component along the road in newtons (N). A positive
	// value opposes motion on an ascent, a negative value assists on a descent
	// and the value is zero on a flat road.
	YETANOTHERCYCLINGSIM_API bool TryCalculateGravitationalForceN(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		double& OutForceN,
		FString& OutError);

	// Rolling resistance force in newtons (N), always non-negative. Uses the
	// effective coefficient Crr multiplied by the environment rolling
	// resistance multiplier and the component of weight perpendicular to the
	// road.
	YETANOTHERCYCLINGSIM_API bool TryCalculateRollingResistanceForceN(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		double& OutForceN,
		FString& OutError);

	// Aerodynamic drag force in newtons (N). SpeedMps must be finite and
	// non-negative. A positive result opposes motion; a strong tailwind can
	// produce a negative result that pushes the rider forward.
	YETANOTHERCYCLINGSIM_API bool TryCalculateAerodynamicForceN(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		double SpeedMps,
		double& OutForceN,
		FString& OutError);

	// Total resistive force along the road in newtons (N): the sum of the
	// gravitational, rolling resistance and aerodynamic drag forces. SpeedMps
	// must be finite and non-negative. A positive value opposes motion; a
	// negative value propels the rider forward on a steep descent or with a
	// strong tailwind.
	YETANOTHERCYCLINGSIM_API bool TryCalculateTotalResistanceForceN(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		double SpeedMps,
		double& OutForceN,
		FString& OutError);
}
