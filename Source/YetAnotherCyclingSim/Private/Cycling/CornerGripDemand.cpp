#include "Cycling/CornerGripDemand.h"

#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingCornerGrip
{
	bool TryCalculateCornerGripDemand(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerLimit::FCornerLateralLimit& LateralLimit,
		double SpeedMps,
		double BrakeRatio,
		FCornerGripDemand& OutDemand,
		FString& OutError)
	{
		OutDemand = FCornerGripDemand{};
		OutError.Reset();

		if (!Context.bHasCorner)
		{
			OutError = TEXT("corner grip demand requires a context with a corner");
			return false;
		}
		if (!std::isfinite(Context.EffectiveRadiusM) || Context.EffectiveRadiusM <= 0.0)
		{
			OutError = TEXT("corner context effective radius must be finite and greater than zero");
			return false;
		}
		if (!std::isfinite(Context.SignedCurvaturePerM) || Context.SignedCurvaturePerM == 0.0)
		{
			OutError = TEXT("corner context signed curvature must be finite and non-zero");
			return false;
		}
		if (!std::isfinite(Context.CrossSlopeAngleRad))
		{
			OutError = TEXT("corner context cross-slope angle must be finite");
			return false;
		}
		if (!std::isfinite(LateralLimit.LateralAccelerationLimitMps2)
			|| LateralLimit.LateralAccelerationLimitMps2 <= 0.0)
		{
			OutError = TEXT("lateral acceleration limit must be finite and positive");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
		{
			return false;
		}
		if (!CheckClosedUnitInterval(BrakeRatio, TEXT("brake_ratio"), OutError))
		{
			return false;
		}

		if (LateralLimit.SurfaceId != Context.SurfaceId)
		{
			OutError = TEXT("lateral limit surface id does not match corner context");
			return false;
		}
		if (LateralLimit.Wetness != Context.Wetness)
		{
			OutError = TEXT("lateral limit wetness does not match corner context");
			return false;
		}

		const double TurnSign = Context.SignedCurvaturePerM > 0.0 ? 1.0 : -1.0;
		const double ExpectedSupportAngleRad = -TurnSign * Context.CrossSlopeAngleRad;
		if (std::abs(LateralLimit.BankSupportAngleRad - ExpectedSupportAngleRad) > 1e-12)
		{
			OutError = TEXT("lateral limit bank support angle does not match corner context");
			return false;
		}

		const double LateralAccelerationDemandMps2 =
			SpeedMps * SpeedMps / Context.EffectiveRadiusM;
		if (!std::isfinite(LateralAccelerationDemandMps2)
			|| LateralAccelerationDemandMps2 < 0.0)
		{
			OutError = TEXT("derived lateral acceleration demand must be finite and non-negative");
			return false;
		}

		const double LateralUsage =
			LateralAccelerationDemandMps2 / LateralLimit.LateralAccelerationLimitMps2;
		if (!std::isfinite(LateralUsage) || LateralUsage < 0.0)
		{
			OutError = TEXT("derived lateral usage must be finite and non-negative");
			return false;
		}

		CyclingGripBudget::FSharedGripBudget Budget;
		if (!CyclingGripBudget::TryCalculateSharedGripBudget(
			BrakeRatio,
			LateralUsage,
			Budget,
			OutError))
		{
			return false;
		}

		OutDemand.SpeedMps = SpeedMps;
		OutDemand.LateralAccelerationDemandMps2 = LateralAccelerationDemandMps2;
		OutDemand.LongitudinalUsage = BrakeRatio;
		OutDemand.LateralUsage = LateralUsage;
		OutDemand.Budget = Budget;
		return true;
	}
}
