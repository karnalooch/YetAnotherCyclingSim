#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/Braking.h"
#include "Cycling/CornerContext.h"
#include "Cycling/CornerGripDemand.h"
#include "Cycling/CornerLateralLimit.h"
#include "Cycling/RiderInput.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/RoadPhysicsProfile.h"
#include "Cycling/SimulationState.h"
#include "Cycling/SurfaceGripPolicy.h"

namespace CyclingCornerBraking
{
	// Stage 4C-B3c result for one authoritative fixed simulation substep.
	//
	// CurrentRoadState is always sampled at the rider's current S/D and owns
	// the longitudinal tyre-contact inputs (grade, cross-slope, surface and
	// wetness). CornerContext may describe a look-ahead corner during
	// Approach; that future metadata must not replace current tyre contact.
	struct YETANOTHERCYCLINGSIM_API FCornerBrakingStepResolution
	{
		CyclingRoadPhysics::FRoadPhysicsState CurrentRoadState;
		CyclingCornerContext::FCornerContext CornerContext;
		bool bHasActiveLateralDemand = false;
		CyclingCornerLimit::FCornerLateralLimit LateralLimit;
		CyclingCornerGrip::FCornerGripDemand GripDemand;
		CyclingBraking::FBrakingForceDemand BrakingForceDemand;
	};

	// Resolves the complete Stage 4C-B3c tyre demand for one pre-step state.
	//
	// Lateral demand consumes shared grip only in Entry/Apex/Exit. Approach is
	// look-ahead guidance and therefore retains zero actual lateral usage.
	// Longitudinal braking capacity always uses the current road state under
	// the tyres, never a future corner's surface/bank metadata.
	YETANOTHERCYCLINGSIM_API bool TryResolveCornerBrakingStep(
		const CyclingRoadPhysics::FRoadPhysicsProfile& RoadProfile,
		const CyclingCornerContext::FCornerContextSettings& CornerSettings,
		const CyclingSurfaceGrip::FSurfaceGripPolicy& GripPolicy,
		double BaseFrictionCoefficient,
		double LateralPositionM,
		const FRiderParameters& Rider,
		const FRiderInput& RiderInput,
		const FSimulationState& State,
		FCornerBrakingStepResolution& OutResolution,
		FString& OutError);
}
