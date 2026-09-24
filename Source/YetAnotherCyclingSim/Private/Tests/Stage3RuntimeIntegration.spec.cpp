#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Cycling/AlpineJourneyRuntimeContext.h"
#include "Cycling/CyclingPrototypePawn.h"
#include "Cycling/CyclingSimulationSession.h"

#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

namespace Stage3RuntimeIntegrationTests
{
	using namespace CyclingSimulation;

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

	FCyclingSimulationSessionConfig MakeFastSessionConfig()
	{
		FCyclingSimulationSessionConfig Config;
		Config.Rider.RiderMassKg = 75.0;
		Config.Rider.BikeMassKg = 8.5;
		Config.Rider.CdaM2 = 0.32;
		Config.Rider.RollingResistanceCoefficient = 0.004;
		Config.Rider.DrivetrainEfficiency = 0.97;
		Config.Environment = MakeBaseEnvironment();
		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 2000.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = 2000.0;
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 250.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 90.0;
		return Config;
	}

	struct FRouteRunResult
	{
		FSimulationState State;
		double RemainingTimeS = 0.0;
		TArray<FSimulationBoundaryCrossing> Crossings;
		bool bFinished = false;
	};

	bool RunToFinish(
		FCyclingSimulationSession& Session,
		const FAlpineJourneySimulationStepContextProvider& Provider,
		const TArray<double>& FramePatternS,
		FRouteRunResult& OutResult,
		FString& OutError)
	{
		OutResult = FRouteRunResult();
		if (FramePatternS.Num() == 0)
		{
			OutError = TEXT("frame pattern must not be empty");
			return false;
		}

		for (int32 FrameIndex = 0; FrameIndex < 20000; ++FrameIndex)
		{
			const double FrameDeltaS = FramePatternS[FrameIndex % FramePatternS.Num()];
			int32 CompletedSteps = 0;
			TArray<FSimulationBoundaryCrossing> FrameCrossings;
			bool bStoppedAfterStep = false;

			if (!Session.TryAdvanceWithContext(
					FrameDeltaS,
					Provider,
					OutResult.State,
					OutResult.RemainingTimeS,
					CompletedSteps,
					FrameCrossings,
					bStoppedAfterStep,
					OutError))
			{
				return false;
			}

			OutResult.Crossings.Append(FrameCrossings);
			if (bStoppedAfterStep)
			{
				OutResult.bFinished = true;
				return true;
			}
		}

		OutError = TEXT("route did not reach terminal finish within frame budget");
		return false;
	}

	UWorld* CreateTransientWorld()
	{
		return UWorld::CreateWorld(EWorldType::Game, false, TEXT("Stage3RuntimeIntegrationWorld"));
	}

	void DestroyTransientWorld(UWorld* World)
	{
		if (World)
		{
			World->DestroyWorld(false);
		}
	}

	AActor* SpawnStraightRouteActor(UWorld* World, float LengthCm)
	{
		AActor* RouteActor = World->SpawnActor<AActor>();
		if (!RouteActor)
		{
			return nullptr;
		}

		USceneComponent* Root = NewObject<USceneComponent>(
			RouteActor,
			USceneComponent::StaticClass(),
			TEXT("RouteRoot"));
		Root->SetMobility(EComponentMobility::Movable);
		RouteActor->SetRootComponent(Root);
		Root->RegisterComponent();

		USplineComponent* Spline = NewObject<USplineComponent>(
			RouteActor,
			USplineComponent::StaticClass(),
			TEXT("RouteSpline"));
		Spline->SetMobility(EComponentMobility::Movable);
		Spline->SetupAttachment(Root);
		Spline->RegisterComponent();
		Spline->ClearSplinePoints(false);
		Spline->AddSplinePoint(
			FVector::ZeroVector,
			ESplineCoordinateSpace::Local,
			false);
		Spline->AddSplinePoint(
			FVector(LengthCm, 0.0f, 0.0f),
			ESplineCoordinateSpace::Local,
			false);
		Spline->UpdateSpline();

		return RouteActor;
	}

	ACyclingPrototypePawn* SpawnPawn(UWorld* World, AActor* RouteActor)
	{
		ACyclingPrototypePawn* Pawn = World->SpawnActor<ACyclingPrototypePawn>();
		if (Pawn)
		{
			Pawn->RouteActor = RouteActor;
			Pawn->bAutoStart = false;
		}
		return Pawn;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RuntimeMarkerContractTest,
	"CyclingStage3Runtime.MarkerContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RuntimeMarkerContractTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RuntimeIntegrationTests;

	FAlpineJourneySimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("Alpine runtime context config succeeds"),
		Provider.TryConfigure(MakeBaseEnvironment(), 20.0, Error));
	TestTrue(TEXT("Alpine runtime context config clears error"), Error.IsEmpty());
	TestEqual(TEXT("authoritative route length is 10 km"),
		Provider.GetRouteLengthM(), 10000.0);

	const TArray<FSimulationBoundaryDefinition>& Boundaries = Provider.GetBoundaries();
	TestEqual(TEXT("start + four sectors + finish"), Boundaries.Num(), 6);

	const TCHAR* ExpectedIds[] = {
		TEXT("start"),
		TEXT("sector-meadow-rollers"),
		TEXT("sector-challenge-climb"),
		TEXT("sector-high-valley-descent"),
		TEXT("sector-lakeside-finish"),
		TEXT("finish"),
	};
	const double ExpectedDistancesM[] = {
		0.0,
		2200.0,
		4700.0,
		7200.0,
		8700.0,
		10000.0,
	};

	if (Boundaries.Num() == 6)
	{
		for (int32 Index = 0; Index < 6; ++Index)
		{
			TestEqual(TEXT("marker id is stable"),
				Boundaries[Index].Id, FString(ExpectedIds[Index]));
			TestEqual(TEXT("marker distance derives from Alpine profile"),
				Boundaries[Index].DistanceM, ExpectedDistancesM[Index]);
		}

		TestEqual(TEXT("first marker kind is Start"),
			static_cast<int32>(Boundaries[0].Kind),
			static_cast<int32>(ESimulationBoundaryKind::Start));
		TestEqual(TEXT("last marker kind is Finish"),
			static_cast<int32>(Boundaries.Last().Kind),
			static_cast<int32>(ESimulationBoundaryKind::Finish));
		TestTrue(TEXT("finish is terminal"), Boundaries.Last().bStopAfterCrossing);
	}

	FSimulationState Pre;
	FSimulationState Post;
	Pre.DistanceM = 4699.9;
	Pre.ElapsedTimeS = 10.0;
	Post.DistanceM = 4700.0;
	Post.ElapsedTimeS = 10.05;

	TArray<FSimulationBoundaryCrossing> Crossings;
	bool bStopped = false;
	TestTrue(TEXT("exact sector crossing observes successfully"),
		Provider.TryObserveCompletedStep(Pre, Post, Crossings, bStopped, Error));
	TestEqual(TEXT("exact sector crossing emits one event"), Crossings.Num(), 1);
	if (Crossings.Num() == 1)
	{
		TestEqual(TEXT("exact sector is Challenge Climb"),
			Crossings[0].Id, FString(TEXT("sector-challenge-climb")));
	}
	TestFalse(TEXT("sector crossing is non-terminal"), bStopped);

	// The production Stage 3D provider must carry the Stage 3C geometry-derived
	// grade into the same fixed-step context used for lifecycle markers.
	struct FGradeCase
	{
		double DistanceM;
		double ExpectedGrade;
	};
	const FGradeCase GradeCases[] = {
		{ 500.0, 0.005 },
		{ 5450.0, 0.065 },
		{ 7950.0, -0.030 },
	};
	for (const FGradeCase& Case : GradeCases)
	{
		FSimulationState GradeState;
		GradeState.DistanceM = Case.DistanceM;
		FEnvironment Environment;
		TestTrue(TEXT("production route context resolves local grade"),
			Provider.TryResolveEnvironment(GradeState, Environment, Error));
		TestTrue(TEXT("production route context grade matches Alpine geometry"),
			FMath::IsNearlyEqual(Environment.GradeDecimal, Case.ExpectedGrade, 1e-3));
	}

	Pre = Post;
	Post.DistanceM = 4700.1;
	Post.ElapsedTimeS = 10.10;
	TestTrue(TEXT("post-boundary observation succeeds"),
		Provider.TryObserveCompletedStep(Pre, Post, Crossings, bStopped, Error));
	TestEqual(TEXT("already-crossed sector is not replayed"), Crossings.Num(), 0);

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RuntimeFramePacingFinishTest,
	"CyclingStage3Runtime.FullRouteFramePacing",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RuntimeFramePacingFinishTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace Stage3RuntimeIntegrationTests;

	FAlpineJourneySimulationStepContextProvider Provider;
	FString Error;
	TestTrue(TEXT("Alpine runtime context config succeeds"),
		Provider.TryConfigure(MakeBaseEnvironment(), 20.0, Error));

	FCyclingSimulationSession RegularSession;
	FCyclingSimulationSession HitchSession;
	const FCyclingSimulationSessionConfig Config = MakeFastSessionConfig();
	TestTrue(TEXT("regular session config succeeds"),
		RegularSession.TryConfigure(Config, Error));
	TestTrue(TEXT("hitch session config succeeds"),
		HitchSession.TryConfigure(Config, Error));

	FRouteRunResult Regular;
	FRouteRunResult Hitch;
	const TArray<double> RegularPattern = { 0.25 };
	const TArray<double> HitchPattern = { 0.03, 0.07, 0.11, 0.04, 0.30, 0.50 };

	TestTrue(TEXT("regular full-route run reaches finish"),
		RunToFinish(RegularSession, Provider, RegularPattern, Regular, Error));
	TestTrue(TEXT("hitch full-route run reaches finish"),
		RunToFinish(HitchSession, Provider, HitchPattern, Hitch, Error));
	TestTrue(TEXT("regular run terminal flag set"), Regular.bFinished);
	TestTrue(TEXT("hitch run terminal flag set"), Hitch.bFinished);

	TestEqual(TEXT("frame pacing final speed is bit-exact"),
		Regular.State.SpeedMps, Hitch.State.SpeedMps);
	TestEqual(TEXT("frame pacing final distance is bit-exact"),
		Regular.State.DistanceM, Hitch.State.DistanceM);
	TestEqual(TEXT("frame pacing final elapsed time is bit-exact"),
		Regular.State.ElapsedTimeS, Hitch.State.ElapsedTimeS);
	TestTrue(TEXT("finish step crosses authoritative 10 km"),
		Regular.State.DistanceM >= 10000.0);
	TestTrue(TEXT("finish overshoot stays within one small fixed-step band"),
		Regular.State.DistanceM <= 10005.0);

	TestEqual(TEXT("both runs emit the same six route markers"),
		Regular.Crossings.Num(), Hitch.Crossings.Num());
	TestEqual(TEXT("full route emits start + four sectors + finish"),
		Regular.Crossings.Num(), 6);

	if (Regular.Crossings.Num() == Hitch.Crossings.Num())
	{
		for (int32 Index = 0; Index < Regular.Crossings.Num(); ++Index)
		{
			TestEqual(TEXT("crossing id independent of frame grouping"),
				Regular.Crossings[Index].Id, Hitch.Crossings[Index].Id);
			TestEqual(TEXT("crossing step time independent of frame grouping"),
				Regular.Crossings[Index].PostStepState.ElapsedTimeS,
				Hitch.Crossings[Index].PostStepState.ElapsedTimeS);
			TestEqual(TEXT("crossing step distance independent of frame grouping"),
				Regular.Crossings[Index].PostStepState.DistanceM,
				Hitch.Crossings[Index].PostStepState.DistanceM);
		}
	}

	if (Regular.Crossings.Num() == 6)
	{
		TestEqual(TEXT("last full-route event is finish"),
			static_cast<int32>(Regular.Crossings.Last().Kind),
			static_cast<int32>(ESimulationBoundaryKind::Finish));
	}

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage3RuntimePauseRestartMarkersTest,
	"CyclingStage3Runtime.PauseResumeRestartMarkers",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage3RuntimePauseRestartMarkersTest::RunTest(const FString& Parameters)
{
	using namespace Stage3RuntimeIntegrationTests;

	UWorld* World = CreateTransientWorld();
	AActor* Route = SpawnStraightRouteActor(World, 1000000.0f);
	ACyclingPrototypePawn* Pawn = SpawnPawn(World, Route);
	if (!Pawn)
	{
		AddError(TEXT("failed to spawn Stage 3 runtime Pawn"));
		DestroyTransientWorld(World);
		return false;
	}

	Pawn->InitializeRide();
	Pawn->StartRide();
	Pawn->Tick(0.10f);

	TestEqual(TEXT("first forward ride emits exactly one start marker"),
		Pawn->GetBoundaryHistory().Num(), 1);
	if (Pawn->GetBoundaryHistory().Num() == 1)
	{
		TestEqual(TEXT("first marker is start"),
			Pawn->GetBoundaryHistory()[0].Id, FString(TEXT("start")));
	}

	const double DistanceBeforePause = Pawn->GetAuthoritativeState().DistanceM;
	Pawn->StopRide();
	Pawn->StartRide();
	Pawn->Tick(0.10f);

	TestTrue(TEXT("resume advances existing authoritative ride"),
		Pawn->GetAuthoritativeState().DistanceM > DistanceBeforePause);
	TestEqual(TEXT("resume does not replay start marker"),
		Pawn->GetBoundaryHistory().Num(), 1);

	Pawn->RestartRide();
	TestEqual(TEXT("restart clears per-ride marker history"),
		Pawn->GetBoundaryHistory().Num(), 0);
	TestEqual(TEXT("restart resets authoritative distance"),
		Pawn->GetAuthoritativeState().DistanceM, 0.0);

	Pawn->Tick(0.10f);
	TestEqual(TEXT("restart re-arms start marker"),
		Pawn->GetBoundaryHistory().Num(), 1);
	if (Pawn->GetBoundaryHistory().Num() == 1)
	{
		TestEqual(TEXT("replayed ride emits start again"),
			Pawn->GetBoundaryHistory()[0].Id, FString(TEXT("start")));
	}

	DestroyTransientWorld(World);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
