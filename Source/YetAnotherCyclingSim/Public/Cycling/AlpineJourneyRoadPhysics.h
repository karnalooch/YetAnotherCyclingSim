#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RoadPhysicsProfile.h"

namespace CyclingRoadPhysics
{
	// Stage 3 physical-road baseline. The current rendered prototype road is
	// also 6 m wide; final presentation should consume the same route metadata
	// at the integration stage rather than becoming a physics source of truth.
	inline constexpr double AlpineJourneyRoadWidthM = 6.0;

	inline constexpr double AlpineJourneyRoadPhysicsGradeHalfWindowM = 20.0;
	inline constexpr double AlpineJourneyRoadPhysicsCurvatureHalfWindowM = 10.0;

	// Builds the static physical-road baseline for the 10 km Alpine Journey.
	//
	// Stage 3H-B deliberately keeps:
	// - bank angle at 0 (banking authoring comes next);
	// - surface = asphalt;
	// - baseline wetness = 0 (dynamic weather is composed later);
	// - roughness = 0 (advanced roughness physics is post-MVP).
	YETANOTHERCYCLINGSIM_API bool TryBuildAlpineJourneyRoadPhysicsProfile(
		FRoadPhysicsProfile& OutProfile,
		FString& OutError);
}
