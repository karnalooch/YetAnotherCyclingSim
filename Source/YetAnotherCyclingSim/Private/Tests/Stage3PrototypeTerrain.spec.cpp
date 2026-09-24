#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/Stage3PrototypeTerrainActor.h"

#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3PrototypeTerrainBuildTest,
	"CyclingStage3World.PrototypeTerrain",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3PrototypeTerrainBuildTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;

	UWorld* World = UWorld::CreateWorld(
		EWorldType::Game,
		false,
		TEXT("Stage3PrototypeTerrainTestWorld"));
	if (!World)
	{
		AddError(TEXT("failed to create transient Stage 3 terrain test world"));
		return false;
	}

	FRouteGeometryProfile Geometry;
	FString Error;
	TestTrue(TEXT("Alpine geometry builds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	AStage3PrototypeTerrainActor* Terrain =
		World->SpawnActor<AStage3PrototypeTerrainActor>();
	TestNotNull(TEXT("prototype terrain actor spawns"), Terrain);

	if (Terrain)
	{
		TestTrue(TEXT("prototype terrain rebuild succeeds"),
			Terrain->RebuildFromGeometry(Geometry, Error));
		TestTrue(TEXT("prototype terrain validates against route geometry"),
			Terrain->ValidateAgainstGeometry(Geometry, Error));

		TestEqual(TEXT("one road tile per 10 m geometry interval"),
			Terrain->GetRoadInstanceCount(), 1000);
		TestEqual(TEXT("terrain support uses 50 m tile stride"),
			Terrain->GetTerrainInstanceCount(), 200);
		TestTrue(TEXT("forest progression props exist"),
			Terrain->GetForestPropInstanceCount() > 0);
		TestTrue(TEXT("high-mountain progression props exist"),
			Terrain->GetMountainPropInstanceCount() > 0);

		const int32 RoadCountBefore =
			Terrain->GetRoadInstanceCount();
		const int32 TerrainCountBefore =
			Terrain->GetTerrainInstanceCount();
		const int32 ForestCountBefore =
			Terrain->GetForestPropInstanceCount();
		const int32 MountainCountBefore =
			Terrain->GetMountainPropInstanceCount();

		TestTrue(TEXT("idempotent rebuild succeeds"),
			Terrain->RebuildFromGeometry(Geometry, Error));
		TestEqual(TEXT("idempotent road count unchanged"),
			Terrain->GetRoadInstanceCount(), RoadCountBefore);
		TestEqual(TEXT("idempotent terrain count unchanged"),
			Terrain->GetTerrainInstanceCount(), TerrainCountBefore);
		TestEqual(TEXT("idempotent forest prop count unchanged"),
			Terrain->GetForestPropInstanceCount(), ForestCountBefore);
		TestEqual(TEXT("idempotent mountain prop count unchanged"),
			Terrain->GetMountainPropInstanceCount(), MountainCountBefore);
	}

	World->DestroyWorld(false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
