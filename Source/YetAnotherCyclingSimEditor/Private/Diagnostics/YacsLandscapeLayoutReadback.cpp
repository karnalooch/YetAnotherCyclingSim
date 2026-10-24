#include "Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "LandscapeComponent.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"

FString UYacsLandscapeMeshDiagnosticLibrary::ReadLesson07ComponentLayout(ULandscapeComponent* Component)
{
    const TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("schema_version"), 1);
    Result->SetBoolField(TEXT("observed"), false);
    const auto Serialize = [&Result]() -> FString
    {
        FString Json;
        const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
        if (!FJsonSerializer::Serialize(Result, Writer))
        {
            return TEXT("{\"schema_version\":1,\"observed\":false,\"error\":\"serialization_failed\"}");
        }
        return Json;
    };
    const auto Refuse = [&Result, &Serialize](const TCHAR* Error) -> FString
    {
        Result->SetStringField(TEXT("error"), Error);
        return Serialize();
    };

    if (!IsInGameThread()) { return Refuse(TEXT("game_thread_required")); }
    if (!IsValid(Component)) { return Refuse(TEXT("invalid_component")); }
    const UWorld* World = Component->GetWorld();
    if (!IsValid(World) || World->WorldType != EWorldType::Editor)
    {
        return Refuse(TEXT("editor_world_required"));
    }
    const UPackage* Package = World->GetOutermost();
    if (!IsValid(Package)) { return Refuse(TEXT("world_package_unavailable")); }
    const FString WorldPackage = Package->GetName();
    // This getter belongs only to the isolated saved L07 consumer readback.
    if (WorldPackage != TEXT("/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"))
    {
        return Refuse(TEXT("lesson07_world_required"));
    }

    const TSharedRef<FJsonObject> Fields = MakeShared<FJsonObject>();
    Fields->SetNumberField(TEXT("component_size_quads"), Component->ComponentSizeQuads);
    Fields->SetNumberField(TEXT("subsection_size_quads"), Component->SubsectionSizeQuads);
    Fields->SetNumberField(TEXT("num_subsections"), Component->NumSubsections);
    Fields->SetNumberField(TEXT("section_base_x"), Component->SectionBaseX);
    Fields->SetNumberField(TEXT("section_base_y"), Component->SectionBaseY);
    Result->SetStringField(TEXT("component_path"), Component->GetPathName());
    Result->SetStringField(TEXT("world_package"), WorldPackage);
    Result->SetObjectField(TEXT("fields"), Fields);
    Result->SetBoolField(TEXT("observed"), true);
    return Serialize();
}
