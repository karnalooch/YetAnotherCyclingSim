#include "Cycling/SharedGripBudget.h"

#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingGripBudget
{
	bool TryCalculateSharedGripBudget(
		double LongitudinalUsage,
		double LateralUsage,
		FSharedGripBudget& OutBudget,
		FString& OutError)
	{
		OutBudget = FSharedGripBudget{};
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(
			LongitudinalUsage,
			TEXT("longitudinal_usage"),
			OutError))
		{
			return false;
		}
		if (!CheckNonNegative(
			LateralUsage,
			TEXT("lateral_usage"),
			OutError))
		{
			return false;
		}

		const double CombinedUsage = std::hypot(LongitudinalUsage, LateralUsage);
		const double RemainingLongitudinalCapacity =
			std::sqrt(std::fmax(0.0, 1.0 - LateralUsage * LateralUsage));
		const double RemainingLateralCapacity =
			std::sqrt(std::fmax(0.0, 1.0 - LongitudinalUsage * LongitudinalUsage));

		if (!std::isfinite(CombinedUsage)
			|| !std::isfinite(RemainingLongitudinalCapacity)
			|| !std::isfinite(RemainingLateralCapacity))
		{
			OutError = TEXT("derived shared grip budget values must be finite");
			return false;
		}

		OutBudget.LongitudinalUsage = LongitudinalUsage;
		OutBudget.LateralUsage = LateralUsage;
		OutBudget.CombinedUsage = CombinedUsage;
		OutBudget.RemainingLongitudinalCapacity = RemainingLongitudinalCapacity;
		OutBudget.RemainingLateralCapacity = RemainingLateralCapacity;
		OutBudget.bExceeded = CombinedUsage > 1.0;
		return true;
	}
}
