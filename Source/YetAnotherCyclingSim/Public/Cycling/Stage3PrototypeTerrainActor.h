#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Cycling/RouteGeometry.h"
#include "Stage3PrototypeTerrainActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;

// Deterministic Stage 3 prototype-world presentation.
//
// This actor remains a deterministic validation/presentation scaffold rather
// than final Stage 7 art. Stage 3F established the road/material baseline;
// Stage 3G progressively replaces placeholder presentation with validated
// project-owned assets. R1 adds texture-backed biome ground and imported rock
// dressing while forest/mountain silhouettes remain explicit placeholders for
// later Stage 3G recovery tranches. Simulation truth stays outside presentation.
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
	int32 GetValleyRidgeInstanceCount() const;
	int32 GetForestCanopyInstanceCount() const;
	int32 GetDistantMountainInstanceCount() const;
	int32 GetRockPropInstanceCount() const;
	int32 GetWaterTileInstanceCount() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> RoadTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> TerrainTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ForestTerrainTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> HighAlpineTerrainTiles;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ForestProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> MountainProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|PrototypeWorld")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> RoadEdgeLines;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ValleyRidgeProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> ForestCanopyProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> DistantMountainProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> RockProps;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Stage3|ReferenceEnvironment")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> WaterTiles;

	// Stage 3F presentation paths. Assigned via ConstructorHelpers so the
	// material references survive rebuild / fresh checkout. The Python
	// authoring script (scripts/ue/stage3f_author_materials.py) is
	// responsible for creating these uassets under
	// /Game/Prototype/Environment/Stage3F/Materials/ on first install.
	static const TCHAR* RoadAsphaltMaterialPath;
	static const TCHAR* RoadEdgeLineMaterialPath;
	static const TCHAR* TerrainMaterialPath;

	// Stage 3G optional presentation materials. The actor deliberately falls
	// back to the Stage 3F terrain material until these assets are authored by
	// scripts/ue/stage3g_author_materials.py, so source builds remain valid
	// before the binary .uasset generation step.
	static const TCHAR* Stage3GGrassMaterialPath;
	static const TCHAR* Stage3GForestMaterialPath;
	static const TCHAR* Stage3GFoliageMaterialPath;
	static const TCHAR* Stage3GRockMaterialPath;
	static const TCHAR* Stage3GDistantRockMaterialPath;
	static const TCHAR* Stage3GWaterMaterialPath;
	static const TCHAR* Stage3GBoulderMeshPath;
};
