#include "Cycling/SimulationStep.h"

#include "Cycling/CyclingForces.h"
#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace CyclingSimulation
{
	bool TryStepSimulation(
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		const FRiderInput& RiderInput,
		const FSimulationState& State,
		double DtS,
		FSimulationState& OutState,
		FString& OutError)
	{
		// Snapshot the input before touching the output so that State and
		// OutState may safely alias the same object.
		const FSimulationState InputState = State;

		// Reset the output so that a failure always leaves a deterministic
		// zero state and never a stale result.
		OutState = FSimulationState();
		OutError.Reset();

		// Validate in a fixed order; use InputState only.
		if (!Rider.Validate(OutError))
		{
			return false;
		}
		if (!Environment.Validate(OutError))
		{
			return false;
		}
		if (!RiderInput.Validate(OutError))
		{
			return false;
		}
		if (!InputState.Validate(OutError))
		{
			return false;
		}
		using namespace CyclingPhysicsValidation;
		if (!CheckPositive(DtS, TEXT("dt_s"), OutError))
		{
			return false;
		}

		const double TotalMassKg = Rider.GetTotalMassKg();
		const double CurrentSpeedMps = InputState.SpeedMps;

		const double InitialEnergyJ = 0.5 * TotalMassKg * CurrentSpeedMps * CurrentSpeedMps;
		const double DriveWorkJ = RiderInput.PowerW * Rider.DrivetrainEfficiency * DtS;

		double ResistanceForceN = 0.0;
		if (!CyclingForces::TryCalculateTotalResistanceForceN(Rider, Environment, CurrentSpeedMps, ResistanceForceN, OutError))
		{
			return false;
		}

		const double ExternalAccelerationMps2 = -ResistanceForceN / TotalMassKg;
		const double ExternalPredictedSpeedMps = std::fmax(0.0, CurrentSpeedMps + ExternalAccelerationMps2 * DtS);
		const double PredictedSpeedMps = std::sqrt(std::fmax(0.0, ExternalPredictedSpeedMps * ExternalPredictedSpeedMps + 2.0 * DriveWorkJ / TotalMassKg));
		const double EstimatedAverageSpeedMps = 0.5 * (CurrentSpeedMps + PredictedSpeedMps);

		double AverageResistanceForceN = 0.0;
		if (!CyclingForces::TryCalculateTotalResistanceForceN(Rider, Environment, EstimatedAverageSpeedMps, AverageResistanceForceN, OutError))
		{
			return false;
		}

		const double ResistanceWorkJ = AverageResistanceForceN * EstimatedAverageSpeedMps * DtS;
		const double FinalEnergyJ = std::fmax(0.0, InitialEnergyJ + DriveWorkJ - ResistanceWorkJ);
		const double NewSpeedMps = std::sqrt(2.0 * FinalEnergyJ / TotalMassKg);

		const double DistanceDeltaM = 0.5 * (CurrentSpeedMps + NewSpeedMps) * DtS;

		FSimulationState CandidateState;
		CandidateState.SpeedMps = NewSpeedMps;
		CandidateState.DistanceM = InputState.DistanceM + DistanceDeltaM;
		CandidateState.ElapsedTimeS = InputState.ElapsedTimeS + DtS;

		if (!CandidateState.Validate(OutError))
		{
			return false;
		}

		OutState = CandidateState;
		return true;
	}
}
