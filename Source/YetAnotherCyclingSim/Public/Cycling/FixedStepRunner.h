#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace CyclingSimulation
{
	// Fixed-step runner that converts variable frame delta time into deterministic
	// 0.05-second calls to TryStepSimulation. This runner accumulates frame time
	// and executes as many fixed simulation steps as will fit in the accumulated time.
	//
	// The runner maintains its own simulation state and accumulated time. It does not
	// modify the input parameters. On failure, the runner state and accumulated time
	// remain unchanged (transactional semantics).
	//
	// All times are in seconds (s), speeds in metres per second (m/s), distances
	// in metres (m). The fixed step duration is exactly 0.05 seconds.
	class YETANOTHERCYCLINGSIM_API FFixedStepSimulationRunner
	{
	public:
		// The fixed simulation step duration in seconds (s). This value is passed
		// to TryStepSimulation for each substep.
		static constexpr double FixedStepDtS = 0.05;

		// A small boundary tolerance expressed in seconds (s). It is used when
		// comparing accumulated time to the fixed-step boundary and when
		// deciding whether a tiny negative accumulator is normal floating-point
		// boundary error. This is needed because binary floating-point
		// representation cannot exactly represent 0.05. The tolerance is much
		// smaller than the fixed step itself.
		static constexpr double FixedStepBoundaryToleranceS = 1e-12;

		// Constructs a runner with default (zero) state and zero accumulated time.
		FFixedStepSimulationRunner() = default;

		// Advances the simulation by FrameDeltaS seconds, executing zero, one, or
		// multiple fixed simulation steps. The accumulated frame time is combined
		// with any previously remaining time.
		//
		// FrameDeltaS must be finite and non-negative. A zero frame delta is valid
		// and performs no steps.
		//
		// On success, the runner state is updated to the new simulation state,
		// RemainingAccumulatedTimeS contains the unused fractional time, and
		// CompletedSteps contains the number of fixed steps executed.
		//
		// On failure, the runner state and accumulated time are left unchanged,
		// OutError contains the first error message, and CompletedSteps is zero.
		bool TryAdvance(
			double FrameDeltaS,
			const FRiderParameters& Rider,
			const FEnvironment& Environment,
			const FRiderInput& RiderInput,
			FSimulationState& OutState,
			double& RemainingAccumulatedTimeS,
			int32& CompletedSteps,
			FString& OutError);

		// Returns the current simulation state.
		const FSimulationState& GetState() const { return State; }

		// Returns the accumulated unprocessed frame time in seconds (s).
		double GetAccumulatedTimeS() const { return AccumulatedTimeS; }

	private:
		FSimulationState State;
		double AccumulatedTimeS = 0.0;
	};
}
