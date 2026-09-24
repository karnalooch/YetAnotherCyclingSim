#include "Cycling/FixedStepRunner.h"

#include "Cycling/SimulationStep.h"
#include "Cycling/PhysicsValidation.h"
#include "Math/NumericLimits.h"

#include <cmath>

namespace CyclingSimulation
{
	namespace
	{
		class FStaticSimulationStepContextProvider final : public ISimulationStepContextProvider
		{
		public:
			explicit FStaticSimulationStepContextProvider(const FEnvironment& InEnvironment)
				: Environment(InEnvironment)
			{
			}

			virtual bool TryResolveEnvironment(
				const FSimulationState& PreStepState,
				FEnvironment& OutEnvironment,
				FString& OutError) const override
			{
				(void)PreStepState;
				OutError.Reset();
				OutEnvironment = Environment;
				return true;
			}

			virtual bool TryObserveCompletedStep(
				const FSimulationState& PreStepState,
				const FSimulationState& PostStepState,
				TArray<FSimulationBoundaryCrossing>& OutCrossings,
				bool& bOutStopAfterStep,
				FString& OutError) const override
			{
				(void)PreStepState;
				(void)PostStepState;
				OutError.Reset();
				OutCrossings.Reset();
				bOutStopAfterStep = false;
				return true;
			}

		private:
			FEnvironment Environment;
		};
	}

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
		FStaticSimulationStepContextProvider StaticContext(Environment);
		TArray<FSimulationBoundaryCrossing> IgnoredCrossings;
		bool bIgnoredStoppedAfterStep = false;

		return TryAdvanceWithContext(
			FrameDeltaS,
			Rider,
			StaticContext,
			RiderInput,
			OutState,
			RemainingAccumulatedTimeS,
			CompletedSteps,
			IgnoredCrossings,
			bIgnoredStoppedAfterStep,
			OutError);
	}

	bool FFixedStepSimulationRunner::TryAdvanceWithContext(
		double FrameDeltaS,
		const FRiderParameters& Rider,
		const ISimulationStepContextProvider& StepContextProvider,
		const FRiderInput& RiderInput,
		FSimulationState& OutState,
		double& RemainingAccumulatedTimeS,
		int32& CompletedSteps,
		TArray<FSimulationBoundaryCrossing>& OutBoundaryCrossings,
		bool& bOutStoppedAfterStep,
		FString& OutError)
	{
		using namespace CyclingPhysicsValidation;

		OutError.Reset();
		OutBoundaryCrossings.Reset();
		bOutStoppedAfterStep = false;

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

		const int32 RequiredSteps = static_cast<int32>(std::floor(RequiredStepsAsDouble));

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
		int32 LocalCompletedSteps = 0;
		TArray<FSimulationBoundaryCrossing> LocalCrossings;
		bool bLocalStoppedAfterStep = false;

		for (int32 StepIndex = 0; StepIndex < RequiredSteps; ++StepIndex)
		{
			FEnvironment StepEnvironment;
			FString ContextError;
			if (!StepContextProvider.TryResolveEnvironment(LocalState, StepEnvironment, ContextError))
			{
				OutError = ContextError.IsEmpty()
					? TEXT("step context provider failed to resolve environment")
					: ContextError;
				CompletedSteps = 0;
				return false;
			}

			FSimulationState NextState;
			FString StepError;
			if (!TryStepSimulation(Rider, StepEnvironment, RiderInput, LocalState, FixedStepDtS, NextState, StepError))
			{
				OutError = StepError;
				CompletedSteps = 0;
				return false;
			}

			TArray<FSimulationBoundaryCrossing> StepCrossings;
			bool bStopAfterThisStep = false;
			if (!StepContextProvider.TryObserveCompletedStep(
				LocalState,
				NextState,
				StepCrossings,
				bStopAfterThisStep,
				ContextError))
			{
				OutError = ContextError.IsEmpty()
					? TEXT("step context provider failed to observe completed step")
					: ContextError;
				CompletedSteps = 0;
				return false;
			}

			LocalCrossings.Append(StepCrossings);
			LocalState = NextState;
			LocalAccumulator -= FixedStepDtS;
			++LocalCompletedSteps;

			if (LocalAccumulator < 0.0 && LocalAccumulator > -FixedStepBoundaryToleranceS)
			{
				LocalAccumulator = 0.0;
			}

			if (bStopAfterThisStep)
			{
				bLocalStoppedAfterStep = true;
				break;
			}
		}

		State = LocalState;
		AccumulatedTimeS = LocalAccumulator;

		OutState = State;
		RemainingAccumulatedTimeS = AccumulatedTimeS;
		CompletedSteps = LocalCompletedSteps;
		OutBoundaryCrossings = LocalCrossings;
		bOutStoppedAfterStep = bLocalStoppedAfterStep;
		return true;
	}
}
