#include "Diagnostics/YacsTextureAuditLibrary.h"

#include "Engine/Texture2D.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "PixelFormat.h"
#include "TextureCompiler.h"

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
