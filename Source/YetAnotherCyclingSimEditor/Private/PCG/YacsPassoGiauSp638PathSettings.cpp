#include "PCG/YacsPassoGiauSp638PathSettings.h"

#include "Data/PCGPointData.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformCrt.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PCGContext.h"
#include "PCGData.h"
#include "PCGPin.h"
#include "PCGPoint.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#define LOCTEXT_NAMESPACE "YacsPassoGiauSp638Path"

namespace
{
    constexpr TCHAR OutputPinName[] = TEXT("Path");

    bool TryReadCoordinate(
        const TSharedPtr<FJsonObject>& JsonPoint,
        const TCHAR* Field,
        double& OutValue)
    {
        if (!JsonPoint.IsValid() || !JsonPoint->TryGetNumberField(Field, OutValue))
        {
            return false;
        }
        return FMath::IsFinite(OutValue);
    }
}

FName UYacsPassoGiauSp638PathSettings::GetDefaultNodeName() const
{
    return FName(TEXT("YacsPassoGiauSp638Path"));
}

FText UYacsPassoGiauSp638PathSettings::GetDefaultNodeTitle() const
{
    return LOCTEXT("NodeTitle", "YACS SP638 Presentation Path");
}

FText UYacsPassoGiauSp638PathSettings::GetNodeTooltipText() const
{
    return LOCTEXT(
        "NodeTooltip",
        "Loads ordered presentation-only SP638 points prepared from the official Veneto source. "
        "This node is never route or physics authority.");
}

EPCGSettingsType UYacsPassoGiauSp638PathSettings::GetType() const
{
    return EPCGSettingsType::InputOutput;
}

TArray<FPCGPinProperties> UYacsPassoGiauSp638PathSettings::InputPinProperties() const
{
    return {};
}

TArray<FPCGPinProperties> UYacsPassoGiauSp638PathSettings::OutputPinProperties() const
{
    return {
        FPCGPinProperties(
            FName(OutputPinName),
            FPCGDataTypeIdentifier(EPCGDataType::Point),
            false,
            true,
            LOCTEXT("OutputPinTooltip", "Ordered SP638 presentation points in local Unreal centimetres."))
    };
}

FPCGElementPtr UYacsPassoGiauSp638PathSettings::CreateElement() const
{
    return MakeShared<FYacsPassoGiauSp638PathElement>();
}

bool FYacsPassoGiauSp638PathElement::ExecuteInternal(FPCGContext* Context) const
{
    check(Context);

    const UYacsPassoGiauSp638PathSettings* Settings =
        Context->GetInputSettings<UYacsPassoGiauSp638PathSettings>();
    if (!Settings)
    {
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    FString JsonPath = Settings->RoadJsonRelativePath;
    if (FPaths::IsRelative(JsonPath))
    {
        JsonPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), JsonPath);
    }

    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *JsonPath))
    {
        UE_LOG(LogTemp, Error, TEXT("YACS SP638 PCG source: failed to read '%s'."), *JsonPath);
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("YACS SP638 PCG source: invalid JSON '%s'."), *JsonPath);
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    const TSharedPtr<FJsonObject>* Policy = nullptr;
    if (!Root->TryGetObjectField(TEXT("yacs_policy"), Policy)
        || !Policy
        || !Policy->IsValid()
        || !(*Policy)->GetBoolField(TEXT("presentation_only"))
        || (*Policy)->GetBoolField(TEXT("authoritative_route_geometry"))
        || (*Policy)->GetBoolField(TEXT("authoritative_physics")))
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("YACS SP638 PCG source: JSON policy does not prove presentation-only authority separation."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    const TCHAR* ArrayField =
        Settings->bUseSplineControlPoints ? TEXT("spline_points") : TEXT("points");
    const TArray<TSharedPtr<FJsonValue>>* JsonPoints = nullptr;
    if (!Root->TryGetArrayField(ArrayField, JsonPoints) || !JsonPoints || JsonPoints->Num() < 2)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("YACS SP638 PCG source: '%s' is missing or contains fewer than two points."),
            ArrayField);
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    TArray<FPCGPoint> Points;
    Points.Reserve(JsonPoints->Num());

    for (int32 Index = 0; Index < JsonPoints->Num(); ++Index)
    {
        const TSharedPtr<FJsonObject> PointObject = (*JsonPoints)[Index]->AsObject();
        double X = 0.0;
        double Y = 0.0;
        double Z = 0.0;
        if (!TryReadCoordinate(PointObject, TEXT("ue_x_cm"), X)
            || !TryReadCoordinate(PointObject, TEXT("ue_y_cm"), Y)
            || !TryReadCoordinate(PointObject, TEXT("ue_z_cm"), Z))
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("YACS SP638 PCG source: invalid UE coordinate at point %d."),
                Index);
            Context->OutputData.bCancelExecution = true;
            return true;
        }

        FPCGPoint Point(FTransform(FVector(X, Y, Z)), 1.0f, Index);
        Point.SetExtents(FVector(1.0));
        Points.Add(MoveTemp(Point));
    }

    UPCGPointData* OutputData = NewObject<UPCGPointData>();
    OutputData->SetPoints(Points);

    FPCGTaggedData& TaggedOutput = Context->OutputData.TaggedData.Emplace_GetRef();
    TaggedOutput.Pin = FName(OutputPinName);
    TaggedOutput.Data = OutputData;
    TaggedOutput.Tags.Add(TEXT("YACS.SP638.PresentationOnly"));
    TaggedOutput.Tags.Add(TEXT("YACS.Source.RegioneDelVeneto"));

    UE_LOG(
        LogTemp,
        Display,
        TEXT("YACS SP638 PCG source: emitted %d presentation points from %s."),
        Points.Num(),
        *JsonPath);
    return true;
}

#undef LOCTEXT_NAMESPACE
