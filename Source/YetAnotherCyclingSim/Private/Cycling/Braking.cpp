#include "Cycling/Braking.h"

#include "Cycling/CyclingForces.h"
#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingBraking
{
	bool TryCalculateBrakingForceDemand(
		const FRiderParameters& Rider,
		double GradeDecimal,
		double CrossSlopeAngleRad,
		double EffectiveFrictionCoefficient,
		double BrakeRatio,
		double LateralUsage,
		FBrakingForceDemand& OutDemand,
		FString& OutError)
	{
		OutDemand = FBrakingForceDemand{};
		OutError.Reset();

		if (!Rider.Validate(OutError))
		{
			return false;
		}

		double RoadAngleRad = 0.0;
		if (!CyclingForces::TryCalculateRoadAngleRad(
			GradeDecimal,
			RoadAngleRad,
			OutError))
		{
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckFinite(
			CrossSlopeAngleRad,
			TEXT("cross_slope_angle_rad"),
			OutError))
		{
			return false;
		}

		const double HalfPi = 0.5 * std::acos(-1.0);
		if (CrossSlopeAngleRad <= -HalfPi || CrossSlopeAngleRad >= HalfPi)
		{
			OutError = TEXT("cross_slope_angle_rad must lie strictly inside (-pi/2, pi/2)");
			return false;
		}

		if (!CheckPositive(
			EffectiveFrictionCoefficient,
			TEXT("effective_friction_coefficient"),
			OutError))
		{
			return false;
		}
		if (!CheckClosedUnitInterval(
			BrakeRatio,
			TEXT("brake_ratio"),
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

		CyclingGripBudget::FSharedGripBudget RequestedBudget;
		if (!CyclingGripBudget::TryCalculateSharedGripBudget(
			BrakeRatio,
			LateralUsage,
			RequestedBudget,
			OutError))
		{
			return false;
		}

		const double AppliedLongitudinalUsage =
			FMath::Min(
				BrakeRatio,
				RequestedBudget.RemainingLongitudinalCapacity);

		const double TotalMassKg = Rider.GetTotalMassKg();
		if (!std::isfinite(TotalMassKg) || TotalMassKg <= 0.0)
		{
			OutError = TEXT("rider total mass must be finite and positive");
			return false;
		}

		const double StaticNormalLoadN =
			TotalMassKg
			* CyclingForces::StandardGravityMps2
			* std::cos(RoadAngleRad)
			* std::cos(CrossSlopeAngleRad);
		if (!std::isfinite(StaticNormalLoadN) || StaticNormalLoadN <= 0.0)
		{
			OutError = TEXT("derived static normal load must be finite and positive");
			return false;
		}

		const double StandaloneLongitudinalForceCapacityN =
			EffectiveFrictionCoefficient * StaticNormalLoadN;
		if (!std::isfinite(StandaloneLongitudinalForceCapacityN)
			|| StandaloneLongitudinalForceCapacityN <= 0.0)
		{
			OutError = TEXT("derived standalone longitudinal force capacity must be finite and positive");
			return false;
		}

		const double AppliedBrakeForceN =
			AppliedLongitudinalUsage * StandaloneLongitudinalForceCapacityN;
		const double AppliedBrakeAccelerationMps2 =
			AppliedBrakeForceN / TotalMassKg;
		if (!std::isfinite(AppliedBrakeForceN)
			|| !std::isfinite(AppliedBrakeAccelerationMps2)
			|| AppliedBrakeForceN < 0.0
			|| AppliedBrakeAccelerationMps2 < 0.0)
		{
			OutError = TEXT("derived braking force and acceleration must be finite and non-negative");
			return false;
		}

		OutDemand.BrakeRatioRequested = BrakeRatio;
		OutDemand.LateralUsage = LateralUsage;
		OutDemand.RequestedBudget = RequestedBudget;
		OutDemand.AppliedLongitudinalUsage = AppliedLongitudinalUsage;
		OutDemand.bSaturatedBySharedBudget = AppliedLongitudinalUsage < BrakeRatio;
		OutDemand.EffectiveFrictionCoefficient = EffectiveFrictionCoefficient;
		OutDemand.StaticNormalLoadN = StaticNormalLoadN;
		OutDemand.StandaloneLongitudinalForceCapacityN =
			StandaloneLongitudinalForceCapacityN;
		OutDemand.AppliedBrakeForceN = AppliedBrakeForceN;
		OutDemand.AppliedBrakeAccelerationMps2 = AppliedBrakeAccelerationMps2;
		return true;
	}
}
