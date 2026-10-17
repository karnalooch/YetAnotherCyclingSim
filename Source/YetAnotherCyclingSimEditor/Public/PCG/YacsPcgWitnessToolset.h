#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ToolsetRegistry/ToolsetDefinition.h"
#include "YacsPcgWitnessToolset.generated.h"

class AActor;
class UPCGComponent;
class UPCGGraph;

/**
 * Authentic, GameThread-only native PCG point buffer witness toolset exposed to Epic's MCP.
 *
 * Inherits from UToolsetDefinition to be discoverable and invokable by Epic's ModelContextProtocol
 * server without generic remote code execution or reflection bridges.
 *
 * Reads UPCGBasePointData::GetNumPoints() directly from in-memory FPCGDataCollection
 * without calling GetNodeDataView, without serializing row data, and without transport slicing.
 */
UCLASS(BlueprintType)
class YETANOTHERCYCLINGSIMEDITOR_API UYacsPcgWitnessToolset : public UToolsetDefinition
{
    GENERATED_BODY()

public:
    /**
     * Inspects the live GameThread output of an authentic reduction node on a PCGComponent.
     * Returns a JSON string containing the authenticated witness and verified point count,
     * or a JSON error object if unreduced, unstable, or missing.
     */
    UFUNCTION(meta = (AICallable), Category = "YACS|PCG")
    static FString InspectReducedNodeOutput(
        const FString& InActorPath,
        const FString& InGraphPath,
        const FString& InSourceNodePath,
        const FString& InReductionNodePath,
        const FString& InReductionClass,
        const FString& InOutputPin = TEXT("Out"),
        int32 MaxAllowedPoints = 256
    );
};

/**
 * Authentic, GameThread-only native PCG point buffer witness inspection library.
 * Blueprint Function Library wrapper forwarding to UYacsPcgWitnessToolset.
 */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsPcgWitnessInspectionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "YACS|PCG")
    static FString InspectReducedNodeOutput(
        const FString& InActorPath,
        const FString& InGraphPath,
        const FString& InSourceNodePath,
        const FString& InReductionNodePath,
        const FString& InReductionClass,
        const FString& InOutputPin = TEXT("Out"),
        int32 MaxAllowedPoints = 256
    );
};
