#include "Cycling/CyclingStage3RouteSetupCommandlet.h"

#if WITH_EDITOR

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/Stage3PrototypeTerrainActor.h"

#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "FileHelpers.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingStage3RouteSetup, Log, All);

namespace CyclingStage3RouteSetupInternal
{
	const TCHAR* MapPackagePath = TEXT("/Game/Prototype/Maps/L_CyclingTest");
	constexpr double MetresToCentimetres = 100.0;

	bool TryFindSoleRouteActor(
		UWorld* World,
		AActor*& OutRouteActor,
		USplineComponent*& OutSpline,
		FString& OutError)
	{
		OutRouteActor = nullptr;
		OutSpline = nullptr;
		OutError.Reset();

		int32 RouteActorCount = 0;
		for (AActor* Actor : World->GetCurrentLevel()->Actors)
		{
			if (!IsValid(Actor) || Actor->IsA(ACyclingPrototypePawn::StaticClass()))
			{
				continue;
			}

			TArray<USplineComponent*> Splines;
			Actor->GetComponents<USplineComponent>(Splines);
			if (Splines.Num() == 0)
			{
				continue;
			}

			++RouteActorCount;
			if (Splines.Num() != 1)
			{
				OutError = FString::Printf(
					TEXT("route actor '%s' has %d splines; exactly one is required"),
					*Actor->GetName(),
					Splines.Num());
				return false;
			}

			OutRouteActor = Actor;
			OutSpline = Splines[0];
		}

		if (RouteActorCount != 1 || !IsValid(OutRouteActor) || !IsValid(OutSpline))
		{
			OutError = FString::Printf(
				TEXT("expected exactly one route actor with one spline; found %d"),
				RouteActorCount);
			return false;
		}
		return true;
	}
}

UCyclingStage3RouteSetupCommandlet::UCyclingStage3RouteSetupCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingStage3RouteSetupCommandlet::Main(const FString& Params)
{
	using namespace CyclingSimulation;
	using namespace CyclingStage3RouteSetupInternal;

	UE_LOG(LogCyclingStage3RouteSetup, Display,
		TEXT("CyclingStage3RouteSetupCommandlet: starting."));

	UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
	if (!MapPackage)
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Failed to load map package '%s'."), MapPackagePath);
		return 1;
	}

	UWorld* MapWorld = UWorld::FindWorldInPackage(MapPackage);
	if (!MapWorld)
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Map package '%s' does not contain a UWorld."), MapPackagePath);
		return 1;
	}
	MapWorld->WorldType = EWorldType::Editor;

	AActor* RouteActor = nullptr;
	USplineComponent* Spline = nullptr;
	FString Error;
	if (!TryFindSoleRouteActor(MapWorld, RouteActor, Spline, Error))
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error, TEXT("%s"), *Error);
		return 1;
	}

	FRouteGeometryProfile Geometry;
	if (!TryBuildAlpineJourneyRouteGeometry(Geometry, Error))
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Failed to build Alpine geometry: %s"), *Error);
		return 1;
	}

	RouteActor->Modify();
	Spline->Modify();
	Spline->SetClosedLoop(false, false);
	Spline->ClearSplinePoints(false);

	const TArray<FRouteGeometrySample>& Samples = Geometry.GetSamples();
	for (int32 Index = 0; Index < Samples.Num(); ++Index)
	{
		const FVector PositionCm =
			Samples[Index].PositionM * MetresToCentimetres;
		Spline->AddSplinePoint(
			PositionCm,
			ESplineCoordinateSpace::Local,
			false);
		Spline->SetSplinePointType(
			Index,
			ESplinePointType::Linear,
			false);
	}
	Spline->UpdateSpline();

	// UE 5.8 persists spline overrides on BP SCS instances only when
	// bSplineHasBeenEdited ("Override Construction Script") is true.
	// AddSplinePoint/SetSplinePointType mutate the in-memory spline but
	// never flip this flag, so GetComponentInstanceData() returns empty
	// instance data and the new points are dropped on save+reload.
	Spline->SetOverrideConstructionScript(true);

	AStage3PrototypeTerrainActor* TerrainActor = nullptr;
	int32 TerrainActorCount = 0;
	for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
	{
		if (AStage3PrototypeTerrainActor* Candidate =
			Cast<AStage3PrototypeTerrainActor>(Actor))
		{
			++TerrainActorCount;
			TerrainActor = Candidate;
		}
	}

	if (TerrainActorCount > 1)
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Expected at most one Stage 3 prototype terrain actor; found %d."),
			TerrainActorCount);
		return 1;
	}

	if (!IsValid(TerrainActor))
	{
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.OverrideLevel = MapWorld->GetCurrentLevel();
		SpawnParameters.Name = TEXT("Stage3PrototypeTerrain");
		TerrainActor = MapWorld->SpawnActor<AStage3PrototypeTerrainActor>(
			AStage3PrototypeTerrainActor::StaticClass(),
			RouteActor->GetActorTransform(),
			SpawnParameters);
	}

	if (!IsValid(TerrainActor))
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Failed to create Stage 3 prototype terrain actor."));
		return 1;
	}

	TerrainActor->SetActorTransform(RouteActor->GetActorTransform());
	if (!TerrainActor->RebuildFromGeometry(Geometry, Error))
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Failed to rebuild Stage 3 prototype terrain: %s"),
			*Error);
		return 1;
	}

	const double ExpectedLengthCm =
		Geometry.GetTotalLengthM() * MetresToCentimetres;
	const double ActualLengthCm =
		static_cast<double>(Spline->GetSplineLength());

	if (Spline->GetNumberOfSplinePoints() != Samples.Num())
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Spline point count mismatch: actual=%d expected=%d."),
			Spline->GetNumberOfSplinePoints(),
			Samples.Num());
		return 1;
	}
	if (!FMath::IsNearlyEqual(ActualLengthCm, ExpectedLengthCm, 1.0))
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Spline length mismatch: actual=%.3f cm expected=%.3f cm."),
			ActualLengthCm,
			ExpectedLengthCm);
		return 1;
	}

	const bool bSaved = UEditorLoadingAndSavingUtils::SaveMap(
		MapWorld,
		MapPackagePath);
	if (!bSaved)
	{
		UE_LOG(LogCyclingStage3RouteSetup, Error,
			TEXT("Failed to save map '%s'."), MapPackagePath);
		return 1;
	}

	UE_LOG(LogCyclingStage3RouteSetup, Display,
		TEXT("Stage 3 route saved: actor='%s' points=%d length=%.3f m."),
		*RouteActor->GetName(),
		Spline->GetNumberOfSplinePoints(),
		ActualLengthCm / MetresToCentimetres);
	UE_LOG(LogCyclingStage3RouteSetup, Display,
		TEXT("Stage 3 prototype world saved: road=%d terrain=%d forest_props=%d mountain_props=%d valley_ridges=%d forest_canopy=%d distant_mountains=%d water_tiles=%d."),
		TerrainActor->GetRoadInstanceCount(),
		TerrainActor->GetTerrainInstanceCount(),
		TerrainActor->GetForestPropInstanceCount(),
		TerrainActor->GetMountainPropInstanceCount(),
		TerrainActor->GetValleyRidgeInstanceCount(),
		TerrainActor->GetForestCanopyInstanceCount(),
		TerrainActor->GetDistantMountainInstanceCount(),
		TerrainActor->GetWaterTileInstanceCount());
	UE_LOG(LogCyclingStage3RouteSetup, Display,
		TEXT("CyclingStage3RouteSetupCommandlet: done."));
	return 0;
}

#endif // WITH_EDITOR
