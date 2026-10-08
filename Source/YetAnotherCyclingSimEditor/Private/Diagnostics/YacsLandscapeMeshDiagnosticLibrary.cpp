#include "Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h"

#include "LandscapeComponent.h"
#include "LandscapeProxy.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "MeshDescriptionToDynamicMesh.h"
#include "UDynamicMesh.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/MeshNormals.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
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

    TArray<FVector3d> Original;
    Original.SetNum(Mesh.MaxVertexID());
    TArray<bool> Movable;
    Movable.Init(true, Mesh.MaxVertexID());
    for (int32 V : Mesh.VertexIndicesItr())
    {
        Original[V] = Mesh.GetVertex(V);
        // Native half-metre grid is required; no inferred resampling.
        if (FMath::Abs(Original[V].X / 50.0 - FMath::RoundToDouble(Original[V].X / 50.0)) > 1.e-6 ||
            FMath::Abs(Original[V].Y / 50.0 - FMath::RoundToDouble(Original[V].Y / 50.0)) > 1.e-6)
        {
            Error = TEXT("native export differs from authoritative 50 cm grid");
            return false;
        }
        Movable[V] = !Mesh.IsBoundaryVertex(V);
    }
    int32 AllowedTriangles = 0;
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto Face = Mesh.GetTriangle(T);
        const FVector3d Center = (Original[Face.A] + Original[Face.B] + Original[Face.C]) / 3.0;
        const bool Allowed = AllowedQuads.Contains(FIntPoint(
            FMath::FloorToInt(Center.X / 50.0), FMath::FloorToInt(Center.Y / 50.0)));
        if (Allowed)
        {
            ++AllowedTriangles;
        }
        else
        {
            // Lock every interface vertex, including holes and narrow corridors.
            Movable[Face.A] = Movable[Face.B] = Movable[Face.C] = false;
        }
    }
    if (AllowedTriangles != 8136)
    {
        Error = TEXT("native cliff footprint does not cover exactly 1017 square metres");
        return false;
    }

    constexpr int32 Passes = 24;
    constexpr double Blend = 0.35;
    constexpr double MaxDisplacementCm = 50.0;
    int32 Backtracks = 0;
    int32 CompletedPasses = 0;
    bool StoppedAtConstraint = false;
    for (int32 Pass = 0; Pass < Passes; ++Pass)
    {
        TArray<FVector3d> Before, Target, Normals;
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
            int32 Count = 0;
            for (int32 Neighbor : Mesh.VtxVerticesItr(V))
            {
                Mean += Before[Neighbor];
                ++Count;
            }
            if (Count == 0 || !Normals[V].Normalize()) { continue; }
            // Normal-space relaxation: horizontal on walls, vertical on flats.
            const FVector3d N = Normals[V];
            Target[V] = Before[V] + N * (Blend * FVector3d::DotProduct(Mean / Count - Before[V], N));
            FVector3d Delta = Target[V] - Original[V];
            const double Length = Delta.Length();
            if (Length > MaxDisplacementCm)
            {
                Target[V] = Original[V] + Delta * (MaxDisplacementCm / Length);
            }
        }
        bool Accepted = false;
        for (int32 Attempt = 0; Attempt < 12; ++Attempt)
        {
            const double Alpha = FMath::Pow(0.5, Attempt);
            bool Valid = true;
            for (int32 T : Mesh.TriangleIndicesItr())
            {
                const auto F = Mesh.GetTriangle(T);
                const FVector3d A = Before[F.A] + (Target[F.A] - Before[F.A]) * Alpha;
                const FVector3d B = Before[F.B] + (Target[F.B] - Before[F.B]) * Alpha;
                const FVector3d C = Before[F.C] + (Target[F.C] - Before[F.C]) * Alpha;
                const double OldXY = FVector3d::CrossProduct(
                    Original[F.B] - Original[F.A], Original[F.C] - Original[F.A]).Z;
                const double NewXY = FVector3d::CrossProduct(B - A, C - A).Z;
                // Fixed domain boundary + consistent positive Jacobians preserves
                // the planar footprint; reject folds instead of hiding them.
                if (!FMath::IsFinite(NewXY) || NewXY * OldXY <= 0 ||
                    FMath::Abs(NewXY) < FMath::Abs(OldXY) * 0.10)
                {
                    Valid = false;
                    break;
                }
            }
            if (Valid)
            {
                for (int32 V : Mesh.VertexIndicesItr())
                {
                    Mesh.SetVertex(V, Before[V] + (Target[V] - Before[V]) * Alpha);
                }
                Backtracks += Attempt;
                Accepted = true;
                break;
            }
        }
        if (!Accepted)
        {
            // A constrained optimum is a valid stopping point. Never commit an
            // invalid proposal merely to complete the requested pass count.
            StoppedAtConstraint = true;
            break;
        }
        ++CompletedPasses;
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
    if (Changed == 0 || !UE::Geometry::FMeshNormals::QuickRecomputeOverlayNormals(Mesh, false, true, true, false))
    {
        Error = TEXT("empty smoothing result or normal recomputation failure");
        return false;
    }
    Report->SetBoolField(TEXT("local_smoothing"), true);
    Report->SetNumberField(TEXT("source_skin_cells"), 1017);
    Report->SetNumberField(TEXT("allowed_native_triangles"), AllowedTriangles);
    Report->SetNumberField(TEXT("changed_vertices"), Changed);
    Report->SetNumberField(TEXT("max_displacement_cm"), MaxShift);
    Report->SetNumberField(TEXT("max_xy_displacement_cm"), MaxXY);
    Report->SetNumberField(TEXT("max_z_displacement_cm"), MaxZ);
    Report->SetNumberField(TEXT("locked_vertex_displacement_cm"), 0);
    Report->SetNumberField(TEXT("folded_xy_triangles"), 0);
    Report->SetNumberField(TEXT("smoothing_passes"), CompletedPasses);
    Report->SetBoolField(TEXT("stopped_at_constraint"), StoppedAtConstraint);
    Report->SetNumberField(TEXT("line_search_backtracks"), Backtracks);
    Report->SetStringField(TEXT("smoothing_policy"), TEXT("bounded normal-space relaxation with fixed footprint interfaces"));
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
        Component->GetName() != TEXT("LandscapeComponent_230"))
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

