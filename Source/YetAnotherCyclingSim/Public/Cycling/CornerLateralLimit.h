#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerContext.h"
#include "Cycling/SurfaceGripPolicy.h"

namespace CyclingCornerLimit
{
	// Pure-lateral physical limit for one route-derived corner context.
	//
	// No recommended-speed safety factor and no longitudinal braking demand is
	// applied here. Stage 4C later combines longitudinal/lateral grip.
	struct YETANOTHERCYCLINGSIM_API FCornerLateralLimit
	{
		FString SurfaceId;
		double Wetness = 0.0;
		double GripMultiplier = 0.0;
		double EffectiveFrictionCoefficient = 0.0;
		double BankSupportAngleRad = 0.0;
		double LateralAccelerationLimitMps2 = 0.0;
		double MaximumSpeedMps = 0.0;
	};

	// Calculates the pure-lateral cornering limit from:
	// - Stage 4B-A CornerContext;
	// - Stage 4B-B SurfaceGripPolicy;
	// - caller-owned base tyre friction coefficient.
	//
	// Route sign convention:
	// positive curvature turns toward +D (right), while positive cross-slope
	// rises toward +D. A supportive bank therefore has opposite signs for
	// curvature and cross-slope:
	//   support_angle = -sign(curvature) * cross_slope.
	YETANOTHERCYCLINGSIM_API bool TryCalculateCornerLateralLimit(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingSurfaceGrip::FSurfaceGripPolicy& GripPolicy,
		double BaseFrictionCoefficient,
		FCornerLateralLimit& OutLimit,
		FString& OutError);
}
