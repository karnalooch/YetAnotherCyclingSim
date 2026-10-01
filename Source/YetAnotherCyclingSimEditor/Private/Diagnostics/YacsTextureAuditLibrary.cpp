#include "Diagnostics/YacsTextureAuditLibrary.h"

#include "Engine/Texture2D.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "PixelFormat.h"

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
	Report->SetBoolField(TEXT("srgb"), Texture->SRGB);
	Report->SetBoolField(TEXT("virtual_texture"), Texture->IsCurrentlyVirtualTextured());

	FString Json;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
	return FJsonSerializer::Serialize(Report, Writer) ? Json : TEXT("{\"error\":\"JSON serialization failed\"}");
}
