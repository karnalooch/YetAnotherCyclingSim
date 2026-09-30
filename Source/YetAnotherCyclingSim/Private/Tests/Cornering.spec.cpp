#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/Cornering.h"
#include "Cycling/CyclingForces.h"

#include <cmath>
#include <limits>

namespace Stage4ACorneringTests
{
	using namespace CyclingCornering;

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}

	bool BuildReferenceCorner(FCornerProfile& OutProfile, const FCorner*& OutCorner, FString& OutError)
	{
		TArray<FCornerDefinition> Definitions;
		Definitions.Add({ TEXT("Reference"), 1000.0, 100.0, 25.0 });
		if (!OutProfile.TryConfigure(TEXT("Reference profile"), 2000.0, Definitions, OutError))
		{
			return false;
		}

		int32 CornerIndex = INDEX_NONE;
		return OutProfile.TryGetCornerAtDistance(1000.0, OutCorner, CornerIndex, OutError)
			&& OutCorner != nullptr
			&& CornerIndex == 0;
	}

	FCornerTechniqueSummary MakeAssessmentSummary(
		double MaxGripUsage = 0.8,
		double EntryPowerW = 100.0,
		double EntryCadenceRpm = 80.0,
		double ApexPowerW = 60.0,
		double ApexCadenceRpm = 65.0,
		double ExitPowerW = 200.0,
		double ExitCadenceRpm = 100.0)
	{
		FCornerTechniqueSummary Summary;
		Summary.ApproachPowerW = 200.0;
		Summary.EntryPowerW = EntryPowerW;
		Summary.ApexPowerW = ApexPowerW;
		Summary.ExitPowerW = ExitPowerW;
		Summary.ApproachCadenceRpm = 100.0;
		Summary.EntryCadenceRpm = EntryCadenceRpm;
		Summary.ApexCadenceRpm = ApexCadenceRpm;
		Summary.ExitCadenceRpm = ExitCadenceRpm;
		Summary.MaxGripUsage = MaxGripUsage;
		return Summary;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4ACornerProfileParityTest,
	"CyclingCornering.ProfileParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4ACornerProfileParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;

	FCornerProfile Profile;
	FString Error;

	TArray<FCornerDefinition> Corners;
	Corners.Add({ TEXT("  First  "), 100.0, 50.0, 20.0 });
	Corners.Add({ TEXT("Second"), 150.0, 75.0, 35.0 });

	TestTrue(TEXT("valid corner profile config succeeds"),
		Profile.TryConfigure(TEXT("  Test corners  "), 500.0, Corners, Error));
	TestEqual(TEXT("profile name is trimmed"), Profile.GetName(), FString(TEXT("Test corners")));
	TestEqual(TEXT("corner name is trimmed"), Profile.GetCorners()[0].GetName(), FString(TEXT("First")));
	TestEqual(TEXT("corner count"), Profile.GetCorners().Num(), 2);
	TestTrue(TEXT("touching corners are accepted"),
		Profile.GetCorners()[0].GetEndDistanceM() == Profile.GetCorners()[1].GetStartDistanceM());

	const FCorner* Corner = nullptr;
	int32 CornerIndex = INDEX_NONE;
	TestTrue(TEXT("distance before first corner is valid"),
		Profile.TryGetCornerAtDistance(99.999, Corner, CornerIndex, Error));
	TestTrue(TEXT("distance before first corner resolves no corner"), Corner == nullptr);
	TestEqual(TEXT("no-corner index is INDEX_NONE"), CornerIndex, INDEX_NONE);

	TestTrue(TEXT("exact corner start resolves"),
		Profile.TryGetCornerAtDistance(100.0, Corner, CornerIndex, Error));
	TestTrue(TEXT("corner pointer populated"), Corner != nullptr);
	TestEqual(TEXT("exact start selects first corner"), CornerIndex, 0);

	TestTrue(TEXT("exact touching boundary resolves"),
		Profile.TryGetCornerAtDistance(150.0, Corner, CornerIndex, Error));
	TestEqual(TEXT("touching boundary selects second corner"), CornerIndex, 1);

	TestTrue(TEXT("exact profile end is valid"),
		Profile.TryGetCornerAtDistance(500.0, Corner, CornerIndex, Error));
	TestTrue(TEXT("profile end is outside corners"), Corner == nullptr);
	TestEqual(TEXT("profile end index is INDEX_NONE"), CornerIndex, INDEX_NONE);

	const FString PreservedName = Profile.GetName();
	const int32 PreservedCount = Profile.GetCorners().Num();
	TArray<FCornerDefinition> Overlap;
	Overlap.Add({ TEXT("A"), 100.0, 100.0, 20.0 });
	Overlap.Add({ TEXT("B"), 150.0, 100.0, 20.0 });
	TestFalse(TEXT("overlap is rejected"),
		Profile.TryConfigure(TEXT("Invalid"), 500.0, Overlap, Error));
	TestEqual(TEXT("failed reconfigure preserves name"), Profile.GetName(), PreservedName);
	TestEqual(TEXT("failed reconfigure preserves corners"), Profile.GetCorners().Num(), PreservedCount);

	TArray<FCornerDefinition> Empty;
	FCornerProfile EmptyProfile;
	TestTrue(TEXT("empty corner list matches Python contract"),
		EmptyProfile.TryConfigure(TEXT("Empty"), 500.0, Empty, Error));
	TestEqual(TEXT("empty profile has zero corners"), EmptyProfile.GetCorners().Num(), 0);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4AGripAndPhaseParityTest,
	"CyclingCornering.GripAndPhaseParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4AGripAndPhaseParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;
	using namespace Stage4ACorneringTests;

	FString Error;
	double Value = 0.0;

	TestTrue(TEXT("dry effective friction succeeds"),
		TryCalculateEffectiveFrictionCoefficient(0.8, 1.0, Value, Error));
	TestTrue(TEXT("dry effective friction parity"), NearlyEqual(Value, 0.8));

	TestTrue(TEXT("wet effective friction succeeds"),
		TryCalculateEffectiveFrictionCoefficient(0.8, 0.5, Value, Error));
	TestTrue(TEXT("wet effective friction parity"), NearlyEqual(Value, 0.4));

	TestTrue(TEXT("maximum speed succeeds"),
		TryCalculateMaximumCornerSpeedMps(25.0, 0.8, 1.0, Value, Error));
	const double ExpectedMaximumSpeed = FMath::Sqrt(
		0.8 * CyclingForces::StandardGravityMps2 * 25.0);
	TestTrue(TEXT("maximum speed formula parity"),
		NearlyEqual(Value, ExpectedMaximumSpeed));

	TestTrue(TEXT("grip usage at physical limit succeeds"),
		TryCalculateCornerGripUsage(ExpectedMaximumSpeed, 25.0, 0.8, 1.0, Value, Error));
	TestTrue(TEXT("grip usage at physical limit is one"), NearlyEqual(Value, 1.0));

	ECornerGripStatus Status = ECornerGripStatus::Safe;
	TestTrue(TEXT("0.849 grip classifies"), TryClassifyCornerGripUsage(0.849, Status, Error));
	TestTrue(TEXT("below 0.85 is safe"), Status == ECornerGripStatus::Safe);
	TestTrue(TEXT("0.85 grip classifies"), TryClassifyCornerGripUsage(0.85, Status, Error));
	TestTrue(TEXT("0.85 is near limit"), Status == ECornerGripStatus::NearLimit);
	TestTrue(TEXT("1.0 grip classifies"), TryClassifyCornerGripUsage(1.0, Status, Error));
	TestTrue(TEXT("1.0 remains near limit"), Status == ECornerGripStatus::NearLimit);
	TestTrue(TEXT("above one grip classifies"), TryClassifyCornerGripUsage(1.001, Status, Error));
	TestTrue(TEXT("above one exceeds grip"), Status == ECornerGripStatus::GripExceeded);

	FCornerProfile Profile;
	const FCorner* Corner = nullptr;
	TestTrue(TEXT("reference corner builds"), BuildReferenceCorner(Profile, Corner, Error));
	if (Corner == nullptr)
	{
		return false;
	}

	ECornerPhase Phase = ECornerPhase::Outside;
	TestTrue(TEXT("899.999 phase resolves"), TryGetCornerPhase(*Corner, 899.999, 100.0, Phase, Error));
	TestTrue(TEXT("before approach is outside"), Phase == ECornerPhase::Outside);
	TestTrue(TEXT("900 approach start resolves"), TryGetCornerPhase(*Corner, 900.0, 100.0, Phase, Error));
	TestTrue(TEXT("approach start is approach"), Phase == ECornerPhase::Approach);
	TestTrue(TEXT("1000 entry start resolves"), TryGetCornerPhase(*Corner, 1000.0, 100.0, Phase, Error));
	TestTrue(TEXT("corner start is entry"), Phase == ECornerPhase::Entry);
	TestTrue(TEXT("1025 apex start resolves"), TryGetCornerPhase(*Corner, 1025.0, 100.0, Phase, Error));
	TestTrue(TEXT("25 percent is apex"), Phase == ECornerPhase::Apex);
	TestTrue(TEXT("1075 exit start resolves"), TryGetCornerPhase(*Corner, 1075.0, 100.0, Phase, Error));
	TestTrue(TEXT("75 percent is exit"), Phase == ECornerPhase::Exit);
	TestTrue(TEXT("1100 corner end resolves"), TryGetCornerPhase(*Corner, 1100.0, 100.0, Phase, Error));
	TestTrue(TEXT("exact corner end is outside"), Phase == ECornerPhase::Outside);

	double DistanceToStartM = -1.0;
	TestTrue(TEXT("distance to corner succeeds"),
		TryGetDistanceToCornerStartM(*Corner, 950.0, DistanceToStartM, Error));
	TestTrue(TEXT("distance to corner is 50 m"), NearlyEqual(DistanceToStartM, 50.0));
	TestTrue(TEXT("inside corner distance succeeds"),
		TryGetDistanceToCornerStartM(*Corner, 1050.0, DistanceToStartM, Error));
	TestTrue(TEXT("inside corner distance is zero"), NearlyEqual(DistanceToStartM, 0.0));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4ATechniqueParityTest,
	"CyclingCornering.TechniqueParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4ATechniqueParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;
	using namespace Stage4ACorneringTests;

	FString Error;
	FCornerProfile Profile;
	const FCorner* Corner = nullptr;
	TestTrue(TEXT("reference corner builds"), BuildReferenceCorner(Profile, Corner, Error));
	if (Corner == nullptr)
	{
		return false;
	}

	TArray<FCornerTechniqueSample> Samples;
	Samples.Add({ 850.0, 999.0, 999.0, 5.0 }); // outside; ignored
	Samples.Add({ 950.0, 250.0, 90.0, 5.0 });  // approach grip ignored
	Samples.Add({ 1010.0, 120.0, 75.0, 0.6 });
	Samples.Add({ 1050.0, 50.0, 65.0, 0.8 });
	Samples.Add({ 1090.0, 280.0, 92.0, 0.7 });

	FCornerTechniqueSummary Summary;
	TestTrue(TEXT("technique summary succeeds"),
		TrySummarizeCornerTechnique(*Corner, Samples, 100.0, Summary, Error));
	TestTrue(TEXT("approach power parity"), NearlyEqual(Summary.ApproachPowerW, 250.0));
	TestTrue(TEXT("entry power parity"), NearlyEqual(Summary.EntryPowerW, 120.0));
	TestTrue(TEXT("apex power parity"), NearlyEqual(Summary.ApexPowerW, 50.0));
	TestTrue(TEXT("exit power parity"), NearlyEqual(Summary.ExitPowerW, 280.0));
	TestTrue(TEXT("approach cadence parity"), NearlyEqual(Summary.ApproachCadenceRpm, 90.0));
	TestTrue(TEXT("entry cadence parity"), NearlyEqual(Summary.EntryCadenceRpm, 75.0));
	TestTrue(TEXT("apex cadence parity"), NearlyEqual(Summary.ApexCadenceRpm, 65.0));
	TestTrue(TEXT("exit cadence parity"), NearlyEqual(Summary.ExitCadenceRpm, 92.0));
	TestTrue(TEXT("approach grip is excluded from max"), NearlyEqual(Summary.MaxGripUsage, 0.8));

	FCornerTechniqueAssessment Assessment;
	TestTrue(TEXT("technique assessment succeeds"),
		TryAssessCornerTechnique(Summary, Assessment, Error));
	TestTrue(TEXT("reference technique remains excellent"),
		Assessment.Rating == ECornerTechniqueRating::Excellent);
	TestTrue(TEXT("reference technique score is at least 99"),
		Assessment.Score >= 99.0 && Assessment.Score <= 100.0);
	TestTrue(TEXT("reference technique feedback matches Python apex cadence rule"),
		Assessment.Feedback == ECornerTechniqueFeedback::StayOffPowerAtApex);
	TestTrue(TEXT("reference grip status is safe"),
		Assessment.GripStatus == ECornerGripStatus::Safe);

	FCornerTechniqueSummary ZeroBaseline = Summary;
	ZeroBaseline.ApproachPowerW = 0.0;
	ZeroBaseline.EntryPowerW = 0.0;
	ZeroBaseline.ApexPowerW = 50.0;
	TestTrue(TEXT("zero-over-zero ratio is zero"),
		ZeroBaseline.GetEntryPowerRatio() == 0.0);
	TestTrue(TEXT("positive-over-zero ratio is infinity"),
		std::isinf(ZeroBaseline.GetApexPowerRatio()));
	TestTrue(TEXT("infinite ratio assessment remains valid"),
		TryAssessCornerTechnique(ZeroBaseline, Assessment, Error));
	TestTrue(TEXT("assessment score remains finite"),
		FMath::IsFinite(Assessment.Score));

	TArray<FCornerTechniqueSample> Descending = Samples;
	Swap(Descending[2], Descending[3]);
	TestFalse(TEXT("descending samples are rejected"),
		TrySummarizeCornerTechnique(*Corner, Descending, 100.0, Summary, Error));

	TArray<FCornerTechniqueSample> MissingExit;
	MissingExit.Add({ 950.0, 250.0, 90.0, 0.4 });
	MissingExit.Add({ 1010.0, 120.0, 75.0, 0.6 });
	MissingExit.Add({ 1050.0, 50.0, 65.0, 0.8 });
	TestFalse(TEXT("missing phase is rejected"),
		TrySummarizeCornerTechnique(*Corner, MissingExit, 100.0, Summary, Error));
	TestTrue(TEXT("missing phase error names exit"), Error.Contains(TEXT("exit")));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4AAssessmentBoundaryParityTest,
	"CyclingCornering.AssessmentBoundaryParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4AAssessmentBoundaryParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;
	using namespace Stage4ACorneringTests;

	FString Error;
	FCornerTechniqueAssessment Assessment;

	TestTrue(TEXT("ideal technique assesses"),
		TryAssessCornerTechnique(MakeAssessmentSummary(), Assessment, Error));
	TestTrue(TEXT("ideal technique is 100"), NearlyEqual(Assessment.Score, 100.0));
	TestTrue(TEXT("ideal technique is excellent"),
		Assessment.Rating == ECornerTechniqueRating::Excellent);

	TestTrue(TEXT("90 boundary assesses"),
		TryAssessCornerTechnique(MakeAssessmentSummary(0.925), Assessment, Error));
	TestTrue(TEXT("90 boundary score parity"), NearlyEqual(Assessment.Score, 90.0));
	TestTrue(TEXT("90 boundary is excellent"),
		Assessment.Rating == ECornerTechniqueRating::Excellent);

	TestTrue(TEXT("75 boundary assesses"),
		TryAssessCornerTechnique(MakeAssessmentSummary(1.0625), Assessment, Error));
	TestTrue(TEXT("75 boundary score parity"), NearlyEqual(Assessment.Score, 75.0));
	TestTrue(TEXT("75 boundary is good"),
		Assessment.Rating == ECornerTechniqueRating::Good);
	TestTrue(TEXT("grip exceeded prioritizes reduce speed"),
		Assessment.Feedback == ECornerTechniqueFeedback::ReduceSpeed);

	TestTrue(TEXT("release earlier feedback assesses"),
		TryAssessCornerTechnique(
			MakeAssessmentSummary(0.8, 140.0),
			Assessment,
			Error));
	TestTrue(TEXT("entry power feedback parity"),
		Assessment.Feedback == ECornerTechniqueFeedback::ReleaseEarlier);

	TestTrue(TEXT("apex feedback assesses"),
		TryAssessCornerTechnique(
			MakeAssessmentSummary(0.8, 100.0, 80.0, 100.0),
			Assessment,
			Error));
	TestTrue(TEXT("apex feedback parity"),
		Assessment.Feedback == ECornerTechniqueFeedback::StayOffPowerAtApex);

	TestTrue(TEXT("exit feedback assesses"),
		TryAssessCornerTechnique(
			MakeAssessmentSummary(0.8, 100.0, 80.0, 60.0, 65.0, 100.0),
			Assessment,
			Error));
	TestTrue(TEXT("exit feedback parity"),
		Assessment.Feedback == ECornerTechniqueFeedback::AccelerateOnExit);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4AConsequenceParityTest,
	"CyclingCornering.ConsequenceParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4AConsequenceParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;
	using namespace Stage4ACorneringTests;

	struct FExpected
	{
		double Usage;
		ECornerOutcome Outcome;
		double Multiplier;
		double Deviation;
		ECornerHudFeedback Feedback;
	};

	const FExpected Cases[] = {
		{ 0.0, ECornerOutcome::Clean, 1.0, 0.0, ECornerHudFeedback::CleanCorner },
		{ 0.85, ECornerOutcome::Clean, 1.0, 0.0, ECornerHudFeedback::CleanCorner },
		{ 1.0, ECornerOutcome::Clean, 1.0, 0.0, ECornerHudFeedback::CleanCorner },
		{ 1.075, ECornerOutcome::WideLine, 0.925, 0.25, ECornerHudFeedback::WiderSlowerLine },
		{ 1.15, ECornerOutcome::WideLine, 0.85, 0.5, ECornerHudFeedback::WiderSlowerLine },
		{ 1.325, ECornerOutcome::ControlledSlip, 0.725, 0.75, ECornerHudFeedback::RearWheelSlip },
		{ 1.50, ECornerOutcome::ControlledSlip, 0.60, 1.0, ECornerHudFeedback::RearWheelSlip },
		{ 2.0, ECornerOutcome::ControlledSlip, 0.60, 1.0, ECornerHudFeedback::RearWheelSlip },
	};

	FString Error;
	for (const FExpected& Expected : Cases)
	{
		FCornerConsequence Consequence;
		TestTrue(TEXT("consequence calculation succeeds"),
			TryCalculateCornerConsequence(Expected.Usage, Consequence, Error));
		TestTrue(TEXT("outcome parity"), Consequence.Outcome == Expected.Outcome);
		TestTrue(TEXT("exit multiplier parity"),
			NearlyEqual(Consequence.ExitSpeedMultiplier, Expected.Multiplier));
		TestTrue(TEXT("line deviation parity"),
			NearlyEqual(Consequence.LineDeviationRatio, Expected.Deviation));
		TestTrue(TEXT("HUD feedback parity"),
			Consequence.HudFeedback == Expected.Feedback);
	}

	FCornerConsequence Wide;
	TestTrue(TEXT("wide-line consequence builds"),
		TryCalculateCornerConsequence(1.15, Wide, Error));
	double ExitSpeedMps = 0.0;
	TestTrue(TEXT("exit speed application succeeds"),
		TryApplyCornerExitSpeedMps(10.0, Wide, ExitSpeedMps, Error));
	TestTrue(TEXT("exit speed parity"), NearlyEqual(ExitSpeedMps, 8.5));

	FCornerConsequence Invalid = Wide;
	Invalid.ExitSpeedMultiplier = 1.1;
	TestFalse(TEXT("invalid consequence is rejected"),
		TryApplyCornerExitSpeedMps(10.0, Invalid, ExitSpeedMps, Error));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4AValidationTest,
	"CyclingCornering.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4AValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingCornering;

	FString Error;
	double Value = 123.0;
	TestFalse(TEXT("negative speed rejected"),
		TryCalculateCornerGripUsage(-1.0, 25.0, 0.8, 1.0, Value, Error));
	TestEqual(TEXT("failed calculation resets output"), Value, 0.0);
	TestTrue(TEXT("negative speed has error"), !Error.IsEmpty());

	TestFalse(TEXT("zero radius rejected"),
		TryCalculateMaximumCornerSpeedMps(0.0, 0.8, 1.0, Value, Error));
	TestFalse(TEXT("zero base friction rejected"),
		TryCalculateMaximumCornerSpeedMps(25.0, 0.0, 1.0, Value, Error));
	TestFalse(TEXT("zero grip multiplier rejected"),
		TryCalculateMaximumCornerSpeedMps(25.0, 0.8, 0.0, Value, Error));
	TestFalse(TEXT("grip multiplier above one rejected"),
		TryCalculateMaximumCornerSpeedMps(25.0, 0.8, 1.01, Value, Error));
	FCornerConsequence Consequence;
	TestFalse(TEXT("NaN usage rejected"),
		TryCalculateCornerConsequence(
			std::numeric_limits<double>::quiet_NaN(),
			Consequence,
			Error));

	FCorner DefaultCorner;
	ECornerPhase Phase = ECornerPhase::Entry;
	TestFalse(TEXT("unconfigured corner rejected"),
		TryGetCornerPhase(DefaultCorner, 0.0, 100.0, Phase, Error));
	TestTrue(TEXT("phase resets on failure"), Phase == ECornerPhase::Outside);

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
