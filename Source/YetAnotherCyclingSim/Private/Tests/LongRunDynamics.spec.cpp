#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/SimulationStep.h"
#include "Cycling/RiderParameters.h"
#include "Cycling/Environment.h"
#include "Cycling/RiderInput.h"
#include "Cycling/SimulationState.h"

namespace LongRunDynamicsTest
{
	constexpr double RelTolerance = 0.005;
	constexpr double CoastEpsilon = 1e-12;

	// Exact step counts, avoiding float duration/dt division.
	constexpr int32 Steps600sAt50ms = 12000;
	constexpr int32 Steps600sAt10ms = 60000;
	constexpr int32 Steps30sAt50ms = 600;
	constexpr int32 Steps60sAt50ms = 1200;

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

	FEnvironment MakeEnvironment(double GradeDecimal)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = 0.0;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FRiderInput MakeRiderInput(double PowerW)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = 90.0;
		return Input;
	}

	FSimulationState MakeState(double SpeedMps)
	{
		FSimulationState State;
		State.SpeedMps = SpeedMps;
		State.DistanceM = 0.0;
		State.ElapsedTimeS = 0.0;
		return State;
	}

	// Advances one validated step. On a failed step it reports the step index and
	// the error and returns false; on success it also re-verifies the returned
	// state is valid.
	bool Advance(FAutomationTestBase& Test, const FRiderParameters& Rider, const FEnvironment& Environment,
		const FRiderInput& Input, const FSimulationState& In, double DtS, int32 StepIndex, FSimulationState& Out)
	{
		FString Error;
		if (!CyclingSimulation::TryStepSimulation(Rider, Environment, Input, In, DtS, Out, Error))
		{
			Test.AddError(FString::Printf(TEXT("step %d failed: %s"), StepIndex, *Error));
			return false;
		}
		if (!Out.IsValid())
		{
			Test.AddError(FString::Printf(TEXT("step %d returned an invalid state"), StepIndex));
			return false;
		}
		return true;
	}

	// Runs StepCount validated steps, stopping immediately on the first failure.
	bool RunSteps(FAutomationTestBase& Test, const FRiderParameters& Rider, const FEnvironment& Environment,
		const FRiderInput& Input, FSimulationState State, double DtS, int32 StepCount, FSimulationState& OutFinal)
	{
		for (int32 StepIndex = 0; StepIndex < StepCount; ++StepIndex)
		{
			FSimulationState Next;
			if (!Advance(Test, Rider, Environment, Input, State, DtS, StepIndex, Next))
			{
				return false;
			}
			State = Next;
		}
		OutFinal = State;
		return true;
	}

	// Computes the relative difference |A - B| / |B|, guarding against a zero or
	// non-finite denominator.
	bool TryRelativeDifference(double A, double B, double& OutRelative)
	{
		if (!FMath::IsFinite(B) || B == 0.0)
		{
			return false;
		}
		OutRelative = FMath::Abs(A - B) / FMath::Abs(B);
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLongRunDynamicsTest, "CyclingPhysics.LongRunDynamics",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FLongRunDynamicsTest::RunTest(const FString& Parameters)
{
	using namespace LongRunDynamicsTest;

	// --- 600-second step-size comparison at 0.05 s and 0.01 s ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FRiderInput Input = MakeRiderInput(250.0);

		FSimulationState Coarse;
		FSimulationState Fine;
		if (!RunSteps(*this, Rider, Environment, Input, MakeState(0.0), 0.05, Steps600sAt50ms, Coarse))
		{
			return false;
		}
		if (!RunSteps(*this, Rider, Environment, Input, MakeState(0.0), 0.01, Steps600sAt10ms, Fine))
		{
			return false;
		}

		TestTrue(TEXT("fine speed is positive"), Fine.SpeedMps > 0.0);

		double RelSpeed = 0.0;
		TestTrue(TEXT("speed denominator is safe"), TryRelativeDifference(Coarse.SpeedMps, Fine.SpeedMps, RelSpeed));
		TestTrue(TEXT("speed relative difference within 0.5%"), RelSpeed <= RelTolerance);

		double RelDistance = 0.0;
		TestTrue(TEXT("distance denominator is safe"), TryRelativeDifference(Coarse.DistanceM, Fine.DistanceM, RelDistance));
		TestTrue(TEXT("distance relative difference within 0.5%"), RelDistance <= RelTolerance);

		AddInfo(FString::Printf(TEXT("coarse: speed %.9f m/s, distance %.6f m"), Coarse.SpeedMps, Coarse.DistanceM));
		AddInfo(FString::Printf(TEXT("fine: speed %.9f m/s, distance %.6f m"), Fine.SpeedMps, Fine.DistanceM));
		AddInfo(FString::Printf(TEXT("relative difference: speed %.6f, distance %.6f"), RelSpeed, RelDistance));
	}

	// --- Monotonic flat-road coasting for 30 seconds ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FRiderInput Input = MakeRiderInput(0.0);

		FSimulationState State = MakeState(12.0);
		double PreviousSpeed = State.SpeedMps;

		for (int32 StepIndex = 0; StepIndex < Steps30sAt50ms; ++StepIndex)
		{
			FSimulationState Next;
			if (!Advance(*this, Rider, Environment, Input, State, 0.05, StepIndex, Next))
			{
				return false;
			}
			TestTrue(TEXT("coasting speed never increases"), Next.SpeedMps <= PreviousSpeed + CoastEpsilon);
			TestTrue(TEXT("coasting speed is non-negative"), Next.SpeedMps >= 0.0);
			TestTrue(TEXT("coasting distance is non-negative"), Next.DistanceM >= 0.0);
			PreviousSpeed = Next.SpeedMps;
			State = Next;
		}
	}

	// --- Stop and remain stopped on an 8% climb within 60 seconds ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.08);
		const FRiderInput Input = MakeRiderInput(0.0);

		FSimulationState State = MakeState(5.0);
		bool Stopped = false;
		int32 StopStep = -1;
		double StopTimeS = 0.0;

		for (int32 StepIndex = 0; StepIndex < Steps60sAt50ms; ++StepIndex)
		{
			FSimulationState Next;
			if (!Advance(*this, Rider, Environment, Input, State, 0.05, StepIndex, Next))
			{
				return false;
			}
			TestTrue(TEXT("uphill speed is finite"), FMath::IsFinite(Next.SpeedMps));
			TestTrue(TEXT("uphill distance is finite"), FMath::IsFinite(Next.DistanceM));
			TestTrue(TEXT("uphill time is finite"), FMath::IsFinite(Next.ElapsedTimeS));
			TestTrue(TEXT("uphill speed is non-negative"), Next.SpeedMps >= 0.0);
			TestTrue(TEXT("uphill distance is non-negative"), Next.DistanceM >= 0.0);

			if (Next.SpeedMps == 0.0)
			{
				Stopped = true;
				if (StopStep < 0)
				{
					StopStep = StepIndex;
					StopTimeS = Next.ElapsedTimeS;
				}
			}
			else if (Stopped)
			{
				TestTrue(TEXT("bike moved again after stopping"), false);
				return false;
			}

			State = Next;
		}

		TestTrue(TEXT("bike stopped on the climb"), Stopped);
		TestTrue(TEXT("final speed is zero"), State.SpeedMps == 0.0);
		AddInfo(FString::Printf(TEXT("rider stopped at step %d (%.3f s)"), StopStep, StopTimeS));
	}

	// --- Accelerate from rest on a 6% descent for 30 seconds ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(-0.06);
		const FRiderInput Input = MakeRiderInput(0.0);

		FSimulationState Final;
		if (!RunSteps(*this, Rider, Environment, Input, MakeState(0.0), 0.05, Steps30sAt50ms, Final))
		{
			return false;
		}

		TestTrue(TEXT("descent accelerates from rest"), Final.SpeedMps > 0.0);
		TestTrue(TEXT("descent gains distance"), Final.DistanceM > 0.0);
		AddInfo(FString::Printf(TEXT("descent final: speed %.9f m/s, distance %.6f m"), Final.SpeedMps, Final.DistanceM));
	}

	// --- Identical 600-second runs produce identical final states ---

	{
		const FRiderParameters Rider = MakeValidRider();
		const FEnvironment Environment = MakeEnvironment(0.0);
		const FRiderInput Input = MakeRiderInput(250.0);

		FSimulationState First;
		FSimulationState Second;
		if (!RunSteps(*this, Rider, Environment, Input, MakeState(0.0), 0.05, Steps600sAt50ms, First))
		{
			return false;
		}
		if (!RunSteps(*this, Rider, Environment, Input, MakeState(0.0), 0.05, Steps600sAt50ms, Second))
		{
			return false;
		}

		TestEqual(TEXT("identical runs give identical speed"), First.SpeedMps, Second.SpeedMps);
		TestEqual(TEXT("identical runs give identical distance"), First.DistanceM, Second.DistanceM);
		TestEqual(TEXT("identical runs give identical time"), First.ElapsedTimeS, Second.ElapsedTimeS);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
