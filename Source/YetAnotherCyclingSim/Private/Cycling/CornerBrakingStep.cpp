#include "Cycling/CornerBrakingStep.h"

#include "Cycling/Cornering.h"

namespace CyclingCornerBraking
{
	namespace
	{
		bool IsActiveLateralPhase(CyclingCornering::ECornerPhase Phase)
		{
			return Phase == CyclingCornering::ECornerPhase::Entry
				|| Phase == CyclingCornering::ECornerPhase::Apex
				|| Phase == CyclingCornering::ECornerPhase::Exit;
		}
	}

	bool TryResolveCornerBrakingStep(
		const CyclingRoadPhysics::FRoadPhysicsProfile& RoadProfile,
		const CyclingCornerContext::FCornerContextSettings& CornerSettings,
		const CyclingSurfaceGrip::FSurfaceGripPolicy& GripPolicy,
		double BaseFrictionCoefficient,
		double LateralPositionM,
		const FRiderParameters& Rider,
		const FRiderInput& RiderInput,
		const FSimulationState& State,
		FCornerBrakingStepResolution& OutResolution,
		FString& OutError)
	{
		OutResolution = FCornerBrakingStepResolution{};
		OutError.Reset();

		FString ValidationError;
		if (!RiderInput.Validate(ValidationError))
		{
			OutError = FString::Printf(
				TEXT("corner braking rider input is invalid: %s"),
				*ValidationError);
			return false;
		}
		if (!State.Validate(ValidationError))
		{
			OutError = FString::Printf(
				TEXT("corner braking simulation state is invalid: %s"),
				*ValidationError);
			return false;
		}

		CyclingRoadPhysics::FRoadPhysicsState CurrentRoadState;
		if (!RoadProfile.TryGetStateAt(
			State.DistanceM,
			LateralPositionM,
			CurrentRoadState,
			OutError))
		{
			return false;
		}

		CyclingCornerContext::FCornerContext Context;
		if (!CyclingCornerContext::TryBuildCornerContext(
			RoadProfile,
			State.DistanceM,
			LateralPositionM,
			CornerSettings,
			Context,
			OutError))
		{
			return false;
		}

		CyclingSurfaceGrip::FResolvedSurfaceGrip CurrentSurfaceGrip;
		if (!GripPolicy.TryResolve(
			CurrentRoadState.SurfaceId,
			CurrentRoadState.Wetness,
			CurrentSurfaceGrip,
			OutError))
		{
			return false;
		}

		double CurrentEffectiveFriction = 0.0;
		if (!CyclingCornering::TryCalculateEffectiveFrictionCoefficient(
			BaseFrictionCoefficient,
			CurrentSurfaceGrip.GripMultiplier,
			CurrentEffectiveFriction,
			OutError))
		{
			return false;
		}

		const bool bHasActiveLateralDemand =
			Context.bHasCorner && IsActiveLateralPhase(Context.Phase);

		CyclingCornerLimit::FCornerLateralLimit LateralLimit;
		CyclingCornerGrip::FCornerGripDemand GripDemand;
		double LateralUsage = 0.0;

		if (bHasActiveLateralDemand)
		{
			if (!CyclingCornerLimit::TryCalculateCornerLateralLimit(
				Context,
				GripPolicy,
				BaseFrictionCoefficient,
				LateralLimit,
				OutError))
			{
				return false;
			}
			if (!CyclingCornerGrip::TryCalculateCornerGripDemand(
				Context,
				LateralLimit,
				State.SpeedMps,
				RiderInput.BrakeRatio,
				GripDemand,
				OutError))
			{
				return false;
			}
			LateralUsage = GripDemand.LateralUsage;
		}

		CyclingBraking::FBrakingForceDemand BrakingForceDemand;
		if (!CyclingBraking::TryCalculateBrakingForceDemand(
			Rider,
			CurrentRoadState.GradeDecimal,
			CurrentRoadState.CrossSlopeAngleRad,
			CurrentEffectiveFriction,
			RiderInput.BrakeRatio,
			LateralUsage,
			BrakingForceDemand,
			OutError))
		{
			return false;
		}

		OutResolution.CurrentRoadState = CurrentRoadState;
		OutResolution.CornerContext = Context;
		OutResolution.bHasActiveLateralDemand = bHasActiveLateralDemand;
		OutResolution.LateralLimit = LateralLimit;
		OutResolution.GripDemand = GripDemand;
		OutResolution.BrakingForceDemand = BrakingForceDemand;
		return true;
	}
}
