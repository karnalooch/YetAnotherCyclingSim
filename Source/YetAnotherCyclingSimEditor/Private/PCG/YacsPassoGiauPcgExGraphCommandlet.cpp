#include "PCG/YacsPassoGiauPcgExGraphCommandlet.h"

#include "PCG/YacsPassoGiauSp638PathSettings.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Data/PCGPointData.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "FileHelpers.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "PCGComponent.h"
#include "PCGData.h"
#include "PCGGraph.h"
#include "PCGNode.h"
#include "PCGPin.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "WorldPartition/WorldPartitionHelpers.h"

#if YACS_WITH_PCGEX
#include "Elements/PCGExOffsetPath.h"
#include "Elements/PCGExPathResample.h"
#include "Elements/PCGExSmooth.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogYacsPassoGiauPcgExGraph, Log, All);

namespace
{
    constexpr TCHAR DefaultPackageName[] =
        TEXT("/Game/WorldGen/PCGEx/PCG_PassoGiau_SP638_Corridor");

    bool ExecuteGraphAndWriteProof(
        UPCGGraph* Graph,
        const FString& PackageName,
        const FString& OutputPath,
        const double TimeoutSeconds)
    {
        if (!Graph || OutputPath.IsEmpty())
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCGEx execution: graph or output path is missing."));
            return false;
        }

        UWorld* World = UEditorLoadingAndSavingUtils::NewBlankMap(false);
        if (!World)
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCGEx execution: failed to create a blank editor world."));
            return false;
        }

        FActorSpawnParameters SpawnParameters;
        SpawnParameters.Name = TEXT("YacsPcgExProofHost");
        AActor* Host = World->SpawnActor<AActor>(
            AActor::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            SpawnParameters);
        if (!Host)
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCGEx execution: failed to spawn proof host actor."));
            return false;
        }

        UPCGComponent* Component = NewObject<UPCGComponent>(Host, TEXT("YacsPcgExProofComponent"));
        if (!Component)
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCGEx execution: failed to allocate PCG component."));
            return false;
        }
        Host->AddInstanceComponent(Component);
        Component->RegisterComponent();
        Component->SetGraphLocal(Graph);

        // Execute through stock UE PCG component APIs. Generation is delayed, so
        // pump editor frames using the same helper used by Epic's PCG world builder.
        Component->GenerateLocal(true);
        FWorldPartitionHelpers::FakeEngineTick(World);

        const double StartedAt = FPlatformTime::Seconds();
        while (Component->IsGenerating())
        {
            if ((FPlatformTime::Seconds() - StartedAt) > TimeoutSeconds)
            {
                UE_LOG(
                    LogYacsPassoGiauPcgExGraph,
                    Error,
                    TEXT("PCGEx execution timed out after %.1f seconds."),
                    TimeoutSeconds);
                return false;
            }
            FWorldPartitionHelpers::FakeEngineTick(World);
        }
        FWorldPartitionHelpers::FakeEngineTick(World);

        const FPCGDataCollection& Generated = Component->GetGeneratedGraphOutput();
        TArray<TSharedPtr<FJsonValue>> DatasetValues;
        int32 TotalPointCount = 0;
        int32 PointDatasetCount = 0;

        for (int32 DatasetIndex = 0; DatasetIndex < Generated.TaggedData.Num(); ++DatasetIndex)
        {
            const FPCGTaggedData& Tagged = Generated.TaggedData[DatasetIndex];
            const UPCGPointData* PointData = Cast<const UPCGPointData>(Tagged.Data);
            if (!PointData)
            {
                UE_LOG(
                    LogYacsPassoGiauPcgExGraph,
                    Warning,
                    TEXT("PCGEx execution output %d is not UPCGPointData; skipping it in the point proof."),
                    DatasetIndex);
                continue;
            }

            const TArray<FPCGPoint>& Points = PointData->GetPoints();
            TSharedRef<FJsonObject> DatasetObject = MakeShared<FJsonObject>();
            DatasetObject->SetNumberField(TEXT("source_collection_index"), DatasetIndex);
            DatasetObject->SetNumberField(TEXT("point_count"), Points.Num());

            TArray<TSharedPtr<FJsonValue>> TagValues;
            for (const FString& Tag : Tagged.Tags)
            {
                TagValues.Add(MakeShared<FJsonValueString>(Tag));
            }
            DatasetObject->SetArrayField(TEXT("tags"), MoveTemp(TagValues));

            TArray<TSharedPtr<FJsonValue>> PointValues;
            PointValues.Reserve(Points.Num());
            for (const FPCGPoint& Point : Points)
            {
                const FVector Location = Point.Transform.GetLocation();
                TSharedRef<FJsonObject> PointObject = MakeShared<FJsonObject>();
                PointObject->SetNumberField(TEXT("x_cm"), Location.X);
                PointObject->SetNumberField(TEXT("y_cm"), Location.Y);
                PointObject->SetNumberField(TEXT("z_cm"), Location.Z);
                PointValues.Add(MakeShared<FJsonValueObject>(PointObject));
            }
            DatasetObject->SetArrayField(TEXT("points"), MoveTemp(PointValues));

            TotalPointCount += Points.Num();
            ++PointDatasetCount;
            DatasetValues.Add(MakeShared<FJsonValueObject>(DatasetObject));
        }

        if (PointDatasetCount < 3 || TotalPointCount <= 0)
        {
            UE_LOG(
                LogYacsPassoGiauPcgExGraph,
                Error,
                TEXT("PCGEx execution produced insufficient point output: datasets=%d total_points=%d."),
                PointDatasetCount,
                TotalPointCount);
            return false;
        }

        TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
        Root->SetNumberField(TEXT("schema_version"), 1);
        Root->SetStringField(TEXT("status"), TEXT("PASS"));
        Root->SetStringField(TEXT("graph_package"), PackageName);
        Root->SetNumberField(TEXT("point_dataset_count"), PointDatasetCount);
        Root->SetNumberField(TEXT("total_point_count"), TotalPointCount);
        Root->SetArrayField(TEXT("datasets"), MoveTemp(DatasetValues));

        FString JsonText;
        const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
        if (!FJsonSerializer::Serialize(Root, Writer))
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCGEx execution: failed to serialize output proof."));
            return false;
        }

        IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutputPath), true);
        if (!FFileHelper::SaveStringToFile(JsonText, *OutputPath))
        {
            UE_LOG(
                LogYacsPassoGiauPcgExGraph,
                Error,
                TEXT("PCGEx execution: failed to write output proof to %s."),
                *OutputPath);
            return false;
        }

        UE_LOG(
            LogYacsPassoGiauPcgExGraph,
            Display,
            TEXT("YACS PCGEx corridor graph executed: datasets=%d total_points=%d output=%s"),
            PointDatasetCount,
            TotalPointCount,
            *OutputPath);
        return true;
    }

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
                LogYacsPassoGiauPcgExGraph,
                Error,
                TEXT("PCGEx graph: null node while connecting %s."),
                Description);
            return false;
        }

        Graph->AddLabeledEdge(From, FromPin, To, ToPin);
        UE_LOG(
            LogYacsPassoGiauPcgExGraph,
            Display,
            TEXT("PCGEx graph edge: %s [%s -> %s]."),
            Description,
            *FromPin.ToString(),
            *ToPin.ToString());
        return true;
    }
}

UYacsPassoGiauPcgExGraphCommandlet::UYacsPassoGiauPcgExGraphCommandlet()
{
    IsClient = false;
    IsEditor = true;
    IsServer = false;
    LogToConsole = true;
}

int32 UYacsPassoGiauPcgExGraphCommandlet::Main(const FString& Params)
{
#if !YACS_WITH_PCGEX
    UE_LOG(
        LogYacsPassoGiauPcgExGraph,
        Error,
        TEXT("PCGEx graph authoring requires the pinned Plugins/PCGExtendedToolkit checkout. "
             "Run scripts/worldgen/Bootstrap-YacsPcgEx.ps1 -Mode Install first."));
    return 20;
#else
    FString PackageName = DefaultPackageName;
    FParse::Value(*Params, TEXT("Package="), PackageName);

    if (!FPackageName::IsValidLongPackageName(PackageName))
    {
        UE_LOG(
            LogYacsPassoGiauPcgExGraph,
            Error,
            TEXT("Invalid PCG graph package name: %s"),
            *PackageName);
        return 21;
    }

    const FString AssetName = FPackageName::GetLongPackageAssetName(PackageName);
    UPackage* Package = CreatePackage(*PackageName);
    if (!Package)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to create package %s."), *PackageName);
        return 22;
    }

    if (FindObject<UPCGGraph>(Package, *AssetName))
    {
        UE_LOG(
            LogYacsPassoGiauPcgExGraph,
            Error,
            TEXT("PCG graph asset already exists in package %s. "
                 "Delete the generated spike asset before deterministic regeneration."),
            *PackageName);
        return 23;
    }

    UPCGGraph* Graph = NewObject<UPCGGraph>(
        Package,
        *AssetName,
        RF_Public | RF_Standalone | RF_Transactional);
    if (!Graph)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to allocate PCG graph."));
        return 24;
    }

    UPCGSettings* SourceBase = nullptr;
    UPCGNode* SourceNode = Graph->AddNodeOfType(
        UYacsPassoGiauSp638PathSettings::StaticClass(),
        SourceBase);
    UYacsPassoGiauSp638PathSettings* Source =
        Cast<UYacsPassoGiauSp638PathSettings>(SourceBase);
    if (!SourceNode || !Source)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to add YACS SP638 source node."));
        return 25;
    }
    Source->bUseSplineControlPoints = false;

    UPCGExResamplePathSettings* Resample = nullptr;
    UPCGNode* ResampleNode = Graph->AddNodeOfType<UPCGExResamplePathSettings>(Resample);
    if (!ResampleNode || !Resample)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to add PCGEx Path Resample node."));
        return 26;
    }
    Resample->Mode = EPCGExResampleMode::Sweep;
    Resample->ResolutionMode = EPCGExResolutionMode::Distance;
    Resample->SampleLength.Constant = 100.0;
    Resample->bRedistributeEvenly = true;
    Resample->bPreserveLastPoint = true;

    UPCGExSmoothSettings* Smooth = nullptr;
    UPCGNode* SmoothNode = Graph->AddNodeOfType<UPCGExSmoothSettings>(Smooth);
    if (!SmoothNode || !Smooth)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to add PCGEx Path Smooth node."));
        return 27;
    }
    Smooth->bPreserveStart = true;
    Smooth->bPreserveEnd = true;
    Smooth->Influence.Constant = 1.0;
    Smooth->SmoothingAmount.Constant = 3.0;

    UPCGExOffsetPathSettings* OffsetLeft = nullptr;
    UPCGNode* OffsetLeftNode = Graph->AddNodeOfType<UPCGExOffsetPathSettings>(OffsetLeft);
    UPCGExOffsetPathSettings* OffsetRight = nullptr;
    UPCGNode* OffsetRightNode = Graph->AddNodeOfType<UPCGExOffsetPathSettings>(OffsetRight);
    if (!OffsetLeftNode || !OffsetLeft || !OffsetRightNode || !OffsetRight)
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("Failed to add PCGEx Path Offset nodes."));
        return 28;
    }

    // 3.0 m from centerline = the current 6.0 m YACS presentation road width.
    // Line/Plane holds the requested distance through corners better than a raw slide.
    OffsetLeft->OffsetMethod = EPCGExOffsetMethod::LinePlane;
    OffsetLeft->Offset.Constant = 300.0;
    OffsetLeft->bInvertDirection = false;
    OffsetLeft->bApplyPointScaleToOffset = false;

    OffsetRight->OffsetMethod = EPCGExOffsetMethod::LinePlane;
    OffsetRight->Offset.Constant = 300.0;
    OffsetRight->bInvertDirection = true;
    OffsetRight->bApplyPointScaleToOffset = false;

    const FName PathPin(TEXT("Paths"));
    const FName SourcePin(TEXT("Path"));

    if (!Connect(Graph, SourceNode, SourcePin, ResampleNode, PathPin, TEXT("SP638 -> Resample"))
        || !Connect(Graph, ResampleNode, PathPin, SmoothNode, PathPin, TEXT("Resample -> Smooth"))
        || !Connect(Graph, SmoothNode, PathPin, OffsetLeftNode, PathPin, TEXT("Smooth -> Offset Left"))
        || !Connect(Graph, SmoothNode, PathPin, OffsetRightNode, PathPin, TEXT("Smooth -> Offset Right")))
    {
        return 29;
    }

    // Keep both derived edge paths wired into the graph output. PCG graph output
    // carries a data collection, so both path datasets remain distinct items.
    UPCGNode* OutputNode = Graph->GetOutputNode();
    if (!OutputNode || OutputNode->GetInputPins().IsEmpty())
    {
        UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("PCG graph has no usable output pin."));
        return 30;
    }

    const FName GraphOutputPin = OutputNode->GetInputPins()[0]->Properties.Label;
    Graph->AddLabeledEdge(SmoothNode, PathPin, OutputNode, GraphOutputPin);
    Graph->AddLabeledEdge(OffsetLeftNode, PathPin, OutputNode, GraphOutputPin);
    Graph->AddLabeledEdge(OffsetRightNode, PathPin, OutputNode, GraphOutputPin);

    FAssetRegistryModule& AssetRegistry =
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    AssetRegistry.AssetCreated(Graph);

    Package->MarkPackageDirty();

    const FString Filename = FPackageName::LongPackageNameToFilename(
        PackageName,
        FPackageName::GetAssetPackageExtension());
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true);

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;

    if (!UPackage::SavePackage(Package, Graph, *Filename, SaveArgs))
    {
        UE_LOG(
            LogYacsPassoGiauPcgExGraph,
            Error,
            TEXT("Failed to save PCGEx graph asset to %s."),
            *Filename);
        return 31;
    }

    const bool bExecute = FParse::Param(*Params, TEXT("Execute"));
    if (bExecute)
    {
        FString ExecutionOutput;
        FParse::Value(*Params, TEXT("ExecutionOutput="), ExecutionOutput);
        if (ExecutionOutput.IsEmpty())
        {
            UE_LOG(LogYacsPassoGiauPcgExGraph, Error, TEXT("-Execute requires -ExecutionOutput=<path>."));
            return 32;
        }
        if (FPaths::IsRelative(ExecutionOutput))
        {
            ExecutionOutput = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), ExecutionOutput);
        }
        if (!ExecuteGraphAndWriteProof(Graph, PackageName, ExecutionOutput, 60.0))
        {
            return 33;
        }
    }

    UE_LOG(
        LogYacsPassoGiauPcgExGraph,
        Display,
        TEXT("YACS PCGEx corridor graph authored: %s"),
        *PackageName);
    UE_LOG(
        LogYacsPassoGiauPcgExGraph,
        Display,
        TEXT("Contract: SP638 presentation -> resample 1m -> bounded smooth -> +/-3m offsets."));
    return 0;
#endif
}
