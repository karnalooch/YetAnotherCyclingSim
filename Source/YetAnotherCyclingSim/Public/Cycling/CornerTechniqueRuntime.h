#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerConsequence.h"
#include "Cycling/CornerContext.h"
#include "Cycling/CornerTechnique.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace CyclingCornerTechniqueRuntime
{
	struct YETANOTHERCYCLINGSIM_API FCompletedRouteCornerTechniqueScore
	{
		double CornerStartM = 0.0;
		double CornerEndM = 0.0;
		CyclingCornerTechnique::FRouteCornerTechniqueScore Score;
	};

	// Transactional Stage 4C-C3 runtime episode state.
	//
	// This value is copied by the fixed-step runner before a multi-substep
	// advance and committed only with the authoritative simulation state.
	struct YETANOTHERCYCLINGSIM_API FCornerTechniqueRuntimeState
	{
		bool bHasActiveEpisode = false;
		double ActiveCornerStartM = 0.0;
		double ActiveCornerEndM = 0.0;
		TArray<CyclingCornerTechnique::FRouteCornerTechniqueObservation> Observations;
		double MaxLineDeviationRatio = 0.0;
		double MinExitSpeedMultiplier = 1.0;
		TArray<FCompletedRouteCornerTechniqueScore> CompletedScores;
		int32 SkippedEpisodeCount = 0;
	};

	// Observes one successfully integrated fixed substep.
	//
	// Context is the pre-step route-derived corner context and PostStepState is
	// the authoritative state after C3 consequence application. Consequence may
	// be null during Approach or outside active lateral-demand phases.
	//
	// A complete episode is finalized through the reviewed C2 score. Truncated
	// episodes or zero Approach baselines are skipped deterministically instead
	// of failing the physics simulation. Invalid/inconsistent domain state still
	// fails closed.
	YETANOTHERCYCLINGSIM_API bool TryObserveCornerTechniqueStep(
		const FCornerTechniqueRuntimeState& InState,
		const CyclingCornerContext::FCornerContext& Context,
		const FRiderInput& RiderInput,
		const CyclingCornerConsequence::FCornerGeometryConsequence* Consequence,
		const FSimulationState& PostStepState,
		FCornerTechniqueRuntimeState& OutState,
		FString& OutError);
}
