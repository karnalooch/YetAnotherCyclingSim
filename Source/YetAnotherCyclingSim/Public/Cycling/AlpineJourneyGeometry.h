#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "Cycling/RouteGeometry.h"

namespace CyclingSimulation
{
	struct YETANOTHERCYCLINGSIM_API FAlpineCornerGeometryDefinition
	{
		FString Id;
		double CenterDistanceM = 0.0;
		double LengthM = 0.0;
		double RadiusM = 0.0;
		double DirectionSign = 1.0;
	};

	// Fixed sampling interval used by the Stage 3 prototype geometry.
	inline constexpr double AlpineGeometrySampleSpacingM = 10.0;

	// Half-width of the smooth grade transition around each Stage 3B segment
	// boundary. Nominal segment grades are blended with smoothstep across a
	// 100 m total window to avoid discontinuous vertical tangents.
	inline constexpr double AlpineGradeBlendHalfWindowM = 50.0;

	YETANOTHERCYCLINGSIM_API void BuildAlpineCornerGeometryDefinitions(
		TArray<FAlpineCornerGeometryDefinition>& OutCorners);

	// Builds a deterministic 10 km geometry profile from the Stage 3B
	// Alpine Journey route specification.
	//
	// Geometry construction integrates:
	// - smoothed nominal route grade for elevation;
	// - signed circular curvature in eight corner zones for XY heading.
	//
	// Every generated interval has exactly the requested route-surface length
	// within floating-point tolerance. The resulting geometry is suitable for
	// deterministic grade queries and for writing to the prototype spline.
	YETANOTHERCYCLINGSIM_API bool TryBuildAlpineJourneyRouteGeometry(
		FRouteGeometryProfile& OutGeometry,
		FString& OutError);
}
