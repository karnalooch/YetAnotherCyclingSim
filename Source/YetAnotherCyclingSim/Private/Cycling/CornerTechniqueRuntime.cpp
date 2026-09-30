#include "Cycling/CornerTechniqueRuntime.h"

#include "Cycling/PhysicsValidation.h"

#include <cmath>

namespace
{
	using namespace CyclingCornerTechniqueRuntime;

	bool IsScorablePhase(CyclingCornering::ECornerPhase Phase)
	{
		return Phase == CyclingCornering::ECornerPhase::Approach
			|| Phase == CyclingCornering::ECornerPhase::Entry
			|| Phase == CyclingCornering::ECornerPhase::Apex
			|| Phase == CyclingCornering::ECornerPhase::Exit;
	}

	bool ValidateRuntimeState(
		const FCornerTechniqueRuntimeState& State,
		FString& OutError)
	{
		using namespace CyclingPhysicsValidation;

		if (State.bHasActiveEpisode)
		{
			if (!CheckNonNegative(
					State.ActiveCornerStartM,
					TEXT("active_corner_start_m"),
					OutError)
				|| !CheckFinite(
					State.ActiveCornerEndM,
					TEXT("active_corner_end_m"),
					OutError))
			{
				return false;
			}
			if (State.ActiveCornerEndM <= State.ActiveCornerStartM)
			{
				OutError = TEXT("active_corner_end_m must be greater than start");
				return false;
			}
		}
		if (!CheckClosedUnitInterval(
				State.MaxLineDeviationRatio,
				TEXT("max_line_deviation_ratio"),
				OutError)
			|| !CheckClosedUnitInterval(
				State.MinExitSpeedMultiplier,
				TEXT("min_exit_speed_multiplier"),
				OutError))
		{
			return false;
		}
		if (State.SkippedEpisodeCount < 0)
		{
			OutError = TEXT("skipped_episode_count must be non-negative");
			return false;
		}
		return true;
	}

	bool HasAllPhases(
		const TArray<CyclingCornerTechnique::FRouteCornerTechniqueObservation>& Observations)
	{
		bool bApproach = false;
		bool bEntry = false;
		bool bApex = false;
		bool bExit = false;
		for (const CyclingCornerTechnique::FRouteCornerTechniqueObservation& Observation : Observations)
		{
			switch (Observation.Phase)
			{
			case CyclingCornering::ECornerPhase::Approach:
				bApproach = true;
				break;
			case CyclingCornering::ECornerPhase::Entry:
				bEntry = true;
				break;
			case CyclingCornering::ECornerPhase::Apex:
				bApex = true;
				break;
			case CyclingCornering::ECornerPhase::Exit:
				bExit = true;
				break;
			default:
				break;
			}
		}
		return bApproach && bEntry && bApex && bExit;
	}

	void ResetActiveEpisode(FCornerTechniqueRuntimeState& State)
	{
		State.bHasActiveEpisode = false;
		State.ActiveCornerStartM = 0.0;
		State.ActiveCornerEndM = 0.0;
		State.Observations.Reset();
		State.MaxLineDeviationRatio = 0.0;
		State.MinExitSpeedMultiplier = 1.0;
	}

	bool TryFinalizeEpisode(
		FCornerTechniqueRuntimeState& State,
		FString& OutError)
	{
		if (!State.bHasActiveEpisode)
		{
			return true;
		}

		if (!HasAllPhases(State.Observations))
		{
			++State.SkippedEpisodeCount;
			ResetActiveEpisode(State);
			return true;
		}

		CyclingCornerTechnique::FRouteCornerTechniqueSummary Summary;
		if (!CyclingCornerTechnique::TrySummarizeRouteCornerTechnique(
				State.Observations,
				Summary,
				OutError))
		{
			return false;
		}

		if (Summary.ApproachPowerW <= 0.0 || Summary.ApproachCadenceRpm <= 0.0)
		{
			++State.SkippedEpisodeCount;
			ResetActiveEpisode(State);
			return true;
		}

		CyclingCornerConsequence::FCornerGeometryConsequence Aggregate;
		Aggregate.LineDeviationRatio = State.MaxLineDeviationRatio;
		Aggregate.ExitSpeedMultiplier = State.MinExitSpeedMultiplier;
		if (State.MinExitSpeedMultiplier < 1.0)
		{
			Aggregate.Outcome =
				CyclingCornerConsequence::ECornerGeometryOutcome::ControlledSlip;
		}
		else if (State.MaxLineDeviationRatio > 0.0)
		{
			Aggregate.Outcome =
				CyclingCornerConsequence::ECornerGeometryOutcome::WideLine;
		}
		else
		{
			Aggregate.Outcome =
				CyclingCornerConsequence::ECornerGeometryOutcome::Clean;
		}

		CyclingCornerTechnique::FRouteCornerTechniqueScore Score;
		if (!CyclingCornerTechnique::TryScoreRouteCornerTechnique(
				Summary,
				Aggregate,
				Score,
				OutError))
		{
			return false;
		}

		FCompletedRouteCornerTechniqueScore Completed;
		Completed.CornerStartM = State.ActiveCornerStartM;
		Completed.CornerEndM = State.ActiveCornerEndM;
		Completed.Score = Score;
		State.CompletedScores.Add(Completed);
		ResetActiveEpisode(State);
		return true;
	}
}

namespace CyclingCornerTechniqueRuntime
{
	bool TryObserveCornerTechniqueStep(
		const FCornerTechniqueRuntimeState& InState,
		const CyclingCornerContext::FCornerContext& Context,
		const FRiderInput& RiderInput,
		const CyclingCornerConsequence::FCornerGeometryConsequence* Consequence,
		const FSimulationState& PostStepState,
		FCornerTechniqueRuntimeState& OutState,
		FString& OutError)
	{
		OutState = InState;
		OutError.Reset();

		if (!ValidateRuntimeState(InState, OutError))
		{
			return false;
		}
		FString StateError;
		if (!PostStepState.Validate(StateError))
		{
			OutError = FString::Printf(
				TEXT("post-step state is invalid: %s"),
				*StateError);
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(RiderInput.PowerW, TEXT("power_w"), OutError)
			|| !CheckNonNegative(RiderInput.CadenceRpm, TEXT("cadence_rpm"), OutError))
		{
			return false;
		}
		if (Consequence != nullptr)
		{
			if (!CheckClosedUnitInterval(
					Consequence->LineDeviationRatio,
					TEXT("line_deviation_ratio"),
					OutError)
				|| !CheckClosedUnitInterval(
					Consequence->ExitSpeedMultiplier,
					TEXT("exit_speed_multiplier"),
					OutError))
			{
				return false;
			}
		}

		FCornerTechniqueRuntimeState Candidate = InState;

		if (!Context.bHasCorner || !IsScorablePhase(Context.Phase))
		{
			if (Candidate.bHasActiveEpisode
				&& PostStepState.DistanceM >= Candidate.ActiveCornerEndM)
			{
				if (!TryFinalizeEpisode(Candidate, OutError))
				{
					return false;
				}
			}
			OutState = MoveTemp(Candidate);
			return true;
		}

		if (!CheckNonNegative(Context.CornerStartM, TEXT("corner_start_m"), OutError)
			|| !CheckFinite(Context.CornerEndM, TEXT("corner_end_m"), OutError))
		{
			return false;
		}
		if (Context.CornerEndM <= Context.CornerStartM)
		{
			OutError = TEXT("corner context interval must be finite and ordered");
			return false;
		}

		if (!Candidate.bHasActiveEpisode)
		{
			Candidate.bHasActiveEpisode = true;
			Candidate.ActiveCornerStartM = Context.CornerStartM;
			Candidate.ActiveCornerEndM = Context.CornerEndM;
			Candidate.Observations.Reset();
			Candidate.MaxLineDeviationRatio = 0.0;
			Candidate.MinExitSpeedMultiplier = 1.0;
		}
		else if (Context.CornerStartM != Candidate.ActiveCornerStartM
			|| Context.CornerEndM != Candidate.ActiveCornerEndM)
		{
			OutError = TEXT(
				"corner context changed interval before active technique episode completed");
			return false;
		}

		CyclingCornerTechnique::FRouteCornerTechniqueObservation Observation;
		Observation.Phase = Context.Phase;
		Observation.PowerW = RiderInput.PowerW;
		Observation.CadenceRpm = RiderInput.CadenceRpm;
		Candidate.Observations.Add(Observation);

		if (Consequence != nullptr)
		{
			Candidate.MaxLineDeviationRatio =
				FMath::Max(
					Candidate.MaxLineDeviationRatio,
					Consequence->LineDeviationRatio);
			Candidate.MinExitSpeedMultiplier =
				FMath::Min(
					Candidate.MinExitSpeedMultiplier,
					Consequence->ExitSpeedMultiplier);
		}

		if (PostStepState.DistanceM >= Candidate.ActiveCornerEndM)
		{
			if (!TryFinalizeEpisode(Candidate, OutError))
			{
				return false;
			}
		}

		OutState = MoveTemp(Candidate);
		return true;
	}
}
