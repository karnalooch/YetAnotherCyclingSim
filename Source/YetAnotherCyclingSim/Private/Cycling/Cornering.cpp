#include "Cycling/Cornering.h"

#include "Cycling/CyclingForces.h"
#include "Cycling/PhysicsValidation.h"
#include "Math/UnrealMathUtility.h"

#include <cmath>
#include <limits>

namespace CyclingCornering
{
	namespace
	{
		double BaselineRatio(double Numerator, double Baseline)
		{
			if (Baseline == 0.0)
			{
				return Numerator == 0.0 ? 0.0 : std::numeric_limits<double>::infinity();
			}
			return Numerator / Baseline;
		}

		double LowerIsBetterFactor(double Value, double FullAt, double ZeroAt)
		{
			if (Value <= FullAt)
			{
				return 1.0;
			}
			if (Value >= ZeroAt)
			{
				return 0.0;
			}
			return (ZeroAt - Value) / (ZeroAt - FullAt);
		}

		double HigherIsBetterFactor(double Value, double ZeroAt, double FullAt)
		{
			if (Value <= ZeroAt)
			{
				return 0.0;
			}
			if (Value >= FullAt)
			{
				return 1.0;
			}
			return (Value - ZeroAt) / (FullAt - ZeroAt);
		}

		double GripFactor(double GripUsage)
		{
			if (GripUsage <= 0.85)
			{
				return 1.0;
			}
			if (GripUsage <= 1.0)
			{
				return 1.0 - (GripUsage - 0.85) / 0.15 * 0.5;
			}
			if (GripUsage < 1.25)
			{
				return 0.5 - (GripUsage - 1.0) / 0.25 * 0.5;
			}
			return 0.0;
		}

		bool ValidateConfiguredCorner(const FCorner& Corner, FString& OutError)
		{
			if (!Corner.IsConfigured())
			{
				OutError = TEXT("corner is not configured");
				return false;
			}
			return true;
		}

		bool ValidateTechniqueSummary(const FCornerTechniqueSummary& Summary, FString& OutError)
		{
			using namespace CyclingPhysicsValidation;
			return CheckNonNegative(Summary.ApproachPowerW, TEXT("approach_power_w"), OutError)
				&& CheckNonNegative(Summary.EntryPowerW, TEXT("entry_power_w"), OutError)
				&& CheckNonNegative(Summary.ApexPowerW, TEXT("apex_power_w"), OutError)
				&& CheckNonNegative(Summary.ExitPowerW, TEXT("exit_power_w"), OutError)
				&& CheckNonNegative(Summary.ApproachCadenceRpm, TEXT("approach_cadence_rpm"), OutError)
				&& CheckNonNegative(Summary.EntryCadenceRpm, TEXT("entry_cadence_rpm"), OutError)
				&& CheckNonNegative(Summary.ApexCadenceRpm, TEXT("apex_cadence_rpm"), OutError)
				&& CheckNonNegative(Summary.ExitCadenceRpm, TEXT("exit_cadence_rpm"), OutError)
				&& CheckNonNegative(Summary.MaxGripUsage, TEXT("max_grip_usage"), OutError);
		}

		bool ValidateConsequence(const FCornerConsequence& Consequence, FString& OutError)
		{
			using namespace CyclingPhysicsValidation;
			if (!CheckClosedUnitInterval(
				Consequence.ExitSpeedMultiplier,
				TEXT("exit_speed_multiplier"),
				OutError))
			{
				return false;
			}
			if (!CheckClosedUnitInterval(
				Consequence.LineDeviationRatio,
				TEXT("line_deviation_ratio"),
				OutError))
			{
				return false;
			}

			switch (Consequence.Outcome)
			{
			case ECornerOutcome::Clean:
			case ECornerOutcome::WideLine:
			case ECornerOutcome::ControlledSlip:
				break;
			default:
				OutError = TEXT("corner outcome is invalid");
				return false;
			}

			switch (Consequence.HudFeedback)
			{
			case ECornerHudFeedback::CleanCorner:
			case ECornerHudFeedback::WiderSlowerLine:
			case ECornerHudFeedback::RearWheelSlip:
				break;
			default:
				OutError = TEXT("corner HUD feedback is invalid");
				return false;
			}

			return true;
		}
	}

	bool FCornerProfile::TryConfigure(
		const FString& InName,
		double InTotalLengthM,
		const TArray<FCornerDefinition>& InCorners,
		FString& OutError)
	{
		OutError.Reset();

		const FString TrimmedName = InName.TrimStartAndEnd();
		if (TrimmedName.IsEmpty())
		{
			OutError = TEXT("corner profile name must not be empty");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckPositive(InTotalLengthM, TEXT("total_length_m"), OutError))
		{
			return false;
		}

		TArray<FCorner> CandidateCorners;
		CandidateCorners.Reserve(InCorners.Num());

		for (int32 Index = 0; Index < InCorners.Num(); ++Index)
		{
			const FCornerDefinition& Definition = InCorners[Index];
			const FString TrimmedCornerName = Definition.Name.TrimStartAndEnd();
			if (TrimmedCornerName.IsEmpty())
			{
				OutError = FString::Printf(
					TEXT("corner %d name must not be empty"),
					Index);
				return false;
			}
			if (!CheckNonNegative(
				Definition.StartDistanceM,
				TEXT("start_distance_m"),
				OutError))
			{
				return false;
			}
			if (!CheckPositive(Definition.LengthM, TEXT("length_m"), OutError))
			{
				return false;
			}
			if (!CheckPositive(Definition.RadiusM, TEXT("radius_m"), OutError))
			{
				return false;
			}

			const double EndDistanceM = Definition.StartDistanceM + Definition.LengthM;
			if (!std::isfinite(EndDistanceM))
			{
				OutError = FString::Printf(
					TEXT("corner '%s' end distance must be finite"),
					*TrimmedCornerName);
				return false;
			}
			if (EndDistanceM > InTotalLengthM)
			{
				OutError = FString::Printf(
					TEXT("corner '%s' end distance %.6f m must not exceed total profile length %.6f m"),
					*TrimmedCornerName,
					EndDistanceM,
					InTotalLengthM);
				return false;
			}

			if (CandidateCorners.Num() > 0)
			{
				const FCorner& Previous = CandidateCorners.Last();
				if (Definition.StartDistanceM < Previous.GetStartDistanceM())
				{
					OutError = TEXT("corners must be ordered by ascending start distance");
					return false;
				}
				if (Definition.StartDistanceM < Previous.GetEndDistanceM())
				{
					OutError = TEXT("corners must not overlap");
					return false;
				}
			}

			FCorner Corner;
			Corner.Name = TrimmedCornerName;
			Corner.StartDistanceM = Definition.StartDistanceM;
			Corner.LengthM = Definition.LengthM;
			Corner.RadiusM = Definition.RadiusM;
			Corner.bIsConfigured = true;
			CandidateCorners.Add(MoveTemp(Corner));
		}

		Name = TrimmedName;
		TotalLengthM = InTotalLengthM;
		Corners = MoveTemp(CandidateCorners);
		bIsConfigured = true;
		return true;
	}

	bool FCornerProfile::TryGetCornerAtDistance(
		double DistanceM,
		const FCorner*& OutCorner,
		int32& OutCornerIndex,
		FString& OutError) const
	{
		OutError.Reset();
		OutCorner = nullptr;
		OutCornerIndex = INDEX_NONE;

		if (!bIsConfigured)
		{
			OutError = TEXT("corner profile is not configured");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(DistanceM, TEXT("distance_m"), OutError))
		{
			return false;
		}
		if (DistanceM > TotalLengthM)
		{
			OutError = FString::Printf(
				TEXT("distance_m must not exceed total profile length %.6f m"),
				TotalLengthM);
			return false;
		}

		for (int32 Index = 0; Index < Corners.Num(); ++Index)
		{
			const FCorner& Corner = Corners[Index];
			if (Corner.GetStartDistanceM() <= DistanceM
				&& DistanceM < Corner.GetEndDistanceM())
			{
				OutCorner = &Corner;
				OutCornerIndex = Index;
				return true;
			}
		}

		return true;
	}

	double FCornerTechniqueSummary::GetEntryPowerRatio() const
	{
		return BaselineRatio(EntryPowerW, ApproachPowerW);
	}

	double FCornerTechniqueSummary::GetApexPowerRatio() const
	{
		return BaselineRatio(ApexPowerW, ApproachPowerW);
	}

	double FCornerTechniqueSummary::GetExitPowerRatio() const
	{
		return BaselineRatio(ExitPowerW, ApproachPowerW);
	}

	double FCornerTechniqueSummary::GetEntryCadenceRatio() const
	{
		return BaselineRatio(EntryCadenceRpm, ApproachCadenceRpm);
	}

	double FCornerTechniqueSummary::GetApexCadenceRatio() const
	{
		return BaselineRatio(ApexCadenceRpm, ApproachCadenceRpm);
	}

	double FCornerTechniqueSummary::GetExitCadenceRatio() const
	{
		return BaselineRatio(ExitCadenceRpm, ApproachCadenceRpm);
	}

	bool TryCalculateEffectiveFrictionCoefficient(
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutEffectiveFrictionCoefficient,
		FString& OutError)
	{
		OutEffectiveFrictionCoefficient = 0.0;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckPositive(
			BaseFrictionCoefficient,
			TEXT("base_friction_coefficient"),
			OutError))
		{
			return false;
		}
		if (!CheckOpenUpperUnitInterval(
			GripMultiplier,
			TEXT("grip_multiplier"),
			OutError))
		{
			return false;
		}

		OutEffectiveFrictionCoefficient = BaseFrictionCoefficient * GripMultiplier;
		return true;
	}

	bool TryCalculateMaximumCornerSpeedMps(
		double RadiusM,
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutMaximumSpeedMps,
		FString& OutError)
	{
		OutMaximumSpeedMps = 0.0;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckPositive(RadiusM, TEXT("radius_m"), OutError))
		{
			return false;
		}

		double EffectiveFriction = 0.0;
		if (!TryCalculateEffectiveFrictionCoefficient(
			BaseFrictionCoefficient,
			GripMultiplier,
			EffectiveFriction,
			OutError))
		{
			return false;
		}

		OutMaximumSpeedMps = std::sqrt(
			EffectiveFriction * CyclingForces::StandardGravityMps2 * RadiusM);
		return true;
	}

	bool TryCalculateCornerGripUsage(
		double SpeedMps,
		double RadiusM,
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutGripUsage,
		FString& OutError)
	{
		OutGripUsage = 0.0;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
		{
			return false;
		}
		if (!CheckPositive(RadiusM, TEXT("radius_m"), OutError))
		{
			return false;
		}

		double EffectiveFriction = 0.0;
		if (!TryCalculateEffectiveFrictionCoefficient(
			BaseFrictionCoefficient,
			GripMultiplier,
			EffectiveFriction,
			OutError))
		{
			return false;
		}

		OutGripUsage = SpeedMps * SpeedMps
			/ (EffectiveFriction * CyclingForces::StandardGravityMps2 * RadiusM);
		return true;
	}

	bool TryClassifyCornerGripUsage(
		double GripUsage,
		ECornerGripStatus& OutStatus,
		FString& OutError)
	{
		OutStatus = ECornerGripStatus::Safe;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(GripUsage, TEXT("grip_usage"), OutError))
		{
			return false;
		}

		if (GripUsage < 0.85)
		{
			OutStatus = ECornerGripStatus::Safe;
		}
		else if (GripUsage <= 1.0)
		{
			OutStatus = ECornerGripStatus::NearLimit;
		}
		else
		{
			OutStatus = ECornerGripStatus::GripExceeded;
		}
		return true;
	}

	bool TryGetCornerPhase(
		const FCorner& Corner,
		double DistanceM,
		double ApproachLengthM,
		ECornerPhase& OutPhase,
		FString& OutError)
	{
		OutPhase = ECornerPhase::Outside;
		OutError.Reset();

		if (!ValidateConfiguredCorner(Corner, OutError))
		{
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(DistanceM, TEXT("distance_m"), OutError))
		{
			return false;
		}
		if (!CheckPositive(ApproachLengthM, TEXT("approach_length_m"), OutError))
		{
			return false;
		}

		const double StartM = Corner.GetStartDistanceM();
		const double LengthM = Corner.GetLengthM();
		const double EndM = Corner.GetEndDistanceM();
		const double ApproachStartM = FMath::Max(0.0, StartM - ApproachLengthM);

		if (DistanceM < StartM)
		{
			OutPhase = DistanceM >= ApproachStartM
				? ECornerPhase::Approach
				: ECornerPhase::Outside;
			return true;
		}
		if (DistanceM < StartM + 0.25 * LengthM)
		{
			OutPhase = ECornerPhase::Entry;
			return true;
		}
		if (DistanceM < StartM + 0.75 * LengthM)
		{
			OutPhase = ECornerPhase::Apex;
			return true;
		}
		if (DistanceM < EndM)
		{
			OutPhase = ECornerPhase::Exit;
			return true;
		}

		OutPhase = ECornerPhase::Outside;
		return true;
	}

	bool TryGetDistanceToCornerStartM(
		const FCorner& Corner,
		double DistanceM,
		double& OutDistanceM,
		FString& OutError)
	{
		OutDistanceM = 0.0;
		OutError.Reset();

		if (!ValidateConfiguredCorner(Corner, OutError))
		{
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(DistanceM, TEXT("distance_m"), OutError))
		{
			return false;
		}

		if (DistanceM < Corner.GetStartDistanceM())
		{
			OutDistanceM = Corner.GetStartDistanceM() - DistanceM;
		}
		return true;
	}

	bool TrySummarizeCornerTechnique(
		const FCorner& Corner,
		const TArray<FCornerTechniqueSample>& Samples,
		double ApproachLengthM,
		FCornerTechniqueSummary& OutSummary,
		FString& OutError)
	{
		OutSummary = FCornerTechniqueSummary{};
		OutError.Reset();

		if (!ValidateConfiguredCorner(Corner, OutError))
		{
			return false;
		}
		if (Samples.Num() == 0)
		{
			OutError = TEXT("samples must contain at least one corner technique sample");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckPositive(ApproachLengthM, TEXT("approach_length_m"), OutError))
		{
			return false;
		}

		struct FPhaseAccumulator
		{
			double PowerSum = 0.0;
			double CadenceSum = 0.0;
			int32 Count = 0;
		};

		FPhaseAccumulator Approach;
		FPhaseAccumulator Entry;
		FPhaseAccumulator Apex;
		FPhaseAccumulator Exit;
		double MaxGripUsage = 0.0;

		for (int32 Index = 0; Index < Samples.Num(); ++Index)
		{
			const FCornerTechniqueSample& Sample = Samples[Index];
			if (!CheckNonNegative(Sample.DistanceM, TEXT("distance_m"), OutError)
				|| !CheckNonNegative(Sample.PowerW, TEXT("power_w"), OutError)
				|| !CheckNonNegative(Sample.CadenceRpm, TEXT("cadence_rpm"), OutError)
				|| !CheckNonNegative(Sample.GripUsage, TEXT("grip_usage"), OutError))
			{
				return false;
			}
			if (Index > 0 && Sample.DistanceM < Samples[Index - 1].DistanceM)
			{
				OutError = TEXT("samples must be ordered by non-decreasing distance_m");
				return false;
			}

			ECornerPhase Phase = ECornerPhase::Outside;
			if (!TryGetCornerPhase(
				Corner,
				Sample.DistanceM,
				ApproachLengthM,
				Phase,
				OutError))
			{
				return false;
			}

			FPhaseAccumulator* Accumulator = nullptr;
			switch (Phase)
			{
			case ECornerPhase::Approach:
				Accumulator = &Approach;
				break;
			case ECornerPhase::Entry:
				Accumulator = &Entry;
				MaxGripUsage = FMath::Max(MaxGripUsage, Sample.GripUsage);
				break;
			case ECornerPhase::Apex:
				Accumulator = &Apex;
				MaxGripUsage = FMath::Max(MaxGripUsage, Sample.GripUsage);
				break;
			case ECornerPhase::Exit:
				Accumulator = &Exit;
				MaxGripUsage = FMath::Max(MaxGripUsage, Sample.GripUsage);
				break;
			case ECornerPhase::Outside:
				break;
			}

			if (Accumulator != nullptr)
			{
				Accumulator->PowerSum += Sample.PowerW;
				Accumulator->CadenceSum += Sample.CadenceRpm;
				++Accumulator->Count;
			}
		}

		if (Approach.Count == 0)
		{
			OutError = TEXT("missing samples for corner phase(s): approach");
			return false;
		}
		if (Entry.Count == 0)
		{
			OutError = TEXT("missing samples for corner phase(s): entry");
			return false;
		}
		if (Apex.Count == 0)
		{
			OutError = TEXT("missing samples for corner phase(s): apex");
			return false;
		}
		if (Exit.Count == 0)
		{
			OutError = TEXT("missing samples for corner phase(s): exit");
			return false;
		}

		FCornerTechniqueSummary Candidate;
		Candidate.ApproachPowerW = Approach.PowerSum / Approach.Count;
		Candidate.EntryPowerW = Entry.PowerSum / Entry.Count;
		Candidate.ApexPowerW = Apex.PowerSum / Apex.Count;
		Candidate.ExitPowerW = Exit.PowerSum / Exit.Count;
		Candidate.ApproachCadenceRpm = Approach.CadenceSum / Approach.Count;
		Candidate.EntryCadenceRpm = Entry.CadenceSum / Entry.Count;
		Candidate.ApexCadenceRpm = Apex.CadenceSum / Apex.Count;
		Candidate.ExitCadenceRpm = Exit.CadenceSum / Exit.Count;
		Candidate.MaxGripUsage = MaxGripUsage;

		if (!ValidateTechniqueSummary(Candidate, OutError))
		{
			return false;
		}

		OutSummary = Candidate;
		return true;
	}

	bool TryAssessCornerTechnique(
		const FCornerTechniqueSummary& Summary,
		FCornerTechniqueAssessment& OutAssessment,
		FString& OutError)
	{
		OutAssessment = FCornerTechniqueAssessment{};
		OutError.Reset();

		if (!ValidateTechniqueSummary(Summary, OutError))
		{
			return false;
		}

		const double EntryPowerRatio = Summary.GetEntryPowerRatio();
		const double EntryCadenceRatio = Summary.GetEntryCadenceRatio();
		const double ApexPowerRatio = Summary.GetApexPowerRatio();
		const double ApexCadenceRatio = Summary.GetApexCadenceRatio();
		const double ExitPowerRatio = Summary.GetExitPowerRatio();
		const double ExitCadenceRatio = Summary.GetExitCadenceRatio();

		const double RawScore =
			40.0 * GripFactor(Summary.MaxGripUsage)
			+ 15.0 * LowerIsBetterFactor(EntryPowerRatio, 0.60, 1.00)
			+ 5.0 * LowerIsBetterFactor(EntryCadenceRatio, 0.85, 1.05)
			+ 10.0 * LowerIsBetterFactor(ApexPowerRatio, 0.35, 0.85)
			+ 5.0 * LowerIsBetterFactor(ApexCadenceRatio, 0.70, 1.00)
			+ 15.0 * HigherIsBetterFactor(ExitPowerRatio, 0.40, 0.90)
			+ 10.0 * HigherIsBetterFactor(ExitCadenceRatio, 0.50, 0.90);

		FCornerTechniqueAssessment Candidate;
		Candidate.Score = FMath::Clamp(RawScore, 0.0, 100.0);
		if (Candidate.Score >= 90.0)
		{
			Candidate.Rating = ECornerTechniqueRating::Excellent;
		}
		else if (Candidate.Score >= 75.0)
		{
			Candidate.Rating = ECornerTechniqueRating::Good;
		}
		else if (Candidate.Score >= 50.0)
		{
			Candidate.Rating = ECornerTechniqueRating::NeedsImprovement;
		}
		else
		{
			Candidate.Rating = ECornerTechniqueRating::Poor;
		}

		if (Summary.MaxGripUsage > 1.0)
		{
			Candidate.Feedback = ECornerTechniqueFeedback::ReduceSpeed;
		}
		else if (EntryPowerRatio > 0.60 || EntryCadenceRatio > 0.85)
		{
			Candidate.Feedback = ECornerTechniqueFeedback::ReleaseEarlier;
		}
		else if (ApexPowerRatio > 0.35 || ApexCadenceRatio > 0.70)
		{
			Candidate.Feedback = ECornerTechniqueFeedback::StayOffPowerAtApex;
		}
		else if (ExitPowerRatio < 0.90 || ExitCadenceRatio < 0.90)
		{
			Candidate.Feedback = ECornerTechniqueFeedback::AccelerateOnExit;
		}
		else
		{
			Candidate.Feedback = ECornerTechniqueFeedback::GoodTechnique;
		}

		if (!TryClassifyCornerGripUsage(
			Summary.MaxGripUsage,
			Candidate.GripStatus,
			OutError))
		{
			return false;
		}

		OutAssessment = Candidate;
		return true;
	}

	bool TryCalculateCornerConsequence(
		double GripUsage,
		FCornerConsequence& OutConsequence,
		FString& OutError)
	{
		OutConsequence = FCornerConsequence{};
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(GripUsage, TEXT("grip_usage"), OutError))
		{
			return false;
		}

		FCornerConsequence Candidate;
		if (GripUsage <= 1.0)
		{
			Candidate.Outcome = ECornerOutcome::Clean;
			Candidate.ExitSpeedMultiplier = 1.0;
			Candidate.LineDeviationRatio = 0.0;
			Candidate.HudFeedback = ECornerHudFeedback::CleanCorner;
		}
		else if (GripUsage <= 1.15)
		{
			const double Progress = (GripUsage - 1.0) / 0.15;
			Candidate.Outcome = ECornerOutcome::WideLine;
			Candidate.ExitSpeedMultiplier = 1.0 - Progress * 0.15;
			Candidate.LineDeviationRatio = Progress * 0.5;
			Candidate.HudFeedback = ECornerHudFeedback::WiderSlowerLine;
		}
		else
		{
			const double Progress = FMath::Clamp(
				(GripUsage - 1.15) / 0.35,
				0.0,
				1.0);
			Candidate.Outcome = ECornerOutcome::ControlledSlip;
			Candidate.ExitSpeedMultiplier = 0.85 - Progress * 0.25;
			Candidate.LineDeviationRatio = 0.5 + Progress * 0.5;
			Candidate.HudFeedback = ECornerHudFeedback::RearWheelSlip;
		}

		OutConsequence = Candidate;
		return true;
	}

	bool TryApplyCornerExitSpeedMps(
		double SpeedMps,
		const FCornerConsequence& Consequence,
		double& OutSpeedMps,
		FString& OutError)
	{
		OutSpeedMps = 0.0;
		OutError.Reset();

		using namespace CyclingPhysicsValidation;
		if (!CheckNonNegative(SpeedMps, TEXT("speed_mps"), OutError))
		{
			return false;
		}
		if (!ValidateConsequence(Consequence, OutError))
		{
			return false;
		}

		OutSpeedMps = SpeedMps * Consequence.ExitSpeedMultiplier;
		return true;
	}
}
