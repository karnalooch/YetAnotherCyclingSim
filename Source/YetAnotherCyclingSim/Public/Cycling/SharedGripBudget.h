#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

namespace CyclingGripBudget
{
	// Shared unit friction-circle result for normalized longitudinal and
	// lateral tyre-force usage.
	//
	// This is stateless and contains no tyre coefficient, braking-control
	// mapping, safety factor or consequence policy. It can be evaluated for
	// the simplified whole-bike MVP model or independently per tyre/axle in
	// a future split model.
	struct YETANOTHERCYCLINGSIM_API FSharedGripBudget
	{
		double LongitudinalUsage = 0.0;
		double LateralUsage = 0.0;
		double CombinedUsage = 0.0;
		double RemainingLongitudinalCapacity = 0.0;
		double RemainingLateralCapacity = 0.0;
		bool bExceeded = false;
	};

	// Resolves the MVP unit friction circle:
	//
	//   combined = sqrt(longitudinal^2 + lateral^2)
	//
	// Inputs are non-negative normalized usage fractions and are deliberately
	// not clamped. A combined result > 1 means the shared grip budget is
	// exceeded even when each axis demand is individually <= 1.
	YETANOTHERCYCLINGSIM_API bool TryCalculateSharedGripBudget(
		double LongitudinalUsage,
		double LateralUsage,
		FSharedGripBudget& OutBudget,
		FString& OutError);
}
