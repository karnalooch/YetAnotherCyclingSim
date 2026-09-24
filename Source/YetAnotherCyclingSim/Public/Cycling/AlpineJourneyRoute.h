#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RouteProfile.h"

namespace CyclingSimulation
{
	// Builds the Stage 3 Alpine Journey route profile used by the MVP.
	//
	// This is the Unreal-side parity port of
	// physics_reference/src/cycling_physics/sample_routes.py::ALPINE_JOURNEY.
	// If these values change intentionally, update the Python reference and
	// parity tests in the same scoped change.
	YETANOTHERCYCLINGSIM_API bool TryBuildAlpineJourneyRouteProfile(
		FRouteProfile& OutProfile,
		FString& OutError);
}
