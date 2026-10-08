#include "Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h"
#include "Landscape.h"
#include "LandscapeComponent.h"
#include "LandscapeDataAccess.h"
#include "LandscapeInfo.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
constexpr int32 TrialQuads = 126;
constexpr int32 TrialSize = TrialQuads + 1;
const FName TrialTag(TEXT("YACS_Component230_TerrainTrial"));

bool ValidTrialSource(ULandscapeComponent* Component)
{
    return IsValid(Component) && Component->ComponentSizeQuads == TrialQuads &&
        Component->GetLandscapeProxy() && !Component->GetLandscapeProxy()->HasNaniteComponents() &&
        Component->GetComponentTransform().GetRotation().Equals(FQuat::Identity, 1.e-6) &&
        FMath::IsNearlyEqual(Component->GetComponentTransform().GetScale3D().X, 50.0) &&
        FMath::IsNearlyEqual(Component->GetComponentTransform().GetScale3D().Y, 50.0) &&
        Component->GetComponentTransform().GetScale3D().Z > 0 &&
        (Component->GetName() == TEXT("LandscapeComponent_230") ||
         Component->GetOwner()->ActorHasTag(TrialTag));
}
}

FString UYacsLandscapeMeshDiagnosticLibrary::ReadComponent230Heightfield(ULandscapeComponent* Component)
{
    if (!ValidTrialSource(Component)) { return TEXT("{\"error\":\"unsupported terrain trial component\"}"); }
    FLandscapeComponentDataInterface Data(Component, 0, false);
    TArray<TSharedPtr<FJsonValue>> Heights;
    for (int32 Y = 0; Y < TrialSize; ++Y)
    {
        for (int32 X = 0; X < TrialSize; ++X)
        {
            Heights.Add(MakeShared<FJsonValueNumber>(Data.GetHeight(X, Y)));
        }
    }
    const FVector Origin = Data.GetWorldVertex(0, 0);
    TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
    Report->SetNumberField(TEXT("size"), TrialSize);
    Report->SetNumberField(TEXT("origin_col"), FMath::RoundToInt(Origin.X / 50.0));
    Report->SetNumberField(TEXT("origin_row"), FMath::RoundToInt(Origin.Y / 50.0));
    Report->SetNumberField(TEXT("height_unit_cm"), Component->GetComponentTransform().GetScale3D().Z / 128.0);
    Report->SetArrayField(TEXT("heights"), Heights);
    FString Result;
    FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Result));
    return Result;
}

ALandscape* UYacsLandscapeMeshDiagnosticLibrary::CreateComponent230TerrainTrial(
    ULandscapeComponent* Component, const FString& CandidateJson, const FString& PlanJson)
{
    if (!ValidTrialSource(Component) || Component->GetName() != TEXT("LandscapeComponent_230")) { return nullptr; }
    TSharedPtr<FJsonObject> Candidate, Plan;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(CandidateJson), Candidate) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(PlanJson), Plan) ||
        !Candidate.IsValid() || !Plan.IsValid()) { return nullptr; }
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Cells = nullptr;
    if (!Candidate->TryGetArrayField(TEXT("heights"), Values) || Values->Num() != TrialSize * TrialSize ||
        !Plan->TryGetArrayField(TEXT("skin_cells"), Cells) || Cells->Num() != 1017) { return nullptr; }
    const bool bRoundingDomain = Plan->HasField(TEXT("terrain_rounding_domain")) &&
        Plan->GetBoolField(TEXT("terrain_rounding_domain"));
    if (bRoundingDomain)
    {
        const TSharedPtr<FJsonObject>* Contract = nullptr;
        if (!Plan->TryGetObjectField(TEXT("rounding_domain_contract"), Contract) ||
            (*Contract)->GetStringField(TEXT("method")) != TEXT("source-cliff-six-metre-crown-apron-v1") ||
            (*Contract)->GetNumberField(TEXT("radius_m")) != 6 ||
            !(*Contract)->GetBoolField(TEXT("classifier_unchanged")) ||
            (*Contract)->GetNumberField(TEXT("hard_protected_samples")) != 0 ||
            !Plan->TryGetArrayField(TEXT("rounding_cells"), Cells) ||
            Cells->Num() < 1017 || Cells->Num() > 3969 ||
            (*Contract)->GetNumberField(TEXT("cell_count")) != Cells->Num()) { return nullptr; }
    }
    TSet<FIntPoint> Allowed;
    for (const auto& Value : *Cells)
    {
        const TSharedPtr<FJsonObject>* Cell = nullptr;
        double R0, R1, C0, C1, Protected;
        if (!Value->TryGetObject(Cell) || !(*Cell)->TryGetNumberField(TEXT("row0"), R0) ||
            !(*Cell)->TryGetNumberField(TEXT("row1"), R1) || !(*Cell)->TryGetNumberField(TEXT("col0"), C0) ||
            !(*Cell)->TryGetNumberField(TEXT("col1"), C1) || !(*Cell)->TryGetNumberField(TEXT("protected_samples"), Protected) ||
            Protected != 0 || R1 - R0 != 2 || C1 - C0 != 2 || R0 < 882 || R1 > 1008 ||
            C0 < 756 || C1 > 882 || R0 != FMath::FloorToDouble(R0) || C0 != FMath::FloorToDouble(C0)) { return nullptr; }
        for (int32 R = int32(R0); R < int32(R1); ++R)
            for (int32 C = int32(C0); C < int32(C1); ++C) { Allowed.Add(FIntPoint(C, R)); }
    }
    if (Allowed.Num() != Cells->Num() * 4) { return nullptr; }
    if (bRoundingDomain)
    {
        // Crown movement is a separate presentation domain, not a replacement
        // for the original cliff selector. It must contain every original cell.
        const auto& OriginalCells = Plan->GetArrayField(TEXT("skin_cells"));
        for (const auto& Value : OriginalCells)
        {
            const auto Cell = Value->AsObject();
            if (!Cell.IsValid()) { return nullptr; }
            const int32 R0 = int32(Cell->GetNumberField(TEXT("row0")));
            const int32 C0 = int32(Cell->GetNumberField(TEXT("col0")));
            for (int32 R = R0; R < R0 + 2; ++R)
                for (int32 C = C0; C < C0 + 2; ++C)
                    if (!Allowed.Contains(FIntPoint(C, R))) { return nullptr; }
        }
    }
    FLandscapeComponentDataInterface Source(Component, 0, false);
    const double Unit = Component->GetComponentTransform().GetScale3D().Z / 128.0;
    TArray<uint16> Heights;
    int32 Changed = 0;
    for (int32 Y = 0; Y < TrialSize; ++Y)
    {
        for (int32 X = 0; X < TrialSize; ++X)
        {
            double Value;
            if (!(*Values)[Y * TrialSize + X]->TryGetNumber(Value) || !FMath::IsFinite(Value) ||
                Value < 0 || Value > 65535 || Value != FMath::FloorToDouble(Value)) { return nullptr; }
            const int32 Delta = int32(Value) - int32(Source.GetHeight(X, Y));
            if (FMath::Abs(Delta * Unit) > 150.000001) { return nullptr; }
            if (Delta != 0)
            {
                const FVector P = Source.GetWorldVertex(X, Y);
                const FIntPoint Grid(FMath::RoundToInt(P.X / 50.0), FMath::RoundToInt(P.Y / 50.0));
                if (X == 0 || Y == 0 || X == TrialQuads || Y == TrialQuads ||
                    !Allowed.Contains(Grid) || !Allowed.Contains(Grid - FIntPoint(1, 0)) ||
                    !Allowed.Contains(Grid - FIntPoint(0, 1)) || !Allowed.Contains(Grid - FIntPoint(1, 1))) { return nullptr; }
                ++Changed;
            }
            Heights.Add(uint16(Value));
        }
    }
    if (Changed == 0) { return nullptr; }
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ALandscape* Trial = Component->GetWorld()->SpawnActor<ALandscape>(ALandscape::StaticClass(),
        FTransform::Identity, Spawn);
    if (!Trial) { return nullptr; }
    // Spawn combines the supplied scale with Landscape's default root scale.
    // Set the exact transform afterwards, as the native terrain importer does.
    Trial->SetActorTransform(Component->GetComponentTransform());
    Trial->Tags.Add(TrialTag);
    Trial->SetActorLabel(TEXT("YACS Component230 DTM thermal erosion trial (unsaved)"));
    Trial->LandscapeMaterial = Component->OverrideMaterial;
    TMap<FGuid, TArray<uint16>> HeightLayers;
    HeightLayers.Add(FGuid(), Heights);
    TMap<FGuid, TArray<FLandscapeImportLayerInfo>> MaterialLayers;
    MaterialLayers.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());
    Trial->Import(FGuid::NewGuid(), 0, 0, TrialQuads, TrialQuads,
        Component->NumSubsections, Component->SubsectionSizeQuads, HeightLayers,
        TEXT(""), MaterialLayers, ELandscapeImportAlphamapType::Additive,
        TArrayView<const FLandscapeLayer>());
    Trial->RegisterAllComponents();
    Trial->PostEditChange();
    // UE 5.8 automatically creates edit layers at registration. Complete their
    // composite/readback before checking the imported native height samples.
    Trial->ForceLayersFullUpdate();
    Trial->SetActorEnableCollision(false);
    if (Trial->LandscapeComponents.Num() != 1) { Trial->Destroy(); return nullptr; }
    ULandscapeComponent* Result = Trial->LandscapeComponents[0];
    Result->SetForcedLOD(0);
    Result->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    FLandscapeComponentDataInterface Actual(Result, 0, false);
    for (int32 Y = 0; Y < TrialSize; ++Y)
    {
        for (int32 X = 0; X < TrialSize; ++X)
        {
            const int32 Index = Y * TrialSize + X;
            FVector Expected = Source.GetWorldVertex(X, Y);
            Expected.Z += (int32(Heights[Index]) - int32(Source.GetHeight(X, Y))) * Unit;
            if (Actual.GetHeight(X, Y) != Heights[Index] ||
                FVector::Distance(Actual.GetWorldVertex(X, Y), Expected) > 0.01)
            {
                UE_LOG(LogTemp, Error, TEXT("YACS terrain trial readback (%d,%d): height %u expected %u, world %s expected %s"),
                    X, Y, uint32(Actual.GetHeight(X, Y)), uint32(Heights[Index]),
                    *Actual.GetWorldVertex(X, Y).ToString(), *Expected.ToString());
                Trial->Destroy();
                return nullptr;
            }
        }
    }
    return Trial;
}
