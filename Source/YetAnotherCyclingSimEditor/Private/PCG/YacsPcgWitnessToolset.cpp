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

    if (InActorPath.IsEmpty() || InGraphPath.IsEmpty() || InSourceNodePath.IsEmpty() ||
        InReductionNodePath.IsEmpty() || InReductionClass.IsEmpty() || InOutputPin.IsEmpty())
    {
        return MakeErrorJson(TEXT("INVALID_ARGUMENT"), TEXT("Required path or class argument is empty"));
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
    if (!Component->bGenerated || Component->IsGenerating() || Component->bDirtyGenerated)
    {
        return MakeErrorJson(
            TEXT("UNSTABLE_GENERATION_STATE"),
            FString::Printf(TEXT("Component is not in a stable generated state (bGenerated=%d, bInProgress=%d, bDirty=%d)"),
                Component->bGenerated, Component->IsGenerating(), Component->bDirtyGenerated)
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

    // 6. Find SourceNode and ReductionNode in Graph
    auto NodeMatchesPath = [](const UPCGNode* Node, const FString& TargetPath) -> bool
    {
        if (!Node)
        {
            return false;
        }
        if (Node->GetPathName() == TargetPath || Node->GetName() == TargetPath)
        {
            return true;
        }
        if (Node->GetPathName().EndsWith(TEXT(":") + TargetPath))
        {
            return true;
        }
        if (Node->GetAuthoredTitleName().ToString() == TargetPath)
        {
            return true;
        }
        return false;
    };

    UPCGNode* SourceNode = nullptr;
    UPCGNode* ReductionNode = nullptr;

    for (UPCGNode* Node : Graph->GetNodes())
    {
        if (!Node)
        {
            continue;
        }
        if (!SourceNode && NodeMatchesPath(Node, InSourceNodePath))
        {
            SourceNode = Node;
        }
        if (!ReductionNode && NodeMatchesPath(Node, InReductionNodePath))
        {
            ReductionNode = Node;
        }
    }

    if (!SourceNode)
    {
        SourceNode = FindObject<UPCGNode>(nullptr, *InSourceNodePath);
    }
    if (!ReductionNode)
    {
        ReductionNode = FindObject<UPCGNode>(nullptr, *InReductionNodePath);
    }

    if (!SourceNode)
    {
        return MakeErrorJson(TEXT("SOURCE_NODE_NOT_FOUND"), FString::Printf(TEXT("Source node not found in graph: %s"), *InSourceNodePath));
    }
    if (!ReductionNode)
    {
        return MakeErrorJson(TEXT("REDUCTION_NODE_NOT_FOUND"), FString::Printf(TEXT("Reduction node not found in graph: %s"), *InReductionNodePath));
    }

    if (SourceNode->GetGraph() != Graph || ReductionNode->GetGraph() != Graph)
    {
        return MakeErrorJson(TEXT("NODE_GRAPH_MISMATCH"), TEXT("Source or reduction node does not belong to the target graph"));
    }

    // 7. Verify ReductionNode settings class
    UPCGSettings* ReductionSettings = ReductionNode->GetSettings();
    if (!ReductionSettings)
    {
        return MakeErrorJson(TEXT("MISSING_REDUCTION_SETTINGS"), TEXT("Reduction node has no settings interface"));
    }
    UClass* ReductionSettingsClass = ReductionSettings->GetClass();
    if (!ReductionSettingsClass || ReductionSettingsClass->GetName() != InReductionClass)
    {
        return MakeErrorJson(
            TEXT("REDUCTION_CLASS_MISMATCH"),
            FString::Printf(TEXT("Reduction settings class mismatch: expected %s, found %s"),
                *InReductionClass, ReductionSettingsClass ? *ReductionSettingsClass->GetName() : TEXT("nullptr"))
        );
    }

    // 8. Verify Graph Pin Topology
    // 8a. ReductionNode input pins must be fed exclusively by SourceNode
    int32 ReductionInboundEdges = 0;
    for (const TObjectPtr<UPCGPin>& Pin : ReductionNode->GetInputPins())
    {
        if (!Pin)
        {
            continue;
        }
        for (const TObjectPtr<UPCGEdge>& Edge : Pin->Edges)
        {
            if (!Edge)
            {
                continue;
            }
            ReductionInboundEdges++;
            const UPCGNode* UpstreamNode = Edge->GetInputNode();
            if (!UpstreamNode && Edge->InputPin)
            {
                UpstreamNode = Edge->InputPin->Node.Get();
            }
            if (UpstreamNode != SourceNode)
            {
                return MakeErrorJson(
                    TEXT("UNVERIFIED_UPSTREAM_CONNECTION"),
                    FString::Printf(TEXT("Reduction node input pin '%s' has edge from unexpected upstream node: %s"),
                        *Pin->Properties.Label.ToString(),
                        UpstreamNode ? *UpstreamNode->GetPathName() : TEXT("nullptr"))
                );
            }
        }
    }
    if (ReductionInboundEdges == 0)
    {
        return MakeErrorJson(TEXT("REDUCTION_DISCONNECTED"), TEXT("Reduction node has no incoming edges from source node"));
    }

    // 8b. OutputNode input pins must be fed exclusively by ReductionNode (no bypasses allowed)
    UPCGNode* OutputNode = Graph->GetOutputNode();
    if (!OutputNode)
    {
        return MakeErrorJson(TEXT("OUTPUT_NODE_NOT_FOUND"), TEXT("PCG Graph has no output node"));
    }

    int32 OutputInboundEdges = 0;
    for (const TObjectPtr<UPCGPin>& Pin : OutputNode->GetInputPins())
    {
        if (!Pin)
        {
            continue;
        }
        for (const TObjectPtr<UPCGEdge>& Edge : Pin->Edges)
        {
            if (!Edge)
            {
                continue;
            }
            OutputInboundEdges++;
            const UPCGNode* UpstreamNode = Edge->GetInputNode();
            if (!UpstreamNode && Edge->InputPin)
            {
                UpstreamNode = Edge->InputPin->Node.Get();
            }
            if (UpstreamNode != ReductionNode)
            {
                return MakeErrorJson(
                    TEXT("OUTPUT_BYPASS_DETECTED"),
                    FString::Printf(TEXT("Output node pin '%s' is fed by non-reduction node '%s' (bypass detected)"),
                        *Pin->Properties.Label.ToString(),
                        UpstreamNode ? *UpstreamNode->GetPathName() : TEXT("nullptr"))
                );
            }
        }
    }
    if (OutputInboundEdges == 0)
    {
        return MakeErrorJson(TEXT("OUTPUT_DISCONNECTED"), TEXT("Graph output node has no incoming edges from reduction node"));
    }

    // 9. Inspect GeneratedGraphOutput collection directly in GameThread memory
    // Strict requirement: all tagged data must match InOutputPin, be UPCGBasePointData, and total <= MaxAllowedPoints.
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
            return MakeErrorJson(
                TEXT("FOREIGN_PIN_DATA"),
                FString::Printf(TEXT("Unexpected tagged data pin in output collection: %s (expected %s)"),
                    *TaggedData.Pin.ToString(), *InOutputPin)
            );
        }

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
        MatchingTaggedDataCount++;
    }

    if (MatchingTaggedDataCount == 0 || TotalPointCount == 0)
    {
        return MakeErrorJson(TEXT("NO_MATCHING_POINTS"), FString::Printf(TEXT("No points found on pin %s"), *InOutputPin));
    }

    // 10. Format authentic witness receipt bound to engine PID, session, and node identities
    const uint32 SessionPid = FPlatformProcess::GetCurrentProcessId();
    const FString GenerationToken = FGuid::NewGuid().ToString();
    const FString TimestampIso = FDateTime::UtcNow().ToIso8601();

    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("status"), TEXT("NATIVE_IN_PROCESS_OUTPUT_COUNTED"));
    Root->SetNumberField(TEXT("session_pid"), SessionPid);
    Root->SetStringField(TEXT("actor_path"), InActorPath);
    Root->SetStringField(TEXT("graph_path"), InGraphPath);
    Root->SetStringField(TEXT("source_node_path"), SourceNode->GetPathName());
    Root->SetStringField(TEXT("reduction_node_path"), ReductionNode->GetPathName());
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
