#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"
#include "Cycling/Environment.h"
#include "Cycling/SimulationState.h"

namespace CyclingSimulation
{
	enum class ESimulationBoundaryKind : uint8
	{
		Start,
		Sector,
		Finish,
	};

	struct YETANOTHERCYCLINGSIM_API FSimulationEnvironmentSection
	{
		double StartDistanceM = 0.0;
		FEnvironment Environment;
	};

	struct YETANOTHERCYCLINGSIM_API FSimulationBoundaryDefinition
	{
		FString Id;
		ESimulationBoundaryKind Kind = ESimulationBoundaryKind::Sector;
		double DistanceM = 0.0;

		// When true, the runner commits the crossing step and returns immediately
		// without executing later fixed steps from the same render-frame batch.
		// Remaining accumulated frame time is preserved and reported explicitly.
		bool bStopAfterCrossing = false;
	};

	struct YETANOTHERCYCLINGSIM_API FSimulationBoundaryCrossing
	{
		FString Id;
		ESimulationBoundaryKind Kind = ESimulationBoundaryKind::Sector;
		double BoundaryDistanceM = 0.0;
		FSimulationState PreStepState;
		FSimulationState PostStepState;
	};

	// Pure, rendering-independent context source invoked at fixed-step granularity.
	//
	// Implementations must derive context only from deterministic domain data and
	// the authoritative simulation state supplied to each call. They must not read
	// Actor transforms, rendering state, wall-clock time or frame-rate-dependent
	// state. Implementations are expected to be logically const/transaction-safe:
	// a failed runner advance must not leave externally visible provider mutations.
	class YETANOTHERCYCLINGSIM_API ISimulationStepContextProvider
	{
	public:
		virtual ~ISimulationStepContextProvider() = default;

		// Resolves the environment for exactly one fixed step from the
		// authoritative state at the START of that step.
		virtual bool TryResolveEnvironment(
			const FSimulationState& PreStepState,
			FEnvironment& OutEnvironment,
			FString& OutError) const = 0;

		// Observes one successfully-computed fixed step and returns any route
		// boundary crossings attributable to that step. Crossing semantics are:
		// - Start at 0 m: emitted on the first forward step whose pre-step
		//   distance is exactly 0 m;
		// - other boundaries: PreStepState.DistanceM < boundary <=
		//   PostStepState.DistanceM.
		//
		// Setting bOutStopAfterStep asks the runner to commit this step and stop
		// processing further fixed steps from the same frame batch. The runner
		// preserves (does not silently drop) any unprocessed accumulated time.
		virtual bool TryObserveCompletedStep(
			const FSimulationState& PreStepState,
			const FSimulationState& PostStepState,
			TArray<FSimulationBoundaryCrossing>& OutCrossings,
			bool& bOutStopAfterStep,
			FString& OutError) const = 0;
	};

	// Minimal Stage 3 distance-based provider. It is intentionally generic:
	// Stage 3B may construct these sections/boundaries from the real Alpine
	// route profile without changing the fixed-step runner contract.
	class YETANOTHERCYCLINGSIM_API FDistanceBasedSimulationStepContextProvider final
		: public ISimulationStepContextProvider
	{
	public:
		// Accepts ordered environment sections and ordered route boundaries.
		//
		// Environment sections:
		// - at least one is required;
		// - the first must start at exactly 0 m;
		// - starts must be finite, non-negative and strictly increasing;
		// - every environment must validate.
		//
		// Boundaries:
		// - distance must be finite and non-negative;
		// - Id must be non-empty after trimming;
		// - distances must be strictly increasing;
		// - Ids must be unique;
		// - Start boundaries are allowed only at exactly 0 m;
		// - only Finish boundaries may request bStopAfterCrossing.
		//
		// Configuration is transactional. On failure the previous valid
		// configuration is preserved.
		bool TryConfigure(
			const TArray<FSimulationEnvironmentSection>& InEnvironmentSections,
			const TArray<FSimulationBoundaryDefinition>& InBoundaries,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }

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
		TArray<FSimulationEnvironmentSection> EnvironmentSections;
		TArray<FSimulationBoundaryDefinition> Boundaries;
		bool bIsConfigured = false;
	};
}
