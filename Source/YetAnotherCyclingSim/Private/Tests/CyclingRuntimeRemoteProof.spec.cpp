// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// RemoteProof: deterministic end-to-end exercise of the runtime layer
// driving the cycling session directly through the existing
// FCyclingSimulationSession API. This is the replacement for the manual
// Stage 2 proof that required a human to drive the keyboard under PIE.
//
// The test does NOT synthesise OS keyboard events. It calls the domain
// methods directly so the physics oracle is independent of the human
// interaction proof. Keyboard-binding responsiveness remains a separate
// interaction proof (already covered by CyclingInputBinding.spec.cpp and
// the human PIE pass).
//
// Scenarios covered:
//
//   1.  Ready          -> StartRide -> Running.
//   2.  Running        -> Power step up via TryIncreasePower.
//   3.  Running        -> Cadence step up via TryIncreaseCadence.
//   4.  Running        -> StopRide -> Stopped (pause, state preserved).
//   5.  Stopped        -> StartRide -> Running (resume, preserved state).
//   6.  Running        -> RestartRide -> Running from zero (reset).
//   7.  Restarted      -> drive until route completion -> Finished.
//   8.  Finished       -> visible transform clamped to route end;
//       authoritative DistanceM may overshoot.
//   9.  Finished       -> StartRide is a no-op (must Restart to recover).
//   10. Restart         -> StartRide is valid (Running).

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Components/SplineComponent.h"
#include "Components/SceneComponent.h"
#include "GameFramework/Actor.h"

#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/CyclingSimulationSession.h"

namespace CyclingRuntimeRemoteProofTest
{
	UWorld* CreateTransientWorld()
	{
		return UWorld::CreateWorld(EWorldType::Game, false, TEXT("CyclingRuntimeRemoteProofWorld"));
	}

	void DestroyTransientWorld(UWorld* World)
	{
		if (World)
		{
			World->DestroyWorld(false);
		}
	}

	AActor* SpawnStraightRouteActor(UWorld* World, float LengthCm)
	{
		AActor* RouteActor = World->SpawnActor<AActor>();
		if (!RouteActor)
		{
			return nullptr;
		}
		USceneComponent* RouteRoot = NewObject<USceneComponent>(RouteActor, USceneComponent::StaticClass(), TEXT("RouteRoot"));
		RouteRoot->SetMobility(EComponentMobility::Movable);
		RouteActor->SetRootComponent(RouteRoot);
		RouteRoot->RegisterComponent();

		USplineComponent* Spline = NewObject<USplineComponent>(RouteActor, USplineComponent::StaticClass(), TEXT("RouteSpline"));
		Spline->SetMobility(EComponentMobility::Movable);
		Spline->SetupAttachment(RouteRoot);
		Spline->RegisterComponent();

		Spline->ClearSplinePoints(false);
		Spline->AddSplinePoint(FVector(0.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
		Spline->AddSplinePoint(FVector(LengthCm, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
		Spline->UpdateSpline();
		return RouteActor;
	}

	ACyclingPrototypePawn* SpawnPrototypePawn(UWorld* World, AActor* RouteActor)
	{
		ACyclingPrototypePawn* Pawn = World->SpawnActor<ACyclingPrototypePawn>();
		if (!Pawn) { return nullptr; }
		Pawn->RouteActor = RouteActor;
		Pawn->bAutoStart = false;
		return Pawn;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FCyclingRuntimeRemoteProofTest,
	"CyclingRuntime.RemoteProof",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimeRemoteProofTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeRemoteProofTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f); // 500 m
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	if (!Pawn)
	{
		AddError(TEXT("Failed to spawn Pawn."));
		DestroyTransientWorld(World);
		return false;
	}

	FString Error;
	auto Expect = [&](const TCHAR* Label, bool bOk)
	{
		TestTrue(Label, bOk);
	};

	// -------------------------------------------------------------------
	// (1) Initialise -> Ready.
	// -------------------------------------------------------------------
	Pawn->InitializeRide();
	Expect(TEXT("step 1: lifecycle is Ready after InitializeRide"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Ready);
	Expect(TEXT("step 1: session is configured"),
		Pawn->GetSession().IsConfigured());
	Expect(TEXT("step 1: actor at spline origin X"),
		FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));

	// -------------------------------------------------------------------
	// (2) Ready -> StartRide -> Running.
	// -------------------------------------------------------------------
	Pawn->StartRide();
	Expect(TEXT("step 2: lifecycle is Running after StartRide"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running);
	Expect(TEXT("step 2: Tick is enabled after StartRide"),
		Pawn->IsActorTickEnabled());

	// -------------------------------------------------------------------
	// (3) Power step up via the existing TryIncreasePower API.
	// -------------------------------------------------------------------
	const double PowerBefore = Pawn->GetSession().GetRiderInput().PowerW;
	Expect(TEXT("step 3: power step up succeeds"),
		Pawn->GetMutableSession().TryIncreasePower(Error));
	const double PowerAfter = Pawn->GetSession().GetRiderInput().PowerW;
	Expect(TEXT("step 3: power increased by the configured step"),
		FMath::IsNearlyEqual(PowerAfter - PowerBefore, 10.0, 1e-9));

	// -------------------------------------------------------------------
	// (4) Cadence step up via the existing TryIncreaseCadence API.
	// -------------------------------------------------------------------
	const double CadenceBefore = Pawn->GetSession().GetRiderInput().CadenceRpm;
	Expect(TEXT("step 4: cadence step up succeeds"),
		Pawn->GetMutableSession().TryIncreaseCadence(Error));
	const double CadenceAfter = Pawn->GetSession().GetRiderInput().CadenceRpm;
	Expect(TEXT("step 4: cadence increased by the configured step"),
		FMath::IsNearlyEqual(CadenceAfter - CadenceBefore, 5.0, 1e-9));

	// -------------------------------------------------------------------
	// (5) Drive a meaningful horizon and capture Running-state snapshot.
	// -------------------------------------------------------------------
	Pawn->Tick(0.5f); // 10 fixed steps
	Pawn->Tick(0.04f); // leaves a sub-step in the accumulator
	const FSimulationState RunningSnapshot = Pawn->GetAuthoritativeState();
	const double AccumulatorBeforeStop = Pawn->GetSession().GetAccumulatedTimeS();
	Expect(TEXT("step 5: speed > 0 after a short ride"),
		RunningSnapshot.SpeedMps > 0.0);
	Expect(TEXT("step 5: distance > 0 after a short ride"),
		RunningSnapshot.DistanceM > 0.0);
	Expect(TEXT("step 5: accumulator strictly positive (sub-step pending)"),
		AccumulatorBeforeStop > 0.0);

	// -------------------------------------------------------------------
	// (6) StopRide -> Stopped (pause, preserve state).
	// -------------------------------------------------------------------
	Pawn->StopRide();
	Expect(TEXT("step 6: lifecycle is Stopped after StopRide"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Stopped);
	Expect(TEXT("step 6: Tick disabled after StopRide"),
		!Pawn->IsActorTickEnabled());
	Expect(TEXT("step 6: authoritative speed preserved across StopRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().SpeedMps, RunningSnapshot.SpeedMps, 0.0));
	Expect(TEXT("step 6: authoritative distance preserved across StopRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().DistanceM, RunningSnapshot.DistanceM, 0.0));
	Expect(TEXT("step 6: authoritative elapsed time preserved across StopRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().ElapsedTimeS, RunningSnapshot.ElapsedTimeS, 0.0));
	Expect(TEXT("step 6: accumulator preserved across StopRide"),
		FMath::IsNearlyEqual(Pawn->GetSession().GetAccumulatedTimeS(), AccumulatorBeforeStop, 0.0));

	// -------------------------------------------------------------------
	// (7) StartRide resumes without resetting.
	// -------------------------------------------------------------------
	Pawn->StartRide();
	Expect(TEXT("step 7: lifecycle is Running after resume"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running);
	Expect(TEXT("step 7: Tick re-enabled after resume"),
		Pawn->IsActorTickEnabled());
	Expect(TEXT("step 7: authoritative speed preserved across Stop/Start"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().SpeedMps, RunningSnapshot.SpeedMps, 0.0));
	Expect(TEXT("step 7: authoritative distance preserved across Stop/Start"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().DistanceM, RunningSnapshot.DistanceM, 0.0));
	Expect(TEXT("step 7: accumulator preserved across Stop/Start"),
		FMath::IsNearlyEqual(Pawn->GetSession().GetAccumulatedTimeS(), AccumulatorBeforeStop, 0.0));

	// -------------------------------------------------------------------
	// (8) RestartRide -> Running from zero.
	// -------------------------------------------------------------------
	Pawn->RestartRide();
	Expect(TEXT("step 8: lifecycle is Running after RestartRide"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running);
	Expect(TEXT("step 8: Tick enabled after RestartRide"),
		Pawn->IsActorTickEnabled());
	Expect(TEXT("step 8: speed reset to 0 after RestartRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().SpeedMps, 0.0, 0.0));
	Expect(TEXT("step 8: distance reset to 0 after RestartRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().DistanceM, 0.0, 0.0));
	Expect(TEXT("step 8: elapsed reset to 0 after RestartRide"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().ElapsedTimeS, 0.0, 0.0));
	Expect(TEXT("step 8: accumulator reset to 0 after RestartRide"),
		FMath::IsNearlyEqual(Pawn->GetSession().GetAccumulatedTimeS(), 0.0, 0.0));
	Expect(TEXT("step 8: power restored to initial 200 W"),
		FMath::IsNearlyEqual(Pawn->GetSession().GetRiderInput().PowerW, 200.0, 0.0));
	Expect(TEXT("step 8: cadence restored to initial 90 rpm"),
		FMath::IsNearlyEqual(Pawn->GetSession().GetRiderInput().CadenceRpm, 90.0, 0.0));
	Expect(TEXT("step 8: actor snapped to spline origin"),
		FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));

	// -------------------------------------------------------------------
	// (9) Drive until route completion -> Finished.
	//     500 m on flat ground at 200 W takes ~63 s of simulated time.
	//     Drive up to 80 s in 0.5 s chunks.
	// -------------------------------------------------------------------
	bool bReachedFinished = false;
	for (int32 i = 0; i < 160; ++i)
	{
		Pawn->Tick(0.5f);
		if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
		{
			bReachedFinished = true;
			break;
		}
	}
	Expect(TEXT("step 9: lifecycle reached Finished within 80 s"),
		bReachedFinished);
	Expect(TEXT("step 9: Tick disabled at Finished"),
		!Pawn->IsActorTickEnabled());
	Expect(TEXT("step 9: authoritative distance >= route length 500 m"),
		Pawn->GetAuthoritativeState().DistanceM >= 500.0);
	Expect(TEXT("step 9: authoritative distance has only a small overshoot (<= 510 m)"),
		Pawn->GetAuthoritativeState().DistanceM <= 510.0);
	Expect(TEXT("step 9: visible X is clamped to spline end (50000 cm)"),
		FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 50000.0f, 0.5f));

	// -------------------------------------------------------------------
	// (10) Finished is a sticky state: StartRide must NOT silently
	//      transition back to Running (Restart is required to recover
	//      from overshoot). This protects the user from losing
	//      awareness that the route is over.
	// -------------------------------------------------------------------
	Pawn->StartRide();
	Expect(TEXT("step 10: StartRide in Finished is a documented no-op"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished);
	Expect(TEXT("step 10: Tick remains disabled in Finished after StartRide"),
		!Pawn->IsActorTickEnabled());

	// -------------------------------------------------------------------
	// (11) Restart from Finished recovers to Running.
	// -------------------------------------------------------------------
	Pawn->RestartRide();
	Expect(TEXT("step 11: Restart from Finished returns to Running"),
		Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Running);
	Expect(TEXT("step 11: Tick re-enabled after Restart from Finished"),
		Pawn->IsActorTickEnabled());
	Expect(TEXT("step 11: authoritative distance reset after Restart from Finished"),
		FMath::IsNearlyEqual(Pawn->GetAuthoritativeState().DistanceM, 0.0, 0.0));

	// -------------------------------------------------------------------
	// (12) Optional: attempt stat unit / stat unitgraph console
	//      commands. These do nothing useful in a headless Automation
	//      pass without a real viewport, but the engine-side
	//      implementations are safe no-ops in that case and the
	//      commands are the documented ones that satisfy #49.
	//      The screenshot is captured by the surrounding PIE driver
	//      (Invoke-YacsInsightsProof.ps1) which DOES have a viewport.
	// -------------------------------------------------------------------
	if (GEngine)
	{
		UWorld* EngineWorld = GEngine->GetCurrentPlayWorld();
		if (EngineWorld)
		{
			GEngine->Exec(EngineWorld, TEXT("stat unit"));
			GEngine->Exec(EngineWorld, TEXT("stat unitgraph"));
		}
	}

	DestroyTransientWorld(World);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
