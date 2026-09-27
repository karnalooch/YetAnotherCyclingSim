#include "Cycling/CornerLateralLimit.h"

#include "Cycling/Cornering.h"
#include "Cycling/CyclingForces.h"

#include <cmath>

namespace CyclingCornerLimit
{
	bool TryCalculateCornerLateralLimit(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingSurfaceGrip::FSurfaceGripPolicy& GripPolicy,
		double BaseFrictionCoefficient,
		FCornerLateralLimit& OutLimit,
		FString& OutError)
	{
		OutLimit = FCornerLateralLimit{};
		OutError.Reset();

		if (!Context.bHasCorner)
		{
			OutError = TEXT("corner lateral limit requires a context with a corner");
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

		CyclingSurfaceGrip::FResolvedSurfaceGrip SurfaceGrip;
		if (!GripPolicy.TryResolve(
			Context.SurfaceId,
			Context.Wetness,
			SurfaceGrip,
			OutError))
		{
			return false;
		}

		double EffectiveFriction = 0.0;
		if (!CyclingCornering::TryCalculateEffectiveFrictionCoefficient(
			BaseFrictionCoefficient,
			SurfaceGrip.GripMultiplier,
			EffectiveFriction,
			OutError))
		{
			return false;
		}

		const double TurnSign = Context.SignedCurvaturePerM > 0.0 ? 1.0 : -1.0;
		const double SupportAngleRad = -TurnSign * Context.CrossSlopeAngleRad;
		const double SinBank = std::sin(SupportAngleRad);
		const double CosBank = std::cos(SupportAngleRad);
		const double Numerator = SinBank + EffectiveFriction * CosBank;
		const double Denominator = CosBank - EffectiveFriction * SinBank;

		if (!std::isfinite(Numerator)
			|| !std::isfinite(Denominator)
			|| Numerator <= 0.0
			|| Denominator <= 0.0)
		{
			OutError = TEXT("bank/friction combination is outside the supported pure-lateral model");
			return false;
		}

		const double LateralAccelerationLimitMps2 =
			CyclingForces::StandardGravityMps2 * Numerator / Denominator;
		if (!std::isfinite(LateralAccelerationLimitMps2)
			|| LateralAccelerationLimitMps2 <= 0.0)
		{
			OutError = TEXT("derived lateral acceleration limit must be finite and positive");
			return false;
		}

		const double MaximumSpeedMps =
			std::sqrt(LateralAccelerationLimitMps2 * Context.EffectiveRadiusM);
		if (!std::isfinite(MaximumSpeedMps))
		{
			OutError = TEXT("derived maximum corner speed must be finite");
			return false;
		}

		OutLimit.SurfaceId = SurfaceGrip.SurfaceId;
		OutLimit.Wetness = SurfaceGrip.Wetness;
		OutLimit.GripMultiplier = SurfaceGrip.GripMultiplier;
		OutLimit.EffectiveFrictionCoefficient = EffectiveFriction;
		OutLimit.BankSupportAngleRad = SupportAngleRad;
		OutLimit.LateralAccelerationLimitMps2 = LateralAccelerationLimitMps2;
		OutLimit.MaximumSpeedMps = MaximumSpeedMps;
		return true;
	}
}
