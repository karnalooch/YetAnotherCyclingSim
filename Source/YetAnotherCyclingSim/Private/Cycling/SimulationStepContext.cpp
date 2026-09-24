#include "Cycling/SimulationStepContext.h"

#include <cmath>

namespace CyclingSimulation
{
	namespace
	{
		bool IsFiniteNonNegative(double Value)
		{
			return std::isfinite(Value) && Value >= 0.0;
		}
	}

	bool FDistanceBasedSimulationStepContextProvider::TryConfigure(
		const TArray<FSimulationEnvironmentSection>& InEnvironmentSections,
		const TArray<FSimulationBoundaryDefinition>& InBoundaries,
		FString& OutError)
	{
		OutError.Reset();

		if (InEnvironmentSections.IsEmpty())
		{
			OutError = TEXT("environment sections must contain at least one section");
			return false;
		}

		if (InEnvironmentSections[0].StartDistanceM != 0.0)
		{
			OutError = TEXT("first environment section must start at exactly 0 m");
			return false;
		}

		double PreviousSectionStartM = -1.0;
		for (int32 Index = 0; Index < InEnvironmentSections.Num(); ++Index)
		{
			const FSimulationEnvironmentSection& Section = InEnvironmentSections[Index];

			if (!IsFiniteNonNegative(Section.StartDistanceM))
			{
				OutError = FString::Printf(
					TEXT("environment section %d start distance must be finite and non-negative"),
					Index);
				return false;
			}
			if (Index > 0 && Section.StartDistanceM <= PreviousSectionStartM)
			{
				OutError = FString::Printf(
					TEXT("environment section %d start distance must be strictly increasing"),
					Index);
				return false;
			}

			FString EnvironmentError;
			if (!Section.Environment.Validate(EnvironmentError))
			{
				OutError = FString::Printf(
					TEXT("environment section %d is invalid: %s"),
					Index,
					*EnvironmentError);
				return false;
			}

			PreviousSectionStartM = Section.StartDistanceM;
		}

		double PreviousBoundaryDistanceM = -1.0;
		for (int32 Index = 0; Index < InBoundaries.Num(); ++Index)
		{
			const FSimulationBoundaryDefinition& Boundary = InBoundaries[Index];
			const FString TrimmedId = Boundary.Id.TrimStartAndEnd();

			if (TrimmedId.IsEmpty())
			{
				OutError = FString::Printf(TEXT("boundary %d id must not be empty"), Index);
				return false;
			}
			if (!IsFiniteNonNegative(Boundary.DistanceM))
			{
				OutError = FString::Printf(
					TEXT("boundary %d distance must be finite and non-negative"),
					Index);
				return false;
			}
			if (Index > 0 && Boundary.DistanceM <= PreviousBoundaryDistanceM)
			{
				OutError = FString::Printf(
					TEXT("boundary %d distance must be strictly increasing"),
					Index);
				return false;
			}
			if (Boundary.bStopAfterCrossing && Boundary.Kind != ESimulationBoundaryKind::Finish)
			{
				OutError = FString::Printf(
					TEXT("boundary '%s' requests stop-after-crossing but is not a Finish boundary"),
					*TrimmedId);
				return false;
			}

			for (int32 EarlierIndex = 0; EarlierIndex < Index; ++EarlierIndex)
			{
				if (TrimmedId == InBoundaries[EarlierIndex].Id.TrimStartAndEnd())
				{
					OutError = FString::Printf(
						TEXT("boundary id '%s' must be unique"),
						*TrimmedId);
					return false;
				}
			}

			PreviousBoundaryDistanceM = Boundary.DistanceM;
		}

		TArray<FSimulationEnvironmentSection> CandidateSections = InEnvironmentSections;
		TArray<FSimulationBoundaryDefinition> CandidateBoundaries = InBoundaries;
		for (FSimulationBoundaryDefinition& Boundary : CandidateBoundaries)
		{
			Boundary.Id = Boundary.Id.TrimStartAndEnd();
		}

		EnvironmentSections = MoveTemp(CandidateSections);
		Boundaries = MoveTemp(CandidateBoundaries);
		bIsConfigured = true;
		return true;
	}

	bool FDistanceBasedSimulationStepContextProvider::TryResolveEnvironment(
		const FSimulationState& PreStepState,
		FEnvironment& OutEnvironment,
		FString& OutError) const
	{
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("step context provider is not configured");
			return false;
		}

		FString StateError;
		if (!PreStepState.Validate(StateError))
		{
			OutError = FString::Printf(TEXT("pre-step state is invalid: %s"), *StateError);
			return false;
		}

		int32 SelectedIndex = 0;
		for (int32 Index = 1; Index < EnvironmentSections.Num(); ++Index)
		{
			if (PreStepState.DistanceM < EnvironmentSections[Index].StartDistanceM)
			{
				break;
			}
			SelectedIndex = Index;
		}

		OutEnvironment = EnvironmentSections[SelectedIndex].Environment;
		return true;
	}

	bool FDistanceBasedSimulationStepContextProvider::TryObserveCompletedStep(
		const FSimulationState& PreStepState,
		const FSimulationState& PostStepState,
		TArray<FSimulationBoundaryCrossing>& OutCrossings,
		bool& bOutStopAfterStep,
		FString& OutError) const
	{
		OutError.Reset();
		OutCrossings.Reset();
		bOutStopAfterStep = false;

		if (!bIsConfigured)
		{
			OutError = TEXT("step context provider is not configured");
			return false;
		}

		FString StateError;
		if (!PreStepState.Validate(StateError))
		{
			OutError = FString::Printf(TEXT("pre-step state is invalid: %s"), *StateError);
			return false;
		}
		if (!PostStepState.Validate(StateError))
		{
			OutError = FString::Printf(TEXT("post-step state is invalid: %s"), *StateError);
			return false;
		}
		if (PostStepState.DistanceM < PreStepState.DistanceM)
		{
			OutError = TEXT("post-step distance must not be less than pre-step distance");
			return false;
		}

		for (const FSimulationBoundaryDefinition& Boundary : Boundaries)
		{
			if (PreStepState.DistanceM < Boundary.DistanceM
				&& PostStepState.DistanceM >= Boundary.DistanceM)
			{
				FSimulationBoundaryCrossing Crossing;
				Crossing.Id = Boundary.Id;
				Crossing.Kind = Boundary.Kind;
				Crossing.BoundaryDistanceM = Boundary.DistanceM;
				Crossing.PreStepState = PreStepState;
				Crossing.PostStepState = PostStepState;
				OutCrossings.Add(Crossing);

				if (Boundary.bStopAfterCrossing)
				{
					bOutStopAfterStep = true;
					break;
				}
			}
		}

		return true;
	}
}
