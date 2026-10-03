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
   if (World->GetPackage()->GetName() != TEXT("/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"))
    return Fail(TEXT("Wrong performance map"));
   int32 Landscapes=0, Components=0;
   for (TActorIterator<ALandscape> It(World); It; ++It)
   { ++Landscapes; TArray<ULandscapeComponent*> Items; It->GetComponents(Items); Components += Items.Num(); }
   if (Landscapes != 1 || Components != 1024) return Fail(TEXT("Landscape topology mismatch"));
   if (!GRHIAdapterName.Contains(TEXT("RTX 2070")) || !GRHIAdapterName.Contains(TEXT("SUPER")))
    return Fail(TEXT("Active RHI GPU is not RTX 2070 SUPER"));
   if (!GEngine->GameViewport || !GEngine->GameViewport->Viewport ||
       GEngine->GameViewport->Viewport->GetSizeXY() != FIntPoint(1920,1080))
    return Fail(TEXT("Actual game viewport is not 1920x1080"));
   Csv = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_SA_PERF_CSV"));
   const FString SettingsPath = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_SA_PERF_SETTINGS"));
   FString Text; TSharedPtr<FJsonObject> Settings;
   if (Csv.IsEmpty() || !FFileHelper::LoadFileToString(Text,*SettingsPath) ||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Settings))
    return Fail(TEXT("Missing performance settings"));
   Views = Settings->GetArrayField(TEXT("views"));
   if (Views.Num()!=3) return Fail(TEXT("Expected three fixed views"));
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
   ADirectionalLight* Sun=World->SpawnActor<ADirectionalLight>();
   ASkyLight* Sky=World->SpawnActor<ASkyLight>();
   if (!Sun || !Sky) return Fail(TEXT("Lighting unavailable"));
   Sun->SetActorRotation(FRotator(-33,-48,0));
   Sun->GetLightComponent()->SetIntensity(8.0f);
   Sun->GetLightComponent()->SetCastShadows(false);
   Sky->GetLightComponent()->SetIntensity(0.8f);
   if (!FFileHelper::SaveStringToFile(TEXT("sector,rel_s,frame_ms,game_ms,draw_ms,rhi_ms,gpu_ms\n"),*Csv))
    return Fail(TEXT("Cannot create timing CSV"));
   FString Identity=FString::Printf(TEXT("{\"MapPackage\":\"%s\",\"ComponentCount\":%d,\"ActiveGpu\":\"%s\",\"Resolution\":\"1920x1080\"}"),*World->GetPackage()->GetName(),Components,*GRHIAdapterName);
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
  Buffer+=FString::Printf(TEXT("%s,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n"),*Sector,Elapsed,
   FApp::GetDeltaTime()*1000.0,FPlatformTime::ToMilliseconds(GGameThreadTime),
   FPlatformTime::ToMilliseconds(GRenderThreadTime),FPlatformTime::ToMilliseconds(GRHIThreadTime),GpuMs);
  if (Elapsed<8.0) return false;
  if (!FFileHelper::SaveStringToFile(Buffer,*Csv,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append))
   return Fail(TEXT("Cannot append timing CSV"));
  Buffer.Empty();
  if (++View==3) return true;
  BeginView(); return false;
 }
private:
 bool Fail(const TCHAR* Message) { Test->AddError(Message); return true; }
 void BeginView()
 {
  const auto V=Views[View]->AsObject(); Sector=V->GetStringField(TEXT("name"));
  auto Vector=[](const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());};
  FVector Position=Vector(V->GetArrayField(TEXT("location_cm")));
  FVector Target=Vector(V->GetArrayField(TEXT("target_cm")));
  Camera->SetActorLocation(Position); Camera->SetActorRotation((Target-Position).Rotation());
  Start=FPlatformTime::Seconds();
 }
 FAutomationTestBase* Test; UWorld* World=nullptr; ACameraActor* Camera=nullptr;
 TArray<TSharedPtr<FJsonValue>> Views; int32 View=0; double Start=0;
 FString Csv, Sector, Buffer; FRHIGPUFrameTimeHistory::FState GpuState;
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
