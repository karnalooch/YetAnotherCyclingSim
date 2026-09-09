#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

// Deterministic single-step simulation, ported from the Python reference model
// (physics_reference/src/cycling_physics/model.py, step_simulation).
//
// The function follows the Try convention: it snapshots the input state before
// touching the output, resets OutState to a zero state and OutError, validates
// the inputs in a fixed order, then computes the next state using the existing
// CyclingForces API. The calculated result is validated before it is written
// to OutState. On failure OutState remains a zero state and OutError holds the
// first error. State and OutState may alias the same object. No exceptions are
// thrown.
namespace CyclingSimulation
{
	// Advances the simulation by one deterministic fixed step of DtS seconds
	// (must be finite and greater than zero) using an energy balance, and
	// writes the resulting state to OutState. Returns false with OutError set
	// when any input is invalid or when the calculated state is not valid.
	YETANOTHERCYCLINGSIM_API bool TryStepSimulation(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		const FRiderInput& RiderInput,
		const FSimulationState& State,
		double DtS,
		FSimulationState& OutState,
		FString& OutError);
}
