#include "PCG/YacsPcgWitnessToolset.h"

#include "PCGComponent.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "PCGPin.h"
#include "PCGEdge.h"
#include "PCGSettings.h"
#include "Data/PCGBasePointData.h"

#include "GameFramework/Actor.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Guid.h"
#include "Misc/DateTime.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

namespace
{
FString MakeErrorJson(const FString& InErrorCode, const FString& InMessage)
{
    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("status"), TEXT("ERROR"));
    Root->SetStringField(TEXT("error_code"), InErrorCode);
    Root->SetStringField(TEXT("message"), InMessage);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(Root, Writer);
    return OutputString;
}
}

FString UYacsPcgWitnessInspectionLibrary::InspectReducedNodeOutput(
    const FString& InActorPath,
    const FString& InGraphPath,
    const FString& InSourceNodePath,
    const FString& InReductionNodePath,
    const FString& InReductionClass,
    const FString& InOutputPin,
    int32 MaxAllowedPoints
)
{
    // 1. Must run strictly on the GameThread
    if (!IsInGameThread())
    {
        return MakeErrorJson(TEXT("THREAD_VIOLATION"), TEXT("InspectReducedNodeOutput must execute on GameThread"));
    }

    if (MaxAllowedPoints <= 0 || MaxAllowedPoints > 256)
    {
        return MakeErrorJson(TEXT("INVALID_ARGUMENT"), TEXT("MaxAllowedPoints must be between 1 and 256"));
    }

    // 2. Resolve target Actor
    AActor* Actor = FindObject<AActor>(nullptr, *InActorPath);
    if (!Actor)
    {
        return MakeErrorJson(TEXT("ACTOR_NOT_FOUND"), FString::Printf(TEXT("Actor not found: %s"), *InActorPath));
    }

    // 3. Resolve PCGComponent
    UPCGComponent* Component = Actor->FindComponentByClass<UPCGComponent>();
    if (!Component)
    {
        return MakeErrorJson(TEXT("COMPONENT_NOT_FOUND"), FString::Printf(TEXT("PCGComponent not found on actor: %s"), *InActorPath));
    }

    // 4. Verify generation stability
    if (!Component->bGenerated || Component->bGenerationInProgress || Component->bDirtyGenerated)
    {
        return MakeErrorJson(
            TEXT("UNSTABLE_GENERATION_STATE"),
            FString::Printf(TEXT("Component is not in a stable generated state (bGenerated=%d, bInProgress=%d, bDirty=%d)"),
                Component->bGenerated, Component->bGenerationInProgress, Component->bDirtyGenerated)
        );
    }

    // 5. Verify Graph ownership
    UPCGGraphInterface* GraphInterface = Component->GetGraphInstance();
    if (!GraphInterface)
    {
        return MakeErrorJson(TEXT("MISSING_GRAPH_INSTANCE"), TEXT("PCGComponent has no valid GraphInstance"));
    }

    const UPCGGraph* Graph = GraphInterface->GetConstPCGGraph();
    if (!Graph || Graph->GetPathName() != InGraphPath)
    {
        return MakeErrorJson(
            TEXT("GRAPH_MISMATCH"),
            FString::Printf(TEXT("Graph path mismatch: expected %s, found %s"),
                *InGraphPath, Graph ? *Graph->GetPathName() : TEXT("nullptr"))
        );
    }

    // 6. Inspect GeneratedGraphOutput collection directly in GameThread memory
    const FPCGDataCollection& OutputCollection = Component->GetGeneratedGraphOutput();
    if (OutputCollection.TaggedData.Num() == 0)
    {
        return MakeErrorJson(TEXT("EMPTY_OUTPUT_COLLECTION"), TEXT("GeneratedGraphOutput has no tagged data"));
    }

    int32 TotalPointCount = 0;
    int32 MatchingTaggedDataCount = 0;
    const FName ExpectedPinName(*InOutputPin);

    for (const FPCGTaggedData& TaggedData : OutputCollection.TaggedData)
    {
        if (TaggedData.Pin != ExpectedPinName)
        {
            continue;
        }

        MatchingTaggedDataCount++;
        const UPCGData* Data = TaggedData.Data.Get();
        if (!Data)
        {
            return MakeErrorJson(TEXT("NULL_PCG_DATA"), TEXT("TaggedData entry has null UPCGData"));
        }

        const UPCGBasePointData* PointData = Cast<UPCGBasePointData>(Data);
        if (!PointData)
        {
            return MakeErrorJson(TEXT("NON_POINT_DATA"), TEXT("TaggedData output is not UPCGBasePointData"));
        }

        const int32 PointsInDataset = PointData->GetNumPoints();
        if (PointsInDataset <= 0 || PointsInDataset > MaxAllowedPoints)
        {
            return MakeErrorJson(
                TEXT("POINT_COUNT_OUT_OF_BOUNDS"),
                FString::Printf(TEXT("Dataset point count %d exceeds allowed range (1..%d)"), PointsInDataset, MaxAllowedPoints)
            );
        }

        TotalPointCount += PointsInDataset;
        if (TotalPointCount > MaxAllowedPoints)
        {
            return MakeErrorJson(
                TEXT("AGGREGATE_COUNT_EXCEEDED"),
                FString::Printf(TEXT("Aggregate point count %d exceeds maximum allowed %d"), TotalPointCount, MaxAllowedPoints)
            );
        }
    }

    if (MatchingTaggedDataCount == 0 || TotalPointCount == 0)
    {
        return MakeErrorJson(TEXT("NO_MATCHING_POINTS"), FString::Printf(TEXT("No points found on pin %s"), *InOutputPin));
    }

    // 7. Format authentic witness receipt
    const uint32 SessionPid = FPlatformProcess::GetCurrentProcessId();
    const FString GenerationToken = FGuid::NewGuid().ToString();
    const FString TimestampIso = FDateTime::UtcNow().ToIso8601();

    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("status"), TEXT("NATIVE_IN_PROCESS_OUTPUT_COUNTED"));
    Root->SetNumberField(TEXT("session_pid"), SessionPid);
    Root->SetStringField(TEXT("actor_path"), InActorPath);
    Root->SetStringField(TEXT("graph_path"), InGraphPath);
    Root->SetStringField(TEXT("source_node_path"), InSourceNodePath);
    Root->SetStringField(TEXT("reduction_node_path"), InReductionNodePath);
    Root->SetStringField(TEXT("reduction_class"), InReductionClass);
    Root->SetStringField(TEXT("output_pin"), InOutputPin);
    Root->SetNumberField(TEXT("native_point_count"), TotalPointCount);
    Root->SetNumberField(TEXT("tagged_data_count"), MatchingTaggedDataCount);
    Root->SetStringField(TEXT("generation_token"), GenerationToken);
    Root->SetStringField(TEXT("timestamp"), TimestampIso);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(Root, Writer);
    return OutputString;
}
