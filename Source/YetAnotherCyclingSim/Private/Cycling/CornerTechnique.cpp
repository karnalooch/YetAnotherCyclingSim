#include "Cycling/CornerTechnique.h"

#include "Cycling/PhysicsValidation.h"
#include "Math/UnrealMathUtility.h"

namespace
{
	struct FPhaseAccumulator
	{
		double PowerSum = 0.0;
		double CadenceSum = 0.0;
		int32 Count = 0;
	};

	bool ValidateSummary(
		const CyclingCornerTechnique::FRouteCornerTechniqueSummary& Summary,
		FString& OutError)
	{
		using namespace CyclingPhysicsValidation;
		return
			CheckNonNegative(Summary.ApproachPowerW, TEXT("approach_power_w"), OutError)
			&& CheckNonNegative(Summary.EntryPowerW, TEXT("entry_power_w"), OutError)
			&& CheckNonNegative(Summary.ApexPowerW, TEXT("apex_power_w"), OutError)
			&& CheckNonNegative(Summary.ExitPowerW, TEXT("exit_power_w"), OutError)
			&& CheckNonNegative(Summary.ApproachCadenceRpm, TEXT("approach_cadence_rpm"), OutError)
			&& CheckNonNegative(Summary.EntryCadenceRpm, TEXT("entry_cadence_rpm"), OutError)
			&& CheckNonNegative(Summary.ApexCadenceRpm, TEXT("apex_cadence_rpm"), OutError)
			&& CheckNonNegative(Summary.ExitCadenceRpm, TEXT("exit_cadence_rpm"), OutError);
	}

	double ReleaseScore(double Value, double Baseline)
	{
		const double Ratio = FMath::Clamp(Value / Baseline, 0.0, 1.0);
		return 100.0 * (1.0 - Ratio);
	}

	double RecoveryScore(double Value, double Baseline)
	{
		const double Ratio = FMath::Clamp(Value / Baseline, 0.0, 1.0);
		return 100.0 * Ratio;
	}
}

namespace CyclingCornerTechnique
{
	bool TrySummarizeRouteCornerTechnique(
		const TArray<FRouteCornerTechniqueObservation>& Observations,
		FRouteCornerTechniqueSummary& OutSummary,
		FString& OutError)
	{
		OutSummary = FRouteCornerTechniqueSummary{};
		OutError.Reset();

		if (Observations.IsEmpty())
		{
			OutError = TEXT("observations must not be empty");
			return false;
		}

		FPhaseAccumulator Approach;
		FPhaseAccumulator Entry;
		FPhaseAccumulator Apex;
		FPhaseAccumulator Exit;

		for (int32 Index = 0; Index < Observations.Num(); ++Index)
		{
			const FRouteCornerTechniqueObservation& Observation = Observations[Index];
			using namespace CyclingPhysicsValidation;
			if (!CheckNonNegative(Observation.PowerW, TEXT("power_w"), OutError)
				|| !CheckNonNegative(Observation.CadenceRpm, TEXT("cadence_rpm"), OutError))
			{
				return false;
			}

			FPhaseAccumulator* Accumulator = nullptr;
			switch (Observation.Phase)
			{
			case CyclingCornering::ECornerPhase::Approach:
				Accumulator = &Approach;
				break;
			case CyclingCornering::ECornerPhase::Entry:
				Accumulator = &Entry;
				break;
			case CyclingCornering::ECornerPhase::Apex:
				Accumulator = &Apex;
				break;
			case CyclingCornering::ECornerPhase::Exit:
				Accumulator = &Exit;
				break;
			default:
				OutError = TEXT("phase must be approach, entry, apex or exit");
				return false;
			}

			Accumulator->PowerSum += Observation.PowerW;
			Accumulator->CadenceSum += Observation.CadenceRpm;
			++Accumulator->Count;
		}

		if (Approach.Count == 0)
		{
			OutError = TEXT("missing observations for corner phase(s): approach");
			return false;
		}
		if (Entry.Count == 0)
		{
			OutError = TEXT("missing observations for corner phase(s): entry");
			return false;
		}
		if (Apex.Count == 0)
		{
			OutError = TEXT("missing observations for corner phase(s): apex");
			return false;
		}
		if (Exit.Count == 0)
		{
			OutError = TEXT("missing observations for corner phase(s): exit");
			return false;
		}

		FRouteCornerTechniqueSummary Candidate;
		Candidate.ApproachPowerW = Approach.PowerSum / Approach.Count;
		Candidate.EntryPowerW = Entry.PowerSum / Entry.Count;
		Candidate.ApexPowerW = Apex.PowerSum / Apex.Count;
		Candidate.ExitPowerW = Exit.PowerSum / Exit.Count;
		Candidate.ApproachCadenceRpm = Approach.CadenceSum / Approach.Count;
		Candidate.EntryCadenceRpm = Entry.CadenceSum / Entry.Count;
		Candidate.ApexCadenceRpm = Apex.CadenceSum / Apex.Count;
		Candidate.ExitCadenceRpm = Exit.CadenceSum / Exit.Count;

		if (!ValidateSummary(Candidate, OutError))
		{
			return false;
		}

		OutSummary = Candidate;
		return true;
	}

	bool TryScoreRouteCornerTechnique(
		const FRouteCornerTechniqueSummary& Summary,
		const CyclingCornerConsequence::FCornerGeometryConsequence& Consequence,
		FRouteCornerTechniqueScore& OutScore,
		FString& OutError)
	{
		OutScore = FRouteCornerTechniqueScore{};
		OutError.Reset();

		if (!ValidateSummary(Summary, OutError))
		{
			return false;
		}
		if (Summary.ApproachPowerW <= 0.0)
		{
			OutError = TEXT("approach_power_w must be positive for technique scoring");
			return false;
		}
		if (Summary.ApproachCadenceRpm <= 0.0)
		{
			OutError = TEXT("approach_cadence_rpm must be positive for technique scoring");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(
				Consequence.LineDeviationRatio,
				TEXT("line_deviation_ratio"),
				OutError)
			|| !CheckNonNegative(
				Consequence.ExitSpeedMultiplier,
				TEXT("exit_speed_multiplier"),
				OutError))
		{
			return false;
		}
		if (Consequence.LineDeviationRatio > 1.0)
		{
			OutError = TEXT("line_deviation_ratio must not exceed 1");
			return false;
		}
		if (Consequence.ExitSpeedMultiplier > 1.0)
		{
			OutError = TEXT("exit_speed_multiplier must not exceed 1");
			return false;
		}

		FRouteCornerTechniqueScore Candidate;
		Candidate.EntryPowerReleaseScore =
			ReleaseScore(Summary.EntryPowerW, Summary.ApproachPowerW);
		Candidate.ApexPowerReleaseScore =
			ReleaseScore(Summary.ApexPowerW, Summary.ApproachPowerW);
		Candidate.ExitPowerRecoveryScore =
			RecoveryScore(Summary.ExitPowerW, Summary.ApproachPowerW);
		Candidate.EntryCadenceReleaseScore =
			ReleaseScore(Summary.EntryCadenceRpm, Summary.ApproachCadenceRpm);
		Candidate.ApexCadenceReleaseScore =
			ReleaseScore(Summary.ApexCadenceRpm, Summary.ApproachCadenceRpm);
		Candidate.ExitCadenceRecoveryScore =
			RecoveryScore(Summary.ExitCadenceRpm, Summary.ApproachCadenceRpm);
		Candidate.LineRetentionScore = 100.0 * (1.0 - Consequence.LineDeviationRatio);
		Candidate.SpeedRetentionScore = 100.0 * Consequence.ExitSpeedMultiplier;

		Candidate.Score =
			(Candidate.EntryPowerReleaseScore
				+ Candidate.ApexPowerReleaseScore
				+ Candidate.ExitPowerRecoveryScore
				+ Candidate.EntryCadenceReleaseScore
				+ Candidate.ApexCadenceReleaseScore
				+ Candidate.ExitCadenceRecoveryScore
				+ Candidate.LineRetentionScore
				+ Candidate.SpeedRetentionScore)
			/ 8.0;

		if (!FMath::IsFinite(Candidate.Score)
			|| Candidate.Score < 0.0
			|| Candidate.Score > 100.0)
		{
			OutError = TEXT("derived technique score must be finite and lie in [0, 100]");
			return false;
		}

		OutScore = Candidate;
		return true;
	}
}
