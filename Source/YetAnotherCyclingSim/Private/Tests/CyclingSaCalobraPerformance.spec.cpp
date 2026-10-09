// Copyright YetAnotherCyclingSim. All Rights Reserved.
#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "HAL/IConsoleManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
#include "Landscape.h"
#include "LandscapeComponent.h"
#include "RenderTimer.h"
#include "GPUProfiler.h"
#include "RHI.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Materials/MaterialInstance.h"
#include "UObject/UnrealType.h"
#include <cfloat>

// Same frame/thread counters and FRHIGPUFrameTimeHistory as the existing
// Stage3G environment sampler. This scenario has no route/pawn dependency.
class FSaCalobraPerformanceCommand final : public IAutomationLatentCommand
{
public:
 explicit FSaCalobraPerformanceCommand(FAutomationTestBase* InTest) : Test(InTest) {}
 bool Update() override
 {
  if (!World)
  {
   for (const auto& Context : GEngine->GetWorldContexts())
    if (Context.WorldType == EWorldType::Game) World = Context.World();
   if (!World) return Fail(TEXT("Standalone game world missing"));
   Csv = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_SA_PERF_CSV"));
   const FString SettingsPath = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_SA_PERF_SETTINGS"));
   FString Text; TSharedPtr<FJsonObject> Settings;
   if (Csv.IsEmpty() || !FFileHelper::LoadFileToString(Text,*SettingsPath) ||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Settings))
    return Fail(TEXT("Missing performance settings"));
   FString Scenario;
   Settings->TryGetStringField(TEXT("scenario_id"), Scenario);
   bConsumer = Scenario == TEXT("sa-calobra-material");
   const FString ExpectedMap = bConsumer
    ? TEXT("/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview")
    : TEXT("/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline");
   if (World->GetPackage()->GetName() != ExpectedMap)
    return Fail(TEXT("Wrong performance map"));
   int32 Landscapes=0, Components=0;
   double MaximumGroundZ = -DBL_MAX;
   for (TActorIterator<ALandscape> It(World); It; ++It)
   { ++Landscapes; TArray<ULandscapeComponent*> Items; It->GetComponents(Items); Components += Items.Num();
     for (ULandscapeComponent* Component : Items) MaximumGroundZ = FMath::Max(MaximumGroundZ, static_cast<double>(Component->Bounds.Origin.Z + Component->Bounds.BoxExtent.Z)); }
   if (Landscapes != 1 || Components != 1024) return Fail(TEXT("Landscape topology mismatch"));
   if (!GRHIAdapterName.Contains(TEXT("RTX 2070")) || !GRHIAdapterName.Contains(TEXT("SUPER")))
    return Fail(TEXT("Active RHI GPU is not RTX 2070 SUPER"));
   if (!GEngine->GameViewport || !GEngine->GameViewport->Viewport ||
       GEngine->GameViewport->Viewport->GetSizeXY() != FIntPoint(1920,1080))
    return Fail(TEXT("Actual game viewport is not 1920x1080"));
   Views = Settings->GetArrayField(TEXT("views"));
   if (Views.Num() != (bConsumer ? 12 : 3)) return Fail(TEXT("Incomplete performance coverage"));
   if (bConsumer)
   {
    const TArray<TSharedPtr<FJsonValue>>& Path = Views.Last()->AsObject()->GetArrayField(TEXT("path"));
    if (Path.Num() < 3) return Fail(TEXT("Incomplete camera traversal"));
    for (const auto& Pose : Path)
     if (Pose->AsObject()->GetArrayField(TEXT("location_cm"))[2]->AsNumber() < MaximumGroundZ + 2000)
      return Fail(TEXT("Camera traversal is not clear of the actual Landscape envelope"));
   }
   for (const auto& Pair : TArray<TPair<FString,int32>>{{TEXT("r.VSync"),0},{TEXT("r.ScreenPercentage"),100},{TEXT("r.DynamicRes.OperationMode"),0},{TEXT("t.MaxFPS"),0}})
   {
    IConsoleVariable* CVar=IConsoleManager::Get().FindConsoleVariable(*Pair.Key);
    if (!CVar) return Fail(TEXT("Required render CVar missing"));
    CVar->Set(Pair.Value, ECVF_SetByConsole);
    if (CVar->GetInt()!=Pair.Value) return Fail(TEXT("Render setting did not apply"));
   }
   Camera=World->SpawnActor<ACameraActor>();
   if (!Camera || !World->GetFirstPlayerController()) return Fail(TEXT("Performance camera unavailable"));
   Camera->GetCameraComponent()->SetFieldOfView(74.0f);
   World->GetFirstPlayerController()->SetViewTarget(Camera);
   if (!bConsumer)
   {
    ADirectionalLight* Sun=World->SpawnActor<ADirectionalLight>();
    ASkyLight* Sky=World->SpawnActor<ASkyLight>();
    if (!Sun || !Sky) return Fail(TEXT("Lighting unavailable"));
    Sun->SetActorRotation(FRotator(-33,-48,0));
    Sun->GetLightComponent()->SetIntensity(8.0f);
    Sun->GetLightComponent()->SetCastShadows(false);
    Sky->GetLightComponent()->SetIntensity(0.8f);
   }
   if (!FFileHelper::SaveStringToFile(TEXT("sector,rel_s,frame_ms,game_ms,draw_ms,rhi_ms,gpu_ms\n"),*Csv))
    return Fail(TEXT("Cannot create timing CSV"));
   const TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
   Report->SetStringField(TEXT("MapPackage"), World->GetPackage()->GetName());
   Report->SetNumberField(TEXT("ComponentCount"), Components);
   Report->SetStringField(TEXT("ActiveGpu"), GRHIAdapterName);
   Report->SetStringField(TEXT("Resolution"), TEXT("1920x1080"));
   if (bConsumer)
   {
    const FString Parent = Settings->GetStringField(TEXT("expected_material_parent"));
    int32 VerifiedComponents = 0, Instances = 0;
    for (TActorIterator<ALandscape> It(World); It; ++It)
    {
     if (!IsValid(It->LandscapeMaterial) || It->LandscapeMaterial->GetOutermost()->GetName() != Settings->GetStringField(TEXT("expected_material_instance")))
      return Fail(TEXT("Saved Landscape instance differs from the admitted candidate"));
     TArray<ULandscapeComponent*> Items; It->GetComponents(Items);
     for (ULandscapeComponent* Component : Items)
     {
      if (Component->OverrideMaterial != nullptr) return Fail(TEXT("Unadmitted component material override"));
      const int32 Count = MaterialInstances(Component, Parent);
      if (Count < 1) return Fail(TEXT("Saved consumer has wrong or missing native material parents"));
      ++VerifiedComponents; Instances += Count;
     }
    }
    Report->SetStringField(TEXT("Head"), Settings->GetStringField(TEXT("exact_sha")));
    Report->SetStringField(TEXT("MapSha256"), Settings->GetStringField(TEXT("map_sha256")));
    Report->SetStringField(TEXT("ConsumerManifestSha256"), Settings->GetStringField(TEXT("consumer_manifest_sha256")));
    Report->SetStringField(TEXT("MaterialParent"), Parent);
    Report->SetNumberField(TEXT("MaterialComponentCount"), VerifiedComponents);
    Report->SetNumberField(TEXT("RenderInstanceCount"), Instances);
    Report->SetBoolField(TEXT("LightingPreserved"), true);
   }
   FString Identity;
   if (!FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Identity))) return Fail(TEXT("Cannot serialize runtime identity"));
   if (!FFileHelper::SaveStringToFile(Identity,*(Csv+TEXT(".identity.json")))) return Fail(TEXT("Cannot write runtime identity"));
   BeginView();
  }
  const double Now=FPlatformTime::Seconds();
  // Drain while warming up too, so a previous camera's GPU history cannot leak.
  uint64 Cycles=0; double GpuMs=0;
  while (GpuState.PopFrameCycles(Cycles)!=FRHIGPUFrameTimeHistory::EResult::Empty)
   if (Cycles>0) GpuMs=FPlatformTime::ToMilliseconds64(Cycles);
  if (Now-Start<5.0) return false;
  const double Elapsed=Now-Start-5.0;
  const double SampleSeconds = bConsumer && Sector == TEXT("traversal") ? 30.0 : 8.0;
  if (bConsumer) MoveCamera(FMath::Clamp(Elapsed / SampleSeconds, 0.0, 1.0));
  Buffer+=FString::Printf(TEXT("%s,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n"),*Sector,Elapsed,
   FApp::GetDeltaTime()*1000.0,FPlatformTime::ToMilliseconds(GGameThreadTime),
   FPlatformTime::ToMilliseconds(GRenderThreadTime),FPlatformTime::ToMilliseconds(GRHIThreadTime),GpuMs);
  if (Elapsed<SampleSeconds) return false;
  if (!FFileHelper::SaveStringToFile(Buffer,*Csv,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append))
   return Fail(TEXT("Cannot append timing CSV"));
  Buffer.Empty();
  if (++View==Views.Num()) return true;
  BeginView(); return false;
 }
private:
 // Same UE 5.8.2 reflected-array/parent contract as YacsTextureAuditLibrary;
 // keep runtime proof independent of the editor module and never rebuild it.
 int32 MaterialInstances(ULandscapeComponent* Component, const FString& Parent)
 {
  int32 Count = 0;
  for (const FName Name : {FName(TEXT("MaterialInstances")), FName(TEXT("MaterialInstancesDynamic"))})
  {
   FArrayProperty* Property = FindFProperty<FArrayProperty>(Component->GetClass(), Name);
   const FObjectPropertyBase* Inner = Property ? CastField<FObjectPropertyBase>(Property->Inner) : nullptr;
   if (!Inner) return -1;
   FScriptArrayHelper Items(Property, Property->ContainerPtrToValuePtr<void>(Component));
   if (Name == FName(TEXT("MaterialInstances")) && Items.Num() == 0) return -1;
   for (int32 Index = 0; Index < Items.Num(); ++Index)
   {
    UMaterialInterface* Root = Cast<UMaterialInterface>(Inner->GetObjectPropertyValue(Items.GetRawPtr(Index)));
    TSet<UMaterialInterface*> Seen;
    while (UMaterialInstance* Instance = Cast<UMaterialInstance>(Root))
    {
     if (Seen.Contains(Root)) return -1;
     Seen.Add(Root); Root = Instance->Parent;
    }
    if (!IsValid(Root) || Root->GetOutermost()->GetName() != Parent) return -1;
    ++Count;
   }
  }
  return Count;
 }
 void MoveCamera(double Alpha)
 {
  const auto V = Views[View]->AsObject();
  auto Vector=[](const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());};
  const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
  TSharedPtr<FJsonObject> A = V, B = V;
  double Blend = 0;
  if (V->TryGetArrayField(TEXT("path"), Path))
  {
   if (Path->Num() < 3) { Test->AddError(TEXT("Incomplete camera traversal")); return; }
   const double Position = Alpha * (Path->Num() - 1);
   const int32 Index = FMath::Min(FMath::FloorToInt(Position), Path->Num() - 2);
   A = (*Path)[Index]->AsObject(); B = (*Path)[Index + 1]->AsObject(); Blend = Position - Index;
  }
  const FVector Position = FMath::Lerp(Vector(A->GetArrayField(TEXT("location_cm"))), Vector(B->GetArrayField(TEXT("location_cm"))), Blend);
  const FVector Target = FMath::Lerp(Vector(A->GetArrayField(TEXT("target_cm"))), Vector(B->GetArrayField(TEXT("target_cm"))), Blend);
  Camera->SetActorLocation(Position); Camera->SetActorRotation((Target-Position).Rotation());
  Camera->GetCameraComponent()->SetFieldOfView(FMath::Lerp(A->GetNumberField(TEXT("fov_deg")), B->GetNumberField(TEXT("fov_deg")), Blend));
 }
 bool Fail(const TCHAR* Message) { Test->AddError(Message); return true; }
 void BeginView()
 {
  const auto V=Views[View]->AsObject(); Sector=V->GetStringField(TEXT("name"));
  auto Vector=[](const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());};
  if (bConsumer) MoveCamera(0);
  else
  {
   FVector Position=Vector(V->GetArrayField(TEXT("location_cm")));
   FVector Target=Vector(V->GetArrayField(TEXT("target_cm")));
   Camera->SetActorLocation(Position); Camera->SetActorRotation((Target-Position).Rotation());
  }
  Start=FPlatformTime::Seconds();
 }
 FAutomationTestBase* Test; UWorld* World=nullptr; ACameraActor* Camera=nullptr;
 TArray<TSharedPtr<FJsonValue>> Views; int32 View=0; double Start=0;
 FString Csv, Sector, Buffer; bool bConsumer=false; FRHIGPUFrameTimeHistory::FState GpuState;
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingSaCalobraPerformanceTest,
 "CyclingRuntime.SaCalobraTerrainPerformanceProof",EAutomationTestFlags::ClientContext|EAutomationTestFlags::PerfFilter)
bool FCyclingSaCalobraPerformanceTest::RunTest(const FString&)
{
 if (FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_SA_PERF_CSV")).IsEmpty())
 { AddError(TEXT("Explicit Sa Calobra performance harness required")); return false; }
 ADD_LATENT_AUTOMATION_COMMAND(FSaCalobraPerformanceCommand(this)); return true;
}
#endif
