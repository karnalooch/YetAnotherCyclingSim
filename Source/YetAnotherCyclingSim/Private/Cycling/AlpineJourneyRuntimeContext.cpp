#include "Cycling/AlpineJourneyRuntimeContext.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/AlpineJourneyRoute.h"
#include "Cycling/RouteProfile.h"

namespace CyclingSimulation
{
	namespace
	{
		bool TryAddSectorAtSegmentStart(
			const FRouteProfile& Route,
			const TCHAR* BoundaryId,
			const TCHAR* SegmentId,
			TArray<FSimulationBoundaryDefinition>& OutBoundaries,
			FString& OutError)
		{
			for (const FRouteSegment& Segment : Route.GetSegments())
			{
				if (Segment.GetId() == SegmentId)
				{
					FSimulationBoundaryDefinition Boundary;
					Boundary.Id = BoundaryId;
					Boundary.Kind = ESimulationBoundaryKind::Sector;
					Boundary.DistanceM = Segment.GetStartDistanceM();
					Boundary.bStopAfterCrossing = false;
					OutBoundaries.Add(Boundary);
					return true;
				}
			}

			OutError = FString::Printf(
				TEXT("Alpine runtime marker '%s' references missing segment '%s'"),
				BoundaryId,
				SegmentId);
			return false;
		}
	}

	bool TryBuildAlpineJourneyRuntimeBoundaries(
		TArray<FSimulationBoundaryDefinition>& OutBoundaries,
		FString& OutError)
	{
		OutError.Reset();

		FRouteProfile Route;
		if (!TryBuildAlpineJourneyRouteProfile(Route, OutError))
		{
			OutBoundaries.Reset();
			return false;
		}

		TArray<FSimulationBoundaryDefinition> CandidateBoundaries;

		FSimulationBoundaryDefinition Start;
		Start.Id = TEXT("start");
		Start.Kind = ESimulationBoundaryKind::Start;
		Start.DistanceM = 0.0;
		Start.bStopAfterCrossing = false;
		CandidateBoundaries.Add(Start);

		if (!TryAddSectorAtSegmentStart(
				Route,
				TEXT("sector-meadow-rollers"),
				TEXT("Meadow Rollers"),
				CandidateBoundaries,
				OutError)
			|| !TryAddSectorAtSegmentStart(
				Route,
				TEXT("sector-challenge-climb"),
				TEXT("Challenge Climb"),
				CandidateBoundaries,
				OutError)
			|| !TryAddSectorAtSegmentStart(
				Route,
				TEXT("sector-high-valley-descent"),
				TEXT("High Valley Descent"),
				CandidateBoundaries,
				OutError)
			|| !TryAddSectorAtSegmentStart(
				Route,
				TEXT("sector-lakeside-finish"),
				TEXT("Lakeside Finish"),
				CandidateBoundaries,
				OutError))
		{
			OutBoundaries.Reset();
			return false;
		}

		FSimulationBoundaryDefinition Finish;
		Finish.Id = TEXT("finish");
		Finish.Kind = ESimulationBoundaryKind::Finish;
		Finish.DistanceM = Route.GetTotalLengthM();
		Finish.bStopAfterCrossing = true;
		CandidateBoundaries.Add(Finish);

		OutBoundaries = MoveTemp(CandidateBoundaries);
		return true;
	}

	bool FAlpineJourneySimulationStepContextProvider::TryConfigure(
		const FEnvironment& InBaseEnvironment,
		double InGradeHalfWindowM,
		FString& OutError)
	{
		OutError.Reset();

		FRouteGeometryProfile CandidateGeometry;
		if (!TryBuildAlpineJourneyRouteGeometry(CandidateGeometry, OutError))
		{
			return false;
		}

		FRouteGeometrySimulationStepContextProvider CandidateGeometryProvider;
		if (!CandidateGeometryProvider.TryConfigure(
				CandidateGeometry,
				InBaseEnvironment,
				InGradeHalfWindowM,
				OutError))
		{
			return false;
		}

		TArray<FSimulationBoundaryDefinition> CandidateBoundaries;
		if (!TryBuildAlpineJourneyRuntimeBoundaries(CandidateBoundaries, OutError))
		{
			return false;
		}

		TArray<FSimulationEnvironmentSection> BoundarySections;
		FSimulationEnvironmentSection BaseSection;
		BaseSection.StartDistanceM = 0.0;
		BaseSection.Environment = InBaseEnvironment;
		BoundarySections.Add(BaseSection);

		FDistanceBasedSimulationStepContextProvider CandidateBoundaryProvider;
		if (!CandidateBoundaryProvider.TryConfigure(
				BoundarySections,
				CandidateBoundaries,
				OutError))
		{
			return false;
		}

		GeometryProvider = CandidateGeometryProvider;
		BoundaryProvider = CandidateBoundaryProvider;
		Boundaries = CandidateBoundaries;
		RouteLengthM = CandidateGeometry.GetTotalLengthM();
		bIsConfigured = true;
		return true;
	}

	bool FAlpineJourneySimulationStepContextProvider::TryResolveEnvironment(
		const FSimulationState& PreStepState,
		FEnvironment& OutEnvironment,
		FString& OutError) const
	{
		if (!bIsConfigured)
		{
			OutError = TEXT("Alpine runtime route context is not configured");
			return false;
		}

		return GeometryProvider.TryResolveEnvironment(
			PreStepState,
			OutEnvironment,
			OutError);
	}

	bool FAlpineJourneySimulationStepContextProvider::TryObserveCompletedStep(
		const FSimulationState& PreStepState,
		const FSimulationState& PostStepState,
		TArray<FSimulationBoundaryCrossing>& OutCrossings,
		bool& bOutStopAfterStep,
		FString& OutError) const
	{
		if (!bIsConfigured)
		{
			OutError = TEXT("Alpine runtime route context is not configured");
			OutCrossings.Reset();
			bOutStopAfterStep = false;
			return false;
		}

		return BoundaryProvider.TryObserveCompletedStep(
			PreStepState,
			PostStepState,
			OutCrossings,
			bOutStopAfterStep,
			OutError);
	}
}
