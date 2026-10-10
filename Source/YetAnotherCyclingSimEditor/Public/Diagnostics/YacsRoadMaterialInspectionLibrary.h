#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsRoadMaterialInspectionLibrary.generated.h"

class UDynamicMeshComponent;

/** Read-only full-buffer evidence for the accepted #364 road and 186 supports. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsRoadMaterialInspectionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Hash the existing mesh and optionally return an ordered support triangle prefix. Never edit or save. */
    UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
    static FString InspectMesh(UDynamicMeshComponent* Component, int32 WitnessTriangleCount = 0);
};
