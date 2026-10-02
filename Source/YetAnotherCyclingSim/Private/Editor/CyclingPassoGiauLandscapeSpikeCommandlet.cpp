#include "Cycling/CyclingPassoGiauLandscapeSpikeCommandlet.h"

#if WITH_EDITOR

#include "Components/SplineComponent.h"
#include "Components/SplineMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/FileManager.h"
#include "Landscape.h"
#include "LandscapeComponent.h"
#include "LandscapeInfo.h"
#include "LandscapeImportHelper.h"
#include "LandscapeEditLayer.h"
#include "LandscapePatchEditLayer.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "FileHelpers.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingPassoGiauLandscapeSpike, Log, All);

namespace CyclingPassoGiauLandscapeSpikeInternal
{
	const TCHAR* SpikeMapPackagePath = TEXT("/Game/Prototype/Maps/L_PassoGiauTerrainSpike");
	constexpr int32 LandscapeVertices = 4033;
	constexpr int32 LandscapeMaxIndex = LandscapeVertices - 1;
	constexpr int32 NumSubsections = 2;
	constexpr int32 SubsectionSizeQuads = 63;
	constexpr int32 ExpectedComponentSizeQuads = NumSubsections * SubsectionSizeQuads;
	constexpr int32 ExpectedComponentGrid = 32;
	constexpr int32 ExpectedComponentCount = ExpectedComponentGrid * ExpectedComponentGrid;
	constexpr double XYScaleCmPerVertex = 198.412698;
	constexpr double ZScale = 301.26543;
	constexpr double LocationZCm = 194259.253;
	constexpr uint16 MaxResampleEdgeLoss = 512;
	constexpr int64 ExpectedR16Bytes =
		static_cast<int64>(LandscapeVertices) *
		static_cast<int64>(LandscapeVertices) * 2;
	constexpr double RoadWidthCm = 600.0;
	constexpr double RoadThicknessCm = 8.0;
	constexpr double RoadEarthworksHalfWidthCm = 450.0;
	constexpr double RoadEarthworksSideFalloffCm = 650.0;
	constexpr int32 RoadEarthworksMinSubdivisions = 256;
	constexpr int32 RoadEarthworksMaxSubdivisions = 4096;
	constexpr int32 RoadEarthworksSubdivisionsPerControlPoint = 4;
	constexpr int32 MinRoadControlPoints = 50;
	constexpr int32 MaxRoadControlPoints = 1000;

	bool ReadR16LittleEndian(
		const FString& Path,
		TArray<uint16>& OutHeightData,
		uint16& OutMin,
		uint16& OutMax,
		FString& OutError)
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Path))
		{
			OutError = FString::Printf(TEXT("failed to read R16 heightmap '%s'"), *Path);
			return false;
		}

		if (Bytes.Num() != ExpectedR16Bytes)
		{
			OutError = FString::Printf(
				TEXT("R16 byte count mismatch: actual=%d expected=%lld"),
				Bytes.Num(),
				ExpectedR16Bytes);
			return false;
		}

		const int32 SampleCount = LandscapeVertices * LandscapeVertices;
		OutHeightData.SetNumUninitialized(SampleCount);
		OutMin = MAX_uint16;
		OutMax = 0;

		for (int32 Index = 0; Index < SampleCount; ++Index)
		{
			const int32 ByteIndex = Index * 2;
			const uint16 Value =
				static_cast<uint16>(Bytes[ByteIndex]) |
				(static_cast<uint16>(Bytes[ByteIndex + 1]) << 8);
			OutHeightData[Index] = Value;
			OutMin = FMath::Min(OutMin, Value);
			OutMax = FMath::Max(OutMax, Value);
		}

		// Terrain preparation may use cubic reprojection/resampling, so exact
		// source extrema are not guaranteed to survive on the 4033 grid.
		// Require near-full-domain coverage so meaningful relief is preserved
		// without pretending resampling must contain exactly 0 and 65535.
		if (OutMin > MaxResampleEdgeLoss ||
			OutMax < static_cast<uint16>(MAX_uint16 - MaxResampleEdgeLoss))
		{
			OutError = FString::Printf(
				TEXT("prepared heightmap lost too much vertical domain after resampling; min=%u max=%u"),
				OutMin,
				OutMax);
			return false;
		}

		return true;
	}

	bool VerifyUnrealImportReaderParity(
		const FString& Path,
		const TArray<uint16>& ExpectedHeightData,
		FString& OutError)
	{
		FLandscapeImportDescriptor ImportDescriptor;
		FText DescriptorMessage;
		const ELandscapeImportResult DescriptorResult =
			FLandscapeImportHelper::GetHeightmapImportDescriptor(
				Path,
				true,
				false,
				ImportDescriptor,
				DescriptorMessage);
		if (DescriptorResult == ELandscapeImportResult::Error)
		{
			OutError = FString::Printf(
				TEXT("Unreal native heightmap descriptor rejected R16 '%s': %s"),
				*Path,
				*DescriptorMessage.ToString());
			return false;
		}

		TArray<uint16> UnrealHeightData;
		FText DataMessage;
		const ELandscapeImportResult DataResult =
			FLandscapeImportHelper::GetHeightmapImportData(
				ImportDescriptor,
				0,
				UnrealHeightData,
				DataMessage);
		if (DataResult == ELandscapeImportResult::Error)
		{
			OutError = FString::Printf(
				TEXT("Unreal native heightmap reader rejected R16 '%s': %s"),
				*Path,
				*DataMessage.ToString());
			return false;
		}

		if (UnrealHeightData.Num() != ExpectedHeightData.Num())
		{
			OutError = FString::Printf(
				TEXT("Unreal native R16 reader sample count mismatch: actual=%d expected=%d"),
				UnrealHeightData.Num(),
				ExpectedHeightData.Num());
			return false;
		}

		for (int32 Index = 0; Index < ExpectedHeightData.Num(); ++Index)
		{
			if (UnrealHeightData[Index] != ExpectedHeightData[Index])
			{
				OutError = FString::Printf(
					TEXT("Unreal native R16 reader parity mismatch at sample %d: unreal=%u manual=%u"),
					Index,
					UnrealHeightData[Index],
					ExpectedHeightData[Index]);
				return false;
			}
		}

		return true;
	}

	bool ReadRoadSplineJson(
		const FString& Path,
		TArray<FVector>& OutPoints,
		FString& OutRoadName,
		FString& OutError)
	{
		FString JsonText;
		if (!FFileHelper::LoadFileToString(JsonText, *Path))
		{
			OutError = FString::Printf(TEXT("failed to read road JSON '%s'"), *Path);
			return false;
		}

		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			OutError = FString::Printf(TEXT("failed to parse road JSON '%s'"), *Path);
			return false;
		}

		Root->TryGetStringField(TEXT("name"), OutRoadName);
		if (OutRoadName.IsEmpty())
		{
			OutRoadName = TEXT("SP 638 DEL PASSO GIAU (BL)");
		}

		const TArray<TSharedPtr<FJsonValue>>* PointValues = nullptr;
		if (!Root->TryGetArrayField(TEXT("spline_points"), PointValues) || PointValues == nullptr)
		{
			OutError = TEXT("road JSON is missing spline_points");
			return false;
		}
		if (PointValues->Num() < MinRoadControlPoints ||
			PointValues->Num() > MaxRoadControlPoints)
		{
			OutError = FString::Printf(
				TEXT("road spline control count is outside [%d,%d]: %d"),
				MinRoadControlPoints,
				MaxRoadControlPoints,
				PointValues->Num());
			return false;
		}

		OutPoints.Reset();
		OutPoints.Reserve(PointValues->Num());
		for (int32 Index = 0; Index < PointValues->Num(); ++Index)
		{
			const TSharedPtr<FJsonObject> PointObject = (*PointValues)[Index]->AsObject();
			if (!PointObject.IsValid())
			{
				OutError = FString::Printf(TEXT("road spline point %d is not an object"), Index);
				return false;
			}

			double X = 0.0;
			double Y = 0.0;
			double Z = 0.0;
			if (!PointObject->TryGetNumberField(TEXT("ue_x_cm"), X) ||
				!PointObject->TryGetNumberField(TEXT("ue_y_cm"), Y) ||
				!PointObject->TryGetNumberField(TEXT("ue_z_cm"), Z))
			{
				OutError = FString::Printf(TEXT("road spline point %d is missing UE coordinates"), Index);
				return false;
			}
			if (!FMath::IsFinite(X) || !FMath::IsFinite(Y) || !FMath::IsFinite(Z) ||
				X < -1000.0 || X > 801000.0 ||
				Y < -1000.0 || Y > 801000.0 ||
				Z < 100000.0 || Z > 300000.0)
			{
				OutError = FString::Printf(
					TEXT("road spline point %d is outside the isolated Passo Giau world bounds"),
					Index);
				return false;
			}

			const FVector Point(X, Y, Z);
			if (OutPoints.Num() > 0)
			{
				const double StepCm = FVector::Dist2D(OutPoints.Last(), Point);
				if (StepCm < 1.0 || StepCm > 200000.0)
				{
					OutError = FString::Printf(
						TEXT("road spline point spacing is invalid at %d: %.3f cm"),
						Index,
						StepCm);
					return false;
				}
			}
			OutPoints.Add(Point);
		}

		return true;
	}


	bool SpawnRoadSpline(
		UWorld* World,
		ALandscape* Landscape,
		const FName& RoadEditLayerName,
		const TArray<FVector>& Points,
		int32& OutSplineMeshCount,
		int32& OutEarthworksSubdivisions,
		FString& OutError)
	{
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.OverrideLevel = World->GetCurrentLevel();
		SpawnParameters.Name = TEXT("PassoGiauRoad");
		SpawnParameters.SpawnCollisionHandlingOverride =
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

		AActor* RoadActor = World->SpawnActor<AActor>(
			AActor::StaticClass(),
			FTransform::Identity,
			SpawnParameters);
		if (!IsValid(RoadActor))
		{
			OutError = TEXT("failed to spawn Passo Giau road actor");
			return false;
		}
		RoadActor->SetActorLabel(TEXT("SP638 Passo Giau — presentation road"));

		USplineComponent* Spline = NewObject<USplineComponent>(
			RoadActor,
			TEXT("SP638Spline"),
			RF_Transactional);
		if (!IsValid(Spline))
		{
			OutError = TEXT("failed to allocate SP638 spline component");
			return false;
		}
		Spline->CreationMethod = EComponentCreationMethod::Instance;
		Spline->SetMobility(EComponentMobility::Static);
		RoadActor->SetRootComponent(Spline);
		RoadActor->AddInstanceComponent(Spline);
		Spline->RegisterComponent();
		Spline->ClearSplinePoints(false);

		for (int32 Index = 0; Index < Points.Num(); ++Index)
		{
			Spline->AddSplinePoint(
				Points[Index],
				ESplineCoordinateSpace::World,
				false);
			Spline->SetSplinePointType(
				Index,
				ESplinePointType::CurveClamped,
				false);
		}
		Spline->SetClosedLoop(false, false);
		Spline->UpdateSpline();

		if (!IsValid(Landscape))
		{
			OutError = TEXT("cannot apply SP638 earthworks without a valid Landscape");
			return false;
		}
		if (RoadEditLayerName.IsNone())
		{
			OutError = TEXT("cannot apply SP638 earthworks without a named edit layer");
			return false;
		}

		OutEarthworksSubdivisions = FMath::Clamp(
			Points.Num() * RoadEarthworksSubdivisionsPerControlPoint,
			RoadEarthworksMinSubdivisions,
			RoadEarthworksMaxSubdivisions);

		// World Building Bible contract: the real SP638 centerline owns the local
		// road corridor, while the macro DTM remains intact on its base edit layer.
		// EditorApplySpline writes only to Road_Earthworks and uses both raise and
		// lower so the Landscape can form believable cut/fill around the road.
		Landscape->EditorApplySpline(
			Spline,
			static_cast<float>(RoadEarthworksHalfWidthCm),
			static_cast<float>(RoadEarthworksHalfWidthCm),
			static_cast<float>(RoadEarthworksSideFalloffCm),
			static_cast<float>(RoadEarthworksSideFalloffCm),
			0.0f,
			0.0f,
			OutEarthworksSubdivisions,
			true,
			true,
			nullptr,
			RoadEditLayerName);
		Landscape->ForceLayersFullUpdate();
		Landscape->PostEditChange();

		UStaticMesh* RoadMesh = LoadObject<UStaticMesh>(
			nullptr,
			TEXT("/Engine/BasicShapes/Cube.Cube"));
		if (!IsValid(RoadMesh))
		{
			OutError = TEXT("failed to load /Engine/BasicShapes/Cube for road proof");
			return false;
		}

		OutSplineMeshCount = 0;
		const FVector2D CrossSectionScale(
			RoadWidthCm / 100.0,
			RoadThicknessCm / 100.0);
		for (int32 Index = 0; Index < Points.Num() - 1; ++Index)
		{
			USplineMeshComponent* Segment = NewObject<USplineMeshComponent>(
				RoadActor,
				*FString::Printf(TEXT("SP638Segment_%04d"), Index),
				RF_Transactional);
			if (!IsValid(Segment))
			{
				OutError = FString::Printf(TEXT("failed to allocate road segment %d"), Index);
				return false;
			}
			Segment->CreationMethod = EComponentCreationMethod::Instance;
			Segment->SetupAttachment(Spline);
			Segment->SetStaticMesh(RoadMesh);
			Segment->SetMobility(EComponentMobility::Static);
			Segment->SetForwardAxis(ESplineMeshAxis::X, false);
			Segment->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Segment->SetGenerateOverlapEvents(false);
			Segment->SetCastShadow(false);

			FVector StartPosition;
			FVector StartTangent;
			FVector EndPosition;
			FVector EndTangent;
			Spline->GetLocationAndTangentAtSplinePoint(
				Index,
				StartPosition,
				StartTangent,
				ESplineCoordinateSpace::Local);
			Spline->GetLocationAndTangentAtSplinePoint(
				Index + 1,
				EndPosition,
				EndTangent,
				ESplineCoordinateSpace::Local);

			Segment->SetStartAndEnd(
				StartPosition,
				StartTangent,
				EndPosition,
				EndTangent,
				false);
			Segment->SetStartScale(CrossSectionScale, false);
			Segment->SetEndScale(CrossSectionScale, false);
			RoadActor->AddInstanceComponent(Segment);
			Segment->RegisterComponent();
			Segment->UpdateMesh();
			++OutSplineMeshCount;
		}

		RoadActor->MarkPackageDirty();
		return true;
	}

	void StripSpikeMapActors(UWorld* World)
	{
		TArray<AActor*> ToDestroy;
		for (AActor* Actor : World->GetCurrentLevel()->Actors)
		{
			if (!IsValid(Actor) || Actor->IsA<AWorldSettings>())
			{
				continue;
			}
			ToDestroy.Add(Actor);
		}

		for (AActor* Actor : ToDestroy)
		{
			World->EditorDestroyActor(Actor, false);
		}
	}
}

UCyclingPassoGiauLandscapeSpikeCommandlet::UCyclingPassoGiauLandscapeSpikeCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingPassoGiauLandscapeSpikeCommandlet::Main(const FString& Params)
{
	using namespace CyclingPassoGiauLandscapeSpikeInternal;

	FString HeightmapPath;
	FString ProofPath;
	FString RoadJsonPath;
	FString TerrainManifestPath;
	FParse::Value(*Params, TEXT("Heightmap="), HeightmapPath);
	FParse::Value(*Params, TEXT("Proof="), ProofPath);
	FParse::Value(*Params, TEXT("RoadJson="), RoadJsonPath);
	FParse::Value(*Params, TEXT("TerrainManifest="), TerrainManifestPath);
	double RuntimeZScale = ZScale;
	double RuntimeLocationZCm = LocationZCm;
	double RuntimeXYScale = XYScaleCmPerVertex;
	FString RuntimeMapPackagePath = SpikeMapPackagePath;
	FString RuntimeRegionId = TEXT("passo_giau_legacy");
	FParse::Value(*Params, TEXT("ScaleZ="), RuntimeZScale);
	FParse::Value(*Params, TEXT("LocationZCm="), RuntimeLocationZCm);
	HeightmapPath.TrimQuotesInline();
	ProofPath.TrimQuotesInline();
	RoadJsonPath.TrimQuotesInline();
	TerrainManifestPath.TrimQuotesInline();
	const bool bManifestImport = !TerrainManifestPath.IsEmpty();
	if (bManifestImport)
	{
		FString ManifestText;
		TSharedPtr<FJsonObject> Manifest;
		if (!FFileHelper::LoadFileToString(ManifestText, *TerrainManifestPath) ||
			!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ManifestText), Manifest) ||
			!Manifest.IsValid())
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("Invalid terrain import manifest."));
			return 1;
		}
		FString SourceCrs;
		FString SourceSha;
		bool bSourceShaValid = Manifest->TryGetStringField(TEXT("source_sha256"), SourceSha) && SourceSha.Len() == 64;
		for (const TCHAR Character : SourceSha)
		{
			bSourceShaValid = bSourceShaValid && ((Character >= TEXT('0') && Character <= TEXT('9')) ||
				(Character >= TEXT('a') && Character <= TEXT('f')));
		}
		double SchemaVersion = 0.0;
		double NoDataCount = -1.0;
		bool bPresentationOnly = false;
		bool bRouteAuthority = true;
		bool bPhysicsAuthority = true;
		const TArray<TSharedPtr<FJsonValue>>* Vertices = nullptr;
		if (!Manifest->TryGetNumberField(TEXT("schema_version"), SchemaVersion) || SchemaVersion != 1.0 ||
			!Manifest->TryGetStringField(TEXT("region_id"), RuntimeRegionId) || RuntimeRegionId != TEXT("sa_calobra") ||
			!Manifest->TryGetStringField(TEXT("source_crs"), SourceCrs) || SourceCrs != TEXT("EPSG:25831") ||
			!bSourceShaValid ||
			!Manifest->TryGetStringField(TEXT("map_package"), RuntimeMapPackagePath) ||
			RuntimeMapPackagePath != TEXT("/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline") ||
			!Manifest->TryGetArrayField(TEXT("vertices"), Vertices) || Vertices->Num() != 2 ||
			(*Vertices)[0]->AsNumber() != LandscapeVertices || (*Vertices)[1]->AsNumber() != LandscapeVertices ||
			!Manifest->TryGetNumberField(TEXT("nodata_sample_count"), NoDataCount) || NoDataCount != 0.0 ||
			!Manifest->TryGetBoolField(TEXT("presentation_only"), bPresentationOnly) || !bPresentationOnly ||
			!Manifest->TryGetBoolField(TEXT("authoritative_route_geometry"), bRouteAuthority) || bRouteAuthority ||
			!Manifest->TryGetBoolField(TEXT("authoritative_physics"), bPhysicsAuthority) || bPhysicsAuthority ||
			!Manifest->TryGetNumberField(TEXT("scale_xy_cm_per_vertex"), RuntimeXYScale) || RuntimeXYScale != 50.0 ||
			!Manifest->TryGetNumberField(TEXT("scale_z"), RuntimeZScale) ||
			!Manifest->TryGetNumberField(TEXT("location_z_cm"), RuntimeLocationZCm) || !RoadJsonPath.IsEmpty())
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("Terrain manifest violates the admitted Sa Calobra terrain-only contract."));
			return 1;
		}
	}

	if (!FMath::IsFinite(RuntimeZScale) ||
		RuntimeZScale < (bManifestImport ? 0.001 : 250.0) ||
		RuntimeZScale > (bManifestImport ? 2000.0 : 350.0))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Invalid terrain ScaleZ value %.6f for the selected import contract."),
			RuntimeZScale);
		return 1;
	}
	if (!FMath::IsFinite(RuntimeLocationZCm) ||
		RuntimeLocationZCm < (bManifestImport ? -50000.0 : 150000.0) ||
		RuntimeLocationZCm > (bManifestImport ? 900000.0 : 250000.0))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Invalid terrain LocationZCm value %.3f for the selected import contract."),
			RuntimeLocationZCm);
		return 1;
	}

	if (HeightmapPath.IsEmpty())
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Missing required -Heightmap=<absolute .r16 path>."));
		return 1;
	}
	HeightmapPath = FPaths::ConvertRelativePathToFull(HeightmapPath);
	if (!FPaths::FileExists(HeightmapPath))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Heightmap does not exist: %s"), *HeightmapPath);
		return 1;
	}

	TArray<FVector> RoadPoints;
	FString RoadName;
	const bool bImportRoad = !RoadJsonPath.IsEmpty();
	if (bImportRoad)
	{
		RoadJsonPath = FPaths::ConvertRelativePathToFull(RoadJsonPath);
		if (!FPaths::FileExists(RoadJsonPath))
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
				TEXT("Road JSON does not exist: %s"), *RoadJsonPath);
			return 1;
		}
		FString RoadError;
		if (!ReadRoadSplineJson(RoadJsonPath, RoadPoints, RoadName, RoadError))
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("%s"), *RoadError);
			return 1;
		}
	}

	TArray<uint16> HeightData;
	uint16 EncodedMin = 0;
	uint16 EncodedMax = 0;
	FString Error;
	if (!ReadR16LittleEndian(
			HeightmapPath,
			HeightData,
			EncodedMin,
			EncodedMax,
			Error))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("%s"), *Error);
		return 1;
	}

	if (!VerifyUnrealImportReaderParity(HeightmapPath, HeightData, Error))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("%s"), *Error);
		return 1;
	}
	UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
		TEXT("Unreal native R16 import-reader parity: PASS (%d samples)."),
		HeightData.Num());

	UPackage* MapPackage = LoadPackage(nullptr, *RuntimeMapPackagePath, LOAD_None);
	if (!MapPackage)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to load isolated spike map package '%s'."),
			*RuntimeMapPackagePath);
		return 1;
	}

	UWorld* MapWorld = UWorld::FindWorldInPackage(MapPackage);
	if (!MapWorld)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Spike map package does not contain a UWorld."));
		return 1;
	}
	MapWorld->WorldType = EWorldType::Editor;

	StripSpikeMapActors(MapWorld);

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.OverrideLevel = MapWorld->GetCurrentLevel();
	SpawnParameters.Name = bManifestImport ? TEXT("SaCalobraLandscape") : TEXT("PassoGiauLandscape");
	SpawnParameters.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	ALandscape* Landscape = MapWorld->SpawnActor<ALandscape>(
		ALandscape::StaticClass(),
		FTransform::Identity,
		SpawnParameters);
	if (!IsValid(Landscape))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to spawn ALandscape in isolated spike map."));
		return 1;
	}

	Landscape->SetActorLabel(bManifestImport ? TEXT("Sa Calobra native DTM Landscape") : TEXT("Passo Giau DEM Landscape"));
	Landscape->LandscapeMaterial = nullptr;
	Landscape->SetActorTransform(
		FTransform(
			FRotator::ZeroRotator,
			FVector(0.0, 0.0, RuntimeLocationZCm),
			FVector(RuntimeXYScale, RuntimeXYScale, RuntimeZScale)));

	TArray<FLandscapeImportLayerInfo> MaterialImportLayers;
	TMap<FGuid, TArray<uint16>> HeightDataPerLayers;
	TMap<FGuid, TArray<FLandscapeImportLayerInfo>> MaterialLayerDataPerLayers;
	HeightDataPerLayers.Add(FGuid(), HeightData);
	MaterialLayerDataPerLayers.Add(FGuid(), MoveTemp(MaterialImportLayers));

	Landscape->Import(
		FGuid::NewGuid(),
		0,
		0,
		LandscapeMaxIndex,
		LandscapeMaxIndex,
		NumSubsections,
		SubsectionSizeQuads,
		HeightDataPerLayers,
		*HeightmapPath,
		MaterialLayerDataPerLayers,
		ELandscapeImportAlphamapType::Additive,
		TArrayView<const FLandscapeLayer>());

	Landscape->StaticLightingLOD = 0;
	if (ULandscapeInfo* LandscapeInfo = Landscape->GetLandscapeInfo())
	{
		LandscapeInfo->UpdateLayerInfoMap(Landscape);
	}
	else
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("LandscapeInfo was not created after import."));
		return 1;
	}

	Landscape->RegisterAllComponents();
	Landscape->PostEditChange();

	// World Building Bible contract: preserve the imported real DTM as the
	// non-destructive macro base, then author SP638 cut/fill on a separate
	// persistent Landscape edit layer. The visible road mesh stays independent
	// from the Landscape vertex grid.
	if (Landscape->GetEditLayers().IsEmpty())
	{
		Landscape->ConvertNonEditLayerLandscape();
	}

	TArray<ULandscapeEditLayerBase*> EditLayers = Landscape->GetEditLayers();
	if (EditLayers.Num() != 1 || !IsValid(EditLayers[0]))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape edit-layer conversion failed: expected one default layer, found %d."),
			EditLayers.Num());
		return 1;
	}

	const FName BaseLayerName(TEXT("Base_DTM"));
	const FName RoadLayerName(TEXT("Road_Earthworks"));
	EditLayers[0]->SetName(BaseLayerName, true);

	const int32 RoadLayerIndex = Landscape->CreateLayer(
		RoadLayerName,
		// Sa Calobra CUT-only authoring uses Epic's procedural Landscape Patch
		// edit layer. Texture patches can use Min blending, so road earthworks
		// can lower terrain without ever turning the same recipe into fill.
		bManifestImport ? ULandscapePatchEditLayer::StaticClass() : ULandscapeEditLayer::StaticClass(),
		false);
	if (RoadLayerIndex == INDEX_NONE)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to create dedicated Road_Earthworks Landscape edit layer."));
		return 1;
	}

	ULandscapeEditLayerBase* RoadEditLayer = Landscape->GetEditLayer(RoadLayerIndex);
	ULandscapeEditLayerBase* BaseEditLayer = Landscape->GetEditLayer(BaseLayerName);
	if (!IsValid(RoadEditLayer) || !IsValid(BaseEditLayer))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape edit-layer lookup failed after creation."));
		return 1;
	}
	if (RoadEditLayer->GetName() != RoadLayerName ||
		BaseEditLayer->GetName() != BaseLayerName)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape edit-layer naming drifted: base='%s' road='%s'."),
			*BaseEditLayer->GetName().ToString(),
			*RoadEditLayer->GetName().ToString());
		return 1;
	}

	EditLayers = Landscape->GetEditLayers();
	if (EditLayers.Num() != 2)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape edit-layer count mismatch after SP638 setup: %d."),
			EditLayers.Num());
		return 1;
	}
	Landscape->ForceLayersFullUpdate();

	TArray<ULandscapeComponent*> Components;
	Landscape->GetComponents<ULandscapeComponent>(Components);
	if (Components.Num() != ExpectedComponentCount)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape component count mismatch: actual=%d expected=%d."),
			Components.Num(),
			ExpectedComponentCount);
		return 1;
	}

	if (Landscape->NumSubsections != NumSubsections ||
		Landscape->SubsectionSizeQuads != SubsectionSizeQuads ||
		Landscape->ComponentSizeQuads != ExpectedComponentSizeQuads)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape topology mismatch: component_quads=%d subsections=%d subsection_quads=%d."),
			Landscape->ComponentSizeQuads,
			Landscape->NumSubsections,
			Landscape->SubsectionSizeQuads);
		return 1;
	}

	const FBox Bounds = Landscape->GetComponentsBoundingBox(true);
	const FVector BoundsSize = Bounds.GetSize();
	const double ExpectedPlanarSizeCm = RuntimeXYScale * (LandscapeVertices - 1);
	const double PlanarToleranceCm = bManifestImport ? 1.0 : 3000.0;
	if (!FMath::IsNearlyEqual(BoundsSize.X, ExpectedPlanarSizeCm, PlanarToleranceCm) ||
		!FMath::IsNearlyEqual(BoundsSize.Y, ExpectedPlanarSizeCm, PlanarToleranceCm))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape planar bounds mismatch: X=%.3f cm Y=%.3f cm expected~=%.3f cm."),
			BoundsSize.X,
			BoundsSize.Y,
			ExpectedPlanarSizeCm);
		return 1;
	}
	const double ExpectedReliefCm =
		(static_cast<double>(EncodedMax) - static_cast<double>(EncodedMin)) * RuntimeZScale / 128.0;
	const bool bReliefMatches = bManifestImport
		? FMath::IsNearlyEqual(BoundsSize.Z, ExpectedReliefCm, 1.0)
		: (BoundsSize.Z >= 140000.0 && BoundsSize.Z <= 170000.0);
	if (!bReliefMatches)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape vertical relief mismatch: actual=%.3f cm encoded-source expectation=%.3f cm."),
			BoundsSize.Z,
			ExpectedReliefCm);
		return 1;
	}

	int32 RoadSplineMeshCount = 0;
	int32 RoadEarthworksSubdivisions = 0;
	if (bImportRoad)
	{
		FString RoadError;
		if (!SpawnRoadSpline(
			MapWorld,
			Landscape,
			RoadLayerName,
			RoadPoints,
			RoadSplineMeshCount,
			RoadEarthworksSubdivisions,
			RoadError))
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error, TEXT("%s"), *RoadError);
			return 1;
		}
		if (RoadSplineMeshCount != RoadPoints.Num() - 1)
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
				TEXT("Road spline mesh count mismatch: actual=%d expected=%d."),
				RoadSplineMeshCount,
				RoadPoints.Num() - 1);
			return 1;
		}
	}

	MapWorld->MarkPackageDirty();
	if (!UEditorLoadingAndSavingUtils::SaveMap(MapWorld, RuntimeMapPackagePath))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to save isolated spike map '%s'."),
			*RuntimeMapPackagePath);
		return 1;
	}

	// UE Landscape stores height around 32768 at 1/128 local Z units.
	// Report the elevation represented by the persisted Landscape transform.
	const double SampledElevationMinM =
		(RuntimeLocationZCm + ((static_cast<double>(EncodedMin) - 32768.0) / 128.0) * RuntimeZScale) / 100.0;
	const double SampledElevationMaxM =
		(RuntimeLocationZCm + ((static_cast<double>(EncodedMax) - 32768.0) / 128.0) * RuntimeZScale) / 100.0;

	const FString ProofJson = FString::Printf(
		TEXT("{\n")
		TEXT("  \"schema_version\": 1,\n")
		TEXT("  \"passo_giau_landscape_import\": \"PASS\",\n")
		TEXT("  \"terrain_region_id\": \"%s\",\n")
		TEXT("  \"map\": \"%s\",\n")
		TEXT("  \"vertices\": [%d, %d],\n")
		TEXT("  \"component_grid\": [%d, %d],\n")
		TEXT("  \"component_count\": %d,\n")
		TEXT("  \"num_subsections\": %d,\n")
		TEXT("  \"subsection_size_quads\": %d,\n")
		TEXT("  \"component_size_quads\": %d,\n")
		TEXT("  \"unreal_native_import_reader_parity\": \"PASS\",\n")
		TEXT("  \"encoded_min\": %u,\n")
		TEXT("  \"encoded_max\": %u,\n")
		TEXT("  \"sampled_elevation_min_m\": %.3f,\n")
		TEXT("  \"sampled_elevation_max_m\": %.3f,\n")
		TEXT("  \"scale_x_cm_per_vertex\": %.6f,\n")
		TEXT("  \"scale_y_cm_per_vertex\": %.6f,\n")
		TEXT("  \"scale_z\": %.6f,\n")
		TEXT("  \"location_z_cm\": %.3f,\n")
		TEXT("  \"bounds_size_cm\": [%.3f, %.3f, %.3f],\n")
		TEXT("  \"road_imported\": %s,\n")
		TEXT("  \"road_control_points\": %d,\n")
		TEXT("  \"road_spline_mesh_segments\": %d,\n")
		TEXT("  \"road_width_cm\": %.3f,\n")
		TEXT("  \"edit_layers_enabled\": true,\n")
		TEXT("  \"edit_layer_count\": %d,\n")
		TEXT("  \"base_edit_layer\": \"Base_DTM\",\n")
		TEXT("  \"road_edit_layer\": \"Road_Earthworks\",\n")
		TEXT("  \"road_earthworks_applied\": %s,\n")
		TEXT("  \"road_earthworks_half_width_cm\": %.3f,\n")
		TEXT("  \"road_earthworks_side_falloff_cm\": %.3f,\n")
		TEXT("  \"road_earthworks_subdivisions\": %d,\n")
		TEXT("  \"road_earthworks_raise_heights\": true,\n")
		TEXT("  \"road_earthworks_lower_heights\": true,\n")
		TEXT("  \"presentation_only\": true,\n")
		TEXT("  \"authoritative_route_geometry\": false,\n")
		TEXT("  \"authoritative_physics\": false\n")
		TEXT("}\n"),
		*RuntimeRegionId,
		*RuntimeMapPackagePath,
		LandscapeVertices,
		LandscapeVertices,
		ExpectedComponentGrid,
		ExpectedComponentGrid,
		Components.Num(),
		Landscape->NumSubsections,
		Landscape->SubsectionSizeQuads,
		Landscape->ComponentSizeQuads,
		EncodedMin,
		EncodedMax,
		SampledElevationMinM,
		SampledElevationMaxM,
		RuntimeXYScale,
		RuntimeXYScale,
		RuntimeZScale,
		RuntimeLocationZCm,
		BoundsSize.X,
		BoundsSize.Y,
		BoundsSize.Z,
		bImportRoad ? TEXT("true") : TEXT("false"),
		RoadPoints.Num(),
		RoadSplineMeshCount,
		RoadWidthCm,
		EditLayers.Num(),
		bImportRoad ? TEXT("true") : TEXT("false"),
		RoadEarthworksHalfWidthCm,
		RoadEarthworksSideFalloffCm,
		RoadEarthworksSubdivisions);

	if (!ProofPath.IsEmpty())
	{
		ProofPath = FPaths::ConvertRelativePathToFull(ProofPath);
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(ProofPath), true);
		if (!FFileHelper::SaveStringToFile(ProofJson, *ProofPath))
		{
			UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
				TEXT("Failed to write import proof: %s"), *ProofPath);
			return 1;
		}
	}

	UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
		TEXT("PassoGiauLandscapeSpike: PASS vertices=4033x4033 components=1024 grid=32x32 subsections=2 subsection_quads=63 bounds_cm=(%.3f,%.3f,%.3f) encoded=(%u,%u)."),
		BoundsSize.X,
		BoundsSize.Y,
		BoundsSize.Z,
		EncodedMin,
		EncodedMax);
	if (bImportRoad)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
			TEXT("PassoGiauRoad: imported '%s' control_points=%d spline_meshes=%d width_cm=%.1f."),
			*RoadName,
			RoadPoints.Num(),
			RoadSplineMeshCount,
			RoadWidthCm);
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
			TEXT("SP638 earthworks: layer=Road_Earthworks half_width_cm=%.1f falloff_cm=%.1f subdivisions=%d raise=true lower=true."),
			RoadEarthworksHalfWidthCm,
			RoadEarthworksSideFalloffCm,
			RoadEarthworksSubdivisions);
	}
	UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
		TEXT("Landscape edit layers: base=Base_DTM road=Road_Earthworks count=%d."),
		EditLayers.Num());
	UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
		TEXT("CyclingPassoGiauLandscapeSpikeCommandlet: done."));
	return 0;
}

#endif // WITH_EDITOR
