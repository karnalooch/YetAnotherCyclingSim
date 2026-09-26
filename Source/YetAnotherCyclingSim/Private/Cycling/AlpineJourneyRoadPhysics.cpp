#include "Cycling/AlpineJourneyRoadPhysics.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/RoadPhysicsProfileBuilder.h"

namespace CyclingRoadPhysics
{
	bool TryBuildAlpineJourneyRoadPhysicsProfile(
		FRoadPhysicsProfile& OutProfile,
		FString& OutError)
	{
		CyclingSimulation::FRouteGeometryProfile Geometry;
		if (!CyclingSimulation::TryBuildAlpineJourneyRouteGeometry(
			Geometry,
			OutError))
		{
			return false;
		}

		FRoadPhysicsGeometryBuildSettings Settings;
		Settings.GradeHalfWindowM =
			AlpineJourneyRoadPhysicsGradeHalfWindowM;
		Settings.CurvatureHalfWindowM =
			AlpineJourneyRoadPhysicsCurvatureHalfWindowM;
		Settings.RoadWidthM = AlpineJourneyRoadWidthM;
		Settings.BankAngleRad = 0.0;
		Settings.SurfaceId = TEXT("asphalt");
		Settings.Wetness = 0.0;
		Settings.Roughness = 0.0;

		return TryBuildRoadPhysicsProfileFromGeometry(
			TEXT("Alpine Journey Road Physics"),
			Geometry,
			Settings,
			OutProfile,
			OutError);
	}
}
