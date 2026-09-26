#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/CornerTechnique.h"

namespace Stage4CCornerTechniqueTests
{
	using namespace CyclingCornerConsequence;
	using namespace CyclingCornerTechnique;
	using namespace CyclingCornering;

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
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
		Consequence.TargetSpeedMps = 20.0 * ExitSpeedMultiplier;
		Consequence.ExitSpeedMultiplier = ExitSpeedMultiplier;
		return Consequence;
	}

	FRouteCornerTechniqueSummary MakeSummary()
	{
		FRouteCornerTechniqueSummary Summary;
		Summary.ApproachPowerW = 250.0;
		Summary.EntryPowerW = 0.0;
		Summary.ApexPowerW = 0.0;
		Summary.ExitPowerW = 250.0;
		Summary.ApproachCadenceRpm = 90.0;
		Summary.EntryCadenceRpm = 0.0;
		Summary.ApexCadenceRpm = 0.0;
		Summary.ExitCadenceRpm = 90.0;
		return Summary;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueSummaryTest,
	"CyclingCornering.Technique.RouteSummary",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueSummaryTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	TArray<FRouteCornerTechniqueObservation> Observations;
	Observations.Add({ ECornerPhase::Approach, 240.0, 88.0 });
	Observations.Add({ ECornerPhase::Approach, 260.0, 92.0 });
	Observations.Add({ ECornerPhase::Entry, 80.0, 45.0 });
	Observations.Add({ ECornerPhase::Apex, 20.0, 10.0 });
	Observations.Add({ ECornerPhase::Exit, 200.0, 80.0 });
	Observations.Add({ ECornerPhase::Exit, 300.0, 100.0 });

	FRouteCornerTechniqueSummary Summary;
	FString Error;
	TestTrue(TEXT("route-derived summary resolves"),
		TrySummarizeRouteCornerTechnique(Observations, Summary, Error));
	TestTrue(TEXT("approach power mean"), NearlyEqual(Summary.ApproachPowerW, 250.0));
	TestTrue(TEXT("approach cadence mean"), NearlyEqual(Summary.ApproachCadenceRpm, 90.0));
	TestTrue(TEXT("entry power mean"), NearlyEqual(Summary.EntryPowerW, 80.0));
	TestTrue(TEXT("apex cadence mean"), NearlyEqual(Summary.ApexCadenceRpm, 10.0));
	TestTrue(TEXT("exit power mean"), NearlyEqual(Summary.ExitPowerW, 250.0));
	TestTrue(TEXT("exit cadence mean"), NearlyEqual(Summary.ExitCadenceRpm, 90.0));

	TArray<FRouteCornerTechniqueObservation> MissingExit;
	MissingExit.Add({ ECornerPhase::Approach, 250.0, 90.0 });
	MissingExit.Add({ ECornerPhase::Entry, 0.0, 0.0 });
	MissingExit.Add({ ECornerPhase::Apex, 0.0, 0.0 });
	TestFalse(TEXT("missing exit is rejected"),
		TrySummarizeRouteCornerTechnique(MissingExit, Summary, Error));
	TestTrue(TEXT("missing exit error names exit"), Error.Contains(TEXT("exit")));

	TArray<FRouteCornerTechniqueObservation> Outside = Observations;
	Outside.Add({ ECornerPhase::Outside, 0.0, 0.0 });
	TestFalse(TEXT("outside phase is rejected"),
		TrySummarizeRouteCornerTechnique(Outside, Summary, Error));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueIdealScoreTest,
	"CyclingCornering.Technique.IdealScore",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueIdealScoreTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	FRouteCornerTechniqueScore Score;
	FString Error;
	TestTrue(TEXT("ideal score resolves"),
		TryScoreRouteCornerTechnique(
			MakeSummary(),
			MakeConsequence(),
			Score,
			Error));
	TestTrue(TEXT("overall score is 100"), NearlyEqual(Score.Score, 100.0));
	TestTrue(TEXT("entry power is 100"), NearlyEqual(Score.EntryPowerReleaseScore, 100.0));
	TestTrue(TEXT("apex power is 100"), NearlyEqual(Score.ApexPowerReleaseScore, 100.0));
	TestTrue(TEXT("exit power is 100"), NearlyEqual(Score.ExitPowerRecoveryScore, 100.0));
	TestTrue(TEXT("entry cadence is 100"), NearlyEqual(Score.EntryCadenceReleaseScore, 100.0));
	TestTrue(TEXT("apex cadence is 100"), NearlyEqual(Score.ApexCadenceReleaseScore, 100.0));
	TestTrue(TEXT("exit cadence is 100"), NearlyEqual(Score.ExitCadenceRecoveryScore, 100.0));
	TestTrue(TEXT("line retention is 100"), NearlyEqual(Score.LineRetentionScore, 100.0));
	TestTrue(TEXT("speed retention is 100"), NearlyEqual(Score.SpeedRetentionScore, 100.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueContinuousScoreTest,
	"CyclingCornering.Technique.ContinuousScore",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueContinuousScoreTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	FRouteCornerTechniqueSummary Summary = MakeSummary();
	Summary.EntryPowerW = 125.0;
	Summary.ApexPowerW = 125.0;
	Summary.ExitPowerW = 125.0;
	Summary.EntryCadenceRpm = 45.0;
	Summary.ApexCadenceRpm = 45.0;
	Summary.ExitCadenceRpm = 45.0;

	FRouteCornerTechniqueScore Score;
	FString Error;
	TestTrue(TEXT("half-effort score resolves"),
		TryScoreRouteCornerTechnique(Summary, MakeConsequence(), Score, Error));
	TestTrue(TEXT("entry power half score"), NearlyEqual(Score.EntryPowerReleaseScore, 50.0));
	TestTrue(TEXT("apex power half score"), NearlyEqual(Score.ApexPowerReleaseScore, 50.0));
	TestTrue(TEXT("exit power half score"), NearlyEqual(Score.ExitPowerRecoveryScore, 50.0));
	TestTrue(TEXT("entry cadence half score"), NearlyEqual(Score.EntryCadenceReleaseScore, 50.0));
	TestTrue(TEXT("apex cadence half score"), NearlyEqual(Score.ApexCadenceReleaseScore, 50.0));
	TestTrue(TEXT("exit cadence half score"), NearlyEqual(Score.ExitCadenceRecoveryScore, 50.0));
	TestTrue(TEXT("overall continuous mean"), NearlyEqual(Score.Score, 62.5));

	Summary.EntryPowerW = 500.0;
	Summary.ApexPowerW = 500.0;
	Summary.ExitPowerW = 500.0;
	Summary.EntryCadenceRpm = 180.0;
	Summary.ApexCadenceRpm = 180.0;
	Summary.ExitCadenceRpm = 180.0;
	TestTrue(TEXT("above-baseline score resolves"),
		TryScoreRouteCornerTechnique(Summary, MakeConsequence(), Score, Error));
	TestTrue(TEXT("entry power clamps to zero"), NearlyEqual(Score.EntryPowerReleaseScore, 0.0));
	TestTrue(TEXT("apex power clamps to zero"), NearlyEqual(Score.ApexPowerReleaseScore, 0.0));
	TestTrue(TEXT("exit power clamps to 100"), NearlyEqual(Score.ExitPowerRecoveryScore, 100.0));
	TestTrue(TEXT("entry cadence clamps to zero"), NearlyEqual(Score.EntryCadenceReleaseScore, 0.0));
	TestTrue(TEXT("apex cadence clamps to zero"), NearlyEqual(Score.ApexCadenceReleaseScore, 0.0));
	TestTrue(TEXT("exit cadence clamps to 100"), NearlyEqual(Score.ExitCadenceRecoveryScore, 100.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueConsequenceScoreTest,
	"CyclingCornering.Technique.ConsequenceScore",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueConsequenceScoreTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	FRouteCornerTechniqueScore Score;
	FString Error;
	TestTrue(TEXT("wide-line score resolves"),
		TryScoreRouteCornerTechnique(
			MakeSummary(),
			MakeConsequence(ECornerGeometryOutcome::WideLine, 0.5, 1.0),
			Score,
			Error));
	TestTrue(TEXT("wide line retains half line score"), NearlyEqual(Score.LineRetentionScore, 50.0));
	TestTrue(TEXT("wide line keeps speed score"), NearlyEqual(Score.SpeedRetentionScore, 100.0));
	TestTrue(TEXT("wide line overall score"), NearlyEqual(Score.Score, 93.75));

	TestTrue(TEXT("controlled-slip score resolves"),
		TryScoreRouteCornerTechnique(
			MakeSummary(),
			MakeConsequence(ECornerGeometryOutcome::ControlledSlip, 1.0, 0.8),
			Score,
			Error));
	TestTrue(TEXT("slip line score is zero"), NearlyEqual(Score.LineRetentionScore, 0.0));
	TestTrue(TEXT("slip speed score is 80"), NearlyEqual(Score.SpeedRetentionScore, 80.0));
	TestTrue(TEXT("slip overall score"), NearlyEqual(Score.Score, 85.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueValidationTest,
	"CyclingCornering.Technique.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueValidationTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	FRouteCornerTechniqueScore Score;
	FString Error;
	FRouteCornerTechniqueSummary Summary = MakeSummary();

	Summary.ApproachPowerW = 0.0;
	TestFalse(TEXT("zero approach power is rejected"),
		TryScoreRouteCornerTechnique(Summary, MakeConsequence(), Score, Error));
	TestTrue(TEXT("power baseline error names field"), Error.Contains(TEXT("approach_power_w")));

	Summary = MakeSummary();
	Summary.ApproachCadenceRpm = 0.0;
	TestFalse(TEXT("zero approach cadence is rejected"),
		TryScoreRouteCornerTechnique(Summary, MakeConsequence(), Score, Error));
	TestTrue(TEXT("cadence baseline error names field"), Error.Contains(TEXT("approach_cadence_rpm")));

	FCornerGeometryConsequence Invalid = MakeConsequence();
	Invalid.LineDeviationRatio = 1.1;
	TestFalse(TEXT("line deviation above one is rejected"),
		TryScoreRouteCornerTechnique(MakeSummary(), Invalid, Score, Error));

	Invalid = MakeConsequence();
	Invalid.ExitSpeedMultiplier = 1.1;
	TestFalse(TEXT("speed multiplier above one is rejected"),
		TryScoreRouteCornerTechnique(MakeSummary(), Invalid, Score, Error));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CRouteTechniqueDeterminismTest,
	"CyclingCornering.Technique.Determinism",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CRouteTechniqueDeterminismTest::RunTest(const FString& Parameters)
{
	using namespace Stage4CCornerTechniqueTests;

	FRouteCornerTechniqueSummary Summary = MakeSummary();
	Summary.EntryPowerW = 73.0;
	Summary.ApexPowerW = 19.0;
	Summary.ExitPowerW = 221.0;
	Summary.EntryCadenceRpm = 42.0;
	Summary.ApexCadenceRpm = 11.0;
	Summary.ExitCadenceRpm = 83.0;

	const FCornerGeometryConsequence Consequence =
		MakeConsequence(ECornerGeometryOutcome::WideLine, 0.37, 0.91);

	FString Error;
	FRouteCornerTechniqueScore Reference;
	TestTrue(TEXT("reference score resolves"),
		TryScoreRouteCornerTechnique(Summary, Consequence, Reference, Error));

	for (int32 Index = 0; Index < 20; ++Index)
	{
		FRouteCornerTechniqueScore Repeated;
		TestTrue(TEXT("repeated score resolves"),
			TryScoreRouteCornerTechnique(Summary, Consequence, Repeated, Error));
		TestTrue(TEXT("overall score deterministic"), Repeated.Score == Reference.Score);
		TestTrue(TEXT("entry power deterministic"),
			Repeated.EntryPowerReleaseScore == Reference.EntryPowerReleaseScore);
		TestTrue(TEXT("line score deterministic"),
			Repeated.LineRetentionScore == Reference.LineRetentionScore);
		TestTrue(TEXT("speed score deterministic"),
			Repeated.SpeedRetentionScore == Reference.SpeedRetentionScore);
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
