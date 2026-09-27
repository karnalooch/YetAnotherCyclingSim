#include "Cycling/CyclingPassoGiauLandscapeSpikeCommandlet.h"

#if WITH_EDITOR

#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/FileManager.h"
#include "Landscape.h"
#include "LandscapeComponent.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "FileHelpers.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingPassoGiauLandscapeSpike, Log, All);

namespace CyclingPassoGiauLandscapeSpikeInternal
{
	const TCHAR* SpikeMapPackagePath = TEXT("/Game/Prototype/Maps/L_PassoGiauTerrainSpike");
	constexpr int32 LandscapeVertices = 1009;
	constexpr int32 LandscapeMaxIndex = LandscapeVertices - 1;
	constexpr int32 NumSubsections = 2;
	constexpr int32 SubsectionSizeQuads = 63;
	constexpr int32 ExpectedComponentSizeQuads = NumSubsections * SubsectionSizeQuads;
	constexpr int32 ExpectedComponentGrid = 8;
	constexpr int32 ExpectedComponentCount = ExpectedComponentGrid * ExpectedComponentGrid;
	constexpr double XYScaleCmPerVertex = 793.650794;
	constexpr double ZScale = 301.26543;
	constexpr double LocationZCm = 194259.253;
	constexpr uint16 MaxResampleEdgeLoss = 512;
	constexpr int64 ExpectedR16Bytes =
		static_cast<int64>(LandscapeVertices) *
		static_cast<int64>(LandscapeVertices) * 2;

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

		// Bilinear 800 -> 1009 resampling is not guaranteed to preserve the
		// exact source extrema. The accepted remote artifact currently spans
		// 31..65405. Require near-full-domain coverage so meaningful relief is
		// preserved without pretending resampling must contain 0 and 65535.
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
	FParse::Value(*Params, TEXT("Heightmap="), HeightmapPath);
	FParse::Value(*Params, TEXT("Proof="), ProofPath);
	HeightmapPath.TrimQuotesInline();
	ProofPath.TrimQuotesInline();

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

	UPackage* MapPackage = LoadPackage(nullptr, SpikeMapPackagePath, LOAD_None);
	if (!MapPackage)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to load isolated spike map package '%s'."),
			SpikeMapPackagePath);
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
	SpawnParameters.Name = TEXT("PassoGiauLandscape");
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

	Landscape->SetActorLabel(TEXT("Passo Giau DEM Landscape"));
	Landscape->LandscapeMaterial = nullptr;
	Landscape->SetActorTransform(
		FTransform(
			FRotator::ZeroRotator,
			FVector(0.0, 0.0, LocationZCm),
			FVector(XYScaleCmPerVertex, XYScaleCmPerVertex, ZScale)));

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
	constexpr double ExpectedPlanarSizeCm = 800000.0;
	constexpr double PlanarToleranceCm = 3000.0;
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
	if (BoundsSize.Z < 140000.0 || BoundsSize.Z > 170000.0)
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Landscape vertical relief is outside expected Passo Giau range: %.3f cm."),
			BoundsSize.Z);
		return 1;
	}

	MapWorld->MarkPackageDirty();
	if (!UEditorLoadingAndSavingUtils::SaveMap(MapWorld, SpikeMapPackagePath))
	{
		UE_LOG(LogCyclingPassoGiauLandscapeSpike, Error,
			TEXT("Failed to save isolated spike map '%s'."),
			SpikeMapPackagePath);
		return 1;
	}

	// UE Landscape stores height around 32768 at 1/128 local Z units.
	// Report the elevation represented by the persisted Landscape transform.
	const double SampledElevationMinM =
		(LocationZCm + ((static_cast<double>(EncodedMin) - 32768.0) / 128.0) * ZScale) / 100.0;
	const double SampledElevationMaxM =
		(LocationZCm + ((static_cast<double>(EncodedMax) - 32768.0) / 128.0) * ZScale) / 100.0;

	const FString ProofJson = FString::Printf(
		TEXT("{\n")
		TEXT("  \"schema_version\": 1,\n")
		TEXT("  \"passo_giau_landscape_import\": \"PASS\",\n")
		TEXT("  \"map\": \"%s\",\n")
		TEXT("  \"vertices\": [%d, %d],\n")
		TEXT("  \"component_grid\": [%d, %d],\n")
		TEXT("  \"component_count\": %d,\n")
		TEXT("  \"num_subsections\": %d,\n")
		TEXT("  \"subsection_size_quads\": %d,\n")
		TEXT("  \"component_size_quads\": %d,\n")
		TEXT("  \"encoded_min\": %u,\n")
		TEXT("  \"encoded_max\": %u,\n")
		TEXT("  \"sampled_elevation_min_m\": %.3f,\n")
		TEXT("  \"sampled_elevation_max_m\": %.3f,\n")
		TEXT("  \"scale_x_cm_per_vertex\": %.6f,\n")
		TEXT("  \"scale_y_cm_per_vertex\": %.6f,\n")
		TEXT("  \"scale_z\": %.6f,\n")
		TEXT("  \"location_z_cm\": %.3f,\n")
		TEXT("  \"bounds_size_cm\": [%.3f, %.3f, %.3f],\n")
		TEXT("  \"presentation_only\": true,\n")
		TEXT("  \"authoritative_route_geometry\": false,\n")
		TEXT("  \"authoritative_physics\": false\n")
		TEXT("}\n"),
		SpikeMapPackagePath,
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
		XYScaleCmPerVertex,
		XYScaleCmPerVertex,
		ZScale,
		LocationZCm,
		BoundsSize.X,
		BoundsSize.Y,
		BoundsSize.Z);

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
		TEXT("PassoGiauLandscapeSpike: PASS vertices=1009x1009 components=64 grid=8x8 subsections=2 subsection_quads=63 bounds_cm=(%.3f,%.3f,%.3f) encoded=(%u,%u)."),
		BoundsSize.X,
		BoundsSize.Y,
		BoundsSize.Z,
		EncodedMin,
		EncodedMax);
	UE_LOG(LogCyclingPassoGiauLandscapeSpike, Display,
		TEXT("CyclingPassoGiauLandscapeSpikeCommandlet: done."));
	return 0;
}

#endif // WITH_EDITOR
