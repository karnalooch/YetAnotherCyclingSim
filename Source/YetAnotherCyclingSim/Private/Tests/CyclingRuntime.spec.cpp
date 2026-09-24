// Copyright YetAnotherCyclingSim. All Rights Reserved.

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/WorldSettings.h"
#include "Components/SplineComponent.h"
#include "Components/SceneComponent.h"

#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/CyclingSimulationSession.h"

namespace CyclingRuntimeTest
{
	// Helper: build a minimal test world. The transient world is enough
	// for the Pawn's lifecycle and route spline caching.
	UWorld* CreateTransientWorld()
	{
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("CyclingRuntimeTransientWorld"));
		return World;
	}

	void DestroyTransientWorld(UWorld* World)
	{
		if (World)
		{
			World->DestroyWorld(false);
		}
	}

	// Helper: spawn a route Actor with exactly one USplineComponent that
	// describes a straight line from (0,0,0) to (LengthCm,0,0).
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

	// Helper: spawn a route Actor that has TWO splines (for ambiguous test).
	AActor* SpawnAmbiguousRouteActor(UWorld* World)
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

		for (int32 Index = 0; Index < 2; ++Index)
		{
			USplineComponent* Spline = NewObject<USplineComponent>(RouteActor, USplineComponent::StaticClass(),
				*FString::Printf(TEXT("RouteSpline_%d"), Index));
			Spline->SetMobility(EComponentMobility::Movable);
			Spline->SetupAttachment(RouteRoot);
			Spline->RegisterComponent();

			Spline->ClearSplinePoints(false);
			Spline->AddSplinePoint(FVector(0.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
			Spline->AddSplinePoint(FVector(100.0f, 0.0f, 0.0f), ESplineCoordinateSpace::Local, false);
			Spline->UpdateSpline();
		}

		return RouteActor;
	}

	// Helper: spawn a route Actor with one spline that has zero/empty points.
	AActor* SpawnZeroLengthRouteActor(UWorld* World)
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
		// No points -> zero length
		Spline->UpdateSpline();

		return RouteActor;
	}

	// Spawns an ACyclingPrototypePawn at world origin, attached to a route
	// with the given length in centimetres.
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingRuntimeTest, "CyclingRuntime.PrototypePawn",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimeTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeTest;

	// ===========================================================
	// 1. Valid initialization -> Ready, no auto start, presentation snapped to spline start.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f); // 500 m
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();

		TestEqual(TEXT("ready: lifecycle is Ready"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Ready));
		TestEqual(TEXT("ready: Tick is disabled"), Pawn->IsActorTickEnabled(), false);
		TestEqual(TEXT("ready: cached spline length is 500 m in cm"),
			Pawn->GetCachedSplineLengthCm(), 50000.0);
		TestTrue(TEXT("ready: last error is empty"), Pawn->GetLastError().IsEmpty());
		TestTrue(TEXT("ready: actor at spline origin X"),
			FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));
		TestTrue(TEXT("ready: session is configured"),
			Pawn->GetSession().IsConfigured());

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 2. Missing route -> Error.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, /*RouteActor=*/nullptr, /*bAutoStart=*/false);

		Pawn->InitializeRide();

		TestEqual(TEXT("missing route: lifecycle is Error"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));
		TestEqual(TEXT("missing route: Tick is disabled"), Pawn->IsActorTickEnabled(), false);
		TestFalse(TEXT("missing route: last error is set"), Pawn->GetLastError().IsEmpty());
		TestFalse(TEXT("missing route: session is not configured"),
			Pawn->GetSession().IsConfigured());

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 3. Multiple/ambiguous splines -> Error.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnAmbiguousRouteActor(World);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();

		TestEqual(TEXT("ambiguous splines: lifecycle is Error"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));
		TestEqual(TEXT("ambiguous splines: Tick is disabled"), Pawn->IsActorTickEnabled(), false);
		TestFalse(TEXT("ambiguous splines: last error is set"), Pawn->GetLastError().IsEmpty());
		TestTrue(TEXT("ambiguous splines: error message mentions spline count"),
			Pawn->GetLastError().Contains(TEXT("2 splines")) ||
			Pawn->GetLastError().Contains(TEXT("exactly one")));

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 3b. Zero-length spline -> Error.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnZeroLengthRouteActor(World);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();

		TestEqual(TEXT("zero-length spline: lifecycle is Error"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));
		TestEqual(TEXT("zero-length spline: Tick is disabled"), Pawn->IsActorTickEnabled(), false);
		TestFalse(TEXT("zero-length spline: last error is set"), Pawn->GetLastError().IsEmpty());

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 4. Start from Ready -> Running, Tick enabled.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		TestEqual(TEXT("start: ready before StartRide"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Ready));

		Pawn->StartRide();
		TestEqual(TEXT("start: Running after StartRide"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestEqual(TEXT("start: Tick is enabled"), Pawn->IsActorTickEnabled(), true);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 5/6. Stop preserves state and accumulator.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();

		// Drive some fixed-step time: 0.5 s = 10 fixed steps.
		Pawn->Tick(0.5f);
		const FSimulationState Snapshot = Pawn->GetAuthoritativeState();
		const double SnapshotAccumulator = Pawn->GetSession().GetAccumulatedTimeS();

		// Drive a sub-step to leave non-zero accumulator < fixed step.
		Pawn->Tick(0.04f);
		const double AccumulatorBeforeStop = Pawn->GetSession().GetAccumulatedTimeS();

		Pawn->StopRide();
		TestEqual(TEXT("stop: lifecycle is Stopped"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Stopped));
		TestEqual(TEXT("stop: Tick is disabled"), Pawn->IsActorTickEnabled(), true == false);
		TestTrue(TEXT("stop: Tick disabled actually"),
			!Pawn->IsActorTickEnabled());

		// State preserved.
		TestEqual(TEXT("stop: authoritative speed preserved"),
			Pawn->GetAuthoritativeState().SpeedMps, Snapshot.SpeedMps);
		TestEqual(TEXT("stop: authoritative distance preserved"),
			Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);
		TestEqual(TEXT("stop: authoritative elapsed time preserved"),
			Pawn->GetAuthoritativeState().ElapsedTimeS, Snapshot.ElapsedTimeS);
		TestTrue(TEXT("stop: accumulator preserved strictly positive (sub-step still pending)"),
			AccumulatorBeforeStop > 0.0);
		TestEqual(TEXT("stop: accumulator equals pre-stop value"),
			Pawn->GetSession().GetAccumulatedTimeS(), AccumulatorBeforeStop);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 7. Start from Stopped resumes session (state preserved, not reset).
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.5f);
		Pawn->Tick(0.04f); // leaves sub-step in accumulator

		const FSimulationState Snapshot = Pawn->GetAuthoritativeState();
		const double AccumulatorSnapshot = Pawn->GetSession().GetAccumulatedTimeS();

		Pawn->StopRide();
		Pawn->StartRide();

		TestEqual(TEXT("resume: lifecycle is Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestTrue(TEXT("resume: Tick is enabled"), Pawn->IsActorTickEnabled());
		TestEqual(TEXT("resume: authoritative speed preserved"),
			Pawn->GetAuthoritativeState().SpeedMps, Snapshot.SpeedMps);
		TestEqual(TEXT("resume: authoritative distance preserved"),
			Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);
		TestEqual(TEXT("resume: accumulator preserved"),
			Pawn->GetSession().GetAccumulatedTimeS(), AccumulatorSnapshot);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 8/9. Restart resets session and snaps presentation to spline start.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();

		// Change power to a non-default value, then drive some time.
		FString Error;
		Pawn->GetMutableSession().TrySetPowerW(800.0, Error);
		Pawn->Tick(1.0f); // 20 fixed steps

		TestTrue(TEXT("restart: pre-restart distance > 0"),
			Pawn->GetAuthoritativeState().DistanceM > 0.0);

		// Drive enough time to be well off spline start.
		Pawn->Tick(5.0f);
		TestTrue(TEXT("restart: pre-restart location off origin"),
			FMath::Abs(Pawn->GetActorLocation().X) > 100.0f);

		Pawn->RestartRide();

		TestEqual(TEXT("restart: lifecycle is Running"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestTrue(TEXT("restart: Tick is enabled"), Pawn->IsActorTickEnabled());

		TestEqual(TEXT("restart: speed reset to 0"),
			Pawn->GetAuthoritativeState().SpeedMps, 0.0);
		TestEqual(TEXT("restart: distance reset to 0"),
			Pawn->GetAuthoritativeState().DistanceM, 0.0);
		TestEqual(TEXT("restart: elapsed time reset to 0"),
			Pawn->GetAuthoritativeState().ElapsedTimeS, 0.0);
		TestEqual(TEXT("restart: accumulator reset to 0"),
			Pawn->GetSession().GetAccumulatedTimeS(), 0.0);
		TestEqual(TEXT("restart: power restored to 200"),
			Pawn->GetSession().GetRiderInput().PowerW, 200.0);
		TestEqual(TEXT("restart: cadence restored to 90"),
			Pawn->GetSession().GetRiderInput().CadenceRpm, 90.0);
		TestTrue(TEXT("restart: actor snapped to spline origin"),
			FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 10. Zero-fixed-step rendered frame: Tick(0.01) does no advance but
	//     leaves time in the accumulator; visible transform stays the same.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.1f); // 2 fixed steps
		const FVector PosAfter = Pawn->GetActorLocation();
		const double DistAfter = Pawn->GetAuthoritativeState().DistanceM;

		Pawn->Tick(0.01f); // below 0.05 -> zero steps
		TestEqual(TEXT("zero-step frame: distance unchanged"),
			Pawn->GetAuthoritativeState().DistanceM, DistAfter);
		TestEqual(TEXT("zero-step frame: visible location unchanged"),
			Pawn->GetActorLocation(), PosAfter);
		TestEqual(TEXT("zero-step frame: accumulator increased by 0.01"),
			Pawn->GetSession().GetAccumulatedTimeS(), 0.01);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 11. Multi-step rendered frame: 0.2 s Tick -> 4 fixed steps advance
	//     (no leftover accumulator).
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.2f);

		TestTrue(TEXT("multi-step: distance > 0"),
			Pawn->GetAuthoritativeState().DistanceM > 0.0);
		TestTrue(TEXT("multi-step: speed > 0"),
			Pawn->GetAuthoritativeState().SpeedMps > 0.0);
		TestTrue(TEXT("multi-step: location advanced along X"),
			Pawn->GetActorLocation().X > 0.0f);
		// Accumulator should be 0 after an exact 4-step Tick (0.2 s).
		TestEqual(TEXT("multi-step: accumulator equals 0"),
			Pawn->GetSession().GetAccumulatedTimeS(), 0.0);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 12/13. Stage 3 deterministic Finish is emitted at the authoritative
	//         Alpine route end (10 km), not from render-frame spline polling.
	//         Presentation clamps to the spline end and Finished is sticky.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 1000000.0f); // 10 km presentation fixture
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();

		FString Error;
		TestTrue(TEXT("finished: high proof power accepted"),
			Pawn->GetMutableSession().TrySetPowerW(2000.0, Error));

		for (int32 i = 0; i < 2000; ++i)
		{
			Pawn->Tick(1.0f);
			if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
			{
				break;
			}
		}

		TestEqual(TEXT("finished: lifecycle is Finished"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Finished));
		TestTrue(TEXT("finished: Tick is disabled"), !Pawn->IsActorTickEnabled());
		TestTrue(TEXT("finished: authoritative distance crossed 10 km"),
			Pawn->GetAuthoritativeState().DistanceM >= 10000.0);
		TestTrue(TEXT("finished: fixed-step overshoot stays small"),
			Pawn->GetAuthoritativeState().DistanceM <= 10005.0);
		TestTrue(TEXT("finished: visible X is clamped to 10 km spline end"),
			FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 1000000.0f, 1.0f));
		TestTrue(TEXT("finished: boundary history contains terminal finish"),
			Pawn->GetBoundaryHistory().Num() > 0
			&& Pawn->GetBoundaryHistory().Last().Kind == CyclingSimulation::ESimulationBoundaryKind::Finish);

		// No further advancement after Finished even if Tick is called directly.
		const double DistanceBeforeIdle = Pawn->GetAuthoritativeState().DistanceM;
		const FVector LocationBeforeIdle = Pawn->GetActorLocation();
		Pawn->Tick(1.0f);
		TestEqual(TEXT("finished: distance does not advance further"),
			Pawn->GetAuthoritativeState().DistanceM, DistanceBeforeIdle);
		TestEqual(TEXT("finished: location does not advance further"),
			Pawn->GetActorLocation(), LocationBeforeIdle);

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 14. Error disables progression. Restoring the route and restarting
	//     must revalidate/reconfigure before progression resumes.
	// ===========================================================
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);

		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.5f);

		const FSimulationState Snapshot = Pawn->GetAuthoritativeState();
		const FVector LocationSnapshot = Pawn->GetActorLocation();

		// Remove route reference and re-init -> Error; previous state/visual preserved.
		Pawn->RouteActor = nullptr;
		Pawn->InitializeRide();

		TestEqual(TEXT("error: lifecycle is Error"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Error));
		TestTrue(TEXT("error: Tick is disabled"), !Pawn->IsActorTickEnabled());
		TestFalse(TEXT("error: last error is set"), Pawn->GetLastError().IsEmpty());
		TestEqual(TEXT("error: authoritative state preserved (Speed)"),
			Pawn->GetAuthoritativeState().SpeedMps, Snapshot.SpeedMps);
		TestEqual(TEXT("error: authoritative state preserved (Distance)"),
			Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);
		TestEqual(TEXT("error: visual transform preserved"),
			Pawn->GetActorLocation(), LocationSnapshot);

		Pawn->RouteActor = Route;
		Pawn->RestartRide();
		TestEqual(TEXT("error restart: lifecycle is Running after revalidation"),
			static_cast<int32>(Pawn->GetLifecycle()),
			static_cast<int32>(ECyclingPrototypeLifecycle::Running));
		TestTrue(TEXT("error restart: Tick is enabled"), Pawn->IsActorTickEnabled());
		TestTrue(TEXT("error restart: diagnostic is cleared"), Pawn->GetLastError().IsEmpty());
		TestEqual(TEXT("error restart: authoritative distance reset"),
			Pawn->GetAuthoritativeState().DistanceM, 0.0);
		TestTrue(TEXT("error restart: actor snapped to spline origin"),
			FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 0.0f, 0.01f));

		DestroyTransientWorld(World);
	}

	// ===========================================================
	// 15. Identical supplied frame-time/input sequences produce equivalent
	//     authoritative state. Run two Pawns with identical command/time
	//     sequences and confirm equal final state.
	// ===========================================================
	{
		UWorld* WorldA = CreateTransientWorld();
		UWorld* WorldB = CreateTransientWorld();
		AActor* RouteA = SpawnStraightRouteActor(WorldA, 50000.0f);
		AActor* RouteB = SpawnStraightRouteActor(WorldB, 50000.0f);
		ACyclingPrototypePawn* PawnA = SpawnPrototypePawn(WorldA, RouteA, /*bAutoStart=*/false);
		ACyclingPrototypePawn* PawnB = SpawnPrototypePawn(WorldB, RouteB, /*bAutoStart=*/false);

		PawnA->InitializeRide();
		PawnA->StartRide();
		PawnB->InitializeRide();
		PawnB->StartRide();

		struct FFakeFrame { double Dt; double PowerW; };
		const FFakeFrame Sequence[] = {
			{0.04, 200.0},
			{0.06, 200.0},
			{0.05, 250.0},
			{0.10, 300.0},
			{0.20, 350.0},
			{0.50, 400.0},
			{1.00, 200.0},
		};

		FString Error;
		for (const FFakeFrame& F : Sequence)
		{
			PawnA->GetMutableSession().TrySetPowerW(F.PowerW, Error);
			PawnB->GetMutableSession().TrySetPowerW(F.PowerW, Error);
			PawnA->Tick(static_cast<float>(F.Dt));
			PawnB->Tick(static_cast<float>(F.Dt));
		}

		TestEqual(TEXT("deterministic: equal speed after identical sequence"),
			PawnA->GetAuthoritativeState().SpeedMps,
			PawnB->GetAuthoritativeState().SpeedMps);
		TestEqual(TEXT("deterministic: equal distance after identical sequence"),
			PawnA->GetAuthoritativeState().DistanceM,
			PawnB->GetAuthoritativeState().DistanceM);
		TestEqual(TEXT("deterministic: equal elapsed time after identical sequence"),
			PawnA->GetAuthoritativeState().ElapsedTimeS,
			PawnB->GetAuthoritativeState().ElapsedTimeS);
		TestEqual(TEXT("deterministic: equal accumulator after identical sequence"),
			PawnA->GetSession().GetAccumulatedTimeS(),
			PawnB->GetSession().GetAccumulatedTimeS());

		DestroyTransientWorld(WorldA);
		DestroyTransientWorld(WorldB);
	}

	return true;
}

// =====================================================================
// Frame-pacing proof. Compares authoritative state across different
// render-frame cadences (~30 FPS, ~60 FPS, ~120 FPS) and a hitch sequence
// with at least one frame requiring >1 fixed step.
//
// Uses the same prototype fixture values:
//   200 W, 90 rpm, 75 kg + 8.5 kg, CdA 0.32, Crr 0.004, eta 0.97,
//   grade 0, no wind, sea-level air.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingRuntimeFramePacingTest, "CyclingRuntime.FramePacing",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimeFramePacingTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeTest;

	// Total simulated horizon ~30 s.
	constexpr double TotalS = 30.0;

	struct FCadenceSequence { double Dt; };
	TArray<FCadenceSequence> Sequence30;
	TArray<FCadenceSequence> Sequence60;
	TArray<FCadenceSequence> Sequence120;
	TArray<FCadenceSequence> SequenceJitter;

	// Build representative ~30 FPS frames (1/30 s nominal).
	{
		const double Dt = 1.0 / 30.0;
		double Accum = 0.0;
		while (Accum + Dt <= TotalS + 1e-9)
		{
			Sequence30.Add({ Dt });
			Accum += Dt;
		}
	}

	// Build representative ~60 FPS frames (1/60 s nominal).
	{
		const double Dt = 1.0 / 60.0;
		double Accum = 0.0;
		while (Accum + Dt <= TotalS + 1e-9)
		{
			Sequence60.Add({ Dt });
			Accum += Dt;
		}
	}

	// Build representative ~120 FPS frames (1/120 s nominal).
	{
		const double Dt = 1.0 / 120.0;
		double Accum = 0.0;
		while (Accum + Dt <= TotalS + 1e-9)
		{
			Sequence120.Add({ Dt });
			Accum += Dt;
		}
	}

	// Build a hitch sequence: many 1/60 s frames, with one frame requiring
	// 0.30 s (i.e. 6 fixed steps of 0.05 s).
	{
		const double NominalDt = 1.0 / 60.0;
		double Accum = 0.0;
		bool HitchEmitted = false;
		while (Accum + NominalDt <= TotalS + 1e-9)
		{
			if (!HitchEmitted && Accum > 5.0)
			{
				SequenceJitter.Add({ 0.30 }); // 6 fixed steps
				HitchEmitted = true;
				Accum += 0.30;
				continue;
			}
			SequenceJitter.Add({ NominalDt });
			Accum += NominalDt;
		}
	}

	auto RunSequence = [](const TArray<FCadenceSequence>& Seq) -> FSimulationState
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route, /*bAutoStart=*/false);
		Pawn->InitializeRide();
		Pawn->StartRide();

		for (const FCadenceSequence& F : Seq)
		{
			Pawn->Tick(static_cast<float>(F.Dt));
		}

		const FSimulationState Result = Pawn->GetAuthoritativeState();
		DestroyTransientWorld(World);
		return Result;
	};

	const FSimulationState Result30  = RunSequence(Sequence30);
	const FSimulationState Result60  = RunSequence(Sequence60);
	const FSimulationState Result120 = RunSequence(Sequence120);
	const FSimulationState ResultJit = RunSequence(SequenceJitter);

	// Within the existing deterministic contract, floating-point equality
	// (or near-equality) is expected for these patterns. We assert exact
	// equality per the existing test convention (TestEqual).
	TestEqual(TEXT("frame-pacing 30 FPS speed equals 60 FPS"),
		Result30.SpeedMps, Result60.SpeedMps);
	TestEqual(TEXT("frame-pacing 30 FPS distance equals 60 FPS"),
		Result30.DistanceM, Result60.DistanceM);
	TestEqual(TEXT("frame-pacing 30 FPS elapsed equals 60 FPS"),
		Result30.ElapsedTimeS, Result60.ElapsedTimeS);

	TestEqual(TEXT("frame-pacing 60 FPS speed equals 120 FPS"),
		Result60.SpeedMps, Result120.SpeedMps);
	TestEqual(TEXT("frame-pacing 60 FPS distance equals 120 FPS"),
		Result60.DistanceM, Result120.DistanceM);
	TestEqual(TEXT("frame-pacing 60 FPS elapsed equals 120 FPS"),
		Result60.ElapsedTimeS, Result120.ElapsedTimeS);

	TestEqual(TEXT("frame-pacing jitter speed equals 30 FPS"),
		ResultJit.SpeedMps, Result30.SpeedMps);
	TestEqual(TEXT("frame-pacing jitter distance equals 30 FPS"),
		ResultJit.DistanceM, Result30.DistanceM);
	TestEqual(TEXT("frame-pacing jitter elapsed equals 30 FPS"),
		ResultJit.ElapsedTimeS, Result30.ElapsedTimeS);

	// Also confirm no run has reached Finished within 30 s on flat ground
	// at 200 W (riders reach ~9 m/s -> ~270 m in 30 s).
	TestTrue(TEXT("frame-pacing 30s not finished"),
		Result30.DistanceM < 500.0);
	TestTrue(TEXT("frame-pacing jitter not finished"),
		ResultJit.DistanceM < 500.0);

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
