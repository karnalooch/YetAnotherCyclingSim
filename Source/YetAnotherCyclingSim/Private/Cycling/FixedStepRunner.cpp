#include "Cycling/FixedStepRunner.h"

#include "Cycling/SimulationStep.h"
#include "Cycling/PhysicsValidation.h"
#include "Math/NumericLimits.h"

#include <cmath>

namespace CyclingSimulation
{
	bool FFixedStepSimulationRunner::TryAdvance(
		double FrameDeltaS,
		const FRiderParameters& Rider,
		const FEnvironment& Environment,
		const FRiderInput& RiderInput,
		FSimulationState& OutState,
		double& RemainingAccumulatedTimeS,
		int32& CompletedSteps,
		FString& OutError)
	{
		using namespace CyclingPhysicsValidation;

		OutError.Reset();

		if (!CheckFinite(FrameDeltaS, TEXT("frame_delta_s"), OutError))
		{
			CompletedSteps = 0;
			return false;
		}

		if (!CheckNonNegative(FrameDeltaS, TEXT("frame_delta_s"), OutError))
		{
			CompletedSteps = 0;
			return false;
		}

		const double TotalAccumulatedTime = AccumulatedTimeS + FrameDeltaS;

		if (!CheckFinite(TotalAccumulatedTime, TEXT("accumulator_total_s"), OutError))
		{
			CompletedSteps = 0;
			return false;
		}

		const double RequiredStepsAsDouble = (TotalAccumulatedTime + FixedStepBoundaryToleranceS) / FixedStepDtS;

		if (!CheckFinite(RequiredStepsAsDouble, TEXT("required_steps"), OutError))
		{
			CompletedSteps = 0;
			return false;
		}

		if (RequiredStepsAsDouble < 0.0)
		{
			OutError = FString::Printf(TEXT("required_steps must not be negative"));
			CompletedSteps = 0;
			return false;
		}

		if (RequiredStepsAsDouble > static_cast<double>(TNumericLimits<int32>::Max()))
		{
			OutError = FString::Printf(TEXT("required_steps exceeds int32 range"));
			CompletedSteps = 0;
			return false;
		}

		int32 RequiredSteps = static_cast<int32>(std::floor(RequiredStepsAsDouble));

		if (RequiredSteps <= 0)
		{
			AccumulatedTimeS = TotalAccumulatedTime;
			OutState = State;
			RemainingAccumulatedTimeS = AccumulatedTimeS;
			CompletedSteps = 0;
			return true;
		}

		FSimulationState LocalState = State;
		double LocalAccumulator = TotalAccumulatedTime;

		for (int32 StepIndex = 0; StepIndex < RequiredSteps; ++StepIndex)
		{
			FSimulationState NextState;
			FString StepError;

			if (!TryStepSimulation(Rider, Environment, RiderInput, LocalState, FixedStepDtS, NextState, StepError))
			{
				OutError = StepError;
				CompletedSteps = 0;
				return false;
			}

			LocalState = NextState;
			LocalAccumulator -= FixedStepDtS;
			if (LocalAccumulator < 0.0 && LocalAccumulator > -FixedStepBoundaryToleranceS)
			{
				LocalAccumulator = 0.0;
			}
		}

		State = LocalState;
		AccumulatedTimeS = LocalAccumulator;

		OutState = State;
		RemainingAccumulatedTimeS = AccumulatedTimeS;
		CompletedSteps = RequiredSteps;
		return true;
	}
}
