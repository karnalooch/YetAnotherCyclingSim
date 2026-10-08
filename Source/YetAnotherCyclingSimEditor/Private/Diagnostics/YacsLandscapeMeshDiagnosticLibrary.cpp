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

    // Use Epic's conforming selective tessellator, not global subdivision.
    // The linear refinement preserves source geometry before normal relaxation.
    TArray<int32> Levels;
    Levels.Init(0, Mesh.MaxTriangleID());
    int32 SourceCliffTriangles = 0;
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto F = Mesh.GetTriangle(T);
        const FVector3d Center = (Mesh.GetVertex(F.A) + Mesh.GetVertex(F.B) + Mesh.GetVertex(F.C)) / 3.0;
        if (AllowedQuads.Contains(FIntPoint(FMath::FloorToInt(Center.X / 50.0), FMath::FloorToInt(Center.Y / 50.0))))
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
    if (AllowedTriangles != 32544)
    {
        Error = TEXT("native cliff footprint does not cover exactly 1017 square metres");
        return false;
    }

    // Retain the historical control; the limestone proposal uses less flow.
    const bool bLimestone = Plan->HasField(TEXT("limestone_feature_flow")) &&
        Plan->GetBoolField(TEXT("limestone_feature_flow"));
    const int32 Passes = bLimestone ? 24 : 84;
    constexpr double Blend = 0.10;
    // Normal-only flow can crowd vertices into thin triangles. A short
    // tangential redistribution improves sampling without extending the domain.
    const int32 TangentialPasses = bLimestone ? 0 : 3;
    constexpr double TangentialBlend = 0.20;
    // Owner-approved presentation envelope; canonical source stays unchanged.
    const bool bPostErosion = Plan->HasField(TEXT("post_erosion_mesh")) && Plan->GetBoolField(TEXT("post_erosion_mesh"));
    const double MaxDisplacementCm = bPostErosion ? 50.0 : 100.0;
    // Freeze the source orientation guide: evolving normals must not gradually
    // erase a crease and then admit diffusion across it. No noise or invented
    // strata are added. This preserves existing angular source structure.
    TArray<FVector3d> GuideNormals;
    GuideNormals.Init(FVector3d::Zero(), Mesh.MaxVertexID());
    for (int32 T : Mesh.TriangleIndicesItr())
    {
        const auto F = Mesh.GetTriangle(T);
        const FVector3d N = FVector3d::CrossProduct(
            Original[F.B] - Original[F.A], Original[F.C] - Original[F.A]);
        GuideNormals[F.A] += N;
        GuideNormals[F.B] += N;
        GuideNormals[F.C] += N;
    }
    for (int32 V : Mesh.VertexIndicesItr()) { GuideNormals[V].Normalize(); }
    constexpr double FeatureCosine = 0.85; // approximately 32 degrees
    // Blunt source-sampling teeth only on convex upper surfaces. A sharp wall
    // can be a limestone fracture; do not relax it merely for being angular.
    constexpr double CrestUpCosine = 0.70; // upper surfaces within about 45 degrees
    constexpr double CrestResidualCm = -1.0;
    constexpr double CrestBlend = 0.35;
    const int32 CrestPasses = bLimestone ? 12 : 0;
    TArray<bool> CrestEligible;
    CrestEligible.Init(false, Mesh.MaxVertexID());
    TArray<double> SourceConvexResidual;
    SourceConvexResidual.Init(0.0, Mesh.MaxVertexID());
    TArray<FVector3d> BeforeCrest;
    BeforeCrest.SetNum(Mesh.MaxVertexID());
    int32 CrestEligibleVertices = 0;
    for (int32 V : Mesh.VertexIndicesItr())
    {
        FVector3d Mean = FVector3d::Zero();
        int32 Neighbors = 0;
        for (int32 Neighbor : Mesh.VtxVerticesItr(V))
        {
            Mean += Original[Neighbor];
            ++Neighbors;
        }
        if (Neighbors == 0) { continue; }
        SourceConvexResidual[V] = FVector3d::DotProduct(Mean / Neighbors - Original[V], GuideNormals[V]);
        CrestEligible[V] = bLimestone && Movable[V] &&
            GuideNormals[V].Z >= CrestUpCosine && SourceConvexResidual[V] < CrestResidualCm;
        if (CrestEligible[V]) { ++CrestEligibleVertices; }
    }
    int32 Backtracks = 0;
    int32 CompletedPasses = 0;
    int32 CompletedTangentialPasses = 0;
    int32 VerticalFallbackUpdates = 0;
    int32 CompletedCrestPasses = 0;
    bool StoppedAtConstraint = false;
    for (int32 Pass = 0; Pass < Passes + CrestPasses + TangentialPasses; ++Pass)
    {
        const bool bCrest = Pass >= Passes && Pass < Passes + CrestPasses;
        const bool bTangential = Pass >= Passes + CrestPasses;
        TArray<FVector3d> Before, Target, Normals;
        TArray<double> VerticalDelta;
        VerticalDelta.Init(0.0, Mesh.MaxVertexID());
        Before.SetNum(Mesh.MaxVertexID());
        Target.SetNum(Mesh.MaxVertexID());
        Normals.Init(FVector3d::Zero(), Mesh.MaxVertexID());
        for (int32 V : Mesh.VertexIndicesItr())
        {
            Before[V] = Target[V] = Mesh.GetVertex(V);
            if (Pass == Passes) { BeforeCrest[V] = Before[V]; }
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
            if (bCrest && !CrestEligible[V]) { continue; }
            FVector3d Mean = FVector3d::Zero();
            double WeightSum = 0;
            for (int32 Neighbor : Mesh.VtxVerticesItr(V))
            {
                const double Alignment = FVector3d::DotProduct(GuideNormals[V], GuideNormals[Neighbor]);
                const double Weight = bLimestone && !bCrest
                    ? FMath::Square(FMath::Clamp((Alignment - FeatureCosine) / (1.0 - FeatureCosine), 0.0, 1.0))
                    : 1.0;
                Mean += Before[Neighbor] * Weight;
                WeightSum += Weight;
            }
            if (WeightSum < 1.e-9 || !Normals[V].Normalize()) { continue; }
            // Normal-space relaxation: horizontal on walls, vertical on flats.
            const FVector3d N = Normals[V];
            const FVector3d Laplacian = Mean / WeightSum - Before[V];
            const double NormalResidual = FVector3d::DotProduct(Laplacian, N);
            const double NormalDelta = Blend * NormalResidual;
            Target[V] = bCrest
                ? Before[V] + FVector3d(0.0, 0.0, CrestBlend * FMath::Min(0.0,
                    NormalResidual) / FMath::Max(CrestUpCosine, N.Z))
                : Before[V] + (bTangential
                ? TangentialBlend * (Laplacian - N * NormalResidual)
                : N * NormalDelta);
            // If XY motion is constrained, solve the same tangent-plane residual
            // vertically. This preserves XY authority instead of freezing ridges.
            if (!bTangential && !bCrest && FMath::Abs(N.Z) > 1.e-6)
            {
                VerticalDelta[V] = NormalDelta / N.Z;
            }
            FVector3d Delta = Target[V] - Original[V];
            const double Length = Delta.Length();
            if (Length > MaxDisplacementCm)
            {
                if (bCrest)
                {
                    const double ZBudget = FMath::Sqrt(FMath::Max(0.0,
                        MaxDisplacementCm * MaxDisplacementCm - Delta.X * Delta.X - Delta.Y * Delta.Y));
                    Target[V].Z = FMath::Clamp(Target[V].Z, Original[V].Z - ZBudget, Original[V].Z + ZBudget);
                }
                else
                {
                    Target[V] = Original[V] + Delta * (MaxDisplacementCm / Length);
                }
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
        else if (bCrest) { ++CompletedCrestPasses; }
        else { ++CompletedPasses; }
    }
    TArray<TSharedPtr<FJsonValue>> CrestVertices;
    int32 CrestChangedVertices = 0;
    if (bLimestone)
    {
        if (CompletedCrestPasses != CrestPasses)
        {
            Error = TEXT("convex upper-surface crest trial did not complete");
            return false;
        }
        for (int32 V : Mesh.VertexIndicesItr())
        {
            const FVector3d P = Mesh.GetVertex(V);
            const FVector3d Delta = P - BeforeCrest[V];
            if (FMath::Abs(Delta.X) > 1.e-9 || FMath::Abs(Delta.Y) > 1.e-9 ||
                Delta.Z > 1.e-9 || (!CrestEligible[V] && Delta.Length() > 1.e-9))
            {
                Error = TEXT("crest correction changed a wall, concavity, XY or raised a vertex");
                return false;
            }
            if (Delta.Z < -1.e-6) { ++CrestChangedVertices; }
            TArray<TSharedPtr<FJsonValue>> Row;
            for (double Number : {double(V), BeforeCrest[V].X, BeforeCrest[V].Y, BeforeCrest[V].Z,
                P.X, P.Y, P.Z, CrestEligible[V] ? 1.0 : 0.0, GuideNormals[V].Z, SourceConvexResidual[V]})
            {
                Row.Add(MakeShared<FJsonValueNumber>(Number));
            }
            CrestVertices.Add(MakeShared<FJsonValueArray>(Row));
        }
        Report->SetArrayField(TEXT("crest_audit_vertices"), CrestVertices);
    }
    Report->SetNumberField(TEXT("crest_passes"), CompletedCrestPasses);
    Report->SetNumberField(TEXT("crest_eligible_vertices"), CrestEligibleVertices);
    Report->SetNumberField(TEXT("crest_changed_vertices"), CrestChangedVertices);
    Report->SetNumberField(TEXT("crest_up_cosine"), CrestUpCosine);
    Report->SetNumberField(TEXT("crest_source_residual_cm"), CrestResidualCm);
    Report->SetStringField(TEXT("crest_policy"), TEXT("source-convex upper surfaces only, downward Z, unchanged XY and walls, shared mesh-stage envelope"));
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
    Report->SetStringField(TEXT("shape_profile"), bLimestone
        ? TEXT("limestone-source-feature-flow-v2-upper-crests") : TEXT("legacy-normal-flow-v1"));
    Report->SetNumberField(TEXT("source_feature_cosine"), bLimestone ? FeatureCosine : -1.0);
    Report->SetNumberField(TEXT("source_skin_cells"), 1017);
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
    Report->SetStringField(TEXT("smoothing_policy"), bLimestone
        ? TEXT("bounded source-feature normal flow plus convex upper-surface crest correction, fixed guide, unchanged walls in crest stage, no tangential redistribution")
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
