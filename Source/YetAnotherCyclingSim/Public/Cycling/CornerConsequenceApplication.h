#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerConsequence.h"
#include "Cycling/CornerContext.h"
#include "Cycling/SimulationState.h"

namespace CyclingCornerApplication
{
	// One deterministic Stage 4C-C3 post-integrator consequence application.
	struct YETANOTHERCYCLINGSIM_API FCornerConsequenceApplication
	{
		FSimulationState State;
		double AppliedSpeedLossMps = 0.0;
		double AppliedLateralShiftM = 0.0;
	};

	// Applies one C1 geometry consequence to authoritative route state.
	//
	// Clean/wide-line preserve integrated forward speed/distance exactly.
	// Controlled slip may only reduce speed; when it does, distance is
	// recomputed using the base integrator's trapezoidal convention.
	//
	// Signed route-local D moves continuously toward the C1 target over the
	// remaining corner distance. This is an MVP route-line projection, not a
	// detailed steering/front-rear tyre model.
	YETANOTHERCYCLINGSIM_API bool TryApplyCornerGeometryConsequence(
		const FSimulationState& PreStepState,
		const FSimulationState& IntegratedState,
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerConsequence::FCornerGeometryConsequence& Consequence,
		FCornerConsequenceApplication& OutApplication,
		FString& OutError);
}
