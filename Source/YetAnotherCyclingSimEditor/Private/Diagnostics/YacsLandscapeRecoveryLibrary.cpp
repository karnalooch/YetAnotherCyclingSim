#include "Diagnostics/YacsLandscapeRecoveryLibrary.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Landscape.h"
#include "LandscapeEdit.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
	constexpr int32 Vertices = 4033;
	constexpr int32 SampleCount = Vertices * Vertices;
	bool ReadHeights(const FString& Path, TArray<uint16>& Heights)
	{
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *Path) || Bytes.Num() != SampleCount * 2)
		{
			return false;
		}
		Heights.SetNumUninitialized(SampleCount);
		for (int32 Index = 0; Index < SampleCount; ++Index)
		{
			Heights[Index] = static_cast<uint16>(Bytes[Index * 2]) |
				(static_cast<uint16>(Bytes[Index * 2 + 1]) << 8);
		}
		return true;
	}
}

ALandscape* UYacsLandscapeRecoveryLibrary::ImportCleanBaseline(
	UWorld* World, const FString& HeightmapPath, const FVector& Scale, const FVector& Location)
{
	if (!IsInGameThread() || !IsValid(World) || World->WorldType != EWorldType::Editor ||
		Scale.ContainsNaN() || Location.ContainsNaN() ||
		!FMath::IsNearlyEqual(Scale.X, 800000.0 / 4032.0, 0.001) ||
		!FMath::IsNearlyEqual(Scale.Y, Scale.X, 0.001) ||
		Scale.Z < 250.0 || Scale.Z > 350.0 ||
		Location.X != 0.0 || Location.Y != 0.0 ||
		Location.Z < 150000.0 || Location.Z > 250000.0)
	{
		return nullptr;
	}
	TArray<uint16> Heights;
	if (!ReadHeights(HeightmapPath, Heights))
	{
		return nullptr;
	}
	FActorSpawnParameters Parameters;
	Parameters.OverrideLevel = World->GetCurrentLevel();
	Parameters.Name = TEXT("PassoGiauCleanBaseline");
	Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ALandscape* Landscape = World->SpawnActor<ALandscape>(
		ALandscape::StaticClass(), FTransform::Identity, Parameters);
	if (!IsValid(Landscape))
	{
		return nullptr;
	}
	Landscape->SetActorLabel(TEXT("Passo Giau clean DTM baseline"));
	Landscape->SetActorTransform(FTransform(FRotator::ZeroRotator, Location, Scale));
	Landscape->LandscapeMaterial = nullptr;
	TMap<FGuid, TArray<uint16>> HeightLayers;
	HeightLayers.Add(FGuid(), MoveTemp(Heights));
	TMap<FGuid, TArray<FLandscapeImportLayerInfo>> MaterialLayers;
	MaterialLayers.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());
	Landscape->Import(FGuid::NewGuid(), 0, 0, Vertices - 1, Vertices - 1,
		2, 63, HeightLayers, *HeightmapPath, MaterialLayers,
		ELandscapeImportAlphamapType::Additive, TArrayView<const FLandscapeLayer>());
	Landscape->RegisterAllComponents();
	Landscape->PostEditChange();
	return Landscape;
}

FString UYacsLandscapeRecoveryLibrary::VerifyBaselineHeights(
	ALandscape* Landscape, const FString& HeightmapPath)
{
	if (!IsInGameThread() || !IsValid(Landscape) || !Landscape->GetLandscapeInfo())
	{
		return TEXT("{\"error\":\"invalid Landscape or LandscapeInfo\"}");
	}
	TArray<uint16> Expected;
	if (!ReadHeights(HeightmapPath, Expected))
	{
		return TEXT("{\"error\":\"invalid 4033-square little-endian R16\"}");
	}
	TArray<uint16> Actual;
	Actual.Init(0, SampleCount);
	FLandscapeEditDataInterface Edit(Landscape->GetLandscapeInfo(), FGuid(), false);
	Edit.GetHeightDataFast(0, 0, Vertices - 1, Vertices - 1,
		Actual.GetData(), Vertices, nullptr, nullptr);
	int32 Mismatches = 0;
	int32 MaxDelta = 0;
	int32 FirstMismatch = INDEX_NONE;
	for (int32 Index = 0; Index < SampleCount; ++Index)
	{
		const int32 Delta = FMath::Abs(static_cast<int32>(Actual[Index]) - Expected[Index]);
		if (Delta != 0)
		{
			++Mismatches;
			if (FirstMismatch == INDEX_NONE) { FirstMismatch = Index; }
			MaxDelta = FMath::Max(MaxDelta, Delta);
		}
	}
	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	Report->SetStringField(TEXT("status"), Mismatches == 0 ? TEXT("PASS") : TEXT("FAIL"));
	Report->SetNumberField(TEXT("sample_count"), SampleCount);
	Report->SetNumberField(TEXT("mismatch_count"), Mismatches);
	Report->SetNumberField(TEXT("max_encoded_delta"), MaxDelta);
	Report->SetNumberField(TEXT("first_mismatch_index"), FirstMismatch);
	Report->SetBoolField(TEXT("height_edits_applied"), false);
	Report->SetStringField(TEXT("readback_api"), TEXT("FLandscapeEditDataInterface::GetHeightDataFast"));
	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	return FJsonSerializer::Serialize(Report, Writer) ? Json : TEXT("{\"error\":\"serialization failed\"}");
}
