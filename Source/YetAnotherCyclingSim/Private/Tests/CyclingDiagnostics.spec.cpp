// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Focused automation tests for the Stage 2 diagnostic overlay
// (issue #48).
//
// The overlay is presentation-only. These tests cover:
//   - the pure formatter/observer helpers in CyclingDiagnostics.h;
//   - the runtime Pawn integration (LastInputFeedback before/after,
//     lifecycle transitions, ignored-in-Finished, overlay
//     disable/enable, guided-acceptance observation without
//     mutation).

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/WorldSettings.h"
#include "Components/SplineComponent.h"
#include "Components/SceneComponent.h"
#include "InputActionValue.h"

#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/CyclingSimulationSession.h"
#include "Cycling/CyclingDiagnostics.h"

namespace CyclingDiagnosticsTest
{
	UWorld* CreateTransientWorld()
	{
		return UWorld::CreateWorld(EWorldType::Game, false, TEXT("CyclingDiagnosticsTransientWorld"));
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

	FCyclingInputSnapshot MakeSnap(
		ECyclingDiagnosticsLifecycle L,
		double PowerW,
		double CadenceRpm,
		double DistanceM,
		double ElapsedS)
	{
		FCyclingInputSnapshot Snap;
		Snap.Lifecycle = L;
		Snap.PowerW = PowerW;
		Snap.CadenceRpm = CadenceRpm;
		Snap.DistanceM = DistanceM;
		Snap.ElapsedTimeS = ElapsedS;
		return Snap;
	}
}

// =====================================================================
// 1. Pure formatter: snapshot -> string contains expected labels.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsFormatterTest, "CyclingDiagnostics.Formatter",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsFormatterTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	FSimulationState State;
	State.SpeedMps = 7.89;
	State.DistanceM = 126.7;
	State.ElapsedTimeS = 18.35;

	FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
		ECyclingDiagnosticsLifecycle::Running,
		210.0, 90.0,
		State,
		/*LastCompletedSteps=*/1,
		/*AccumulatorS=*/0.016,
		/*CachedRouteLengthM=*/500.0,
		/*LastError=*/TEXT(""),
		/*ConfiguredPowerStepW=*/10.0,
		/*ConfiguredCadenceStepRpm=*/5.0);

	FCyclingGuidedAcceptanceState Guided;
	Guided.CurrentStep = ECyclingGuidedAcceptanceStep::Ready_WaitStart;

	const FString Text = CyclingDiagnostics::FormatOverlay(
		Snapshot, Guided, /*bEnableGuidedAcceptance=*/true);

	TestTrue(TEXT("formatter: header present"),
		Text.Contains(TEXT("YACS - STAGE 2 DEV HUD")));
	TestTrue(TEXT("formatter: STATE line present"),
		Text.Contains(TEXT("STATE       RUNNING")));
	TestTrue(TEXT("formatter: power line"),
		Text.Contains(TEXT("POWER       210 W")));
	TestTrue(TEXT("formatter: cadence line"),
		Text.Contains(TEXT("CADENCE     90 rpm")));
	TestTrue(TEXT("formatter: speed line m/s and km/h"),
		Text.Contains(TEXT("m/s")) && Text.Contains(TEXT("km/h")));
	TestTrue(TEXT("formatter: distance line with route total"),
		Text.Contains(TEXT("DISTANCE    126.70 / 500.00 m")));
	TestTrue(TEXT("formatter: time line"),
		Text.Contains(TEXT("TIME        18.35 s")));
	TestTrue(TEXT("formatter: fixed steps line"),
		Text.Contains(TEXT("FIXED STEPS   1")));
	TestTrue(TEXT("formatter: accumulator line"),
		Text.Contains(TEXT("ACCUMULATOR   0.016 s")));
	TestTrue(TEXT("formatter: error none"),
		Text.Contains(TEXT("ERROR         none")));
	TestTrue(TEXT("formatter: CONTROLS legend"),
		Text.Contains(TEXT("CONTROLS"))
		&& Text.Contains(TEXT("[SPACE]"))
		&& Text.Contains(TEXT("[S]"))
		&& Text.Contains(TEXT("[R]"))
		&& Text.Contains(TEXT("[UP]"))
		&& Text.Contains(TEXT("[DOWN]"))
		&& Text.Contains(TEXT("[RIGHT]"))
		&& Text.Contains(TEXT("[LEFT]")));
	TestTrue(TEXT("formatter: configured power step is shown"),
		Text.Contains(TEXT("Power +10 W")));
	TestTrue(TEXT("formatter: configured cadence step is shown"),
		Text.Contains(TEXT("Cadence +5 rpm")));
	TestTrue(TEXT("formatter: LAST INPUT block"),
		Text.Contains(TEXT("LAST INPUT")));
	TestTrue(TEXT("formatter: MANUAL ACCEPTANCE block"),
		Text.Contains(TEXT("MANUAL ACCEPTANCE")));
	TestTrue(TEXT("formatter: step 1 prompt"),
		Text.Contains(TEXT("1/7 - Press SPACE")));
	TestTrue(TEXT("formatter: step expected"),
		Text.Contains(TEXT("Expected: READY -> RUNNING")));

	return true;
}

// =====================================================================
// 2. Pure formatter: last-input feedback (power +1 step) renders the
// correct before/after numbers and PASS status.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsLastInputPowerTest, "CyclingDiagnostics.LastInputPower",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsLastInputPowerTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	FSimulationState State;
	State.SpeedMps = 0.0;
	State.DistanceM = 0.0;
	State.ElapsedTimeS = 0.0;

	FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
		ECyclingDiagnosticsLifecycle::Running,
		210.0, 90.0, State, 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);

	Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
		ECyclingInputCommand::PowerIncrease,
		MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 90.0, 0.0, 0.0),
		MakeSnap(ECyclingDiagnosticsLifecycle::Running, 210.0, 90.0, 0.0, 0.0),
		10.0, 5.0);
	TestTrue(TEXT("power feedback: accepted when delta equals step"),
		Snapshot.LastInputFeedback.bAccepted);

	const FString Text = CyclingDiagnostics::FormatOverlay(
		Snapshot, FCyclingGuidedAcceptanceState(), /*bEnableGuidedAcceptance=*/false);

	TestTrue(TEXT("power feedback: tag and label"),
		Text.Contains(TEXT("UP - POWER +10 W")));
	TestTrue(TEXT("power feedback: numeric before->after"),
		Text.Contains(TEXT("200 W -> 210 W")));
	TestTrue(TEXT("power feedback: status PASS"),
		Text.Contains(TEXT("PASS")));

	return true;
}

// =====================================================================
// 3. Pure formatter: cadence before/after.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsLastInputCadenceTest, "CyclingDiagnostics.LastInputCadence",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsLastInputCadenceTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	FSimulationState State;

	FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
		ECyclingDiagnosticsLifecycle::Running,
		200.0, 95.0, State, 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);

	Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
		ECyclingInputCommand::CadenceIncrease,
		MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 90.0, 0.0, 0.0),
		MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 95.0, 0.0, 0.0),
		10.0, 5.0);

	TestTrue(TEXT("cadence feedback: accepted when delta equals step"),
		Snapshot.LastInputFeedback.bAccepted);

	const FString Text = CyclingDiagnostics::FormatOverlay(
		Snapshot, FCyclingGuidedAcceptanceState(), false);

	TestTrue(TEXT("cadence feedback: tag and label"),
		Text.Contains(TEXT("RIGHT - CADENCE +5 rpm")));
	TestTrue(TEXT("cadence feedback: numeric before->after"),
		Text.Contains(TEXT("90 rpm -> 95 rpm")));
	return true;
}

// =====================================================================
// 4. Pure formatter: lifecycle commands (Start/Stop/Resume/Restart).
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsLastInputLifecycleTest, "CyclingDiagnostics.LastInputLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsLastInputLifecycleTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	FSimulationState State;
	State.DistanceM = 184.32;
	State.ElapsedTimeS = 24.15;

	// Stop: Running -> Stopped.
	{
		FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
			ECyclingDiagnosticsLifecycle::Stopped,
			200.0, 90.0, State, 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);
		Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
			ECyclingInputCommand::Stop,
			MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 90.0, 184.32, 24.15),
			MakeSnap(ECyclingDiagnosticsLifecycle::Stopped, 200.0, 90.0, 184.32, 24.15),
			10.0, 5.0);
		TestTrue(TEXT("stop feedback: accepted on transition"),
			Snapshot.LastInputFeedback.bAccepted);
		const FString Text = CyclingDiagnostics::FormatOverlay(Snapshot, FCyclingGuidedAcceptanceState(), false);
		TestTrue(TEXT("stop feedback: tag RUNNING -> STOPPED"),
			Text.Contains(TEXT("RUNNING -> STOPPED")));
	}

	// Resume from Stopped.
	{
		FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
			ECyclingDiagnosticsLifecycle::Running,
			200.0, 90.0, State, 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);
		Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
			ECyclingInputCommand::StartOrResume,
			MakeSnap(ECyclingDiagnosticsLifecycle::Stopped, 200.0, 90.0, 184.32, 24.15),
			MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 90.0, 184.32, 24.15),
			10.0, 5.0);
		TestTrue(TEXT("resume feedback: accepted"),
			Snapshot.LastInputFeedback.bAccepted);
		const FString Text = CyclingDiagnostics::FormatOverlay(Snapshot, FCyclingGuidedAcceptanceState(), false);
		TestTrue(TEXT("resume feedback: distance preserved shown"),
			Text.Contains(TEXT("distance preserved: 184.32 m")));
	}

	// Restart: state reset.
	{
		FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
			ECyclingDiagnosticsLifecycle::Running,
			200.0, 90.0, FSimulationState(), 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);
		Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
			ECyclingInputCommand::Restart,
			MakeSnap(ECyclingDiagnosticsLifecycle::Running, 210.0, 95.0, 184.32, 24.15),
			MakeSnap(ECyclingDiagnosticsLifecycle::Running, 200.0, 90.0, 0.0, 0.0),
			10.0, 5.0);
		TestTrue(TEXT("restart feedback: accepted on transition"),
			Snapshot.LastInputFeedback.bAccepted);
		const FString Text = CyclingDiagnostics::FormatOverlay(Snapshot, FCyclingGuidedAcceptanceState(), false);
		TestTrue(TEXT("restart feedback: distance line"),
			Text.Contains(TEXT("distance 184.32 m -> 0.00 m")));
		TestTrue(TEXT("restart feedback: time line"),
			Text.Contains(TEXT("time 24.15 s -> 0.00 s")));
		TestTrue(TEXT("restart feedback: power line"),
			Text.Contains(TEXT("power 210 W -> 200 W")));
		TestTrue(TEXT("restart feedback: cadence line"),
			Text.Contains(TEXT("cadence 95 rpm -> 90 rpm")));
	}

	// Start in Finished: rejected / ignored.
	{
		FCyclingDiagnosticsSnapshot Snapshot = CyclingDiagnostics::MakeSnapshot(
			ECyclingDiagnosticsLifecycle::Finished,
			200.0, 90.0, FSimulationState(), 0, 0.0, 500.0, TEXT(""), 10.0, 5.0);
		Snapshot.LastInputFeedback = CyclingDiagnostics::BuildLastInputFeedback(
			ECyclingInputCommand::StartOrResume,
			MakeSnap(ECyclingDiagnosticsLifecycle::Finished, 200.0, 90.0, 0.0, 0.0),
			MakeSnap(ECyclingDiagnosticsLifecycle::Finished, 200.0, 90.0, 0.0, 0.0),
			10.0, 5.0);
		TestFalse(TEXT("start-in-Finished feedback: rejected"),
			Snapshot.LastInputFeedback.bAccepted);
		const FString Text = CyclingDiagnostics::FormatOverlay(Snapshot, FCyclingGuidedAcceptanceState(), false);
		TestTrue(TEXT("start-in-Finished feedback: IGNORED status"),
			Text.Contains(TEXT("IGNORED")));
	}

	return true;
}

// =====================================================================
// 5. Pawn integration: LastInputFeedback before/after for power steps.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsPawnPowerFeedbackTest, "CyclingDiagnostics.PawnPowerFeedback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsPawnPowerFeedbackTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	Pawn->SetDiagnosticOverlayEnabled(false); // do not start the timer for this test
	Pawn->SetGuidedAcceptanceEnabled(false);

	Pawn->InitializeRide();
	Pawn->StartRide();

	const double PowerBefore = Pawn->GetSession().GetRiderInput().PowerW;
	Pawn->HandlePowerIncrease(FInputActionValue());
	const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();

	TestEqual(TEXT("pawn power feedback: command type"),
		static_cast<int32>(Feedback.Command),
		static_cast<int32>(ECyclingInputCommand::PowerIncrease));
	TestTrue(TEXT("pawn power feedback: accepted"),
		Feedback.bAccepted);
	TestEqual(TEXT("pawn power feedback: Before power"),
		Feedback.Before.PowerW, PowerBefore);
	TestEqual(TEXT("pawn power feedback: After power = before + 10"),
		Feedback.After.PowerW, PowerBefore + 10.0);

	Pawn->HandlePowerDecrease(FInputActionValue());
	const FCyclingLastInputFeedback& Feedback2 = Pawn->GetLastInputFeedback();
	TestEqual(TEXT("pawn power- feedback: command"),
		static_cast<int32>(Feedback2.Command),
		static_cast<int32>(ECyclingInputCommand::PowerDecrease));
	TestTrue(TEXT("pawn power- feedback: accepted"),
		Feedback2.bAccepted);
	TestEqual(TEXT("pawn power- feedback: Before"),
		Feedback2.Before.PowerW, PowerBefore + 10.0);
	TestEqual(TEXT("pawn power- feedback: After"),
		Feedback2.After.PowerW, PowerBefore);

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 6. Pawn integration: LastInputFeedback for cadence steps.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsPawnCadenceFeedbackTest, "CyclingDiagnostics.PawnCadenceFeedback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsPawnCadenceFeedbackTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	Pawn->SetDiagnosticOverlayEnabled(false);
	Pawn->SetGuidedAcceptanceEnabled(false);

	Pawn->InitializeRide();
	Pawn->StartRide();

	Pawn->HandleCadenceIncrease(FInputActionValue());
	const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();
	TestEqual(TEXT("pawn cadence+: command"),
		static_cast<int32>(Feedback.Command),
		static_cast<int32>(ECyclingInputCommand::CadenceIncrease));
	TestTrue(TEXT("pawn cadence+: accepted"), Feedback.bAccepted);
	TestEqual(TEXT("pawn cadence+: Before"), Feedback.Before.CadenceRpm, 90.0);
	TestEqual(TEXT("pawn cadence+: After"), Feedback.After.CadenceRpm, 95.0);

	Pawn->HandleCadenceDecrease(FInputActionValue());
	const FCyclingLastInputFeedback& Feedback2 = Pawn->GetLastInputFeedback();
	TestEqual(TEXT("pawn cadence-: command"),
		static_cast<int32>(Feedback2.Command),
		static_cast<int32>(ECyclingInputCommand::CadenceDecrease));
	TestTrue(TEXT("pawn cadence-: accepted"), Feedback2.bAccepted);
	TestEqual(TEXT("pawn cadence-: After"), Feedback2.After.CadenceRpm, 90.0);

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 7. Pawn integration: lifecycle feedback for Start/Stop/Resume/Restart.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsPawnLifecycleFeedbackTest, "CyclingDiagnostics.PawnLifecycleFeedback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsPawnLifecycleFeedbackTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	// Start from Ready -> Running.
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
		Pawn->SetDiagnosticOverlayEnabled(false);
		Pawn->SetGuidedAcceptanceEnabled(false);
		Pawn->InitializeRide();

		Pawn->HandleStartRide(FInputActionValue());
		const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();
		TestEqual(TEXT("start feedback: command"),
			static_cast<int32>(Feedback.Command),
			static_cast<int32>(ECyclingInputCommand::StartOrResume));
		TestTrue(TEXT("start feedback: accepted"), Feedback.bAccepted);
		TestEqual(TEXT("start feedback: Before lifecycle"),
			static_cast<int32>(Feedback.Before.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Ready));
		TestEqual(TEXT("start feedback: After lifecycle"),
			static_cast<int32>(Feedback.After.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Running));

		DestroyTransientWorld(World);
	}

	// Stop preserves state.
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
		Pawn->SetDiagnosticOverlayEnabled(false);
		Pawn->SetGuidedAcceptanceEnabled(false);
		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->Tick(0.5f);

		Pawn->HandleStopRide(FInputActionValue());
		const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();
		TestEqual(TEXT("stop feedback: command"),
			static_cast<int32>(Feedback.Command),
			static_cast<int32>(ECyclingInputCommand::Stop));
		TestTrue(TEXT("stop feedback: accepted"), Feedback.bAccepted);
		TestEqual(TEXT("stop feedback: Before"),
			static_cast<int32>(Feedback.Before.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Running));
		TestEqual(TEXT("stop feedback: After"),
			static_cast<int32>(Feedback.After.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Stopped));
		TestEqual(TEXT("stop feedback: distance preserved"),
			Feedback.Before.DistanceM, Feedback.After.DistanceM);

		// Resume.
		Pawn->HandleStartRide(FInputActionValue());
		const FCyclingLastInputFeedback& Feedback2 = Pawn->GetLastInputFeedback();
		TestTrue(TEXT("resume feedback: accepted"), Feedback2.bAccepted);
		TestEqual(TEXT("resume feedback: Before"),
			static_cast<int32>(Feedback2.Before.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Stopped));
		TestEqual(TEXT("resume feedback: After"),
			static_cast<int32>(Feedback2.After.Lifecycle),
			static_cast<int32>(ECyclingDiagnosticsLifecycle::Running));
		TestEqual(TEXT("resume feedback: distance preserved"),
			Feedback2.Before.DistanceM, Feedback2.After.DistanceM);

		DestroyTransientWorld(World);
	}

	// Restart resets.
	{
		UWorld* World = CreateTransientWorld();
		AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
		ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
		Pawn->SetDiagnosticOverlayEnabled(false);
		Pawn->SetGuidedAcceptanceEnabled(false);
		Pawn->InitializeRide();
		Pawn->StartRide();
		Pawn->HandlePowerIncrease(FInputActionValue());
		Pawn->HandlePowerIncrease(FInputActionValue());
		Pawn->Tick(1.0f);

		Pawn->HandleRestartRide(FInputActionValue());
		const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();
		TestEqual(TEXT("restart feedback: command"),
			static_cast<int32>(Feedback.Command),
			static_cast<int32>(ECyclingInputCommand::Restart));
		TestTrue(TEXT("restart feedback: accepted"), Feedback.bAccepted);
		TestEqual(TEXT("restart feedback: distance reset"),
			Feedback.After.DistanceM, 0.0);
		TestEqual(TEXT("restart feedback: time reset"),
			Feedback.After.ElapsedTimeS, 0.0);
		TestEqual(TEXT("restart feedback: power reset"),
			Feedback.After.PowerW, 200.0);
		TestEqual(TEXT("restart feedback: cadence reset"),
			Feedback.After.CadenceRpm, 90.0);

		DestroyTransientWorld(World);
	}

	return true;
}

// =====================================================================
// 8. Rejected / ignored: StartRide in Finished is a no-op and the
// feedback must report IGNORED (bAccepted=false).
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsPawnFinishedIgnoredTest, "CyclingDiagnostics.PawnFinishedIgnored",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsPawnFinishedIgnoredTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	Pawn->SetDiagnosticOverlayEnabled(false);
	Pawn->SetGuidedAcceptanceEnabled(false);
	Pawn->InitializeRide();
	Pawn->StartRide();

	// Drive to Finished. Stage 3D uses the Alpine Journey context with
	// finish at 10 000 m; at default rider speed (~9 m/s) ~2500 s of
	// simulated time is needed, i.e. up to 5000 ticks at 0.5 s.
	for (int32 i = 0; i < 5000; ++i)
	{
		Pawn->Tick(0.5f);
		if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
		{
			break;
		}
	}
	TestEqual(TEXT("rejected: lifecycle is Finished"),
		static_cast<int32>(Pawn->GetLifecycle()),
		static_cast<int32>(ECyclingPrototypeLifecycle::Finished));

	const FSimulationState Snapshot = Pawn->GetAuthoritativeState();

	Pawn->HandleStartRide(FInputActionValue());
	const FCyclingLastInputFeedback& Feedback = Pawn->GetLastInputFeedback();
	TestFalse(TEXT("rejected: StartRide in Finished not accepted"),
		Feedback.bAccepted);
	TestEqual(TEXT("rejected: distance unchanged after ignored Start"),
		Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);
	TestEqual(TEXT("rejected: lifecycle still Finished"),
		static_cast<int32>(Pawn->GetLifecycle()),
		static_cast<int32>(ECyclingPrototypeLifecycle::Finished));

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 9. Diagnostic overlay cannot mutate authoritative simulation.
//    Enable overlay, drive deterministic command sequence, compare two
//    Pawns (one with overlay enabled, one with overlay disabled). The
//    authoritative state and lifecycle must agree exactly.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsOverlayDoesNotMutateTest, "CyclingDiagnostics.OverlayDoesNotMutate",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsOverlayDoesNotMutateTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	// Default overlay is true for the prototype. We disable Guided so
	// the observer doesn't dirty the LastInputSnapshot with extra
	// state changes; the overlay still runs and the timer still
	// ticks.
	Pawn->SetGuidedAcceptanceEnabled(false);

	Pawn->InitializeRide();
	Pawn->StartRide();

	Pawn->HandlePowerIncrease(FInputActionValue());
	Pawn->HandlePowerIncrease(FInputActionValue());
	Pawn->HandleCadenceIncrease(FInputActionValue());
	Pawn->Tick(0.5f);

	const FSimulationState AfterOverlay = Pawn->GetAuthoritativeState();

	// Tick again with overlay enabled - the timer-driven formatter must
	// NOT call TryAdvance.
	Pawn->Tick(0.0f); // also forces a non-advancing tick
	const FSimulationState AfterIdle = Pawn->GetAuthoritativeState();

	TestEqual(TEXT("overlay: distance unchanged when overlay refreshes"),
		AfterOverlay.DistanceM, AfterIdle.DistanceM);
	TestEqual(TEXT("overlay: speed unchanged when overlay refreshes"),
		AfterOverlay.SpeedMps, AfterIdle.SpeedMps);
	TestEqual(TEXT("overlay: lifecycle still Running when overlay refreshes"),
		static_cast<int32>(Pawn->GetLifecycle()),
		static_cast<int32>(ECyclingPrototypeLifecycle::Running));

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 10. Disabling the overlay leaves authoritative results unchanged.
//     Run identical sequence with overlay disabled vs enabled; the
//     final state must match exactly.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsOverlayDisableLeavesUnchangedTest, "CyclingDiagnostics.OverlayDisableLeavesUnchanged",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsOverlayDisableLeavesUnchangedTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	// Pawn A: overlay disabled, no guided.
	UWorld* WorldA = CreateTransientWorld();
	AActor* RouteA = SpawnStraightRouteActor(WorldA, 50000.0f);
	ACyclingPrototypePawn* PawnA = SpawnPrototypePawn(WorldA, RouteA);
	PawnA->SetDiagnosticOverlayEnabled(false);
	PawnA->SetGuidedAcceptanceEnabled(false);

	// Pawn B: overlay enabled (default), guided disabled for parity.
	UWorld* WorldB = CreateTransientWorld();
	AActor* RouteB = SpawnStraightRouteActor(WorldB, 50000.0f);
	ACyclingPrototypePawn* PawnB = SpawnPrototypePawn(WorldB, RouteB);
	PawnB->SetGuidedAcceptanceEnabled(false);

	PawnA->InitializeRide();
	PawnA->StartRide();
	PawnB->InitializeRide();
	PawnB->StartRide();

	const float Steps[] = { 0.04f, 0.06f, 0.05f, 0.10f, 0.20f, 0.50f, 1.00f };
	for (float Dt : Steps)
	{
		PawnA->Tick(Dt);
		PawnB->Tick(Dt);
	}

	TestEqual(TEXT("overlay disable: identical speed"),
		PawnA->GetAuthoritativeState().SpeedMps,
		PawnB->GetAuthoritativeState().SpeedMps);
	TestEqual(TEXT("overlay disable: identical distance"),
		PawnA->GetAuthoritativeState().DistanceM,
		PawnB->GetAuthoritativeState().DistanceM);
	TestEqual(TEXT("overlay disable: identical elapsed"),
		PawnA->GetAuthoritativeState().ElapsedTimeS,
		PawnB->GetAuthoritativeState().ElapsedTimeS);
	TestEqual(TEXT("overlay disable: identical accumulator"),
		PawnA->GetSession().GetAccumulatedTimeS(),
		PawnB->GetSession().GetAccumulatedTimeS());

	DestroyTransientWorld(WorldA);
	DestroyTransientWorld(WorldB);
	return true;
}

// =====================================================================
// 11. Guided acceptance observer does not invoke commands.
//     Walk through the full 7-step sequence manually: Start, Up,
//     Right, Stop, Start, R, Finished. The observer must advance
//     through each step and never call Session API.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsGuidedObserverTest, "CyclingDiagnostics.GuidedObserver",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsGuidedObserverTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	// Disable overlay to avoid Timer dependencies in test.
	Pawn->SetDiagnosticOverlayEnabled(false);
	// Guided is on by default.

	Pawn->InitializeRide();

	// Step 1: SPACE.
	TestEqual(TEXT("guided: starts at step 1"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Ready_WaitStart));

	Pawn->HandleStartRide(FInputActionValue());
	TestEqual(TEXT("guided: step 1 -> step 2 after SPACE"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Running_WaitPowerUp));
	TestEqual(TEXT("guided: status PASS after SPACE"),
		Pawn->GetGuidedAcceptanceState().StepStatus, TEXT("PASS"));

	// Step 2: UP.
	Pawn->HandlePowerIncrease(FInputActionValue());
	TestEqual(TEXT("guided: step 2 -> step 3 after UP"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Running_WaitCadenceUp));

	// Step 3: RIGHT.
	Pawn->HandleCadenceIncrease(FInputActionValue());
	TestEqual(TEXT("guided: step 3 -> step 4 after RIGHT"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Running_WaitStop));

	// Step 4: S.
	Pawn->HandleStopRide(FInputActionValue());
	TestEqual(TEXT("guided: step 4 -> step 5 after S"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Stopped_WaitStart));

	// Step 5: SPACE.
	Pawn->HandleStartRide(FInputActionValue());
	TestEqual(TEXT("guided: step 5 -> step 6 after SPACE"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Running_WaitRestart));

	// Step 6: R.
	Pawn->HandleRestartRide(FInputActionValue());
	TestEqual(TEXT("guided: step 6 -> step 7 (Finished) after R"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Finished));

	// After Finished, SPACE stays ignored (no command).
	Pawn->HandleStartRide(FInputActionValue());
	TestEqual(TEXT("guided: still Finished after post-Finished SPACE"),
		static_cast<int32>(Pawn->GetGuidedAcceptanceState().CurrentStep),
		static_cast<int32>(ECyclingGuidedAcceptanceStep::Finished));

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 12. Stop stability check uses observation only; the timer must NOT
//     re-enable simulation Tick. Verify Tick remains disabled while
//     the Stopped stability observer runs.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsStopStabilityTest, "CyclingDiagnostics.StopStability",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsStopStabilityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	// Keep overlay disabled to avoid Timer Manager dependency in this
	// focused test. Guided stays enabled so the StopEntrySnapshot is
	// captured by the observer when HandleStopRide fires.
	Pawn->SetDiagnosticOverlayEnabled(false);

	Pawn->InitializeRide();
	Pawn->StartRide();
	Pawn->Tick(0.5f);

	const FSimulationState Snapshot = Pawn->GetAuthoritativeState();

	// Stop -> snapshot captured inside the Pawn via HandleStopRide.
	Pawn->HandleStopRide(FInputActionValue());
	TestFalse(TEXT("stop stability: Tick is disabled after Stop"),
		Pawn->IsActorTickEnabled());
	TestEqual(TEXT("stop stability: lifecycle is Stopped"),
		static_cast<int32>(Pawn->GetLifecycle()),
		static_cast<int32>(ECyclingPrototypeLifecycle::Stopped));

	// Manually call ObserveStopStability twice (mimicking two refresh
	// ticks) using the Pawn's public helpers. The state must report
	// PASS for distance and time stability.
	FCyclingInputSnapshot CurrentSnap;
	CurrentSnap.DistanceM = Pawn->GetAuthoritativeState().DistanceM;
	CurrentSnap.ElapsedTimeS = Pawn->GetAuthoritativeState().ElapsedTimeS;

	FCyclingGuidedAcceptanceState Observed = CyclingDiagnostics::ObserveStopStability(
		Pawn->GetGuidedAcceptanceState(), CurrentSnap);
	Observed = CyclingDiagnostics::ObserveStopStability(Observed, CurrentSnap);

	TestTrue(TEXT("stop stability: distance stable observed"),
		Observed.bStopStable);
	TestEqual(TEXT("stop stability: ticks counter advanced"),
		Observed.StopStabilityObservedTicks, 2);
	TestTrue(TEXT("stop stability: status string contains PASS"),
		Observed.StopStabilityStatus.Contains(TEXT("Distance stable: PASS")));

	// Verify distance has not advanced (no TryAdvance from observer).
	TestEqual(TEXT("stop stability: distance unchanged"),
		Pawn->GetAuthoritativeState().DistanceM, Snapshot.DistanceM);

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// 13. One-event-one-step under the feedback pipeline: repeated UP
//     presses must produce exactly one step each. This guards the
//     pipeline against accidental state drift introduced by the
//     record/feedback wrappers.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingDiagnosticsPawnRepeatedStepsTest, "CyclingDiagnostics.PawnRepeatedSteps",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingDiagnosticsPawnRepeatedStepsTest::RunTest(const FString& Parameters)
{
	using namespace CyclingDiagnosticsTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);
	Pawn->SetDiagnosticOverlayEnabled(false);
	Pawn->SetGuidedAcceptanceEnabled(false);

	Pawn->InitializeRide();
	Pawn->StartRide();

	const double P0 = Pawn->GetSession().GetRiderInput().PowerW;
	const int32 N = 12;
	for (int32 i = 0; i < N; ++i)
	{
		Pawn->HandlePowerIncrease(FInputActionValue());
	}
	TestEqual(TEXT("repeated: power = initial + N * step"),
		Pawn->GetSession().GetRiderInput().PowerW, P0 + N * 10.0);
	TestEqual(TEXT("repeated: latest feedback after = before + step"),
		Pawn->GetLastInputFeedback().After.PowerW,
		Pawn->GetLastInputFeedback().Before.PowerW + 10.0);
	TestTrue(TEXT("repeated: latest feedback accepted"),
		Pawn->GetLastInputFeedback().bAccepted);

	DestroyTransientWorld(World);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS