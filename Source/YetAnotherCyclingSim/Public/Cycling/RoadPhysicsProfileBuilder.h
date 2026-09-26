#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RoadPhysicsProfile.h"
#include "Cycling/RouteGeometry.h"

namespace CyclingRoadPhysics
{
	// Explicit inputs used to derive a canonical Road Physics Profile from the
	// authoritative, rendering-independent Stage 3 route geometry.
	//
	// Dynamic weather is intentionally not part of this builder. Wetness here
	// represents a route-surface baseline; runtime weather may compose with it
	// later without changing the route geometry contract.
	struct YETANOTHERCYCLINGSIM_API FRoadPhysicsGeometryBuildSettings
	{
		double GradeHalfWindowM = 0.0;
		double CurvatureHalfWindowM = 0.0;
		double RoadWidthM = 0.0;
		double BankAngleRad = 0.0;
		FString SurfaceId;
		double Wetness = 0.0;
		double Roughness = 0.0;
	};

	// Builds one Road Physics Profile sample for every authoritative route
	// geometry sample.
	//
	// Derived from geometry:
	// - S / route distance;
	// - elevation;
	// - longitudinal grade;
	// - signed horizontal curvature;
	// - vertical curvature.
	//
	// Supplied explicitly by route metadata/settings:
	// - road width;
	// - banking / cross-slope;
	// - surface id;
	// - baseline wetness;
	// - roughness.
	//
	// The rendered spline, terrain mesh, road mesh and PCG output are never
	// queried by this function.
	YETANOTHERCYCLINGSIM_API bool TryBuildRoadPhysicsProfileFromGeometry(
		const FString& Name,
		const CyclingSimulation::FRouteGeometryProfile& Geometry,
		const FRoadPhysicsGeometryBuildSettings& Settings,
		FRoadPhysicsProfile& OutProfile,
		FString& OutError);
}
