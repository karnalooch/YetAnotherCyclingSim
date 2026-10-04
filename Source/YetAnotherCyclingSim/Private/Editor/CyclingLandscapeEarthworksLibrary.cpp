#include "Cycling/CyclingLandscapeEarthworksLibrary.h"

#if WITH_EDITOR

#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Landscape.h"
#include "LandscapePatchEditLayer.h"
#include "LandscapeTexturePatch.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingLandscapeEarthworks, Log, All);

namespace CyclingLandscapeEarthworksInternal
{
	constexpr int32 LandscapeMaxIndex = 4032;
	constexpr float LandscapeGridStepCm = 50.0f;
	constexpr int64 MaxPatchSamples = 4000000;

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

	bool ReadBoolFalse(
		const TSharedPtr<FJsonObject>& Object,
		const TCHAR* Name)
	{
		bool Value = true;
		return Object.IsValid() &&
			Object->TryGetBoolField(Name, Value) &&
			!Value;
	}
}

bool UCyclingLandscapeEarthworksLibrary::ApplyRoadEarthworksPatch(
	ALandscape* Landscape,
	const FString& PatchManifestPath,
	bool bDeferLandscapeUpdate,
	const FString& PersistentTexturePackage)
{
	using namespace CyclingLandscapeEarthworksInternal;
	const bool bPersistent = !PersistentTexturePackage.IsEmpty();
	if (bPersistent && (!PersistentTexturePackage.StartsWith(TEXT("/Game/")) ||
		!FPackageName::IsValidLongPackageName(PersistentTexturePackage) ||
		FindPackage(nullptr, *PersistentTexturePackage) != nullptr ||
		FPackageName::DoesPackageExist(PersistentTexturePackage)))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Persistent CUT texture must use a new /Game package."));
		return false;
	}

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
	FString BlendMode;
	FString HeightEncoding;
	FString ZeroHeightMeaning;
	FString WorldSpaceUnit;
	FString BaseLayerName;
	FString PatchFile;
	if (!Root->TryGetNumberField(TEXT("schema_version"), SchemaVersion) ||
		SchemaVersion != 1.0 ||
		!Root->TryGetStringField(TEXT("region_id"), RegionId) ||
		RegionId != TEXT("sa_calobra") ||
		!Root->TryGetStringField(TEXT("operation"), Operation) ||
		Operation != TEXT("CUT_ONLY") ||
		!Root->TryGetStringField(TEXT("layer"), LayerName) ||
		LayerName != TEXT("Road_Earthworks") ||
		!Root->TryGetStringField(TEXT("layer_encoding"), LayerEncoding) ||
		LayerEncoding != TEXT("LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN") ||
		!Root->TryGetStringField(TEXT("blend_mode"), BlendMode) ||
		BlendMode != TEXT("Min") ||
		!Root->TryGetStringField(TEXT("height_encoding"), HeightEncoding) ||
		HeightEncoding != TEXT("WorldUnits") ||
		!Root->TryGetStringField(TEXT("zero_height_meaning"), ZeroHeightMeaning) ||
		ZeroHeightMeaning != TEXT("WorldZero") ||
		!Root->TryGetStringField(TEXT("world_space_unit"), WorldSpaceUnit) ||
		WorldSpaceUnit != TEXT("centimeter") ||
		!Root->TryGetStringField(TEXT("base_layer"), BaseLayerName) ||
		BaseLayerName != TEXT("Base_DTM") ||
		!Root->TryGetStringField(TEXT("patch_file"), PatchFile) ||
		PatchFile.IsEmpty() ||
		FPaths::GetCleanFilename(PatchFile) != PatchFile ||
		!ReadBoolFalse(Root, TEXT("base_dtm_modified")) ||
		!ReadBoolFalse(Root, TEXT("fill_authoring_permitted")) ||
		!ReadBoolFalse(Root, TEXT("structure_authoring_permitted")) ||
		!ReadBoolFalse(Root, TEXT("save_map")))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch manifest violates the native Min-patch contract."));
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
		MinX < 0 || MinY < 0 ||
		MaxX > LandscapeMaxIndex || MaxY > LandscapeMaxIndex ||
		MaxX < MinX || MaxY < MinY ||
		Width != MaxX - MinX + 1 ||
		Height != MaxY - MinY + 1)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch rect is invalid."));
		return false;
	}

	const int64 ExpectedSamples =
		static_cast<int64>(Width) * static_cast<int64>(Height);
	if (ExpectedSamples <= 0 || ExpectedSamples > MaxPatchSamples)
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch rect exceeds bounded sample budget."));
		return false;
	}

	const FString PatchPath = FPaths::Combine(FPaths::GetPath(ManifestPath), PatchFile);
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *PatchPath) ||
		Bytes.Num() != ExpectedSamples * static_cast<int64>(sizeof(float)))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch float32 byte count mismatch: %s"), *PatchPath);
		return false;
	}

	TArray<float> HeightsCm;
	HeightsCm.SetNumUninitialized(static_cast<int32>(ExpectedSamples));
	FMemory::Memcpy(
		HeightsCm.GetData(),
		Bytes.GetData(),
		static_cast<SIZE_T>(Bytes.Num()));

	float MinHeightCm = TNumericLimits<float>::Max();
	float MaxHeightCm = TNumericLimits<float>::Lowest();
	for (const float HeightCm : HeightsCm)
	{
		if (!FMath::IsFinite(HeightCm) ||
			HeightCm < -50000.0f ||
			HeightCm > 200000.0f)
		{
			UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch contains invalid world-space height."));
			return false;
		}
		MinHeightCm = FMath::Min(MinHeightCm, HeightCm);
		MaxHeightCm = FMath::Max(MaxHeightCm, HeightCm);
	}

	ULandscapeEditLayerBase* BaseLayer =
		Landscape->GetEditLayer(FName(TEXT("Base_DTM")));
	ULandscapeEditLayerBase* RoadLayerBase =
		Landscape->GetEditLayer(FName(TEXT("Road_Earthworks")));
	ULandscapePatchEditLayer* RoadLayer =
		Cast<ULandscapePatchEditLayer>(RoadLayerBase);
	if (!IsValid(BaseLayer) || !IsValid(RoadLayer))
	{
		UE_LOG(
			LogCyclingLandscapeEarthworks,
			Error,
			TEXT("CUT patch requires Base_DTM plus native Landscape Patch Road_Earthworks layer."));
		return false;
	}

	UWorld* World = Landscape->GetWorld();
	if (!IsValid(World))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("CUT patch Landscape world is unavailable."));
		return false;
	}

	UTexture2D* HeightTexture = UTexture2D::CreateTransient(
		Width,
		Height,
		PF_R32_FLOAT,
		NAME_None);
	if (!IsValid(HeightTexture) ||
		HeightTexture->GetPlatformData() == nullptr ||
		HeightTexture->GetPlatformData()->Mips.IsEmpty())
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Failed to allocate transient float32 CUT texture."));
		return false;
	}
	HeightTexture->SRGB = false;
	HeightTexture->NeverStream = true;
	HeightTexture->Filter = TF_Bilinear;
	HeightTexture->CompressionSettings = TC_HDR;
	HeightTexture->MipGenSettings = TMGS_NoMipmaps;
	HeightTexture->SetFlags(RF_Transient);

	FTexture2DMipMap& Mip = HeightTexture->GetPlatformData()->Mips[0];
	void* TextureData = Mip.BulkData.Lock(LOCK_READ_WRITE);
	if (TextureData == nullptr)
	{
		Mip.BulkData.Unlock();
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Failed to lock transient CUT texture."));
		return false;
	}
	FMemory::Memcpy(
		TextureData,
		HeightsCm.GetData(),
		static_cast<SIZE_T>(Bytes.Num()));
	Mip.BulkData.Unlock();
	if (bPersistent)
	{
		UPackage* Package = CreatePackage(*PersistentTexturePackage);
		HeightTexture->Rename(*FPackageName::GetLongPackageAssetName(PersistentTexturePackage), Package, REN_DontCreateRedirectors);
		HeightTexture->ClearFlags(RF_Transient);
		HeightTexture->SetFlags(RF_Public | RF_Standalone);
		// Keep float32 precision across editor restart; TC_HDR would quantize heights.
		HeightTexture->CompressionSettings = TC_SingleFloat;
		HeightTexture->Source.Init(Width, Height, 1, 1, TSF_R32F, Bytes.GetData());
		HeightTexture->MarkPackageDirty();
		FAssetRegistryModule::AssetCreated(HeightTexture);
	}
	HeightTexture->UpdateResource();

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.OverrideLevel = World->GetCurrentLevel();
	if (!bPersistent)
	{
		SpawnParameters.ObjectFlags |= RF_Transient;
	}
	SpawnParameters.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AActor* PatchActor = World->SpawnActor<AActor>(
		AActor::StaticClass(),
		FTransform::Identity,
		SpawnParameters);
	if (!IsValid(PatchActor))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Failed to spawn transient CUT patch actor."));
		return false;
	}
	PatchActor->SetActorLabel(bPersistent ? TEXT("YACS_PERSIST_CUT") : TEXT("BOB Road_Earthworks CUT-only Min patch — transient"));

	ULandscapeTexturePatch* Patch = NewObject<ULandscapeTexturePatch>(
		PatchActor,
		TEXT("BOB_RoadEarthworks_MinPatch"),
		bPersistent ? RF_Transactional : (RF_Transient | RF_Transactional));
	if (!IsValid(Patch))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Failed to allocate Landscape Texture Patch component."));
		return false;
	}
	Patch->CreationMethod = EComponentCreationMethod::Instance;
	PatchActor->SetRootComponent(Patch);
	PatchActor->AddInstanceComponent(Patch);
	Patch->RegisterComponent();

	const FVector PatchLocation(
		(static_cast<double>(MinX) + static_cast<double>(MaxX)) *
			0.5 * LandscapeGridStepCm,
		(static_cast<double>(MinY) + static_cast<double>(MaxY)) *
			0.5 * LandscapeGridStepCm,
		0.0);
	PatchActor->SetActorLocation(PatchLocation, false, nullptr, ETeleportType::TeleportPhysics);
	PatchActor->SetActorRotation(FRotator::ZeroRotator);

	Patch->SetUnscaledCoverage(
		FVector2D(
			static_cast<double>(Width - 1) * LandscapeGridStepCm,
			static_cast<double>(Height - 1) * LandscapeGridStepCm));
	Patch->SetHeightSourceMode(ELandscapeTexturePatchSourceMode::TextureAsset);
	Patch->SetHeightTextureAsset(HeightTexture);
	Patch->SetHeightEncodingMode(
		ELandscapeTextureHeightPatchEncoding::WorldUnits);
	Patch->SetZeroHeightMeaning(
		ELandscapeTextureHeightPatchZeroHeightMeaning::WorldZero);
	FLandscapeTexturePatchEncodingSettings EncodingSettings;
	EncodingSettings.ZeroInEncoding = 0.0;
	EncodingSettings.WorldSpaceEncodingScale = 1.0;
	Patch->SetHeightEncodingSettings(EncodingSettings);
	Patch->SetHeightAlphaSourceMode(
		ELandscapeTexturePatchAlphaSourceMode::None,
		false);
	Patch->SetBlendMode(ELandscapeTexturePatchBlendMode::Min);
	Patch->SetFalloff(0.0f);
	Patch->SetIsEnabled(true);

	if (!Patch->AssignToLandscape(
		Landscape,
		FName(TEXT("Road_Earthworks"))))
	{
		UE_LOG(LogCyclingLandscapeEarthworks, Error, TEXT("Failed to bind CUT patch to Road_Earthworks."));
		return false;
	}
	// Request the full merge through Landscape; the patch-layer helper is not
	// exported by the installed UE 5.8 binary (LNK2019).
	if (!bDeferLandscapeUpdate && !FinishRoadEarthworksBatch(Landscape))
	{
		return false;
	}

	UE_LOG(
		LogCyclingLandscapeEarthworks,
		Display,
		TEXT("BOB native Min CUT patch active transiently: rect=(%d,%d)-(%d,%d) texture=%dx%d height_cm=[%.3f,%.3f] layer=Road_Earthworks."),
		MinX,
		MinY,
		MaxX,
		MaxY,
		Width,
		Height,
		MinHeightCm,
		MaxHeightCm);
	return true;
}

bool UCyclingLandscapeEarthworksLibrary::FinishRoadEarthworksBatch(ALandscape* Landscape)
{
	if (!IsValid(Landscape))
	{
		return false;
	}
	Landscape->ForceLayersFullUpdate();
	Landscape->PostEditChange();
	return true;
}

#endif // WITH_EDITOR
