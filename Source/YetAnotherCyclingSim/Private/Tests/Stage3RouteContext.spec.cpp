#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/CyclingSimulationSession.h"
#include "Cycling/FixedStepRunner.h"
#include "Cycling/SimulationStepContext.h"

namespace Stage3RouteContextTests
{
	using namespace CyclingSimulation;

	FEnvironment MakeEnvironment(
		double GradeDecimal,
		double SurfaceWetness = 0.0,
		double RollingResistanceMultiplier = 1.0)
	{
		FEnvironment Environment;
		Environment.GradeDecimal = GradeDecimal;
		Environment.WindSpeedMps = 0.0;
		Environment.AirDensityKgM3 = 1.225;
		Environment.SurfaceWetness = SurfaceWetness;
		Environment.RollingResistanceMultiplier = RollingResistanceMultiplier;
		Environment.GripMultiplier = 1.0;
		return Environment;
	}

	FCyclingSimulationSessionConfig MakeSessionConfig(double InitialPowerW = 800.0)
	{
		FCyclingSimulationSessionConfig Config;
		Config.Rider.RiderMassKg = 75.0;
		Config.Rider.BikeMassKg = 8.5;
		Config.Rider.CdaM2 = 0.32;
		Config.Rider.RollingResistanceCoefficient = 0.004;
		Config.Rider.DrivetrainEfficiency = 0.97;
		Config.Environment = MakeEnvironment(0.0);
		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 2000.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = InitialPowerW;
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 250.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 90.0;
		return Config;
	}

	FSimulationEnvironmentSection MakeSection(double StartDistanceM, const FEnvironment& Environment)
	{
		FSimulationEnvironmentSection Section;
		Section.StartDistanceM = StartDistanceM;
		Section.Environment = Environment;
		return Section;
	}

	FSimulationBoundaryDefinition MakeBoundary(
		const TCHAR* Id,
		ESimulationBoundaryKind Kind,
		double DistanceM,
		bool bStopAfterCrossing)
	{
		FSimulationBoundaryDefinition Boundary;
		Boundary.Id = Id;
		Boundary.Kind = Kind;
		Boundary.DistanceM = DistanceM;
		Boundary.bStopAfterCrossing = bStopAfterCrossing;
		return Boundary;
	}

	bool ConfigureDynamicProvider(
		FDistanceBasedSimulationStepContextProvider& Provider,
		FString& OutError,
		bool bIncludeBoundaries = false,
		bool bTerminalFinish = false)
	{
		TArray<FSimulationEnvironmentSection> Sections;
		Sections.Add(MakeSection(0.0, MakeEnvironment(0.0, 0.0, 1.0)));
		Sections.Add(MakeSection(0.02, MakeEnvironment(0.08, 0.25, 1.10)));
		Sections.Add(MakeSection(0.06, MakeEnvironment(-0.04, 0.80, 1.30)));

		TArray<FSimulationBoundaryDefinition> Boundaries;
		if (bIncludeBoundaries)
		{
			Boundaries.Add(MakeBoundary(
				TEXT("sector-a"),
				ESimulationBoundaryKind::Sector,
				0.02,
				false));
			Boundaries.Add(MakeBoundary(
				TEXT("finish"),
				ESimulationBoundaryKind::Finish,
				0.08,
				bTerminalFinish));
		}

		return Provider.TryConfigure(Sections, Boundaries, OutError);
	}

	bool ConfigureFlatBoundaryProvider(
		FDistanceBasedSimulationStepContextProvider& Provider,
		FString& OutError,
		bool bTerminalFinish)
	{
		TArray<FSimulationEnvironmentSection> Sections;
		Sections.Add(MakeSection(0.0, MakeEnvironment(0.0)));

		TArray<FSimulationBoundaryDefinition> Boundaries;
		Boundaries.Add(MakeBoundary(
			TEXT("sector-a"),
			ESimulationBoundaryKind::Sector,
			0.02,
			false));
		Boundaries.Add(MakeBoundary(
			TEXT("finish"),
			ESimulationBoundaryKind::Finish,
			0.08,
			bTerminalFinish));

		return Provider.TryConfigure(Sections, Boundaries, OutError);
	}

	bool AdvanceSequence(
		FCyclingSimulationSession& Session,
		const ISimulationStepContextProvider& Provider,
		const TArray<double>& FrameDeltasS,
		FSimulationState& OutState,
		double& OutRemainingTimeS,
		TArray<FSimulationBoundaryCrossing>& OutAllCrossings,
		bool& bOutStoppedAfterStep,
		FString& OutError)
	{
		OutAllCrossings.Reset();
		bOutStoppedAfterStep = false;
		int32 CompletedSteps = 0;

		for (const double FrameDeltaS : FrameDeltasS)
		{
			TArray<FSimulationBoundaryCrossing> FrameCrossings;
			bool bFrameStoppedAfterStep = false;
			if (!Session.TryAdvanceWithContext(
				FrameDeltaS,
				Provider,
				OutState,
				OutRemainingTimeS,
				CompletedSteps,
				FrameCrossings,
				bFrameStoppedAfterStep,
				OutError))
			{
				return false;
			}

			OutAllCrossings.Append(FrameCrossings);
			if (bFrameStoppedAfterStep)
			{
				bOutStoppedAfterStep = true;
				break;
			}
		}

		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextProviderSemanticsTest,
	"CyclingRouteContext.ProviderSemantics",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextProviderSemanticsTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	FDistanceBasedSimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("provider configuration succeeds"), ConfigureDynamicProvider(Provider, Error, true, true));
	TestTrue(TEXT("provider configuration clears error"), Error.IsEmpty());

	FSimulationState State;
	FEnvironment Environment;

	State.DistanceM = 0.02 - 1e-9;
	TestTrue(TEXT("lookup immediately before climb succeeds"),
		Provider.TryResolveEnvironment(State, Environment, Error));
	TestEqual(TEXT("immediately before climb uses flat grade"), Environment.GradeDecimal, 0.0);

	State.DistanceM = 0.02;
	TestTrue(TEXT("lookup exactly at climb boundary succeeds"),
		Provider.TryResolveEnvironment(State, Environment, Error));
	TestEqual(TEXT("exact climb boundary selects new section"), Environment.GradeDecimal, 0.08);
	TestEqual(TEXT("climb boundary applies route-local wetness"), Environment.SurfaceWetness, 0.25);
	TestEqual(TEXT("climb boundary applies route-local rolling multiplier"),
		Environment.RollingResistanceMultiplier, 1.10);

	State.DistanceM = 0.02 + 1e-9;
	TestTrue(TEXT("lookup immediately after climb succeeds"),
		Provider.TryResolveEnvironment(State, Environment, Error));
	TestEqual(TEXT("immediately after climb uses climb grade"), Environment.GradeDecimal, 0.08);

	State.DistanceM = 0.06;
	TestTrue(TEXT("lookup exactly at descent boundary succeeds"),
		Provider.TryResolveEnvironment(State, Environment, Error));
	TestEqual(TEXT("exact descent boundary selects descent"), Environment.GradeDecimal, -0.04);
	TestEqual(TEXT("descent section applies route-local wetness"), Environment.SurfaceWetness, 0.80);
	TestEqual(TEXT("descent section applies route-local rolling multiplier"),
		Environment.RollingResistanceMultiplier, 1.30);

	FSimulationState Pre;
	FSimulationState Post;
	Pre.DistanceM = 0.01;
	Post.DistanceM = 0.02;
	Post.ElapsedTimeS = 0.05;

	TArray<FSimulationBoundaryCrossing> Crossings;
	bool bStopAfterStep = false;
	TestTrue(TEXT("exact sector crossing observation succeeds"),
		Provider.TryObserveCompletedStep(Pre, Post, Crossings, bStopAfterStep, Error));
	TestEqual(TEXT("exact sector boundary emits once"), Crossings.Num(), 1);
	if (Crossings.Num() == 1)
	{
		TestEqual(TEXT("sector crossing id"), Crossings[0].Id, FString(TEXT("sector-a")));
		TestEqual(TEXT("sector crossing boundary distance"), Crossings[0].BoundaryDistanceM, 0.02);
	}
	TestFalse(TEXT("sector crossing is non-terminal"), bStopAfterStep);

	Pre = Post;
	Post.DistanceM = 0.03;
	Post.ElapsedTimeS = 0.10;
	TestTrue(TEXT("observation starting exactly on crossed boundary succeeds"),
		Provider.TryObserveCompletedStep(Pre, Post, Crossings, bStopAfterStep, Error));
	TestEqual(TEXT("boundary is not emitted again when pre-step is exactly on it"),
		Crossings.Num(), 0);

	Pre.DistanceM = 0.07;
	Pre.ElapsedTimeS = 0.10;
	Post.DistanceM = 0.09;
	Post.ElapsedTimeS = 0.15;
	TestTrue(TEXT("finish crossing observation succeeds"),
		Provider.TryObserveCompletedStep(Pre, Post, Crossings, bStopAfterStep, Error));
	TestEqual(TEXT("finish crossing emitted once"), Crossings.Num(), 1);
	if (Crossings.Num() == 1)
	{
		TestEqual(TEXT("finish crossing kind"),
			static_cast<int32>(Crossings[0].Kind),
			static_cast<int32>(ESimulationBoundaryKind::Finish));
	}
	TestTrue(TEXT("terminal finish requests stop after crossing step"), bStopAfterStep);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextMultiStepEnvironmentTest,
	"CyclingRouteContext.MultiStepEnvironment",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextMultiStepEnvironmentTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	FDistanceBasedSimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("dynamic provider config succeeds"), ConfigureDynamicProvider(Provider, Error));

	FCyclingSimulationSession BatchSession;
	FCyclingSimulationSession SplitSession;
	FCyclingSimulationSession StaticFlatSession;
	const FCyclingSimulationSessionConfig Config = MakeSessionConfig();
	TestTrue(TEXT("batch session config succeeds"), BatchSession.TryConfigure(Config, Error));
	TestTrue(TEXT("split session config succeeds"), SplitSession.TryConfigure(Config, Error));
	TestTrue(TEXT("static session config succeeds"), StaticFlatSession.TryConfigure(Config, Error));

	FSimulationState BatchState;
	double BatchRemainingS = 0.0;
	int32 BatchSteps = 0;
	TArray<FSimulationBoundaryCrossing> BatchCrossings;
	bool bBatchStopped = false;
	TestTrue(TEXT("single catch-up batch succeeds"),
		BatchSession.TryAdvanceWithContext(
			0.25,
			Provider,
			BatchState,
			BatchRemainingS,
			BatchSteps,
			BatchCrossings,
			bBatchStopped,
			Error));
	TestEqual(TEXT("0.25 s catch-up executes five fixed steps"), BatchSteps, 5);
	TestFalse(TEXT("environment-only provider does not stop batch"), bBatchStopped);
	TestTrue(TEXT("batch crosses climb and descent section starts"), BatchState.DistanceM > 0.06);

	FSimulationState SplitState;
	double SplitRemainingS = 0.0;
	int32 SplitSteps = 0;
	for (int32 Step = 0; Step < 5; ++Step)
	{
		TArray<FSimulationBoundaryCrossing> Crossings;
		bool bStopped = false;
		TestTrue(TEXT("split fixed-step frame succeeds"),
			SplitSession.TryAdvanceWithContext(
				0.05,
				Provider,
				SplitState,
				SplitRemainingS,
				SplitSteps,
				Crossings,
				bStopped,
				Error));
	}

	TestEqual(TEXT("single batch vs split speed is bit-exact"),
		BatchState.SpeedMps, SplitState.SpeedMps);
	TestEqual(TEXT("single batch vs split distance is bit-exact"),
		BatchState.DistanceM, SplitState.DistanceM);
	TestEqual(TEXT("single batch vs split elapsed time is bit-exact"),
		BatchState.ElapsedTimeS, SplitState.ElapsedTimeS);

	FSimulationState StaticState;
	double StaticRemainingS = 0.0;
	int32 StaticSteps = 0;
	TestTrue(TEXT("static flat reference advance succeeds"),
		StaticFlatSession.TryAdvance(0.25, StaticState, StaticRemainingS, StaticSteps, Error));
	TestFalse(TEXT("dynamic route context changes physics relative to one flat environment"),
		BatchState.SpeedMps == StaticState.SpeedMps);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextWetnessRollingTest,
	"CyclingRouteContext.RouteLocalWetnessRollingResistance",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextWetnessRollingTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	TArray<FSimulationEnvironmentSection> WetSections;
	WetSections.Add(MakeSection(0.0, MakeEnvironment(0.0, 0.0, 1.0)));
	WetSections.Add(MakeSection(0.02, MakeEnvironment(0.0, 1.0, 4.0)));

	TArray<FSimulationEnvironmentSection> DrySections;
	DrySections.Add(MakeSection(0.0, MakeEnvironment(0.0, 0.0, 1.0)));

	TArray<FSimulationBoundaryDefinition> NoBoundaries;
	FDistanceBasedSimulationStepContextProvider WetProvider;
	FDistanceBasedSimulationStepContextProvider DryProvider;
	FString Error;
	TestTrue(TEXT("wet provider config succeeds"),
		WetProvider.TryConfigure(WetSections, NoBoundaries, Error));
	TestTrue(TEXT("dry provider config succeeds"),
		DryProvider.TryConfigure(DrySections, NoBoundaries, Error));

	FCyclingSimulationSession WetSession;
	FCyclingSimulationSession DrySession;
	const FCyclingSimulationSessionConfig Config = MakeSessionConfig();
	TestTrue(TEXT("wet session config succeeds"), WetSession.TryConfigure(Config, Error));
	TestTrue(TEXT("dry session config succeeds"), DrySession.TryConfigure(Config, Error));

	const TArray<double> Frames = { 0.10, 0.15, 0.25 };
	FSimulationState WetState;
	FSimulationState DryState;
	double WetRemainingS = 0.0;
	double DryRemainingS = 0.0;
	TArray<FSimulationBoundaryCrossing> WetCrossings;
	TArray<FSimulationBoundaryCrossing> DryCrossings;
	bool bWetStopped = false;
	bool bDryStopped = false;
	TestTrue(TEXT("wet route run succeeds"),
		AdvanceSequence(
			WetSession,
			WetProvider,
			Frames,
			WetState,
			WetRemainingS,
			WetCrossings,
			bWetStopped,
			Error));
	TestTrue(TEXT("dry route run succeeds"),
		AdvanceSequence(
			DrySession,
			DryProvider,
			Frames,
			DryState,
			DryRemainingS,
			DryCrossings,
			bDryStopped,
			Error));

	TestTrue(TEXT("both runs cross the route-local environment boundary"),
		WetState.DistanceM > 0.02 && DryState.DistanceM > 0.02);
	TestTrue(TEXT("higher route-local rolling resistance lowers final speed"),
		WetState.SpeedMps < DryState.SpeedMps);
	TestTrue(TEXT("higher route-local rolling resistance lowers final distance"),
		WetState.DistanceM < DryState.DistanceM);
	TestEqual(TEXT("environment change does not alter simulation elapsed time"),
		WetState.ElapsedTimeS, DryState.ElapsedTimeS);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextBoundaryCatchUpTest,
	"CyclingRouteContext.BoundaryCatchUp",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextBoundaryCatchUpTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	FDistanceBasedSimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("boundary provider config succeeds"),
		ConfigureFlatBoundaryProvider(Provider, Error, true));

	const FCyclingSimulationSessionConfig Config = MakeSessionConfig();
	FCyclingSimulationSession BatchSession;
	FCyclingSimulationSession RegularSession;
	TestTrue(TEXT("batch session config succeeds"), BatchSession.TryConfigure(Config, Error));
	TestTrue(TEXT("regular session config succeeds"), RegularSession.TryConfigure(Config, Error));

	FSimulationState BatchState;
	double BatchRemainingS = 0.0;
	int32 BatchSteps = 0;
	TArray<FSimulationBoundaryCrossing> BatchCrossings;
	bool bBatchStopped = false;
	TestTrue(TEXT("catch-up frame succeeds"),
		BatchSession.TryAdvanceWithContext(
			0.25,
			Provider,
			BatchState,
			BatchRemainingS,
			BatchSteps,
			BatchCrossings,
			bBatchStopped,
			Error));
	TestTrue(TEXT("catch-up frame stops on terminal finish"), bBatchStopped);
	TestEqual(TEXT("catch-up frame emits sector then finish"), BatchCrossings.Num(), 2);
	if (BatchCrossings.Num() == 2)
	{
		TestEqual(TEXT("first catch-up event is sector"),
			BatchCrossings[0].Id, FString(TEXT("sector-a")));
		TestEqual(TEXT("second catch-up event is finish"),
			BatchCrossings[1].Id, FString(TEXT("finish")));
	}
	TestTrue(TEXT("terminal stop preserves unprocessed accumulated frame time"),
		BatchRemainingS >= FFixedStepSimulationRunner::FixedStepDtS);

	FSimulationState RegularState;
	double RegularRemainingS = 0.0;
	TArray<FSimulationBoundaryCrossing> RegularCrossings;
	bool bRegularStopped = false;
	const TArray<double> RegularFrames = { 0.05, 0.05, 0.05, 0.05, 0.05 };
	TestTrue(TEXT("regular fixed-step sequence succeeds"),
		AdvanceSequence(
			RegularSession,
			Provider,
			RegularFrames,
			RegularState,
			RegularRemainingS,
			RegularCrossings,
			bRegularStopped,
			Error));
	TestTrue(TEXT("regular sequence stops on same terminal finish"), bRegularStopped);

	TestEqual(TEXT("catch-up and regular crossing counts match"),
		BatchCrossings.Num(), RegularCrossings.Num());
	TestEqual(TEXT("catch-up and regular final speed match"),
		BatchState.SpeedMps, RegularState.SpeedMps);
	TestEqual(TEXT("catch-up and regular final distance match"),
		BatchState.DistanceM, RegularState.DistanceM);
	TestEqual(TEXT("catch-up and regular final elapsed time match"),
		BatchState.ElapsedTimeS, RegularState.ElapsedTimeS);

	if (BatchCrossings.Num() == RegularCrossings.Num())
	{
		for (int32 Index = 0; Index < BatchCrossings.Num(); ++Index)
		{
			TestEqual(TEXT("crossing ids are deterministic"),
				BatchCrossings[Index].Id, RegularCrossings[Index].Id);
			TestEqual(TEXT("crossing fixed-step elapsed time is deterministic"),
				BatchCrossings[Index].PostStepState.ElapsedTimeS,
				RegularCrossings[Index].PostStepState.ElapsedTimeS);
			TestEqual(TEXT("crossing fixed-step distance is deterministic"),
				BatchCrossings[Index].PostStepState.DistanceM,
				RegularCrossings[Index].PostStepState.DistanceM);
		}
	}

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextFramePacingTest,
	"CyclingRouteContext.FramePacing",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextFramePacingTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	FDistanceBasedSimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("dynamic provider with non-terminal boundaries config succeeds"),
		ConfigureDynamicProvider(Provider, Error, true, false));

	const FCyclingSimulationSessionConfig Config = MakeSessionConfig();
	FCyclingSimulationSession RegularSession;
	FCyclingSimulationSession JitterSession;
	TestTrue(TEXT("regular session config succeeds"), RegularSession.TryConfigure(Config, Error));
	TestTrue(TEXT("jitter session config succeeds"), JitterSession.TryConfigure(Config, Error));

	const TArray<double> RegularFrames = {
		0.05, 0.05, 0.05, 0.05, 0.05,
		0.05, 0.05, 0.05, 0.05, 0.05
	};
	const TArray<double> JitterFrames = { 0.03, 0.07, 0.11, 0.04, 0.10, 0.15 };

	FSimulationState RegularState;
	FSimulationState JitterState;
	double RegularRemainingS = 0.0;
	double JitterRemainingS = 0.0;
	TArray<FSimulationBoundaryCrossing> RegularCrossings;
	TArray<FSimulationBoundaryCrossing> JitterCrossings;
	bool bRegularStopped = false;
	bool bJitterStopped = false;

	TestTrue(TEXT("regular route-context run succeeds"),
		AdvanceSequence(
			RegularSession,
			Provider,
			RegularFrames,
			RegularState,
			RegularRemainingS,
			RegularCrossings,
			bRegularStopped,
			Error));
	TestTrue(TEXT("jitter route-context run succeeds"),
		AdvanceSequence(
			JitterSession,
			Provider,
			JitterFrames,
			JitterState,
			JitterRemainingS,
			JitterCrossings,
			bJitterStopped,
			Error));

	TestFalse(TEXT("non-terminal boundary provider never stops regular run"), bRegularStopped);
	TestFalse(TEXT("non-terminal boundary provider never stops jitter run"), bJitterStopped);
	TestEqual(TEXT("regular vs jitter speed is bit-exact"),
		RegularState.SpeedMps, JitterState.SpeedMps);
	TestEqual(TEXT("regular vs jitter distance is bit-exact"),
		RegularState.DistanceM, JitterState.DistanceM);
	TestEqual(TEXT("regular vs jitter elapsed time is bit-exact"),
		RegularState.ElapsedTimeS, JitterState.ElapsedTimeS);
	TestEqual(TEXT("regular vs jitter crossing count matches"),
		RegularCrossings.Num(), JitterCrossings.Num());

	if (RegularCrossings.Num() == JitterCrossings.Num())
	{
		for (int32 Index = 0; Index < RegularCrossings.Num(); ++Index)
		{
			TestEqual(TEXT("regular vs jitter crossing id"),
				RegularCrossings[Index].Id, JitterCrossings[Index].Id);
			TestEqual(TEXT("regular vs jitter crossing elapsed time"),
				RegularCrossings[Index].PostStepState.ElapsedTimeS,
				JitterCrossings[Index].PostStepState.ElapsedTimeS);
			TestEqual(TEXT("regular vs jitter crossing distance"),
				RegularCrossings[Index].PostStepState.DistanceM,
				JitterCrossings[Index].PostStepState.DistanceM);
		}
	}

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteContextResetReplayTest,
	"CyclingRouteContext.ResetReplay",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteContextResetReplayTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteContextTests;

	FDistanceBasedSimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("terminal boundary provider config succeeds"),
		ConfigureFlatBoundaryProvider(Provider, Error, true));

	FCyclingSimulationSession Session;
	TestTrue(TEXT("session config succeeds"), Session.TryConfigure(MakeSessionConfig(), Error));

	const TArray<double> OneCatchUpFrame = { 0.25 };
	FSimulationState FirstState;
	double FirstRemainingS = 0.0;
	TArray<FSimulationBoundaryCrossing> FirstCrossings;
	bool bFirstStopped = false;
	TestTrue(TEXT("first terminal route run succeeds"),
		AdvanceSequence(
			Session,
			Provider,
			OneCatchUpFrame,
			FirstState,
			FirstRemainingS,
			FirstCrossings,
			bFirstStopped,
			Error));
	TestTrue(TEXT("first run reaches terminal finish"), bFirstStopped);

	Session.Reset();

	FSimulationState ReplayState;
	double ReplayRemainingS = 0.0;
	TArray<FSimulationBoundaryCrossing> ReplayCrossings;
	bool bReplayStopped = false;
	TestTrue(TEXT("replay after reset succeeds"),
		AdvanceSequence(
			Session,
			Provider,
			OneCatchUpFrame,
			ReplayState,
			ReplayRemainingS,
			ReplayCrossings,
			bReplayStopped,
			Error));
	TestTrue(TEXT("replay reaches terminal finish"), bReplayStopped);

	TestEqual(TEXT("reset/replay speed identical"),
		FirstState.SpeedMps, ReplayState.SpeedMps);
	TestEqual(TEXT("reset/replay distance identical"),
		FirstState.DistanceM, ReplayState.DistanceM);
	TestEqual(TEXT("reset/replay elapsed time identical"),
		FirstState.ElapsedTimeS, ReplayState.ElapsedTimeS);
	TestEqual(TEXT("reset/replay preserved remainder identical"),
		FirstRemainingS, ReplayRemainingS);
	TestEqual(TEXT("reset/replay crossing count identical"),
		FirstCrossings.Num(), ReplayCrossings.Num());

	if (FirstCrossings.Num() == ReplayCrossings.Num())
	{
		for (int32 Index = 0; Index < FirstCrossings.Num(); ++Index)
		{
			TestEqual(TEXT("reset/replay crossing id identical"),
				FirstCrossings[Index].Id, ReplayCrossings[Index].Id);
			TestEqual(TEXT("reset/replay crossing step time identical"),
				FirstCrossings[Index].PostStepState.ElapsedTimeS,
				ReplayCrossings[Index].PostStepState.ElapsedTimeS);
			TestEqual(TEXT("reset/replay crossing step distance identical"),
				FirstCrossings[Index].PostStepState.DistanceM,
				ReplayCrossings[Index].PostStepState.DistanceM);
		}
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
