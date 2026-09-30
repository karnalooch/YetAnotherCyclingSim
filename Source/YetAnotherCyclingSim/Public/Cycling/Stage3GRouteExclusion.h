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

	// Route-relative Stage 3G presentation surface shared by the persisted
	// prototype terrain and editor PCG. SurfaceRiseM is measured above the
	// route-centre support surface; simulation/physics never reads this value.
	struct YETANOTHERCYCLINGSIM_API FRoutePresentationSurfaceResult
	{
		double CorridorHalfWidthM = 0.0;
		double TerrainHalfWidthM = 0.0;
		double MaxRiseM = 0.0;
		double SurfaceRiseM = 0.0;
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

	// Resolves the deterministic Stage 3G route-relative presentation surface.
	//
	// A flat 8 m half-width corridor preserves road readability. Outside that
	// corridor, each biome rises smoothly toward its support edge:
	// valley 10 m / 110 m half-width, forest 8 m / 60 m, high Alpine
	// 28 m / 220 m. The profile is deliberately presentation-only.
	YETANOTHERCYCLINGSIM_API bool TryEvaluateRoutePresentationSurface(
		double RouteDistanceM,
		double SignedLateralOffsetM,
		FRoutePresentationSurfaceResult& OutResult,
		FString& OutError);
}
