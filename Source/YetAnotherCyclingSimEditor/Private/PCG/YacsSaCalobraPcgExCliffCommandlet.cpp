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
#include "DynamicSubmesh3.h"
#include "GeometryScript/MeshSubdivideFunctions.h"
#include "Selections/MeshConnectedComponents.h"
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
    double ComputeMaxEdgeLengthCm(const UE::Geometry::FDynamicMesh3& Mesh)
    {
        double MaxEdge = 0.0;
        for (const int32 TriangleId : Mesh.TriangleIndicesItr())
        {
            const UE::Geometry::FIndex3i Triangle = Mesh.GetTriangle(TriangleId);
            const FVector A = Mesh.GetVertex(Triangle.A);
            const FVector B = Mesh.GetVertex(Triangle.B);
            const FVector C = Mesh.GetVertex(Triangle.C);
            MaxEdge = FMath::Max(MaxEdge, FVector::Distance(A, B));
            MaxEdge = FMath::Max(MaxEdge, FVector::Distance(B, C));
            MaxEdge = FMath::Max(MaxEdge, FVector::Distance(C, A));
        }
        return MaxEdge;
    }

    bool ExecuteGraph(
        UPCGGraph* Graph,
        TArray<TSharedPtr<FJsonValue>>& OutMeshes,
        int32& OutVertexCount,
        int32& OutTriangleCount,
        double& OutMaxEdgeBeforeCm,
        double& OutMaxEdgeAfterCm,
        int32& OutMaxTessellation,
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

        // Execute through the same stock component path already proven by the
        // Passo Giau PCGEx authoring proof. The graph itself lives in a named
        // transient package (not GetTransientPackage), which gives PCG's graph
        // compiler a normal asset-style object lifecycle without ever writing
        // a package to disk.
        UE_LOG(LogYacsSaCalobraPcgExCliff, Display, TEXT("Phase 2C PCG: scheduling packaged transient graph."));
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
        UE_LOG(LogYacsSaCalobraPcgExCliff, Display, TEXT("Phase 2C PCG: generation completed."));

        const FPCGDataCollection& Generated = Component->GetGeneratedGraphOutput();
        if (Generated.TaggedData.IsEmpty())
        {
            OutError = TEXT("PCGEx Phase 2C graph produced no output data.");
            return false;
        }
        constexpr double TargetEdgeCm = 150.0;
        constexpr int32 MaxTessellation = 12;
        constexpr int32 MaxTriangleCountPerMesh = 60000;

        for (const FPCGTaggedData& Tagged : Generated.TaggedData)
        {
            const UPCGDynamicMeshData* MeshData =
                Cast<const UPCGDynamicMeshData>(Tagged.Data);
            if (!MeshData || !MeshData->GetDynamicMesh())
            {
                continue;
            }

            const UE::Geometry::FDynamicMesh3& SourceMesh =
                MeshData->GetDynamicMesh()->GetMeshRef();
            if (SourceMesh.VertexCount() <= 0 || SourceMesh.TriangleCount() <= 0)
            {
                continue;
            }

            // PCGEx currently emits the consolidated admitted footprint as one
            // DynamicMesh containing the disconnected cliff islands. A single
            // longest edge must not force every island to the same uniform
            // tessellation level. Split by real triangle connectivity first,
            // then densify each component independently.
            UE::Geometry::FMeshConnectedComponents Components(&SourceMesh);
            Components.FindConnectedTriangles();
            if (Components.Num() <= 0)
            {
                continue;
            }

            TArray<int32> ComponentOrder;
            ComponentOrder.Reserve(Components.Num());
            for (int32 ComponentIndex = 0; ComponentIndex < Components.Num(); ++ComponentIndex)
            {
                ComponentOrder.Add(ComponentIndex);
            }
            ComponentOrder.Sort(
                [&Components](const int32 Left, const int32 Right)
                {
                    const TArray<int>& LeftTriangles =
                        Components.GetComponent(Left).Indices;
                    const TArray<int>& RightTriangles =
                        Components.GetComponent(Right).Indices;
                    const int32 LeftMin =
                        LeftTriangles.IsEmpty() ? MAX_int32 : Algo::Min(LeftTriangles);
                    const int32 RightMin =
                        RightTriangles.IsEmpty() ? MAX_int32 : Algo::Min(RightTriangles);
                    return LeftMin < RightMin;
                });

            for (const int32 ComponentIndex : ComponentOrder)
            {
                const TArray<int>& TriangleIds =
                    Components.GetComponent(ComponentIndex).Indices;
                if (TriangleIds.IsEmpty())
                {
                    continue;
                }

                UE::Geometry::FDynamicSubmesh3 Submesh(
                    &SourceMesh,
                    TriangleIds,
                    static_cast<int>(UE::Geometry::EMeshComponents::None),
                    false);
                UE::Geometry::FDynamicMesh3 ComponentMesh =
                    MoveTemp(Submesh.GetSubmesh());
                if (ComponentMesh.VertexCount() <= 0 || ComponentMesh.TriangleCount() <= 0)
                {
                    continue;
                }

                UDynamicMesh* DynamicMesh =
                    NewObject<UDynamicMesh>(GetTransientPackage());
                if (!DynamicMesh)
                {
                    OutError = TEXT("Could not allocate transient component tessellation mesh.");
                    return false;
                }
                DynamicMesh->InitializeMesh();
                DynamicMesh->SetMesh(MoveTemp(ComponentMesh));

                const UE::Geometry::FDynamicMesh3& BeforeMesh =
                    DynamicMesh->GetMeshRef();
                const int32 PreTessVertices = BeforeMesh.VertexCount();
                const int32 PreTessTriangles = BeforeMesh.TriangleCount();
                const double MaxEdgeBefore = ComputeMaxEdgeLengthCm(BeforeMesh);
                OutMaxEdgeBeforeCm =
                    FMath::Max(OutMaxEdgeBeforeCm, MaxEdgeBefore);

                // FUniformTessellate inserts TessellationNum points along each
                // original edge, yielding TessellationNum + 1 edge segments.
                // Therefore the minimum level that satisfies TargetEdgeCm is
                // ceil(edge/target) - 1, not ceil(edge/target).
                const int32 RequiredSegments = FMath::Max(
                    1,
                    FMath::CeilToInt(MaxEdgeBefore / TargetEdgeCm));
                const int32 Tessellation = FMath::Clamp(
                    RequiredSegments - 1,
                    0,
                    MaxTessellation);
                OutMaxTessellation =
                    FMath::Max(OutMaxTessellation, Tessellation);

                if (Tessellation > 0)
                {
                    UDynamicMesh* Result =
                        UGeometryScriptLibrary_MeshSubdivideFunctions::ApplyUniformTessellation(
                            DynamicMesh,
                            Tessellation,
                            nullptr);
                    if (Result != DynamicMesh)
                    {
                        OutError = TEXT("GeometryScript uniform tessellation failed.");
                        return false;
                    }
                }

                const UE::Geometry::FDynamicMesh3& Mesh =
                    DynamicMesh->GetMeshRef();
                const double MaxEdgeAfter = ComputeMaxEdgeLengthCm(Mesh);
                OutMaxEdgeAfterCm =
                    FMath::Max(OutMaxEdgeAfterCm, MaxEdgeAfter);

                if (MaxEdgeAfter > TargetEdgeCm * 1.05)
                {
                    OutError = FString::Printf(
                        TEXT("Phase 2C component topology remains too coarse after deterministic tessellation: %.3f cm > %.3f cm."),
                        MaxEdgeAfter,
                        TargetEdgeCm * 1.05);
                    return false;
                }
                if (Mesh.TriangleCount() > MaxTriangleCountPerMesh)
                {
                    OutError = FString::Printf(
                        TEXT("Phase 2C component topology exceeds per-mesh triangle budget: %d > %d."),
                        Mesh.TriangleCount(),
                        MaxTriangleCountPerMesh);
                    return false;
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
                    const UE::Geometry::FIndex3i Triangle =
                        Mesh.GetTriangle(TriangleId);
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
                TSharedRef<FJsonObject> MeshObject =
                    MakeShared<FJsonObject>();
                MeshObject->SetNumberField(
                    TEXT("source_component_index"),
                    ComponentIndex);
                MeshObject->SetNumberField(
                    TEXT("pre_tessellation_vertex_count"),
                    PreTessVertices);
                MeshObject->SetNumberField(
                    TEXT("pre_tessellation_triangle_count"),
                    PreTessTriangles);
                MeshObject->SetNumberField(
                    TEXT("tessellation"),
                    Tessellation);
                MeshObject->SetNumberField(
                    TEXT("target_edge_cm"),
                    TargetEdgeCm);
                MeshObject->SetNumberField(
                    TEXT("max_edge_cm_before"),
                    MaxEdgeBefore);
                MeshObject->SetNumberField(
                    TEXT("max_edge_cm_after"),
                    MaxEdgeAfter);
                MeshObject->SetArrayField(
                    TEXT("vertices_cm"),
                    MoveTemp(Vertices));
                MeshObject->SetArrayField(
                    TEXT("triangles"),
                    MoveTemp(Triangles));

                TArray<TSharedPtr<FJsonValue>> TagValues;
                for (const FString& Tag : Tagged.Tags)
                {
                    TagValues.Add(
                        MakeShared<FJsonValueString>(Tag));
                }
                MeshObject->SetArrayField(
                    TEXT("tags"),
                    MoveTemp(TagValues));
                OutMeshes.Add(
                    MakeShared<FJsonValueObject>(MeshObject));
            }
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

    constexpr TCHAR GraphPackageName[] =
        TEXT("/Game/WorldGen/PCGEx/Transient/PCG_SaCalobra_Component230_Phase2C");
    constexpr TCHAR GraphAssetName[] =
        TEXT("PCG_SaCalobra_Component230_Phase2C");
    const FString GraphFilename = FPackageName::LongPackageNameToFilename(
        GraphPackageName,
        FPackageName::GetAssetPackageExtension());
    if (IFileManager::Get().FileExists(*GraphFilename))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Phase 2C transient graph unexpectedly exists on disk: %s"),
            *GraphFilename);
        return 13;
    }

    UPackage* GraphPackage = CreatePackage(GraphPackageName);
    if (!GraphPackage)
    {
        return 13;
    }
    GraphPackage->SetFlags(RF_Transient);

    UPCGGraph* Graph = NewObject<UPCGGraph>(
        GraphPackage,
        GraphAssetName,
        RF_Public | RF_Standalone | RF_Transient);
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

    // Smooth may never weaken YACS hard exclusions. Intersect the refined
    // boundary back with the original admitted union before triangulation.
    UPCGExClipper2BooleanSettings* HardClip = nullptr;
    UPCGNode* HardClipNode =
        Graph->AddNodeOfType<UPCGExClipper2BooleanSettings>(HardClip);
    if (!HardClipNode || !HardClip)
    {
        return 18;
    }
    HardClip->Operation = EPCGExClipper2BooleanOp::Intersection;
    HardClip->FillRule = EPCGExClipper2FillRule::NonZero;
    HardClip->MainInputGroupingPolicy = EPCGExGroupingPolicy::Consolidate;
    HardClip->bSkipOpenPaths = true;
    HardClip->OpenPathsOutput = EPCGExClipper2OpenPathOutput::Ignore;
    HardClip->bSimplifyPaths = true;
    HardClip->bPreserveCollinear = false;

    UPCGExClipper2TriangulateSettings* Triangulate = nullptr;
    UPCGNode* TriangulateNode =
        Graph->AddNodeOfType<UPCGExClipper2TriangulateSettings>(Triangulate);
    if (!TriangulateNode || !Triangulate)
    {
        return 19;
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
            Graph, SubdivideNode, PathsPin, HardClipNode, PathsPin,
            TEXT("Subdivide -> hard-policy intersection subjects"))
        || !Connect(
            Graph, UnionNode, PathsPin, HardClipNode, FName(TEXT("Operands")),
            TEXT("Original YACS union -> hard-policy intersection operands"))
        || !Connect(
            Graph, HardClipNode, PathsPin, TriangulateNode, PathsPin,
            TEXT("Hard-policy intersection -> Clipper2 Triangulate")))
    {
        return 20;
    }

    UPCGNode* OutputNode = Graph->GetOutputNode();
    if (!OutputNode || OutputNode->GetInputPins().IsEmpty())
    {
        return 21;
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
    double MaxEdgeBeforeCm = 0.0;
    double MaxEdgeAfterCm = 0.0;
    int32 MaxTessellation = 1;
    FString ExecutionError;
    if (!ExecuteGraph(
            Graph,
            Meshes,
            VertexCount,
            TriangleCount,
            MaxEdgeBeforeCm,
            MaxEdgeAfterCm,
            MaxTessellation,
            ExecutionError))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Phase 2C PCGEx execution failed: %s"),
            *ExecutionError);
        return 22;
    }

    if (IFileManager::Get().FileExists(*GraphFilename))
    {
        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Error,
            TEXT("Phase 2C transient PCG graph was persisted unexpectedly: %s"),
            *GraphFilename);
        return 22;
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
             "Path Subdivide -> Clipper2 Intersection(original YACS union) -> "
             "Clipper2 Triangulate -> connected-component-aware deterministic "
             "UE Uniform Tessellation"));
    Root->SetBoolField(TEXT("canonical_landscape_mutation"), false);
    Root->SetBoolField(TEXT("assets_saved"), false);
    Root->SetBoolField(TEXT("graph_saved"), false);
    Root->SetNumberField(TEXT("source_skin_cell_count"), ExpectedSkinCells);
    Root->SetNumberField(TEXT("mesh_count"), Meshes.Num());
    Root->SetNumberField(TEXT("vertex_count"), VertexCount);
    Root->SetNumberField(TEXT("triangle_count"), TriangleCount);
    Root->SetNumberField(TEXT("target_edge_cm"), 150.0);
    Root->SetNumberField(TEXT("max_edge_cm_before"), MaxEdgeBeforeCm);
    Root->SetNumberField(TEXT("max_edge_cm_after"), MaxEdgeAfterCm);
    Root->SetNumberField(TEXT("max_tessellation"), MaxTessellation);
    Root->SetArrayField(TEXT("meshes"), MoveTemp(Meshes));

    FString JsonText;
    const TSharedRef<TJsonWriter<>> Writer =
        TJsonWriterFactory<>::Create(&JsonText);
    if (!FJsonSerializer::Serialize(Root, Writer))
    {
        return 23;
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
        return 24;
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
