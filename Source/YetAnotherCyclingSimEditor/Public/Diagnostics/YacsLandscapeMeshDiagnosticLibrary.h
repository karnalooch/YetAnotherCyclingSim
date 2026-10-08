#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsLandscapeMeshDiagnosticLibrary.generated.h"

class ULandscapeComponent;
class UDynamicMesh;
class ALandscape;

/** Bounded, read-only Component 230 geometry export for isolated visual diagnosis. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsLandscapeMeshDiagnosticLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
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
};
