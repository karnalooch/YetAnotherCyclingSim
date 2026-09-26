#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerContext.h"
#include "Cycling/CornerGripDemand.h"

namespace CyclingCornerConsequence
{
	enum class ECornerGeometryOutcome : uint8
	{
		Clean,
		WideLine,
		ControlledSlip,
	};

	// Stage 4C-C geometry-derived consequence for one active corner state.
	//
	// No arbitrary grip thresholds are used. If lateral demand exceeds the
	// physical limit, the resolver first consumes available road width toward
	// the outside of the turn to increase effective radius one-for-one. If
	// road width is insufficient, the remaining excess becomes a controlled
	// slip speed consequence. Crashes are intentionally absent from MVP.
	struct YETANOTHERCYCLINGSIM_API FCornerGeometryConsequence
	{
		ECornerGeometryOutcome Outcome = ECornerGeometryOutcome::Clean;
		double MinimumRequiredRadiusM = 0.0;
		double MaximumFeasibleRadiusM = 0.0;
		double RequiredOutwardShiftM = 0.0;
		double AppliedOutwardShiftM = 0.0;
		double LineDeviationRatio = 0.0;
		double TargetLateralPositionM = 0.0;
		double TargetSpeedMps = 0.0;
		double ExitSpeedMultiplier = 1.0;
	};

	YETANOTHERCYCLINGSIM_API bool TryResolveCornerGeometryConsequence(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerGrip::FCornerGripDemand& Demand,
		FCornerGeometryConsequence& OutConsequence,
		FString& OutError);
}
