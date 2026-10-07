#include "PCG/YacsSaCalobraCliffCellsSettings.h"

#include "Data/PCGPointData.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PCGContext.h"
#include "PCGData.h"
#include "PCGPin.h"
#include "PCGPoint.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#if YACS_WITH_PCGEX
#include "Paths/PCGExPathsHelpers.h"
#endif

#define LOCTEXT_NAMESPACE "YacsSaCalobraCliffCells"

namespace
{
    constexpr TCHAR OutputPinName[] = TEXT("Paths");
    constexpr double SourcePixelSizeCm = 50.0;

    bool ReadIntegralField(
        const TSharedPtr<FJsonObject>& Object,
        const TCHAR* Name,
        int32& OutValue)
    {
        double Value = 0.0;
        if (!Object.IsValid() || !Object->TryGetNumberField(Name, Value))
        {
            return false;
        }
        const double Rounded = FMath::RoundToDouble(Value);
        if (!FMath::IsNearlyEqual(Value, Rounded, UE_DOUBLE_SMALL_NUMBER))
        {
            return false;
        }
        OutValue = static_cast<int32>(Rounded);
        return true;
    }
}

FName UYacsSaCalobraCliffCellsSettings::GetDefaultNodeName() const
{
    return FName(TEXT("YacsSaCalobraCliffCells"));
}

FText UYacsSaCalobraCliffCellsSettings::GetDefaultNodeTitle() const
{
    return LOCTEXT("NodeTitle", "YACS Sa Calobra Cliff Cells");
}

FText UYacsSaCalobraCliffCellsSettings::GetNodeTooltipText() const
{
    return LOCTEXT(
        "NodeTooltip",
        "Emits closed presentation-only 1 m cell paths from the frozen Component_230 "
        "cliff plan. Classification and hard exclusions remain YACS authority.");
}

EPCGSettingsType UYacsSaCalobraCliffCellsSettings::GetType() const
{
    return EPCGSettingsType::InputOutput;
}

TArray<FPCGPinProperties> UYacsSaCalobraCliffCellsSettings::InputPinProperties() const
{
    return {};
}

TArray<FPCGPinProperties> UYacsSaCalobraCliffCellsSettings::OutputPinProperties() const
{
    return {
        FPCGPinProperties(
            FName(OutputPinName),
            FPCGDataTypeIdentifier(EPCGDataType::Point),
            false,
            true,
            LOCTEXT(
                "OutputPinTooltip",
                "One closed four-point path per admitted Component_230 skin cell."))
    };
}

FPCGElementPtr UYacsSaCalobraCliffCellsSettings::CreateElement() const
{
    return MakeShared<FYacsSaCalobraCliffCellsElement>();
}

bool FYacsSaCalobraCliffCellsElement::ExecuteInternal(FPCGContext* Context) const
{
    check(Context);

#if !YACS_WITH_PCGEX
    UE_LOG(
        LogTemp,
        Error,
        TEXT("YACS Sa Calobra cliff cells require the pinned PCGEx authoring checkout."));
    Context->OutputData.bCancelExecution = true;
    return true;
#else
    const UYacsSaCalobraCliffCellsSettings* Settings =
        Context->GetInputSettings<UYacsSaCalobraCliffCellsSettings>();
    if (!Settings || Settings->PlanJsonPath.IsEmpty())
    {
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    FString JsonPath = Settings->PlanJsonPath;
    if (FPaths::IsRelative(JsonPath))
    {
        JsonPath = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), JsonPath);
    }

    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *JsonPath))
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: failed to read '%s'."), *JsonPath);
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: invalid plan JSON '%s'."), *JsonPath);
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    if (Root->GetStringField(TEXT("status")) != TEXT("COMPONENT230_CLIFF_VISUAL_PLAN")
        || Root->GetBoolField(TEXT("canonical_landscape_mutation"))
        || Root->GetBoolField(TEXT("selector_policy_mutation")))
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: plan authority contract failed."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    const TSharedPtr<FJsonObject>* Counts = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Cells = nullptr;
    if (!Root->TryGetObjectField(TEXT("counts"), Counts)
        || !Counts
        || !Counts->IsValid()
        || !Root->TryGetArrayField(TEXT("skin_cells"), Cells)
        || !Cells)
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: plan counts/skin_cells are missing."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    const int32 ExpectedCellCount =
        static_cast<int32>((*Counts)->GetNumberField(TEXT("skin_cell_count")));
    if (ExpectedCellCount != Cells->Num()
        || static_cast<int32>((*Counts)->GetNumberField(TEXT("component_cliff_cells"))) != 2611)
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("YACS cliff cells: frozen Component_230 count contract drifted."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    int32 EmittedPaths = 0;
    for (int32 CellIndex = 0; CellIndex < Cells->Num(); ++CellIndex)
    {
        const TSharedPtr<FJsonObject> Cell = (*Cells)[CellIndex]->AsObject();
        int32 Row0 = 0;
        int32 Row1 = 0;
        int32 Col0 = 0;
        int32 Col1 = 0;
        if (!ReadIntegralField(Cell, TEXT("row0"), Row0)
            || !ReadIntegralField(Cell, TEXT("row1"), Row1)
            || !ReadIntegralField(Cell, TEXT("col0"), Col0)
            || !ReadIntegralField(Cell, TEXT("col1"), Col1)
            || Row1 <= Row0
            || Col1 <= Col0)
        {
            UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: invalid cell %d."), CellIndex);
            Context->OutputData.bCancelExecution = true;
            return true;
        }

        const FString ClusterId = Cell->GetStringField(TEXT("cluster_id"));
        if (ClusterId.IsEmpty())
        {
            Context->OutputData.bCancelExecution = true;
            return true;
        }

        const double X0 = Col0 * SourcePixelSizeCm;
        const double X1 = Col1 * SourcePixelSizeCm;
        const double Y0 = Row0 * SourcePixelSizeCm;
        const double Y1 = Row1 * SourcePixelSizeCm;

        TArray<FPCGPoint> Points;
        Points.Reserve(4);
        const FVector Locations[] = {
            FVector(X0, Y0, 0.0),
            FVector(X1, Y0, 0.0),
            FVector(X1, Y1, 0.0),
            FVector(X0, Y1, 0.0),
        };
        for (int32 CornerIndex = 0; CornerIndex < 4; ++CornerIndex)
        {
            FPCGPoint Point(
                FTransform(Locations[CornerIndex]),
                1.0f,
                CellIndex * 4 + CornerIndex);
            Point.SetExtents(FVector(1.0));
            Points.Add(MoveTemp(Point));
        }

        UPCGPointData* OutputData = NewObject<UPCGPointData>();
        OutputData->SetPoints(Points);
        PCGExPaths::Helpers::SetClosedLoop(OutputData, true);

        FPCGTaggedData& TaggedOutput = Context->OutputData.TaggedData.Emplace_GetRef();
        TaggedOutput.Pin = FName(OutputPinName);
        TaggedOutput.Data = OutputData;
        TaggedOutput.Tags.Add(TEXT("YACS.Component230.CliffCandidate"));
        TaggedOutput.Tags.Add(FString::Printf(TEXT("YACS.Cluster.%s"), *ClusterId));
        ++EmittedPaths;
    }

    if (EmittedPaths != ExpectedCellCount || EmittedPaths <= 0)
    {
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    UE_LOG(
        LogTemp,
        Display,
        TEXT("YACS cliff cells: emitted %d closed candidate paths for PCGEx."),
        EmittedPaths);
    return true;
#endif
}

#undef LOCTEXT_NAMESPACE
