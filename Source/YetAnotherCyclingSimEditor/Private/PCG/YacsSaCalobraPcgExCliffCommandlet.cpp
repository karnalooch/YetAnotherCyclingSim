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
#include "CompGeom/Delaunay2.h"
#include "Curve/GeneralPolygon2.h"
#include "Data/PCGBasePointData.h"
#include "Clipper2Lib/clipper.h"
#include "Polygon2.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "GeometryScript/MeshSubdivideFunctions.h"
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

    bool SanitizePlanarLoop(TArray<FVector2d>& Vertices)
    {
        constexpr double DuplicateToleranceSq = 1.e-12;
        constexpr double CollinearTolerance = 1.e-10;

        if (Vertices.Num() < 3)
        {
            return false;
        }

        // Remove consecutive duplicates, including a repeated closing point.
        TArray<FVector2d> Deduplicated;
        Deduplicated.Reserve(Vertices.Num());
        for (const FVector2d& Vertex : Vertices)
        {
            if (
                Deduplicated.IsEmpty()
                || FVector2d::DistSquared(Deduplicated.Last(), Vertex)
                    > DuplicateToleranceSq)
            {
                Deduplicated.Add(Vertex);
            }
        }
        if (
            Deduplicated.Num() > 1
            && FVector2d::DistSquared(Deduplicated[0], Deduplicated.Last())
                <= DuplicateToleranceSq)
        {
            Deduplicated.Pop();
        }
        Vertices = MoveTemp(Deduplicated);

        // Remove only mathematically redundant collinear/spike vertices. This
        // is contour hygiene, not simplification: every removed point lies on
        // the exact segment between its two neighbours.
        bool bRemoved = true;
        while (bRemoved && Vertices.Num() >= 3)
        {
            bRemoved = false;
            for (int32 Index = 0; Index < Vertices.Num(); ++Index)
            {
                const FVector2d& Previous =
                    Vertices[(Index + Vertices.Num() - 1) % Vertices.Num()];
                const FVector2d& Current = Vertices[Index];
                const FVector2d& Next =
                    Vertices[(Index + 1) % Vertices.Num()];

                const FVector2d Incoming = Current - Previous;
                const FVector2d Outgoing = Next - Current;
                const double Cross =
                    Incoming.X * Outgoing.Y - Incoming.Y * Outgoing.X;
                const double IncomingLengthSq =
                    Incoming.X * Incoming.X + Incoming.Y * Incoming.Y;
                const double OutgoingLengthSq =
                    Outgoing.X * Outgoing.X + Outgoing.Y * Outgoing.Y;
                const double Scale = FMath::Max(
                    1.0,
                    FMath::Sqrt(IncomingLengthSq * OutgoingLengthSq));
                const double Dot =
                    Incoming.X * Outgoing.X + Incoming.Y * Outgoing.Y;

                if (
                    IncomingLengthSq <= DuplicateToleranceSq
                    || OutgoingLengthSq <= DuplicateToleranceSq
                    || (FMath::Abs(Cross) <= CollinearTolerance * Scale
                        && Dot >= 0.0))
                {
                    Vertices.RemoveAt(Index);
                    bRemoved = true;
                    break;
                }
            }
        }

        if (Vertices.Num() < 3)
        {
            return false;
        }

        double TwiceSignedArea = 0.0;
        for (int32 Index = 0; Index < Vertices.Num(); ++Index)
        {
            const FVector2d& A = Vertices[Index];
            const FVector2d& B = Vertices[(Index + 1) % Vertices.Num()];
            TwiceSignedArea += A.X * B.Y - B.X * A.Y;
        }

        // A mathematically zero-area contour carries no authoritative
        // footprint. Reject it as contour hygiene before it can become a
        // degenerate hole/outer in UE's constrained triangulator.
        return FMath::Abs(TwiceSignedArea) > 1.e-8;
    }

    bool ExecuteGraph(
        UPCGGraph* Graph,
        TArray<TSharedPtr<FJsonValue>>& OutMeshes,
        int32& OutVertexCount,
        int32& OutTriangleCount,
        double& OutMaxEdgeBeforeCm,
        double& OutMaxEdgeAfterCm,
        int32& OutMaxTessellation,
        int32& OutUnionOuterCount,
        int32& OutUnionHoleCount,
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

        constexpr int32 ClipperPrecision = 100;
        constexpr double InvClipperPrecision =
            1.0 / static_cast<double>(ClipperPrecision);

        PCGExClipper2Lib::Paths64 SourcePaths;
        SourcePaths.reserve(Generated.TaggedData.Num());

        for (const FPCGTaggedData& Tagged : Generated.TaggedData)
        {
            const UPCGBasePointData* PointData =
                Cast<const UPCGBasePointData>(Tagged.Data);
            if (!PointData)
            {
                continue;
            }

            const auto Transforms = PointData->GetConstTransformValueRange();
            if (Transforms.Num() < 3)
            {
                continue;
            }

            PCGExClipper2Lib::Path64 Path;
            Path.reserve(Transforms.Num());
            for (int32 PointIndex = 0; PointIndex < Transforms.Num(); ++PointIndex)
            {
                const FVector Position = Transforms[PointIndex].GetLocation();
                Path.emplace_back(
                    FMath::RoundToInt64(Position.X * ClipperPrecision),
                    FMath::RoundToInt64(Position.Y * ClipperPrecision));
            }
            SourcePaths.push_back(MoveTemp(Path));
        }

        if (SourcePaths.size() != 1017)
        {
            OutError = FString::Printf(
                TEXT("Phase 2C source graph returned %d closed paths; expected 1017."),
                static_cast<int32>(SourcePaths.size()));
            return false;
        }

        // IMPORTANT: do not consume the PCG Boolean node's flattened path
        // output here. PCGEx 0.79's point-data restoration path drops small
        // nested rings. Use the same pinned PCGEx/Clipper2 implementation
        // directly and retain its PolyTree hierarchy losslessly.
        PCGExClipper2Lib::Clipper64 Clipper;
        Clipper.AddSubject(SourcePaths);
        PCGExClipper2Lib::PolyTree64 UnionTree;
        if (!Clipper.Execute(
                PCGExClipper2Lib::ClipType::Union,
                PCGExClipper2Lib::FillRule::NonZero,
                UnionTree))
        {
            OutError = TEXT("PCGEx embedded Clipper2 failed to union authoritative cliff cells.");
            return false;
        }

        struct FPolygonGroup
        {
            UE::Geometry::TPolygon2<double> Outer;
            TArray<UE::Geometry::TPolygon2<double>> Holes;
        };

        TArray<FPolygonGroup> PolygonGroups;
        OutUnionOuterCount = 0;
        OutUnionHoleCount = 0;

        auto ConvertClipperPath =
            [InvClipperPrecision](
                const PCGExClipper2Lib::Path64& InPath,
                TArray<FVector2d>& OutVertices) -> bool
            {
                OutVertices.Reset();
                OutVertices.Reserve(static_cast<int32>(InPath.size()));
                for (const PCGExClipper2Lib::Point64& Point : InPath)
                {
                    OutVertices.Add(
                        FVector2d(
                            static_cast<double>(Point.x) * InvClipperPrecision,
                            static_cast<double>(Point.y) * InvClipperPrecision));
                }
                return SanitizePlanarLoop(OutVertices);
            };

        TFunction<bool(const PCGExClipper2Lib::PolyPath64*)> CollectOuter;
        CollectOuter =
            [&](
                const PCGExClipper2Lib::PolyPath64* OuterNode) -> bool
            {
                if (!OuterNode)
                {
                    return true;
                }

                const PCGExClipper2Lib::Path64& OuterPath =
                    OuterNode->Polygon();
                if (OuterPath.empty())
                {
                    for (size_t ChildIndex = 0;
                         ChildIndex < OuterNode->Count();
                         ++ChildIndex)
                    {
                        if (!CollectOuter(OuterNode->Child(ChildIndex)))
                        {
                            return false;
                        }
                    }
                    return true;
                }

                TArray<FVector2d> OuterVertices;
                if (!ConvertClipperPath(OuterPath, OuterVertices))
                {
                    OutError = TEXT("PCGEx PolyTree produced an invalid outer contour.");
                    return false;
                }

                FPolygonGroup& Group = PolygonGroups.AddDefaulted_GetRef();
                Group.Outer =
                    UE::Geometry::TPolygon2<double>(MoveTemp(OuterVertices));
                if (Group.Outer.SignedArea() < 0.0)
                {
                    Group.Outer.Reverse();
                }
                ++OutUnionOuterCount;

                for (size_t HoleIndex = 0;
                     HoleIndex < OuterNode->Count();
                     ++HoleIndex)
                {
                    const PCGExClipper2Lib::PolyPath64* HoleNode =
                        OuterNode->Child(HoleIndex);
                    if (!HoleNode)
                    {
                        continue;
                    }

                    TArray<FVector2d> HoleVertices;
                    if (!ConvertClipperPath(
                            HoleNode->Polygon(),
                            HoleVertices))
                    {
                        OutError = TEXT("PCGEx PolyTree produced an invalid hole contour.");
                        return false;
                    }

                    UE::Geometry::TPolygon2<double> Hole(
                        MoveTemp(HoleVertices));
                    if (Hole.SignedArea() > 0.0)
                    {
                        Hole.Reverse();
                    }
                    Group.Holes.Add(MoveTemp(Hole));
                    ++OutUnionHoleCount;

                    // Children of a hole are solid islands and must restart
                    // as independent outer polygons.
                    for (size_t IslandIndex = 0;
                         IslandIndex < HoleNode->Count();
                         ++IslandIndex)
                    {
                        if (!CollectOuter(HoleNode->Child(IslandIndex)))
                        {
                            return false;
                        }
                    }
                }

                return true;
            };

        for (size_t RootIndex = 0;
             RootIndex < UnionTree.Count();
             ++RootIndex)
        {
            if (!CollectOuter(UnionTree.Child(RootIndex)))
            {
                return false;
            }
        }

        UE_LOG(
            LogYacsSaCalobraPcgExCliff,
            Display,
            TEXT("Phase 2C PCGEx PolyTree Union: outer_paths=%d hole_paths=%d."),
            OutUnionOuterCount,
            OutUnionHoleCount);

        if (OutUnionOuterCount != 19 || OutUnionHoleCount != 19)
        {
            OutError = FString::Printf(
                TEXT("PCGEx PolyTree authority mismatch: outer=%d/19 holes=%d/19."),
                OutUnionOuterCount,
                OutUnionHoleCount);
            return false;
        }

        for (int32 GroupIndex = 0; GroupIndex < PolygonGroups.Num(); ++GroupIndex)
        {
            FPolygonGroup& Group = PolygonGroups[GroupIndex];
            UE::Geometry::TGeneralPolygon2<double> GeneralPolygon(Group.Outer);

            for (const UE::Geometry::TPolygon2<double>& Hole : Group.Holes)
            {
                UE::Geometry::TPolygon2<double> HoleCopy = Hole;
                if (!GeneralPolygon.AddHole(MoveTemp(HoleCopy), true, true))
                {
                    OutError = FString::Printf(
                        TEXT("UE general polygon rejected PCGEx hole for outer %d: %dv/%.3fcm2."),
                        GroupIndex,
                        Hole.VertexCount(),
                        FMath::Abs(Hole.SignedArea()));
                    return false;
                }
            }

            UE::Geometry::FDelaunay2 Delaunay;
            TArray<UE::Geometry::FIndex3i> SurfaceTriangles;
            TArray<FVector2d> SurfaceVertices;
            if (!Delaunay.Triangulate(
                    GeneralPolygon,
                    &SurfaceTriangles,
                    &SurfaceVertices,
                    true)
                || SurfaceTriangles.IsEmpty()
                || SurfaceVertices.IsEmpty())
            {
                FString HoleSummary;
                for (int32 HoleIndex = 0; HoleIndex < Group.Holes.Num(); ++HoleIndex)
                {
                    HoleSummary += FString::Printf(
                        TEXT("%s%dv/%.3fcm2"),
                        HoleIndex == 0 ? TEXT("") : TEXT(","),
                        Group.Holes[HoleIndex].VertexCount(),
                        FMath::Abs(Group.Holes[HoleIndex].SignedArea()));
                }
                OutError = FString::Printf(
                    TEXT("UE 5.8 constrained Delaunay failed for PCGEx outer %d: outer=%dv/%.3fcm2 holes=%d [%s]."),
                    GroupIndex,
                    Group.Outer.VertexCount(),
                    FMath::Abs(Group.Outer.SignedArea()),
                    Group.Holes.Num(),
                    *HoleSummary);
                return false;
            }

            UE::Geometry::FDynamicMesh3 SurfaceMesh;
            TArray<int32> VertexIds;
            VertexIds.Reserve(SurfaceVertices.Num());
            for (const FVector2d& Position : SurfaceVertices)
            {
                VertexIds.Add(
                    SurfaceMesh.AppendVertex(FVector(Position.X, Position.Y, 0.0)));
            }

            for (const UE::Geometry::FIndex3i& Triangle : SurfaceTriangles)
            {
                if (
                    !VertexIds.IsValidIndex(Triangle.A)
                    || !VertexIds.IsValidIndex(Triangle.B)
                    || !VertexIds.IsValidIndex(Triangle.C))
                {
                    OutError = TEXT("UE constrained Delaunay returned an invalid vertex index.");
                    return false;
                }

                if (SurfaceMesh.AppendTriangle(
                        VertexIds[Triangle.A],
                        VertexIds[Triangle.B],
                        VertexIds[Triangle.C]) < 0)
                {
                    OutError = TEXT("Could not append UE constrained-Delaunay triangle.");
                    return false;
                }
            }

            UDynamicMesh* DynamicMesh =
                NewObject<UDynamicMesh>(GetTransientPackage());
            if (!DynamicMesh)
            {
                OutError = TEXT("Could not allocate transient tessellation mesh.");
                return false;
            }
            DynamicMesh->InitializeMesh();
            DynamicMesh->SetMesh(MoveTemp(SurfaceMesh));

            const UE::Geometry::FDynamicMesh3& BeforeMesh = DynamicMesh->GetMeshRef();
            const int32 PreTessVertices = BeforeMesh.VertexCount();
            const int32 PreTessTriangles = BeforeMesh.TriangleCount();
            const double MaxEdgeBefore = ComputeMaxEdgeLengthCm(BeforeMesh);
            OutMaxEdgeBeforeCm = FMath::Max(OutMaxEdgeBeforeCm, MaxEdgeBefore);

            const int32 RequiredSegments = FMath::Max(
                1,
                FMath::CeilToInt(MaxEdgeBefore / TargetEdgeCm));
            const int32 Tessellation = FMath::Clamp(
                RequiredSegments - 1,
                0,
                MaxTessellation);
            OutMaxTessellation = FMath::Max(OutMaxTessellation, Tessellation);

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

            const UE::Geometry::FDynamicMesh3& Mesh = DynamicMesh->GetMeshRef();
            const double MaxEdgeAfter = ComputeMaxEdgeLengthCm(Mesh);
            OutMaxEdgeAfterCm = FMath::Max(OutMaxEdgeAfterCm, MaxEdgeAfter);

            if (MaxEdgeAfter > TargetEdgeCm * 1.05)
            {
                OutError = FString::Printf(
                    TEXT("Phase 2C topology remains too coarse after deterministic tessellation: %.3f cm > %.3f cm."),
                    MaxEdgeAfter,
                    TargetEdgeCm * 1.05);
                return false;
            }
            if (Mesh.TriangleCount() > MaxTriangleCountPerMesh)
            {
                OutError = FString::Printf(
                    TEXT("Phase 2C topology exceeds per-mesh triangle budget: %d > %d."),
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
            MeshObject->SetNumberField(TEXT("source_component_index"), GroupIndex);
            MeshObject->SetNumberField(TEXT("hole_count"), Group.Holes.Num());
            MeshObject->SetNumberField(
                TEXT("pre_tessellation_vertex_count"),
                PreTessVertices);
            MeshObject->SetNumberField(
                TEXT("pre_tessellation_triangle_count"),
                PreTessTriangles);
            MeshObject->SetNumberField(TEXT("tessellation"), Tessellation);
            MeshObject->SetNumberField(TEXT("target_edge_cm"), TargetEdgeCm);
            MeshObject->SetNumberField(TEXT("max_edge_cm_before"), MaxEdgeBefore);
            MeshObject->SetNumberField(TEXT("max_edge_cm_after"), MaxEdgeAfter);
            MeshObject->SetArrayField(TEXT("vertices_cm"), MoveTemp(Vertices));
            MeshObject->SetArrayField(TEXT("triangles"), MoveTemp(Triangles));

            TArray<TSharedPtr<FJsonValue>> TagValues;
            TagValues.Add(MakeShared<FJsonValueString>(
                TEXT("YACS.Component230.CliffCandidate")));
            TagValues.Add(MakeShared<FJsonValueString>(
                TEXT("YACS.PCGEx.Clipper2Union")));
            TagValues.Add(MakeShared<FJsonValueString>(
                TEXT("YACS.UE58.ConstrainedDelaunay")));
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

    // Materialize only the exact YACS cell paths through stock PCG. The
    // topology operation itself is performed immediately after graph execution
    // with the pinned PCGEx-embedded Clipper2 PolyTree API, avoiding the
    // lossy PCG point-data restoration layer while keeping PCGEx as the
    // authoritative footprint topology implementation.
    const FName PathsPin(PathPinName);

    UPCGNode* OutputNode = Graph->GetOutputNode();
    if (!OutputNode || OutputNode->GetInputPins().IsEmpty())
    {
        return 20;
    }
    const FName GraphOutputPin = OutputNode->GetInputPins()[0]->Properties.Label;
    Graph->AddLabeledEdge(
        SourceNode,
        PathsPin,
        OutputNode,
        GraphOutputPin);

    TArray<TSharedPtr<FJsonValue>> Meshes;
    int32 VertexCount = 0;
    int32 TriangleCount = 0;
    double MaxEdgeBeforeCm = 0.0;
    double MaxEdgeAfterCm = 0.0;
    int32 MaxTessellation = 1;
    int32 UnionOuterCount = 0;
    int32 UnionHoleCount = 0;
    FString ExecutionError;
    if (!ExecuteGraph(
            Graph,
            Meshes,
            VertexCount,
            TriangleCount,
            MaxEdgeBeforeCm,
            MaxEdgeAfterCm,
            MaxTessellation,
            UnionOuterCount,
            UnionHoleCount,
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
        TEXT("YACS exact cliff cells -> pinned PCGEx embedded Clipper2 "
             "PolyTree Union(NonZero, lossless outer+hole hierarchy) -> "
             "UE 5.8 FDelaunay2(TGeneralPolygon2 holes) -> deterministic "
             "UE Uniform Tessellation; PCGEx owns admitted footprint topology, "
             "UE owns only surface triangulation; presentation smoothing remains "
             "post-drape so hard exclusions stay exact"));
    Root->SetBoolField(TEXT("canonical_landscape_mutation"), false);
    Root->SetBoolField(TEXT("assets_saved"), false);
    Root->SetBoolField(TEXT("graph_saved"), false);
    Root->SetNumberField(TEXT("source_skin_cell_count"), ExpectedSkinCells);
    Root->SetNumberField(TEXT("pcgex_union_outer_count"), UnionOuterCount);
    Root->SetNumberField(TEXT("pcgex_union_hole_count"), UnionHoleCount);
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
