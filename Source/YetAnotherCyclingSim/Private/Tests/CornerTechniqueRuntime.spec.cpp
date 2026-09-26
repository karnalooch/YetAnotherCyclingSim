#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/CornerTechniqueRuntime.h"

namespace Stage4CTechniqueRuntimeTests
{
	using namespace CyclingCornerConsequence;
	using namespace CyclingCornerContext;
	using namespace CyclingCornerTechniqueRuntime;
	using namespace CyclingCornering;

	FCornerContext MakeContext(
		ECornerPhase Phase,
		double CornerStartM = 100.0,
		double CornerEndM = 140.0)
	{
		FCornerContext Context;
		Context.Phase = Phase;
		Context.bHasCorner = true;
		Context.CornerStartM = CornerStartM;
		Context.CornerEndM = CornerEndM;
		Context.Direction = ECornerDirection::Right;
		Context.CenterlineRadiusM = 50.0;
		Context.EffectiveRadiusM = 50.0;
		Context.RoadWidthM = 6.0;
		Context.LeftMarginM = 3.0;
		Context.RightMarginM = 3.0;
		Context.SurfaceId = TEXT("asphalt");
		return Context;
	}

	FRiderInput MakeInput(double PowerW, double CadenceRpm)
	{
		FRiderInput Input;
		Input.PowerW = PowerW;
		Input.CadenceRpm = CadenceRpm;
		return Input;
	}

	FSimulationState MakePostState(double DistanceM)
	{
		FSimulationState State;
		State.SpeedMps = 10.0;
		State.DistanceM = DistanceM;
		State.ElapsedTimeS = 1.0;
		return State;
	}

	FCornerGeometryConsequence MakeConsequence(
		ECornerGeometryOutcome Outcome = ECornerGeometryOutcome::Clean,
		double LineDeviationRatio = 0.0,
		double ExitSpeedMultiplier = 1.0)
	{
		FCornerGeometryConsequence Consequence;
		Consequence.Outcome = Outcome;
		Consequence.MinimumRequiredRadiusM = 50.0;
		Consequence.MaximumFeasibleRadiusM = 53.0;
		Consequence.LineDeviationRatio = LineDeviationRatio;
		Consequence.TargetSpeedMps = 10.0 * ExitSpeedMultiplier;
		Consequence.ExitSpeedMultiplier = ExitSpeedMultiplier;
		return Consequence;
	}

	bool Observe(
		const FCornerTechniqueRuntimeState& InState,
		ECornerPhase Phase,
		double PowerW,
		double CadenceRpm,
		const FCornerGeometryConsequence* Consequence,
		double PostDistanceM,
		FCornerTechniqueRuntimeState& OutState,
		FString& OutError)
	{
		return TryObserveCornerTechniqueStep(
			InState,
			MakeContext(Phase),
			MakeInput(PowerW, CadenceRpm),
			Consequence,
			MakePostState(PostDistanceM),
			OutState,
			OutError);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeIdealTest,
	"CyclingCornering.Technique.Runtime.IdealEpisode",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeIdealTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	FCornerTechniqueRuntimeState State;
	FCornerTechniqueRuntimeState Next;
	FString Error;
	FCornerGeometryConsequence Clean = MakeConsequence();

	TestTrue(TEXT("approach observes"),
		Observe(State, ECornerPhase::Approach, 250.0, 90.0, nullptr, 95.0, Next, Error));
	State = Next;
	TestTrue(TEXT("entry observes"),
		Observe(State, ECornerPhase::Entry, 0.0, 0.0, &Clean, 110.0, Next, Error));
	State = Next;
	TestTrue(TEXT("apex observes"),
		Observe(State, ECornerPhase::Apex, 0.0, 0.0, &Clean, 130.0, Next, Error));
	State = Next;
	TestTrue(TEXT("exit observes/finalizes"),
		Observe(State, ECornerPhase::Exit, 250.0, 90.0, &Clean, 141.0, Next, Error));

	TestEqual(TEXT("one score completed"), Next.CompletedScores.Num(), 1);
	TestEqual(TEXT("no episode skipped"), Next.SkippedEpisodeCount, 0);
	TestEqual(TEXT("ideal runtime score"), Next.CompletedScores[0].Score.Score, 100.0);
	TestFalse(TEXT("episode reset after completion"), Next.bHasActiveEpisode);
	TestEqual(TEXT("observations reset"), Next.Observations.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeConsequenceTest,
	"CyclingCornering.Technique.Runtime.ConsequenceAggregation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeConsequenceTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	FCornerTechniqueRuntimeState State;
	FCornerTechniqueRuntimeState Next;
	FString Error;
	FCornerGeometryConsequence Wide25 =
		MakeConsequence(ECornerGeometryOutcome::WideLine, 0.25, 1.0);
	FCornerGeometryConsequence Slip =
		MakeConsequence(ECornerGeometryOutcome::ControlledSlip, 0.75, 0.8);
	FCornerGeometryConsequence Wide50 =
		MakeConsequence(ECornerGeometryOutcome::WideLine, 0.5, 1.0);

	TestTrue(TEXT("approach observes"),
		Observe(State, ECornerPhase::Approach, 250.0, 90.0, nullptr, 95.0, Next, Error));
	State = Next;
	TestTrue(TEXT("entry observes"),
		Observe(State, ECornerPhase::Entry, 0.0, 0.0, &Wide25, 110.0, Next, Error));
	State = Next;
	TestTrue(TEXT("apex observes"),
		Observe(State, ECornerPhase::Apex, 0.0, 0.0, &Slip, 130.0, Next, Error));
	State = Next;
	TestTrue(TEXT("exit observes"),
		Observe(State, ECornerPhase::Exit, 250.0, 90.0, &Wide50, 141.0, Next, Error));

	TestEqual(TEXT("one score completed"), Next.CompletedScores.Num(), 1);
	TestEqual(TEXT("max line penalty retained"),
		Next.CompletedScores[0].Score.LineRetentionScore, 25.0);
	TestEqual(TEXT("minimum speed retention retained"),
		Next.CompletedScores[0].Score.SpeedRetentionScore, 80.0);
	TestEqual(TEXT("physical aggregate affects mean"),
		Next.CompletedScores[0].Score.Score, 88.125);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeSkipTest,
	"CyclingCornering.Technique.Runtime.SkippedEpisodes",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeSkipTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	FCornerTechniqueRuntimeState State;
	FCornerTechniqueRuntimeState Next;
	FString Error;
	FCornerGeometryConsequence Clean = MakeConsequence();

	TestTrue(TEXT("truncated entry observes"),
		Observe(State, ECornerPhase::Entry, 100.0, 80.0, &Clean, 110.0, Next, Error));
	State = Next;
	TestTrue(TEXT("truncated apex observes"),
		Observe(State, ECornerPhase::Apex, 100.0, 80.0, &Clean, 130.0, Next, Error));
	State = Next;
	TestTrue(TEXT("truncated exit finalizes skip"),
		Observe(State, ECornerPhase::Exit, 100.0, 80.0, &Clean, 141.0, Next, Error));
	TestEqual(TEXT("truncated episode not scored"), Next.CompletedScores.Num(), 0);
	TestEqual(TEXT("truncated episode counted skipped"), Next.SkippedEpisodeCount, 1);

	State = FCornerTechniqueRuntimeState{};
	TestTrue(TEXT("zero baseline approach observes"),
		Observe(State, ECornerPhase::Approach, 0.0, 0.0, nullptr, 95.0, Next, Error));
	State = Next;
	TestTrue(TEXT("zero baseline entry observes"),
		Observe(State, ECornerPhase::Entry, 0.0, 90.0, &Clean, 110.0, Next, Error));
	State = Next;
	TestTrue(TEXT("zero baseline apex observes"),
		Observe(State, ECornerPhase::Apex, 0.0, 90.0, &Clean, 130.0, Next, Error));
	State = Next;
	TestTrue(TEXT("zero baseline exit finalizes skip"),
		Observe(State, ECornerPhase::Exit, 0.0, 90.0, &Clean, 141.0, Next, Error));
	TestEqual(TEXT("zero baseline not scored"), Next.CompletedScores.Num(), 0);
	TestEqual(TEXT("zero baseline counted skipped"), Next.SkippedEpisodeCount, 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeMeanTest,
	"CyclingCornering.Technique.Runtime.PhaseMeans",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeMeanTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	FCornerTechniqueRuntimeState State;
	FCornerTechniqueRuntimeState Next;
	FString Error;
	FCornerGeometryConsequence Clean = MakeConsequence();

	TestTrue(TEXT("approach 1 observes"),
		Observe(State, ECornerPhase::Approach, 200.0, 90.0, nullptr, 94.0, Next, Error));
	State = Next;
	TestTrue(TEXT("approach 2 observes"),
		Observe(State, ECornerPhase::Approach, 300.0, 90.0, nullptr, 96.0, Next, Error));
	State = Next;
	TestTrue(TEXT("entry observes"),
		Observe(State, ECornerPhase::Entry, 125.0, 45.0, &Clean, 110.0, Next, Error));
	State = Next;
	TestTrue(TEXT("apex observes"),
		Observe(State, ECornerPhase::Apex, 125.0, 45.0, &Clean, 130.0, Next, Error));
	State = Next;
	TestTrue(TEXT("exit observes"),
		Observe(State, ECornerPhase::Exit, 125.0, 45.0, &Clean, 141.0, Next, Error));
	TestEqual(TEXT("phase means feed C2 exactly"), Next.CompletedScores[0].Score.Score, 62.5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeValidationTest,
	"CyclingCornering.Technique.Runtime.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeValidationTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	FCornerTechniqueRuntimeState State;
	FCornerTechniqueRuntimeState Next;
	FString Error;
	TestTrue(TEXT("episode starts"),
		Observe(State, ECornerPhase::Approach, 250.0, 90.0, nullptr, 95.0, Next, Error));
	State = Next;

	const FCornerContext Changed = MakeContext(ECornerPhase::Entry, 101.0, 141.0);
	TestFalse(TEXT("interval mutation fails closed"),
		TryObserveCornerTechniqueStep(
			State,
			Changed,
			MakeInput(0.0, 0.0),
			nullptr,
			MakePostState(110.0),
			Next,
			Error));
	TestTrue(TEXT("interval error is useful"), Error.Contains(TEXT("changed interval")));

	FCornerTechniqueRuntimeState Invalid;
	Invalid.MaxLineDeviationRatio = 1.1;
	TestFalse(TEXT("invalid runtime aggregate rejected"),
		TryObserveCornerTechniqueStep(
			Invalid,
			MakeContext(ECornerPhase::Approach),
			MakeInput(250.0, 90.0),
			nullptr,
			MakePostState(95.0),
			Next,
			Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CTechniqueRuntimeDeterminismTest,
	"CyclingCornering.Technique.Runtime.Determinism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CTechniqueRuntimeDeterminismTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CTechniqueRuntimeTests;

	const FCornerTechniqueRuntimeState Initial;
	const FCornerContext Context = MakeContext(ECornerPhase::Approach);
	const FRiderInput Input = MakeInput(250.0, 90.0);
	const FSimulationState Post = MakePostState(95.0);

	FCornerTechniqueRuntimeState Reference;
	FString Error;
	TestTrue(TEXT("reference observe succeeds"),
		TryObserveCornerTechniqueStep(
			Initial,
			Context,
			Input,
			nullptr,
			Post,
			Reference,
			Error));

	for (int32 Index = 0; Index < 20; ++Index)
	{
		FCornerTechniqueRuntimeState Repeated;
		TestTrue(TEXT("repeated observe succeeds"),
			TryObserveCornerTechniqueStep(
				Initial,
				Context,
				Input,
				nullptr,
				Post,
				Repeated,
				Error));
		TestEqual(TEXT("active start deterministic"),
			Repeated.ActiveCornerStartM, Reference.ActiveCornerStartM);
		TestEqual(TEXT("observation count deterministic"),
			Repeated.Observations.Num(), Reference.Observations.Num());
		TestEqual(TEXT("observation power deterministic"),
			Repeated.Observations[0].PowerW, Reference.Observations[0].PowerW);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
