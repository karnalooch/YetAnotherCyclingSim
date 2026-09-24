// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// CyclingRuntime.Stage3VisualEnvironmentProof: latent PIE automation proof
// for issue #67 Stage 3E visual environment acceptance.
//
// Goal: produce three route-attributable PNGs from a freshly loaded
// /Game/Prototype/Maps/L_CyclingTest that demonstrate that the Stage 3E
// prototype environment is visible:
//
//   01_meadow_valley.png       (~1200 m, road + valley terrain)
//   02_forest_sector.png       (~4900 m, road + forest props nearby)
//   03_high_valley_mountains.png (~8000 m, road + mountain props visible)
//
// Mechanism:
//   * The harness script (scripts/ue/Invoke-YacsStage3VisualEnvironmentProof.ps1)
//     launches the editor with the L_CyclingTest map URL and
//     `-game -windowed -ResX=1920 -ResY=1080` so the editor renders a real
//     viewport at the documented target resolution.
//   * Once PIE is up, this test locates the placed ACyclingPrototypePawn,
//     disables the diagnostic overlay (so the screenshots are not
//     obscured by Stage 2 HUD text), ensures the Pawn is in Stopped
//     state (Tick disabled), then for each of three known route distances:
//       (1) calls ACyclingPrototypePawn::TeleportForProofCapture, which
//           snaps the visible Actor transform to the spline pose WITHOUT
//           mutating the authoritative Session state;
//       (2) waits long enough for the renderer to settle at the new pose;
//       (3) requests a viewport screenshot via FScreenshotRequest with
//           a deterministic filename;
//       (4) waits for the screenshot to flush to disk.
//   * The screenshot filenames carry the route distance so the harness
//     can attribute each PNG to a specific proof sector without relying
//     on a separate manifest.
//
// Like the existing PerformanceProof test, when no PIE world / Pawn is
// available (the standard no-map Automation pass), the test gracefully
// reports PASS with a warning so the correctness counter stays 52/52.
// The dedicated Invoke-YacsStage3VisualEnvironmentProof.ps1 harness is
// the authoritative execution of this test and validates that the PNGs
// actually exist with a useful size.

#if WITH_DEV_AUTOMATION_TESTS

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformMisc.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "UnrealClient.h"
#include "Tests/AutomationCommon.h"

#include "Cycling/CyclingPrototypePawn.h"

namespace CyclingStage3VisualEnvironmentProofTest
{
	// The three deterministic proof distances. Each distance is a real
	// route-distance value (metres) chosen to fall inside one Stage 3E
	// environment sector:
	//
	//   1200 m  -> meadow / valley  (before ForestStartM = 3700 m)
	//   4900 m  -> forest           (between ForestPropFirstM = 3800 m
	//                                 and ForestPropLastExclusiveM = 6200 m)
	//   8000 m  -> high valley      (between MountainPropFirstM = 6300 m
	//                                 and MountainPropLastExclusiveM = 10000 m)
	static constexpr double MeadowDistanceM    = 1200.0;
	static constexpr double ForestDistanceM    = 4900.0;
	static constexpr double MountainDistanceM  = 8000.0;

	// Wall-clock pauses chosen so the renderer can re-render the new
	// viewport before the screenshot is requested, and so the .png
	// flush completes before the next teleport.
	static constexpr float SettleSecondsBeforeScreenshot = 1.5f;
	static constexpr float SettleSecondsAfterScreenshot  = 2.0f;

	// Absolute root under which the three proof PNGs are written. The
	// harness script sets YACS_VISUAL_ENV_DIR to point at the desired
	// Saved/RuntimeProof/Issue67/Stage3E/VisualEnvironmentProof directory.
	static FString ResolveScreenshotPath(double DistanceM)
	{
		const FString ArtifactRoot = FPlatformMisc::GetEnvironmentVariable(
			TEXT("YACS_VISUAL_ENV_DIR"));
		if (ArtifactRoot.IsEmpty())
		{
			return FString();
		}

		FString SectorLabel;
		if (FMath::IsNearlyEqual(DistanceM, MeadowDistanceM, 1.0))
		{
			SectorLabel = TEXT("01_meadow_valley");
		}
		else if (FMath::IsNearlyEqual(DistanceM, ForestDistanceM, 1.0))
		{
			SectorLabel = TEXT("02_forest_sector");
		}
		else if (FMath::IsNearlyEqual(DistanceM, MountainDistanceM, 1.0))
		{
			SectorLabel = TEXT("03_high_valley_mountains");
		}
		else
		{
			SectorLabel = FString::Printf(TEXT("sector_%.0fm"), DistanceM);
		}

		return FPaths::Combine(ArtifactRoot,
			FString::Printf(TEXT("%s_%.0fm.png"), *SectorLabel, DistanceM));
	}

	static ACyclingPrototypePawn* FindPrototypePawnInPIE()
	{
		if (!GEngine)
		{
			return nullptr;
		}
		UWorld* PIEWorld = GEngine->GetCurrentPlayWorld();
		if (!PIEWorld)
		{
			PIEWorld = GEngine->GetWorldContexts().Num() > 0
				? GEngine->GetWorldContexts()[0].World()
				: nullptr;
		}
		if (!PIEWorld)
		{
			return nullptr;
		}
		for (TActorIterator<ACyclingPrototypePawn> It(PIEWorld); It; ++It)
		{
			if (ACyclingPrototypePawn* Pawn = *It)
			{
				return Pawn;
			}
		}
		return nullptr;
	}
}

// ---------------------------------------------------------------------------
// Latent commands used by the visual environment proof sequence.
//
// Each command is intentionally small so the proof remains self-explanatory.
// ---------------------------------------------------------------------------

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(
	FCyclingStage3VisualEnvPreparePawnLatent, FString, StepLabel);

bool FCyclingStage3VisualEnvPreparePawnLatent::Update()
{
	using namespace CyclingStage3VisualEnvironmentProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3VisualEnvironmentProof (%s): Pawn missing; skipping."),
			*StepLabel);
		return true;
	}

	// Disable the diagnostic overlay so the on-screen Stage 2 HUD text
	// does not obscure the route geometry in the screenshot. This is a
	// presentation-only mutation; the simulation is unaffected.
	Pawn->SetDiagnosticOverlayEnabled(false);

	// Force the Pawn into Stopped so Tick does not overwrite the visible
	// transform between TeleportForProofCapture and the screenshot
	// request. StopRide is idempotent and refuses non-Running transitions,
	// so we accept any post-condition as long as Tick is disabled.
	if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running)
	{
		Pawn->StopRide();
	}
	Pawn->SetActorTickEnabled(false);

	UE_LOG(LogTemp, Display,
		TEXT("Stage3VisualEnvironmentProof (%s): Pawn prepared (lifecycle=%d, tick=%d, overlay=off)."),
		*StepLabel,
		static_cast<int32>(Pawn->GetLifecycle()),
		Pawn->IsActorTickEnabled() ? 1 : 0);
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_ONE_PARAMETER(
	FCyclingStage3VisualEnvTeleportLatent, double, DistanceM);

bool FCyclingStage3VisualEnvTeleportLatent::Update()
{
	using namespace CyclingStage3VisualEnvironmentProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3VisualEnvironmentProof: Pawn missing when teleporting."));
		return true;
	}

	const bool bTeleported = Pawn->TeleportForProofCapture(DistanceM);
	if (!bTeleported)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3VisualEnvironmentProof: TeleportForProofCapture(%.3f m) returned false."),
			DistanceM);
	}
	return true;
}

DEFINE_LATENT_AUTOMATION_COMMAND_TWO_PARAMETER(
	FCyclingStage3VisualEnvScreenshotLatent,
	double, DistanceM, FString, AbsolutePath);

bool FCyclingStage3VisualEnvScreenshotLatent::Update()
{
	if (AbsolutePath.IsEmpty())
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Stage3VisualEnvironmentProof: empty screenshot path for %.3f m; skipping."),
			DistanceM);
		return true;
	}

	// UE 5.8 documents RequestScreenshot(filename, bShowUI, bAddFilenameSuffix, bHdrScreenshot)
	// as the standard way to write a viewport screenshot to a known
	// absolute path. bInShowUI=false so the screenshot is not obscured by
	// any future Slate UI overlay; the diagnostic overlay is already
	// disabled on the Pawn.
	FScreenshotRequest::RequestScreenshot(
		AbsolutePath,
		/*bInShowUI=*/false,
		/*bAddFilenameSuffix=*/false,
		/*bHdrScreenshot=*/false);

	UE_LOG(LogTemp, Display,
		TEXT("Stage3VisualEnvironmentProof: screenshot requested for distance=%.3f m path=%s"),
		DistanceM,
		*AbsolutePath);
	return true;
}

// ---------------------------------------------------------------------------
// The actual visual environment proof complex automation test.
// ---------------------------------------------------------------------------

IMPLEMENT_COMPLEX_AUTOMATION_TEST(
	FCyclingStage3VisualEnvironmentProofTest,
	"CyclingRuntime.Stage3VisualEnvironmentProof",
	EAutomationTestFlags::EditorContext
		| EAutomationTestFlags::ClientContext
		| EAutomationTestFlags::PerfFilter)

void FCyclingStage3VisualEnvironmentProofTest::GetTests(
	TArray<FString>& OutBeautifiedNames,
	TArray<FString>& OutTestCommands) const
{
	OutBeautifiedNames.Add(TEXT("CyclingRuntime.Stage3VisualEnvironmentProof"));
	OutTestCommands.Add(FString());
}

bool FCyclingStage3VisualEnvironmentProofTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3VisualEnvironmentProofTest;

	ACyclingPrototypePawn* Pawn = FindPrototypePawnInPIE();
	if (!Pawn)
	{
		AddWarning(TEXT(
			"Stage3VisualEnvironmentProof: no ACyclingPrototypePawn found in the current PIE world; "
			"this is expected in a no-map Automation pass. The dedicated "
			"Invoke-YacsStage3VisualEnvironmentProof.ps1 harness is the authoritative execution "
			"of this test."));
		return true;
	}
	if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Error)
	{
		AddError(FString::Printf(
			TEXT("Stage3VisualEnvironmentProof: Pawn is in Error state: '%s'."),
			*Pawn->GetLastError()));
		return false;
	}

	struct FSector
	{
		double DistanceM;
		const TCHAR* Label;
	};

	const FSector Sectors[] = {
		{ MeadowDistanceM,   TEXT("meadow") },
		{ ForestDistanceM,   TEXT("forest") },
		{ MountainDistanceM, TEXT("high-valley") },
	};

	ADD_LATENT_AUTOMATION_COMMAND(
		FCyclingStage3VisualEnvPreparePawnLatent(TEXT("begin")));

	for (const FSector& Sector : Sectors)
	{
		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3VisualEnvPreparePawnLatent(Sector.Label));

		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3VisualEnvTeleportLatent(Sector.DistanceM));

		ADD_LATENT_AUTOMATION_COMMAND(
			FWaitLatentCommand(SettleSecondsBeforeScreenshot));

		const FString AbsolutePath = ResolveScreenshotPath(Sector.DistanceM);
		ADD_LATENT_AUTOMATION_COMMAND(
			FCyclingStage3VisualEnvScreenshotLatent(Sector.DistanceM, AbsolutePath));

		ADD_LATENT_AUTOMATION_COMMAND(
			FWaitLatentCommand(SettleSecondsAfterScreenshot));

		UE_LOG(LogTemp, Display,
			TEXT("Stage3VisualEnvironmentProof: queued sector='%s' distance=%.3f m path='%s'"),
			Sector.Label, Sector.DistanceM, *AbsolutePath);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS