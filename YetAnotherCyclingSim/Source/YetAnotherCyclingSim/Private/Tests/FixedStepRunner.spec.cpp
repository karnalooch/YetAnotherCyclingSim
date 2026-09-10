#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include <limits>

#include "Cycling/FixedStepRunner.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace FixedStepRunnerTest
{
	const double NaNValue = std::numeric_limits<double>::quiet_NaN();
	const double InfinityValue = std::numeric_limits<double>::infinity();
	const double Tolerance = 1e-9;
	const double FixedStep = 0.05;

	void ExpectNearlyEqual(FAutomationTestBase& Test, double Actual, double Expected, double ToleranceValue = Tolerance)
	{
		Test.TestTrue(TEXT("expected values to be nearly equal"), FMath::Abs(Actual - Expected) <= ToleranceValue);
	}

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

	FEnvironment MakeEnvironment(double GradeDecimal = 0.0, double WindSpeedMps = 0.0)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = WindSpeedMps;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FRiderInput MakeRiderInput(double PowerW, double CadenceRpm = 90.0)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = CadenceRpm;
		return Input;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFixedStepRunnerTest, "CyclingPhysics.FixedStepRunner",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFixedStepRunnerTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace FixedStepRunnerTest;

	// --- Frame shorter than fixed step performs zero steps and retains time ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		const double FrameDelta = 0.04;
		TestTrue(TEXT("short frame advances"), Runner.TryAdvance(FrameDelta, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		TestTrue(TEXT("short frame performs zero steps"), CompletedSteps == 0);
		ExpectNearlyEqual(*this, RemainingTime, FrameDelta);
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
	}

	// --- Accumulated short frames eventually perform one step ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		const double ShortFrame = 0.04;
		TestTrue(TEXT("first short frame advances"), Runner.TryAdvance(ShortFrame, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));
		TestTrue(TEXT("first short frame performs zero steps"), CompletedSteps == 0);
		ExpectNearlyEqual(*this, RemainingTime, ShortFrame);

		TestTrue(TEXT("second short frame advances"), Runner.TryAdvance(ShortFrame, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));
		TestTrue(TEXT("second short frame performs one step"), CompletedSteps == 1);
		ExpectNearlyEqual(*this, RemainingTime, 0.03);
	}

	// --- A 0.12 s frame performs two steps and retains approximately 0.02 s ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		const double FrameDelta = 0.12;
		TestTrue(TEXT("0.12s frame advances"), Runner.TryAdvance(FrameDelta, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		TestTrue(TEXT("0.12s frame performs two steps"), CompletedSteps == 2);
		ExpectNearlyEqual(*this, RemainingTime, 0.02);
	}

	// --- A zero frame delta succeeds without changing state ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		TestTrue(TEXT("zero frame advances"), Runner.TryAdvance(0.0, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		TestTrue(TEXT("zero frame performs zero steps"), CompletedSteps == 0);
		ExpectNearlyEqual(*this, RemainingTime, 0.0);
		ExpectNearlyEqual(*this, OutState.SpeedMps, 0.0);
	}

	// --- Negative, NaN, and infinite frame deltas fail transactionally ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState = MakeValidRider();
		double RemainingTime = 1.0;
		int32 CompletedSteps = 5;
		FString Error = TEXT("stale");

		for (double InvalidDelta : { -0.01, NaNValue, InfinityValue, -InfinityValue })
		{
			TestFalse(TEXT("invalid frame delta fails"), Runner.TryAdvance(InvalidDelta, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));
			TestTrue(TEXT("error message is set"), !Error.IsEmpty());
			TestTrue(TEXT("completed steps is zero after failure"), CompletedSteps == 0);
		}
	}

	// --- Invalid rider causes failure and leaves runner state unchanged ---

	{
		FFixedStepSimulationRunner Runner;

		FSimulationState InitialState;
		InitialState.SpeedMps = 10.0;
		InitialState.DistanceM = 100.0;
		InitialState.ElapsedTimeS = 50.0;

		FRiderParameters InvalidRider;

		FSimulationState OutState = InitialState;
		double RemainingTime = 1.0;
		int32 CompletedSteps = 3;
		FString Error;

		TestFalse(TEXT("invalid rider fails"), Runner.TryAdvance(0.1, InvalidRider, MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		ExpectNearlyEqual(*this, OutState.SpeedMps, 10.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 100.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 50.0);
		TestTrue(TEXT("completed steps is zero after invalid rider"), CompletedSteps == 0);
	}

	// --- Deterministic frame-rate independence: 30 FPS, 60 FPS, jittered produce identical results ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment();
		const FRiderInput Input = MakeRiderInput(250.0);

		// Sequence 1: 30 FPS - 30 frames each intended as 1/30 seconds.
		// Mathematical intended total duration: 30 * (1/30) = 1.0 seconds.
		// Binary floating-point representation does not represent 1/30 exactly,
		// so the summed value will deviate from exactly 1.0 by an amount
		// within FixedStepBoundaryToleranceS.
		// Expected cumulative fixed steps: floor(1.0 / 0.05) = 20.
		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			int32 TotalCompletedSteps = 0;
			bool bAllSucceeded = true;

			for (int32 i = 0; i < 30; ++i)
			{
				if (!Runner.TryAdvance(1.0 / 30.0, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error))
				{
					bAllSucceeded = false;
					break;
				}
				TotalCompletedSteps += FrameCompletedSteps;
			}

			TestTrue(TEXT("30 FPS every frame succeeds"), bAllSucceeded);
			TestEqual(TEXT("30 FPS cumulative steps equal 20"), TotalCompletedSteps, 20);
		}

		// Sequence 2: 60 FPS - 60 frames each intended as 1/60 seconds.
		// Mathematical intended total duration: 60 * (1/60) = 1.0 seconds.
		// Binary floating-point representation does not represent 1/60 exactly,
		// so the summed value will deviate from exactly 1.0 by an amount
		// within FixedStepBoundaryToleranceS.
		// Expected cumulative fixed steps: floor(1.0 / 0.05) = 20.
		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			int32 TotalCompletedSteps = 0;
			bool bAllSucceeded = true;

			for (int32 i = 0; i < 60; ++i)
			{
				if (!Runner.TryAdvance(1.0 / 60.0, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error))
				{
					bAllSucceeded = false;
					break;
				}
				TotalCompletedSteps += FrameCompletedSteps;
			}

			TestTrue(TEXT("60 FPS every frame succeeds"), bAllSucceeded);
			TestEqual(TEXT("60 FPS cumulative steps equal 20"), TotalCompletedSteps, 20);
		}

		// Sequence 3: Genuinely jittered frames - varying positive deltas.
		// Pattern repeated 5 times: [0.04, 0.06, 0.03, 0.07]
		// Per cycle sum: 0.04 + 0.06 + 0.03 + 0.07 = 0.20
		// Total across 5 cycles: 5 * 0.20 = 1.0 seconds (mathematical intent).
		// Individual frames are below and above the 0.05 fixed-step boundary,
		// exercising accumulation across irregular boundaries.
		// Expected cumulative fixed steps: floor(1.0 / 0.05) = 20.
		// Per-frame breakdown:
		//   0.04 -> acc=0.04, 0 steps
		//   0.06 -> acc=0.10, 2 steps, rem=0.0
		//   0.03 -> acc=0.03, 0 steps
		//   0.07 -> acc=0.10, 2 steps, rem=0.0
		// Per cycle: 4 steps. 5 cycles: 20 steps.
		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			int32 TotalCompletedSteps = 0;
			bool bAllSucceeded = true;

			const double JitteredPattern[] = { 0.04, 0.06, 0.03, 0.07 };
			for (int32 Cycle = 0; Cycle < 5; ++Cycle)
			{
				for (double FrameDelta : JitteredPattern)
				{
					if (!Runner.TryAdvance(FrameDelta, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error))
					{
						bAllSucceeded = false;
						break;
					}
					TotalCompletedSteps += FrameCompletedSteps;
				}
				if (!bAllSucceeded)
				{
					break;
				}
			}

			TestTrue(TEXT("jittered every frame succeeds"), bAllSucceeded);
			TestEqual(TEXT("jittered cumulative steps equal 20"), TotalCompletedSteps, 20);
		}

		// Re-run all three sequences and capture final states for exact equality check.
		FSimulationState State30FPS;
		FSimulationState State60FPS;
		FSimulationState StateJittered;
		double RemainingTime30FPS = 0.0;
		double RemainingTime60FPS = 0.0;
		double RemainingTimeJittered = 0.0;

		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			for (int32 i = 0; i < 30; ++i)
			{
				Runner.TryAdvance(1.0 / 30.0, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error);
			}
			State30FPS = OutState;
			RemainingTime30FPS = RemainingTime;
		}

		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			for (int32 i = 0; i < 60; ++i)
			{
				Runner.TryAdvance(1.0 / 60.0, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error);
			}
			State60FPS = OutState;
			RemainingTime60FPS = RemainingTime;
		}

		{
			FFixedStepSimulationRunner Runner;
			FSimulationState OutState;
			double RemainingTime;
			int32 FrameCompletedSteps;
			FString Error;
			const double JitteredPattern[] = { 0.04, 0.06, 0.03, 0.07 };
			for (int32 Cycle = 0; Cycle < 5; ++Cycle)
			{
				for (double FrameDelta : JitteredPattern)
				{
					Runner.TryAdvance(FrameDelta, Rider, Environment, Input, OutState, RemainingTime, FrameCompletedSteps, Error);
				}
			}
			StateJittered = OutState;
			RemainingTimeJittered = RemainingTime;
		}

		// Verify SpeedMps is exactly identical across all three final states
		TestEqual(TEXT("30 FPS vs 60 FPS speed identical"), State30FPS.SpeedMps, State60FPS.SpeedMps);
		TestEqual(TEXT("30 FPS vs jittered speed identical"), State30FPS.SpeedMps, StateJittered.SpeedMps);

		// Verify DistanceM is exactly identical across all three final states
		TestEqual(TEXT("30 FPS vs 60 FPS distance identical"), State30FPS.DistanceM, State60FPS.DistanceM);
		TestEqual(TEXT("30 FPS vs jittered distance identical"), State30FPS.DistanceM, StateJittered.DistanceM);

		// Verify ElapsedTimeS is exactly identical across all three final states
		TestEqual(TEXT("30 FPS vs 60 FPS time identical"), State30FPS.ElapsedTimeS, State60FPS.ElapsedTimeS);
		TestEqual(TEXT("30 FPS vs jittered time identical"), State30FPS.ElapsedTimeS, StateJittered.ElapsedTimeS);

		// Verify remaining accumulated time in seconds (s) is approximately equal
		// across all three sequences. Use a very small tolerance justified by
		// binary floating-point representation. The tolerance is much smaller
		// than FixedStepBoundaryToleranceS (1e-12 s).
		const double RemainingTimeToleranceS = 1e-15;
		TestTrue(TEXT("30 FPS vs 60 FPS remaining time approximately equal"),
			FMath::Abs(RemainingTime30FPS - RemainingTime60FPS) <= RemainingTimeToleranceS);
		TestTrue(TEXT("30 FPS vs jittered remaining time approximately equal"),
			FMath::Abs(RemainingTime30FPS - RemainingTimeJittered) <= RemainingTimeToleranceS);
		TestTrue(TEXT("60 FPS vs jittered remaining time approximately equal"),
			FMath::Abs(RemainingTime60FPS - RemainingTimeJittered) <= RemainingTimeToleranceS);
	}

	// --- State persists across multiple Advance calls ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		Runner.TryAdvance(0.1, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error);
		const double FirstSpeed = OutState.SpeedMps;
		const double FirstDistance = OutState.DistanceM;
		const double FirstTime = OutState.ElapsedTimeS;

		Runner.TryAdvance(0.1, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error);

		TestTrue(TEXT("speed increases after second step"), OutState.SpeedMps > FirstSpeed);
		TestTrue(TEXT("distance increases after second step"), OutState.DistanceM > FirstDistance);
		TestTrue(TEXT("time increases after second step"), OutState.ElapsedTimeS > FirstTime);
	}

	// --- Multiple steps in single frame ---

	{
		FFixedStepSimulationRunner Runner;
		FSimulationState OutState;
		double RemainingTime;
		int32 CompletedSteps;
		FString Error;

		// 0.25s should result in exactly 5 steps (5 * 0.05 = 0.25)
		TestTrue(TEXT("0.25s advances"), Runner.TryAdvance(0.25, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		TestTrue(TEXT("0.25s performs 5 steps"), CompletedSteps == 5);
		ExpectNearlyEqual(*this, RemainingTime, 0.0);
	}

	// --- Large frame delta exceeding int32 step count fails transactionally ---

	{
		FFixedStepSimulationRunner Runner;

		// Use sentinel output values to prove outputs are not partially overwritten.
		FSimulationState OutState;
		OutState.SpeedMps = 999.0;
		OutState.DistanceM = 999.0;
		OutState.ElapsedTimeS = 999.0;

		constexpr double SentinelRemainingTime = 999.0;
		double RemainingTime = SentinelRemainingTime;

		constexpr int32 SentinelCompletedSteps = 999;
		int32 CompletedSteps = SentinelCompletedSteps;

		FString Error = TEXT("stale");

		// A frame delta large enough that step count exceeds int32 range.
		// int32 max = 2147483647. Steps needed > int32 max.
		// FixedStepDtS = 0.05, so FrameDelta > 2147483647 * 0.05 = 107374182.35 seconds.
		const double HugeFrameDelta = 1.0e12;

		TestFalse(TEXT("huge frame delta fails"), Runner.TryAdvance(HugeFrameDelta, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		// Outputs must not be partially overwritten on failure.
		ExpectNearlyEqual(*this, OutState.SpeedMps, 999.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 999.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 999.0);
		ExpectNearlyEqual(*this, RemainingTime, SentinelRemainingTime);
		TestTrue(TEXT("completed steps set to zero on overflow failure"), CompletedSteps == 0);
		TestTrue(TEXT("error message is set on overflow failure"), !Error.IsEmpty());

		// Internal state must be unchanged.
		ExpectNearlyEqual(*this, Runner.GetState().SpeedMps, 0.0);
		ExpectNearlyEqual(*this, Runner.GetState().DistanceM, 0.0);
		ExpectNearlyEqual(*this, Runner.GetState().ElapsedTimeS, 0.0);
		ExpectNearlyEqual(*this, Runner.GetAccumulatedTimeS(), 0.0);
	}

	// --- Sentinel output values preserved on invalid rider failure ---

	{
		FFixedStepSimulationRunner Runner;

		// First do a valid step to give the runner some state.
		FSimulationState TempOutState;
		double TempRemaining;
		int32 TempSteps;
		FString TempError;
		Runner.TryAdvance(0.1, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), TempOutState, TempRemaining, TempSteps, TempError);

		const double PreSpeed = Runner.GetState().SpeedMps;
		const double PreDistance = Runner.GetState().DistanceM;
		const double PreTime = Runner.GetState().ElapsedTimeS;
		const double PreAccumulator = Runner.GetAccumulatedTimeS();

		// Now attempt with invalid rider and sentinel outputs.
		FSimulationState OutState;
		OutState.SpeedMps = 888.0;
		OutState.DistanceM = 888.0;
		OutState.ElapsedTimeS = 888.0;

		constexpr double SentinelRemainingTime = 888.0;
		double RemainingTime = SentinelRemainingTime;

		constexpr int32 SentinelCompletedSteps = 888;
		int32 CompletedSteps = SentinelCompletedSteps;

		FString Error = TEXT("stale");

		FRiderParameters InvalidRider;

		TestFalse(TEXT("invalid rider fails"), Runner.TryAdvance(0.1, InvalidRider, MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		// Internal state must be unchanged.
		ExpectNearlyEqual(*this, Runner.GetState().SpeedMps, PreSpeed);
		ExpectNearlyEqual(*this, Runner.GetState().DistanceM, PreDistance);
		ExpectNearlyEqual(*this, Runner.GetState().ElapsedTimeS, PreTime);
		ExpectNearlyEqual(*this, Runner.GetAccumulatedTimeS(), PreAccumulator);

		// Output sentinels must be preserved.
		ExpectNearlyEqual(*this, OutState.SpeedMps, 888.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 888.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 888.0);
		ExpectNearlyEqual(*this, RemainingTime, SentinelRemainingTime);
		TestTrue(TEXT("completed steps set to zero"), CompletedSteps == 0);
		TestTrue(TEXT("error message is set"), !Error.IsEmpty());
	}

	// --- Sentinel output values preserved on negative frame delta failure ---

	{
		FFixedStepSimulationRunner Runner;

		FSimulationState OutState;
		OutState.SpeedMps = 777.0;
		OutState.DistanceM = 777.0;
		OutState.ElapsedTimeS = 777.0;

		constexpr double SentinelRemainingTime = 777.0;
		double RemainingTime = SentinelRemainingTime;

		constexpr int32 SentinelCompletedSteps = 777;
		int32 CompletedSteps = SentinelCompletedSteps;

		FString Error = TEXT("stale");

		TestFalse(TEXT("negative frame delta fails"), Runner.TryAdvance(-0.01, MakeValidRider(), MakeEnvironment(), MakeRiderInput(250.0), OutState, RemainingTime, CompletedSteps, Error));

		ExpectNearlyEqual(*this, OutState.SpeedMps, 777.0);
		ExpectNearlyEqual(*this, OutState.DistanceM, 777.0);
		ExpectNearlyEqual(*this, OutState.ElapsedTimeS, 777.0);
		ExpectNearlyEqual(*this, RemainingTime, SentinelRemainingTime);
		TestTrue(TEXT("completed steps set to zero"), CompletedSteps == 0);
		TestTrue(TEXT("error message is set"), !Error.IsEmpty());
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
