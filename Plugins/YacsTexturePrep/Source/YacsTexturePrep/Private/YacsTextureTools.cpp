#include "YacsTextureTools.h"
#include "YacsTextureGraph.h"
#include "TextureGraph.h"
#include "Blueprint/TG_AsyncRenderTask.h"
#include "TG_Graph.h"
#include "TG_Node.h"
#include "Expressions/Output/TG_Expression_Output.h"
#include "Async/Async.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "HAL/FileManager.h"
#include "Modules/ModuleManager.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, YacsTexturePrep)

namespace
{
constexpr double DeadlineSeconds = 180;
const TCHAR* Roles[] = {TEXT("BaseColor"), TEXT("Height"), TEXT("Normal"), TEXT("Roughness"), TEXT("MacroMask")};
FString Json(const TSharedRef<FJsonObject>& Object)
{
    FString Result;
    FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Result));
    return Result;
}
FString Failure(const FString& Error)
{
    auto O = MakeShared<FJsonObject>(); O->SetStringField(TEXT("status"), TEXT("rejected")); O->SetStringField(TEXT("error"), Error); return Json(O);
}
bool Supported()
{
    const auto& V = FEngineVersion::Current();
    return V.GetMajor() == 5 && V.GetMinor() == 8 && V.GetPatch() == 2;
}
bool InRange(float Value, float Low, float High) { return FMath::IsFinite(Value) && Value >= Low && Value <= High; }
bool Valid(const FYacsTextureRecipe& R)
{
    return R.Resolution >= 128 && R.Resolution <= 1024 && FMath::IsPowerOfTwo(R.Resolution)
        && FMath::IsFinite(R.WorldSizeMeters.X) && FMath::IsFinite(R.WorldSizeMeters.Y)
        && R.WorldSizeMeters.X > 0 && R.WorldSizeMeters.Y > 0
        && R.WorldSizeMeters.X <= 1000 && R.WorldSizeMeters.Y <= 1000
        && InRange(R.SeamBlendWidth, 0, 0.25f) && InRange(R.DeLightStrength, 0, 1)
        && InRange(R.ColorGain.R, 0, 2) && InRange(R.ColorGain.G, 0, 2) && InRange(R.ColorGain.B, 0, 2) && R.ColorGain.A == 1
        && InRange(R.HeightStrength, 0, 1) && InRange(R.NormalStrength, 0, 2)
        && InRange(R.RoughnessMin, 0, 1) && InRange(R.RoughnessMax, R.RoughnessMin, 1)
        && InRange(R.MacroVariation, 0, 1);
}
bool SaveFresh(UObject* Asset)
{
    UPackage* Package = Asset->GetOutermost();
    const FString File = FPackageName::LongPackageNameToFilename(Package->GetName(), FPackageName::GetAssetPackageExtension());
    if (IFileManager::Get().FileExists(*File)) return false;
    FSavePackageArgs Args;
    Args.TopLevelFlags = RF_Public | RF_Standalone;
    Args.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Package, Asset, *File, Args);
}
FString GraphHash(const UYacsTextureJob& J)
{
    const FString File = FPackageName::LongPackageNameToFilename(J.Graph->GetOutermost()->GetName(), FPackageName::GetAssetPackageExtension());
    TArray<uint8> Bytes;
    return FFileHelper::LoadFileToArray(Bytes, *File) ? FSHA1::HashBuffer(Bytes.GetData(), Bytes.Num()).ToString() : FString();
}
bool SourceUnchanged(UYacsTextureJob& J)
{
    UTexture2D* Source = LoadObject<UTexture2D>(nullptr, *J.SourcePath);
    return Source && Source->Source.GetId().ToString() == J.SourceId && !Source->GetOutermost()->IsDirty()
        && J.Graph && !J.Graph->GetOutermost()->IsDirty() && !J.GraphHash.IsEmpty() && GraphHash(J) == J.GraphHash;
}
TSharedRef<FJsonObject> Report(UYacsTextureJob& J)
{
    if (J.bDraining && FPlatformTime::Seconds() - J.Started > DeadlineSeconds)
    {
        J.bTimedOut = true;
        J.State = TEXT("timeout_draining");
        J.Error = TEXT("Deadline elapsed; task is NOT cancelled. Writes remain locked until completion or editor exit.");
    }
    auto O = MakeShared<FJsonObject>();
    O->SetNumberField(TEXT("schema_version"), 1);
    O->SetStringField(TEXT("job_id"), J.Id);
    O->SetStringField(TEXT("status"), J.State);
    O->SetStringField(TEXT("error"), J.Error);
    O->SetStringField(TEXT("source_asset"), J.SourcePath);
    O->SetStringField(TEXT("source_id"), J.SourceId);
    O->SetStringField(TEXT("graph_package_sha1"), J.GraphHash);
    O->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    O->SetStringField(TEXT("adapter_version"), TEXT("0.1.0"));
    O->SetStringField(TEXT("export_backend"), TEXT("exact TG render readback serialized by UTexture2D::Source.Init; no re-render"));
    O->SetStringField(TEXT("graph_asset"), J.Graph ? J.Graph->GetPathName() : TEXT(""));
    O->SetStringField(TEXT("output_folder"), J.Folder);
    O->SetStringField(TEXT("evidence_directory"), J.Evidence);
    O->SetStringField(TEXT("admission"), TEXT("review_required"));
    O->SetBoolField(TEXT("task_still_running"), J.bDraining);
    O->SetObjectField(TEXT("recipe"), FJsonObjectConverter::UStructToJsonObject(J.Recipe));
    return O;
}
}

UYacsTextureJob* UYacsTextureTools::FindJob(const FString& Id)
{
    if (!IsInGameThread()) return nullptr;
    auto* Found = GetMutableDefault<UYacsTextureTools>()->Jobs.Find(Id);
    return Found ? Found->Get() : nullptr;
}
bool UYacsTextureTools::Busy()
{
    for (const auto& Pair : GetMutableDefault<UYacsTextureTools>()->Jobs) if (Pair.Value->bDraining) return true;
    return false;
}
FString UYacsTextureTools::InspectCapabilities()
{
    auto O = MakeShared<FJsonObject>();
    O->SetStringField(TEXT("status"), Supported() ? TEXT("available_opt_in") : TEXT("unsupported_engine"));
    O->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    O->SetStringField(TEXT("transport"), TEXT("ToolsetRegistry definition only; existing MCP route must explicitly allowlist it"));
    O->SetBoolField(TEXT("pixels_processed_by_texture_graph"), true);
    O->SetBoolField(TEXT("automatic_world_integration"), false);
    O->SetNumberField(TEXT("maximum_resolution"), 1024);
    return Json(O);
}
FString UYacsTextureTools::PrepareTexture(const FString& SourceAssetPath, FYacsTextureRecipe Recipe)
{
    if (!IsInGameThread() || !Supported()) return Failure(TEXT("Requires game thread and UE 5.8.2"));
    if (Busy()) return Failure(TEXT("Another Texture Graph task is active or draining"));
    auto* Owner = GetMutableDefault<UYacsTextureTools>();
    if (Owner->Jobs.Num() >= 8) return Failure(TEXT("Session limit of eight jobs reached; reopen the isolated proof editor"));
    if (!Valid(Recipe)) return Failure(TEXT("Invalid or unsupported recipe value"));
    FText Reason;
    if (!SourceAssetPath.StartsWith(TEXT("/Game/")) || !FPackageName::IsValidObjectPath(SourceAssetPath, &Reason))
        return Failure(TEXT("Source must be an existing /Game/ texture object path"));
    UTexture2D* Source = LoadObject<UTexture2D>(nullptr, *SourceAssetPath);
    if (!Source || !Source->SRGB || Source->VirtualTextureStreaming || !Source->Source.IsValid()
        || Source->Source.GetNumBlocks() != 1 || Source->Source.GetNumLayers() != 1
        || Source->Source.GetSizeX() > 4096 || Source->Source.GetSizeY() > 4096
        || Source->Source.GetSizeX() < 8 || Source->Source.GetSizeY() < 8 || Source->GetOutermost()->IsDirty())
        return Failure(TEXT("Source must be a saved, non-virtual, single-layer sRGB Texture2D, 8..4096 pixels"));
    FImage SourceImage;
    if (!Source->Source.GetMipImage(SourceImage, 0) || SourceImage.Format != ERawImageFormat::BGRA8)
        return Failure(TEXT("Initial adapter supports opaque BGRA8 source data only"));
    for (const FColor& Pixel : SourceImage.AsBGRA8()) if (Pixel.A != 255) return Failure(TEXT("Source alpha must be opaque"));
    UYacsTextureJob* J = NewObject<UYacsTextureJob>(Owner);
    J->Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    J->Folder = TEXT("/Game/Generated/YACS/TextureMaterialPrep/Runs/") + J->Id;
    J->Evidence = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("RuntimeProof/TextureMaterialPrep") / J->Id);
    J->Recipe = Recipe; J->SourcePath = SourceAssetPath; J->SourceId = Source->Source.GetId().ToString();
    const FString DiskFolder = FPackageName::LongPackageNameToFilename(J->Folder);
    if (IFileManager::Get().DirectoryExists(*DiskFolder) || IFileManager::Get().DirectoryExists(*J->Evidence)) return Failure(TEXT("Run collision"));
    if (!BuildYacsTextureGraph(*J, Source, J->Error) || !SaveFresh(J->Graph)) return Failure(TEXT("Graph construction or fresh save failed: ") + J->Error);
    J->GraphHash = GraphHash(*J);
    if (!IFileManager::Get().MakeDirectory(*J->Evidence, true)
        || !FImageUtils::SaveImageByExtension(*(J->Evidence / TEXT("Source.png")), SourceImage)) return Failure(TEXT("Source evidence write failed"));
    J->State = TEXT("prepared"); Owner->Jobs.Add(J->Id, J);
    return Json(Report(*J));
}
FString UYacsTextureTools::RenderPreview(const FString& JobId)
{
    auto* J = FindJob(JobId);
    if (!J || Busy() || J->State != TEXT("prepared") || !SourceUnchanged(*J)) return Failure(TEXT("Render requires a prepared immutable job and idle scheduler"));
    J->State = TEXT("rendering"); J->Started = FPlatformTime::Seconds(); J->bDraining = true;
    J->StartNextRender();
    return Json(Report(*J));
}
void UYacsTextureJob::StartNextRender()
{
    if (bTimedOut || FPlatformTime::Seconds() - Started > DeadlineSeconds || !SourceUnchanged(*this))
    { bDraining = false; State = TEXT("failed"); Error = TEXT("Render identity/deadline changed"); return; }
    WorkingGraph = Cast<UTextureGraph>(StaticDuplicateObject(Graph, GetTransientPackage()));
    TArray<UTG_Node*> Remove;
    int32 Selected = 0;
    WorkingGraph->Graph()->ForEachNodes([&](const UTG_Node* Node, uint32) {
        if (Node) if (auto* Output = Cast<UTG_Expression_Output>(Node->GetExpression()))
        {
            if (Output->GetTitleName() == FName(Roles[RenderRole])) ++Selected;
            else Remove.Add(const_cast<UTG_Node*>(Node));
        }
    });
    for (auto* Node : Remove) WorkingGraph->Graph()->RemoveNode(Node);
    if (Selected != 1)
    { bDraining = false; State = TEXT("failed"); Error = TEXT("Named output is not unique"); return; }
    RenderTask = UTG_AsyncRenderTask::TG_AsyncRenderTask(WorkingGraph);
    if (!RenderTask)
    { bDraining = false; State = TEXT("failed"); Error = TEXT("Texture Graph refused render task"); return; }
    RenderTask->OnDone.AddDynamic(this, &UYacsTextureJob::OnRendered);
    RenderTask->Activate();
}
void UYacsTextureJob::OnRendered(const TArray<UTextureRenderTarget2D*>& Targets)
{
    bTimedOut |= FPlatformTime::Seconds() - Started > DeadlineSeconds;
    FImage Image;
    // Exactly one named Output exists in the selected working graph. No array
    // position is used to guess the role of a multi-output render.
    bool bValid = !bTimedOut && SourceUnchanged(*this) && Targets.Num() == 1 && Targets[0]
        && Targets[0]->SizeX == Recipe.Resolution && Targets[0]->SizeY == Recipe.Resolution
        && FImageUtils::GetRenderTargetImage(Targets[0], Image) && Image.Format == ERawImageFormat::BGRA8;
    if (bValid)
    {
        for (const FColor& Pixel : Image.AsBGRA8())
        {
            if (RenderRole == 3)
            {
                const float Value = Pixel.R / 255.0f;
                bValid &= Value >= Recipe.RoughnessMin - 2.0f / 255 && Value <= Recipe.RoughnessMax + 2.0f / 255;
            }
            if (RenderRole == 2)
            {
                const FVector N(Pixel.R / 127.5 - 1, Pixel.G / 127.5 - 1, Pixel.B / 127.5 - 1);
                bValid &= FMath::Abs(N.Length() - 1) <= 0.03;
            }
        }
    }
    const FString File = Evidence / (FString(TEXT("Preview-")) + Roles[RenderRole] + TEXT(".png"));
    bValid &= !IFileManager::Get().FileExists(*File);
    if (bValid) bValid = FImageUtils::SaveImageByExtension(*File, Image);
    if (!bValid)
    { bDraining = false; State = TEXT("failed"); Error = TEXT("Named render readback, pixel sanity, identity or deadline failed: ") + FString(Roles[RenderRole]); return; }
    RenderedImages.Add(Roles[RenderRole], MoveTemp(Image));
    ++RenderRole;
    if (RenderRole == 5) { bDraining = false; State = TEXT("rendered"); return; }
    TWeakObjectPtr<UYacsTextureJob> Weak(this);
    AsyncTask(ENamedThreads::GameThread, [Weak]() { if (Weak.IsValid()) Weak->StartNextRender(); });
}
FString UYacsTextureTools::ExportPbrSet(const FString& JobId)
{
    auto* J = FindJob(JobId);
    if (!J || Busy() || J->State != TEXT("rendered") || !SourceUnchanged(*J) || J->RenderedImages.Num() != 5)
        return Failure(TEXT("Export requires a completed immutable named render"));
    for (const TCHAR* Role : Roles)
    {
        const FString Path = J->Folder / Role;
        if (FPackageName::DoesPackageExist(Path) || FindObject<UPackage>(nullptr, *Path)) return Failure(TEXT("Export destination already exists"));
    }
    // UE 5.8.2 TG async re-render/export produced intermittent zero maps in the
    // isolated GPU proof. Serialize the already checked TG pixels instead.
    // This performs no resampling, color correction, synthesis or other processing.
    J->State = TEXT("exporting");
    for (int I = 0; I < 5; ++I)
    {
        UPackage* Package = CreatePackage(*(J->Folder / Roles[I]));
        UTexture2D* Texture = NewObject<UTexture2D>(Package, FName(Roles[I]), RF_Public | RF_Standalone);
        Texture->SRGB = I == 0;
        Texture->CompressionSettings = I == 2 ? TC_Normalmap : I == 0 ? TC_Default : TC_Masks;
        Texture->LODGroup = TEXTUREGROUP_World;
        Texture->Source.Init(J->RenderedImages.FindChecked(Roles[I]));
        Texture->UpdateResource();
        Texture->MarkPackageDirty();
        FAssetRegistryModule::AssetCreated(Texture);
    }
    J->State = TEXT("export_completed_unverified");
    return Json(Report(*J));
}
FString UYacsTextureTools::ValidateTexture(const FString& JobId)
{
    auto* J = FindJob(JobId);
    if (!J || Busy() || J->State != TEXT("export_completed_unverified") || !SourceUnchanged(*J)) return Failure(TEXT("Validation requires completed export and unchanged source"));
    if (J->bValidated) return Failure(TEXT("Evidence cannot be overwritten"));
    J->bValidated = true;
    auto Outputs = MakeShared<FJsonObject>();
    // Verify the entire bundle before saving any output package.
    TArray<UTexture2D*> Textures;
    for (int I = 0; I < 5; ++I)
    {
        const FString Path = J->Folder / Roles[I];
        UTexture2D* T = FindObject<UTexture2D>(nullptr, *(Path + TEXT(".") + Roles[I]));
        const auto Compression = I == 2 ? TC_Normalmap : I == 0 ? TC_Default : TC_Masks;
        if (!T || T->Source.GetSizeX() != J->Recipe.Resolution || T->Source.GetSizeY() != J->Recipe.Resolution
            || T->SRGB != (I == 0) || T->CompressionSettings != Compression || T->VirtualTextureStreaming)
        {
            J->State = TEXT("failed"); J->Error = TEXT("Missing output or dimension/color/compression mismatch: ") + FString(Roles[I]);
            return Json(Report(*J));
        }
        FImage Readback;
        const FImage& Expected = J->RenderedImages.FindChecked(Roles[I]);
        if (!T->Source.GetMipImage(Readback, 0) || Readback.Format != Expected.Format
            || Readback.RawData.Num() != Expected.RawData.Num()
            || FMemory::Memcmp(Readback.RawData.GetData(), Expected.RawData.GetData(), Expected.RawData.Num()) != 0)
        { J->State = TEXT("failed"); J->Error = TEXT("Export pixels differ from named TG render"); return Json(Report(*J)); }
        Textures.Add(T);
    }
    for (int I = 0; I < Textures.Num(); ++I)
    {
        FImage Image;
        UTexture2D* T = Textures[I];
        const FString File = J->Evidence / (FString(Roles[I]) + TEXT(".png"));
        if (!T->Source.GetMipImage(Image, 0) || Image.Format != ERawImageFormat::BGRA8
            || IFileManager::Get().FileExists(*File) || !FImageUtils::SaveImageByExtension(*File, Image) || !SaveFresh(T))
        {
            J->State = TEXT("failed"); J->Error = TEXT("Output readback/save failed; partial run quarantined"); return Json(Report(*J));
        }
        auto Output = MakeShared<FJsonObject>();
        Output->SetStringField(TEXT("asset"), T->GetPathName()); Output->SetStringField(TEXT("file"), FPaths::GetCleanFilename(File));
        Output->SetBoolField(TEXT("srgb"), T->SRGB); Output->SetNumberField(TEXT("resolution"), J->Recipe.Resolution);
        Output->SetStringField(TEXT("source_id"), T->Source.GetId().ToString()); Outputs->SetObjectField(Roles[I], Output);
    }
    J->State = TEXT("exported_review_required");
    auto O = Report(*J); O->SetObjectField(TEXT("outputs"), Outputs);
    O->SetStringField(TEXT("reopen_validation"), TEXT("pending"));
    O->SetStringField(TEXT("metrics_validation"), TEXT("run texture_material_prep_bundle.py on this directory"));
    const FString File = J->Evidence / TEXT("ue-receipt.json");
    if (IFileManager::Get().FileExists(*File) || !FFileHelper::SaveStringToFile(Json(O), *File, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    { J->State = TEXT("failed"); J->Error = TEXT("Receipt write failed"); return Json(Report(*J)); }
    return Json(O);
}
FString UYacsTextureTools::GetJobStatus(const FString& JobId)
{
    auto* J = FindJob(JobId); return J ? Json(Report(*J)) : Failure(TEXT("Unknown job or wrong thread"));
}
