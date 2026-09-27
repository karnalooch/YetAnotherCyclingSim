#include "Cycling/SurfaceGripPolicy.h"

#include "Cycling/PhysicsValidation.h"
#include "Math/UnrealMathUtility.h"

namespace CyclingSurfaceGrip
{
	bool FSurfaceGripPolicy::TryConfigure(
		const FString& InName,
		const TArray<FSurfaceGripRuleDefinition>& InRules,
		FString& OutError)
	{
		OutError.Reset();

		const FString TrimmedName = InName.TrimStartAndEnd();
		if (TrimmedName.IsEmpty())
		{
			OutError = TEXT("surface grip policy name must not be empty");
			return false;
		}
		if (InRules.Num() == 0)
		{
			OutError = TEXT("surface grip policy must contain at least one rule");
			return false;
		}

		TArray<FSurfaceGripRule> CandidateRules;
		CandidateRules.Reserve(InRules.Num());

		for (int32 Index = 0; Index < InRules.Num(); ++Index)
		{
			const FSurfaceGripRuleDefinition& Definition = InRules[Index];
			const FString SurfaceId = Definition.SurfaceId.TrimStartAndEnd();
			if (SurfaceId.IsEmpty())
			{
				OutError = FString::Printf(
					TEXT("surface grip rule %d surface id must not be empty"),
					Index);
				return false;
			}

			using namespace CyclingPhysicsValidation;
			if (!CheckOpenUpperUnitInterval(
				Definition.DryGripMultiplier,
				TEXT("dry_grip_multiplier"),
				OutError)
				|| !CheckOpenUpperUnitInterval(
					Definition.FullyWetGripMultiplier,
					TEXT("fully_wet_grip_multiplier"),
					OutError))
			{
				return false;
			}

			for (const FSurfaceGripRule& Existing : CandidateRules)
			{
				if (Existing.SurfaceId == SurfaceId)
				{
					OutError = FString::Printf(
						TEXT("duplicate surface id '%s' in surface grip policy"),
						*SurfaceId);
					return false;
				}
			}

			FSurfaceGripRule Rule;
			Rule.SurfaceId = SurfaceId;
			Rule.DryGripMultiplier = Definition.DryGripMultiplier;
			Rule.FullyWetGripMultiplier = Definition.FullyWetGripMultiplier;
			CandidateRules.Add(MoveTemp(Rule));
		}

		Name = TrimmedName;
		Rules = MoveTemp(CandidateRules);
		bIsConfigured = true;
		return true;
	}

	bool FSurfaceGripPolicy::TryResolve(
		const FString& SurfaceId,
		double Wetness,
		FResolvedSurfaceGrip& OutGrip,
		FString& OutError) const
	{
		OutGrip = FResolvedSurfaceGrip{};
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("surface grip policy is not configured");
			return false;
		}

		const FString TrimmedSurfaceId = SurfaceId.TrimStartAndEnd();
		if (TrimmedSurfaceId.IsEmpty())
		{
			OutError = TEXT("surface id must not be empty");
			return false;
		}

		using namespace CyclingPhysicsValidation;
		if (!CheckClosedUnitInterval(Wetness, TEXT("wetness"), OutError))
		{
			return false;
		}

		const FSurfaceGripRule* MatchedRule = nullptr;
		for (const FSurfaceGripRule& Rule : Rules)
		{
			if (Rule.SurfaceId == TrimmedSurfaceId)
			{
				MatchedRule = &Rule;
				break;
			}
		}

		if (MatchedRule == nullptr)
		{
			OutError = FString::Printf(
				TEXT("surface id '%s' is not configured in grip policy '%s'"),
				*TrimmedSurfaceId,
				*Name);
			return false;
		}

		OutGrip.SurfaceId = MatchedRule->SurfaceId;
		OutGrip.Wetness = Wetness;
		OutGrip.DryGripMultiplier = MatchedRule->DryGripMultiplier;
		OutGrip.FullyWetGripMultiplier = MatchedRule->FullyWetGripMultiplier;
		OutGrip.GripMultiplier = FMath::Lerp(
			MatchedRule->DryGripMultiplier,
			MatchedRule->FullyWetGripMultiplier,
			Wetness);
		return true;
	}

	bool TryBuildAlpineSurfaceGripPolicy(
		FSurfaceGripPolicy& OutPolicy,
		FString& OutError)
	{
		TArray<FSurfaceGripRuleDefinition> Rules;
		Rules.Add({TEXT("asphalt"), 1.0, 0.75});

		FSurfaceGripPolicy Candidate;
		if (!Candidate.TryConfigure(
			TEXT("Alpine Journey Surface Grip"),
			Rules,
			OutError))
		{
			return false;
		}

		OutPolicy = MoveTemp(Candidate);
		return true;
	}
}
