#pragma once

#include "Containers/UnrealString.h"
#include "Math/Vector.h"

#include "Cycling/RouteGeometry.h"

namespace CyclingStage3G
{
	// Result of a deterministic horizontal route-clearance query for world
	// generation. The caller owns the protected corridor width; no hidden
	// vegetation/roadside distance is embedded in this contract.
	struct YETANOTHERCYCLINGSIM_API FRouteExclusionResult
	{
		double HorizontalDistanceToRouteM = 0.0;
		double ProtectedHalfWidthM = 0.0;
		double ClearanceFromProtectedCorridorM = 0.0;
		bool bExcluded = false;
	};

	// Evaluates whether a world-generation candidate lies inside the protected
	// horizontal corridor around the canonical Stage 3 route geometry.
	//
	// CandidatePositionM and route geometry use the same metre-space geometry
	// contract. This helper never reads render meshes, terrain, PCG output or
	// Actor transforms and therefore cannot become a second source of route
	// truth.
	YETANOTHERCYCLINGSIM_API bool TryEvaluateRouteExclusion(
		const CyclingSimulation::FRouteGeometryProfile& RouteGeometry,
		const FVector& CandidatePositionM,
		double ProtectedHalfWidthM,
		FRouteExclusionResult& OutResult,
		FString& OutError);
}
