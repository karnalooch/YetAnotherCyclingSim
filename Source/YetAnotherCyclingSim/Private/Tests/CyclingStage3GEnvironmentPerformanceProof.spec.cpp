// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Stage 3G environment performance gate.
//
// This is deliberately separate from CyclingRuntime.PerformanceProof (the
// Stage 2 baseline). It measures the actual rendered Stage 3G reference world
// at the three stable Visual History route distances: 1200 / 4900 / 8000 m.
//
// The companion PowerShell harness owns the acceptance policy. This test only
// produces exact-sector per-frame timing evidence from a real 1920x1080
// rendered PIE viewport.

#if WITH_DEV_AUTOMATION_TESTS

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Engine/Engine.h"\n#include "EngineGlobals.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Tests/AutomationCommon.h"
#include "RenderTimer.h"

#include "Cycling/CyclingPrototypePawn.h"

namespace CyclingStage3GEnvironmentPerformanceProofTest
{
	static constexpr double ValleyDistanceM = 1200.0;
	static constexpr double ForestDistanceM = 4900.0;
	static constexpr double HighAlpineDistanceM = 8000.0;

	static constexpr float SettleSeconds = 2.0f;
	static constexpr float SampleSeconds = 8.0f;

	static ACyclingPrototypePawn* FindPrototypePawnInPIE()
	{
		if (!GEngine)
		{
			return nullptr;
		}

		UWorld* PIEWorld = GEngine->GetCurrentPlayWorld();
		if (!PIEWorld && GEngine->GetWorldContexts().Num() > 0)
		{
			PIEWorld = GEngine->GetWorldContexts()[0].World();
		}
		if (!PIEWorld)
		{
			return nullptr;
		}

		for (TActorIterator<ACyclingPrototypePawn> It(PIEWorld); It; ++It)
		{
			return *It;
		}
		return nullptr;
	}

	static FString ResolveCsvPath()
	{
		return FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_STAGE3G_PERF_CSV"));
	}
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(
	FCyclingStage3GPerfPreparePawnLatent, FString, Label);

bool FCyclingStage3GPerfPreparePawnLatent::Update()
{
	using namespace CyclingStage3GEnvironmentPerformanceProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3GEnvironmentPerformanceProof (%s): Pawn missing."),
			*Label);
		return true;
	}

	Pawn->SetDiagnosticOverlayEnabled(false);
	if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running)
	{
		Pawn->StopRide();
	}
	Pawn->SetActorTickEnabled(false);

	UE_LOG(LogTemp, Display,
		TEXT("Stage3GEnvironmentPerformanceProof (%s): pawn prepared."),
		*Label);
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(
	FCyclingStage3GPerfTeleportLatent, double, DistanceM, FString, Sector);

bool FCyclingStage3GPerfTeleportLatent::Update()
{
	using namespace CyclingStage3GEnvironmentPerformanceProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3GEnvironmentPerformanceProof: Pawn missing for sector %s."),
			*Sector);
		return true;
	}

	if (!Pawn->TeleportForProofCapture(DistanceM))
	{
		UE_LOG(LogTemp, Error,
			TEXT("Stage3GEnvironmentPerformanceProof: TeleportForProofCapture failed sector=%s distance=%.3f."),
			*Sector,
			DistanceM);
	}
	else
	{
		UE_LOG(LogTemp, Display,
			TEXT("Stage3GEnvironmentPerformanceProof: sector=%s distance=%.3f ready."),
			*Sector,
			DistanceM);
	}
	return true;
}

class FCyclingStage3GPerfSampleLatent final : public IAutomationLatentCommand
{
public:
	FCyclingStage3GPerfSampleLatent(
		FString InSector,
		double InDistanceM,
		float InDurationS)
		: Sector(MoveTemp(InSector))
		, DistanceM(InDistanceM)
		, DurationS(InDurationS)
	{
	}

	virtual bool Update() override
	{
		using namespace CyclingStage3GEnvironmentPerformanceProofTest;

		const FString CsvPath = ResolveCsvPath();
		if (CsvPath.IsEmpty())
		{
			UE_LOG(LogTemp, Error,
				TEXT("Stage3GEnvironmentPerformanceProof: YACS_STAGE3G_PERF_CSV is not set."));
			return true;
		}

		const double Now = FPlatformTime::Seconds();
		if (StartTime <= 0.0)
		{
			StartTime = Now;
		}

		const double FrameMs = FApp::GetDeltaTime() * 1000.0;
		const double GameMs = FPlatformTime::ToMilliseconds(GGameThreadTime);
		const double DrawMs = FPlatformTime::ToMilliseconds(GRenderThreadTime);
		const double RHIMs = FPlatformTime::ToMilliseconds(GRHIThreadTime);

		double FrameAvgMs = 0.0;
		// GetAverageUnitTimes may report 0 for GPU in an unattended editor
		// viewport even when D3D12 timing is available. GGPUFrameTime is the
		// engine's last-rendered-frame GPU duration in platform cycles and is
		// also used by GameViewportClient when reasoning about frame rate.
		double GpuMs = FPlatformTime::ToMilliseconds(GGPUFrameTime);
		double RenderAvgMs = 0.0;
		double RhiAvgMs = 0.0;
		if (GEngine)
		{
			TArray<float> Averages;
			GEngine->GetAverageUnitTimes(Averages);
			if (Averages.Num() >= 5)
			{
				FrameAvgMs = static_cast<double>(Averages[0]);
				const double AveragedGpuMs = static_cast<double>(Averages[2]);
				if (GpuMs <= 0.01 && AveragedGpuMs > 0.01)
				{
					GpuMs = AveragedGpuMs;
				}
				RenderAvgMs = static_cast<double>(Averages[3]);
				RhiAvgMs = static_cast<double>(Averages[4]);
			}
		}

		const double RelS = Now - StartTime;
		const FString Row = FString::Printf(
			TEXT("%s,%.1f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n"),
			*Sector,
			DistanceM,
			RelS,
			FrameMs,
			GameMs,
			DrawMs,
			RHIMs,
			FrameAvgMs,
			GpuMs,
			RenderAvgMs,
			RhiAvgMs);

		if (!bHeaderWritten)
		{
			const FString Header =
				TEXT("sector,distance_m,rel_s,frame_ms,game_ms,draw_ms,rhi_ms,frame_avg_ms,gpu_ms,render_avg_ms,rhi_avg_ms\n");

			if (!IFileManager::Get().FileExists(*CsvPath))
			{
				FFileHelper::SaveStringToFile(
					Header,
					*CsvPath,
					FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
			}
			bHeaderWritten = true;
		}

		FFileHelper::SaveStringToFile(
			Row,
			*CsvPath,
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
			&IFileManager::Get(),
			FILEWRITE_Append);

		if (RelS < static_cast<double>(DurationS))
		{
			return false;
		}

		UE_LOG(LogTemp, Display,
			TEXT("Stage3GEnvironmentPerformanceProof: sampled sector=%s distance=%.1f duration=%.3f s."),
			*Sector,
			DistanceM,
			RelS);
		return true;
	}

private:
	FString Sector;
	double DistanceM = 0.0;
	float DurationS = 0.0f;
	double StartTime = 0.0;
	bool bHeaderWritten = false;
};

IMPLEMENT_COMPLEX_AUTOMATION_TEST(
	FCyclingStage3GEnvironmentPerformanceProofTest,
	"CyclingRuntime.Stage3GEnvironmentPerformanceProof",
	EAutomationTestFlags::EditorContext
		| EAutomationTestFlags::ClientContext
		| EAutomationTestFlags::PerfFilter)

void FCyclingStage3GEnvironmentPerformanceProofTest::GetTests(
	TArray<FString>& OutBeautifiedNames,
	TArray<FString>& OutTestCommands) const
{
	OutBeautifiedNames.Add(TEXT("CyclingRuntime.Stage3GEnvironmentPerformanceProof"));
	OutTestCommands.Add(FString());
}

bool FCyclingStage3GEnvironmentPerformanceProofTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3GEnvironmentPerformanceProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		AddWarning(TEXT(
			"Stage3GEnvironmentPerformanceProof: no ACyclingPrototypePawn found; "
			"expected in generic no-map Automation. The dedicated harness is authoritative."));
		return true;
	}
	if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Error)
	{
		AddError(FString::Printf(
			TEXT("Stage3GEnvironmentPerformanceProof: Pawn Error state: %s"),
			*Pawn->GetLastError()));
		return false;
	}

	struct FSector
	{
		const TCHAR* Name;
		double DistanceM;
	};

	const FSector Sectors[] = {
		{ TEXT("valley"), ValleyDistanceM },
		{ TEXT("forest"), ForestDistanceM },
		{ TEXT("high_alpine"), HighAlpineDistanceM },
	};

	ADD_LATENT_AUTOMATION_COMMAND(
		FCyclingStage3GPerfPreparePawnLatent(TEXT("begin")));

	for (const FSector& Sector : Sectors)
	{
		const FString SectorName(Sector.Name);

		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3GPerfPreparePawnLatent(SectorName));

		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3GPerfTeleportLatent(
				Sector.DistanceM,
				SectorName));

		ADD_LATENT_AUTOMATION_COMMAND(
			FWaitLatentCommand(SettleSeconds));

		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3GPerfSampleLatent(
				SectorName,
				Sector.DistanceM,
				SampleSeconds));
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
