#include "PCG/YacsSaCalobraPcgExCliffCommandlet.h"

#include "PCG/YacsSaCalobraCliffCellsSettings.h"

#include "Components/BoxComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "FileHelpers.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "PCGComponent.h"
#include "PCGData.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "PCGPin.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "WorldPartition/WorldPartitionHelpers.h"

#if YACS_WITH_PCGEX
#include "Data/PCGDynamicMeshData.h"
#include "Elements/PCGExClipper2Boolean.h"
#include "Elements/PCGExClipper2Triangulate.h"
#include "Elements/PCGExSmooth.h"
#include "Elements/PCGExSubdivide.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogYacsSaCalobraPcgExCliff, Log, All);

namespace
{
    constexpr TCHAR PathPinName[] = TEXT("Paths");
    constexpr TCHAR PcgExCommit[] =
        TEXT("39a8f1bdc65b2c4613a1e87b71d93b4576db0a66");

    bool Connect(
        UPCGGraph* Graph,
        UPCGNode* From,
        const FName FromPin,
        UPCGNode* To,
        const FName ToPin,
        const TCHAR* Description)
    {
        if (!Graph || !From || !To)
        {
            UE_LOG(
                LogYacsSaCalobraPcgExCliff,
                Error,
                TEXT("Phase 2C graph: null node while connecting %s."),
                Description);
            return false;
        }
        Graph->AddLabeledEdge(From, FromPin, To, ToPin);
        return true;
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
        TArray<TSharedPtr<FJsonValue>>& OutMeshes,
        int32& OutVertexCount,
        int32& OutTriangleCount,
        FString& OutError)
    {
        if (!Graph)
        {
            OutError = TEXT("Transient PCGEx graph is null.");
            return false;
        }

        UWorld* World = UEditorLoadingAndSavingUtils::NewBlankMap(false);
        if (!World)
        {
            OutError = TEXT("Could not create transient Phase 2C editor world.");
            return false;
        }

        FActorSpawnParameters SpawnParameters;
        SpawnParameters.Name = TEXT("YacsSaCalobraPhase2CHost");
        AActor* Host = World->SpawnActor<AActor>(
            AActor::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            SpawnParameters);
        if (!Host)
        {
            OutError = TEXT("Could not spawn Phase 2C scheduler host.");
            return false;
        }

        UBoxComponent* SchedulerBounds = NewObject<UBoxComponent>(
            Host,
            TEXT("YacsSaCalobraPhase2CSchedulerBounds"));
        if (!SchedulerBounds)
        {
            OutError = TEXT("Could not allocate Phase 2C scheduler bounds.");
            return false;
        }
        SchedulerBounds->InitBoxExtent(FVector(50.0));
        SchedulerBounds->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        SchedulerBounds->SetHiddenInGame(true);
        Host->SetRootComponent(SchedulerBounds);
        Host->AddInstanceComponent(SchedulerBounds);
        SchedulerBounds->RegisterComponent();

        UPCGComponent* Component =
            NewObject<UPCGComponent>(Host, TEXT("YacsSaCalobraPhase2CPCG"));
        if (!Component)
        {
            OutError = TEXT("Could not allocate Phase 2C PCG component.");
            return false;
        }
        Host->AddInstanceComponent(Component);
        Component->RegisterComponent();
        Component->SetGraphLocal(Graph);

        Component->GenerateLocal(true);
        FWorldPartitionHelpers::FakeEngineTick(World);

        constexpr double TimeoutSeconds = 120.0;
        const double StartedAt = FPlatformTime::Seconds();
        while (Component->IsGenerating())
        {
            if ((FPlatformTime::Seconds() - StartedAt) > TimeoutSeconds)
            {
                OutError = TEXT("PCGEx Phase 2C graph timed out.");
                return false;
            }
            FWorldPartitionHelpers::FakeEngineTick(World);
            FPlatformProcess::Sleep(0.01f);
        }
        FWorldPartitionHelpers::FakeEngineTick(World);

        const FPCGDataCollection& Generated = Component->GetGeneratedGraphOutput();
        for (const FPCGTaggedData& Tagged : Generated.TaggedData)
        {
            const UPCGDynamicMeshData* MeshData =
                Cast<const UPCGDynamicMeshData>(Tagged.Data);
            if (!MeshData || !MeshData->GetDynamicMesh())
            {
                continue;
            }

            const UE::Geometry::FDynamicMesh3& Mesh =
                MeshData->GetDynamicMesh()->GetMeshRef();
            if (Mesh.VertexCount() <= 0 || Mesh.TriangleCount() <= 0)
            {
                continue;
            }

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

            if (Vertices.IsEmpty() || Triangles.IsEmpty())
            {
                continue;
            }

            OutVertexCount += Vertices.Num();
            OutTriangleCount += Triangles.Num();
            TSharedRef<FJsonObject> MeshObject = MakeShared<FJsonObject>();
            MeshObject->SetArrayField(TEXT("vertices_cm"), MoveTemp(Vertices));
            MeshObject->SetArrayField(TEXT("triangles"), MoveTemp(Triangles));

            TArray<TSharedPtr<FJsonValue>> TagValues;
            for (const FString& Tag : Tagged.Tags)
            {
                TagValues.Add(MakeShared<FJsonValueString>(Tag));
            }
            MeshObject->SetArrayField(TEXT("tags"), MoveTemp(TagValues));
            OutMeshes.Add(MakeShared<FJsonValueObject>(MeshObject));
        }

        Component->CleanupLocalImmediate(true);
        return !OutMeshes.IsEmpty();
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
        LogYacsSaCalobraPcgExCliff,
        Error,
        TEXT("Phase 2C requires the pinned PCGEx checkout. "
             "Run Bootstrap-YacsPcgEx.ps1 -Mode Install first."));
    return 10;
#else
    FString PlanPath;
    FString OutputPath;
    if (!FParse::Value(*Params, TEXT("Plan="), PlanPath)
        || !FParse::Value(*Params, TEXT("ExecutionOutput="), OutputPath))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Usage: -run=YacsSaCalobraPcgExCliff "
                 "-Plan=<plan.json> -ExecutionOutput=<mesh.json>"));
        return 11;
    }
    if (FPaths::IsRelative(PlanPath))
    {
        PlanPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), PlanPath);
    }
    if (FPaths::IsRelative(OutputPath))
    {
        OutputPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), OutputPath);
    }

    const int32 ExpectedSkinCells = ReadExpectedSkinCellCount(PlanPath);
    if (ExpectedSkinCells <= 0)
    {
        UE_LOG(LogYacsSaCalobraPcgExCliff, Error, TEXT("Invalid Phase 2C plan: %s"), *PlanPath);
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

    UPCGSettings* SourceBase = nullptr;
    UPCGNode* SourceNode = Graph->AddNodeOfType(
        UYacsSaCalobraCliffCellsSettings::StaticClass(),
        SourceBase);
    UYacsSaCalobraCliffCellsSettings* Source =
        Cast<UYacsSaCalobraCliffCellsSettings>(SourceBase);
    if (!SourceNode || !Source)
    {
        return 14;
    }
    Source->PlanJsonPath = PlanPath;

    UPCGExClipper2BooleanSettings* Union = nullptr;
    UPCGNode* UnionNode =
        Graph->AddNodeOfType<UPCGExClipper2BooleanSettings>(Union);
    if (!UnionNode || !Union)
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

    UPCGExSmoothSettings* Smooth = nullptr;
    UPCGNode* SmoothNode = Graph->AddNodeOfType<UPCGExSmoothSettings>(Smooth);
    if (!SmoothNode || !Smooth)
    {
        return 16;
    }
    Smooth->bPreserveStart = false;
    Smooth->bPreserveEnd = false;
    Smooth->BlendingInterface = EPCGExBlendingInterface::Monolithic;
    Smooth->BlendingSettings =
        FPCGExBlendingDetails(EPCGExBlendingType::Average);
    Smooth->Influence.Constant = 0.35;
    Smooth->SmoothingAmount.Constant = 2.0;

    UPCGExSubdivideSettings* Subdivide = nullptr;
    UPCGNode* SubdivideNode =
        Graph->AddNodeOfType<UPCGExSubdivideSettings>(Subdivide);
    if (!SubdivideNode || !Subdivide)
    {
        return 17;
    }
    Subdivide->SubdivideMethod = EPCGExSubdivideMode::Distance;
    Subdivide->AmountInput = EPCGExInputValueType::Constant;
    Subdivide->Distance = 100.0;
    Subdivide->bRedistributeEvenly = true;

    UPCGExClipper2TriangulateSettings* Triangulate = nullptr;
    UPCGNode* TriangulateNode =
        Graph->AddNodeOfType<UPCGExClipper2TriangulateSettings>(Triangulate);
    if (!TriangulateNode || !Triangulate)
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

    const FName PathsPin(PathPinName);
    if (!Connect(
            Graph, SourceNode, PathsPin, UnionNode, PathsPin,
            TEXT("YACS cells -> Clipper2 Union"))
        || !Connect(
            Graph, UnionNode, PathsPin, SmoothNode, PathsPin,
            TEXT("Clipper2 Union -> Smooth"))
        || !Connect(
            Graph, SmoothNode, PathsPin, SubdivideNode, PathsPin,
            TEXT("Smooth -> Subdivide"))
        || !Connect(
            Graph, SubdivideNode, PathsPin, TriangulateNode, PathsPin,
            TEXT("Subdivide -> Clipper2 Triangulate")))
    {
        return 19;
    }

    UPCGNode* OutputNode = Graph->GetOutputNode();
    if (!OutputNode || OutputNode->GetInputPins().IsEmpty())
    {
        return 20;
    }
    const FName GraphOutputPin = OutputNode->GetInputPins()[0]->Properties.Label;
    Graph->AddLabeledEdge(
        TriangulateNode,
        FName(TEXT("Mesh")),
        OutputNode,
        GraphOutputPin);

    TArray<TSharedPtr<FJsonValue>> Meshes;
    int32 VertexCount = 0;
    int32 TriangleCount = 0;
    FString ExecutionError;
    if (!ExecuteGraph(
            Graph,
            Meshes,
            VertexCount,
            TriangleCount,
            ExecutionError))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Phase 2C PCGEx execution failed: %s"),
            *ExecutionError);
        return 21;
    }

    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("schema_version"), 1);
    Root->SetStringField(
        TEXT("status"),
        TEXT("YACS_SA_CALOBRA_PCGEX_CLIFF_MESH_PASS"));
    Root->SetStringField(TEXT("generator"), TEXT("PCGEx"));
    Root->SetStringField(TEXT("pcgex_commit"), PcgExCommit);
    Root->SetStringField(
        TEXT("pipeline"),
        TEXT("YACS cliff cells -> Clipper2 Union -> Path Smooth -> "
             "Path Subdivide -> Clipper2 Triangulate"));
    Root->SetBoolField(TEXT("canonical_landscape_mutation"), false);
    Root->SetBoolField(TEXT("assets_saved"), false);
    Root->SetBoolField(TEXT("graph_saved"), false);
    Root->SetNumberField(TEXT("source_skin_cell_count"), ExpectedSkinCells);
    Root->SetNumberField(TEXT("mesh_count"), Meshes.Num());
    Root->SetNumberField(TEXT("vertex_count"), VertexCount);
    Root->SetNumberField(TEXT("triangle_count"), TriangleCount);
    Root->SetArrayField(TEXT("meshes"), MoveTemp(Meshes));

    FString JsonText;
    const TSharedRef<TJsonWriter<>> Writer =
        TJsonWriterFactory<>::Create(&JsonText);
    if (!FJsonSerializer::Serialize(Root, Writer))
    {
        return 22;
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutputPath), true);
    if (!FFileHelper::SaveStringToFile(
            JsonText + LINE_TERMINATOR,
            *OutputPath,
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Could not write Phase 2C mesh receipt: %s"),
            *OutputPath);
        return 23;
    }

    UE_LOG(
        LogYacsSaCalobraPcgExCliff,
        Display,
        TEXT("YACS Phase 2C PCGEx PASS: cells=%d meshes=%d "
             "vertices=%d triangles=%d output=%s"),
        ExpectedSkinCells,
        Root->GetArrayField(TEXT("meshes")).Num(),
        VertexCount,
        TriangleCount,
        *OutputPath);
    return 0;
#endif
}
