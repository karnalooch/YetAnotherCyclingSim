// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Focused automation tests for Stage 2 Enhanced Input handlers
// (issue #47).
//
// The tests invoke the Pawn's public handler methods directly with a
// default FInputActionValue. This avoids driving Enhanced Input
// through the render-frame polling path and instead verifies the
// invariant: one action event -> one session mutation.

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/EngineTypes.h"
#include "Components/SplineComponent.h"
#include "Components/SceneComponent.h"
#include "InputActionValue.h"

#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/CyclingSimulationSession.h"

namespace CyclingInputBindingTest
{
	UWorld* CreateTransientWorld()
	{
		return UWorld::CreateWorld(EWorldType::Game, false, TEXT("CyclingInputBindingTransientWorld"));
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

	ACyclingPrototypePawn* SpawnPrototypePawn(UWorld* World, AActor* RouteActor, bool bAutoStart = false)
	{
		ACyclingPrototypePawn* Pawn = World->SpawnActor<ACyclingPrototypePawn>();
		if (!Pawn)
		{
			return nullptr;
		}
		Pawn->RouteActor = RouteActor;
		Pawn->bAutoStart = bAutoStart;
		return Pawn;
	}
}

// =====================================================================
// Stage 2 Enhanced Input (issue #47) - one-event-one-step semantics.
//
// These tests do NOT exercise Enhanced Input subsystem presses. They
// invoke the Pawn's public handler methods directly with a default
// FInputActionValue, which is the canonical signature for one-shot
// (ETriggerEvent::Started) bindings. The intent is to assert the
// Pawn-level invariant: one input handler call -> one session
// mutation, on the configured step. This is the same invariant that
// the Started trigger preserves at the render-frame layer.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingInputOneEventOneStepTest, "CyclingInput.OneEventOneStep",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingInputOneEventOneStepTest::RunTest(const FString& Parameters)
{
	using namespace CyclingInputBindingTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

	Pawn->InitializeRide();
	Pawn->StartRide();

	// Prototype defaults: InitialPowerW = 200, PowerStepW = 10.
	//                                       InitialCadenceRpm = 90, CadenceStepRpm = 5.

	// 1) Power + : exactly one step (10 W).
	const double PowerBefore = Pawn->GetSession().GetRiderInput().PowerW;
	Pawn->HandlePowerIncrease(FInputActionValue());
	TestEqual(TEXT("power+: power advanced by exactly one configured step"),
		Pawn->GetSession().GetRiderInput().PowerW, PowerBefore + 10.0);

	// 2) Power - : exactly one step.
	const double PowerAfterInc = Pawn->GetSession().GetRiderInput().PowerW;
	Pawn->HandlePowerDecrease(FInputActionValue());
	TestEqual(TEXT("power-: power regressed by exactly one configured step"),
		Pawn->GetSession().GetRiderInput().PowerW, PowerAfterInc - 10.0);

	// 3) Cadence + : exactly one step (5 rpm).
	const double CadenceBefore = Pawn->GetSession().GetRiderInput().CadenceRpm;
	Pawn->HandleCadenceIncrease(FInputActionValue());
	TestEqual(TEXT("cadence+: cadence advanced by exactly one configured step"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, CadenceBefore + 5.0);

	// 4) Cadence - : exactly one step.
	const double CadenceAfterInc = Pawn->GetSession().GetRiderInput().CadenceRpm;
	Pawn->HandleCadenceDecrease(FInputActionValue());
	TestEqual(TEXT("cadence-: cadence regressed by exactly one configured step"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, CadenceAfterInc - 5.0);

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// Power clamping is delegated to the existing controller. The handler
// must never bypass clamping or mutate outside [Min, Max].
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingInputClampTest, "CyclingInput.Clamping",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingInputClampTest::RunTest(const FString& Parameters)
{
	using namespace CyclingInputBindingTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

	Pawn->InitializeRide();
	Pawn->StartRide();

	// Drive power to clamp at max (2000 W with step 10 -> 180 steps).
	// The Pawn-level invariant is: 180 successful increments arrive at
	// exactly 2000 W.
	for (int32 i = 0; i < 200; ++i)
	{
		Pawn->HandlePowerIncrease(FInputActionValue());
	}
	TestEqual(TEXT("clamp: power stopped at MaxPowerW = 2000"),
		Pawn->GetSession().GetRiderInput().PowerW, 2000.0);

	// One more increment stays clamped; the handler does not overflow.
	Pawn->HandlePowerIncrease(FInputActionValue());
	TestEqual(TEXT("clamp: power stuck at MaxPowerW after extra increment"),
		Pawn->GetSession().GetRiderInput().PowerW, 2000.0);

	// Drop cadence to clamp at min (0 rpm) and confirm stuck.
	for (int32 i = 0; i < 60; ++i)
	{
		Pawn->HandleCadenceDecrease(FInputActionValue());
	}
	TestEqual(TEXT("clamp: cadence stopped at MinCadenceRpm = 0"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, 0.0);

	Pawn->HandleCadenceDecrease(FInputActionValue());
	TestEqual(TEXT("clamp: cadence stuck at MinCadenceRpm after extra decrement"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, 0.0);

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// Lifecycle commands via input handlers preserve session state on
// Stop/Start and reset on Restart. Finished must NOT be resumed by
// StartRide; the existing switch on Lifecycle enforces this.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingInputLifecycleTest, "CyclingInput.Lifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingInputLifecycleTest::RunTest(const FString& Parameters)
{
	using namespace CyclingInputBindingTest;

	// --- Stop preserves state; Start resumes without resetting it. ---
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.5f); // 10 fixed steps
		const FSimulationState Snapshot = Pawn->GetAuthoritativeState();
		const double AccumBefore = Pawn->GetSession().GetAccumulatedTimeS();

		Pawn->HandleStopRide(FInputActionValue());
		TestEqual(TEXT("input Stop -> Stopped"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Stopped));

		Pawn->HandleStartRide(FInputActionValue());
		TestEqual(TEXT("input Start -> Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestEqual(TEXT("input Start after Stop preserves distance"),
			Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);
		TestEqual(TEXT("input Start after Stop preserves speed"),
			Pawn->GetAuthoritativeState().SpeedMps, Snapshot.SpeedMps);
		TestEqual(TEXT("input Start after Stop preserves accumulator"),
			Pawn->GetSession().GetAccumulatedTimeS(), AccumBefore);

		DestroyTransientWorld(World);
	}

	// --- Restart resets session and presentation. ---
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

		Pawn->InitializeRide();
		Pawn->StartRide();

		// Mutate rider input away from initial.
		Pawn->HandlePowerIncrease(FInputActionValue());
		Pawn->HandlePowerIncrease(FInputActionValue());
		Pawn->HandleCadenceIncrease(FInputActionValue());
		Pawn->Tick(2.0f); // drive 40 fixed steps; advance presentation

		TestTrue(TEXT("restart: pre-restart power != initial"),
			Pawn->GetSession().GetRiderInput().PowerW != 200.0);
		TestTrue(TEXT("restart: pre-restart cadence != initial"),
			Pawn->GetSession().GetRiderInput().CadenceRpm != 90.0);
		TestTrue(TEXT("restart: pre-restart actor off origin"),
			FMath::Abs(Pawn->GetActorLocation().X) > 100.0f);

		Pawn->HandleRestartRide(FInputActionValue());
		TestEqual(TEXT("restart: lifecycle Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestEqual(TEXT("restart: power restored to initial 200 W"),
			Pawn->GetSession().GetRiderInput().PowerW, 200.0);
		TestEqual(TEXT("restart: cadence restored to initial 90 rpm"),
			Pawn->GetSession().GetRiderInput().CadenceRpm, 90.0);
		TestEqual(TEXT("restart: distance reset to 0"),
			Pawn->GetAuthoritativeState().DistanceM, 0.0);
		TestTrue(TEXT("restart: actor snapped to spline origin"),
			FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));

		DestroyTransientWorld(World);
	}

	// --- Finished cannot be resumed by Start; Restart is required. ---
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

		Pawn->InitializeRide();
		Pawn->StartRide();

		// Drive enough time to overshoot 500 m at 200 W on flat ground.
		for (int32 i = 0; i < 200; ++i)
		{
			Pawn->Tick(0.5f);
			if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
			{
				break;
			}
		}
		TestEqual(TEXT("finished: lifecycle is Finished"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Finished));

		const FSimulationState Snapshot = Pawn->GetAuthoritativeState();

		// StartRide from Finished is a no-op; lifecycle stays Finished.
		Pawn->HandleStartRide(FInputActionValue());
		TestEqual(TEXT("finished: StartRide ignored, lifecycle stays Finished"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Finished));
		TestEqual(TEXT("finished: StartRide did not touch distance"),
			Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);

		// RestartRide transitions Finished -> Running.
		Pawn->HandleRestartRide(FInputActionValue());
		TestEqual(TEXT("finished: RestartRide -> Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestEqual(TEXT("finished: RestartRide resets distance"),
			Pawn->GetAuthoritativeState().DistanceM, 0.0);

		DestroyTransientWorld(World);
	}

	return true;
}

// =====================================================================
// Invalid / error input does not crash and does not silently reset
// the session. The Pawn's handlers never crash on missing session or
// missing route; they log a warning and leave state untouched.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingInputErrorSafetyTest, "CyclingInput.ErrorSafety",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingInputErrorSafetyTest::RunTest(const FString& Parameters)
{
	using namespace CyclingInputBindingTest;

	// 1. Pawn with no route -> Error state. Input handlers must not crash
	//    and must not modify a stale/empty session.
	{
		UWorld* World = CreateTransientWorld();
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, /*RouteActor=*/nullptr);
		Pawn->InitializeRide();
		TestEqual(TEXT("error: lifecycle is Error"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));

		// Calling the handlers when the session is unconfigured returns
		// false (session unconfigured), the Pawn logs one warning, and
		// the session state stays untouched. There is no crash and no
		// hidden side-effect on the lifecycle.
		const ECyclingPrototypeLifecycle Before = Pawn->GetLifecycle();

		Pawn->HandlePowerIncrease(FInputActionValue());
		Pawn->HandlePowerDecrease(FInputActionValue());
		Pawn->HandleCadenceIncrease(FInputActionValue());
		Pawn->HandleCadenceDecrease(FInputActionValue());

		TestEqual(TEXT("error: lifecycle unchanged after power/cadence handlers"),
			static_cast<int32>(Pawn->GetLifecycle()), static_cast<int32>(Before));

		Pawn->HandleStartRide(FInputActionValue());
		Pawn->HandleStopRide(FInputActionValue());
		TestEqual(TEXT("error: StartRide/StopRide do nothing in Error"),
			static_cast<int32>(Pawn->GetLifecycle()), static_cast<int32>(Before));

		// RestartRide from Error re-runs InitializeRide. Without a
		// route, this is still Error. No crash.
		Pawn->HandleRestartRide(FInputActionValue());
		TestEqual(TEXT("error: RestartRide in Error stays Error (no route)"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));

		DestroyTransientWorld(World);
	}

	// 2. Pawn with valid route. Power+ when session is healthy applies
	//    exactly one step and leaves lifecycle Running. This guards
	//    against accidental reset in the handler path.
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

		Pawn->InitializeRide();
		Pawn->StartRide();
		const double PowerBefore = Pawn->GetSession().GetRiderInput().PowerW;

		Pawn->HandlePowerIncrease(FInputActionValue());

		TestEqual(TEXT("healthy: power increased by one step"),
			Pawn->GetSession().GetRiderInput().PowerW, PowerBefore + 10.0);
		TestEqual(TEXT("healthy: lifecycle still Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));

		DestroyTransientWorld(World);
	}

	return true;
}

// =====================================================================
// One-event-one-step invariant under repeated invokes. Calling the
// same handler many times produces exactly N step mutations, never
// N + drift. This is the regression test for the issue's central
// invariant: holding a key does not multiply mutations (the ETrigger
// ::Started binding already prevents this; the Pawn-level handler
// must remain a strict single-step function so the UI does not
// regress later).
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingInputRepeatedStepsTest, "CyclingInput.RepeatedSteps",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingInputRepeatedStepsTest::RunTest(const FString& Parameters)
{
	using namespace CyclingInputBindingTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

	Pawn->InitializeRide();
	Pawn->StartRide();

	const double P0 = Pawn->GetSession().GetRiderInput().PowerW;
	const double C0 = Pawn->GetSession().GetRiderInput().CadenceRpm;

	// 12 power-up, 7 power-down, 5 cadence-up, 4 cadence-down.
	const int32 PowerUps = 12;
	const int32 PowerDowns = 7;
	const int32 CadenceUps = 5;
	const int32 CadenceDowns = 4;

	for (int32 i = 0; i < PowerUps; ++i) { Pawn->HandlePowerIncrease(FInputActionValue()); }
	for (int32 i = 0; i < PowerDowns; ++i) { Pawn->HandlePowerDecrease(FInputActionValue()); }
	for (int32 i = 0; i < CadenceUps; ++i) { Pawn->HandleCadenceIncrease(FInputActionValue()); }
	for (int32 i = 0; i < CadenceDowns; ++i) { Pawn->HandleCadenceDecrease(FInputActionValue()); }

	const double ExpectedPowerW    = P0 + (PowerUps - PowerDowns) * 10.0;
	const double ExpectedCadenceRpm = C0 + (CadenceUps - CadenceDowns) * 5.0;
	TestEqual(TEXT("repeated: power = initial + (ups - downs) * step"),
		Pawn->GetSession().GetRiderInput().PowerW, ExpectedPowerW);
	TestEqual(TEXT("repeated: cadence = initial + (ups - downs) * step"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, ExpectedCadenceRpm);

	DestroyTransientWorld(World);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
