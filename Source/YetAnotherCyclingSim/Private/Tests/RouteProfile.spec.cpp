#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyRoute.h"
#include "Cycling/RouteProfile.h"

#include <limits>

namespace Stage3RouteProfileTests
{
	using namespace CyclingSimulation;

	const TCHAR* ExpectedIds[] = {
		TEXT("Village Start"),
		TEXT("River Descent"),
		TEXT("Meadow Rollers"),
		TEXT("Forest Approach"),
		TEXT("Challenge Climb"),
		TEXT("Mountain Shelf"),
		TEXT("High Valley Descent"),
		TEXT("Lakeside Finish"),
	};

	const double ExpectedLengthsM[] = {
		1000.0,
		1200.0,
		1500.0,
		1000.0,
		1500.0,
		1000.0,
		1500.0,
		1300.0,
	};

	const double ExpectedGrades[] = {
		0.005,
		-0.015,
		0.015,
		0.025,
		0.065,
		-0.010,
		-0.030,
		0.005,
	};

	const double ExpectedStartsM[] = {
		0.0,
		1000.0,
		2200.0,
		3700.0,
		4700.0,
		6200.0,
		7200.0,
		8700.0,
	};

	const double ExpectedEndsM[] = {
		1000.0,
		2200.0,
		3700.0,
		4700.0,
		6200.0,
		7200.0,
		8700.0,
		10000.0,
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteProfileAlpineParityTest,
	"CyclingRouteProfile.AlpineParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteProfileAlpineParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteProfileTests;

	FRouteProfile Profile;
	FString Error;
	TestTrue(TEXT("Alpine Journey factory succeeds"),
		TryBuildAlpineJourneyRouteProfile(Profile, Error));
	TestTrue(TEXT("factory clears error"), Error.IsEmpty());
	TestTrue(TEXT("profile is configured"), Profile.IsConfigured());
	TestEqual(TEXT("profile name"), Profile.GetName(), FString(TEXT("Alpine Journey")));
	TestEqual(TEXT("segment count"), Profile.GetSegments().Num(), 8);
	TestEqual(TEXT("total route length is exactly 10 km"), Profile.GetTotalLengthM(), 10000.0);

	const TArray<FRouteSegment>& Segments = Profile.GetSegments();
	if (Segments.Num() == 8)
	{
		for (int32 Index = 0; Index < 8; ++Index)
		{
			const FRouteSegment& Segment = Segments[Index];
			TestEqual(TEXT("segment id parity"),
				Segment.GetId(), FString(ExpectedIds[Index]));
			TestEqual(TEXT("segment length parity"),
				Segment.GetLengthM(), ExpectedLengthsM[Index]);
			TestEqual(TEXT("segment grade parity"),
				Segment.GetGradeDecimal(), ExpectedGrades[Index]);
			TestEqual(TEXT("segment start distance parity"),
				Segment.GetStartDistanceM(), ExpectedStartsM[Index]);
			TestEqual(TEXT("segment end distance parity"),
				Segment.GetEndDistanceM(), ExpectedEndsM[Index]);
		}
	}

	int32 ChallengeClimbCount = 0;
	for (const FRouteSegment& Segment : Segments)
	{
		if (Segment.GetGradeDecimal() == 0.065)
		{
			++ChallengeClimbCount;
			TestEqual(TEXT("6.5 percent segment is Challenge Climb"),
				Segment.GetId(), FString(TEXT("Challenge Climb")));
		}
	}
	TestEqual(TEXT("exactly one 6.5 percent segment"), ChallengeClimbCount, 1);

	TestTrue(TEXT("total ascent stays in Python reference range"),
		Profile.GetTotalAscentM() >= 140.0 && Profile.GetTotalAscentM() <= 170.0);
	TestTrue(TEXT("total descent stays in Python reference range"),
		Profile.GetTotalDescentM() >= 60.0 && Profile.GetTotalDescentM() <= 90.0);
	TestTrue(TEXT("net elevation equals ascent minus descent"),
		FMath::IsNearlyEqual(
			Profile.GetTotalElevationChangeM(),
			Profile.GetTotalAscentM() - Profile.GetTotalDescentM(),
			1e-9));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteProfileBoundaryLookupTest,
	"CyclingRouteProfile.BoundaryLookup",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteProfileBoundaryLookupTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteProfileTests;

	FRouteProfile Profile;
	FString Error;
	TestTrue(TEXT("Alpine Journey factory succeeds"),
		TryBuildAlpineJourneyRouteProfile(Profile, Error));

	const FRouteSegment* Segment = nullptr;
	int32 SegmentIndex = INDEX_NONE;

	TestTrue(TEXT("0 m resolves"), Profile.TryGetSegmentAtDistance(0.0, Segment, SegmentIndex, Error));
	TestEqual(TEXT("0 m selects first segment"), SegmentIndex, 0);
	if (Segment != nullptr)
	{
		TestEqual(TEXT("0 m selects Village Start"),
			Segment->GetId(), FString(TEXT("Village Start")));
	}

	for (int32 BoundaryIndex = 0; BoundaryIndex < 7; ++BoundaryIndex)
	{
		const double BoundaryM = ExpectedEndsM[BoundaryIndex];

		Segment = nullptr;
		SegmentIndex = INDEX_NONE;
		TestTrue(TEXT("immediately before interior boundary resolves"),
			Profile.TryGetSegmentAtDistance(BoundaryM - 1e-9, Segment, SegmentIndex, Error));
		TestEqual(TEXT("immediately before boundary stays in previous segment"),
			SegmentIndex, BoundaryIndex);

		Segment = nullptr;
		SegmentIndex = INDEX_NONE;
		TestTrue(TEXT("exact interior boundary resolves"),
			Profile.TryGetSegmentAtDistance(BoundaryM, Segment, SegmentIndex, Error));
		TestEqual(TEXT("exact interior boundary selects next segment"),
			SegmentIndex, BoundaryIndex + 1);

		Segment = nullptr;
		SegmentIndex = INDEX_NONE;
		TestTrue(TEXT("immediately after interior boundary resolves"),
			Profile.TryGetSegmentAtDistance(BoundaryM + 1e-9, Segment, SegmentIndex, Error));
		TestEqual(TEXT("immediately after boundary stays in next segment"),
			SegmentIndex, BoundaryIndex + 1);
	}

	Segment = nullptr;
	SegmentIndex = INDEX_NONE;
	TestTrue(TEXT("exact route end resolves"),
		Profile.TryGetSegmentAtDistance(10000.0, Segment, SegmentIndex, Error));
	TestEqual(TEXT("exact route end selects final segment"), SegmentIndex, 7);
	if (Segment != nullptr)
	{
		TestEqual(TEXT("route end selects Lakeside Finish"),
			Segment->GetId(), FString(TEXT("Lakeside Finish")));
	}

	Segment = nullptr;
	SegmentIndex = 123;
	TestFalse(TEXT("negative route distance rejected"),
		Profile.TryGetSegmentAtDistance(-1.0, Segment, SegmentIndex, Error));
	TestTrue(TEXT("negative route distance has useful error"), !Error.IsEmpty());
	TestTrue(TEXT("negative failure clears segment pointer"), Segment == nullptr);
	TestEqual(TEXT("negative failure resets segment index"), SegmentIndex, INDEX_NONE);

	Segment = nullptr;
	SegmentIndex = 123;
	TestFalse(TEXT("distance beyond route rejected"),
		Profile.TryGetSegmentAtDistance(10000.0 + 1e-9, Segment, SegmentIndex, Error));
	TestTrue(TEXT("beyond-route distance has useful error"), !Error.IsEmpty());

	Segment = nullptr;
	SegmentIndex = 123;
	TestFalse(TEXT("NaN route distance rejected"),
		Profile.TryGetSegmentAtDistance(
			std::numeric_limits<double>::quiet_NaN(),
			Segment,
			SegmentIndex,
			Error));
	TestTrue(TEXT("NaN route distance has useful error"), !Error.IsEmpty());

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RouteProfileValidationTest,
	"CyclingRouteProfile.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RouteProfileValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;

	FRouteProfile Profile;
	FString Error;

	TArray<FRouteSegmentDefinition> ValidSegments;
	ValidSegments.Add({ TEXT("  First  "), 100.0, 0.01 });
	ValidSegments.Add({ TEXT("Second"), 200.0, -0.02 });

	TestTrue(TEXT("valid profile config succeeds"),
		Profile.TryConfigure(TEXT("  Test Route  "), ValidSegments, Error));
	TestEqual(TEXT("profile name is trimmed"),
		Profile.GetName(), FString(TEXT("Test Route")));
	TestEqual(TEXT("segment id is trimmed"),
		Profile.GetSegments()[0].GetId(), FString(TEXT("First")));
	TestEqual(TEXT("valid profile length"), Profile.GetTotalLengthM(), 300.0);

	const FString PreservedName = Profile.GetName();
	const double PreservedLengthM = Profile.GetTotalLengthM();

	TArray<FRouteSegmentDefinition> EmptySegments;
	TestFalse(TEXT("empty segment list rejected"),
		Profile.TryConfigure(TEXT("Invalid"), EmptySegments, Error));
	TestEqual(TEXT("failed reconfigure preserves profile name"),
		Profile.GetName(), PreservedName);
	TestEqual(TEXT("failed reconfigure preserves total length"),
		Profile.GetTotalLengthM(), PreservedLengthM);

	TArray<FRouteSegmentDefinition> DuplicateIds;
	DuplicateIds.Add({ TEXT("same"), 100.0, 0.0 });
	DuplicateIds.Add({ TEXT("same"), 100.0, 0.0 });
	TestFalse(TEXT("duplicate segment ids rejected"),
		Profile.TryConfigure(TEXT("Invalid"), DuplicateIds, Error));

	TArray<FRouteSegmentDefinition> InvalidLength;
	InvalidLength.Add({ TEXT("bad-length"), 0.0, 0.0 });
	TestFalse(TEXT("zero segment length rejected"),
		Profile.TryConfigure(TEXT("Invalid"), InvalidLength, Error));

	TArray<FRouteSegmentDefinition> InvalidGrade;
	InvalidGrade.Add({
		TEXT("bad-grade"),
		100.0,
		std::numeric_limits<double>::infinity()
	});
	TestFalse(TEXT("non-finite grade rejected"),
		Profile.TryConfigure(TEXT("Invalid"), InvalidGrade, Error));

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
