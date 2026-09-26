#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerBrakingStep.h"
#include "Cycling/CyclingSimulationSession.h"
#include "Cycling/FixedStepRunner.h"
#include "Cycling/SimulationStepContext.h"

namespace Stage4CCornerBrakingTests
{
	using namespace CyclingCornerBraking;
	using namespace CyclingCornerContext;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRiderParameters MakeRider()
	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		return Rider;
	}

	FEnvironment MakeEnvironment()
	{
		FEnvironment Environment;
		Environment.GradeDecimal = 0.0;
		Environment.WindSpeedMps = 0.0;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = 0.0;
		Environment.RollingResistanceMultiplier = 1.0;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FRiderInput MakeInput(double BrakeRatio, double PowerW = 300.0)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = 90.0;
		Input.BrakeRatio = BrakeRatio;
		return Input;
	}

	FRoadPhysicsSampleDefinition MakeSample(
		double DistanceM,
		double CurvaturePerM = 0.0,
		const TCHAR* SurfaceId = TEXT("asphalt"),
		double Wetness = 0.0,
		double CrossSlopeAngleRad = 0.0)
	{
		FRoadPhysicsSampleDefinition Sample;
		Sample.DistanceM = DistanceM;
		Sample.ElevationM = 0.0;
		Sample.GradeDecimal = 0.0;
		Sample.HorizontalCurvaturePerM = CurvaturePerM;
		Sample.VerticalCurvaturePerM = 0.0;
		Sample.RoadWidthM = 6.0;
		Sample.LeftCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.RightCrossSlopeAngleRad = CrossSlopeAngleRad;
		Sample.SurfaceId = SurfaceId;
		Sample.Wetness = Wetness;
		Sample.Roughness = 0.0;
		return Sample;
	}

	bool BuildStraightProfile(double Wetness, FRoadPhysicsProfile& OutProfile, FString& OutError)
	{
		TArray<FRoadPhysicsSampleDefinition> Samples;
		Samples.Add(MakeSample(0.0, 0.0, TEXT("asphalt"), Wetness));
		Samples.Add(MakeSample(1000.0, 0.0, TEXT("asphalt"), Wetness));
		return OutProfile.TryConfigure(TEXT("Stage 4C straight"), Samples, OutError);
	}

	bool BuildApproachProfile(FRoadPhysicsProfile& OutProfile, FString& OutError)
	{
		TArray<FRoadPhysicsSampleDefinition> Samples;
		Samples.Add(MakeSample(0.0, 0.0, TEXT("asphalt"), 0.0));
		Samples.Add(MakeSample(90.0, 0.0, TEXT("asphalt"), 0.0));
		Samples.Add(MakeSample(100.0, 0.02, TEXT("paint"), 1.0));
		Samples.Add(MakeSample(160.0, 0.02, TEXT("paint"), 1.0));
		Samples.Add(MakeSample(170.0, 0.0, TEXT("asphalt"), 0.0));
		Samples.Add(MakeSample(250.0, 0.0, TEXT("asphalt"), 0.0));
		return OutProfile.TryConfigure(TEXT("Stage 4C approach"), Samples, OutError);
	}

	bool BuildTightWetCornerProfile(
		FRoadPhysicsProfile& OutProfile,
		FString& OutError)
	{
		TArray<FRoadPhysicsSampleDefinition> Samples;
		Samples.Add(MakeSample(0.0, 0.05, TEXT("paint"), 1.0));
		Samples.Add(MakeSample(200.0, 0.05, TEXT("paint"), 1.0));
		Samples.Add(MakeSample(210.0, 0.0, TEXT("asphalt"), 0.0));
		Samples.Add(MakeSample(300.0, 0.0, TEXT("asphalt"), 0.0));
		return OutProfile.TryConfigure(
			TEXT("Stage 4C tight wet corner"),
			Samples,
			OutError);
	}

	bool BuildGripPolicy(FSurfaceGripPolicy& OutPolicy, FString& OutError)
	{
		TArray<FSurfaceGripRuleDefinition> Rules;

		FSurfaceGripRuleDefinition Asphalt;
		Asphalt.SurfaceId = TEXT("asphalt");
		Asphalt.DryGripMultiplier = 1.0;
		Asphalt.FullyWetGripMultiplier = 0.75;
		Rules.Add(Asphalt);

		FSurfaceGripRuleDefinition Paint;
		Paint.SurfaceId = TEXT("paint");
		Paint.DryGripMultiplier = 0.9;
		Paint.FullyWetGripMultiplier = 0.5;
		Rules.Add(Paint);

		return OutPolicy.TryConfigure(TEXT("Stage 4C test grip"), Rules, OutError);
	}

	FCornerContextSettings MakeCornerSettings()
	{
		FCornerContextSettings Settings;
		Settings.MinAbsCurvaturePerM = 0.01;
		Settings.ScanStepM = 10.0;
		Settings.LookAheadM = 100.0;
		Settings.ApproachLengthM = 50.0;
		return Settings;
	}

	class FFailAfterDistanceContextProvider final
		: public ISimulationStepContextProvider
	{
	public:
		explicit FFailAfterDistanceContextProvider(double InFailAtDistanceM)
			: FailAtDistanceM(InFailAtDistanceM)
		{
		}

		virtual bool TryResolveEnvironment(
			const FSimulationState& PreStepState,
			FEnvironment& OutEnvironment,
			FString& OutError) const override
		{
			if (PreStepState.DistanceM >= FailAtDistanceM)
			{
				OutError = TEXT("intentional context failure after technique observations");
				return false;
			}
			OutEnvironment = MakeEnvironment();
			OutError.Reset();
			return true;
		}

		virtual bool TryObserveCompletedStep(
			const FSimulationState& PreStepState,
			const FSimulationState& PostStepState,
			TArray<FSimulationBoundaryCrossing>& OutCrossings,
			bool& bOutStopAfterStep,
			FString& OutError) const override
		{
			OutCrossings.Reset();
			bOutStopAfterStep = false;
			OutError.Reset();
			return true;
		}

	private:
		double FailAtDistanceM = 0.0;
	};

	bool BuildStaticContext(
		FDistanceBasedSimulationStepContextProvider& OutContext,
		FString& OutError)
	{
		TArray<FSimulationEnvironmentSection> Sections;
		FSimulationEnvironmentSection Section;
		Section.StartDistanceM = 0.0;
		Section.Environment = MakeEnvironment();
		Sections.Add(Section);

		TArray<FSimulationBoundaryDefinition> Boundaries;
		return OutContext.TryConfigure(Sections, Boundaries, OutError);
	}

	struct FSequenceResult
	{
		bool bSucceeded = false;
		FSimulationState State;
		int32 TotalSteps = 0;
		TArray<CyclingCornerTechniqueRuntime::FCompletedRouteCornerTechniqueScore> CompletedTechniqueScores;
		int32 SkippedTechniqueEpisodes = 0;
		FString Error;
	};

	FSequenceResult RunTightCornerSequence(const TArray<double>& FrameDeltas)
	{
		FSequenceResult Result;
		FRoadPhysicsProfile Profile;
		FSurfaceGripPolicy GripPolicy;
		FDistanceBasedSimulationStepContextProvider Context;
		FString Error;
		if (!BuildTightWetCornerProfile(Profile, Error)
			|| !BuildGripPolicy(GripPolicy, Error)
			|| !BuildStaticContext(Context, Error))
		{
			Result.Error = Error;
			return Result;
		}

		FFixedStepSimulationRunner Runner;
		const FRiderParameters Rider = MakeRider();
		const FRiderInput Input = MakeInput(0.0, 1500.0);
		const FCornerContextSettings CornerSettings = MakeCornerSettings();

		for (const double Delta : FrameDeltas)
		{
			FSimulationState State;
			double RemainingTimeS = 0.0;
			int32 CompletedSteps = 0;
			TArray<FSimulationBoundaryCrossing> Crossings;
			bool bStoppedAfterStep = false;
			if (!Runner.TryAdvanceWithCornerBraking(
				Delta,
				Rider,
				Context,
				Input,
				Profile,
				CornerSettings,
				GripPolicy,
				0.8,
				State,
				RemainingTimeS,
				CompletedSteps,
				Crossings,
				bStoppedAfterStep,
				Error))
			{
				Result.Error = Error;
				return Result;
			}
			Result.TotalSteps += CompletedSteps;
		}

		Result.bSucceeded = true;
		Result.State = Runner.GetState();
		Result.CompletedTechniqueScores = Runner.GetCompletedCornerTechniqueScores();
		Result.SkippedTechniqueEpisodes = Runner.GetSkippedCornerTechniqueEpisodeCount();
		return Result;
	}

	FSequenceResult RunTechniqueSequence(const TArray<double>& FrameDeltas)
	{
		FSequenceResult Result;
		FRoadPhysicsProfile Profile;
		FSurfaceGripPolicy GripPolicy;
		FDistanceBasedSimulationStepContextProvider Context;
		FString Error;
		if (!BuildApproachProfile(Profile, Error)
			|| !BuildGripPolicy(GripPolicy, Error)
			|| !BuildStaticContext(Context, Error))
		{
			Result.Error = Error;
			return Result;
		}

		FFixedStepSimulationRunner Runner;
		const FRiderParameters Rider = MakeRider();
		const FRiderInput Input = MakeInput(0.0, 1500.0);
		const FCornerContextSettings CornerSettings = MakeCornerSettings();

		for (const double Delta : FrameDeltas)
		{
			FSimulationState State;
			double RemainingTimeS = 0.0;
			int32 CompletedSteps = 0;
			TArray<FSimulationBoundaryCrossing> Crossings;
			bool bStoppedAfterStep = false;
			if (!Runner.TryAdvanceWithCornerBraking(
				Delta,
				Rider,
				Context,
				Input,
				Profile,
				CornerSettings,
				GripPolicy,
				0.8,
				State,
				RemainingTimeS,
				CompletedSteps,
				Crossings,
				bStoppedAfterStep,
				Error))
			{
				Result.Error = Error;
				return Result;
			}
			Result.TotalSteps += CompletedSteps;
		}

		Result.bSucceeded = true;
		Result.State = Runner.GetState();
		Result.CompletedTechniqueScores = Runner.GetCompletedCornerTechniqueScores();
		Result.SkippedTechniqueEpisodes = Runner.GetSkippedCornerTechniqueEpisodeCount();
		return Result;
	}

	FSequenceResult RunSequence(const TArray<double>& FrameDeltas)
	{
		FSequenceResult Result;
		FRoadPhysicsProfile Profile;
		FSurfaceGripPolicy GripPolicy;
		FDistanceBasedSimulationStepContextProvider Context;
		FString Error;
		if (!BuildStraightProfile(0.0, Profile, Error)
			|| !BuildGripPolicy(GripPolicy, Error)
			|| !BuildStaticContext(Context, Error))
		{
			Result.Error = Error;
			return Result;
		}

		FFixedStepSimulationRunner Runner;
		const FRiderParameters Rider = MakeRider();
		const FRiderInput Input = MakeInput(0.25);
		const FCornerContextSettings CornerSettings = MakeCornerSettings();

		for (const double Delta : FrameDeltas)
		{
			FSimulationState State;
			double RemainingTimeS = 0.0;
			int32 CompletedSteps = 0;
			TArray<FSimulationBoundaryCrossing> Crossings;
			bool bStoppedAfterStep = false;
			if (!Runner.TryAdvanceWithCornerBraking(
				Delta,
				Rider,
				Context,
				Input,
				Profile,
				CornerSettings,
				GripPolicy,
				0.8,
				State,
				RemainingTimeS,
				CompletedSteps,
				Crossings,
				bStoppedAfterStep,
				Error))
			{
				Result.Error = Error;
				return Result;
			}
			Result.TotalSteps += CompletedSteps;
		}

		Result.bSucceeded = true;
		Result.State = Runner.GetState();
		Result.CompletedTechniqueScores = Runner.GetCompletedCornerTechniqueScores();
		Result.SkippedTechniqueEpisodes = Runner.GetSkippedCornerTechniqueEpisodeCount();
		return Result;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerBrakingApproachSurfaceTest,
	"CyclingCornering.Braking.Orchestration.ApproachUsesCurrentSurface",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerBrakingApproachSurfaceTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingCornerBraking;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRoadPhysicsProfile Profile;
	FSurfaceGripPolicy GripPolicy;
	FString Error;
	TestTrue(TEXT("approach profile configures"), BuildApproachProfile(Profile, Error));
	TestTrue(TEXT("grip policy configures"), BuildGripPolicy(GripPolicy, Error));

	FSimulationState State;
	State.SpeedMps = 15.0;
	State.DistanceM = 70.0;
	State.ElapsedTimeS = 0.0;

	FCornerBrakingStepResolution Resolution;
	TestTrue(
		TEXT("approach braking resolves"),
		TryResolveCornerBrakingStep(
			Profile,
			MakeCornerSettings(),
			GripPolicy,
			0.8,
			0.0,
			MakeRider(),
			MakeInput(0.8),
			State,
			Resolution,
			Error));

	TestTrue(TEXT("look-ahead corner is found"), Resolution.CornerContext.bHasCorner);
	TestTrue(
		TEXT("look-ahead phase is approach"),
		Resolution.CornerContext.Phase == CyclingCornering::ECornerPhase::Approach);
	TestEqual(
		TEXT("look-ahead metadata describes future paint"),
		Resolution.CornerContext.SurfaceId,
		FString(TEXT("paint")));
	TestEqual(
		TEXT("current tyre contact remains asphalt"),
		Resolution.CurrentRoadState.SurfaceId,
		FString(TEXT("asphalt")));
	TestFalse(
		TEXT("approach consumes no actual lateral tyre demand"),
		Resolution.bHasActiveLateralDemand);
	TestEqual(
		TEXT("approach lateral usage is zero"),
		Resolution.BrakingForceDemand.LateralUsage,
		0.0);
	TestTrue(
		TEXT("current dry asphalt friction is used"),
		FMath::IsNearlyEqual(
			Resolution.BrakingForceDemand.EffectiveFrictionCoefficient,
			0.8,
			1e-12));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerBrakingActiveCornerTest,
	"CyclingCornering.Braking.Orchestration.ActiveCornerSharesBudget",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerBrakingActiveCornerTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingCornerBraking;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRoadPhysicsProfile Profile;
	FSurfaceGripPolicy GripPolicy;
	FString Error;
	TestTrue(TEXT("corner profile configures"), BuildApproachProfile(Profile, Error));
	TestTrue(TEXT("grip policy configures"), BuildGripPolicy(GripPolicy, Error));

	FSimulationState State;
	State.SpeedMps = 17.0;
	State.DistanceM = 120.0;
	State.ElapsedTimeS = 0.0;

	FCornerBrakingStepResolution Resolution;
	TestTrue(
		TEXT("active corner braking resolves"),
		TryResolveCornerBrakingStep(
			Profile,
			MakeCornerSettings(),
			GripPolicy,
			0.8,
			0.0,
			MakeRider(),
			MakeInput(0.8),
			State,
			Resolution,
			Error));

	TestTrue(TEXT("active corner has lateral demand"), Resolution.bHasActiveLateralDemand);
	TestTrue(TEXT("lateral usage is positive"), Resolution.GripDemand.LateralUsage > 0.0);
	TestTrue(
		TEXT("shared budget caps requested braking"),
		Resolution.BrakingForceDemand.AppliedLongitudinalUsage < 0.8);
	TestTrue(
		TEXT("braking reports shared-budget saturation"),
		Resolution.BrakingForceDemand.bSaturatedBySharedBudget);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerBrakingZeroBrakeParityTest,
	"CyclingCornering.Braking.Orchestration.ZeroBrakeRunnerParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerBrakingZeroBrakeParityTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingCornerBraking;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRoadPhysicsProfile Profile;
	FSurfaceGripPolicy GripPolicy;
	FDistanceBasedSimulationStepContextProvider Context;
	FString Error;
	TestTrue(TEXT("straight profile configures"), BuildStraightProfile(0.0, Profile, Error));
	TestTrue(TEXT("grip policy configures"), BuildGripPolicy(GripPolicy, Error));
	TestTrue(TEXT("static context configures"), BuildStaticContext(Context, Error));

	FFixedStepSimulationRunner Legacy;
	FFixedStepSimulationRunner Orchestrated;
	const FRiderParameters Rider = MakeRider();
	const FRiderInput Input = MakeInput(0.0);

	FSimulationState LegacyState;
	double LegacyRemaining = 0.0;
	int32 LegacySteps = 0;
	TArray<FSimulationBoundaryCrossing> LegacyCrossings;
	bool bLegacyStopped = false;
	TestTrue(
		TEXT("legacy runner advances"),
		Legacy.TryAdvanceWithContext(
			0.25,
			Rider,
			Context,
			Input,
			LegacyState,
			LegacyRemaining,
			LegacySteps,
			LegacyCrossings,
			bLegacyStopped,
			Error));

	FSimulationState OrchestratedState;
	double OrchestratedRemaining = 0.0;
	int32 OrchestratedSteps = 0;
	TArray<FSimulationBoundaryCrossing> OrchestratedCrossings;
	bool bOrchestratedStopped = false;
	TestTrue(
		TEXT("corner braking runner advances"),
		Orchestrated.TryAdvanceWithCornerBraking(
			0.25,
			Rider,
			Context,
			Input,
			Profile,
			MakeCornerSettings(),
			GripPolicy,
			0.8,
			OrchestratedState,
			OrchestratedRemaining,
			OrchestratedSteps,
			OrchestratedCrossings,
			bOrchestratedStopped,
			Error));

	TestEqual(TEXT("step count exact parity"), OrchestratedSteps, LegacySteps);
	TestEqual(TEXT("speed exact parity"), OrchestratedState.SpeedMps, LegacyState.SpeedMps);
	TestEqual(TEXT("distance exact parity"), OrchestratedState.DistanceM, LegacyState.DistanceM);
	TestEqual(TEXT("time exact parity"), OrchestratedState.ElapsedTimeS, LegacyState.ElapsedTimeS);
	TestEqual(TEXT("accumulator exact parity"), OrchestratedRemaining, LegacyRemaining);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerBrakingFrameBatchingTest,
	"CyclingCornering.Braking.Orchestration.FrameBatchingDeterminism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerBrakingFrameBatchingTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingCornerBraking;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	TArray<double> Frames30;
	for (int32 Index = 0; Index < 90; ++Index)
	{
		Frames30.Add(1.0 / 30.0);
	}

	TArray<double> Frames60;
	for (int32 Index = 0; Index < 180; ++Index)
	{
		Frames60.Add(1.0 / 60.0);
	}

	TArray<double> Jittered;
	for (int32 Index = 0; Index < 30; ++Index)
	{
		Jittered.Add(0.011);
		Jittered.Add(0.027);
		Jittered.Add(0.019);
		Jittered.Add(0.043);
	}

	const FSequenceResult Result30 = RunSequence(Frames30);
	const FSequenceResult Result60 = RunSequence(Frames60);
	const FSequenceResult ResultJittered = RunSequence(Jittered);

	TestTrue(TEXT("30 FPS sequence succeeds"), Result30.bSucceeded);
	TestTrue(TEXT("60 FPS sequence succeeds"), Result60.bSucceeded);
	TestTrue(TEXT("jittered sequence succeeds"), ResultJittered.bSucceeded);
	if (!Result30.bSucceeded || !Result60.bSucceeded || !ResultJittered.bSucceeded)
	{
		AddError(FString::Printf(
			TEXT("sequence error(s): 30='%s' 60='%s' jitter='%s'"),
			*Result30.Error,
			*Result60.Error,
			*ResultJittered.Error));
		return false;
	}

	TestEqual(TEXT("30 FPS executes 60 fixed steps"), Result30.TotalSteps, 60);
	TestEqual(TEXT("30/60 step count parity"), Result30.TotalSteps, Result60.TotalSteps);
	TestEqual(TEXT("30/jitter step count parity"), Result30.TotalSteps, ResultJittered.TotalSteps);
	TestEqual(TEXT("30/60 speed exact parity"), Result30.State.SpeedMps, Result60.State.SpeedMps);
	TestEqual(TEXT("30/jitter speed exact parity"), Result30.State.SpeedMps, ResultJittered.State.SpeedMps);
	TestEqual(TEXT("30/60 distance exact parity"), Result30.State.DistanceM, Result60.State.DistanceM);
	TestEqual(TEXT("30/jitter distance exact parity"), Result30.State.DistanceM, ResultJittered.State.DistanceM);
	TestEqual(TEXT("30/60 time exact parity"), Result30.State.ElapsedTimeS, Result60.State.ElapsedTimeS);
	TestEqual(TEXT("30/jitter time exact parity"), Result30.State.ElapsedTimeS, ResultJittered.State.ElapsedTimeS);
	return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CConsequenceRuntimeBatchingTest,
	"CyclingCornering.ConsequenceApplication.RuntimeFrameBatchingDeterminism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CConsequenceRuntimeBatchingTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;

	TArray<double> Frames30;
	for (int32 Index = 0; Index < 300; ++Index)
	{
		Frames30.Add(1.0 / 30.0);
	}

	TArray<double> Frames60;
	for (int32 Index = 0; Index < 600; ++Index)
	{
		Frames60.Add(1.0 / 60.0);
	}

	TArray<double> Jittered;
	for (int32 Index = 0; Index < 100; ++Index)
	{
		Jittered.Add(0.011);
		Jittered.Add(0.027);
		Jittered.Add(0.019);
		Jittered.Add(0.043);
	}

	const FSequenceResult Result30 = RunTightCornerSequence(Frames30);
	const FSequenceResult Result60 = RunTightCornerSequence(Frames60);
	const FSequenceResult ResultJittered = RunTightCornerSequence(Jittered);

	TestTrue(TEXT("tight 30 FPS sequence succeeds"), Result30.bSucceeded);
	TestTrue(TEXT("tight 60 FPS sequence succeeds"), Result60.bSucceeded);
	TestTrue(TEXT("tight jittered sequence succeeds"), ResultJittered.bSucceeded);
	if (!Result30.bSucceeded || !Result60.bSucceeded || !ResultJittered.bSucceeded)
	{
		AddError(FString::Printf(
			TEXT("tight sequence error(s): 30='%s' 60='%s' jitter='%s'"),
			*Result30.Error,
			*Result60.Error,
			*ResultJittered.Error));
		return false;
	}

	TestEqual(TEXT("tight 30 FPS executes 200 fixed steps"), Result30.TotalSteps, 200);
	TestEqual(TEXT("tight 30/60 step count parity"), Result30.TotalSteps, Result60.TotalSteps);
	TestEqual(TEXT("tight 30/jitter step count parity"), Result30.TotalSteps, ResultJittered.TotalSteps);
	TestTrue(TEXT("runtime consequence changes authoritative D"),
		Result30.State.LateralPositionM != 0.0);
	TestEqual(TEXT("tight 30/60 speed exact parity"),
		Result30.State.SpeedMps, Result60.State.SpeedMps);
	TestEqual(TEXT("tight 30/jitter speed exact parity"),
		Result30.State.SpeedMps, ResultJittered.State.SpeedMps);
	TestEqual(TEXT("tight 30/60 distance exact parity"),
		Result30.State.DistanceM, Result60.State.DistanceM);
	TestEqual(TEXT("tight 30/jitter distance exact parity"),
		Result30.State.DistanceM, ResultJittered.State.DistanceM);
	TestEqual(TEXT("tight 30/60 D exact parity"),
		Result30.State.LateralPositionM, Result60.State.LateralPositionM);
	TestEqual(TEXT("tight 30/jitter D exact parity"),
		Result30.State.LateralPositionM, ResultJittered.State.LateralPositionM);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeFrameBatchingTest,
	"CyclingCornering.Technique.Runtime.FixedStepFrameBatchingDeterminism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeFrameBatchingTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;

	TArray<double> Frames30;
	for (int32 Index = 0; Index < 900; ++Index)
	{
		Frames30.Add(1.0 / 30.0);
	}

	TArray<double> Frames60;
	for (int32 Index = 0; Index < 1800; ++Index)
	{
		Frames60.Add(1.0 / 60.0);
	}

	TArray<double> Jittered;
	for (int32 Index = 0; Index < 300; ++Index)
	{
		Jittered.Add(0.011);
		Jittered.Add(0.027);
		Jittered.Add(0.019);
		Jittered.Add(0.043);
	}

	const FSequenceResult Result30 = RunTechniqueSequence(Frames30);
	const FSequenceResult Result60 = RunTechniqueSequence(Frames60);
	const FSequenceResult ResultJittered = RunTechniqueSequence(Jittered);

	TestTrue(TEXT("technique 30 FPS sequence succeeds"), Result30.bSucceeded);
	TestTrue(TEXT("technique 60 FPS sequence succeeds"), Result60.bSucceeded);
	TestTrue(TEXT("technique jittered sequence succeeds"), ResultJittered.bSucceeded);
	if (!Result30.bSucceeded || !Result60.bSucceeded || !ResultJittered.bSucceeded)
	{
		AddError(FString::Printf(
			TEXT("technique sequence error(s): 30='%s' 60='%s' jitter='%s'"),
			*Result30.Error,
			*Result60.Error,
			*ResultJittered.Error));
		return false;
	}

	TestEqual(TEXT("30 FPS executes 600 fixed steps"), Result30.TotalSteps, 600);
	TestEqual(TEXT("technique 30/60 step count parity"), Result30.TotalSteps, Result60.TotalSteps);
	TestEqual(TEXT("technique 30/jitter step count parity"), Result30.TotalSteps, ResultJittered.TotalSteps);
	TestEqual(TEXT("one corner score completes at 30 FPS"), Result30.CompletedTechniqueScores.Num(), 1);
	TestEqual(TEXT("one corner score completes at 60 FPS"), Result60.CompletedTechniqueScores.Num(), 1);
	TestEqual(TEXT("one corner score completes under jitter"), ResultJittered.CompletedTechniqueScores.Num(), 1);
	TestEqual(TEXT("no 30 FPS episode skipped"), Result30.SkippedTechniqueEpisodes, 0);
	TestEqual(TEXT("no 60 FPS episode skipped"), Result60.SkippedTechniqueEpisodes, 0);
	TestEqual(TEXT("no jitter episode skipped"), ResultJittered.SkippedTechniqueEpisodes, 0);

	if (Result30.CompletedTechniqueScores.Num() == 1
		&& Result60.CompletedTechniqueScores.Num() == 1
		&& ResultJittered.CompletedTechniqueScores.Num() == 1)
	{
		const auto& Score30 = Result30.CompletedTechniqueScores[0];
		const auto& Score60 = Result60.CompletedTechniqueScores[0];
		const auto& ScoreJitter = ResultJittered.CompletedTechniqueScores[0];

		TestEqual(TEXT("corner start exact 30/60 parity"),
			Score30.CornerStartM, Score60.CornerStartM);
		TestEqual(TEXT("corner start exact 30/jitter parity"),
			Score30.CornerStartM, ScoreJitter.CornerStartM);
		TestEqual(TEXT("corner end exact 30/60 parity"),
			Score30.CornerEndM, Score60.CornerEndM);
		TestEqual(TEXT("corner end exact 30/jitter parity"),
			Score30.CornerEndM, ScoreJitter.CornerEndM);
		TestEqual(TEXT("overall score exact 30/60 parity"),
			Score30.Score.Score, Score60.Score.Score);
		TestEqual(TEXT("overall score exact 30/jitter parity"),
			Score30.Score.Score, ScoreJitter.Score.Score);
		TestEqual(TEXT("line score exact 30/60 parity"),
			Score30.Score.LineRetentionScore, Score60.Score.LineRetentionScore);
		TestEqual(TEXT("speed score exact 30/jitter parity"),
			Score30.Score.SpeedRetentionScore, ScoreJitter.Score.SpeedRetentionScore);
	}

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeTransactionalRollbackTest,
	"CyclingCornering.Technique.Runtime.TransactionalRollback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeTransactionalRollbackTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRoadPhysicsProfile Profile;
	FSurfaceGripPolicy GripPolicy;
	FString Error;
	TestTrue(TEXT("approach profile configures"), BuildApproachProfile(Profile, Error));
	TestTrue(TEXT("grip policy configures"), BuildGripPolicy(GripPolicy, Error));

	// Approach begins at 50 m for the 100 m corner start. Failing at 95 m
	// guarantees many Approach observations have already been staged locally
	// inside this same multi-substep batch before the intentional failure.
	FFailAfterDistanceContextProvider FailingContext(95.0);
	FFixedStepSimulationRunner Runner;

	FSimulationState OutState;
	OutState.SpeedMps = 777.0;
	OutState.DistanceM = 888.0;
	OutState.ElapsedTimeS = 999.0;
	OutState.LateralPositionM = 3.0;
	double RemainingTimeS = 123.0;
	int32 CompletedSteps = 456;
	TArray<FSimulationBoundaryCrossing> Crossings;
	bool bStoppedAfterStep = true;

	TestFalse(
		TEXT("intentional later substep failure rejects the whole batch"),
		Runner.TryAdvanceWithCornerBraking(
			30.0,
			MakeRider(),
			FailingContext,
			MakeInput(0.0, 1500.0),
			Profile,
			MakeCornerSettings(),
			GripPolicy,
			0.8,
			OutState,
			RemainingTimeS,
			CompletedSteps,
			Crossings,
			bStoppedAfterStep,
			Error));

	TestTrue(TEXT("intentional error propagated"),
		Error.Contains(TEXT("intentional context failure")));
	TestEqual(TEXT("failure reports zero completed steps"), CompletedSteps, 0);
	TestEqual(TEXT("failure returns no crossings"), Crossings.Num(), 0);
	TestFalse(TEXT("failure clears stop flag"), bStoppedAfterStep);

	// Output sentinels and authoritative runner state are not partially
	// published/committed.
	TestEqual(TEXT("output speed sentinel preserved"), OutState.SpeedMps, 777.0);
	TestEqual(TEXT("output distance sentinel preserved"), OutState.DistanceM, 888.0);
	TestEqual(TEXT("output time sentinel preserved"), OutState.ElapsedTimeS, 999.0);
	TestEqual(TEXT("output D sentinel preserved"), OutState.LateralPositionM, 3.0);
	TestEqual(TEXT("remaining-time sentinel preserved"), RemainingTimeS, 123.0);
	TestEqual(TEXT("runner speed rolls back"), Runner.GetState().SpeedMps, 0.0);
	TestEqual(TEXT("runner distance rolls back"), Runner.GetState().DistanceM, 0.0);
	TestEqual(TEXT("runner time rolls back"), Runner.GetState().ElapsedTimeS, 0.0);
	TestEqual(TEXT("runner D rolls back"), Runner.GetState().LateralPositionM, 0.0);
	TestEqual(TEXT("runner accumulator rolls back"), Runner.GetAccumulatedTimeS(), 0.0);

	// Most importantly, staged technique observations from 50..95 m were local
	// to the failed batch and cannot leak into persistent score state.
	TestEqual(TEXT("no score leaked from failed batch"),
		Runner.GetCompletedCornerTechniqueScores().Num(), 0);
	TestEqual(TEXT("no skipped episode leaked from failed batch"),
		Runner.GetSkippedCornerTechniqueEpisodeCount(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CCornerBrakingSessionPathTest,
	"CyclingCornering.Braking.Orchestration.SessionConsumesBrakeInput",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CCornerBrakingSessionPathTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerBrakingTests;
	using namespace CyclingRoadPhysics;
	using namespace CyclingSimulation;
	using namespace CyclingSurfaceGrip;

	FRoadPhysicsProfile Profile;
	FSurfaceGripPolicy GripPolicy;
	FDistanceBasedSimulationStepContextProvider Context;
	FString Error;
	TestTrue(TEXT("straight profile configures"), BuildStraightProfile(0.0, Profile, Error));
	TestTrue(TEXT("grip policy configures"), BuildGripPolicy(GripPolicy, Error));
	TestTrue(TEXT("static context configures"), BuildStaticContext(Context, Error));

	FCyclingSimulationSessionConfig Config;
	Config.Rider = MakeRider();
	Config.Environment = MakeEnvironment();
	Config.RiderInput.InitialPowerW = 300.0;
	Config.RiderInput.InitialCadenceRpm = 90.0;

	FCyclingSimulationSession Released;
	FCyclingSimulationSession Braking;
	TestTrue(TEXT("released session configures"), Released.TryConfigure(Config, Error));
	TestTrue(TEXT("braking session configures"), Braking.TryConfigure(Config, Error));
	TestTrue(TEXT("session brake command accepted"), Braking.TrySetBrakeRatio(0.5, Error));
	TestEqual(TEXT("session owns brake command"), Braking.GetRiderInput().BrakeRatio, 0.5);

	auto Advance = [&](FCyclingSimulationSession& Session, FSimulationState& OutState)
	{
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		TArray<FSimulationBoundaryCrossing> Crossings;
		bool bStoppedAfterStep = false;
		return Session.TryAdvanceWithCornerBraking(
			0.25,
			Context,
			Profile,
			MakeCornerSettings(),
			GripPolicy,
			0.8,
			OutState,
			RemainingTimeS,
			CompletedSteps,
			Crossings,
			bStoppedAfterStep,
			Error);
	};

	FSimulationState ReleasedState;
	FSimulationState BrakingState;
	TestTrue(TEXT("released session advances"), Advance(Released, ReleasedState));
	TestTrue(TEXT("braking session advances"), Advance(Braking, BrakingState));
	TestTrue(
		TEXT("session brake input reduces speed through B3c path"),
		BrakingState.SpeedMps < ReleasedState.SpeedMps);
	TestEqual(TEXT("fixed-step elapsed time parity"), BrakingState.ElapsedTimeS, ReleasedState.ElapsedTimeS);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
