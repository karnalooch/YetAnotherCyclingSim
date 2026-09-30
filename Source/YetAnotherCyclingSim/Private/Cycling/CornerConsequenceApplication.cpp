#include "Cycling/CornerConsequenceApplication.h"

#include "Cycling/PhysicsValidation.h"

#include <algorithm>
#include <cmath>

namespace CyclingCornerApplication
{
	bool TryApplyCornerGeometryConsequence(
		const FSimulationState& PreStepState,
		const FSimulationState& IntegratedState,
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerConsequence::FCornerGeometryConsequence& Consequence,
		FCornerConsequenceApplication& OutApplication,
		FString& OutError)
	{
		OutApplication = FCornerConsequenceApplication{};
		OutError.Reset();

		FString ValidationError;
		if (!PreStepState.Validate(ValidationError))
		{
			OutError = FString::Printf(
				TEXT("pre-step state is invalid: %s"),
				*ValidationError);
			return false;
		}
		if (!IntegratedState.Validate(ValidationError))
		{
			OutError = FString::Printf(
				TEXT("integrated state is invalid: %s"),
				*ValidationError);
			return false;
		}
		if (!Context.bHasCorner)
		{
			OutError = TEXT("consequence application requires an active corner");
			return false;
		}
		if (Context.LateralPositionM != PreStepState.LateralPositionM)
		{
			OutError = TEXT("context lateral_position_m must match authoritative pre-step D");
			return false;
		}
		if (IntegratedState.ElapsedTimeS <= PreStepState.ElapsedTimeS)
		{
			OutError = TEXT("integrated elapsed time must advance");
			return false;
		}
		if (IntegratedState.DistanceM < PreStepState.DistanceM)
		{
			OutError = TEXT("integrated distance must not move backwards");
			return false;
		}
		if (Context.CornerEndM <= PreStepState.DistanceM)
		{
			OutError = TEXT("corner_end_m must be ahead of the pre-step distance");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(Context.LeftMarginM, TEXT("left_margin_m"), OutError)
			|| !CheckNonNegative(Context.RightMarginM, TEXT("right_margin_m"), OutError)
			|| !CheckFinite(
				Consequence.TargetLateralPositionM,
				TEXT("target_lateral_position_m"),
				OutError)
			|| !CheckNonNegative(
				Consequence.TargetSpeedMps,
				TEXT("target_speed_mps"),
				OutError))
		{
			return false;
		}

		const double LeftEdgeM =
			Context.LateralPositionM - Context.LeftMarginM;
		const double RightEdgeM =
			Context.LateralPositionM + Context.RightMarginM;
		if (!std::isfinite(LeftEdgeM) || !std::isfinite(RightEdgeM))
		{
			OutError = TEXT("derived road edges must be finite");
			return false;
		}
		if (LeftEdgeM > RightEdgeM)
		{
			OutError = TEXT("derived road edges are inverted");
			return false;
		}
		if (Consequence.TargetLateralPositionM < LeftEdgeM
			|| Consequence.TargetLateralPositionM > RightEdgeM)
		{
			OutError = TEXT("target_lateral_position_m lies outside road bounds");
			return false;
		}

		double AppliedSpeedMps = IntegratedState.SpeedMps;
		double ProjectedDistanceM = IntegratedState.DistanceM;

		switch (Consequence.Outcome)
		{
		case CyclingCornerConsequence::ECornerGeometryOutcome::Clean:
		case CyclingCornerConsequence::ECornerGeometryOutcome::WideLine:
			break;
		case CyclingCornerConsequence::ECornerGeometryOutcome::ControlledSlip:
			AppliedSpeedMps =
				std::fmin(IntegratedState.SpeedMps, Consequence.TargetSpeedMps);
			if (AppliedSpeedMps < IntegratedState.SpeedMps)
			{
				const double DtS =
					IntegratedState.ElapsedTimeS - PreStepState.ElapsedTimeS;
				const double LongitudinalDeltaM =
					0.5
					* (PreStepState.SpeedMps + AppliedSpeedMps)
					* DtS;
				ProjectedDistanceM =
					PreStepState.DistanceM + LongitudinalDeltaM;
			}
			break;
		default:
			OutError = TEXT("unsupported corner geometry outcome");
			return false;
		}

		const double LongitudinalStepM =
			ProjectedDistanceM - PreStepState.DistanceM;
		if (!std::isfinite(LongitudinalStepM) || LongitudinalStepM < 0.0)
		{
			OutError = TEXT("projected longitudinal step must be finite and non-negative");
			return false;
		}

		double Alpha = 0.0;
		if (LongitudinalStepM > 0.0)
		{
			const double RemainingCornerM =
				Context.CornerEndM - PreStepState.DistanceM;
			const double RemainingTransitionM =
				std::fmax(RemainingCornerM, LongitudinalStepM);
			Alpha = std::fmin(1.0, LongitudinalStepM / RemainingTransitionM);
		}

		const double NextLateralPositionM =
			PreStepState.LateralPositionM
			+ Alpha
				* (Consequence.TargetLateralPositionM
					- PreStepState.LateralPositionM);
		if (!std::isfinite(NextLateralPositionM)
			|| NextLateralPositionM < LeftEdgeM
			|| NextLateralPositionM > RightEdgeM)
		{
			OutError = TEXT("projected lateral position lies outside road bounds");
			return false;
		}

		FSimulationState Candidate = IntegratedState;
		Candidate.SpeedMps = AppliedSpeedMps;
		Candidate.DistanceM = ProjectedDistanceM;
		Candidate.LateralPositionM = NextLateralPositionM;
		if (!Candidate.Validate(ValidationError))
		{
			OutError = FString::Printf(
				TEXT("projected state is invalid: %s"),
				*ValidationError);
			return false;
		}

		OutApplication.State = Candidate;
		OutApplication.AppliedSpeedLossMps =
			IntegratedState.SpeedMps - AppliedSpeedMps;
		OutApplication.AppliedLateralShiftM =
			NextLateralPositionM - PreStepState.LateralPositionM;
		return true;
	}
}
