#include "Cycling/CyclingLandscapeEarthworksLibrary.h"

#if WITH_EDITOR

#include "Dom/JsonObject.h"
#include "Landscape.h"
#include "LandscapeEdit.h"
#include "LandscapeEditLayer.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingLandscapeEarthworks, Log, All);

namespace CyclingLandscapeEarthworksInternal
{
	constexpr int32 LandscapeMaxIndex = 4032;
	constexpr uint16 NeutralHeight = 32768;

	bool ReadIntField(
		const TSharedPtr<FJsonObject>& Object,
		const TCHAR* Name,
		int32& OutValue)
	{
		double Value = 0.0;
		if (!Object.IsValid() || !Object->TryGetNumberField(Name, Value) ||
			!FMath::IsFinite(Value) ||
			!FMath::IsNearlyEqual(Value, FMath::RoundToDouble(Value)))
		{
			return false;
		}
		OutValue = static_cast<int32>(Value);
		return true;
	}
}

bool UCyclingLandscapeEarthworksLibrary::ApplyRoadEarthworksPatch(
	ALandscape* Landscape,
	const FString& PatchManifestPath)
{
	using namespace CyclingLandscapeEarthworksInternal;

	if (!IsValid(Landscape))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch requires one valid Landscape."));
		return false;
	}

	const FString ManifestPath = FPaths::ConvertRelativePathToFull(PatchManifestPath);
	FString JsonText;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(JsonText, *ManifestPath) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) ||
		!Root.IsValid())
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Invalid CUT patch manifest: %s"), *ManifestPath);
		return false;
	}

	double SchemaVersion = 0.0;
	FString RegionId;
	FString Operation;
	FString LayerName;
	FString LayerEncoding;
	FString BaseLayerName;
	FString PatchFile;
	bool bBaseDtmModified = true;
	bool bFillPermitted = true;
	bool bStructurePermitted = true;
	bool bSaveMap = true;
	if (!Root->TryGetNumberField(TEXT("schema_version"), SchemaVersion) ||
		SchemaVersion != 1.0 ||
		!Root->TryGetStringField(TEXT("region_id"), RegionId) ||
		RegionId != TEXT("sa_calobra") ||
		!Root->TryGetStringField(TEXT("operation"), Operation) ||
		Operation != TEXT("CUT_ONLY") ||
		!Root->TryGetStringField(TEXT("layer"), LayerName) ||
		LayerName != TEXT("Road_Earthworks") ||
		!Root->TryGetStringField(TEXT("layer_encoding"), LayerEncoding) ||
		LayerEncoding != TEXT("ADDITIVE_DELTA_R16_32768_ZERO") ||
		!Root->TryGetStringField(TEXT("base_layer"), BaseLayerName) ||
		BaseLayerName != TEXT("Base_DTM") ||
		!Root->TryGetStringField(TEXT("patch_file"), PatchFile) ||
		PatchFile.IsEmpty() ||
		FPaths::GetCleanFilename(PatchFile) != PatchFile ||
		!Root->TryGetBoolField(TEXT("base_dtm_modified"), bBaseDtmModified) ||
		bBaseDtmModified ||
		!Root->TryGetBoolField(TEXT("fill_authoring_permitted"), bFillPermitted) ||
		bFillPermitted ||
		!Root->TryGetBoolField(TEXT("structure_authoring_permitted"), bStructurePermitted) ||
		bStructurePermitted ||
		!Root->TryGetBoolField(TEXT("save_map"), bSaveMap) ||
		bSaveMap)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch manifest violates the bounded recipe contract."));
		return false;
	}

	if (!Root->HasTypedField<EJson::Object>(TEXT("rect")))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch manifest is missing rect."));
		return false;
	}
	const TSharedPtr<FJsonObject> Rect = Root->GetObjectField(TEXT("rect"));
	int32 MinX = 0;
	int32 MinY = 0;
	int32 MaxX = 0;
	int32 MaxY = 0;
	int32 Width = 0;
	int32 Height = 0;
	if (!ReadIntField(Rect, TEXT("min_x"), MinX) ||
		!ReadIntField(Rect, TEXT("min_y"), MinY) ||
		!ReadIntField(Rect, TEXT("max_x"), MaxX) ||
		!ReadIntField(Rect, TEXT("max_y"), MaxY) ||
		!ReadIntField(Rect, TEXT("width"), Width) ||
		!ReadIntField(Rect, TEXT("height"), Height) ||
		MinX < 0 || MinY < 0 || MaxX > LandscapeMaxIndex || MaxY > LandscapeMaxIndex ||
		MaxX < MinX || MaxY < MinY ||
		Width != MaxX - MinX + 1 ||
		Height != MaxY - MinY + 1)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch rect is invalid."));
		return false;
	}

	const int64 ExpectedSamples = static_cast<int64>(Width) * static_cast<int64>(Height);
	if (ExpectedSamples <= 0 || ExpectedSamples > 4000000)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch rect exceeds bounded sample budget."));
		return false;
	}

	const FString PatchPath = FPaths::Combine(FPaths::GetPath(ManifestPath), PatchFile);
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *PatchPath) ||
		Bytes.Num() != ExpectedSamples * 2)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch R16 byte count mismatch: %s"), *PatchPath);
		return false;
	}

	TArray<uint16> HeightData;
	HeightData.SetNumUninitialized(static_cast<int32>(ExpectedSamples));
	int32 ModifiedCount = 0;
	for (int32 Index = 0; Index < HeightData.Num(); ++Index)
	{
		const int32 ByteIndex = Index * 2;
		const uint16 Value =
			static_cast<uint16>(Bytes[ByteIndex]) |
			(static_cast<uint16>(Bytes[ByteIndex + 1]) << 8);
		if (Value > NeutralHeight)
		{
			UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT-only patch attempted a positive/fill delta."));
			return false;
		}
		HeightData[Index] = Value;
		ModifiedCount += Value < NeutralHeight ? 1 : 0;
	}
	if (ModifiedCount <= 0)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch contains no modified vertices."));
		return false;
	}

	ULandscapeEditLayerBase* BaseLayer = Landscape->GetEditLayer(FName(TEXT("Base_DTM")));
	ULandscapeEditLayerBase* RoadLayer = Landscape->GetEditLayer(FName(TEXT("Road_Earthworks")));
	if (!IsValid(BaseLayer) || !IsValid(RoadLayer) ||
		!RoadLayer->IsA<ULandscapeEditLayer>())
	{
		UE_LOG(
			LogCyclingLandscapeEarthworks,
			Error,
			TEXT("CUT patch requires Base_DTM plus a standard Road_Earthworks edit layer."));
		return false;
	}

	ULandscapeInfo* LandscapeInfo = Landscape->GetLandscapeInfo();
	if (!IsValid(LandscapeInfo))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch LandscapeInfo is unavailable."));
		return false;
	}

	const FGuid RoadLayerGuid = RoadLayer->GetGuid();
	{
		FScopedSetLandscapeEditingLayer EditingScope(
			Landscape,
			RoadLayerGuid,
			[]() {});
		FHeightmapAccessor<false> HeightmapAccessor(LandscapeInfo, nullptr);
		HeightmapAccessor.SetEditLayer(RoadLayerGuid);
		HeightmapAccessor.SetData(
			MinX,
			MinY,
			MaxX,
			MaxY,
			HeightData.GetData(),
			ELandscapeLayerPaintingRestriction::None);
		HeightmapAccessor.Flush();

		TArray<uint16> Readback;
		Readback.SetNumUninitialized(HeightData.Num());
		HeightmapAccessor.GetDataFast(MinX, MinY, MaxX, MaxY, Readback.GetData());
		if (Readback != HeightData)
		{
			UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Road_Earthworks layer readback differs from CUT patch."));
			return false;
		}
	}

	// FHeightmapAccessor::Flush owns the changed-component update path. Force
	// the layer stack to evaluate, but do not call component-private collision
	// internals from this utility.
	Landscape->ForceLayersFullUpdate();
	Landscape->PostEditChange();

	UE_LOG(
		LogCyclingLandscapeEarthworks,
		Display,
		TEXT("BOB CUT patch applied transiently: rect=(%d,%d)-(%d,%d) modified_vertices=%d layer=Road_Earthworks."),
		MinX,
		MinY,
		MaxX,
		MaxY,
		ModifiedCount);
	return true;
}

#endif // WITH_EDITOR
