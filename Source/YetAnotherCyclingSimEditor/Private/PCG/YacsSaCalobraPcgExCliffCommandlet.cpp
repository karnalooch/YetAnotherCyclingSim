#include "PCG/YacsSaCalobraPcgExCliffCommandlet.h"

#include "PCG/YacsSaCalobraCliffCellsSettings.h"

#include "Dom/JsonObject.h"
#include "HAL/PlatformProcess.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "PCGComponent.h"
#include "PCGGraph.h"
#include "PCGGraphInputOutputSettings.h"
#include "PCGManagedResource.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if YACS_WITH_PCGEX
#include "Data/PCGDynamicMeshData.h"
#include "Elements/PCGExClipper2Boolean.h"
#include "Elements/PCGExClipper2Triangulate.h"
#include "Elements/PCGExSmooth.h"
#include "Elements/PCGExSubdivide.h"
#include "UDynamicMesh.h"
#endif

#include "DynamicMesh/DynamicMesh3.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "WorldPartition/WorldPartitionHelpers.h"

namespace
{
    constexpr TCHAR SourcePin[] = TEXT("Paths");
    constexpr TCHAR MeshPin[] = TEXT("Mesh");
    constexpr TCHAR PcgExCommit[] =
        TEXT("39a8f1bdc65b2c4613a1e87b71d93b4576db0a66");

    bool AddEdge(
        UPCGGraph* Graph,
        UPCGNode* From,
        const FName FromPin,
        UPCGNode* To,
        const FName ToPin)
    {
        return Graph
            && From
            && To
            && Graph->AddEdge(From, FromPin, To, ToPin);
    }

    int32 ReadExpectedSkinCellCount(const FString& PlanPath)
    {
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *PlanPath))
        {
            return INDEX_NONE;
        }
        TSharedPtr<FJsonObject> Root;
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
        if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
        {
            return INDEX_NONE;
        }
        const TSharedPtr<FJsonObject>* Counts = nullptr;
        if (!Root->TryGetObjectField(TEXT("counts"), Counts) || !Counts || !Counts->IsValid())
        {
            return INDEX_NONE;
        }
        return static_cast<int32>((*Counts)->GetNumberField(TEXT("skin_cell_count")));
    }

#if YACS_WITH_PCGEX
    bool ExecuteGraph(
        UPCGGraph* Graph,
        TArray<FPCGTaggedData>& OutData,
        FString& OutError)
    {
        UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, FName(TEXT("YacsSaCalobraPhase2C")));
        if (!World)
        {
            OutError = TEXT("Could not create transient execution world.");
            return false;
        }

        bool bSuccess = false;
        {
            FWorldContext& WorldContext =
                GEngine->CreateNewWorldContext(EWorldType::Editor);
            WorldContext.SetCurrentWorld(World);
            World->InitializeNewWorld(
                UWorld::InitializationValues()
                    .AllowAudioPlayback(false)
                    .CreatePhysicsScene(false)
                    .RequiresHitProxies(false)
                    .CreateNavigation(false)
                    .CreateAISystem(false)
                    .ShouldSimulatePhysics(false)
                    .EnableTraceCollision(false));

            AActor* Owner = World->SpawnActor<AActor>();
            UPCGComponent* Component = NewObject<UPCGComponent>(Owner, TEXT("YacsPhase2CPCG"));
            Component->RegisterComponent();
            Component->SetGraphLocal(Graph);
            Component->GenerateLocal(true);

            constexpr double TimeoutSeconds = 120.0;
            const double Start = FPlatformTime::Seconds();
            while (Component->IsGenerating())
            {
                FWorldPartitionHelpers::FakeEngineTick(World);
                FPlatformProcess::Sleep(0.01f);
                if (FPlatformTime::Seconds() - Start > TimeoutSeconds)
                {
                    OutError = TEXT("PCGEx Phase 2C graph timed out.");
                    break;
                }
            }

            if (!Component->IsGenerating() && OutError.IsEmpty())
            {
                OutData = Component->GetGeneratedGraphOutput().TaggedData;
                bSuccess = !OutData.IsEmpty();
                if (!bSuccess)
                {
                    OutError = TEXT("PCGEx Phase 2C graph returned no output.");
                }
            }

            Component->CleanupLocalImmediate(true);
            World->DestroyWorld(false);
            GEngine->DestroyWorldContext(World);
        }
        return bSuccess;
    }

    TSharedPtr<FJsonObject> MeshToJson(
        const UPCGDynamicMeshData* MeshData,
        int32& OutVertices,
        int32& OutTriangles)
    {
        if (!MeshData || !MeshData->GetDynamicMesh())
        {
            return nullptr;
        }

        const UE::Geometry::FDynamicMesh3& Mesh =
            MeshData->GetDynamicMesh()->GetMeshRef();

        TMap<int32, int32> Remap;
        TArray<TSharedPtr<FJsonValue>> Vertices;
        Vertices.Reserve(Mesh.VertexCount());
        int32 DenseIndex = 0;
        for (const int32 VertexId : Mesh.VertexIndicesItr())
        {
            Remap.Add(VertexId, DenseIndex++);
            const FVector Position = Mesh.GetVertex(VertexId);
            TArray<TSharedPtr<FJsonValue>> Values;
            Values.Add(MakeShared<FJsonValueNumber>(Position.X));
            Values.Add(MakeShared<FJsonValueNumber>(Position.Y));
            Values.Add(MakeShared<FJsonValueNumber>(Position.Z));
            Vertices.Add(MakeShared<FJsonValueArray>(MoveTemp(Values)));
        }

        TArray<TSharedPtr<FJsonValue>> Triangles;
        Triangles.Reserve(Mesh.TriangleCount());
        for (const int32 TriangleId : Mesh.TriangleIndicesItr())
        {
            const UE::Geometry::FIndex3i Triangle = Mesh.GetTriangle(TriangleId);
            const int32* A = Remap.Find(Triangle.A);
            const int32* B = Remap.Find(Triangle.B);
            const int32* C = Remap.Find(Triangle.C);
            if (!A || !B || !C)
            {
                continue;
            }
            TArray<TSharedPtr<FJsonValue>> Values;
            Values.Add(MakeShared<FJsonValueNumber>(*A));
            Values.Add(MakeShared<FJsonValueNumber>(*B));
            Values.Add(MakeShared<FJsonValueNumber>(*C));
            Triangles.Add(MakeShared<FJsonValueArray>(MoveTemp(Values)));
        }

        OutVertices += Vertices.Num();
        OutTriangles += Triangles.Num();

        TSharedPtr<FJsonObject> Object = MakeShared<FJsonObject>();
        Object->SetArrayField(TEXT("vertices_cm"), MoveTemp(Vertices));
        Object->SetArrayField(TEXT("triangles"), MoveTemp(Triangles));
        return Object;
    }
#endif
}

UYacsSaCalobraPcgExCliffCommandlet::UYacsSaCalobraPcgExCliffCommandlet()
{
    IsClient = false;
    IsEditor = true;
    IsServer = false;
    LogToConsole = true;
}

int32 UYacsSaCalobraPcgExCliffCommandlet::Main(const FString& Params)
{
#if !YACS_WITH_PCGEX
    UE_LOG(
        LogTemp,
        Error,
        TEXT("Phase 2C requires the pinned PCGEx checkout. Run Bootstrap-YacsPcgEx.ps1 first."));
    return 10;
#else
    FString PlanPath;
    FString OutputPath;
    if (!FParse::Value(*Params, TEXT("Plan="), PlanPath)
        || !FParse::Value(*Params, TEXT("ExecutionOutput="), OutputPath))
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("Usage: -run=YacsSaCalobraPcgExCliff -Plan=<plan.json> -ExecutionOutput=<mesh.json>"));
        return 11;
    }

    PlanPath = FPaths::ConvertRelativePathToFull(PlanPath);
    OutputPath = FPaths::ConvertRelativePathToFull(OutputPath);
    const int32 ExpectedSkinCells = ReadExpectedSkinCellCount(PlanPath);
    if (ExpectedSkinCells <= 0)
    {
        UE_LOG(LogTemp, Error, TEXT("Invalid Phase 2C plan: %s"), *PlanPath);
        return 12;
    }

    UPCGGraph* Graph = NewObject<UPCGGraph>(
        GetTransientPackage(),
        FName(TEXT("YacsSaCalobraComponent230Phase2C")),
        RF_Transient);
    if (!Graph)
    {
        return 13;
    }

    UPCGNode* SourceNode = Graph->AddNodeOfType<UYacsSaCalobraCliffCellsSettings>();
    UYacsSaCalobraCliffCellsSettings* Source =
        SourceNode ? Cast<UYacsSaCalobraCliffCellsSettings>(SourceNode->GetSettings()) : nullptr;
    if (!Source)
    {
        return 14;
    }
    Source->PlanJsonPath = PlanPath;

    UPCGNode* UnionNode = Graph->AddNodeOfType<UPCGExClipper2BooleanSettings>();
    UPCGExClipper2BooleanSettings* Union =
        UnionNode ? Cast<UPCGExClipper2BooleanSettings>(UnionNode->GetSettings()) : nullptr;
    if (!Union)
    {
        return 15;
    }
    Union->Operation = EPCGExClipper2BooleanOp::Union;
    Union->FillRule = EPCGExClipper2FillRule::NonZero;
    Union->bUseOperandPin = false;
    Union->MainInputGroupingPolicy = EPCGExGroupingPolicy::Consolidate;
    Union->bSkipOpenPaths = true;
    Union->OpenPathsOutput = EPCGExClipper2OpenPathOutput::Ignore;
    Union->bSimplifyPaths = true;
    Union->bPreserveCollinear = false;

    UPCGNode* SmoothNode = Graph->AddNodeOfType<UPCGExSmoothSettings>();
    UPCGExSmoothSettings* Smooth =
        SmoothNode ? Cast<UPCGExSmoothSettings>(SmoothNode->GetSettings()) : nullptr;
    if (!Smooth)
    {
        return 16;
    }
    Smooth->bPreserveStart = false;
    Smooth->bPreserveEnd = false;
    Smooth->BlendingInterface = EPCGExBlendingInterface::Monolithic;
    Smooth->BlendingSettings = FPCGExBlendingDetails(EPCGExBlendingType::Average);
    Smooth->Influence.Constant = 0.35;
    Smooth->SmoothingAmount.Constant = 2.0;

    UPCGNode* SubdivideNode = Graph->AddNodeOfType<UPCGExSubdivideSettings>();
    UPCGExSubdivideSettings* Subdivide =
        SubdivideNode ? Cast<UPCGExSubdivideSettings>(SubdivideNode->GetSettings()) : nullptr;
    if (!Subdivide)
    {
        return 17;
    }
    Subdivide->SubdivideMethod = EPCGExSubdivideMode::Distance;
    Subdivide->AmountInput = EPCGExInputValueType::Constant;
    Subdivide->Distance = 100.0;
    Subdivide->bRedistributeEvenly = true;

    UPCGNode* TriangulateNode = Graph->AddNodeOfType<UPCGExClipper2TriangulateSettings>();
    UPCGExClipper2TriangulateSettings* Triangulate =
        TriangulateNode
            ? Cast<UPCGExClipper2TriangulateSettings>(TriangulateNode->GetSettings())
            : nullptr;
    if (!Triangulate)
    {
        return 18;
    }
    Triangulate->MainInputGroupingPolicy = EPCGExGroupingPolicy::Consolidate;
    Triangulate->bSkipOpenPaths = true;
    Triangulate->OpenPathsOutput = EPCGExClipper2OpenPathOutput::Ignore;
    Triangulate->bSimplifyPaths = true;
    Triangulate->bPreserveCollinear = false;
    Triangulate->FillRule = EPCGExClipper2FillRule::NonZero;
    Triangulate->bUseDelaunay = true;
    Triangulate->bAttemptRepair = true;
    Triangulate->Topology.bWeldEdges = true;
    Triangulate->Topology.bComputeNormals = true;

    if (!AddEdge(Graph, SourceNode, FName(SourcePin), UnionNode, FName(SourcePin))
        || !AddEdge(Graph, UnionNode, FName(SourcePin), SmoothNode, FName(SourcePin))
        || !AddEdge(Graph, SmoothNode, FName(SourcePin), SubdivideNode, FName(SourcePin))
        || !AddEdge(Graph, SubdivideNode, FName(SourcePin), TriangulateNode, FName(SourcePin))
        || !AddEdge(Graph, TriangulateNode, FName(MeshPin), Graph->GetOutputNode(), FName(MeshPin)))
    {
        UE_LOG(LogTemp, Error, TEXT("Could not wire the transient Phase 2C PCGEx graph."));
        return 19;
    }

    TArray<FPCGTaggedData> Generated;
    FString ExecutionError;
    if (!ExecuteGraph(Graph, Generated, ExecutionError))
    {
        UE_LOG(LogTemp, Error, TEXT("Phase 2C PCGEx execution failed: %s"), *ExecutionError);
        return 20;
    }

    TArray<TSharedPtr<FJsonValue>> Meshes;
    int32 VertexCount = 0;
    int32 TriangleCount = 0;
    for (const FPCGTaggedData& Tagged : Generated)
    {
        if (Tagged.Pin != FName(MeshPin))
        {
            continue;
        }
        const UPCGDynamicMeshData* MeshData = Cast<UPCGDynamicMeshData>(Tagged.Data);
        if (!MeshData)
        {
            continue;
        }
        TSharedPtr<FJsonObject> MeshJson =
            MeshToJson(MeshData, VertexCount, TriangleCount);
        if (MeshJson.IsValid())
        {
            Meshes.Add(MakeShared<FJsonValueObject>(MeshJson));
        }
    }

    if (Meshes.IsEmpty() || VertexCount <= 0 || TriangleCount <= 0)
    {
        UE_LOG(LogTemp, Error, TEXT("Phase 2C produced no triangulated DynamicMesh."));
        return 21;
    }

    TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("schema_version"), 1);
    Root->SetStringField(TEXT("status"), TEXT("YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS"));
    Root->SetStringField(TEXT("generator"), TEXT("PCGEx"));
    Root->SetStringField(TEXT("pcgex_commit"), PcgExCommit);
    Root->SetStringField(
        TEXT("pipeline"),
        TEXT("YACS cliff cells -> Clipper2 Union -> Path Smooth -> Path Subdivide -> Clipper2 Triangulate"));
    Root->SetBoolField(TEXT("canonical_landscape_mutation"), false);
    Root->SetBoolField(TEXT("assets_saved"), false);
    Root->SetBoolField(TEXT("graph_saved"), false);
    Root->SetNumberField(TEXT("source_skin_cell_count"), ExpectedSkinCells);
    Root->SetNumberField(TEXT("mesh_count"), Meshes.Num());
    Root->SetNumberField(TEXT("vertex_count"), VertexCount);
    Root->SetNumberField(TEXT("triangle_count"), TriangleCount);
    Root->SetArrayField(TEXT("meshes"), MoveTemp(Meshes));

    FString JsonText;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
    if (!FJsonSerializer::Serialize(Root.ToSharedRef(), Writer))
    {
        return 22;
    }
    if (!FFileHelper::SaveStringToFile(
            JsonText + LINE_TERMINATOR,
            *OutputPath,
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        UE_LOG(LogTemp, Error, TEXT("Could not write Phase 2C mesh receipt: %s"), *OutputPath);
        return 23;
    }

    UE_LOG(
        LogTemp,
        Display,
        TEXT("YACS Phase 2C PCGEx PASS: cells=%d meshes=%d vertices=%d triangles=%d output=%s"),
        ExpectedSkinCells,
        Root->GetIntegerField(TEXT("mesh_count")),
        VertexCount,
        TriangleCount,
        *OutputPath);
    return 0;
#endif
}
