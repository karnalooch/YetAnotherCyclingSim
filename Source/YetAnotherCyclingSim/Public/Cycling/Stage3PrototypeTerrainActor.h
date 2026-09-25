#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Cycling/RouteGeometry.h"
#include "Stage3PrototypeTerrainActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;

// Minimal Stage 3E world presentation.
//
// This actor intentionally uses only engine basic-shape meshes and deterministic
// route geometry. It is a validation scaffold, not Stage 7 art. One actor owns
// an instanced road ribbon, broad terrain support tiles, sparse silhouette
// props, and (Stage 3F) a thin rail of white edge-line meshes along the
// road that make the valley -> forest -> high-mountain progression readable.
//
// Runtime physics never reads this actor. The geometry profile remains the
// source of route shape/grade truth and the spline remains presentation only.
UCLASS()
class YETANOTHERCYCLINGSIM_API AStage3PrototypeTerrainActor : public AActor
{
	GENERATED_BODY()

public:
	AStage3PrototypeTerrainActor();

	// Rebuilds all prototype-world instances from deterministic route geometry.
	// Existing instances are cleared first, making the operation idempotent.
	bool RebuildFromGeometry(
		const CyclingSimulation::FRouteGeometryProfile& Geometry,
		FString& OutError);

	// Fresh-load verification used by the Stage 3 editor proof. It checks
	// instance counts, representative/all road alignment and finite transforms.
	bool ValidateAgainstGeometry(
		const CyclingSimulation::FRouteGeometryProfile& Geometry,
		FString& OutError) const;

	int32 GetRoadInstanceCount() const;
	int32 GetTerrainInstanceCount() const;
	int32 GetForestPropInstanceCount() const;
	int32 GetMountainPropInstanceCount() const;
	int32 GetRoadEdgeLineInstanceCount() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> RoadTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> TerrainTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ForestProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> MountainProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> RoadEdgeLines;

	// Stage 3F presentation paths. Assigned via ConstructorHelpers so the
	// material references survive rebuild / fresh checkout. The Python
	// authoring script (scripts/ue/stage3f_author_materials.py) is
	// responsible for creating these uassets under
	// /Game/Prototype/Environment/Stage3F/Materials/ on first install.
	static const TCHAR* RoadAsphaltMaterialPath;
	static const TCHAR* RoadEdgeLineMaterialPath;
	static const TCHAR* TerrainMaterialPath;
};
