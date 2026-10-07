#include "Diagnostics/YacsTextureAuditLibrary.h"

#include "Engine/Texture2D.h"
#include "AssetCompilingManager.h"
#include "HAL/PlatformMemory.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "PixelFormat.h"
#include "TextureCompiler.h"
#include "Components/ActorComponent.h"
#include "Materials/MaterialInstance.h"
#include "UObject/UnrealType.h"
#include "UObject/GarbageCollection.h"

FString UYacsTextureAuditLibrary::DescribeLandscapeMaterialInstances(UActorComponent* Component, UMaterialInterface* ExpectedMaterial)
{
	if (!IsValid(Component) || !IsValid(ExpectedMaterial) || Component->GetClass()->GetPathName() != TEXT("/Script/Landscape.LandscapeComponent"))
	{
		return TEXT("{\"error\":\"invalid Landscape component or expected material\"}");
	}
	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	int32 InstanceCount = 0;
	bool bAllMatch = true;
	// Both native arrays are UPROPERTY(TextExportTransient), not editor-visible
	// Python properties. Reflection reads their objects without mutating them.
	for (const FName Name : {FName(TEXT("MaterialInstances")), FName(TEXT("MaterialInstancesDynamic"))})
	{
		FArrayProperty* Property = FindFProperty<FArrayProperty>(Component->GetClass(), Name);
		const FObjectPropertyBase* Inner = Property ? CastField<FObjectPropertyBase>(Property->Inner) : nullptr;
		if (!Inner)
		{
			return TEXT("{\"error\":\"native Landscape material-array contract unavailable\"}");
		}
		FScriptArrayHelper Items(Property, Property->ContainerPtrToValuePtr<void>(Component));
		Report->SetNumberField(Name.ToString(), Items.Num());
		if (Name == FName(TEXT("MaterialInstances")) && Items.Num() == 0)
		{
			bAllMatch = false;
		}
		for (int32 Index = 0; Index < Items.Num(); ++Index)
		{
			UMaterialInterface* Root = Cast<UMaterialInterface>(Inner->GetObjectPropertyValue(Items.GetRawPtr(Index)));
			TSet<UMaterialInterface*> Seen;
			while (UMaterialInstance* Instance = Cast<UMaterialInstance>(Root))
			{
				if (Seen.Contains(Root))
				{
					return TEXT("{\"error\":\"cyclic native material parent\"}");
				}
				Seen.Add(Root);
				Root = Instance->Parent;
			}
			bAllMatch &= Root == ExpectedMaterial;
			++InstanceCount;
		}
	}
	Report->SetStringField(TEXT("component"), Component->GetPathName());
	Report->SetStringField(TEXT("expected_material"), ExpectedMaterial->GetPathName());
	Report->SetNumberField(TEXT("render_instance_count"), InstanceCount);
	Report->SetBoolField(TEXT("all_instances_match"), bAllMatch && InstanceCount > 0);
	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	return FJsonSerializer::Serialize(Report, Writer) ? Json : TEXT("{\"error\":\"JSON serialization failed\"}");
}

FString UYacsTextureAuditLibrary::DescribeTexture(UTexture2D* Texture)
{
	if (!IsValid(Texture))
	{
		return TEXT("{\"error\":\"invalid texture\"}");
	}
	const FTexturePlatformData* Platform = Texture->GetPlatformData();
	if (!Platform)
	{
		return TEXT("{\"error\":\"missing derived texture platform data\"}");
	}

	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	Report->SetStringField(TEXT("texture"), Texture->GetPathName());
	Report->SetStringField(TEXT("description"), Texture->GetDesc());
	Report->SetStringField(TEXT("pixel_format"), GPixelFormats[Texture->GetPixelFormat(0)].Name);
	Report->SetNumberField(TEXT("size_x"), Platform->SizeX);
	Report->SetNumberField(TEXT("size_y"), Platform->SizeY);
	Report->SetNumberField(TEXT("mips"), Texture->GetNumMips());
	Report->SetNumberField(TEXT("resident_mips"), Texture->GetNumResidentMips());
	Report->SetNumberField(TEXT("source_mips"), Texture->Source.GetNumMips());
	Report->SetBoolField(TEXT("is_default_texture"), Texture->IsDefaultTexture());
	Report->SetBoolField(TEXT("is_compiling"), FTextureCompilingManager::Get().IsCompilingTexture(Texture));
	Report->SetBoolField(TEXT("srgb"), Texture->SRGB);
	Report->SetBoolField(TEXT("virtual_texture"), Texture->IsCurrentlyVirtualTextured());

	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	return FJsonSerializer::Serialize(Report, Writer) ? Json : TEXT("{\"error\":\"JSON serialization failed\"}");
}

bool UYacsTextureAuditLibrary::FinishTextureCompilation(const TArray<UTexture2D*>& Textures)
{
	if (!IsInGameThread() || Textures.IsEmpty())
	{
		return false;
	}
	TArray<UTexture*> Pending;
	Pending.Reserve(Textures.Num());
	for (UTexture2D* Texture : Textures)
	{
		if (!IsValid(Texture))
		{
			return false;
		}
		Pending.Add(Texture);
	}
	FTextureCompilingManager::Get().FinishCompilation(Pending);
	for (UTexture2D* Texture : Textures)
	{
		if (Texture->IsDefaultTexture() || FTextureCompilingManager::Get().IsCompilingTexture(Texture))
		{
			return false;
		}
	}
	return true;
}


FString UYacsTextureAuditLibrary::DrainAssetCompilationAndCollectGarbage()
{
	if (!IsInGameThread())
	{
		return TEXT("{\"ok\":false,\"error\":\"must run on game thread\"}");
	}

	FAssetCompilingManager& Manager = FAssetCompilingManager::Get();
	const int32 RemainingBefore = Manager.GetNumRemainingAssets();
	const FPlatformMemoryStats MemoryBefore = FPlatformMemory::GetStats();

	Manager.FinishAllCompilation();
	CollectGarbage(RF_NoFlags, true);

	const int32 RemainingAfter = Manager.GetNumRemainingAssets();
	const FPlatformMemoryStats MemoryAfter = FPlatformMemory::GetStats();

	const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
	Report->SetBoolField(TEXT("ok"), RemainingAfter == 0);
	Report->SetNumberField(TEXT("remaining_before"), RemainingBefore);
	Report->SetNumberField(TEXT("remaining_after"), RemainingAfter);
	Report->SetNumberField(TEXT("available_physical_before"), static_cast<double>(MemoryBefore.AvailablePhysical));
	Report->SetNumberField(TEXT("available_physical_after"), static_cast<double>(MemoryAfter.AvailablePhysical));
	Report->SetNumberField(TEXT("available_virtual_before"), static_cast<double>(MemoryBefore.AvailableVirtual));
	Report->SetNumberField(TEXT("available_virtual_after"), static_cast<double>(MemoryAfter.AvailableVirtual));

	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	return FJsonSerializer::Serialize(Report, Writer)
		? Json
		: TEXT("{\"ok\":false,\"error\":\"JSON serialization failed\"}");
}
