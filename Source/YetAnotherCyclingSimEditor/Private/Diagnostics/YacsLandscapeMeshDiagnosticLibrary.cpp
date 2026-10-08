#include "Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h"

#include "LandscapeComponent.h"
#include "LandscapeProxy.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "MeshDescriptionToDynamicMesh.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/MeshNormals.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "DynamicMesh/DynamicMeshOverlay.h"
#include "Operations/SelectiveTessellate.h"
#include "Operations/MeshBevel.h"
#include "Distance/DistPoint3Triangle3.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
// Keep Epic's topology and profile implementations, but admit the profile only
// after the linear bevel has independently passed the terrain constraints.
class FGuardedLimestoneBevel : public UE::Geometry::FMeshBevel
{
public:
    void ApplyRoundProfile(UE::Geometry::FDynamicMesh3& Mesh) { ApplyProfileShape_Round(Mesh); }
    void UpdateNormals(UE::Geometry::FDynamicMesh3& Mesh) { ComputeNormals(Mesh); }
    void GetTerminatorSpokes(TArray<UE::Geometry::FIndex2i>& Spokes) const
    {
        Spokes.Reset();
        for (const FBevelVertex& Vertex : Vertices)
        {
            if (Vertex.VertexType == EBevelVertexType::TerminatorVertex)
            { Spokes.Add(UE::Geometry::FIndex2i(Vertex.VertexID, Vertex.TerminatorInfo.B)); }
        }
    }
};

// Narrow edge treatment only: no terrain erosion or surface relaxation.
bool RoundLimestoneEdges(UE::Geometry::FDynamicMesh3& Mesh,
    const TSet<FIntPoint>& AllowedQuads, const TSharedRef<FJsonObject>& Report, FString& Error)
{
    using namespace UE::Geometry;
    const FDynamicMesh3 Source(Mesh);
    TArray<bool> Safe;
    Safe.Init(true, Source.MaxVertexID());
    TMap<FIntPoint, TArray<int32>> Tiles;
    for (int32 T : Source.TriangleIndicesItr())
    {
        const auto F = Source.GetTriangle(T);
        const FVector3d P = (Source.GetVertex(F.A) + Source.GetVertex(F.B) + Source.GetVertex(F.C)) / 3.0;
        const FIntPoint Tile(FMath::FloorToInt(P.X / 50.0), FMath::FloorToInt(P.Y / 50.0));
        Tiles.FindOrAdd(Tile).Add(T);
        if (!AllowedQuads.Contains(Tile)) { Safe[F.A] = Safe[F.B] = Safe[F.C] = false; }
    }
    for (int32 V : Source.VertexIndicesItr()) { if (Source.IsBoundaryVertex(V)) { Safe[V] = false; } }
    TArray<int32> Edges;
    TSet<int32> EdgeVertices;
    for (int32 E : Source.EdgeIndicesItr())
    {
        if (Source.IsBoundaryEdge(E)) { continue; }
        const auto V = Source.GetEdgeV(E);
        if (!Safe[V.A] || !Safe[V.B]) { continue; }
        const auto T = Source.GetEdgeT(E);
        FVector3d N0 = Source.GetTriNormal(T.A), N1 = Source.GetTriNormal(T.B);
        if (N0.Z < 0) { N0 = -N0; }
        if (N1.Z < 0) { N1 = -N1; }
        if (FVector3d::DotProduct(N0, N1) >= FMath::Cos(FMath::DegreesToRadians(45.0))) { continue; }
        const auto F = Source.GetTriangle(T.B);
        const int32 Other = F.A != V.A && F.A != V.B ? F.A : (F.B != V.A && F.B != V.B ? F.B : F.C);
        if (FVector3d::DotProduct(N0, Source.GetVertex(Other) - Source.GetVertex(V.A)) >= -1.0) { continue; }
        Edges.Add(E); EdgeVertices.Add(V.A); EdgeVertices.Add(V.B);
    }
    if (Edges.IsEmpty()) { Error = TEXT("no eligible sharp convex limestone edges"); return false; }

    // Epic's terminator fan reaches the next unselected neighbor. On this
    // half-metre mesh that can deform a complete face far outside the edge
    // treatment. Inspect Epic's actual chosen terminator spokes and insert
    // source-exact points only on their closing spokes. Continuing edges and
    // junctions retain local support on each unselected spoke, so a nonplanar
    // source fan cannot be deformed beyond the narrow band.
    TArray<int32> SelectedDegree;
    SelectedDegree.Init(0, Source.MaxVertexID());
    TSet<int32> SelectedEdgeSet;
    TArray<FIndex2i> SelectedPairs;
    for (int32 E : Edges)
    {
        const auto V = Source.GetEdgeV(E);
        ++SelectedDegree[V.A]; ++SelectedDegree[V.B];
        SelectedEdgeSet.Add(E); SelectedPairs.Add(V);
    }
    FDynamicMesh3 TopologySource(Source);
    TopologySource.ReverseOrientation(false);
    FGuardedLimestoneBevel Topology;
    Topology.InitializeFromTriangleEdges(TopologySource, Edges);
    TArray<FIndex2i> TerminatorSpokes;
    Topology.GetTerminatorSpokes(TerminatorSpokes);
    TSet<FIntPoint> TerminatorPairs;
    for (const auto V : TerminatorSpokes)
    {
        const int32 E = Source.FindEdge(V.A, V.B);
        if (E == IndexConstants::InvalidID || SelectedEdgeSet.Contains(E))
        { Error = TEXT("invalid native terminator spoke"); return false; }
        TerminatorPairs.Add(FIntPoint(V.A, V.B));
    }
    FDynamicMesh3 LocalSource(Source);
    int32 EndpointSplits = 0;
    constexpr double EndpointRadiusCm = 6.0;
    auto SplitSpoke = [&LocalSource, &EndpointSplits, EndpointRadiusCm](int32 Center, int32 Neighbor, int32& NewVertex)
    {
        const int32 E = LocalSource.FindEdge(Center, Neighbor);
        if (E == IndexConstants::InvalidID) { return false; }
        const auto V = LocalSource.GetEdgeV(E);
        const double Length = (LocalSource.GetVertex(Neighbor) - LocalSource.GetVertex(Center)).Length();
        if (!FMath::IsFinite(Length) || Length <= 2.0 * EndpointRadiusCm) { return false; }
        const double Fraction = EndpointRadiusCm / Length;
        FDynamicMesh3::FEdgeSplitInfo Info;
        if (LocalSource.SplitEdge(E, Info, V.A == Center ? Fraction : 1.0 - Fraction) != EMeshResult::Ok)
        { return false; }
        NewVertex = Info.NewVertex; ++EndpointSplits;
        return true;
    };
    for (int32 E : Source.EdgeIndicesItr())
    {
        if (SelectedEdgeSet.Contains(E)) { continue; }
        const auto V = Source.GetEdgeV(E);
        const bool SplitA = SelectedDegree[V.A] >= 2 || TerminatorPairs.Contains(FIntPoint(V.A, V.B));
        const bool SplitB = SelectedDegree[V.B] >= 2 || TerminatorPairs.Contains(FIntPoint(V.B, V.A));
        int32 NeighborForB = V.A, NewVertex = IndexConstants::InvalidID;
        if (SplitA)
        {
            if (!SplitSpoke(V.A, V.B, NewVertex)) { Error = TEXT("local endpoint source split failed"); return false; }
            NeighborForB = NewVertex;
        }
        if (SplitB && !SplitSpoke(V.B, NeighborForB, NewVertex))
        { Error = TEXT("local endpoint source split failed"); return false; }
    }
    TArray<int32> LocalEdges;
    for (const auto V : SelectedPairs)
    {
        const int32 E = LocalSource.FindEdge(V.A, V.B);
        if (E == IndexConstants::InvalidID) { Error = TEXT("local split lost a selected native edge"); return false; }
        LocalEdges.Add(E);
    }
    Report->SetNumberField(TEXT("endpoint_source_split_count"), EndpointSplits);
    Report->SetNumberField(TEXT("native_terminator_spoke_count"), TerminatorPairs.Num());
    Report->SetNumberField(TEXT("endpoint_source_split_radius_cm"), EndpointRadiusCm);
    Report->SetNumberField(TEXT("endpoint_refined_source_triangles"), LocalSource.TriangleCount());

    auto BandDistance = [&Source, &Edges](const FVector3d& P)
    {
        double Best = TNumericLimits<double>::Max();
        for (int32 E : Edges)
        {
            const auto V = Source.GetEdgeV(E);
            const FVector3d A = Source.GetVertex(V.A), D = Source.GetVertex(V.B) - A;
            const double U = FMath::Clamp(FVector3d::DotProduct(P - A, D) / D.SquaredLength(), 0.0, 1.0);
            Best = FMath::Min(Best, (P - A - U * D).Length());
        }
        return Best;
    };
    auto SourceClosest = [&Source, &Tiles](const FVector3d& P, FVector3d& Q)
    {
        const FIntPoint Tile(FMath::FloorToInt(P.X / 50.0), FMath::FloorToInt(P.Y / 50.0));
        double Best = TNumericLimits<double>::Max();
        for (int32 DX = -1; DX <= 1; ++DX) for (int32 DY = -1; DY <= 1; ++DY)
        {
            const auto* Faces = Tiles.Find(Tile + FIntPoint(DX, DY));
            if (!Faces) { continue; }
            for (int32 T : *Faces)
            {
                const auto F = Source.GetTriangle(T);
                FDistPoint3Triangle3d Query(P, FTriangle3d(Source.GetVertex(F.A), Source.GetVertex(F.B), Source.GetVertex(F.C)));
                const double Distance = Query.GetSquared();
                if (Distance < Best) { Best = Distance; Q = Query.ClosestTrianglePoint; }
            }
        }
        // A valid edit is within 10 cm of a selected native edge, so its nearest
        // source facet necessarily falls inside this bounded native XY search.
        return FMath::IsFinite(Best) && Best < 100.000001;
    };
    // Epic's inset is not itself a width guarantee at junctions. Independently
    // enforce a 10 cm radius (20 cm total band) and a 20 cm source-relative cap.
    bool Accepted = false;
    TArray<FVector3d> Original;
    double MaxShift = 0, MaxBand = 0, ChosenInset = 0, ChosenProfileAlpha = 0, MaxProfileShift = 0;
    int32 ChosenSubdivisions = 0;
    TArray<TSharedPtr<FJsonValue>> Attempts;
    for (const FIntPoint Attempt : {FIntPoint(2, 5), FIntPoint(2, 3), FIntPoint(2, 2), FIntPoint(1, 5), FIntPoint(1, 3), FIntPoint(1, 2), FIntPoint(1, 1)})
    {
        const double Inset = Attempt.Y;
        const auto Trial = MakeShared<FJsonObject>();
        Trial->SetNumberField(TEXT("inset_cm"), Inset);
        Trial->SetNumberField(TEXT("subdivisions"), Attempt.X);
        Attempts.Add(MakeShared<FJsonValueObject>(Trial));
        Report->SetArrayField(TEXT("bevel_attempts"), Attempts);
        Mesh = LocalSource;
        // Native Landscape export has downward geometric winding. Bevel needs
        // outward (upward) orientation; retain copied native shading normals.
        Mesh.ReverseOrientation(false);
        const FDynamicMesh3 BevelSource(Mesh);
        FGuardedLimestoneBevel Bevel;
        Bevel.InsetDistance = Inset; Bevel.NumSubdivisions = Attempt.X; Bevel.RoundWeight = 0;
        Bevel.InitializeFromTriangleEdges(BevelSource, LocalEdges);
        if (!Bevel.Apply(Mesh, nullptr)) { Trial->SetStringField(TEXT("failure"), TEXT("operation")); continue; }
        Trial->SetNumberField(TEXT("triangles"), Mesh.TriangleCount());
        if (Mesh.TriangleCount() > 60000) { Trial->SetStringField(TEXT("failure"), TEXT("triangle_budget")); continue; }
        auto Validate = [&](const TSharedRef<FJsonObject>& Check)
        {
            Original.SetNum(Mesh.MaxVertexID()); MaxShift = MaxBand = 0;
            for (int32 V : Source.VertexIndicesItr())
            {
                if (!Mesh.IsVertex(V) || (!EdgeVertices.Contains(V) && (Mesh.GetVertex(V) - Source.GetVertex(V)).Length() > 1.e-8))
                { Check->SetStringField(TEXT("failure"), TEXT("source_id_or_outside_vertex")); return false; }
            }
            for (int32 V : Mesh.VertexIndicesItr())
            {
                const FVector3d P = Mesh.GetVertex(V);
                FVector3d Q;
                if (Source.IsVertex(V) && !EdgeVertices.Contains(V)) { Q = Source.GetVertex(V); }
                else if (!SourceClosest(P, Q)) { Check->SetStringField(TEXT("failure"), TEXT("source_projection")); return false; }
                Original[V] = Q;
                const double Shift = (P - Q).Length();
                const bool Edited = !Source.IsVertex(V) || (P - Source.GetVertex(V)).Length() > 1.e-8;
                if (Edited)
                {
                    const double Band = FMath::Max(BandDistance(P), BandDistance(Q));
                    MaxBand = FMath::Max(MaxBand, Band);
                    if (Band > 10.000001 || Shift > 20.000001 || P.ContainsNaN())
                    {
                        Check->SetStringField(TEXT("failure"), TEXT("band_or_displacement"));
                        Check->SetNumberField(TEXT("band_cm"), Band); Check->SetNumberField(TEXT("shift_cm"), Shift);
                        return false;
                    }
                }
                MaxShift = FMath::Max(MaxShift, Shift);
            }
            for (int32 T : Mesh.TriangleIndicesItr())
            {
                const auto F = Mesh.GetTriangle(T);
                const double Area = FVector3d::CrossProduct(Mesh.GetVertex(F.B) - Mesh.GetVertex(F.A), Mesh.GetVertex(F.C) - Mesh.GetVertex(F.A)).Z;
                // The trial is still in Epic's upward orientation at this point.
                if (!FMath::IsFinite(Area) || Area <= 1.e-8)
                {
                    Check->SetStringField(TEXT("failure"), TEXT("xy_fold"));
                    Check->SetNumberField(TEXT("fold_area_z_cm2"), -Area);
                    TArray<TSharedPtr<FJsonValue>> Points;
                    for (int32 V : {F.A, F.B, F.C})
                    {
                        const FVector3d P = Mesh.GetVertex(V);
                        TArray<TSharedPtr<FJsonValue>> Row;
                        for (double X : {P.X, P.Y, P.Z}) { Row.Add(MakeShared<FJsonValueNumber>(X)); }
                        Points.Add(MakeShared<FJsonValueArray>(Row));
                    }
                    Check->SetArrayField(TEXT("fold_vertices_cm"), Points);
                    return false;
                }
            }
            return true;
        };
        const auto LinearCheck = MakeShared<FJsonObject>();
        Trial->SetObjectField(TEXT("linear_check"), LinearCheck);
        if (!Validate(LinearCheck)) { Trial->SetStringField(TEXT("failure"), TEXT("linear_base_guard")); continue; }
        TArray<FVector3d> LinearPositions, RoundedPositions;
        LinearPositions.SetNum(Mesh.MaxVertexID()); RoundedPositions.SetNum(Mesh.MaxVertexID());
        for (int32 V : Mesh.VertexIndicesItr()) { LinearPositions[V] = Mesh.GetVertex(V); }
        Bevel.RoundWeight = 0.5;
        Bevel.ApplyRoundProfile(Mesh);
        double ProfileShift = 0;
        for (int32 V : Mesh.VertexIndicesItr())
        {
            RoundedPositions[V] = Mesh.GetVertex(V);
            ProfileShift = FMath::Max(ProfileShift, (RoundedPositions[V] - LinearPositions[V]).Length());
        }
        if (!FMath::IsFinite(ProfileShift) || ProfileShift <= 1.e-6)
        { Trial->SetStringField(TEXT("failure"), TEXT("empty_or_nonfinite_round_profile")); continue; }
        TArray<TSharedPtr<FJsonValue>> ProfileAttempts;
        for (int32 Backtrack = 0; Backtrack <= 16; ++Backtrack)
        {
            const double Alpha = FMath::Pow(0.5, Backtrack);
            const auto ProfileCheck = MakeShared<FJsonObject>();
            ProfileCheck->SetNumberField(TEXT("alpha"), Alpha);
            ProfileAttempts.Add(MakeShared<FJsonValueObject>(ProfileCheck));
            Trial->SetArrayField(TEXT("profile_attempts"), ProfileAttempts);
            for (int32 V : Mesh.VertexIndicesItr())
            { Mesh.SetVertex(V, LinearPositions[V] + Alpha * (RoundedPositions[V] - LinearPositions[V])); }
            if (Alpha * ProfileShift <= 1.e-6 || !Validate(ProfileCheck)) { continue; }
            // Apply() computed normals on the linear mesh; finalize only after
            // the accepted profile positions are known.
            Bevel.UpdateNormals(Mesh);
            Accepted = true; ChosenInset = Inset; ChosenSubdivisions = Attempt.X;
            ChosenProfileAlpha = Alpha; MaxProfileShift = Alpha * ProfileShift;
            break;
        }
        if (Accepted) { Mesh.ReverseOrientation(false); break; }
        Trial->SetStringField(TEXT("failure"), TEXT("round_profile_guard"));
    }
    if (!Accepted) { Error = TEXT("edge bevel failed strict band, unchanged-surface, fold or triangle guards"); return false; }
    if (!Source.HasAttributes() || !Mesh.HasAttributes() || !Source.Attributes()->PrimaryNormals() || !Mesh.Attributes()->PrimaryNormals())
    { Error = TEXT("edge bevel lost native normals"); return false; }
    auto* Normals = Mesh.Attributes()->PrimaryNormals();
    const auto* SourceNormals = Source.Attributes()->PrimaryNormals();
    int32 PreservedNormals = 0;
    for (int32 E : SourceNormals->ElementIndicesItr())
    {
        const int32 V = SourceNormals->GetParentVertex(E);
        if (EdgeVertices.Contains(V)) { continue; }
        if (!Normals->IsElement(E) || Normals->GetParentVertex(E) != V)
        { Error = TEXT("bevel changed an outside normal element identity"); return false; }
        FVector3f N; SourceNormals->GetElement(E, N); Normals->SetElement(E, N); ++PreservedNormals;
    }
    TArray<TSharedPtr<FJsonValue>> Rows, Faces, SourceRows, SourceFaces, SelectedEdges;
    auto Row = [](std::initializer_list<double> Values)
    {
        TArray<TSharedPtr<FJsonValue>> Result;
        for (double X : Values) { Result.Add(MakeShared<FJsonValueNumber>(X)); }
        return MakeShared<FJsonValueArray>(Result);
    };
    for (int32 V : Mesh.VertexIndicesItr())
    {
        const FVector3d P = Mesh.GetVertex(V), Q = Original[V];
        Rows.Add(Row({double(V), Q.X, Q.Y, Q.Z, P.X, P.Y, P.Z,
            (!Source.IsVertex(V) || EdgeVertices.Contains(V)) ? 1.0 : 0.0}));
    }
    for (int32 T : Mesh.TriangleIndicesItr()) { const auto F = Mesh.GetTriangle(T); Faces.Add(Row({double(F.A), double(F.B), double(F.C)})); }
    for (int32 V : Source.VertexIndicesItr()) { const FVector3d P = Source.GetVertex(V); SourceRows.Add(Row({double(V), P.X, P.Y, P.Z})); }
    for (int32 T : Source.TriangleIndicesItr()) { const auto F = Source.GetTriangle(T); SourceFaces.Add(Row({double(F.A), double(F.B), double(F.C)})); }
    for (int32 E : Edges) { const auto V = Source.GetEdgeV(E); SelectedEdges.Add(Row({double(V.A), double(V.B)})); }
    Report->SetArrayField(TEXT("audit_vertices_cm"), Rows); Report->SetArrayField(TEXT("audit_triangles"), Faces);
    Report->SetArrayField(TEXT("edge_source_vertices_cm"), SourceRows); Report->SetArrayField(TEXT("edge_source_triangles"), SourceFaces);
    Report->SetArrayField(TEXT("rounded_source_edges"), SelectedEdges);
    Report->SetStringField(TEXT("shape_profile"), TEXT("limestone-edge-band-only-v7"));
    Report->SetStringField(TEXT("refinement"), TEXT("source-exact local endpoint splits and guarded Epic FMeshBevel profile"));
    Report->SetNumberField(TEXT("displacement_limit_cm"), 20); Report->SetNumberField(TEXT("max_displacement_cm"), MaxShift);
    Report->SetNumberField(TEXT("edge_band_radius_cm"), 10); Report->SetNumberField(TEXT("max_edge_band_distance_cm"), MaxBand);
    Report->SetNumberField(TEXT("bevel_inset_cm"), ChosenInset); Report->SetNumberField(TEXT("bevel_subdivisions"), ChosenSubdivisions);
    Report->SetNumberField(TEXT("bevel_round_weight"), 0.5);
    Report->SetNumberField(TEXT("bevel_profile_blend"), ChosenProfileAlpha);
    Report->SetNumberField(TEXT("max_round_profile_displacement_cm"), MaxProfileShift);
    Report->SetBoolField(TEXT("bevel_linear_base_valid"), true);
    Report->SetNumberField(TEXT("folded_xy_triangles"), 0);
    Report->SetNumberField(TEXT("sharp_edge_angle_deg"), 45); Report->SetNumberField(TEXT("rounded_edge_count"), Edges.Num());
    Report->SetNumberField(TEXT("smoothing_passes"), 0); Report->SetNumberField(TEXT("tangential_redistribution_passes"), 0);
    Report->SetNumberField(TEXT("locked_normal_max_delta"), 0); Report->SetNumberField(TEXT("preserved_normal_elements"), PreservedNormals);
    Report->SetBoolField(TEXT("terrain_erosion"), false); Report->SetBoolField(TEXT("surface_relaxation"), false);
    Report->SetBoolField(TEXT("outside_edge_vertices_unchanged"), true);
    return true;
}

// This operates on an owned export, never on Landscape or PCG output data.
bool SmoothLocalCliffs(UE::Geometry::FDynamicMesh3& Mesh, const FString& PlanJson,
    const TSharedRef<FJsonObject>& Report, FString& Error)
{
    TSharedPtr<FJsonObject> Plan;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(PlanJson);
    if (!FJsonSerializer::Deserialize(Reader, Plan) || !Plan.IsValid())
    {
        Error = TEXT("invalid local smoothing plan");
        return false;
    }
    const bool bRounded = Plan->HasField(TEXT("limestone_rounded_flow")) &&
        Plan->GetBoolField(TEXT("limestone_rounded_flow"));
    const TArray<TSharedPtr<FJsonValue>>* Cells = nullptr;
    if (!Plan->TryGetArrayField(TEXT("skin_cells"), Cells) || Cells->Num() != 1017)
    {
        Error = TEXT("expected 1017 authoritative cells");
        return false;
    }
    TSet<FIntPoint> AllowedQuads;
    for (const TSharedPtr<FJsonValue>& Value : *Cells)
    {
        const TSharedPtr<FJsonObject>* Cell = nullptr;
        double R0, R1, C0, C1, Protected;
        if (!Value->TryGetObject(Cell) ||
            !(*Cell)->TryGetNumberField(TEXT("row0"), R0) ||
            !(*Cell)->TryGetNumberField(TEXT("row1"), R1) ||
            !(*Cell)->TryGetNumberField(TEXT("col0"), C0) ||
            !(*Cell)->TryGetNumberField(TEXT("col1"), C1) ||
            !(*Cell)->TryGetNumberField(TEXT("protected_samples"), Protected) ||
            Protected != 0 || R1 - R0 != 2 || C1 - C0 != 2 ||
            R0 < 882 || R1 > 1008 || C0 < 756 || C1 > 882 ||
            R0 != FMath::FloorToDouble(R0) || C0 != FMath::FloorToDouble(C0))
        {
            Error = TEXT("invalid or protected smoothing cell");
            return false;
        }
        for (int32 R = int32(R0); R < int32(R1); ++R)
        {
            for (int32 C = int32(C0); C < int32(C1); ++C)
            {
                AllowedQuads.Add(FIntPoint(C, R));
            }
        }
    }
    if (AllowedQuads.Num() != 4068)
    {
        Error = TEXT("smoothing cell overlap or area drift");
        return false;
    }

    // Refinement and original PCGEx footprint stay at the admitted 1017 cells.
    // Rounding movement additionally covers source-backed crowns, preserving
    // every road/shoulder/water sample and the new domain's fixed interfaces.
    const TSet<FIntPoint> RefinementQuads(AllowedQuads);
    if (bRounded)
    {
        const TArray<TSharedPtr<FJsonValue>>* RoundingCells = nullptr;
        if (!Plan->TryGetArrayField(TEXT("rounding_cells"), RoundingCells) || RoundingCells->Num() < 1017)
        {
            Error = TEXT("rounded crown domain is missing");
            return false;
        }
        AllowedQuads.Reset();
        for (const TSharedPtr<FJsonValue>& Value : *RoundingCells)
        {
            const TSharedPtr<FJsonObject>* Cell = nullptr;
            double R0, R1, C0, C1, Protected;
            if (!Value->TryGetObject(Cell) ||
                !(*Cell)->TryGetNumberField(TEXT("row0"), R0) || !(*Cell)->TryGetNumberField(TEXT("row1"), R1) ||
                !(*Cell)->TryGetNumberField(TEXT("col0"), C0) || !(*Cell)->TryGetNumberField(TEXT("col1"), C1) ||
                !(*Cell)->TryGetNumberField(TEXT("protected_samples"), Protected) ||
                Protected != 0 || R1 - R0 != 2 || C1 - C0 != 2 ||
                R0 < 882 || R1 > 1008 || C0 < 756 || C1 > 882 ||
                R0 != FMath::FloorToDouble(R0) || C0 != FMath::FloorToDouble(C0))
            {
                Error = TEXT("invalid or protected rounded crown cell");
                return false;
            }
            for (int32 R = int32(R0); R < int32(R1); ++R)
            {
                for (int32 C = int32(C0); C < int32(C1); ++C)
                {
                    const FIntPoint Tile(C, R);
                    if (AllowedQuads.Contains(Tile))
                    {
                        Error = TEXT("rounded crown domain overlaps");
                        return false;
                    }
                    AllowedQuads.Add(Tile);
                }
            }
        }
        for (const FIntPoint& Tile : RefinementQuads)
        {
            if (!AllowedQuads.Contains(Tile))
            {
                Error = TEXT("rounded domain lost original cliff footprint");
                return false;
            }
        }
    }

    if (Plan->HasField(TEXT("limestone_edge_only")) && Plan->GetBoolField(TEXT("limestone_edge_only")))
    { return RoundLimestoneEdges(Mesh, AllowedQuads, Report, Error); }

    // Use Epic's conforming selective tessellator, not global subdivision.
    // The linear refinement preserves source geometry before normal relaxation.
    TArray<int32> Levels;
    Levels.Init(0, Mesh.MaxTriangleID());
    int32 SourceCliffTriangles = 0;
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto F = Mesh.GetTriangle(T);
        const FVector3d Center = (Mesh.GetVertex(F.A) + Mesh.GetVertex(F.B) + Mesh.GetVertex(F.C)) / 3.0;
        if (RefinementQuads.Contains(FIntPoint(FMath::FloorToInt(Center.X / 50.0), FMath::FloorToInt(Center.Y / 50.0))))
        {
            Levels[T] = 1;
            ++SourceCliffTriangles;
        }
    }
    if (SourceCliffTriangles != 8136)
    {
        Error = TEXT("native cliff source triangle count drift");
        return false;
    }
    const UE::Geometry::FDynamicMesh3 NativeSource(Mesh);
    auto Pattern = UE::Geometry::FSelectiveTessellate::CreateRedGreenTessellationPattern(&NativeSource, Levels);
    if (!Pattern)
    {
        Error = TEXT("native selective tessellation pattern unavailable");
        return false;
    }
    UE::Geometry::FSelectiveTessellate Tessellate(&NativeSource, &Mesh);
    Tessellate.SetPattern(Pattern.Get());
    Tessellate.bUseParallel = false;
    if (!Tessellate.Compute() || Mesh.TriangleCount() > 60000)
    {
        Error = TEXT("selective tessellation failed or exceeded unchanged 60000 triangle limit");
        return false;
    }
    // Independently verify all new source vertices still lie on the original
    // exported triangular surface, including transition triangles outside cliffs.
    TMap<FIntPoint, TArray<int32>> NativeTiles;
    for (int32 T : NativeSource.TriangleIndicesItr())
    {
        const auto F = NativeSource.GetTriangle(T);
        const FVector3d Center = (NativeSource.GetVertex(F.A) + NativeSource.GetVertex(F.B) + NativeSource.GetVertex(F.C)) / 3.0;
        NativeTiles.FindOrAdd(FIntPoint(FMath::FloorToInt(Center.X / 50.0), FMath::FloorToInt(Center.Y / 50.0))).Add(T);
    }
    double RefinementError = 0;
    for (int32 V : Mesh.VertexIndicesItr())
    {
        const FVector3d P = Mesh.GetVertex(V);
        const FIntPoint Tile(FMath::FloorToInt(P.X / 50.0), FMath::FloorToInt(P.Y / 50.0));
        bool Found = false;
        for (int32 DX = -1; DX <= 0; ++DX)
        {
            for (int32 DY = -1; DY <= 0; ++DY)
            {
                const TArray<int32>* Faces = NativeTiles.Find(Tile + FIntPoint(DX, DY));
                if (!Faces) { continue; }
                for (int32 T : *Faces)
                {
                    const auto F = NativeSource.GetTriangle(T);
                    const FVector3d A = NativeSource.GetVertex(F.A);
                    const FVector3d B = NativeSource.GetVertex(F.B);
                    const FVector3d C = NativeSource.GetVertex(F.C);
                    const double Denom = FVector3d::CrossProduct(B - A, C - A).Z;
                    const double U = FVector3d::CrossProduct(P - A, C - A).Z / Denom;
                    const double W = FVector3d::CrossProduct(B - A, P - A).Z / Denom;
                    if (U >= -1.e-8 && W >= -1.e-8 && U + W <= 1.0 + 1.e-8)
                    {
                        RefinementError = FMath::Max(RefinementError, FMath::Abs(P.Z - (A.Z + U * (B.Z - A.Z) + W * (C.Z - A.Z))));
                        Found = true;
                    }
                }
            }
        }
        if (!Found)
        {
            Error = TEXT("refined source vertex escaped native triangle domain");
            return false;
        }
    }
    if (RefinementError > 0.001)
    {
        Error = TEXT("linear refinement altered native source geometry");
        return false;
    }
    Report->SetNumberField(TEXT("native_source_triangles"), NativeSource.TriangleCount());
    Report->SetNumberField(TEXT("refined_triangles"), Mesh.TriangleCount());
    Report->SetNumberField(TEXT("linear_refinement_error_cm"), RefinementError);
    Report->SetStringField(TEXT("refinement"), TEXT("Epic FSelectiveTessellate red-green level 1 on cliff triangles only"));

    TArray<FVector3d> Original;
    Original.SetNum(Mesh.MaxVertexID());
    TArray<bool> Movable;
    Movable.Init(true, Mesh.MaxVertexID());
    for (int32 V : Mesh.VertexIndicesItr())
    {
        Original[V] = Mesh.GetVertex(V);
        // Native half-metre grid is required; no inferred resampling.
        if (FMath::Abs(Original[V].X / 25.0 - FMath::RoundToDouble(Original[V].X / 25.0)) > 1.e-6 ||
            FMath::Abs(Original[V].Y / 25.0 - FMath::RoundToDouble(Original[V].Y / 25.0)) > 1.e-6)
        {
            Error = TEXT("refined native export differs from 25 cm subdivision grid");
            return false;
        }
        Movable[V] = !Mesh.IsBoundaryVertex(V);
    }
    int32 AllowedTriangles = 0;
    double AllowedSourceAreaCm2 = 0.0;
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto Face = Mesh.GetTriangle(T);
        const FVector3d Center = (Original[Face.A] + Original[Face.B] + Original[Face.C]) / 3.0;
        const bool Allowed = AllowedQuads.Contains(FIntPoint(
            FMath::FloorToInt(Center.X / 50.0), FMath::FloorToInt(Center.Y / 50.0)));
        if (Allowed)
        {
            ++AllowedTriangles;
            AllowedSourceAreaCm2 += 0.5 * FMath::Abs(FVector3d::CrossProduct(
                Original[Face.B] - Original[Face.A], Original[Face.C] - Original[Face.A]).Z);
        }
        else
        {
            // Lock every interface vertex, including holes and narrow corridors.
            Movable[Face.A] = Movable[Face.B] = Movable[Face.C] = false;
        }
    }
    if ((!bRounded && AllowedTriangles != 32544) ||
        FMath::Abs(AllowedSourceAreaCm2 - AllowedQuads.Num() * 2500.0) > 1.e-3)
    {
        Error = TEXT("native movement surface does not cover its exact authoritative domain");
        return false;
    }

    // Owner correction: round upper surfaces and walls alike. The historical
    // standalone control is retained; the candidate no longer protects creases.
    const int32 Passes = bRounded ? 96 : 84;
    constexpr double Blend = 0.10;
    const int32 TangentialPasses = bRounded ? 0 : 3;
    constexpr double TangentialBlend = 0.20;
    const bool bPostErosion = Plan->HasField(TEXT("post_erosion_mesh")) && Plan->GetBoolField(TEXT("post_erosion_mesh"));
    const double MaxDisplacementCm = bPostErosion ? 50.0 : 100.0;
    int32 Backtracks = 0;
    int32 CompletedPasses = 0;
    int32 CompletedTangentialPasses = 0;
    int32 VerticalFallbackUpdates = 0;
    bool StoppedAtConstraint = false;
    for (int32 Pass = 0; Pass < Passes + TangentialPasses; ++Pass)
    {
        const bool bTangential = Pass >= Passes;
        TArray<FVector3d> Before, Target, Normals;
        TArray<double> VerticalDelta;
        VerticalDelta.Init(0.0, Mesh.MaxVertexID());
        Before.SetNum(Mesh.MaxVertexID());
        Target.SetNum(Mesh.MaxVertexID());
        Normals.Init(FVector3d::Zero(), Mesh.MaxVertexID());
        for (int32 V : Mesh.VertexIndicesItr())
        {
            Before[V] = Target[V] = Mesh.GetVertex(V);
        }
        for (int32 T : Mesh.TriangleIndicesItr())
        {
            const auto F = Mesh.GetTriangle(T);
            const FVector3d N = FVector3d::CrossProduct(Before[F.B] - Before[F.A], Before[F.C] - Before[F.A]);
            Normals[F.A] += N;
            Normals[F.B] += N;
            Normals[F.C] += N;
        }
        for (int32 V : Mesh.VertexIndicesItr())
        {
            if (!Movable[V]) { continue; }
            FVector3d Mean = FVector3d::Zero();
            double WeightSum = 0;
            for (int32 Neighbor : Mesh.VtxVerticesItr(V))
            {
                constexpr double Weight = 1.0;
                Mean += Before[Neighbor] * Weight;
                WeightSum += Weight;
            }
            if (WeightSum < 1.e-9 || !Normals[V].Normalize()) { continue; }
            // Normal-space relaxation: horizontal on walls, vertical on flats.
            const FVector3d N = Normals[V];
            const FVector3d Laplacian = Mean / WeightSum - Before[V];
            const double NormalResidual = FVector3d::DotProduct(Laplacian, N);
            const double NormalDelta = Blend * NormalResidual;
            Target[V] = Before[V] + (bTangential
                ? TangentialBlend * (Laplacian - N * NormalResidual)
                : N * NormalDelta);
            // If XY motion is constrained, solve the same tangent-plane residual
            // vertically. This preserves XY authority instead of freezing ridges.
            if (!bTangential && FMath::Abs(N.Z) > 1.e-6)
            {
                VerticalDelta[V] = NormalDelta / N.Z;
            }
            FVector3d Delta = Target[V] - Original[V];
            const double Length = Delta.Length();
            if (Length > MaxDisplacementCm)
            {
                Target[V] = Original[V] + Delta * (MaxDisplacementCm / Length);
            }
        }
        bool Accepted = false;
        TArray<double> Weights;
        Weights.Init(1.0, Mesh.MaxVertexID());
        for (int32 Attempt = 0; Attempt < 32; ++Attempt)
        {
            TSet<int32> Restricted;
            for (int32 T : Mesh.TriangleIndicesItr())
            {
                const auto F = Mesh.GetTriangle(T);
                const FVector3d A = Before[F.A] + (Target[F.A] - Before[F.A]) * Weights[F.A];
                const FVector3d B = Before[F.B] + (Target[F.B] - Before[F.B]) * Weights[F.B];
                const FVector3d C = Before[F.C] + (Target[F.C] - Before[F.C]) * Weights[F.C];
                const double OldXY = FVector3d::CrossProduct(
                    Original[F.B] - Original[F.A], Original[F.C] - Original[F.A]).Z;
                const double NewXY = FVector3d::CrossProduct(B - A, C - A).Z;
                // Fixed domain boundary + consistent positive Jacobians preserves
                // the planar footprint; reject folds instead of hiding them.
                if (!FMath::IsFinite(NewXY) || NewXY * OldXY <= 0 ||
                    FMath::Abs(NewXY) < FMath::Abs(OldXY) * 0.10)
                {
                    Restricted.Add(F.A);
                    Restricted.Add(F.B);
                    Restricted.Add(F.C);
                }
            }
            if (Restricted.Num() == 0)
            {
                for (int32 V : Mesh.VertexIndicesItr())
                {
                    FVector3d Position = Before[V] + (Target[V] - Before[V]) * Weights[V];
                    if (Movable[V] && Weights[V] < 1.0 && FMath::Abs(VerticalDelta[V]) > 1.e-9)
                    {
                        Position.Z += VerticalDelta[V] * (1.0 - Weights[V]);
                        const FVector3d Delta = Position - Original[V];
                        const double ZBudget = FMath::Sqrt(FMath::Max(0.0,
                            MaxDisplacementCm * MaxDisplacementCm - Delta.X * Delta.X - Delta.Y * Delta.Y));
                        Position.Z = FMath::Clamp(Position.Z, Original[V].Z - ZBudget, Original[V].Z + ZBudget);
                        ++VerticalFallbackUpdates;
                    }
                    Mesh.SetVertex(V, Position);
                }
                Backtracks += Attempt;
                Accepted = true;
                break;
            }
            for (int32 V : Restricted)
            {
                Weights[V] = Attempt >= 20 ? 0.0 : Weights[V] * 0.5;
            }
        }
        if (!Accepted)
        {
            // A constrained optimum is a valid stopping point. Never commit an
            // invalid proposal merely to complete the requested pass count.
            StoppedAtConstraint = true;
            break;
        }
        if (bTangential) { ++CompletedTangentialPasses; }
        else { ++CompletedPasses; }
    }
    double MaxShift = 0, MaxXY = 0, MaxZ = 0;
    int32 Changed = 0;
    for (int32 V : Mesh.VertexIndicesItr())
    {
        const FVector3d Delta = Mesh.GetVertex(V) - Original[V];
        if (Delta.ContainsNaN() || (!Movable[V] && Delta.Length() > 1.e-9) ||
            Delta.Length() > MaxDisplacementCm + 1.e-6)
        {
            Error = TEXT("smoothing escaped fixed boundary or displacement bound");
            return false;
        }
        if (Delta.Length() > 1.e-6) { ++Changed; }
        MaxShift = FMath::Max(MaxShift, Delta.Length());
        MaxXY = FMath::Max(MaxXY, FMath::Sqrt(Delta.X * Delta.X + Delta.Y * Delta.Y));
        MaxZ = FMath::Max(MaxZ, FMath::Abs(Delta.Z));
    }
    if (!Mesh.HasAttributes() || !Mesh.Attributes()->PrimaryNormals())
    {
        Error = TEXT("native normal overlay missing");
        return false;
    }
    auto* NormalOverlay = Mesh.Attributes()->PrimaryNormals();
    TArray<int32> EditedNormalElements;
    TMap<int32, FVector3f> FixedNormals;
    for (int32 Element : NormalOverlay->ElementIndicesItr())
    {
        const int32 Vertex = NormalOverlay->GetParentVertex(Element);
        if (!Movable.IsValidIndex(Vertex))
        {
            Error = TEXT("normal overlay has invalid parent vertex");
            return false;
        }
        if (Movable[Vertex])
        {
            EditedNormalElements.Add(Element);
        }
        else
        {
            FVector3f Normal;
            NormalOverlay->GetElement(Element, Normal);
            FixedNormals.Add(Element, Normal);
        }
    }
    if (Changed == 0 || !UE::Geometry::FMeshNormals::RecomputeOverlayElementNormals(
        Mesh, EditedNormalElements, true, true))
    {
        Error = TEXT("empty smoothing result or normal recomputation failure");
        return false;
    }
    for (const auto& Pair : FixedNormals)
    {
        FVector3f Actual;
        NormalOverlay->GetElement(Pair.Key, Actual);
        if (Actual != Pair.Value)
        {
            Error = TEXT("normal recomputation changed a fixed vertex");
            return false;
        }
    }
    Report->SetNumberField(TEXT("preserved_normal_elements"), FixedNormals.Num());
    Report->SetNumberField(TEXT("recomputed_normal_elements"), EditedNormalElements.Num());
    Report->SetNumberField(TEXT("locked_normal_max_delta"), 0);
    Report->SetStringField(TEXT("normal_policy"), TEXT("native normals preserved outside movable cliff vertices"));
    Report->SetBoolField(TEXT("local_smoothing"), true);
    Report->SetStringField(TEXT("shape_profile"), bRounded
        ? TEXT("rounded-limestone-crown-domain-v4") : TEXT("legacy-normal-flow-v1"));
    Report->SetBoolField(TEXT("crease_preservation"), false);
    Report->SetNumberField(TEXT("source_feature_cosine"), -1.0);
    Report->SetNumberField(TEXT("source_skin_cells"), 1017);
    Report->SetNumberField(TEXT("movement_domain_cells"), AllowedQuads.Num() / 4);
    Report->SetNumberField(TEXT("movement_domain_area_m2"), AllowedSourceAreaCm2 / 10000.0);
    Report->SetNumberField(TEXT("allowed_native_triangles"), AllowedTriangles);
    Report->SetNumberField(TEXT("changed_vertices"), Changed);
    Report->SetNumberField(TEXT("max_displacement_cm"), MaxShift);
    Report->SetNumberField(TEXT("displacement_limit_cm"), MaxDisplacementCm);
    Report->SetNumberField(TEXT("max_xy_displacement_cm"), MaxXY);
    Report->SetNumberField(TEXT("max_z_displacement_cm"), MaxZ);
    Report->SetNumberField(TEXT("locked_vertex_displacement_cm"), 0);
    Report->SetNumberField(TEXT("folded_xy_triangles"), 0);
    Report->SetNumberField(TEXT("smoothing_passes"), CompletedPasses);
    Report->SetNumberField(TEXT("tangential_redistribution_passes"), CompletedTangentialPasses);
    Report->SetNumberField(TEXT("tangential_redistribution_blend"), TangentialBlend);
    Report->SetNumberField(TEXT("vertical_fallback_updates"), VerticalFallbackUpdates);
    Report->SetBoolField(TEXT("stopped_at_constraint"), StoppedAtConstraint);
    Report->SetNumberField(TEXT("line_search_backtracks"), Backtracks);
    Report->SetStringField(TEXT("smoothing_policy"), bRounded
        ? TEXT("rounded surfaces and walls, unweighted bounded normal flow, no crease preservation or tangential redistribution, fixed protected interfaces")
        : TEXT("bounded normal-space relaxation with vertical fallback, three tangential redistribution passes and fixed footprint interfaces"));
    TArray<TSharedPtr<FJsonValue>> AuditVertices, AuditTriangles;
    for (int32 V : Mesh.VertexIndicesItr())
    {
        const FVector3d P = Mesh.GetVertex(V);
        TArray<TSharedPtr<FJsonValue>> Row;
        for (double Number : {double(V), Original[V].X, Original[V].Y, Original[V].Z, P.X, P.Y, P.Z, Movable[V] ? 1.0 : 0.0})
        {
            Row.Add(MakeShared<FJsonValueNumber>(Number));
        }
        AuditVertices.Add(MakeShared<FJsonValueArray>(Row));
    }
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto F = Mesh.GetTriangle(T);
        TArray<TSharedPtr<FJsonValue>> Row;
        Row.Add(MakeShared<FJsonValueNumber>(F.A));
        Row.Add(MakeShared<FJsonValueNumber>(F.B));
        Row.Add(MakeShared<FJsonValueNumber>(F.C));
        AuditTriangles.Add(MakeShared<FJsonValueArray>(Row));
    }
    Report->SetArrayField(TEXT("audit_vertices_cm"), AuditVertices);
    Report->SetArrayField(TEXT("audit_triangles"), AuditTriangles);
    return true;
}
}

FString UYacsLandscapeMeshDiagnosticLibrary::CopyComponent230(
    ULandscapeComponent* Component, UDynamicMesh* TargetMesh, const FString& SmoothingPlanJson)
{
    if (!IsValid(Component) || !IsValid(TargetMesh) ||
        (Component->GetName() != TEXT("LandscapeComponent_230") &&
         !Component->GetOwner()->ActorHasTag(TEXT("YACS_Component230_TerrainTrial"))))
    {
        return TEXT("{\"error\":\"expected Component 230 and transient target mesh\"}");
    }
    ALandscapeProxy* Proxy = Component->GetLandscapeProxy();
    if (!Proxy || Proxy->HasNaniteComponents())
    {
        return TEXT("{\"error\":\"missing proxy or active Nanite representation requires separate visibility handling\"}");
    }
    TArray<ULandscapeComponent*> SelectedComponents;
    SelectedComponents.Add(Component);
    ALandscapeProxy::FRawMeshExportParams Params;
    Params.ComponentsToExport = MakeArrayView(SelectedComponents);
    Params.ExportLOD = 0;
    Params.ExportCoordinatesType =
        ALandscapeProxy::FRawMeshExportParams::EExportCoordinatesType::Absolute;
    Params.SkirtDepth.Reset();
    FMeshDescription Description;
    FStaticMeshAttributes Attributes(Description);
    Attributes.Register();
    if (!Proxy->ExportToRawMesh(Params, Description) || Description.Triangles().Num() == 0)
    {
        return TEXT("{\"error\":\"native Landscape export failed\"}");
    }

    UE::Geometry::FDynamicMesh3 Converted;
    FMeshDescriptionToDynamicMesh Converter;
    Converter.bCalculateMaps = true;
    Converter.bDisableAttributes = false;
    Converter.Convert(&Description, Converted, true);
    const int32 ExpectedTriangles = 2 * Component->ComponentSizeQuads * Component->ComponentSizeQuads;
    if (Description.Triangles().Num() != ExpectedTriangles ||
        Converted.TriangleCount() != ExpectedTriangles || ExpectedTriangles > 60000)
    {
        return TEXT("{\"error\":\"LOD0 triangle identity or bounded diagnostic budget failed\"}");
    }
    const auto Positions = Attributes.GetVertexPositions();
    double MaxConversionErrorCm = 0;
    for (const int32 VertexId : Converted.VertexIndicesItr())
    {
        if (!Converter.VertIDMap.IsValidIndex(VertexId))
        {
            return TEXT("{\"error\":\"missing native vertex correspondence\"}");
        }
        const FVector3d Source(Positions[Converter.VertIDMap[VertexId]]);
        const FVector3d Actual = Converted.GetVertex(VertexId);
        if (Source.ContainsNaN() || Actual.ContainsNaN())
        {
            return TEXT("{\"error\":\"nonfinite native geometry\"}");
        }
        MaxConversionErrorCm = FMath::Max(MaxConversionErrorCm, (Actual - Source).Length());
    }
    if (MaxConversionErrorCm > 0.001)
    {
        return TEXT("{\"error\":\"native vertex positions changed during conversion\"}");
    }
    const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    if (!SmoothingPlanJson.IsEmpty())
    {
        FString Error;
        if (!SmoothLocalCliffs(Converted, SmoothingPlanJson, Report, Error))
        {
            Report->SetStringField(TEXT("error"), Error);
            FString Failure;
            const TSharedRef<TJsonWriter<>> FailureWriter = TJsonWriterFactory<>::Create(&Failure);
            FJsonSerializer::Serialize(Report, FailureWriter);
            return Failure;
        }
    }
    Report->SetStringField(TEXT("status"), TEXT("NATIVE_LANDSCAPE_COMPONENT_MESH"));
    Report->SetStringField(TEXT("component"), Component->GetPathName());
    Report->SetStringField(TEXT("source"), TEXT("ALandscapeProxy::ExportToRawMesh"));
    Report->SetNumberField(TEXT("lod"), 0);
    Report->SetNumberField(TEXT("vertices"), Converted.VertexCount());
    Report->SetNumberField(TEXT("triangles"), Converted.TriangleCount());
    Report->SetNumberField(TEXT("max_conversion_error_cm"), MaxConversionErrorCm);
    Report->SetBoolField(TEXT("native_attributes_copied"), true);
    Report->SetBoolField(TEXT("skirt_added"), false);
    Report->SetBoolField(TEXT("assets_saved"), false);
    Report->SetBoolField(TEXT("landscape_geometry_mutated"), false);
    TargetMesh->SetMesh(MoveTemp(Converted));
    FString Result;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result);
    FJsonSerializer::Serialize(Report, Writer);
    return Result;
}
