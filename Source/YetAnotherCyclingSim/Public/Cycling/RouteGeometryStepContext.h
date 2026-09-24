#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/Environment.h"
#include "Cycling/RouteGeometry.h"
#include "Cycling/SimulationStepContext.h"

namespace CyclingSimulation
{
	// Fixed-step context provider that derives road grade from deterministic
	// route geometry at the authoritative pre-step DistanceM.
	//
	// All other FEnvironment fields come from BaseEnvironment. This keeps
	// Stage 3C focused on geometry-derived grade; weather remains Stage 8.
	class YETANOTHERCYCLINGSIM_API FRouteGeometrySimulationStepContextProvider final
		: public ISimulationStepContextProvider
	{
	public:
		bool TryConfigure(
			const FRouteGeometryProfile& InGeometry,
			const FEnvironment& InBaseEnvironment,
			double InGradeHalfWindowM,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		double GetGradeHalfWindowM() const { return GradeHalfWindowM; }

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
		FRouteGeometryProfile Geometry;
		FEnvironment BaseEnvironment;
		double GradeHalfWindowM = 0.0;
		bool bIsConfigured = false;
	};
}
