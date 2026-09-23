#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/SimulationStep.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace GoldenRideTest
{
	// Approved Python reference tolerances from physics_reference/tests/test_golden_ride.py.
	constexpr double SpeedToleranceMps = 1e-9;
	constexpr double DistanceToleranceM = 1e-6;
	constexpr double TimeToleranceS = 1e-8;

	// Fixed step dt = 0.05 s. Use compile-time integer step counts rather than
	// duration/dt floating-point division, mirroring physics_reference/tests/test_golden_ride.py.
	constexpr double FixedStepS = 0.05;
	constexpr int32 StepsPhase1 = 2400; // 120.0 s
	constexpr int32 StepsPhase2 = 3600; // 180.0 s
	constexpr int32 StepsPhase3 = 2400; // 120.0 s
	constexpr int32 StepsPhase4 = 3600; // 180.0 s
	constexpr int32 TotalSteps = StepsPhase1 + StepsPhase2 + StepsPhase3 + StepsPhase4; // 12000

	// Approved Python reference checkpoints from physics_reference/tests/test_golden_ride.py.
	// These literals MUST stay in lock-step with the Python Golden Ride.
	struct FPhaseCheckpoint
	{
		const TCHAR* Name;
		double ExpectedSpeedMps;
		double ExpectedDistanceM;
		double ExpectedElapsedTimeS;
	};

	const FPhaseCheckpoint ApprovedCheckpoints[] = {
		{ TEXT("warmup_flat"),            9.04205091278644,  990.3100920589375, 120.0 },
		{ TEXT("climb_headwind_wet"),     4.725107316129324, 1870.6740284419789, 300.0 },
		{ TEXT("descent_tailwind_coast"), 19.854393959326686, 3990.1248734450232, 420.0 },
		{ TEXT("finish_flat_headwind"),   7.41078352861369,  5454.449915576454,  600.0 },
	};

	FRiderParameters MakeValidRider()
	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		return Rider;
	}

	FEnvironment MakeEnvironment(double GradeDecimal, double WindSpeedMps, double AirDensityKgM3,
		double SurfaceWetness, double RollingResistanceMultiplier, double GripMultiplier)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = WindSpeedMps;
		Environment.AirDensityKgM3 = AirDensityKgM3;
		Environment.SurfaceWetness = SurfaceWetness;
		Environment.RollingResistanceMultiplier = RollingResistanceMultiplier;
		Environment.GripMultiplier = GripMultiplier;
		return Environment;
	}

	FRiderInput MakeRiderInput(double PowerW, double CadenceRpm)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = CadenceRpm;
		return Input;
	}

	FSimulationState MakeState()
	{
		FSimulationState State;
		State.SpeedMps = 0.0;
		State.DistanceM = 0.0;
		State.ElapsedTimeS = 0.0;
		return State;
	}

	// Advances one validated step. On a failed step it reports the step index,
	// phase name and the error and returns false; on success it also re-verifies
	// the returned state is valid and finite/non-negative.
	bool Advance(FAutomationTestBase& Test, const FRiderParameters& Rider, const FEnvironment& Environment,
		const FRiderInput& Input, const FSimulationState& In, int32 StepIndex, const TCHAR* PhaseName, FSimulationState& Out)
	{
		FString Error;
		if (!CyclingSimulation::TryStepSimulation(Rider, Environment, Input, In, FixedStepS, Out, Error))
		{
			Test.AddError(FString::Printf(TEXT("phase '%s' step %d failed: %s"), PhaseName, StepIndex, *Error));
			return false;
		}
		if (!Out.IsValid())
		{
			Test.AddError(FString::Printf(TEXT("phase '%s' step %d returned an invalid state"), PhaseName, StepIndex));
			return false;
		}
		if (!FMath::IsFinite(Out.SpeedMps) || !FMath::IsFinite(Out.DistanceM) || !FMath::IsFinite(Out.ElapsedTimeS))
		{
			Test.AddError(FString::Printf(TEXT("phase '%s' step %d returned a non-finite field"), PhaseName, StepIndex));
			return false;
		}
		if (Out.SpeedMps < 0.0 || Out.DistanceM < 0.0 || Out.ElapsedTimeS < 0.0)
		{
			Test.AddError(FString::Printf(TEXT("phase '%s' step %d returned a negative field"), PhaseName, StepIndex));
			return false;
		}
		return true;
	}

	// Runs StepCount validated steps for one phase, stopping immediately on the first failure.
	bool RunPhase(FAutomationTestBase& Test, const FRiderParameters& Rider, const FEnvironment& Environment,
		const FRiderInput& Input, FSimulationState State, int32 StepCount, const TCHAR* PhaseName, FSimulationState& OutFinal)
	{
		for (int32 StepIndex = 0; StepIndex < StepCount; ++StepIndex)
		{
			FSimulationState Next;
			if (!Advance(Test, Rider, Environment, Input, State, StepIndex, PhaseName, Next))
			{
				return false;
			}
			State = Next;
		}
		OutFinal = State;
		return true;
	}

	// Runs the complete Golden Ride scenario from a zero initial state and
	// returns the per-phase checkpoint states.
	bool RunGoldenRide(FAutomationTestBase& Test, TArray<FSimulationState>& OutCheckpoints)
	{
		OutCheckpoints.Reset();

		const FRiderParameters Rider = MakeValidRider();

		struct FPhaseFixture
		{
			const TCHAR* Name;
			int32 Steps;
			FEnvironment Environment;
			FRiderInput Input;
		};

		const FPhaseFixture Phases[] = {
			{
				TEXT("warmup_flat"),
				StepsPhase1,
				MakeEnvironment(0.0, 0.0, 1.225, 0.0, 1.0, 1.0),
				MakeRiderInput(180.0, 85.0),
			},
			{
				TEXT("climb_headwind_wet"),
				StepsPhase2,
				MakeEnvironment(0.06, 2.0, 1.20, 0.70, 1.18, 0.82),
				MakeRiderInput(300.0, 92.0),
			},
			{
				TEXT("descent_tailwind_coast"),
				StepsPhase3,
				MakeEnvironment(-0.07, -3.0, 1.18, 0.40, 1.08, 0.90),
				MakeRiderInput(0.0, 0.0),
			},
			{
				TEXT("finish_flat_headwind"),
				StepsPhase4,
				MakeEnvironment(0.0, 4.0, 1.225, 0.0, 1.0, 1.0),
				MakeRiderInput(220.0, 88.0),
			},
		};

		FSimulationState State = MakeState();
		for (const FPhaseFixture& Phase : Phases)
		{
			FSimulationState Final;
			if (!RunPhase(Test, Rider, Phase.Environment, Phase.Input, State, Phase.Steps, Phase.Name, Final))
			{
				return false;
			}
			OutCheckpoints.Add(Final);
			State = Final;
		}
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FGoldenRideTest, "CyclingPhysics.GoldenRide",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FGoldenRideTest::RunTest(const FString& Parameters)
{
	using namespace GoldenRideTest;

	// --- Reference parity: each phase checkpoint must match the approved Python output ---

	TArray<FSimulationState> Checkpoints;
	if (!RunGoldenRide(*this, Checkpoints))
	{
		return false;
	}

	TestEqual(TEXT("Golden Ride produces four phase checkpoints"), Checkpoints.Num(), static_cast<int32>(UE_ARRAY_COUNT(ApprovedCheckpoints)));

	double MaxSpeedDrift = 0.0;
	double MaxDistanceDrift = 0.0;
	double MaxTimeDrift = 0.0;

	for (int32 PhaseIndex = 0; PhaseIndex < Checkpoints.Num(); ++PhaseIndex)
	{
		const FPhaseCheckpoint& Approved = ApprovedCheckpoints[PhaseIndex];
		const FSimulationState& Actual = Checkpoints[PhaseIndex];

		const double SpeedDrift = FMath::Abs(Actual.SpeedMps - Approved.ExpectedSpeedMps);
		const double DistanceDrift = FMath::Abs(Actual.DistanceM - Approved.ExpectedDistanceM);
		const double TimeDrift = FMath::Abs(Actual.ElapsedTimeS - Approved.ExpectedElapsedTimeS);

		MaxSpeedDrift = FMath::Max(MaxSpeedDrift, SpeedDrift);
		MaxDistanceDrift = FMath::Max(MaxDistanceDrift, DistanceDrift);
		MaxTimeDrift = FMath::Max(MaxTimeDrift, TimeDrift);

		AddInfo(FString::Printf(TEXT("phase '%s': speed %.15f (drift %.3e), distance %.12f (drift %.3e), time %.9f (drift %.3e)"),
			Approved.Name,
			Actual.SpeedMps, SpeedDrift,
			Actual.DistanceM, DistanceDrift,
			Actual.ElapsedTimeS, TimeDrift));

		TestTrue(
			FString::Printf(TEXT("phase '%s' speed matches Python reference within %.0e m/s"), Approved.Name, SpeedToleranceMps),
			SpeedDrift <= SpeedToleranceMps);
		TestTrue(
			FString::Printf(TEXT("phase '%s' distance matches Python reference within %.0e m"), Approved.Name, DistanceToleranceM),
			DistanceDrift <= DistanceToleranceM);
		TestTrue(
			FString::Printf(TEXT("phase '%s' elapsed time matches Python reference within %.0e s"), Approved.Name, TimeToleranceS),
			TimeDrift <= TimeToleranceS);
	}

	// Final state must match phase 4 (after the last phase).
	const FSimulationState& Final = Checkpoints.Last();
	const FPhaseCheckpoint& ApprovedFinal = ApprovedCheckpoints[UE_ARRAY_COUNT(ApprovedCheckpoints) - 1];
	TestEqual(TEXT("final speed equals phase 4 approved speed"), Final.SpeedMps, ApprovedFinal.ExpectedSpeedMps);
	TestEqual(TEXT("final distance equals phase 4 approved distance"), Final.DistanceM, ApprovedFinal.ExpectedDistanceM);
	TestEqual(TEXT("final elapsed time equals phase 4 approved elapsed time"), Final.ElapsedTimeS, ApprovedFinal.ExpectedElapsedTimeS);

	AddInfo(FString::Printf(TEXT("Golden Ride total: %d steps (dt=%.2f s)"), TotalSteps, FixedStepS));
	AddInfo(FString::Printf(TEXT("max drift over all phases: speed %.3e m/s, distance %.3e m, time %.3e s"),
		MaxSpeedDrift, MaxDistanceDrift, MaxTimeDrift));

	// --- Determinism: a second complete Golden Ride must yield identical state ---

	TArray<FSimulationState> SecondCheckpoints;
	if (!RunGoldenRide(*this, SecondCheckpoints))
	{
		return false;
	}

	TestEqual(TEXT("deterministic run produces the same number of checkpoints"), SecondCheckpoints.Num(), Checkpoints.Num());

	for (int32 PhaseIndex = 0; PhaseIndex < Checkpoints.Num(); ++PhaseIndex)
	{
		const FPhaseCheckpoint& Approved = ApprovedCheckpoints[PhaseIndex];
		const FSimulationState& First = Checkpoints[PhaseIndex];
		const FSimulationState& Second = SecondCheckpoints[PhaseIndex];

		TestEqual(
			FString::Printf(TEXT("phase '%s' deterministic speed"), Approved.Name),
			Second.SpeedMps, First.SpeedMps);
		TestEqual(
			FString::Printf(TEXT("phase '%s' deterministic distance"), Approved.Name),
			Second.DistanceM, First.DistanceM);
		TestEqual(
			FString::Printf(TEXT("phase '%s' deterministic elapsed time"), Approved.Name),
			Second.ElapsedTimeS, First.ElapsedTimeS);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS