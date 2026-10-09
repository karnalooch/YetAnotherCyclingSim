#include "Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h"

#include "Components/DynamicMeshComponent.h"
#include "Dom/JsonObject.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "DynamicMesh/DynamicMeshOverlay.h"
#include "DynamicMesh/DynamicMeshTriangleAttribute.h"
#include "DynamicMesh/MeshNormals.h"
#include "GameFramework/Actor.h"
#include "Materials/Material.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UDynamicMesh.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#endif

namespace
{
using namespace UE::Geometry;

constexpr TCHAR RetainedSourceSha[] = TEXT("a9d34dbfb32a59b592dca561a7d7b0e53f7d02d90c095cff7c0812c249247965");
constexpr double PositionToleranceCm = 0.000001;

struct FDetailSession
{
    TWeakObjectPtr<UDynamicMeshComponent> Component;
    FDynamicMesh3 Baseline;
    TArray<int32> RowToTriangle;
    TArray<int32> MaskSlots;
    TSet<int32> SelectedRows;
    TMap<int32, FVector3d> TrialPositions;
    TArray<int32> EditableNormals;
    int32 ProtectedFaceCount = 0;
    int32 ChangedVertexCount = 0;
    double MaxAdditionalCm = 0;
    double MaxTotalCm = 0;
    FString CurrentMode = TEXT("baseline");
};

// The proof admits one transient component and always restores it before the
// owning scene cleanup. A native snapshot retains split normals and UV seams
// that the earlier JSON geometry export intentionally does not serialize.
TUniquePtr<FDetailSession> DetailSession;

FString Json(const TSharedRef<FJsonObject>& Object)
{
    FString Result;
    FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Result));
    return Result;
}

FString Failure(const FString& Error)
{
    const auto Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("status"), TEXT("DETAIL_NATIVE_FAIL"));
    Result->SetStringField(TEXT("error"), Error);
    return Json(Result);
}

bool Parse(const FString& Text, TSharedPtr<FJsonObject>& Result)
{
    return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Result) && Result.IsValid();
}

bool Number(const TSharedPtr<FJsonValue>& Value, double& Result)
{
    return Value.IsValid() && Value->Type == EJson::Number && Value->TryGetNumber(Result) && FMath::IsFinite(Result);
}

bool Integer(const TSharedPtr<FJsonValue>& Value, int32& Result)
{
    double Numeric;
    if (!Number(Value, Numeric) || Numeric < 0 || Numeric > MAX_int32 || FMath::FloorToDouble(Numeric) != Numeric)
    {
        return false;
    }
    Result = static_cast<int32>(Numeric);
    return true;
}

bool ReadVertex(const TSharedPtr<FJsonValue>& Value, int32& Id,
    FVector3d& Source, FVector3d& Candidate, bool& Movable)
{
    const TArray<TSharedPtr<FJsonValue>>* Row = nullptr;
    if (!Value.IsValid() || !Value->TryGetArray(Row) || !Row || Row->Num() != 8 || !Integer((*Row)[0], Id))
    {
        return false;
    }
    double Values[7];
    for (int32 I = 0; I < 7; ++I)
    {
        if (!Number((*Row)[I + 1], Values[I])) { return false; }
    }
    if (Values[6] != 0 && Values[6] != 1) { return false; }
    Source = FVector3d(Values[0], Values[1], Values[2]);
    Candidate = FVector3d(Values[3], Values[4], Values[5]);
    Movable = Values[6] == 1;
    return true;
}

bool ReadFace(const TSharedPtr<FJsonValue>& Value, FIndex3i& Face)
{
    const TArray<TSharedPtr<FJsonValue>>* Row = nullptr;
    if (!Value.IsValid() || !Value->TryGetArray(Row) || !Row || Row->Num() != 3
        || !Integer((*Row)[0], Face.A) || !Integer((*Row)[1], Face.B) || !Integer((*Row)[2], Face.C))
    {
        return false;
    }
    return Face.A != Face.B && Face.A != Face.C && Face.B != Face.C;
}

bool SameGeometry(const FDynamicMesh3& A, const FDynamicMesh3& B)
{
    if (A.VertexCount() != B.VertexCount() || A.TriangleCount() != B.TriangleCount()) { return false; }
    for (int32 V : A.VertexIndicesItr())
    {
        if (!B.IsVertex(V) || A.GetVertex(V) != B.GetVertex(V)) { return false; }
    }
    for (int32 T : A.TriangleIndicesItr())
    {
        if (!B.IsTriangle(T) || A.GetTriangle(T) != B.GetTriangle(T)) { return false; }
    }
    return true;
}

bool SameAttributes(const FDynamicMesh3& A, const FDynamicMesh3& B)
{
    return A.HasAttributes() == B.HasAttributes()
        && (!A.HasAttributes() || A.Attributes()->IsSameAs(*B.Attributes(), false));
}

bool Validate(FDetailSession& Session, const TSharedPtr<FJsonObject>& Source,
    const TSharedPtr<FJsonObject>& Mask, const TSharedPtr<FJsonObject>& Trial,
    const TSharedPtr<FJsonObject>& Manifest, FString& Error)
{
    const TArray<TSharedPtr<FJsonValue>> *SourceVertices = nullptr, *TrialVertices = nullptr;
    const TArray<TSharedPtr<FJsonValue>> *SourceFaces = nullptr, *TrialFaces = nullptr;
    const TArray<TSharedPtr<FJsonValue>> *Tags = nullptr, *Selected = nullptr, *DeclaredChanged = nullptr;
    FString MeshSha, ManifestSha, Bands, Eligible;
    if (!Source->TryGetArrayField(TEXT("vertices_cm"), SourceVertices)
        || !Trial->TryGetArrayField(TEXT("vertices_cm"), TrialVertices)
        || !Source->TryGetArrayField(TEXT("triangles"), SourceFaces)
        || !Trial->TryGetArrayField(TEXT("triangles"), TrialFaces)
        || !Mask->TryGetArrayField(TEXT("proposed_tag_masks"), Tags)
        || !Mask->TryGetStringField(TEXT("mesh_sha256"), MeshSha) || MeshSha != RetainedSourceSha
        || !Manifest->TryGetStringField(TEXT("source_mesh_sha256"), ManifestSha) || ManifestSha != MeshSha
        || !Mask->TryGetStringField(TEXT("bands"), Bands)
        || !Mask->TryGetStringField(TEXT("eligible_all_vertices_movable"), Eligible)
        || !Manifest->TryGetArrayField(TEXT("selected_face_indices"), Selected)
        || !Manifest->TryGetArrayField(TEXT("changed_vertex_ids"), DeclaredChanged))
    {
        Error = TEXT("missing or wrong retained source, mask or treatment fields"); return false;
    }
    const FDynamicMesh3& Native = Session.Baseline;
    if (Native.VertexCount() <= 0 || Native.TriangleCount() <= 0 || Native.TriangleCount() > 60000
        || SourceVertices->Num() != Native.VertexCount() || TrialVertices->Num() != Native.VertexCount()
        || SourceFaces->Num() != Native.TriangleCount() || TrialFaces->Num() != Native.TriangleCount()
        || Bands.Len() != Native.TriangleCount() || Eligible.Len() != Bands.Len() || Tags->Num() != Bands.Len()
        || Selected->IsEmpty() || Selected->Num() > 535)
    {
        Error = TEXT("source, mask, trial or native mesh count mismatch"); return false;
    }
    if (!Native.HasAttributes() || !Native.Attributes()->PrimaryNormals() || !Native.Attributes()->PrimaryUV())
    {
        Error = TEXT("native v8 normal or UV overlay is missing"); return false;
    }

    TMap<int32, bool> Movable;
    TSet<int32> Changed;
    for (int32 I = 0; I < SourceVertices->Num(); ++I)
    {
        int32 V, TV; FVector3d P, Base, TP, Candidate; bool CanMove, TrialCanMove;
        if (!ReadVertex((*SourceVertices)[I], V, P, Base, CanMove)
            || !ReadVertex((*TrialVertices)[I], TV, TP, Candidate, TrialCanMove)
            || Movable.Contains(V) || !Native.IsVertex(V) || V != TV || P != TP || CanMove != TrialCanMove
            || (Native.GetVertex(V) - Base).Length() > PositionToleranceCm)
        {
            Error = FString::Printf(TEXT("source/native/trial vertex mismatch at row %d"), I); return false;
        }
        const FVector3d ActualTrial = Candidate == Base ? Native.GetVertex(V) : Candidate;
        const double Added = (ActualTrial - Native.GetVertex(V)).Length();
        const double Total = (ActualTrial - P).Length();
        if ((Base - P).Length() > 50.0 + PositionToleranceCm || Total > 50.0 + PositionToleranceCm
            || Added > 5.0 + PositionToleranceCm || (!CanMove && (Base != P || Candidate != Base)))
        {
            Error = FString::Printf(TEXT("locked vertex or displacement bound failed at vertex %d"), V); return false;
        }
        Movable.Add(V, CanMove);
        if (Candidate != Base) { Changed.Add(V); Session.TrialPositions.Add(V, Candidate); }
        Session.MaxAdditionalCm = FMath::Max(Session.MaxAdditionalCm, Added);
        Session.MaxTotalCm = FMath::Max(Session.MaxTotalCm, Total);
    }
    for (const auto& Value : *Selected)
    {
        int32 Row;
        if (!Integer(Value, Row) || Row >= Bands.Len() || Session.SelectedRows.Contains(Row))
        {
            Error = TEXT("duplicate or invalid selected source-face row"); return false;
        }
        Session.SelectedRows.Add(Row);
    }
    TSet<int32> ChangedClaim;
    for (const auto& Value : *DeclaredChanged)
    {
        int32 V;
        if (!Integer(Value, V) || ChangedClaim.Contains(V) || !Changed.Contains(V))
        {
            Error = TEXT("treatment changed-vertex declaration mismatch"); return false;
        }
        ChangedClaim.Add(V);
    }
    if (Changed.IsEmpty() || Changed.Num() != ChangedClaim.Num())
    {
        Error = TEXT("empty treatment or incomplete changed-vertex declaration"); return false;
    }
    Session.ChangedVertexCount = Changed.Num();

    TSet<int32> FrozenVertices, SelectedNormalElements, FrozenNormalElements;
    for (int32 V : Native.VertexIndicesItr())
    {
        if (Native.IsBoundaryVertex(V)) { FrozenVertices.Add(V); }
    }
    const auto* Normals = Native.Attributes()->PrimaryNormals();
    const auto* UV = Native.Attributes()->PrimaryUV();
    int32 Row = 0;
    for (int32 T : Native.TriangleIndicesItr())
    {
        FIndex3i Face, TrialFace;
        int32 Tag;
        if (!ReadFace((*SourceFaces)[Row], Face) || !ReadFace((*TrialFaces)[Row], TrialFace)
            || Face != TrialFace || Face != Native.GetTriangle(T) || !Integer((*Tags)[Row], Tag) || Tag > 31
            || !Movable.Contains(Face.A) || !Movable.Contains(Face.B) || !Movable.Contains(Face.C)
            || !FString(TEXT("ABCU")).Contains(FString::Chr(Bands[Row]))
            || (Eligible[Row] != TCHAR('0') && Eligible[Row] != TCHAR('1')))
        {
            Error = FString::Printf(TEXT("native ordered face correspondence failed at row %d"), Row); return false;
        }
        const bool Protected = !Movable[Face.A] || !Movable[Face.B] || !Movable[Face.C];
        if ((Eligible[Row] == TCHAR('0')) != Protected)
        {
            Error = TEXT("mask protection differs from native source vertex flags"); return false;
        }
        const bool IsSelected = Session.SelectedRows.Contains(Row);
        if (IsSelected && (Bands[Row] != TCHAR('A') || Protected || (Tag & 2) != 0))
        {
            Error = TEXT("treatment selected a protected, silhouette or non-A face"); return false;
        }
        if (!IsSelected)
        {
            FrozenVertices.Add(Face.A); FrozenVertices.Add(Face.B); FrozenVertices.Add(Face.C);
        }
        if (!Normals->IsSetTriangle(T) || !UV->IsSetTriangle(T))
        {
            Error = TEXT("native normal or UV overlay is incomplete"); return false;
        }
        const FIndex3i NormalFace = Normals->GetTriangle(T), UVFace = UV->GetTriangle(T);
        for (int32 E : {UVFace.A, UVFace.B, UVFace.C})
        {
            if (!UV->IsElement(E)) { Error = TEXT("native UV overlay is incomplete"); return false; }
        }
        for (int32 E : {NormalFace.A, NormalFace.B, NormalFace.C})
        {
            if (!Normals->IsElement(E)) { Error = TEXT("native normal overlay is incomplete"); return false; }
            if (IsSelected) { SelectedNormalElements.Add(E); } else { FrozenNormalElements.Add(E); }
        }
        const auto TrialPosition = [&Session, &Native](int32 V)
        {
            const FVector3d* ChangedPosition = Session.TrialPositions.Find(V);
            return ChangedPosition ? *ChangedPosition : Native.GetVertex(V);
        };
        const FVector3d A = TrialPosition(Face.A), B = TrialPosition(Face.B), C = TrialPosition(Face.C);
        const FVector3d OA = Native.GetVertex(Face.A), OB = Native.GetVertex(Face.B), OC = Native.GetVertex(Face.C);
        const double OldXY = (OB.X - OA.X) * (OC.Y - OA.Y) - (OB.Y - OA.Y) * (OC.X - OA.X);
        const double NewXY = (B.X - A.X) * (C.Y - A.Y) - (B.Y - A.Y) * (C.X - A.X);
        if (FMath::Abs(OldXY) < 1.e-8 || OldXY * NewXY <= 0 || FMath::Abs(NewXY) < 0.1 * FMath::Abs(OldXY) - 1.e-7)
        {
            Error = TEXT("treatment folded or collapsed a native face"); return false;
        }
        Session.ProtectedFaceCount += Protected ? 1 : 0;
        Session.RowToTriangle.Add(T);
        Session.MaskSlots.Add(Bands[Row] == TCHAR('U') ? 0 : Protected ? 3 : Bands[Row] == TCHAR('A') ? 1 : Bands[Row] == TCHAR('B') ? 2 : 0);
        ++Row;
    }
    for (int32 V : Changed)
    {
        if (FrozenVertices.Contains(V)) { Error = TEXT("treatment moves an outside-face or native-boundary vertex"); return false; }
    }
    for (int32 E : SelectedNormalElements)
    {
        if (!FrozenNormalElements.Contains(E) && !FrozenVertices.Contains(Normals->GetParentVertex(E)))
        {
            Session.EditableNormals.Add(E);
        }
    }
    Session.EditableNormals.Sort();
    return true;
}
}

FString UYacsLandscapeMeshDiagnosticLibrary::BeginComponent230Detail(UDynamicMeshComponent* Component,
    const FString& SourceJson, const FString& MaskJson, const FString& TrialJson, const FString& ManifestJson)
{
    if (DetailSession.IsValid()) { return Failure(TEXT("another native detail session is active")); }
    if (!IsValid(Component) || !Component->GetOwner() || !Component->GetOwner()->HasAnyFlags(RF_Transient)
        || !Component->GetDynamicMesh() || Component->GetCollisionEnabled() != ECollisionEnabled::NoCollision)
    {
        return Failure(TEXT("detail requires the existing transient, non-colliding v8 component"));
    }
    TSharedPtr<FJsonObject> Source, Mask, Trial, Manifest;
    if (!Parse(SourceJson, Source) || !Parse(MaskJson, Mask) || !Parse(TrialJson, Trial) || !Parse(ManifestJson, Manifest))
    {
        return Failure(TEXT("invalid native detail JSON"));
    }
    auto Candidate = MakeUnique<FDetailSession>();
    Candidate->Component = Component;
    Candidate->Baseline = Component->GetDynamicMesh()->GetMeshRef();
    FString Error;
    if (!Validate(*Candidate, Source, Mask, Trial, Manifest, Error)) { return Failure(Error); }
    TArray<TSharedPtr<FJsonValue>> Mapping;
    for (int32 T : Candidate->RowToTriangle) { Mapping.Add(MakeShared<FJsonValueNumber>(T)); }
    const auto Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("status"), TEXT("DETAIL_NATIVE_SOURCE_VERIFIED"));
    Result->SetStringField(TEXT("source_mesh_sha256"), RetainedSourceSha);
    Result->SetArrayField(TEXT("source_row_to_native_triangle_id"), Mapping);
    Result->SetNumberField(TEXT("vertex_count"), Candidate->Baseline.VertexCount());
    Result->SetNumberField(TEXT("triangle_count"), Candidate->Baseline.TriangleCount());
    Result->SetNumberField(TEXT("protected_face_count"), Candidate->ProtectedFaceCount);
    Result->SetNumberField(TEXT("selected_face_count"), Candidate->SelectedRows.Num());
    Result->SetNumberField(TEXT("changed_vertex_count"), Candidate->ChangedVertexCount);
    Result->SetNumberField(TEXT("editable_normal_elements"), Candidate->EditableNormals.Num());
    Result->SetNumberField(TEXT("max_additional_displacement_cm"), Candidate->MaxAdditionalCm);
    Result->SetNumberField(TEXT("max_source_displacement_cm"), Candidate->MaxTotalCm);
    Result->SetBoolField(TEXT("native_attributes_retained"), true);
    Result->SetNumberField(TEXT("source_position_tolerance_cm"), PositionToleranceCm);
    Result->SetBoolField(TEXT("geometry_mutated"), false);
    DetailSession = MoveTemp(Candidate);
    return Json(Result);
}

FString UYacsLandscapeMeshDiagnosticLibrary::SetComponent230DetailMode(UDynamicMeshComponent* Component, const FString& Mode)
{
    if (!DetailSession.IsValid() || DetailSession->Component.Get() != Component || !IsValid(Component))
    {
        return Failure(TEXT("no matching native detail session"));
    }
    const bool IsTrial = Mode == TEXT("trial");
    const bool IsMask = Mode == TEXT("mask");
    const bool Magenta = Mode == TEXT("patch-magenta"), Cyan = Mode == TEXT("patch-cyan");
    if (!IsTrial && !IsMask && !Magenta && !Cyan && Mode != TEXT("baseline"))
    {
        return Failure(TEXT("unknown native detail mode"));
    }
    const auto& Current = Component->GetDynamicMesh()->GetMeshRef();
    if (Current.VertexCount() != DetailSession->Baseline.VertexCount()
        || Current.TriangleCount() != DetailSession->Baseline.TriangleCount())
    {
        return Failure(TEXT("native detail surface changed outside the session"));
    }
    for (int32 V : DetailSession->Baseline.VertexIndicesItr())
    {
        const FVector3d* TrialPosition = DetailSession->CurrentMode == TEXT("trial") ? DetailSession->TrialPositions.Find(V) : nullptr;
        const FVector3d Expected = TrialPosition ? *TrialPosition : DetailSession->Baseline.GetVertex(V);
        if (!Current.IsVertex(V) || Current.GetVertex(V) != Expected)
        {
            return Failure(TEXT("native detail vertex changed outside the session"));
        }
    }
    for (int32 T : DetailSession->Baseline.TriangleIndicesItr())
    {
        if (!Current.IsTriangle(T) || Current.GetTriangle(T) != DetailSession->Baseline.GetTriangle(T))
        {
            return Failure(TEXT("native detail topology changed outside the session"));
        }
    }
    FDynamicMesh3 Candidate(DetailSession->Baseline);
    Candidate.Attributes()->EnableMaterialID();
    auto* Materials = Candidate.Attributes()->GetMaterialID();
    TArray<int32> Counts; Counts.Init(0, 6);
    for (int32 Row = 0; Row < DetailSession->RowToTriangle.Num(); ++Row)
    {
        const int32 Slot = IsMask ? DetailSession->MaskSlots[Row]
            : (Magenta || Cyan) && DetailSession->SelectedRows.Contains(Row) ? (Magenta ? 4 : 5) : 0;
        Materials->SetValue(DetailSession->RowToTriangle[Row], Slot);
        ++Counts[Slot];
    }
    if (IsTrial)
    {
        for (const auto& Pair : DetailSession->TrialPositions) { Candidate.SetVertex(Pair.Key, Pair.Value); }
        if (!DetailSession->EditableNormals.IsEmpty() && !FMeshNormals::RecomputeOverlayElementNormals(
            Candidate, DetailSession->EditableNormals, true, true))
        {
            return Failure(TEXT("selective native normal recomputation failed"));
        }
    }
    const auto* BeforeNormals = DetailSession->Baseline.Attributes()->PrimaryNormals();
    const auto* AfterNormals = Candidate.Attributes()->PrimaryNormals();
    TSet<int32> Edited;
    for (int32 E : DetailSession->EditableNormals) { Edited.Add(E); }
    for (int32 E : BeforeNormals->ElementIndicesItr())
    {
        FVector3f Before, After; BeforeNormals->GetElement(E, Before); AfterNormals->GetElement(E, After);
        if (AfterNormals->GetParentVertex(E) != BeforeNormals->GetParentVertex(E)
            || ((!IsTrial || !Edited.Contains(E)) && Before != After))
        {
            return Failure(TEXT("native fixed/shared normal element changed"));
        }
    }
    const auto* BeforeUV = DetailSession->Baseline.Attributes()->PrimaryUV();
    const auto* AfterUV = Candidate.Attributes()->PrimaryUV();
    for (int32 E : BeforeUV->ElementIndicesItr())
    {
        FVector2f Before, After; BeforeUV->GetElement(E, Before); AfterUV->GetElement(E, After);
        if (Before != After || BeforeUV->GetParentVertex(E) != AfterUV->GetParentVertex(E))
        {
            return Failure(TEXT("native UV element changed"));
        }
    }
    for (int32 T : Candidate.TriangleIndicesItr())
    {
        if (Candidate.GetTriangle(T) != DetailSession->Baseline.GetTriangle(T)
            || BeforeNormals->GetTriangle(T) != AfterNormals->GetTriangle(T)
            || BeforeUV->GetTriangle(T) != AfterUV->GetTriangle(T))
        {
            return Failure(TEXT("native face or attribute topology changed"));
        }
    }
    if (!IsTrial && !SameGeometry(Candidate, DetailSession->Baseline))
    {
        return Failure(TEXT("material-only diagnostic changed geometry"));
    }
    Component->GetDynamicMesh()->SetMesh(MoveTemp(Candidate));
    const auto& Actual = Component->GetDynamicMesh()->GetMeshRef();
    for (int32 V : DetailSession->Baseline.VertexIndicesItr())
    {
        const FVector3d* ChangedPosition = IsTrial ? DetailSession->TrialPositions.Find(V) : nullptr;
        const FVector3d Expected = ChangedPosition ? *ChangedPosition : DetailSession->Baseline.GetVertex(V);
        if (!Actual.IsVertex(V) || Actual.GetVertex(V) != Expected)
        {
            return Failure(TEXT("native changed or fixed position readback mismatch"));
        }
    }
    for (int32 Row = 0; Row < DetailSession->RowToTriangle.Num(); ++Row)
    {
        const int32 T = DetailSession->RowToTriangle[Row];
        const int32 Slot = IsMask ? DetailSession->MaskSlots[Row]
            : (Magenta || Cyan) && DetailSession->SelectedRows.Contains(Row) ? (Magenta ? 4 : 5) : 0;
        if (Actual.Attributes()->GetMaterialID()->GetValue(T) != Slot)
        {
            return Failure(TEXT("native material slot readback mismatch"));
        }
    }
    DetailSession->CurrentMode = Mode;
    const auto Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("status"), TEXT("DETAIL_NATIVE_MODE_APPLIED"));
    Result->SetStringField(TEXT("mode"), Mode);
    TArray<TSharedPtr<FJsonValue>> SlotCounts;
    for (int32 Count : Counts) { SlotCounts.Add(MakeShared<FJsonValueNumber>(Count)); }
    Result->SetArrayField(TEXT("material_slot_face_counts"), SlotCounts);
    Result->SetNumberField(TEXT("triangle_count"), Actual.TriangleCount());
    Result->SetNumberField(TEXT("changed_vertices"), IsTrial ? DetailSession->ChangedVertexCount : 0);
    Result->SetNumberField(TEXT("recomputed_normal_elements"), IsTrial ? DetailSession->EditableNormals.Num() : 0);
    Result->SetNumberField(TEXT("outside_or_shared_normal_max_delta"), 0);
    Result->SetBoolField(TEXT("native_uvs_unchanged"), true);
    Result->SetBoolField(TEXT("topology_unchanged"), true);
    Result->SetBoolField(TEXT("every_source_face_rendered_once"), true);
    return Json(Result);
}

FString UYacsLandscapeMeshDiagnosticLibrary::EndComponent230Detail(UDynamicMeshComponent* Component)
{
    if (!DetailSession.IsValid())
    {
        const auto Result = MakeShared<FJsonObject>(); Result->SetStringField(TEXT("status"), TEXT("DETAIL_NATIVE_NO_SESSION")); return Json(Result);
    }
    if (!IsValid(Component) || DetailSession->Component.Get() != Component)
    {
        return Failure(TEXT("cannot restore a different or destroyed detail component"));
    }
    Component->GetDynamicMesh()->SetMesh(FDynamicMesh3(DetailSession->Baseline));
    if (!SameGeometry(Component->GetDynamicMesh()->GetMeshRef(), DetailSession->Baseline)
        || !SameAttributes(Component->GetDynamicMesh()->GetMeshRef(), DetailSession->Baseline))
    {
        return Failure(TEXT("native detail geometry or attribute restoration failed"));
    }
    DetailSession.Reset();
    const auto Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("status"), TEXT("DETAIL_NATIVE_RESTORED"));
    Result->SetBoolField(TEXT("complete_native_snapshot_restored"), true);
    return Json(Result);
}

UMaterial* UYacsLandscapeMeshDiagnosticLibrary::CreateComponent230DetailMaterial()
{
    UMaterial* Material = NewObject<UMaterial>(GetTransientPackage(), NAME_None, RF_Transient);
    if (Material)
    {
        Material->SetShadingModel(MSM_Unlit);
        Material->BlendMode = BLEND_Opaque;
        Material->TwoSided = false;
    }
    return Material;
}

#if WITH_DEV_AUTOMATION_TESTS
namespace
{
TArray<TSharedPtr<FJsonValue>> TestNumbers(const TArray<double>& Values)
{
    TArray<TSharedPtr<FJsonValue>> Result;
    for (double Value : Values) { Result.Add(MakeShared<FJsonValueNumber>(Value)); }
    return Result;
}

FString ChangeTestCandidate(const FString& Text, int32 Vertex, double DeltaZ)
{
    TSharedPtr<FJsonObject> Object;
    if (!Parse(Text, Object)) { return TEXT("{}"); }
    auto Rows = Object->GetArrayField(TEXT("vertices_cm"));
    auto Row = Rows[Vertex]->AsArray();
    Row[6] = MakeShared<FJsonValueNumber>(Row[6]->AsNumber() + DeltaZ);
    Rows[Vertex] = MakeShared<FJsonValueArray>(Row);
    Object->SetArrayField(TEXT("vertices_cm"), Rows);
    return Json(Object.ToSharedRef());
}

struct FDetailTestFixture
{
    UWorld* World = nullptr;
    UDynamicMeshComponent* Component = nullptr;
    FDynamicMesh3 Baseline;
    FString Source, Mask, Trial, Manifest;

    bool Initialize()
    {
        // Four selected faces meet at vertex 4. The fifth, protected face
        // shares vertices/normals 1 and 2 and has split UVs at that boundary.
        const TArray<FVector3d> Positions = {FVector3d(0, 0, 0), FVector3d(20, 0, 0),
            FVector3d(20, 20, 0), FVector3d(0, 20, 0), FVector3d(10, 10, 2), FVector3d(40, 10, 0)};
        const TArray<FIndex3i> Faces = {FIndex3i(0, 1, 4), FIndex3i(1, 2, 4),
            FIndex3i(2, 3, 4), FIndex3i(3, 0, 4), FIndex3i(1, 5, 2)};
        for (const FVector3d& P : Positions) { Baseline.AppendVertex(P); }
        for (int32 I = 0; I < Faces.Num(); ++I)
        {
            if (Baseline.InsertTriangle(2 + I * 2, Faces[I], 0, false) != EMeshResult::Ok) { return false; }
        }
        Baseline.EnableAttributes();
        auto* Normals = Baseline.Attributes()->PrimaryNormals();
        auto* UV = Baseline.Attributes()->PrimaryUV();
        if (!Normals || !UV) { return false; }
        for (const FVector3d& P : Positions)
        {
            Normals->AppendElement(FVector3f(0, 0, 1));
            UV->AppendElement(FVector2f(static_cast<float>(P.X / 20), static_cast<float>(P.Y / 20)));
        }
        const int32 Split1 = UV->AppendElement(FVector2f(2, 0));
        const int32 Split2 = UV->AppendElement(FVector2f(2, 1));
        Baseline.Attributes()->EnableMaterialID();
        for (int32 I = 0; I < Faces.Num(); ++I)
        {
            const int32 T = 2 + I * 2;
            if (Normals->SetTriangle(T, Faces[I], false) != EMeshResult::Ok
                || UV->SetTriangle(T, I == 4 ? FIndex3i(Split1, 5, Split2) : Faces[I], false) != EMeshResult::Ok)
            { return false; }
            Baseline.Attributes()->GetMaterialID()->SetValue(T, 7 + I);
        }
        // Reproduces harmless JSON rounding on an outside vertex. Trial must
        // retain this exact native value, not write the serialized zero back.
        Baseline.SetVertex(5, Positions[5] + FVector3d(0, 0, PositionToleranceCm * 0.5));
        const auto SourceObject = MakeShared<FJsonObject>();
        TArray<TSharedPtr<FJsonValue>> Vertices, Triangles;
        for (int32 V = 0; V < Positions.Num(); ++V)
        {
            const FVector3d& P = Positions[V];
            Vertices.Add(MakeShared<FJsonValueArray>(TestNumbers(
                {double(V), P.X, P.Y, P.Z, P.X, P.Y, P.Z, V == 5 ? 0.0 : 1.0})));
        }
        for (const FIndex3i& Face : Faces)
        { Triangles.Add(MakeShared<FJsonValueArray>(TestNumbers({double(Face.A), double(Face.B), double(Face.C)}))); }
        SourceObject->SetArrayField(TEXT("vertices_cm"), Vertices);
        SourceObject->SetArrayField(TEXT("triangles"), Triangles);
        Source = Json(SourceObject);
        Trial = ChangeTestCandidate(Source, 4, 0.5);
        const auto MaskObject = MakeShared<FJsonObject>();
        MaskObject->SetStringField(TEXT("mesh_sha256"), RetainedSourceSha);
        MaskObject->SetStringField(TEXT("bands"), TEXT("AAAAB"));
        MaskObject->SetStringField(TEXT("eligible_all_vertices_movable"), TEXT("11110"));
        MaskObject->SetArrayField(TEXT("proposed_tag_masks"), TestNumbers({20, 20, 20, 20, 20}));
        Mask = Json(MaskObject);
        const auto ManifestObject = MakeShared<FJsonObject>();
        ManifestObject->SetStringField(TEXT("source_mesh_sha256"), RetainedSourceSha);
        ManifestObject->SetArrayField(TEXT("selected_face_indices"), TestNumbers({0, 1, 2, 3}));
        ManifestObject->SetArrayField(TEXT("changed_vertex_ids"), TestNumbers({4}));
        Manifest = Json(ManifestObject);
        World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("YacsDetailNativeTestWorld"));
        if (!World) { return false; }
        AActor* Owner = World->SpawnActor<AActor>();
        if (!Owner) { return false; }
        Owner->SetFlags(RF_Transient);
        Component = NewObject<UDynamicMeshComponent>(Owner, NAME_None, RF_Transient);
        if (!Component || !Component->GetDynamicMesh()) { return false; }
        Owner->SetRootComponent(Component);
        Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Component->GetDynamicMesh()->SetMesh(FDynamicMesh3(Baseline));
        return true;
    }

    ~FDetailTestFixture()
    {
        if (DetailSession.IsValid() && DetailSession->Component.Get() == Component)
        { UYacsLandscapeMeshDiagnosticLibrary::EndComponent230Detail(Component); }
        if (World) { World->DestroyWorld(false); }
    }
};

bool DetailTestStatus(const FString& Text, const TCHAR* Expected)
{
    TSharedPtr<FJsonObject> Result;
    FString Status;
    return Parse(Text, Result) && Result->TryGetStringField(TEXT("status"), Status) && Status == Expected;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FYacsDetailRejectBeforeMutation, "YACS.DetailNative.RejectBeforeMutation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FYacsDetailRejectBeforeMutation::RunTest(const FString& Parameters)
{
    if (!TestFalse(TEXT("No other proof session is active"), DetailSession.IsValid())) { return false; }
    FDetailTestFixture F;
    if (!TestTrue(TEXT("Native fixture initialized"), F.Initialize())) { return false; }
    const auto Reject = [this, &F](const TCHAR* Label, const FString& Source, const FString& Mask,
        const FString& Trial, const FString& Manifest)
    {
        TestTrue(Label, DetailTestStatus(UYacsLandscapeMeshDiagnosticLibrary::BeginComponent230Detail(
            F.Component, Source, Mask, Trial, Manifest), TEXT("DETAIL_NATIVE_FAIL")));
        TestFalse(TEXT("Rejected input creates no session"), DetailSession.IsValid());
        TestTrue(TEXT("Rejected input preserves exact native geometry"), SameGeometry(F.Baseline, F.Component->GetDynamicMesh()->GetMeshRef()));
        TestTrue(TEXT("Rejected input preserves complete attributes"), SameAttributes(F.Baseline, F.Component->GetDynamicMesh()->GetMeshRef()));
    };
    Reject(TEXT("Malformed source refused"), TEXT("{}"), F.Mask, F.Trial, F.Manifest);
    Reject(TEXT("Wrong source hash refused"), F.Source, F.Mask.Replace(RetainedSourceSha, TEXT("wrong")), F.Trial, F.Manifest);
    Reject(TEXT("Native/source position drift refused"), ChangeTestCandidate(F.Source, 0, 0.1), F.Mask, F.Trial, F.Manifest);
    Reject(TEXT("Non-A selected mask refused"), F.Source, F.Mask.Replace(TEXT("AAAAB"), TEXT("BAAAB")), F.Trial, F.Manifest);
    Reject(TEXT("Five-centimetre additional bound enforced"), F.Source, F.Mask, ChangeTestCandidate(F.Source, 4, 5.01), F.Manifest);
    TSharedPtr<FJsonObject> BoundaryManifest;
    Parse(F.Manifest, BoundaryManifest);
    BoundaryManifest->SetArrayField(TEXT("changed_vertex_ids"), TestNumbers({1, 4}));
    Reject(TEXT("Vertex shared with outside face is frozen"), F.Source, F.Mask,
        ChangeTestCandidate(F.Trial, 1, 0.25), Json(BoundaryManifest.ToSharedRef()));
    BoundaryManifest->SetArrayField(TEXT("changed_vertex_ids"), TestNumbers({0, 4}));
    Reject(TEXT("Native mesh boundary is frozen"), F.Source, F.Mask,
        ChangeTestCandidate(F.Trial, 0, 0.25), Json(BoundaryManifest.ToSharedRef()));
    TSharedPtr<FJsonObject> ReorderedSource;
    Parse(F.Source, ReorderedSource);
    auto Faces = ReorderedSource->GetArrayField(TEXT("triangles"));
    Faces.Swap(0, 1);
    ReorderedSource->SetArrayField(TEXT("triangles"), Faces);
    Reject(TEXT("Source row/native triangle identity drift refused"), Json(ReorderedSource.ToSharedRef()), F.Mask, F.Trial, F.Manifest);
    F.Component->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Reject(TEXT("Colliding component refused"), F.Source, F.Mask, F.Trial, F.Manifest);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FYacsDetailPreservationAndRestore, "YACS.DetailNative.PreservationAndRestore",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FYacsDetailPreservationAndRestore::RunTest(const FString& Parameters)
{
    if (!TestFalse(TEXT("No other proof session is active"), DetailSession.IsValid())) { return false; }
    FDetailTestFixture F;
    if (!TestTrue(TEXT("Native fixture initialized"), F.Initialize())) { return false; }
    const FString Begin = UYacsLandscapeMeshDiagnosticLibrary::BeginComponent230Detail(F.Component, F.Source, F.Mask, F.Trial, F.Manifest);
    if (!TestTrue(TEXT("Bounded native trial admitted"), DetailTestStatus(Begin, TEXT("DETAIL_NATIVE_SOURCE_VERIFIED")))) { return false; }
    TestTrue(TEXT("Sparse native triangle IDs are explicit"), DetailSession->RowToTriangle == TArray<int32>({2, 4, 6, 8, 10}));
    TestEqual(TEXT("Only changed vertices are retained for writeback"), DetailSession->TrialPositions.Num(), 1);
    TestTrue(TEXT("Unknown mode is refused"), DetailTestStatus(
        UYacsLandscapeMeshDiagnosticLibrary::SetComponent230DetailMode(F.Component, TEXT("unknown")), TEXT("DETAIL_NATIVE_FAIL")));
    for (const TCHAR* Mode : {TEXT("baseline"), TEXT("mask"), TEXT("patch-magenta"), TEXT("patch-cyan"), TEXT("trial")})
    {
        if (!TestTrue(Mode, DetailTestStatus(UYacsLandscapeMeshDiagnosticLibrary::SetComponent230DetailMode(F.Component, Mode),
            TEXT("DETAIL_NATIVE_MODE_APPLIED")))) { return false; }
        const auto& Actual = F.Component->GetDynamicMesh()->GetMeshRef();
        const bool TrialMode = FString(Mode) == TEXT("trial");
        for (int32 V : F.Baseline.VertexIndicesItr())
        {
            const FVector3d Expected = F.Baseline.GetVertex(V) + (TrialMode && V == 4 ? FVector3d(0, 0, 0.5) : FVector3d::Zero());
            TestTrue(TEXT("Exact changed and untouched native positions"), Actual.GetVertex(V) == Expected);
        }
        TestTrue(TEXT("UV values, seams and topology remain exact"),
            Actual.Attributes()->PrimaryUV()->IsSameAs(*F.Baseline.Attributes()->PrimaryUV(), false));
        for (int32 E : {1, 2, 5})
        {
            FVector3f Before, After;
            F.Baseline.Attributes()->PrimaryNormals()->GetElement(E, Before);
            Actual.Attributes()->PrimaryNormals()->GetElement(E, After);
            TestTrue(TEXT("Outside and shared normal elements remain exact"), Before == After);
        }
        TestEqual(TEXT("Exactly one original face per triangle remains"), Actual.TriangleCount(), 5);
    }
    TestTrue(TEXT("Native snapshot restored"), DetailTestStatus(
        UYacsLandscapeMeshDiagnosticLibrary::EndComponent230Detail(F.Component), TEXT("DETAIL_NATIVE_RESTORED")));
    TestTrue(TEXT("Restoration preserves native positions and IDs"), SameGeometry(F.Baseline, F.Component->GetDynamicMesh()->GetMeshRef()));
    TestTrue(TEXT("Restoration includes normals, split UVs and original material IDs"),
        SameAttributes(F.Baseline, F.Component->GetDynamicMesh()->GetMeshRef()));
    TestFalse(TEXT("Restoration releases the native session"), DetailSession.IsValid());
    return true;
}
#endif
