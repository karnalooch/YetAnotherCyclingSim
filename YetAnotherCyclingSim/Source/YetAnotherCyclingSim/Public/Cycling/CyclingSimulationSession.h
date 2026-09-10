#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/RiderInputController.h"
#include "Cycling/SimulationState.h"
#include "Cycling/FixedStepRunner.h"

// Pure C++ deterministic cycling simulation session.
//
// The session is the single orchestration layer above the fixed-step
// simulation runner and the rider input controller. It owns the validated
// configuration, the current rider input, and the simulation runner. It
// exposes one deterministic API for configuring, advancing, controlling,
// and resetting a ride.
//
// The session is independent from Actors, Pawns, components, input bindings,
// maps, assets, rendering, and system time. Identical configuration and
// identical command/frame sequences always produce identical simulation
// state and rider input.
//
// All public fields and parameters use SI units:
//   - rider and bicycle masses in kilograms (kg);
//   - aerodynamic drag area in square metres (m^2);
//   - rolling resistance is dimensionless;
//   - drivetrain efficiency is dimensionless;
//   - environment grade is a decimal fraction (unitless);
//   - environment wind speed in metres per second (m/s);
//   - environment air density in kilograms per cubic metre (kg/m^3);
//   - power in watts (W);
//   - cadence in revolutions per minute (rpm);
//   - simulation speed in metres per second (m/s);
//   - simulation distance in metres (m);
//   - time in seconds (s).
namespace CyclingSimulation
{
	// Configuration of a deterministic cycling simulation session.
	//
	// The session reads the rider, environment, and rider-input controller
	// configuration from this struct when TryConfigure is called. Default
	// values intentionally leave the rider and the environment invalid; a
	// valid configuration must be supplied explicitly. The rider-input
	// controller configuration uses its own documented defaults.
	struct YETANOTHERCYCLINGSIM_API FCyclingSimulationSessionConfig
	{
		// Rider and bicycle parameters used by the cycling physics model.
		// See FRiderParameters for unit definitions and validation rules.
		FRiderParameters Rider;

		// Environmental conditions along the route. See FEnvironment for
		// unit definitions and validation rules.
		FEnvironment Environment;

		// Configuration of the deterministic rider input controller. See
		// FRiderInputControllerConfig for unit definitions and validation
		// rules.
		FRiderInputControllerConfig RiderInput;
	};

	// Deterministic, rendering-independent cycling simulation session.
	//
	// A default-constructed session is unconfigured. TryAdvance, input
	// mutation operations, and Reset are documented to fail or be no-ops
	// until TryConfigure succeeds. Configuration is transactional: a failed
	// TryConfigure preserves the complete previous valid session (accepted
	// configuration, rider input, simulation state, accumulated time,
	// configured flag). A successful TryConfigure starts a fresh ride
	// (speed, distance, elapsed time, accumulated time are reset to zero;
	// rider input is reset to the configured initial power and cadence).
	class YETANOTHERCYCLINGSIM_API FCyclingSimulationSession
	{
	public:
		// Constructs an unconfigured session.
		FCyclingSimulationSession() = default;

		// TryConfigure validates InConfig and, on success, accepts the new
		// configuration and starts a fresh ride. Validation order is
		// deterministic:
		//   1. FRiderParameters::Validate(InConfig.Rider...);
		//   2. FEnvironment::Validate(InConfig.Environment...);
		//   3. InputController.TryConfigure(InConfig.RiderInput...).
		// The candidate values are validated before any session state is
		// mutated. On failure, the previous valid session is preserved
		// unchanged and OutError receives the first validation error. On
		// success, OutError is cleared, the accepted configuration is
		// stored, the input controller is configured with the new initial
		// input, and the fixed-step runner is reset (speed, distance,
		// elapsed time, accumulated time all set to zero).
		bool TryConfigure(const FCyclingSimulationSessionConfig& InConfig, FString& OutError);

		// TryAdvance delegates fixed-step timing and physics to the
		// configured FFixedStepSimulationRunner, using the accepted rider
		// parameters, environment, and the current rider input.
		//
		// FrameDeltaS is in seconds (s). It must be finite and non-negative;
		// the runner performs its own validation.
		//
		// On success, OutState contains the new simulation state, the
		// remaining accumulated time is written to OutRemainingTimeS, and
		// OutCompletedSteps contains the number of fixed steps executed.
		//
		// On failure, the session state and accumulator remain unchanged.
		// OutState and OutRemainingTimeS represent the unchanged current
		// session state (snapshot taken before the runner call). OutCompletedSteps
		// is zero. OutError receives the first failure message.
		//
		// If the session is unconfigured, the operation is rejected with
		// a useful error, the session state remains unchanged, and all
		// outputs represent the unconfigured session state (zero state and
		// zero accumulated time).
		bool TryAdvance(
			double FrameDeltaS,
			FSimulationState& OutState,
			double& OutRemainingTimeS,
			int32& OutCompletedSteps,
			FString& OutError);

		// Sets the current power in watts (W). Delegates to the configured
		// rider input controller. Returns false (with a useful error and
		// without changing the current input) if the session is
		// unconfigured or the controller rejects the value.
		bool TrySetPowerW(double ValueW, FString& OutError);

		// Sets the current cadence in revolutions per minute (rpm).
		// Delegates to the configured rider input controller. Returns
		// false (with a useful error) if the session is unconfigured.
		bool TrySetCadenceRpm(double ValueRpm, FString& OutError);

		// Increases the current power by the configured PowerStepW,
		// clamping at MaxPowerW. Returns false (with a useful error) if the
		// session is unconfigured.
		bool TryIncreasePower(FString& OutError);

		// Decreases the current power by the configured PowerStepW,
		// clamping at MinPowerW. Returns false (with a useful error) if the
		// session is unconfigured.
		bool TryDecreasePower(FString& OutError);

		// Increases the current cadence by the configured CadenceStepRpm,
		// clamping at MaxCadenceRpm. Returns false (with a useful error) if
		// the session is unconfigured.
		bool TryIncreaseCadence(FString& OutError);

		// Decreases the current cadence by the configured CadenceStepRpm,
		// clamping at MinCadenceRpm. Returns false (with a useful error) if
		// the session is unconfigured.
		bool TryDecreaseCadence(FString& OutError);

		// Resets the configured session to a fresh ride while preserving
		// the accepted configuration: speed, distance, and elapsed
		// simulation time are reset to zero; the fixed-step accumulator is
		// reset to zero; the rider input is restored to the configured
		// initial power and cadence. The session stays configured.
		//
		// For an unconfigured session, Reset is a documented no-op and does
		// not make the session configured.
		void Reset();

		// Returns true when TryConfigure has succeeded at least once and the
		// session has not been reconfigured with a failing call.
		bool IsConfigured() const { return bIsConfigured; }

		// Returns the current simulation state. For an unconfigured
		// session the returned state has all fields set to zero.
		const FSimulationState& GetSimulationState() const { return Runner.GetState(); }

		// Returns the current rider input as the physics data contract.
		const FRiderInput& GetRiderInput() const { return InputController.GetInput(); }

		// Returns the accumulated unprocessed frame time in seconds (s).
		double GetAccumulatedTimeS() const { return Runner.GetAccumulatedTimeS(); }

		// Returns the accepted configuration (the configuration from the
		// most recent successful TryConfigure). For an unconfigured session
		// the returned config contains default (invalid) rider and
		// environment fields.
		const FCyclingSimulationSessionConfig& GetConfig() const { return AcceptedConfig; }

	private:
		FCyclingSimulationSessionConfig AcceptedConfig;
		FRiderInputController InputController;
		FFixedStepSimulationRunner Runner;
		bool bIsConfigured = false;
	};
}
