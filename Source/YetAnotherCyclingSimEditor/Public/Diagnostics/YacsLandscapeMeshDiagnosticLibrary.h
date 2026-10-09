#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsLandscapeMeshDiagnosticLibrary.generated.h"

class ULandscapeComponent;
class UDynamicMesh;
class UDynamicMeshComponent;
class UMaterial;
class ALandscape;

/** Bounded, read-only Component 230 geometry export for isolated visual diagnosis. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsLandscapeMeshDiagnosticLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Read at most 12000 existing support triangle positions for Issue459. Empty IDs reads all; never changes the mesh. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString ReadWindow0112SupportTriangles(UDynamicMesh* Mesh, const TArray<int32>& TriangleIds);

    /** Copy native LOD0 geometry and attributes into an existing transient mesh. Never save. Optional plan enables bounded local presentation smoothing. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString CopyComponent230(ULandscapeComponent* Component, UDynamicMesh* TargetMesh,
        const FString& SmoothingPlanJson = TEXT(""));

    /** Read native composite height samples for the isolated terrain erosion trial. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString ReadComponent230Heightfield(ULandscapeComponent* Component);

    /** Import a bounded derived heightfield as a transient native Landscape. Never modify the source. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static ALandscape* CreateComponent230TerrainTrial(ULandscapeComponent* Component,
        const FString& CandidateJson, const FString& PlanJson);

    /** Validate a retained v8 source and keep one native attribute-preserving snapshot for the transient detail proof. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString BeginComponent230Detail(UDynamicMeshComponent* Component,
        const FString& SourceJson, const FString& MaskJson,
        const FString& TrialJson, const FString& ManifestJson);

    /** Select baseline, mask, patch-magenta, patch-cyan or trial on the same validated native surface. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString SetComponent230DetailMode(UDynamicMeshComponent* Component, const FString& Mode);

    /** Restore the complete native snapshot and release the bounded diagnostic session. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString EndComponent230Detail(UDynamicMeshComponent* Component);

    /** Allocate an unsaved transient unlit material for the existing material graph authoring API. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static UMaterial* CreateComponent230DetailMaterial();
};
