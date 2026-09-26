#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/RiderParameters.h"
#include "Cycling/SharedGripBudget.h"

namespace CyclingBraking
{
	// Deterministic no-slip braking-force result.
	//
	// The requested shared budget remains visible even if the physically
	// applied longitudinal usage must be capped by lateral grip demand.
	struct YETANOTHERCYCLINGSIM_API FBrakingForceDemand
	{
		double BrakeRatioRequested = 0.0;
		double LateralUsage = 0.0;
		CyclingGripBudget::FSharedGripBudget RequestedBudget;
		double AppliedLongitudinalUsage = 0.0;
		bool bSaturatedBySharedBudget = false;
		double EffectiveFrictionCoefficient = 0.0;
		double StaticNormalLoadN = 0.0;
		double StandaloneLongitudinalForceCapacityN = 0.0;
		double AppliedBrakeForceN = 0.0;
		double AppliedBrakeAccelerationMps2 = 0.0;
	};

	// Resolves tyre-limited braking force without a hardware-specific maximum
	// brake-force constant.
	//
	// Static gravity-normal load is:
	//   m * g * cos(longitudinal road angle) * cos(cross slope)
	//
	// Standalone longitudinal force capacity is mu_effective * normal load.
	// The shared Stage 4C-A budget then caps the no-slip applied usage by the
	// capacity remaining after lateral demand.
	//
	// Dynamic load transfer, brake bias, ABS, wheel lock and tyre relaxation
	// remain outside this MVP resolver.
	YETANOTHERCYCLINGSIM_API bool TryCalculateBrakingForceDemand(
		const FRiderParameters& Rider,
		double GradeDecimal,
		double CrossSlopeAngleRad,
		double EffectiveFrictionCoefficient,
		double BrakeRatio,
		double LateralUsage,
		FBrakingForceDemand& OutDemand,
		FString& OutError);
}
