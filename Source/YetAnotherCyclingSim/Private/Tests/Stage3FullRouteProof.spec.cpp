#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/AlpineJourneyRoute.h"
#include "Cycling/AlpineJourneyRuntimeContext.h"
#include "Cycling/CyclingSimulationSession.h"

namespace Stage3FullRouteProofTests
{
	using namespace CyclingSimulation;

	FCyclingSimulationSessionConfig MakeReferenceConfig()
	{
		FCyclingSimulationSessionConfig Config;
		Config.Rider.RiderMassKg = 75.0;
		Config.Rider.BikeMassKg = 8.5;
		Config.Rider.CdaM2 = 0.32;
		Config.Rider.RollingResistanceCoefficient = 0.004;
		Config.Rider.DrivetrainEfficiency = 0.97;

		Config.Environment.GradeDecimal = 0.0;
		Config.Environment.WindSpeedMps = 0.0;
		Config.Environment.AirDensityKgM3 = 1.225;
		Config.Environment.SurfaceWetness = 0.0;
		Config.Environment.RollingResistanceMultiplier = 1.0;
		Config.Environment.GripMultiplier = 1.0;

		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 2000.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = 200.0;
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 250.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 90.0;
		return Config;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3FullRouteReferenceRideTest,
	"CyclingStage3FullRoute.ReferenceRide",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3FullRouteReferenceRideTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3FullRouteProofTests;

	FString Error;

	FRouteProfile Route;
	TestTrue(TEXT("Alpine route profile builds"),
		TryBuildAlpineJourneyRouteProfile(Route, Error));
	TestEqual(TEXT("full-route length remains 10 km"),
		Route.GetTotalLengthM(), 10000.0);

	const TCHAR* ExpectedSegments[] = {
		TEXT("Village Start"),
		TEXT("River Descent"),
		TEXT("Meadow Rollers"),
		TEXT("Forest Approach"),
		TEXT("Challenge Climb"),
		TEXT("Mountain Shelf"),
		TEXT("High Valley Descent"),
		TEXT("Lakeside Finish"),
	};
	const TArray<FRouteSegment>& Segments = Route.GetSegments();
	TestEqual(TEXT("Alpine segment count remains eight"), Segments.Num(), 8);
	if (Segments.Num() == 8)
	{
		for (int32 Index = 0; Index < 8; ++Index)
		{
			TestEqual(TEXT("Alpine segment ordering remains stable"),
				Segments[Index].GetId(),
				FString(ExpectedSegments[Index]));
		}
	}

	FRouteGeometryProfile Geometry;
	TestTrue(TEXT("Alpine geometry builds"),
		TryBuildAlpineJourneyRouteGeometry(Geometry, Error));
	TestEqual(TEXT("geometry length remains 10 km"),
		Geometry.GetTotalLengthM(), 10000.0);

	double TotalAscentM = 0.0;
	double TotalDescentM = 0.0;
	const TArray<FRouteGeometrySample>& Samples = Geometry.GetSamples();
	for (int32 Index = 1; Index < Samples.Num(); ++Index)
	{
		const double DeltaZM =
			Samples[Index].PositionM.Z - Samples[Index - 1].PositionM.Z;
		if (DeltaZM >= 0.0)
		{
			TotalAscentM += DeltaZM;
		}
		else
		{
			TotalDescentM -= DeltaZM;
		}
	}

	TestTrue(TEXT("total ascent remains near Stage 3 baseline 155.34 m"),
		FMath::IsNearlyEqual(TotalAscentM, 155.34, 0.10));
	TestTrue(TEXT("total descent remains near Stage 3 baseline 72.03 m"),
		FMath::IsNearlyEqual(TotalDescentM, 72.03, 0.10));

	FAlpineJourneySimulationStepContextProvider Provider;
	const FCyclingSimulationSessionConfig Config = MakeReferenceConfig();
	TestTrue(TEXT("production Alpine context config succeeds"),
		Provider.TryConfigure(Config.Environment, 20.0, Error));

	FCyclingSimulationSession Session;
	TestTrue(TEXT("reference rider session config succeeds"),
		Session.TryConfigure(Config, Error));

	FSimulationState State;
	double RemainingTimeS = 0.0;
	int32 CompletedSteps = 0;
	TArray<FSimulationBoundaryCrossing> AllCrossings;
	bool bFinished = false;

	// 200 W is the representative Stage 3 proof plan. Current baseline is
	// about 23.2 minutes; product acceptance allows approximately 20–30 min.
	for (int32 FrameIndex = 0; FrameIndex < 8000 && !bFinished; ++FrameIndex)
	{
		TArray<FSimulationBoundaryCrossing> FrameCrossings;
		bool bStoppedAfterStep = false;
		TestTrue(TEXT("reference full-route frame advances"),
			Session.TryAdvanceWithContext(
				0.25,
				Provider,
				State,
				RemainingTimeS,
				CompletedSteps,
				FrameCrossings,
				bStoppedAfterStep,
				Error));

		if (!Error.IsEmpty())
		{
			AddError(FString::Printf(
				TEXT("reference full-route advance reported error: %s"),
				*Error));
			return false;
		}

		AllCrossings.Append(FrameCrossings);
		bFinished = bStoppedAfterStep;
	}

	TestTrue(TEXT("reference 200 W ride reaches deterministic finish"),
		bFinished);
	TestTrue(TEXT("reference ride remains within 20 minute lower bound"),
		State.ElapsedTimeS >= 20.0 * 60.0);
	TestTrue(TEXT("reference ride remains within 30 minute upper bound"),
		State.ElapsedTimeS <= 30.0 * 60.0);
	TestTrue(TEXT("final authoritative distance crosses 10 km"),
		State.DistanceM >= 10000.0);
	TestTrue(TEXT("fixed-step finish overshoot remains bounded"),
		State.DistanceM <= 10005.0);

	const TCHAR* ExpectedCrossings[] = {
		TEXT("start"),
		TEXT("sector-meadow-rollers"),
		TEXT("sector-challenge-climb"),
		TEXT("sector-high-valley-descent"),
		TEXT("sector-lakeside-finish"),
		TEXT("finish"),
	};
	TestEqual(TEXT("reference ride emits six route events"),
		AllCrossings.Num(), 6);
	if (AllCrossings.Num() == 6)
	{
		for (int32 Index = 0; Index < 6; ++Index)
		{
			TestEqual(TEXT("reference ride crossing order remains stable"),
				AllCrossings[Index].Id,
				FString(ExpectedCrossings[Index]));
		}

		TestEqual(TEXT("terminal event kind is Finish"),
			static_cast<int32>(AllCrossings.Last().Kind),
			static_cast<int32>(ESimulationBoundaryKind::Finish));
		TestEqual(TEXT("terminal boundary remains 10 km"),
			AllCrossings.Last().BoundaryDistanceM, 10000.0);
		TestEqual(TEXT("terminal event state matches final elapsed time"),
			AllCrossings.Last().PostStepState.ElapsedTimeS,
			State.ElapsedTimeS);
		TestEqual(TEXT("terminal event state matches final distance"),
			AllCrossings.Last().PostStepState.DistanceM,
			State.DistanceM);
	}

	AddInfo(FString::Printf(
		TEXT("Stage3 full-route reference: length=%.1f m ascent=%.2f m descent=%.2f m elapsed=%.2f s (%.2f min) final_distance=%.3f m final_speed=%.3f m/s"),
		Geometry.GetTotalLengthM(),
		TotalAscentM,
		TotalDescentM,
		State.ElapsedTimeS,
		State.ElapsedTimeS / 60.0,
		State.DistanceM,
		State.SpeedMps));

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
