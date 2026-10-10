#include "Diagnostics/YacsRoadMaterialInspectionLibrary.h"

#include "Components/DynamicMeshComponent.h"
#include "DynamicMesh/DynamicMesh3.h"
#include "DynamicMesh/DynamicMeshAttributeSet.h"
#include "DynamicMesh/DynamicMeshOverlay.h"
#include "DynamicMeshActor.h"
#include "GameFramework/Actor.h"
#include "Hash/Blake3.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UDynamicMesh.h"
#include "UObject/Package.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif

namespace
{
using UE::Geometry::FDynamicMesh3;
using UE::Geometry::FIndex3i;
constexpr int32 MaxSupportVertices = 85000;
constexpr int32 MaxSupportTriangles = 150000;
constexpr int32 RoadVertices = 856250;
constexpr int32 RoadTriangles = 1711760;
constexpr int32 MaxWitnessOutputChars = 48 * 1024 * 1024;
constexpr const TCHAR* HashFormat = TEXT("blake3-256-le-i32-f64-corners-v1");

// These scalar encodings match the previous Python <i/<d streams. The hash
// algorithm and field names deliberately change; an old SHA256 is never relabelled.
// Epic UE5.8: /API/Runtime/Core/FBlake3 and /API/Runtime/GeometryCore/FDynamicMeshAttributeSet.
struct FHashRecord
{
    uint8 Bytes[384];
    int32 Count = 0;
    void Integer(int32 Value)
    {
        const uint32 Bits = static_cast<uint32>(Value);
        for (int32 I = 0; I < 4; ++I) { Bytes[Count++] = static_cast<uint8>(Bits >> (I * 8)); }
    }
    void Number(double Value)
    {
        uint64 Bits; FMemory::Memcpy(&Bits, &Value, sizeof(Bits));
        for (int32 I = 0; I < 8; ++I) { Bytes[Count++] = static_cast<uint8>(Bits >> (I * 8)); }
    }
    void Boolean(bool Value) { Bytes[Count++] = Value ? 1 : 0; }
    void AddTo(FBlake3& Hash) const { Hash.Update(Bytes, static_cast<uint64>(Count)); }
};

FString Hex(FBlake3& Hash)
{
    const FBlake3Hash Digest = Hash.Finalize();
    constexpr TCHAR Digits[] = TEXT("0123456789abcdef");
    FString Result; Result.Reserve(64);
    for (uint8 Byte : Digest.GetBytes())
    {
        Result.AppendChar(Digits[Byte >> 4]); Result.AppendChar(Digits[Byte & 15]);
    }
    return Result;
}

bool Finite(const FVector3d& P)
{
    return FMath::IsFinite(P.X) && FMath::IsFinite(P.Y) && FMath::IsFinite(P.Z);
}

bool IsAcceptedLabel(const FString& Label, bool& bRoad)
{
    bRoad = Label == TEXT("YACS_PERSIST_ROAD");
    if (bRoad) { return true; }
    const FString Prefix(TEXT("YACS_PERSIST_SUPPORT_"));
    if (!Label.StartsWith(Prefix) || Label.Len() != Prefix.Len() + 3) { return false; }
    const FString Suffix = Label.Right(3);
    for (TCHAR Ch : Suffix) { if (Ch < TEXT('0') || Ch > TEXT('9')) { return false; } }
    return FCString::Atoi(*Suffix) < 186;
}

FString InspectNative(const FDynamicMesh3& Mesh, bool bRoad, int32 WitnessCount,
    const FString& Label, const FString& ComponentPath, const FString& MeshPath,
    const FString& MapPackage)
{
    const int32 Vertices = Mesh.VertexCount(), Triangles = Mesh.TriangleCount();
    if (Vertices <= 0 || Triangles <= 0 || WitnessCount < 0 || WitnessCount > Triangles
        || (bRoad && (Vertices != RoadVertices || Triangles != RoadTriangles || WitnessCount != 0))
        || (!bRoad && (Vertices > MaxSupportVertices || Triangles > MaxSupportTriangles))
        || Mesh.MaxVertexID() != Vertices || Mesh.MaxTriangleID() != Triangles)
    { return TEXT("{\"error\":\"mesh is sparse, outside the accepted count budget or has invalid witnesses\"}"); }
    if (!Mesh.HasAttributes() || !Mesh.Attributes()->PrimaryNormals() || !Mesh.Attributes()->HasMaterialID())
    { return TEXT("{\"error\":\"required native normal or material-ID attributes are absent\"}"); }
    const auto* Attributes = Mesh.Attributes();
    const auto* Normals = Attributes->PrimaryNormals();
    const int32 UVSets = Attributes->NumUVLayers();
    if (UVSets < 0 || UVSets > 4)
    { return TEXT("{\"error\":\"native UV layer budget exceeded\"}"); }

    FBlake3 Geometry, Corners, MaterialIds;
    FHashRecord Header; Header.Integer(1); Header.Integer(Vertices); Header.Integer(Triangles); Header.AddTo(Geometry);
    FHashRecord CornerHeader; CornerHeader.Integer(1); CornerHeader.Integer(UVSets); CornerHeader.AddTo(Corners);
    for (int32 V = 0; V < Vertices; ++V)
    {
        const FVector3d P = Mesh.GetVertex(V);
        if (!Finite(P)) { return TEXT("{\"error\":\"nonfinite native vertex\"}"); }
        FHashRecord Record; Record.Integer(V); Record.Number(P.X); Record.Number(P.Y); Record.Number(P.Z);
        Record.AddTo(Geometry);
    }

    FString Result;
    const auto Writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Result);
    Writer->WriteObjectStart();
    Writer->WriteValue(TEXT("schema_version"), 2);
    Writer->WriteValue(TEXT("status"), TEXT("ROAD_MATERIAL_MESH_INSPECTED"));
    Writer->WriteValue(TEXT("hash_format"), HashFormat);
    Writer->WriteValue(TEXT("actor_label"), Label);
    Writer->WriteValue(TEXT("component_path"), ComponentPath);
    Writer->WriteValue(TEXT("mesh_path"), MeshPath);
    Writer->WriteValue(TEXT("map_package"), MapPackage);
    Writer->WriteValue(TEXT("geometry_mutated"), false);
    Writer->WriteValue(TEXT("witness_triangle_count"), WitnessCount);
    Writer->WriteArrayStart(TEXT("witness_triangles"));
    for (int32 T = 0; T < Triangles; ++T)
    {
        const FIndex3i Face = Mesh.GetTriangle(T);
        if (Face.A == Face.B || Face.A == Face.C || Face.B == Face.C
            || !Mesh.IsVertex(Face.A) || !Mesh.IsVertex(Face.B) || !Mesh.IsVertex(Face.C)
            || !Normals->IsSetTriangle(T))
        { return TEXT("{\"error\":\"invalid native triangle or missing split normals\"}"); }
        FHashRecord FaceRecord; FaceRecord.Integer(T);
        FaceRecord.Integer(Face.A); FaceRecord.Integer(Face.B); FaceRecord.Integer(Face.C); FaceRecord.AddTo(Geometry);
        FHashRecord CornerRecord; CornerRecord.Integer(T);
        const FIndex3i NormalFace = Normals->GetTriangle(T);
        for (int32 E : {NormalFace.A, NormalFace.B, NormalFace.C})
        {
            if (!Normals->IsElement(E)) { return TEXT("{\"error\":\"invalid native normal element\"}"); }
            FVector3f N; Normals->GetElement(E, N);
            if (!Finite(FVector3d(N))) { return TEXT("{\"error\":\"nonfinite native normal\"}"); }
            CornerRecord.Number(N.X); CornerRecord.Number(N.Y); CornerRecord.Number(N.Z);
        }
        for (int32 Layer = 0; Layer < UVSets; ++Layer)
        {
            const auto* UV = Attributes->GetUVLayer(Layer);
            if (!UV) { return TEXT("{\"error\":\"missing declared native UV layer\"}"); }
            const bool bSet = UV->IsSetTriangle(T);
            CornerRecord.Integer(Layer); CornerRecord.Boolean(bSet);
            const FIndex3i UVFace = bSet ? UV->GetTriangle(T) : FIndex3i(-1, -1, -1);
            for (int32 E : {UVFace.A, UVFace.B, UVFace.C})
            {
                FVector2f Value(0, 0);
                if (bSet)
                {
                    if (!UV->IsElement(E)) { return TEXT("{\"error\":\"invalid native UV element\"}"); }
                    UV->GetElement(E, Value);
                }
                if (!FMath::IsFinite(Value.X) || !FMath::IsFinite(Value.Y))
                { return TEXT("{\"error\":\"nonfinite native UV\"}"); }
                CornerRecord.Number(Value.X); CornerRecord.Number(Value.Y);
            }
        }
        CornerRecord.AddTo(Corners);
        const int32 MaterialId = Attributes->GetMaterialID()->GetValue(T);
        if (MaterialId < 0 || MaterialId > 31) { return TEXT("{\"error\":\"unbounded native material ID\"}"); }
        FHashRecord MaterialRecord; MaterialRecord.Integer(T); MaterialRecord.Integer(MaterialId); MaterialRecord.AddTo(MaterialIds);
        if (T < WitnessCount)
        {
            Writer->WriteArrayStart();
            Writer->WriteValue(T); Writer->WriteValue(Face.A); Writer->WriteValue(Face.B); Writer->WriteValue(Face.C);
            for (int32 V : {Face.A, Face.B, Face.C})
            {
                const FVector3d P = Mesh.GetVertex(V);
                Writer->WriteValue(P.X); Writer->WriteValue(P.Y); Writer->WriteValue(P.Z);
            }
            Writer->WriteArrayEnd();
        }
    }
    Writer->WriteArrayEnd();
    Writer->WriteValue(TEXT("material_ids_included"), !bRoad);
    Writer->WriteArrayStart(TEXT("material_ids"));
    if (!bRoad)
    {
        for (int32 T = 0; T < Triangles; ++T) { Writer->WriteValue(Attributes->GetMaterialID()->GetValue(T)); }
    }
    Writer->WriteArrayEnd();
    Writer->WriteObjectStart(TEXT("summary"));
    Writer->WriteValue(TEXT("vertex_count"), Vertices); Writer->WriteValue(TEXT("triangle_count"), Triangles);
    Writer->WriteValue(TEXT("uv_set_count"), UVSets);
    Writer->WriteValue(TEXT("positions_indices_blake3"), Hex(Geometry));
    Writer->WriteValue(TEXT("triangle_corner_normals_uv_blake3"), Hex(Corners));
    Writer->WriteValue(TEXT("material_ids_blake3"), Hex(MaterialIds));
    Writer->WriteObjectEnd(); Writer->WriteObjectEnd(); Writer->Close();
    return Result.Len() <= MaxWitnessOutputChars ? Result
        : TEXT("{\"error\":\"native witness serialization exceeded its byte budget\"}");
}
}

FString UYacsRoadMaterialInspectionLibrary::InspectMesh(UDynamicMeshComponent* Component, int32 WitnessTriangleCount)
{
    if (!IsInGameThread() || !IsValid(Component) || !IsValid(Component->GetOwner()))
    { return TEXT("{\"error\":\"inspection requires an owned component on the editor game thread\"}"); }
    ADynamicMeshActor* Owner = Cast<ADynamicMeshActor>(Component->GetOwner());
    if (!Owner || Owner->GetDynamicMeshComponent() != Component)
    { return TEXT("{\"error\":\"inspection requires the accepted actor's own dynamic mesh component\"}"); }
    const FString Map = Owner->GetOutermost()->GetName();
    if ((Map != TEXT("/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview")
         && Map != TEXT("/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"))
        || !Owner->GetActorTransform().Equals(FTransform::Identity, 0.0)
        || !Component->GetComponentTransform().Equals(FTransform::Identity, 0.0))
    { return TEXT("{\"error\":\"inspection is outside the accepted map or identity transform\"}"); }
    bool bRoad = false;
    const FString Label = Owner->GetActorLabel();
    if (!IsAcceptedLabel(Label, bRoad) || !IsValid(Component->GetDynamicMesh()))
    { return TEXT("{\"error\":\"inspection requires the accepted road or support owner\"}"); }
    UDynamicMesh* Mesh = Component->GetDynamicMesh();
    return InspectNative(Mesh->GetMeshRef(), bRoad, WitnessTriangleCount, Label,
        Component->GetPathName(), Mesh->GetPathName(), Map);
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FYacsRoadMaterialInspectionTest,
    "CyclingPhysics.World.RoadMaterialReadOnlyInspection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FYacsRoadMaterialInspectionTest::RunTest(const FString& Parameters)
{
    FHashRecord Encoding;
    Encoding.Integer(0x01020304); Encoding.Number(1.0); Encoding.Boolean(true);
    const uint8 ExpectedEncoding[] = {4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 240, 63, 1};
    TestEqual(TEXT("Versioned scalar encoding length"), Encoding.Count, static_cast<int32>(sizeof(ExpectedEncoding)));
    TestTrue(TEXT("Versioned scalar encoding is int32/f64 little-endian and one-byte bool"),
        FMemory::Memcmp(Encoding.Bytes, ExpectedEncoding, sizeof(ExpectedEncoding)) == 0);
    FDynamicMesh3 Mesh;
    Mesh.AppendVertex(FVector3d(0, 0, 0)); Mesh.AppendVertex(FVector3d(10, 0, 0));
    Mesh.AppendVertex(FVector3d(0, 10, 0));
    Mesh.AppendTriangle(0, 1, 2);
    Mesh.EnableAttributes(); Mesh.Attributes()->EnableMaterialID();
    Mesh.Attributes()->GetMaterialID()->SetValue(0, 0);
    auto* Normals = Mesh.Attributes()->PrimaryNormals();
    auto* UV = Mesh.Attributes()->PrimaryUV();
    if (!TestTrue(TEXT("Synthetic corner attributes exist"), Normals != nullptr && UV != nullptr)) { return false; }
    const int32 N0 = Normals->AppendElement(FVector3f(0, 0, 1));
    const int32 N1 = Normals->AppendElement(FVector3f(0, 0, 1));
    const int32 N2 = Normals->AppendElement(FVector3f(0, 0, 1));
    Normals->SetTriangle(0, FIndex3i(N0, N1, N2));
    const int32 U0 = UV->AppendElement(FVector2f(0, 0));
    const int32 U1 = UV->AppendElement(FVector2f(1, 0));
    const int32 U2 = UV->AppendElement(FVector2f(0, 1));
    UV->SetTriangle(0, FIndex3i(U0, U1, U2));
    const auto Read = [&Mesh](int32 Count)
    {
        TSharedPtr<FJsonObject> Report;
        const auto Reader = TJsonReaderFactory<>::Create(InspectNative(Mesh, false, Count,
            TEXT("synthetic"), TEXT("component"), TEXT("mesh"), TEXT("map")));
        FJsonSerializer::Deserialize(Reader, Report);
        return Report;
    };
    const auto Before = Read(1);
    if (!TestTrue(TEXT("Complete native snapshot"), Before.IsValid() && !Before->HasField(TEXT("error")))) { return false; }
    const auto Summary = Before->GetObjectField(TEXT("summary"));
    TestEqual(TEXT("Ordered witness contains triangle, vertex IDs and actual coordinates"),
        Before->GetArrayField(TEXT("witness_triangles"))[0]->AsArray().Num(), 13);
    TestFalse(TEXT("Query declares no mutation"), Before->GetBoolField(TEXT("geometry_mutated")));
    TestTrue(TEXT("Actual coordinates survive the read"), Mesh.GetVertex(1) == FVector3d(10, 0, 0));
    TestTrue(TEXT("Actual topology survives the read"), Mesh.GetTriangle(0) == FIndex3i(0, 1, 2));
    const auto Same = Read(0)->GetObjectField(TEXT("summary"));
    for (const TCHAR* Key : {TEXT("positions_indices_blake3"), TEXT("triangle_corner_normals_uv_blake3"), TEXT("material_ids_blake3")})
    {
        TestEqual(TEXT("Full 256-bit digest"), Summary->GetStringField(Key).Len(), 64);
        TestEqual(TEXT("Witness mode cannot change the hashed buffers"), Summary->GetStringField(Key), Same->GetStringField(Key));
    }
    Mesh.SetVertex(1, FVector3d(11, 0, 0));
    TestNotEqual(TEXT("Position change is detected"), Read(0)->GetObjectField(TEXT("summary"))->GetStringField(TEXT("positions_indices_blake3")), Summary->GetStringField(TEXT("positions_indices_blake3")));
    Mesh.SetVertex(1, FVector3d(10, 0, 0));
    Normals->SetElement(N0, FVector3f(1, 0, 0));
    TestNotEqual(TEXT("Split normal change is detected"), Read(0)->GetObjectField(TEXT("summary"))->GetStringField(TEXT("triangle_corner_normals_uv_blake3")), Summary->GetStringField(TEXT("triangle_corner_normals_uv_blake3")));
    Normals->SetElement(N0, FVector3f(0, 0, 1));
    UV->SetElement(U0, FVector2f(0.5, 0));
    TestNotEqual(TEXT("UV change is detected"), Read(0)->GetObjectField(TEXT("summary"))->GetStringField(TEXT("triangle_corner_normals_uv_blake3")), Summary->GetStringField(TEXT("triangle_corner_normals_uv_blake3")));
    UV->SetElement(U0, FVector2f(0, 0));
    Mesh.Attributes()->GetMaterialID()->SetValue(0, 1);
    const auto Reassigned = Read(0)->GetObjectField(TEXT("summary"));
    TestNotEqual(TEXT("Material ID change is detected"), Reassigned->GetStringField(TEXT("material_ids_blake3")), Summary->GetStringField(TEXT("material_ids_blake3")));
    TestEqual(TEXT("Material ID does not alter geometry hash"), Reassigned->GetStringField(TEXT("positions_indices_blake3")), Summary->GetStringField(TEXT("positions_indices_blake3")));
    TestEqual(TEXT("Material ID does not alter corner hash"), Reassigned->GetStringField(TEXT("triangle_corner_normals_uv_blake3")), Summary->GetStringField(TEXT("triangle_corner_normals_uv_blake3")));
    Mesh.Attributes()->SetNumUVLayers(0);
    TestEqual(TEXT("Existing support meshes with no UV layers are accepted"),
        Read(0)->GetObjectField(TEXT("summary"))->GetIntegerField(TEXT("uv_set_count")), 0);
    TestTrue(TEXT("A small fixture cannot impersonate the exact accepted road"),
        InspectNative(Mesh, true, 0, TEXT("road"), TEXT("component"), TEXT("mesh"), TEXT("map")).Contains(TEXT("error")));
    FDynamicMesh3 Sparse;
    Sparse.AppendVertex(FVector3d(0, 0, 0)); Sparse.AppendVertex(FVector3d(10, 0, 0)); Sparse.AppendVertex(FVector3d(0, 10, 0));
    Sparse.InsertTriangle(2, FIndex3i(0, 1, 2), 0, false);
    TestTrue(TEXT("Sparse source triangle IDs are rejected before hashing"),
        InspectNative(Sparse, false, 0, TEXT("support"), TEXT("component"), TEXT("mesh"), TEXT("map")).Contains(TEXT("sparse")));
    TestTrue(TEXT("Out-of-range witnesses are rejected"), Read(2)->HasField(TEXT("error")));
    TestTrue(TEXT("Negative witnesses are rejected"), Read(-1)->HasField(TEXT("error")));
    TestTrue(TEXT("Missing native component is rejected"), UYacsRoadMaterialInspectionLibrary::InspectMesh(nullptr, 0).Contains(TEXT("error")));
    bool bRoad = false;
    TestFalse(TEXT("Foreign label is rejected"), IsAcceptedLabel(TEXT("YACS_PERSIST_SUPPORT_186"), bRoad));
    TestFalse(TEXT("Non-numeric label is rejected"), IsAcceptedLabel(TEXT("YACS_PERSIST_SUPPORT_01x"), bRoad));
    TestTrue(TEXT("Last accepted support label"), IsAcceptedLabel(TEXT("YACS_PERSIST_SUPPORT_185"), bRoad) && !bRoad);
    return true;
}
#endif
