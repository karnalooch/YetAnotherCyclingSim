#include "PCG/YacsSaCalobraCliffCellsSettings.h"

#include "Data/PCGPointData.h"
#include "Containers/Queue.h"
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
    constexpr TCHAR HolesPinName[] = TEXT("Holes");
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
        if (!FMath::IsNearlyEqual(Value, Rounded, 1.0e-9))
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
                "One closed four-point path per admitted Component_230 skin cell.")),
        FPCGPinProperties(
            FName(HolesPinName),
            FPCGDataTypeIdentifier(EPCGDataType::Point),
            false,
            false,
            LOCTEXT(
                "HolesPinTooltip",
                "One deterministic seed point per enclosed empty region in the "
                "authoritative 1 m cliff-cell footprint."))
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

    const TSharedPtr<FJsonObject>* SkinContract = nullptr;
    int32 GridStepCells = 0;
    if (!Root->TryGetObjectField(TEXT("skin_contract"), SkinContract)
        || !SkinContract
        || !SkinContract->IsValid()
        || !ReadIntegralField(
            *SkinContract,
            TEXT("source_grid_step_cells"),
            GridStepCells)
        || GridStepCells <= 0)
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: invalid source grid contract."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    TSet<FIntPoint> OccupiedCells;
    int32 MinGridRow = MAX_int32;
    int32 MaxGridRow = MIN_int32;
    int32 MinGridCol = MAX_int32;
    int32 MaxGridCol = MIN_int32;

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

        if ((Row1 - Row0) != GridStepCells
            || (Col1 - Col0) != GridStepCells
            || (Row0 % GridStepCells) != 0
            || (Col0 % GridStepCells) != 0)
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("YACS cliff cells: cell %d is not aligned to the frozen coarse grid."),
                CellIndex);
            Context->OutputData.bCancelExecution = true;
            return true;
        }

        const int32 GridRow = Row0 / GridStepCells;
        const int32 GridCol = Col0 / GridStepCells;
        const FIntPoint GridCell(GridCol, GridRow);
        if (OccupiedCells.Contains(GridCell))
        {
            UE_LOG(
                LogTemp,
                Error,
                TEXT("YACS cliff cells: duplicate coarse cell %d."),
                CellIndex);
            Context->OutputData.bCancelExecution = true;
            return true;
        }
        OccupiedCells.Add(GridCell);
        MinGridRow = FMath::Min(MinGridRow, GridRow);
        MaxGridRow = FMath::Max(MaxGridRow, GridRow);
        MinGridCol = FMath::Min(MinGridCol, GridCol);
        MaxGridCol = FMath::Max(MaxGridCol, GridCol);

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

    // Find topological holes in the authoritative 1 m occupancy grid. Pad the
    // bounds by one cell, flood-fill empty cells reachable from that exterior,
    // then each remaining 4-connected empty component is a real enclosed hole.
    // One cell-centre seed per hole is enough for PCGEx Cluster Surface's
    // "Holes" contract and cannot relax the admitted YACS footprint.
    const int32 FloodMinRow = MinGridRow - 1;
    const int32 FloodMaxRow = MaxGridRow + 1;
    const int32 FloodMinCol = MinGridCol - 1;
    const int32 FloodMaxCol = MaxGridCol + 1;

    auto IsWithinFloodBounds =
        [FloodMinRow, FloodMaxRow, FloodMinCol, FloodMaxCol](
            const FIntPoint& Cell)
        {
            return Cell.Y >= FloodMinRow
                && Cell.Y <= FloodMaxRow
                && Cell.X >= FloodMinCol
                && Cell.X <= FloodMaxCol;
        };

    const FIntPoint Neighbours[] = {
        FIntPoint(1, 0),
        FIntPoint(-1, 0),
        FIntPoint(0, 1),
        FIntPoint(0, -1),
    };

    TSet<FIntPoint> ExteriorEmpty;
    TQueue<FIntPoint> ExteriorQueue;
    auto EnqueueExterior =
        [&OccupiedCells, &ExteriorEmpty, &ExteriorQueue](
            const FIntPoint& Cell)
        {
            if (!OccupiedCells.Contains(Cell)
                && !ExteriorEmpty.Contains(Cell))
            {
                ExteriorEmpty.Add(Cell);
                ExteriorQueue.Enqueue(Cell);
            }
        };

    for (int32 Col = FloodMinCol; Col <= FloodMaxCol; ++Col)
    {
        EnqueueExterior(FIntPoint(Col, FloodMinRow));
        EnqueueExterior(FIntPoint(Col, FloodMaxRow));
    }
    for (int32 Row = FloodMinRow; Row <= FloodMaxRow; ++Row)
    {
        EnqueueExterior(FIntPoint(FloodMinCol, Row));
        EnqueueExterior(FIntPoint(FloodMaxCol, Row));
    }

    FIntPoint Current;
    while (ExteriorQueue.Dequeue(Current))
    {
        for (const FIntPoint& Offset : Neighbours)
        {
            const FIntPoint Next = Current + Offset;
            if (IsWithinFloodBounds(Next))
            {
                EnqueueExterior(Next);
            }
        }
    }

    TSet<FIntPoint> VisitedHoles;
    TArray<FPCGPoint> HolePoints;
    for (int32 Row = MinGridRow; Row <= MaxGridRow; ++Row)
    {
        for (int32 Col = MinGridCol; Col <= MaxGridCol; ++Col)
        {
            const FIntPoint Start(Col, Row);
            if (OccupiedCells.Contains(Start)
                || ExteriorEmpty.Contains(Start)
                || VisitedHoles.Contains(Start))
            {
                continue;
            }

            TQueue<FIntPoint> HoleQueue;
            HoleQueue.Enqueue(Start);
            VisitedHoles.Add(Start);

            // Row-major scan makes Start a deterministic representative cell.
            while (HoleQueue.Dequeue(Current))
            {
                for (const FIntPoint& Offset : Neighbours)
                {
                    const FIntPoint Next = Current + Offset;
                    if (!IsWithinFloodBounds(Next)
                        || OccupiedCells.Contains(Next)
                        || ExteriorEmpty.Contains(Next)
                        || VisitedHoles.Contains(Next))
                    {
                        continue;
                    }
                    VisitedHoles.Add(Next);
                    HoleQueue.Enqueue(Next);
                }
            }

            const double CenterX =
                (static_cast<double>(Start.X * GridStepCells)
                    + static_cast<double>(GridStepCells) * 0.5)
                * SourcePixelSizeCm;
            const double CenterY =
                (static_cast<double>(Start.Y * GridStepCells)
                    + static_cast<double>(GridStepCells) * 0.5)
                * SourcePixelSizeCm;

            FPCGPoint HolePoint(
                FTransform(FVector(CenterX, CenterY, 0.0)),
                1.0f,
                1000000 + HolePoints.Num());
            HolePoint.SetExtents(FVector(1.0));
            HolePoints.Add(MoveTemp(HolePoint));
        }
    }

    if (HolePoints.IsEmpty())
    {
        UE_LOG(LogTemp, Error, TEXT("YACS cliff cells: authoritative footprint unexpectedly has no holes."));
        Context->OutputData.bCancelExecution = true;
        return true;
    }

    UPCGPointData* HolesData = NewObject<UPCGPointData>();
    HolesData->SetPoints(HolePoints);
    FPCGTaggedData& HolesOutput = Context->OutputData.TaggedData.Emplace_GetRef();
    HolesOutput.Pin = FName(HolesPinName);
    HolesOutput.Data = HolesData;
    HolesOutput.Tags.Add(TEXT("YACS.Component230.AuthoritativeHoleSeeds"));

    UE_LOG(
        LogTemp,
        Display,
        TEXT("YACS cliff cells: emitted %d closed candidate paths and %d authoritative hole seeds for PCGEx."),
        EmittedPaths,
        HolePoints.Num());
    return true;
#endif
}

#undef LOCTEXT_NAMESPACE
