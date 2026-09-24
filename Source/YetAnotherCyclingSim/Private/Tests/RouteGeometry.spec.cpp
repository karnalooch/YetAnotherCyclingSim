#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/NumericLimits.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/AlpineJourneyRoute.h"
#include "Cycling/RouteGeometry.h"
#include "Cycling/RouteGeometryStepContext.h"

namespace Stage3RouteGeometryTests
{
	using namespace CyclingSimulation;

	double Cross2D(const FVector& A, const FVector& B, const FVector& C)
	{
		return (B.X - A.X) * (C.Y - A.Y)
			- (B.Y - A.Y) * (C.X - A.X);
	}

	bool SegmentsProperlyIntersect2D(
		const FVector& A,
		const FVector& B,
		const FVector& C,
		const FVector& D)
	{
		const double AB_C = Cross2D(A, B, C);
		const double AB_D = Cross2D(A, B, D);
		const double CD_A = Cross2D(C, D, A);
		const double CD_B = Cross2D(C, D, B);
		return AB_C * AB_D < 0.0 && CD_A * CD_B < 0.0;
	}

	FEnvironment MakeBaseEnvironment()
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
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3AlpineGeometryStructureTest,
	"CyclingRouteGeometry.AlpineStructure",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3AlpineGeometryStructureTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;

	FRouteGeometryProfile Geometry;
	FString Error;
	TestTrue(TEXT("Alpine geometry build succeeds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));
	TestTrue(TEXT("Alpine geometry build clears error"), Error.IsEmpty());
	TestTrue(TEXT("geometry is configured"), Geometry.IsConfigured());
	TestEqual(TEXT("geometry total route distance is exactly 10 km"),
		Geometry.GetTotalLengthM(), 10000.0);
	TestEqual(TEXT("10 m sampling produces 1001 samples"),
		Geometry.GetSamples().Num(), 1001);

	const TArray<FRouteGeometrySample>& Samples = Geometry.GetSamples();
	for (int32 Index = 1; Index < Samples.Num(); ++Index)
	{
		const double RouteDeltaM = Samples[Index].DistanceM - Samples[Index - 1].DistanceM;
		const double GeometryDeltaM = FVector::Distance(
			Samples[Index].PositionM,
			Samples[Index - 1].PositionM);

		TestTrue(TEXT("route sample distances are strictly increasing"),
			RouteDeltaM > 0.0);
		TestTrue(TEXT("geometry interval has finite non-zero length"),
			FMath::IsFinite(GeometryDeltaM) && GeometryDeltaM > 0.0);
		TestTrue(TEXT("geometry interval length tracks route distance"),
			FMath::IsNearlyEqual(RouteDeltaM, GeometryDeltaM, 1e-6));
		TestTrue(TEXT("sample X finite"), FMath::IsFinite(Samples[Index].PositionM.X));
		TestTrue(TEXT("sample Y finite"), FMath::IsFinite(Samples[Index].PositionM.Y));
		TestTrue(TEXT("sample Z finite"), FMath::IsFinite(Samples[Index].PositionM.Z));
	}

	double MinY = 0.0;
	double MaxY = 0.0;
	for (const FRouteGeometrySample& Sample : Samples)
	{
		MinY = FMath::Min(MinY, Sample.PositionM.Y);
		MaxY = FMath::Max(MaxY, Sample.PositionM.Y);
	}
	TestTrue(TEXT("route has substantial lateral geometry rather than a straight line"),
		(MaxY - MinY) > 1000.0);

	int32 SelfIntersectionCount = 0;
	for (int32 FirstIndex = 0; FirstIndex < Samples.Num() - 1; ++FirstIndex)
	{
		for (int32 SecondIndex = FirstIndex + 3;
			SecondIndex < Samples.Num() - 1;
			++SecondIndex)
		{
			if (Stage3RouteGeometryTests::SegmentsProperlyIntersect2D(
				Samples[FirstIndex].PositionM,
				Samples[FirstIndex + 1].PositionM,
				Samples[SecondIndex].PositionM,
				Samples[SecondIndex + 1].PositionM))
			{
				++SelfIntersectionCount;
			}
		}
	}
	TestEqual(TEXT("prototype centerline has no unplanned XY self-crossings"),
		SelfIntersectionCount, 0);

	TArray<FAlpineCornerGeometryDefinition> Corners;
	BuildAlpineCornerGeometryDefinitions(Corners);
	TestEqual(TEXT("eight Stage 3 corner geometry zones"), Corners.Num(), 8);

	double MinRadiusM = TNumericLimits<double>::Max();
	double MaxRadiusM = 0.0;
	for (const FAlpineCornerGeometryDefinition& Corner : Corners)
	{
		TestTrue(TEXT("corner radius positive"), Corner.RadiusM > 0.0);
		TestTrue(TEXT("corner length positive"), Corner.LengthM > 0.0);
		MinRadiusM = FMath::Min(MinRadiusM, Corner.RadiusM);
		MaxRadiusM = FMath::Max(MaxRadiusM, Corner.RadiusM);
	}
	TestEqual(TEXT("tightest planned radius is 18 m"), MinRadiusM, 18.0);
	TestEqual(TEXT("widest planned radius is 55 m"), MaxRadiusM, 55.0);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3AlpineGeometryGradeTest,
	"CyclingRouteGeometry.GradeFromGeometry",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3AlpineGeometryGradeTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;

	FRouteGeometryProfile Geometry;
	FRouteProfile Route;
	FString Error;
	TestTrue(TEXT("Alpine geometry build succeeds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));
	TestTrue(TEXT("Alpine route build succeeds"),
		TryBuildAlpineJourneyRouteProfile(Route, Error));

	const TArray<FRouteSegment>& Segments = Route.GetSegments();
	for (const FRouteSegment& Segment : Segments)
	{
		const double MidpointM =
			0.5 * (Segment.GetStartDistanceM() + Segment.GetEndDistanceM());
		double DerivedGrade = 0.0;
		TestTrue(TEXT("mid-segment geometry grade resolves"),
			Geometry.TryCalculateGrade(MidpointM, 20.0, DerivedGrade, Error));
		TestTrue(TEXT("mid-segment geometry grade matches nominal target"),
			FMath::IsNearlyEqual(
				DerivedGrade,
				Segment.GetGradeDecimal(),
				1e-3));
	}

	double PreviousGrade = 0.0;
	bool bHavePrevious = false;
	double MaxAdjacentGradeDelta = 0.0;
	for (double DistanceM = 0.0; DistanceM <= Geometry.GetTotalLengthM(); DistanceM += 10.0)
	{
		double Grade = 0.0;
		TestTrue(TEXT("10 m grid grade resolves"),
			Geometry.TryCalculateGrade(DistanceM, 10.0, Grade, Error));
		TestTrue(TEXT("derived grade finite"), FMath::IsFinite(Grade));

		if (bHavePrevious)
		{
			MaxAdjacentGradeDelta = FMath::Max(
				MaxAdjacentGradeDelta,
				FMath::Abs(Grade - PreviousGrade));
		}
		PreviousGrade = Grade;
		bHavePrevious = true;
	}

	TestTrue(TEXT("smoothed geometry avoids abrupt >1.25 percentage-point grade jumps per 10 m"),
		MaxAdjacentGradeDelta <= 0.0125);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3AlpineGeometryLookupTest,
	"CyclingRouteGeometry.PositionLookup",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3AlpineGeometryLookupTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;

	FRouteGeometryProfile Geometry;
	FString Error;
	TestTrue(TEXT("Alpine geometry build succeeds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	FVector PositionM;
	TestTrue(TEXT("route start position resolves"),
		Geometry.TrySamplePosition(0.0, PositionM, Error));
	TestEqual(TEXT("route starts at origin"), PositionM, FVector::ZeroVector);

	const double QueriesM[] = { 0.001, 650.0, 1000.0, 5350.0, 7550.0, 9999.999, 10000.0 };
	for (const double DistanceM : QueriesM)
	{
		TestTrue(TEXT("representative route position resolves"),
			Geometry.TrySamplePosition(DistanceM, PositionM, Error));
		TestTrue(TEXT("representative position X finite"), FMath::IsFinite(PositionM.X));
		TestTrue(TEXT("representative position Y finite"), FMath::IsFinite(PositionM.Y));
		TestTrue(TEXT("representative position Z finite"), FMath::IsFinite(PositionM.Z));
	}

	TestFalse(TEXT("negative position query rejected"),
		Geometry.TrySamplePosition(-0.001, PositionM, Error));
	TestFalse(TEXT("beyond-route position query rejected"),
		Geometry.TrySamplePosition(10000.001, PositionM, Error));

	double Grade = 0.0;
	TestFalse(TEXT("zero grade window rejected"),
		Geometry.TryCalculateGrade(1000.0, 0.0, Grade, Error));
	TestFalse(TEXT("beyond-route grade query rejected"),
		Geometry.TryCalculateGrade(10000.001, 10.0, Grade, Error));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GeometryContextProviderTest,
	"CyclingRouteGeometry.FixedStepContext",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GeometryContextProviderTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RouteGeometryTests;

	FRouteGeometryProfile Geometry;
	FString Error;
	TestTrue(TEXT("Alpine geometry build succeeds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));

	FRouteGeometrySimulationStepContextProvider Provider;
	TestTrue(TEXT("geometry context config succeeds"),
		Provider.TryConfigure(Geometry, MakeBaseEnvironment(), 20.0, Error));
	TestTrue(TEXT("geometry context config clears error"), Error.IsEmpty());

	struct FExpectedGrade
	{
		double DistanceM;
		double Grade;
	};

	const FExpectedGrade Cases[] = {
		{ 500.0, 0.005 },
		{ 1600.0, -0.015 },
		{ 2950.0, 0.015 },
		{ 4200.0, 0.025 },
		{ 5450.0, 0.065 },
		{ 6700.0, -0.010 },
		{ 7950.0, -0.030 },
		{ 9350.0, 0.005 },
	};

	for (const FExpectedGrade& Case : Cases)
	{
		FSimulationState State;
		State.DistanceM = Case.DistanceM;
		FEnvironment Environment;
		TestTrue(TEXT("fixed-step context environment resolves"),
			Provider.TryResolveEnvironment(State, Environment, Error));
		TestTrue(TEXT("fixed-step context grade comes from geometry"),
			FMath::IsNearlyEqual(Environment.GradeDecimal, Case.Grade, 1e-3));
		TestEqual(TEXT("base wind remains unchanged"),
			Environment.WindSpeedMps, 0.0);
		TestEqual(TEXT("base air density remains unchanged"),
			Environment.AirDensityKgM3, 1.225);
	}

	FSimulationState Before;
	Before.DistanceM = 10.0;
	FSimulationState After = Before;
	After.DistanceM = 10.1;
	After.ElapsedTimeS = 0.05;
	TArray<FSimulationBoundaryCrossing> Crossings;
	bool bStopAfterStep = true;
	TestTrue(TEXT("Stage 3C completed-step observation succeeds"),
		Provider.TryObserveCompletedStep(
			Before,
			After,
			Crossings,
			bStopAfterStep,
			Error));
	TestEqual(TEXT("Stage 3C provider emits no lifecycle boundaries"), Crossings.Num(), 0);
	TestFalse(TEXT("Stage 3C provider does not stop fixed-step batch"), bStopAfterStep);

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
