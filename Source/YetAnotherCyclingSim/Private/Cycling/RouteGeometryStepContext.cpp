#include "Cycling/RouteGeometryStepContext.h"

#include <cmath>

namespace CyclingSimulation
{
	bool FRouteGeometrySimulationStepContextProvider::TryConfigure(
		const FRouteGeometryProfile& InGeometry,
		const FEnvironment& InBaseEnvironment,
		double InGradeHalfWindowM,
		FString& OutError)
	{
		OutError.Reset();

		if (!InGeometry.IsConfigured())
		{
			OutError = TEXT("route geometry context requires configured geometry");
			return false;
		}

		FString EnvironmentError;
		if (!InBaseEnvironment.Validate(EnvironmentError))
		{
			OutError = FString::Printf(
				TEXT("route geometry context base environment is invalid: %s"),
				*EnvironmentError);
			return false;
		}

		if (!std::isfinite(InGradeHalfWindowM) || InGradeHalfWindowM <= 0.0)
		{
			OutError = TEXT("route geometry context grade half-window must be finite and greater than zero");
			return false;
		}

		Geometry = InGeometry;
		BaseEnvironment = InBaseEnvironment;
		GradeHalfWindowM = InGradeHalfWindowM;
		bIsConfigured = true;
		return true;
	}

	bool FRouteGeometrySimulationStepContextProvider::TryResolveEnvironment(
		const FSimulationState& PreStepState,
		FEnvironment& OutEnvironment,
		FString& OutError) const
	{
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("route geometry context provider is not configured");
			return false;
		}

		FString StateError;
		if (!PreStepState.Validate(StateError))
		{
			OutError = FString::Printf(TEXT("pre-step state is invalid: %s"), *StateError);
			return false;
		}

		double GradeDecimal = 0.0;
		if (!Geometry.TryCalculateGrade(
			PreStepState.DistanceM,
			GradeHalfWindowM,
			GradeDecimal,
			OutError))
		{
			return false;
		}

		OutEnvironment = BaseEnvironment;
		OutEnvironment.GradeDecimal = GradeDecimal;
		return true;
	}

	bool FRouteGeometrySimulationStepContextProvider::TryObserveCompletedStep(
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
			OutError = TEXT("route geometry context provider is not configured");
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

		// Route boundary lifecycle belongs to Stage 3D (#66). Stage 3C only
		// supplies geometry-derived environment at fixed-step granularity.
		return true;
	}
}
