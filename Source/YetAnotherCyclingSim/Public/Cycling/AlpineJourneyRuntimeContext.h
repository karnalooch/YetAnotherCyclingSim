#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "Cycling/Environment.h"
#include "Cycling/RouteGeometryStepContext.h"
#include "Cycling/SimulationStepContext.h"

namespace CyclingSimulation
{
	// Builds the named Stage 3 route markers from the authoritative Alpine
	// route profile. Marker distances are derived from FRouteProfile rather
	// than copied from spline/presentation data.
	YETANOTHERCYCLINGSIM_API bool TryBuildAlpineJourneyRuntimeBoundaries(
		TArray<FSimulationBoundaryDefinition>& OutBoundaries,
		FString& OutError);

	// Stage 3D production context: geometry-derived environment + deterministic
	// route marker crossings, both resolved at fixed-step granularity.
	class YETANOTHERCYCLINGSIM_API FAlpineJourneySimulationStepContextProvider final
		: public ISimulationStepContextProvider
	{
	public:
		bool TryConfigure(
			const FEnvironment& InBaseEnvironment,
			double InGradeHalfWindowM,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		double GetRouteLengthM() const { return RouteLengthM; }
		const TArray<FSimulationBoundaryDefinition>& GetBoundaries() const
		{
			return Boundaries;
		}

		virtual bool TryResolveEnvironment(
			const FSimulationState& PreStepState,
			FEnvironment& OutEnvironment,
			FString& OutError) const override;

		virtual bool TryObserveCompletedStep(
			const FSimulationState& PreStepState,
			const FSimulationState& PostStepState,
			TArray<FSimulationBoundaryCrossing>& OutCrossings,
			bool& bOutStopAfterStep,
			FString& OutError) const override;

	private:
		FRouteGeometrySimulationStepContextProvider GeometryProvider;
		FDistanceBasedSimulationStepContextProvider BoundaryProvider;
		TArray<FSimulationBoundaryDefinition> Boundaries;
		double RouteLengthM = 0.0;
		bool bIsConfigured = false;
	};
}
