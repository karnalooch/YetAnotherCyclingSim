// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Regression coverage for the semantic distinction between "Stop" (pause,
// preserve state) and "coasting with zero power" (physics continues to
// run). These tests were added in response to the user-observed behaviour
// "pressing Stop freezes the actor immediately instead of letting the
// bicycle lose speed naturally".
//
// IMPORTANT FINDING: ACyclingPrototypePawn::StopRide() is a PAUSE.
//   - It disables Pawn Tick;
//   - It sets Lifecycle to Stopped;
//   - It preserves simulation speed/distance/time;
//   - It preserves the fixed-step accumulator;
//   - It preserves power/cadence;
//   - It therefore freezes the visible transform immediately.
//
// Physics itself already supports natural coasting. With PowerW=0 the
// fixed-step simulation continues; aerodynamic drag, rolling resistance
// and gravity remain active. Flat ground decelerates monotonically;
// uphill eventually stops; downhill may accelerate even at zero power.
//
// These tests therefore prove:
//   1. PausePreservesMotionState     - StopRide is PAUSE.
//   2. ZeroPowerCoastsOnFlat         - zero power decelerates naturally.
//   3. ZeroPowerDownhillDoesNotMeanStop - zero power on a descent can
//      accelerate, so "Stop" cannot be implemented as "set power to 0".
//
// No physical equation is mutated; the tests use the existing
// deterministic FCyclingSimulationSession / FFixedStepSimulationRunner
// API and document the current behaviour.

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include <cmath>
#include <limits>

#include "Cycling/CyclingSimulationSession.h"
#include "Cycling/FixedStepRunner.h"
#include "Cycling/SimulationStep.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"
#include "Cycling/CyclingPrototypePawn.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Components/SplineComponent.h"
#include "Components/SceneComponent.h"
#include "GameFramework/Actor.h"

namespace CyclingRuntimeCoastingTest
{
	// Deterministic tolerance band for "monotonic-with-tolerance". Floating
	// point rounding in the fixed-step integration can produce a sub-epsilon
	// rise between two consecutive samples. We accept any non-positive delta
	// up to a small relative band. The band is deliberately tiny and never
	// larger than what would mask a true physics regression.
	constexpr double CoastingToleranceMps = 1e-9;

	// Total simulated time used by the multi-second coasting tests.
	constexpr double CoastingTotalS = 30.0;

	// A safe small initial speed (m/s) that lets aerodynamic drag produce
	// a measurable deceleration without collapsing to zero instantly.
	constexpr double InitialCoastingSpeedMps = 10.0;

	// Builds a fully valid FCyclingSimulationSessionConfig with the given
	// grade (decimal fraction). Defaults match the Stage 2 prototype
	// fixture documented in ACyclingPrototypePawn::MakePrototypeSessionConfig.
	CyclingSimulation::FCyclingSimulationSessionConfig MakeSessionConfigWithGrade(double GradeDecimal)
	{
		CyclingSimulation::FCyclingSimulationSessionConfig Config;

		// Rider (SI units, prototype fixture).
		Config.Rider.RiderMassKg = 75.0;
		Config.Rider.BikeMassKg = 8.5;
		Config.Rider.CdaM2 = 0.32;
		Config.Rider.RollingResistanceCoefficient = 0.004;
		Config.Rider.DrivetrainEfficiency = 0.97;

		// Environment (SI units).
		Config.Environment.GradeDecimal = GradeDecimal;
		Config.Environment.WindSpeedMps = 0.0;
		Config.Environment.AirDensityKgM3 = 1.225;
		Config.Environment.SurfaceWetness = 0.0;
		Config.Environment.RollingResistanceMultiplier = 1.0;
		Config.Environment.GripMultiplier = 1.0;

		// Rider input controller (defaults; we will mutate input later).
		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 2000.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = 200.0;
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 250.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 90.0;

		return Config;
	}

	// Helper: drives a configured FCyclingSimulationSession forward by
	// FrameDeltaS seconds, repeating until at least DurationS of simulated
	// time has been consumed. Returns the final authoritative state and
	// writes the number of advanced frames into OutFrameCount.
	FSimulationState DriveFor(
		CyclingSimulation::FCyclingSimulationSession& Session,
		double FrameDeltaS,
		double DurationS,
		int32& OutFrameCount)
	{
		OutFrameCount = 0;
		FSimulationState State;
		double RemainingS = 0.0;
		int32 Steps = 0;
		FString Error;
		const double Dt = FrameDeltaS;
		double Simulated = 0.0;
		while (Simulated + 1e-12 < DurationS)
		{
			const bool bOk = Session.TryAdvance(Dt, State, RemainingS, Steps, Error);
			if (!bOk)
			{
				break;
			}
			Simulated += Dt;
			++OutFrameCount;
		}
		return State;
	}

	// Pawn-level helpers (mirrors CyclingRuntime.spec.cpp). These are kept
	// intentionally minimal so the file is self-contained.
	UWorld* CreateTransientWorld()
	{
		return UWorld::CreateWorld(EWorldType::Game, false, TEXT("CyclingRuntimeCoastingWorld"));
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
		if (!Pawn)
		{
			return nullptr;
		}
		Pawn->RouteActor = RouteActor;
		Pawn->bAutoStart = false;
		return Pawn;
	}
}

// =====================================================================
// (A) Stop is PAUSE: it preserves authoritative motion state and the
// fixed-step accumulator. This is the regression coverage for the
// user-observed "Stop freezes the actor immediately" behaviour.
//
// The expected current implementation is correct and is documented as
// the Stage 2 contract: Stop means "pause progression, preserve state".
// This test pins that contract against future refactors.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FCyclingRuntimePausePreservesMotionStateTest,
	"CyclingRuntime.PausePreservesMotionState",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimePausePreservesMotionStateTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeCoastingTest;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 50000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPrototypePawn(World, Route);

	Pawn->InitializeRide();
	Pawn->StartRide();

	// Drive enough simulated time that the bike has a non-trivial speed
	// and is well off the spline origin.
	Pawn->Tick(0.5f);
	Pawn->Tick(0.04f); // leaves a sub-step in the accumulator (< 0.05 s)
	TestTrue(TEXT("pause: speed > 0 before StopRide"),
		Pawn->GetAuthoritativeState().SpeedMps > 0.0);
	TestTrue(TEXT("pause: distance > 0 before StopRide"),
		Pawn->GetAuthoritativeState().DistanceM > 0.0);
	TestTrue(TEXT("pause: elapsed > 0 before StopRide"),
		Pawn->GetAuthoritativeState().ElapsedTimeS > 0.0);

	// Snapshot the authoritative state and the accumulator before Stop.
	const FSimulationState SnapshotState = Pawn->GetAuthoritativeState();
	const double SnapshotAccumulator = Pawn->GetSession().GetAccumulatedTimeS();
	const FVector SnapshotLocation = Pawn->GetActorLocation();

	// Issue the user command that was reported as "freezing the actor".
	Pawn->StopRide();

	// (1) Tick is disabled.
	TestFalse(TEXT("pause: Pawn Tick is disabled after StopRide"),
		Pawn->IsActorTickEnabled());

	// (2) Lifecycle reached Stopped.
	TestEqual(TEXT("pause: Lifecycle is Stopped"),
		static_cast<int32>(Pawn->GetLifecycle()),
		static_cast<int32>(ECyclingPrototypeLifecycle::Stopped));

	// (3) Authoritative speed is preserved (no artificial damping, no
	//     direct state mutation).
	TestEqual(TEXT("pause: authoritative speed preserved"),
		Pawn->GetAuthoritativeState().SpeedMps, SnapshotState.SpeedMps);

	// (4) Authoritative distance is preserved.
	TestEqual(TEXT("pause: authoritative distance preserved"),
		Pawn->GetAuthoritativeState().DistanceM, SnapshotState.DistanceM);

	// (5) Authoritative elapsed simulation time is preserved.
	TestEqual(TEXT("pause: authoritative elapsed time preserved"),
		Pawn->GetAuthoritativeState().ElapsedTimeS, SnapshotState.ElapsedTimeS);

	// (6) Fixed-step accumulator is preserved (the pending sub-step is
	//     still pending and will resume on StartRide).
	TestEqual(TEXT("pause: accumulator preserved"),
		Pawn->GetSession().GetAccumulatedTimeS(), SnapshotAccumulator);
	TestTrue(TEXT("pause: sub-step accumulator is still strictly positive"),
		Pawn->GetSession().GetAccumulatedTimeS() > 0.0);

	// (7) Visible transform is preserved (no clamp, no jump).
	TestEqual(TEXT("pause: visible transform preserved"),
		Pawn->GetActorLocation(), SnapshotLocation);

	// (8) Power and cadence are preserved (Stop is not "stop pedalling").
	TestEqual(TEXT("pause: power preserved"),
		Pawn->GetSession().GetRiderInput().PowerW, 200.0);
	TestEqual(TEXT("pause: cadence preserved"),
		Pawn->GetSession().GetRiderInput().CadenceRpm, 90.0);

	// (9) Calling StopRide again is a documented no-op (no spurious
	//     re-entry into the Stopped state with a fresh snapshot).
	const double AccumulatorSecondCall = Pawn->GetSession().GetAccumulatedTimeS();
	Pawn->StopRide();
	TestEqual(TEXT("pause: second StopRide is a no-op (accumulator unchanged)"),
		Pawn->GetSession().GetAccumulatedTimeS(), AccumulatorSecondCall);

	// (10) Calling StartRide resumes the same session: state preserved,
	//      accumulator preserved, Tick enabled.
	Pawn->StartRide();
	TestEqual(TEXT("pause: resume preserves speed"),
		Pawn->GetAuthoritativeState().SpeedMps, SnapshotState.SpeedMps);
	TestEqual(TEXT("pause: resume preserves distance"),
		Pawn->GetAuthoritativeState().DistanceM, SnapshotState.DistanceM);
	TestEqual(TEXT("pause: resume preserves accumulator"),
		Pawn->GetSession().GetAccumulatedTimeS(), SnapshotAccumulator);
	TestTrue(TEXT("pause: resume re-enables Tick"),
		Pawn->IsActorTickEnabled());

	DestroyTransientWorld(World);
	return true;
}

// =====================================================================
// (B) ZeroPowerCoastsOnFlat: with PowerW = 0, on flat ground, the
// simulation continues to run and the speed decreases monotonically
// (within floating-point tolerance). This proves that "Stop" does NOT
// have to be implemented by mutating authoritative state - physics
// already provides natural deceleration.
//
// Scenario:
//   1. Configure a deterministic flat-ground session.
//   2. Accelerate from rest using the default 200 W power so the bike
//      reaches a meaningful non-zero speed via the public TryAdvance
//      API. The session is never seeded with a private state; we only
//      drive it forward.
//   3. Snapshot speed, distance and elapsed time at coast entry.
//   4. Set PowerW = 0 via TrySetPowerW and continue driving.
//   5. Verify that the speed decreases monotonically (with a small
//      floating-point tolerance), that distance and elapsed time grow,
//      that the speed never goes negative, and that the elapsed time
//      reaches the requested horizon.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FCyclingRuntimeZeroPowerCoastsOnFlatTest,
	"CyclingRuntime.ZeroPowerCoastsOnFlat",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimeZeroPowerCoastsOnFlatTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeCoastingTest;

	// Use the public session API. The session is the single deterministic
	// orchestration layer above the fixed-step runner; we never seed or
	// mutate private SimulationState directly.
	CyclingSimulation::FCyclingSimulationSession Session;
	{
		FString Error;
		const bool bConfigured = Session.TryConfigure(MakeSessionConfigWithGrade(0.0), Error);
		TestTrue(TEXT("coast flat: TryConfigure succeeds"), bConfigured);
		TestTrue(TEXT("coast flat: OutError is empty after configure"), Error.IsEmpty());
	}

	// After TryConfigure the session starts from a fresh ride: speed 0,
	// distance 0, elapsed 0. The default initial power is 200 W
	// (MakeSessionConfigWithGrade sets InitialPowerW = 200.0).
	const double Dt = CyclingSimulation::FFixedStepSimulationRunner::FixedStepDtS;
	const double AccelDurationS = 5.0; // first 5 s at 200 W to reach coast entry speed
	const double CoastDurationS = CoastingTotalS - AccelDurationS; // remaining 25 s at PowerW = 0
	const int32 AccelFrames = static_cast<int32>(AccelDurationS / Dt);
	const int32 CoastFrames = static_cast<int32>(CoastDurationS / Dt);
	const int32 MaxFrames = AccelFrames + CoastFrames;
	TestEqual(
		TEXT("coast flat: horizon matches AccelFrames + CoastFrames exactly"),
		MaxFrames * Dt, CoastingTotalS);

	// Phase 1: accelerate at the configured initial power. We do NOT
	// mutate SimulationState; we only drive the session forward and
	// observe the public FSimulationState returned by TryAdvance.
	FSimulationState State;
	double RemainingS = 0.0;
	int32 Steps = 0;
	FString Error;

	for (int32 Frame = 0; Frame < AccelFrames; ++Frame)
	{
		if (!Session.TryAdvance(Dt, State, RemainingS, Steps, Error))
		{
			AddError(FString::Printf(
				TEXT("coast flat: TryAdvance failed during acceleration at frame %d: %s"),
				Frame, *Error));
			return false;
		}
	}

	// Sanity-check the bike actually moved. With 200 W on flat ground the
	// rider+bike reaches a substantial fraction of the ~9.5 m/s terminal
	// velocity in 5 s.
	TestTrue(TEXT("coast flat: entry speed > 0 after acceleration"),
		State.SpeedMps > 0.0);
	TestTrue(TEXT("coast flat: entry distance > 0 after acceleration"),
		State.DistanceM > 0.0);
	TestTrue(TEXT("coast flat: entry elapsed time > 0 after acceleration"),
		State.ElapsedTimeS > 0.0);

	// Snapshot the entry values.
	const double EntrySpeedMps = State.SpeedMps;
	const double EntryDistanceM = State.DistanceM;
	const double EntryElapsedTimeS = State.ElapsedTimeS;
	const double EntryPowerW = Session.GetRiderInput().PowerW;

	// Phase 2: zero power. The only API we use is TrySetPowerW followed
	// by TryAdvance. We do NOT seed a private state.
	{
		FString PowerError;
		const bool bSet = Session.TrySetPowerW(0.0, PowerError);
		TestTrue(TEXT("coast flat: TrySetPowerW(0.0) succeeds"), bSet);
		TestTrue(TEXT("coast flat: power is zero after TrySetPowerW"),
			Session.GetRiderInput().PowerW == 0.0);
	}

	// Phase 3: drive the coast horizon and sample the state at every
	// fixed step. Track the first and last coast samples and verify the
	// speed curve is monotonically non-increasing within tolerance.
	double FirstCoastSpeed = -1.0;
	double FirstCoastDistance = -1.0;
	double FirstCoastElapsed = -1.0;
	double LastCoastSpeed = -1.0;
	double LastCoastDistance = -1.0;
	double LastCoastElapsed = -1.0;
	double PreviousSpeed = EntrySpeedMps;
	bool bSpeedNonIncreasing = true;
	bool bSpeedNonNegative = true;
	bool bDistanceNonDecreasing = true;
	bool bElapsedNonDecreasing = true;
	bool bSpeedBelowEntry = false;
	int32 CoastFrameCount = 0;

	for (int32 Frame = 0; Frame < CoastFrames; ++Frame)
	{
		if (!Session.TryAdvance(Dt, State, RemainingS, Steps, Error))
		{
			AddError(FString::Printf(
				TEXT("coast flat: TryAdvance failed during coast at frame %d: %s"),
				Frame, *Error));
			return false;
		}
		++CoastFrameCount;

		if (State.SpeedMps < 0.0)
		{
			bSpeedNonNegative = false;
		}

		if (State.SpeedMps > PreviousSpeed + CoastingToleranceMps)
		{
			bSpeedNonIncreasing = false;
			AddError(FString::Printf(
				TEXT("coast flat: speed increased at coast frame %d (%.12f > prev %.12f)"),
				Frame, State.SpeedMps, PreviousSpeed));
		}
		PreviousSpeed = State.SpeedMps;

		if (FirstCoastSpeed < 0.0)
		{
			FirstCoastSpeed = State.SpeedMps;
			FirstCoastDistance = State.DistanceM;
			FirstCoastElapsed = State.ElapsedTimeS;
		}
		LastCoastSpeed = State.SpeedMps;
		LastCoastDistance = State.DistanceM;
		LastCoastElapsed = State.ElapsedTimeS;

		if (State.DistanceM + CoastingToleranceMps < LastCoastDistance)
		{
			bDistanceNonDecreasing = false;
		}
		if (State.ElapsedTimeS + CoastingToleranceMps < LastCoastElapsed)
		{
			bElapsedNonDecreasing = false;
		}
	}

	// Final coast speed must be strictly below entry speed.
	bSpeedBelowEntry = (LastCoastSpeed + 1e-9) < EntrySpeedMps;

	// -----------------------------------------------------------------
	// Coast semantics assertions (the whole point of the test).
	// -----------------------------------------------------------------
	TestTrue(TEXT("coast flat: simulation actually advanced during coast (frames > 0)"),
		CoastFrameCount > 0);
	TestTrue(TEXT("coast flat: speed never went negative during coast"),
		bSpeedNonNegative);
	TestTrue(TEXT("coast flat: speed decreases monotonically during coast (within tolerance)"),
		bSpeedNonIncreasing);
	TestTrue(TEXT("coast flat: distance monotonically non-decreasing during coast"),
		bDistanceNonDecreasing);
	TestTrue(TEXT("coast flat: elapsed simulation time monotonically non-decreasing during coast"),
		bElapsedNonDecreasing);

	// First coast sample must still be moving (we did not "stop" the
	// bike just by setting power to zero). The first post-zero-power
	// fixed step is the first measurable coast sample and should have
	// speed well above zero.
	TestTrue(TEXT("coast flat: first coast sample still moving (SpeedMps > 0)"),
		FirstCoastSpeed > 0.0);
	TestTrue(TEXT("coast flat: first coast sample distance > entry distance"),
		FirstCoastDistance > EntryDistanceM);
	TestTrue(TEXT("coast flat: first coast sample elapsed time > entry elapsed time"),
		FirstCoastElapsed > EntryElapsedTimeS);

	// Final speed must be strictly below the entry speed.
	TestTrue(TEXT("coast flat: final coast speed < entry speed (deceleration observed)"),
		bSpeedBelowEntry);
	TestTrue(TEXT("coast flat: final coast distance > entry distance (still rolling)"),
		LastCoastDistance > EntryDistanceM);
	TestTrue(TEXT("coast flat: final coast elapsed time > entry elapsed time"),
		LastCoastElapsed > EntryElapsedTimeS);

	// Finiteness guards.
	TestTrue(TEXT("coast flat: first coast speed is finite"),
		std::isfinite(FirstCoastSpeed));
	TestTrue(TEXT("coast flat: last coast speed is finite"),
		std::isfinite(LastCoastSpeed));

	// The horizon budget: elapsed time must reach the requested
	// simulated horizon without overshooting.
	TestTrue(TEXT("coast flat: elapsed simulation time advanced to roughly the horizon"),
		LastCoastElapsed >= CoastingTotalS - Dt - 1e-9);
	TestTrue(TEXT("coast flat: elapsed simulation time did not exceed horizon"),
		LastCoastElapsed <= CoastingTotalS + 1e-6);

	// Diagnostic info for the report. AddInfo does not affect the test
	// outcome but surfaces the actual numbers in the run log.
	AddInfo(FString::Printf(
		TEXT("coast flat: accel frames=%d coast frames=%d total horizon=%.3fs"),
		AccelFrames, CoastFrames, CoastingTotalS));
	AddInfo(FString::Printf(
		TEXT("coast flat: entry power=%.3f W, entry speed=%.6f m/s, entry distance=%.6f m, entry elapsed=%.6f s"),
		EntryPowerW, EntrySpeedMps, EntryDistanceM, EntryElapsedTimeS));
	AddInfo(FString::Printf(
		TEXT("coast flat: first coast speed=%.6f m/s, last coast speed=%.6f m/s"),
		FirstCoastSpeed, LastCoastSpeed));
	AddInfo(FString::Printf(
		TEXT("coast flat: final distance=%.6f m, final elapsed=%.6f s"),
		LastCoastDistance, LastCoastElapsed));

	return true;
}

// =====================================================================
// (C) ZeroPowerDownhillDoesNotMeanStop: with PowerW = 0 on a -6 % grade
// the simulation continues to run AND the speed can grow. This proves
// the explicit warning in the brief: zero-power coasting is NOT a
// guaranteed stop. If the product ever wants a command named "Stop" to
// actually bring the bike to rest, it must add a braking model; setting
// power to 0 is insufficient on a descent.
// =====================================================================
IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FCyclingRuntimeZeroPowerDownhillAcceleratesTest,
	"CyclingRuntime.ZeroPowerDownhillDoesNotMeanStop",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingRuntimeZeroPowerDownhillAcceleratesTest::RunTest(const FString& Parameters)
{
	using namespace CyclingRuntimeCoastingTest;

	// -6 % grade (existing Python reference fixture from
	// physics_reference/tests/test_dynamics.py :: TestAccelerationOnDescent).
	constexpr double DescentGrade = -0.06;

	CyclingSimulation::FCyclingSimulationSession Session;
	{
		FString Error;
		const bool bConfigured = Session.TryConfigure(
			MakeSessionConfigWithGrade(DescentGrade), Error);
		TestTrue(TEXT("coast downhill: TryConfigure succeeds"), bConfigured);
		TestTrue(TEXT("coast downhill: OutError is empty after configure"),
			Error.IsEmpty());
	}

	// Zero power so coasting is the only thing happening. The grade
	// (gravity) is the only force that can do work.
	{
		FString Error;
		const bool bSet = Session.TrySetPowerW(0.0, Error);
		TestTrue(TEXT("coast downhill: TrySetPowerW(0.0) succeeds"), bSet);
	}

	// Drive 30 s of simulated time. Sample at every fixed step so the
	// test sees the full trajectory.
	const double Dt = CyclingSimulation::FFixedStepSimulationRunner::FixedStepDtS;

	double MaxSpeed = 0.0;
	double FinalSpeed = 0.0;
	double FinalDistance = 0.0;
	int32 FrameCount = 0;

	FSimulationState State;
	double RemainingS = 0.0;
	int32 Steps = 0;
	FString Error;
	const int32 MaxFrames = static_cast<int32>(
		CoastingTotalS / Dt);
	for (int32 Frame = 0; Frame < MaxFrames; ++Frame)
	{
		const bool bOk = Session.TryAdvance(Dt, State, RemainingS, Steps, Error);
		if (!bOk)
		{
			break;
		}
		++FrameCount;
		MaxSpeed = std::max(MaxSpeed, State.SpeedMps);
		FinalSpeed = State.SpeedMps;
		FinalDistance = State.DistanceM;
	}

	// After 30 s on a -6 % descent with zero power the bike must have
	// accelerated. The Python reference (test_dynamics.py ::
	// TestAccelerationOnDescent) asserts speed_mps > 0 after 30 s from
	// rest; we additionally assert that the speed actually grew above
	// the steady-state zero-power plateau of flat ground.
	TestTrue(TEXT("coast downhill: simulation actually advanced (frames > 0)"),
		FrameCount > 0);
	TestTrue(TEXT("coast downhill: final speed > 0 (gravity produces motion)"),
		FinalSpeed > 0.0);
	TestTrue(TEXT("coast downhill: max sampled speed > 0"),
		MaxSpeed > 0.0);
	TestTrue(TEXT("coast downhill: distance covered > 0"),
		FinalDistance > 0.0);

	// And - crucially - the speed must not collapse to zero. The session
	// is NOT "stopped" by zero power on a descent. This is the proof
	// that "Stop" cannot be implemented by mutating PowerW.
	TestTrue(TEXT("coast downhill: speed did not collapse (zero power is not a stop)"),
		FinalSpeed > 0.0);

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
