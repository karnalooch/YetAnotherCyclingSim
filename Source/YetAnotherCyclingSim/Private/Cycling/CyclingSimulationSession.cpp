#include "Cycling/CyclingSimulationSession.h"

namespace CyclingSimulation
{
	bool FCyclingSimulationSession::TryConfigure(const FCyclingSimulationSessionConfig& InConfig, FString& OutError)
	{
		OutError.Reset();

		// Build candidate values on local objects so validation runs before any
		// session state is mutated. The RiderInput validation is also performed
		// on a local candidate controller so the active session state cannot be
		// mutated by a partially-valid input configuration.
		FRiderParameters CandidateRider = InConfig.Rider;
		FEnvironment CandidateEnvironment = InConfig.Environment;
		FRiderInputController CandidateInputController;

		// Validation order is deterministic and documented in the header:
		//   1. Rider
		//   2. Environment
		//   3. RiderInput controller configuration
		if (!CandidateRider.Validate(OutError))
		{
			return false;
		}
		if (!CandidateEnvironment.Validate(OutError))
		{
			return false;
		}
		if (!CandidateInputController.TryConfigure(InConfig.RiderInput, OutError))
		{
			return false;
		}

		// All validations passed. Commit the new session atomically.
		AcceptedConfig = InConfig;
		InputController = CandidateInputController;
		Runner = FFixedStepSimulationRunner();
		bIsConfigured = true;
		return true;
	}

	bool FCyclingSimulationSession::TryAdvance(
		double FrameDeltaS,
		FSimulationState& OutState,
		double& OutRemainingTimeS,
		int32& OutCompletedSteps,
		FString& OutError)
	{
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutCompletedSteps = 0;
			OutState = Runner.GetState();
			OutRemainingTimeS = Runner.GetAccumulatedTimeS();
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}

		// Snapshot the current session state so that, on failure, the outputs
		// represent the unchanged current state. The runner does not partially
		// write OutState/OutRemainingTimeS on failure (its own transactional
		// semantics), and it resets CompletedSteps to zero on failure.
		const FSimulationState SnapshotState = Runner.GetState();
		const double SnapshotAccumulatedTimeS = Runner.GetAccumulatedTimeS();

		OutState = SnapshotState;
		OutRemainingTimeS = SnapshotAccumulatedTimeS;

		return Runner.TryAdvance(
			FrameDeltaS,
			AcceptedConfig.Rider,
			AcceptedConfig.Environment,
			InputController.GetInput(),
			OutState,
			OutRemainingTimeS,
			OutCompletedSteps,
			OutError);
	}

	bool FCyclingSimulationSession::TrySetPowerW(double ValueW, FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TrySetPowerW(ValueW, OutError);
	}

	bool FCyclingSimulationSession::TrySetCadenceRpm(double ValueRpm, FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TrySetCadenceRpm(ValueRpm, OutError);
	}

	bool FCyclingSimulationSession::TryIncreasePower(FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TryIncreasePower(OutError);
	}

	bool FCyclingSimulationSession::TryDecreasePower(FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TryDecreasePower(OutError);
	}

	bool FCyclingSimulationSession::TryIncreaseCadence(FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TryIncreaseCadence(OutError);
	}

	bool FCyclingSimulationSession::TryDecreaseCadence(FString& OutError)
	{
		if (!bIsConfigured)
		{
			OutError = FString::Printf(TEXT("session is not configured"));
			return false;
		}
		return InputController.TryDecreaseCadence(OutError);
	}

	void FCyclingSimulationSession::Reset()
	{
		if (!bIsConfigured)
		{
			// Documented no-op for unconfigured sessions. Must not make the
			// session configured.
			return;
		}

		// Preserve AcceptedConfig (do not touch).
		// Restore the configured initial rider input.
		InputController.Reset();
		// Clear simulation state and accumulator by replacing the runner with a
		// freshly default-constructed instance (zero state, zero accumulator).
		Runner = FFixedStepSimulationRunner();
		// bIsConfigured stays true.
	}
}
