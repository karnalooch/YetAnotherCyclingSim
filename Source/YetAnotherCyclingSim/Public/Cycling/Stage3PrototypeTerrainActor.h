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
// an instanced road ribbon, broad terrain support tiles and sparse silhouette
// props that make the valley -> forest -> high-mountain progression readable.
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
};
