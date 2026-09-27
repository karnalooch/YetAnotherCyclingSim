#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/Stage3GRouteExclusion.h"

#include <cmath>
#include <limits>

namespace Stage3GRouteExclusionTests
{
	using namespace CyclingSimulation;

	bool BuildRoute(
		const TArray<FRouteGeometrySample>& Samples,
		FRouteGeometryProfile& OutRoute,
		FString& OutError)
	{
		return OutRoute.TryConfigure(Samples, 1e-9, OutError);
	}

	FRouteGeometryProfile StraightRoute(FString& OutError)
	{
		TArray<FRouteGeometrySample> Samples;
		Samples.Add({0.0, FVector(0.0, 0.0, 0.0)});
		Samples.Add({100.0, FVector(100.0, 0.0, 0.0)});

		FRouteGeometryProfile Route;
		BuildRoute(Samples, Route, OutError);
		return Route;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GRouteExclusionStraightTest,
	"CyclingStage3World.RouteExclusion.StraightCorridor",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GRouteExclusionStraightTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3G;
	using namespace Stage3GRouteExclusionTests;

	FString Error;
	FRouteGeometryProfile Route = StraightRoute(Error);
	TestTrue(TEXT("straight route configures"), Route.IsConfigured());

	FRouteExclusionResult Result;
	TestTrue(TEXT("inside query resolves"),
		TryEvaluateRouteExclusion(Route, FVector(50.0, 2.9, 0.0), 3.0, Result, Error));
	TestTrue(TEXT("inside candidate is excluded"), Result.bExcluded);
	TestTrue(TEXT("inside horizontal distance"), FMath::IsNearlyEqual(Result.HorizontalDistanceToRouteM, 2.9));
	TestTrue(TEXT("inside negative clearance"), Result.ClearanceFromProtectedCorridorM < 0.0);

	TestTrue(TEXT("boundary query resolves"),
		TryEvaluateRouteExclusion(Route, FVector(50.0, 3.0, 100.0), 3.0, Result, Error));
	TestTrue(TEXT("boundary remains protected"), Result.bExcluded);
	TestTrue(TEXT("height does not change horizontal route clearance"),
		FMath::IsNearlyEqual(Result.HorizontalDistanceToRouteM, 3.0));

	TestTrue(TEXT("outside query resolves"),
		TryEvaluateRouteExclusion(Route, FVector(50.0, 3.1, 0.0), 3.0, Result, Error));
	TestFalse(TEXT("outside candidate is allowed"), Result.bExcluded);
	TestTrue(TEXT("outside positive clearance"), Result.ClearanceFromProtectedCorridorM > 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GRouteExclusionEndpointTest,
	"CyclingStage3World.RouteExclusion.EndpointDistance",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GRouteExclusionEndpointTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3G;
	using namespace Stage3GRouteExclusionTests;

	FString Error;
	FRouteGeometryProfile Route = StraightRoute(Error);

	FRouteExclusionResult Result;
	TestTrue(TEXT("endpoint query resolves"),
		TryEvaluateRouteExclusion(Route, FVector(105.0, 0.0, 0.0), 3.0, Result, Error));
	TestFalse(TEXT("candidate beyond route endpoint is clear"), Result.bExcluded);
	TestTrue(TEXT("closest endpoint distance is 5 m"),
		FMath::IsNearlyEqual(Result.HorizontalDistanceToRouteM, 5.0));
	TestTrue(TEXT("clearance outside 3 m corridor is 2 m"),
		FMath::IsNearlyEqual(Result.ClearanceFromProtectedCorridorM, 2.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GRouteExclusionPolylineTest,
	"CyclingStage3World.RouteExclusion.PolylineMinimum",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GRouteExclusionPolylineTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace CyclingStage3G;
	using namespace Stage3GRouteExclusionTests;

	TArray<FRouteGeometrySample> Samples;
	Samples.Add({0.0, FVector(0.0, 0.0, 0.0)});
	Samples.Add({50.0, FVector(50.0, 0.0, 0.0)});
	Samples.Add({100.0, FVector(50.0, 50.0, 0.0)});

	FRouteGeometryProfile Route;
	FString Error;
	TestTrue(TEXT("polyline route configures"), BuildRoute(Samples, Route, Error));

	FRouteExclusionResult Result;
	TestTrue(TEXT("polyline query resolves"),
		TryEvaluateRouteExclusion(Route, FVector(46.0, 30.0, 0.0), 5.0, Result, Error));
	TestTrue(TEXT("minimum is measured against nearest segment"), Result.bExcluded);
	TestTrue(TEXT("nearest segment is four metres away"),
		FMath::IsNearlyEqual(Result.HorizontalDistanceToRouteM, 4.0));
	return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GPresentationSurfaceTest,
	"CyclingStage3World.RouteExclusion.PresentationSurface",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GPresentationSurfaceTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3G;

	FString Error;
	FRoutePresentationSurfaceResult Result;

	TestTrue(TEXT("valley road corridor resolves"),
		TryEvaluateRoutePresentationSurface(1200.0, 8.0, Result, Error));
	TestTrue(TEXT("road corridor stays flat"),
		FMath::IsNearlyZero(Result.SurfaceRiseM));
	TestTrue(TEXT("valley profile exposes expected support width"),
		FMath::IsNearlyEqual(Result.TerrainHalfWidthM, 110.0));

	TestTrue(TEXT("valley outer support resolves"),
		TryEvaluateRoutePresentationSurface(1200.0, 110.0, Result, Error));
	TestTrue(TEXT("valley reaches 10 m rise"),
		FMath::IsNearlyEqual(Result.SurfaceRiseM, 10.0));

	FRoutePresentationSurfaceResult Left;
	FRoutePresentationSurfaceResult Right;
	TestTrue(TEXT("forest left resolves"),
		TryEvaluateRoutePresentationSurface(4900.0, -36.0, Left, Error));
	TestTrue(TEXT("forest right resolves"),
		TryEvaluateRoutePresentationSurface(4900.0, 36.0, Right, Error));
	TestTrue(TEXT("surface profile is symmetric"),
		FMath::IsNearlyEqual(Left.SurfaceRiseM, Right.SurfaceRiseM));
	TestTrue(TEXT("forest support is narrower than valley"),
		FMath::IsNearlyEqual(Left.TerrainHalfWidthM, 60.0));

	TestTrue(TEXT("high Alpine outer support resolves"),
		TryEvaluateRoutePresentationSurface(8000.0, 220.0, Result, Error));
	TestTrue(TEXT("high Alpine reaches 28 m rise"),
		FMath::IsNearlyEqual(Result.SurfaceRiseM, 28.0));

	const double Nan = std::numeric_limits<double>::quiet_NaN();
	TestFalse(TEXT("non-finite surface lateral rejected"),
		TryEvaluateRoutePresentationSurface(1200.0, Nan, Result, Error));
	return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3GRouteExclusionValidationTest,
	"CyclingStage3World.RouteExclusion.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3GRouteExclusionValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingStage3G;
	using namespace Stage3GRouteExclusionTests;

	FString Error;
	FRouteGeometryProfile Route = StraightRoute(Error);
	FRouteExclusionResult Result;

	TestFalse(TEXT("zero corridor rejected"),
		TryEvaluateRouteExclusion(Route, FVector::ZeroVector, 0.0, Result, Error));
	TestTrue(TEXT("zero corridor reports error"), !Error.IsEmpty());

	const double Nan = std::numeric_limits<double>::quiet_NaN();
	TestFalse(TEXT("non-finite candidate rejected"),
		TryEvaluateRouteExclusion(Route, FVector(Nan, 0.0, 0.0), 3.0, Result, Error));

	CyclingSimulation::FRouteGeometryProfile EmptyRoute;
	TestFalse(TEXT("unconfigured route rejected"),
		TryEvaluateRouteExclusion(EmptyRoute, FVector::ZeroVector, 3.0, Result, Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
