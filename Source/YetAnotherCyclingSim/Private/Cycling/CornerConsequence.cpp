#include "Cycling/CornerConsequence.h"

#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingCornerConsequence
{
	bool TryResolveCornerGeometryConsequence(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerGrip::FCornerGripDemand& Demand,
		FCornerGeometryConsequence& OutConsequence,
		FString& OutError)
	{
		OutConsequence = FCornerGeometryConsequence{};
		OutError.Reset();

		if (!Context.bHasCorner)
		{
			OutError = TEXT("corner geometry consequence requires an active corner");
			return false;
		}
		if (Context.Phase != CyclingCornering::ECornerPhase::Entry
			&& Context.Phase != CyclingCornering::ECornerPhase::Apex
			&& Context.Phase != CyclingCornering::ECornerPhase::Exit)
		{
			OutError = TEXT("corner geometry consequence requires entry, apex or exit phase");
			return false;
		}
		if (!std::isfinite(Context.EffectiveRadiusM) || Context.EffectiveRadiusM <= 0.0)
		{
			OutError = TEXT("context effective radius must be finite and positive");
			return false;
		}
		if (!std::isfinite(Context.LateralPositionM))
		{
			OutError = TEXT("context lateral position must be finite");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(Demand.SpeedMps, TEXT("speed_mps"), OutError)
			|| !CheckNonNegative(Demand.LateralUsage, TEXT("lateral_usage"), OutError))
		{
			return false;
		}

		double OutsideMarginM = 0.0;
		double DirectionSign = 0.0;
		switch (Context.Direction)
		{
		case CyclingCornerContext::ECornerDirection::Right:
			if (!CheckNonNegative(Context.LeftMarginM, TEXT("left_margin_m"), OutError))
			{
				return false;
			}
			OutsideMarginM = Context.LeftMarginM;
			DirectionSign = -1.0;
			break;
		case CyclingCornerContext::ECornerDirection::Left:
			if (!CheckNonNegative(Context.RightMarginM, TEXT("right_margin_m"), OutError))
			{
				return false;
			}
			OutsideMarginM = Context.RightMarginM;
			DirectionSign = 1.0;
			break;
		default:
			OutError = TEXT("active corner must have left or right direction");
			return false;
		}

		const double RadiusM = Context.EffectiveRadiusM;
		const double MinimumRequiredRadiusM = RadiusM * Demand.LateralUsage;
		if (!std::isfinite(MinimumRequiredRadiusM) || MinimumRequiredRadiusM < 0.0)
		{
			OutError = TEXT("derived minimum required radius must be finite and non-negative");
			return false;
		}

		const double RequiredOutwardShiftM =
			std::fmax(0.0, MinimumRequiredRadiusM - RadiusM);
		const double MaximumFeasibleRadiusM = RadiusM + OutsideMarginM;
		if (!std::isfinite(MaximumFeasibleRadiusM) || MaximumFeasibleRadiusM <= 0.0)
		{
			OutError = TEXT("derived maximum feasible radius must be finite and positive");
			return false;
		}

		OutConsequence.MinimumRequiredRadiusM = MinimumRequiredRadiusM;
		OutConsequence.MaximumFeasibleRadiusM = MaximumFeasibleRadiusM;

		if (RequiredOutwardShiftM <= 0.0)
		{
			OutConsequence.Outcome = ECornerGeometryOutcome::Clean;
			OutConsequence.TargetLateralPositionM = Context.LateralPositionM;
			OutConsequence.TargetSpeedMps = Demand.SpeedMps;
			OutConsequence.ExitSpeedMultiplier = 1.0;
			return true;
		}

		const double AppliedOutwardShiftM =
			std::fmin(RequiredOutwardShiftM, OutsideMarginM);
		const double TargetLateralPositionM =
			Context.LateralPositionM + DirectionSign * AppliedOutwardShiftM;
		const double LineDeviationRatio =
			OutsideMarginM > 0.0
				? AppliedOutwardShiftM / OutsideMarginM
				: 0.0;

		OutConsequence.RequiredOutwardShiftM = RequiredOutwardShiftM;
		OutConsequence.AppliedOutwardShiftM = AppliedOutwardShiftM;
		OutConsequence.LineDeviationRatio = LineDeviationRatio;
		OutConsequence.TargetLateralPositionM = TargetLateralPositionM;

		if (RequiredOutwardShiftM <= OutsideMarginM)
		{
			OutConsequence.Outcome = ECornerGeometryOutcome::WideLine;
			OutConsequence.TargetSpeedMps = Demand.SpeedMps;
			OutConsequence.ExitSpeedMultiplier = 1.0;
			return true;
		}

		if (MinimumRequiredRadiusM <= 0.0)
		{
			OutError = TEXT("minimum required radius must be positive during slip");
			return false;
		}

		const double ExitSpeedMultiplier =
			std::sqrt(MaximumFeasibleRadiusM / MinimumRequiredRadiusM);
		if (!std::isfinite(ExitSpeedMultiplier)
			|| ExitSpeedMultiplier < 0.0
			|| ExitSpeedMultiplier > 1.0)
		{
			OutError = TEXT("derived exit speed multiplier must lie in [0, 1]");
			return false;
		}

		OutConsequence.Outcome = ECornerGeometryOutcome::ControlledSlip;
		OutConsequence.ExitSpeedMultiplier = ExitSpeedMultiplier;
		OutConsequence.TargetSpeedMps = Demand.SpeedMps * ExitSpeedMultiplier;
		return true;
	}
}
