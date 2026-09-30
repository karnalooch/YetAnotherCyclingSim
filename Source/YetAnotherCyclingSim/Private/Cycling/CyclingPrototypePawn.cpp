// Copyright YetAnotherCyclingSim. All Rights Reserved.

#include "Cycling/CyclingPrototypePawn.h"

#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingPrototypePawn, Log, All);

namespace CyclingPrototypePawnInternal
{
	// Meters -> Unreal centimetres. Used only at the presentation boundary.
	constexpr double MetresToCentimetres = 100.0;

	// Stage 2 diagnostic overlay refresh interval (s). The Stage 2
	// contract recommends 4 Hz (0.25 s). Slow enough to keep the
	// FString build cost negligible, fast enough that PIE feedback
	// remains live.
	constexpr float DiagnosticRefreshIntervalS = 0.25f;

	// Grade is derived from deterministic Stage 3 geometry over a 40 m total
	// window (20 m either side of authoritative pre-step DistanceM).
	constexpr double Stage3GradeHalfWindowM = 20.0;
}

ACyclingPrototypePawn::ACyclingPrototypePawn()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
	Root->SetMobility(EComponentMobility::Movable);

	BicycleMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BicycleMesh"));
	BicycleMesh->SetupAttachment(Root);
	BicycleMesh->SetMobility(EComponentMobility::Movable);
	// Mesh asset is intentionally NOT hard-coded in C++; it is assigned on
	// the instance (Basic Cube from /Engine/BasicShapes/Cube).
	BicycleMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	BicycleMesh->SetGenerateOverlapEvents(false);

	// TEMPORARY Stage 2 validation camera (issue #47). Plain camera
	// component with a fixed offset behind and above the root, so PIE has a
	// usable view of the moving prototype. Not a chase camera, no spring
	// arm, no smoothing; the Stage 6 architecture will replace this.
	ValidationCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ValidationCamera"));
	ValidationCamera->SetupAttachment(Root);
	// 1.5 m up (eye height) and 3.0 m behind the bicycle along its local
	// -X axis. Yaw reset to camera-forward (+X).
	ValidationCamera->SetRelativeLocation(FVector(-300.0, 0.0, 150.0));
	ValidationCamera->SetRelativeRotation(FRotator::ZeroRotator);
	ValidationCamera->bUsePawnControlRotation = false;
}

void ACyclingPrototypePawn::BeginPlay()
{
	Super::BeginPlay();

	InitializeRide();
	StartDiagnosticTimer();
}

void ACyclingPrototypePawn::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// Remove the default mapping context we added on possess. Best effort:
	// PlayerController / LocalPlayer / subsystem may already be gone during
	// teardown (this should never throw, the helper logs and returns).
	if (DefaultMappingContext)
	{
		if (APlayerController* PC = GetController<APlayerController>())
		{
			if (ULocalPlayer* LP = PC->GetLocalPlayer())
			{
				if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
					ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(LP))
				{
					Subsystem->RemoveMappingContext(DefaultMappingContext);
				}
			}
		}
	}

	// Defensive: ensure Tick is disabled if the Pawn is removed mid-flight.
	SetActorTickEnabled(false);

	// Stop the presentation-only diagnostic timer and clear the on-screen
	// message before destruction.
	StopDiagnosticTimerAndClearMessage();

	Super::EndPlay(EndPlayReason);
}

CyclingSimulation::FCyclingSimulationSessionConfig ACyclingPrototypePawn::MakePrototypeSessionConfig()
{
	// Documented Stage 2 prototype fixture values.
	CyclingSimulation::FCyclingSimulationSessionConfig Config;

	// Rider (SI units).
	Config.Rider.RiderMassKg = 75.0;
	Config.Rider.BikeMassKg = 8.5;
	Config.Rider.CdaM2 = 0.32;
	Config.Rider.RollingResistanceCoefficient = 0.004;
	Config.Rider.DrivetrainEfficiency = 0.97;

	// Environment (SI units).
	Config.Environment.GradeDecimal = 0.0;
	Config.Environment.WindSpeedMps = 0.0;
	Config.Environment.AirDensityKgM3 = 1.225;
	Config.Environment.SurfaceWetness = 0.0;
	Config.Environment.RollingResistanceMultiplier = 1.0;
	Config.Environment.GripMultiplier = 1.0;

	// Rider input controller. Ranges/steps match the existing defaults;
	// initial values match the Stage 2 prototype fixture.
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

bool ACyclingPrototypePawn::TryCacheRouteSpline(USplineComponent*& OutSpline, double& OutLengthCm, FString& OutError) const
{
	OutSpline = nullptr;
	OutLengthCm = 0.0;

	if (!IsValid(RouteActor))
	{
		OutError = TEXT("route reference is not assigned");
		return false;
	}

	// The route Actor must own exactly one USplineComponent. Multiple
	// splines or zero splines are rejected with a useful error.
	TArray<USplineComponent*> Splines;
	RouteActor->GetComponents<USplineComponent>(Splines);

	if (Splines.Num() == 0)
	{
		OutError = FString::Printf(TEXT("route actor '%s' has no USplineComponent"), *RouteActor->GetName());
		return false;
	}
	if (Splines.Num() > 1)
	{
		OutError = FString::Printf(TEXT("route actor '%s' has %d splines; exactly one is required"),
			*RouteActor->GetName(), Splines.Num());
		return false;
	}

	USplineComponent* Spline = Splines[0];
	const float LengthCm = Spline->GetSplineLength();
	if (!FMath::IsFinite(LengthCm) || LengthCm <= 0.0f)
	{
		OutError = FString::Printf(TEXT("route spline on '%s' has invalid length %.6f cm"),
			*RouteActor->GetName(), LengthCm);
		return false;
	}

	OutSpline = Spline;
	OutLengthCm = static_cast<double>(LengthCm);
	return true;
}

bool ACyclingPrototypePawn::TryConfigurePrototypeSession(FString& OutError)
{
	const CyclingSimulation::FCyclingSimulationSessionConfig Config = MakePrototypeSessionConfig();
	return Session.TryConfigure(Config, OutError);
}

bool ACyclingPrototypePawn::TryConfigurePrototypeRouteContext(FString& OutError)
{
	if (!Session.IsConfigured())
	{
		OutError = TEXT("session must be configured before route context");
		return false;
	}

	return RouteContext.TryConfigure(
		Session.GetConfig().Environment,
		CyclingPrototypePawnInternal::Stage3GradeHalfWindowM,
		OutError);
}

void ACyclingPrototypePawn::InitializeRide()
{
	LastError.Reset();
	CachedSpline = nullptr;
	CachedSplineLengthCm = 0.0;

	USplineComponent* Spline = nullptr;
	double LengthCm = 0.0;
	FString Error;
	if (!TryCacheRouteSpline(Spline, LengthCm, Error))
	{
		EnterErrorState(FString::Printf(TEXT("route validation failed: %s"), *Error));
		return;
	}

	CachedSpline = Spline;
	CachedSplineLengthCm = LengthCm;

	if (!TryConfigurePrototypeSession(Error))
	{
		EnterErrorState(FString::Printf(TEXT("session configure failed: %s"), *Error));
		return;
	}

	if (!TryConfigurePrototypeRouteContext(Error))
	{
		EnterErrorState(FString::Printf(TEXT("route context configure failed: %s"), *Error));
		return;
	}

	// A successful initialization starts a fresh logical ride. Only clear
	// prior route-event history after all transactional configuration gates
	// have passed so a failed re-initialization keeps diagnostics intact.
	BoundaryHistory.Reset();

	// Snap presentation to spline distance 0 in Ready state.
	UpdatePresentationFromSession();

	Lifecycle = ECyclingPrototypeLifecycle::Ready;
	SetActorTickEnabled(false);

	UE_LOG(LogCyclingPrototypePawn, Log,
		TEXT("Pawn '%s' initialized: spline length %.2f cm (%.2f m); session configured."),
		*GetName(), CachedSplineLengthCm, CachedSplineLengthCm / 100.0);

	if (bAutoStart)
	{
		StartRide();
	}
}

void ACyclingPrototypePawn::StartRide()
{
	switch (Lifecycle)
	{
	case ECyclingPrototypeLifecycle::Ready:
	case ECyclingPrototypeLifecycle::Stopped:
		Lifecycle = ECyclingPrototypeLifecycle::Running;
		SetActorTickEnabled(true);
		UE_LOG(LogCyclingPrototypePawn, Log, TEXT("Pawn '%s' StartRide -> Running."), *GetName());
		break;
	default:
		// Starting is only valid from Ready or Stopped.
		break;
	}
}

void ACyclingPrototypePawn::StopRide()
{
	if (Lifecycle != ECyclingPrototypeLifecycle::Running)
	{
		return;
	}

	// Stop means pause progression. Session state, accumulator, rider input
	// and visible transform are preserved untouched.
	SetActorTickEnabled(false);
	Lifecycle = ECyclingPrototypeLifecycle::Stopped;
	UE_LOG(LogCyclingPrototypePawn, Log, TEXT("Pawn '%s' StopRide -> Stopped."), *GetName());
}

void ACyclingPrototypePawn::RestartRide()
{
	if (Lifecycle == ECyclingPrototypeLifecycle::Uninitialized)
	{
		EnterErrorState(TEXT("RestartRide called before InitializeRide"));
		return;
	}
	if (Lifecycle == ECyclingPrototypeLifecycle::Error)
	{
		// An Error may have been caused by missing/invalid route data or by
		// an unconfigured session. Re-run the transactional initialization
		// before allowing progression; never enter Running on stale caches.
		InitializeRide();
		if (Lifecycle == ECyclingPrototypeLifecycle::Ready)
		{
			StartRide();
		}
		return;
	}

	// Restart always resets the session, regardless of the prior state.
	Session.Reset();
	BoundaryHistory.Reset();

	// Clear presentation-only transient state.
	LastError.Reset();

	// Snap presentation to spline distance 0 before resuming.
	UpdatePresentationFromSession();

	Lifecycle = ECyclingPrototypeLifecycle::Running;
	SetActorTickEnabled(true);

	UE_LOG(LogCyclingPrototypePawn, Log, TEXT("Pawn '%s' RestartRide -> Running (session reset)."), *GetName());
}

void ACyclingPrototypePawn::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (Lifecycle != ECyclingPrototypeLifecycle::Running)
	{
		// Defensive: Tick is disabled outside Running but if a Tick ever
		// fires (e.g. mid-state-transition), still refuse to advance.
		SetActorTickEnabled(false);
		return;
	}

	FSimulationState NewState;
	double RemainingTimeS = 0.0;
	int32 CompletedSteps = 0;
	TArray<CyclingSimulation::FSimulationBoundaryCrossing> FrameCrossings;
	bool bStoppedAfterStep = false;
	FString Error;

	if (!Session.TryAdvanceWithContext(
		static_cast<double>(DeltaSeconds),
		RouteContext,
		NewState,
		RemainingTimeS,
		CompletedSteps,
		FrameCrossings,
		bStoppedAfterStep,
		Error))
	{
		// Session refused the frame: keep last valid authoritative state,
		// keep last valid visible transform, transition to Error, disable
		// Tick. Do NOT auto-reset.
		EnterErrorState(FString::Printf(TEXT("TryAdvanceWithContext failed: %s"), *Error));
		return;
	}

	BoundaryHistory.Append(FrameCrossings);
	for (const CyclingSimulation::FSimulationBoundaryCrossing& Crossing : FrameCrossings)
	{
		UE_LOG(LogCyclingPrototypePawn, Log,
			TEXT("Pawn '%s' route crossing '%s' kind=%d boundary=%.3f m step_end=%.3f m elapsed=%.3f s."),
			*GetName(),
			*Crossing.Id,
			static_cast<int32>(Crossing.Kind),
			Crossing.BoundaryDistanceM,
			Crossing.PostStepState.DistanceM,
			Crossing.PostStepState.ElapsedTimeS);
	}

	// Remember the latest fixed-step counter for the next overlay
	// refresh. We only set it on success so that stale counter values
	// are not surfaced when TryAdvanceWithContext fails.
	LastCompletedSteps = CompletedSteps;

	// Presentation is always derived from the authoritative state. The spline
	// may clamp visually at its end, but it never decides route completion.
	UpdatePresentationFromSession();

	const CyclingSimulation::FSimulationBoundaryCrossing* FinishCrossing =
		FrameCrossings.FindByPredicate(
			[](const CyclingSimulation::FSimulationBoundaryCrossing& Crossing)
			{
				return Crossing.Kind == CyclingSimulation::ESimulationBoundaryKind::Finish;
			});

	if (bStoppedAfterStep || FinishCrossing != nullptr)
	{
		if (!bStoppedAfterStep || FinishCrossing == nullptr)
		{
			EnterErrorState(TEXT("route context terminal-stop contract mismatch"));
			return;
		}

		Lifecycle = ECyclingPrototypeLifecycle::Finished;
		SetActorTickEnabled(false);
		UE_LOG(LogCyclingPrototypePawn, Log,
			TEXT("Pawn '%s' reached deterministic Finish '%s' at authoritative distance %.6f m (boundary %.2f m)."),
			*GetName(),
			*FinishCrossing->Id,
			NewState.DistanceM,
			FinishCrossing->BoundaryDistanceM);
		return;
	}
}

void ACyclingPrototypePawn::UpdatePresentationFromSession()
{
	if (!IsValid(CachedSpline))
	{
		return;
	}

	const FSimulationState& State = Session.GetSimulationState();

	// Only authorised unit conversion: metres -> Unreal centimetres for the
	// spline query. Authoritative state is never modified in centimetres.
	const double DistanceCmRaw = State.DistanceM * CyclingPrototypePawnInternal::MetresToCentimetres;
	const double DistanceCm = FMath::Clamp(DistanceCmRaw, 0.0, CachedSplineLengthCm);

	const FVector SplineLocation = CachedSpline->GetLocationAtDistanceAlongSpline(
		static_cast<float>(DistanceCm), ESplineCoordinateSpace::World);
	const FRotator SplineRotation = CachedSpline->GetRotationAtDistanceAlongSpline(
		static_cast<float>(DistanceCm), ESplineCoordinateSpace::World);

	// Root Actor transform is the spline pose. Mesh relative transform
	// supplies any visual height/pivot offset; the root itself is not
	// adjusted in Z by code.
	SetActorLocationAndRotation(SplineLocation, SplineRotation);
}

void ACyclingPrototypePawn::EnterErrorState(const FString& Message)
{
	LastError = Message;
	Lifecycle = ECyclingPrototypeLifecycle::Error;
	SetActorTickEnabled(false);
	UE_LOG(LogCyclingPrototypePawn, Warning, TEXT("Pawn '%s' Error: %s"), *GetName(), *Message);
}

bool ACyclingPrototypePawn::TeleportForProofCapture(double DistanceM)
{
	if (!IsValid(CachedSpline))
	{
		UE_LOG(LogCyclingPrototypePawn, Warning,
			TEXT("TeleportForProofCapture: no cached spline; refusing."));
		return false;
	}
	if (!FMath::IsFinite(DistanceM))
	{
		UE_LOG(LogCyclingPrototypePawn, Warning,
			TEXT("TeleportForProofCapture: non-finite DistanceM; refusing."));
		return false;
	}
	if (CachedSplineLengthCm <= 0.0)
	{
		UE_LOG(LogCyclingPrototypePawn, Warning,
			TEXT("TeleportForProofCapture: spline length non-positive; refusing."));
		return false;
	}

	// Only authorised unit conversion: metres -> Unreal centimetres for the
	// spline query. Authoritative state is never rewritten.
	const double RawCm = DistanceM * CyclingPrototypePawnInternal::MetresToCentimetres;
	const double DistanceCm = FMath::Clamp(RawCm, 0.0, CachedSplineLengthCm);

	const FVector SplineLocation = CachedSpline->GetLocationAtDistanceAlongSpline(
		static_cast<float>(DistanceCm), ESplineCoordinateSpace::World);
	const FRotator SplineRotation = CachedSpline->GetRotationAtDistanceAlongSpline(
		static_cast<float>(DistanceCm), ESplineCoordinateSpace::World);

	SetActorLocationAndRotation(
		SplineLocation,
		SplineRotation,
		/*bSweep=*/false,
		/*OutSweepHitResult=*/nullptr,
		ETeleportType::TeleportPhysics);

	const double ActualDistanceM =
		static_cast<double>(DistanceCm) / CyclingPrototypePawnInternal::MetresToCentimetres;

	UE_LOG(LogCyclingPrototypePawn, Display,
		TEXT("TeleportForProofCapture: requested=%.3f m actual=%.3f m spline_cm=%.3f session_distance_m=%.6f lifecycle=%d"),
		DistanceM,
		ActualDistanceM,
		CachedSplineLengthCm,
		Session.GetSimulationState().DistanceM,
		static_cast<int32>(Lifecycle));

	return true;
}

// ===========================================================
// Stage 2 Enhanced Input (issue #47).
//
// Bindings use ETriggerEvent::Started so that one key press performs
// exactly one session mutation, regardless of how many render frames
// elapse while the key is held down. There is no key-repeat logic;
// holding a key must NOT advance power or cadence faster than tapping
// it. The handlers below delegate directly to the existing
// FCyclingSimulationSession step/increase/decrease API and never
// duplicate input state.
// ===========================================================

FCyclingInputSnapshot ACyclingPrototypePawn::CaptureCurrentInputSnapshot() const
{
	return CyclingDiagnostics::CaptureInputSnapshot(
		CyclingDiagnostics::MapLifecycle(static_cast<int32>(Lifecycle)),
		Session.GetRiderInput().PowerW,
		Session.GetRiderInput().CadenceRpm,
		Session.GetSimulationState());
}

void ACyclingPrototypePawn::SetDiagnosticOverlayEnabled(bool bEnabled)
{
	bEnableDiagnosticOverlay = bEnabled;
	if (!bEnabled)
	{
		StopDiagnosticTimerAndClearMessage();
	}
	else
	{
		StartDiagnosticTimer();
		RefreshDiagnosticOverlay();
	}
}

void ACyclingPrototypePawn::SetGuidedAcceptanceEnabled(bool bEnabled)
{
	bEnableGuidedAcceptance = bEnabled;
	if (!bEnabled)
	{
		// Wipe the observer state so a later re-enable starts fresh.
		GuidedAcceptance = FCyclingGuidedAcceptanceState();
	}
}

void ACyclingPrototypePawn::StartDiagnosticTimer()
{
	if (!bEnableDiagnosticOverlay)
	{
		return;
	}
	if (UWorld* World = GetWorld())
	{
		// Avoid stacking duplicate timers if BeginPlay is invoked twice
		// (e.g. via the editor's re-instance flow).
		World->GetTimerManager().ClearTimer(DiagnosticTimerHandle);
		World->GetTimerManager().SetTimer(
			DiagnosticTimerHandle,
			FTimerDelegate::CreateUObject(this, &ACyclingPrototypePawn::RefreshDiagnosticOverlay),
			CyclingPrototypePawnInternal::DiagnosticRefreshIntervalS,
			/*bLoop=*/true);
	}
}

void ACyclingPrototypePawn::StopDiagnosticTimerAndClearMessage()
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(DiagnosticTimerHandle);
	}
	ClearOverlayMessage();
}

void ACyclingPrototypePawn::ClearOverlayMessage()
{
	if (GEngine)
	{
		// A negative TimeToDisplay + stable key removes the entry.
		// The key is a non-INDEX_NONE unique constant; per UE docs
		// this is the mechanism that prevents duplicate message spam.
		GEngine->RemoveOnScreenDebugMessage(static_cast<uint64>(YACS_DIAGNOSTIC_OVERLAY_KEY));
	}
}

void ACyclingPrototypePawn::RefreshDiagnosticOverlay()
{
	if (!bEnableDiagnosticOverlay)
	{
		ClearOverlayMessage();
		return;
	}
	if (!GEngine)
	{
		return;
	}

	const double PowerStep = Session.IsConfigured()
		? Session.GetConfig().RiderInput.PowerStepW
		: 10.0;
	const double CadenceStep = Session.IsConfigured()
		? Session.GetConfig().RiderInput.CadenceStepRpm
		: 5.0;

	const FCyclingInputSnapshot CurrentSnap = CaptureCurrentInputSnapshot();

	// Stop-stability observer. While the Pawn is in Stopped we tick the
	// observer so the overlay can surface PASS/FAIL after at least one
	// full refresh interval. The observer is pure and never re-enables
	// the simulation Tick.
	if (Lifecycle == ECyclingPrototypeLifecycle::Stopped
		|| Lifecycle == ECyclingPrototypeLifecycle::Error
		|| Lifecycle == ECyclingPrototypeLifecycle::Finished)
	{
		// Already stopped; observer still receives ticks.
	}
	if (bEnableGuidedAcceptance)
	{
		GuidedAcceptance = CyclingDiagnostics::ObserveStopStability(
			GuidedAcceptance, CurrentSnap);
	}

	// Always advance the guided acceptance observer when the lifecycle
	// reaches Finished (not via a command, but via the runtime state
	// itself). The observer otherwise only advances on user commands.
	if (bEnableGuidedAcceptance
		&& Lifecycle == ECyclingPrototypeLifecycle::Finished
		&& GuidedAcceptance.CurrentStep != ECyclingGuidedAcceptanceStep::Finished)
	{
		FCyclingGuidedAcceptanceState Next = GuidedAcceptance;
		Next.CurrentStep = ECyclingGuidedAcceptanceStep::Finished;
		Next.StepStatus = TEXT("PASS");
		Next.StepNote = TEXT("Route end reached");
		GuidedAcceptance = Next;
	}

	const double RouteLengthM = CachedSplineLengthCm
		/ CyclingPrototypePawnInternal::MetresToCentimetres;
	const int32 CompletedStepsShown = (LastCompletedSteps < 0)
		? 0 : LastCompletedSteps;

	const FCyclingDiagnosticsSnapshot Snapshot =
		CyclingDiagnostics::MakeSnapshot(
			CyclingDiagnostics::MapLifecycle(static_cast<int32>(Lifecycle)),
			CurrentSnap.PowerW,
			CurrentSnap.CadenceRpm,
			Session.GetSimulationState(),
			CompletedStepsShown,
			Session.GetAccumulatedTimeS(),
			RouteLengthM,
			LastError,
			PowerStep,
			CadenceStep,
			LastInputFeedback);

	const FString OverlayText = CyclingDiagnostics::FormatOverlay(
		Snapshot, GuidedAcceptance, bEnableGuidedAcceptance);

	// Single stable keyed message. TimeToDisplay slightly larger than
	// the refresh interval so a single missed frame never produces a
	// flicker. Key is the fixed non-INDEX_NONE YACS_DIAGNOSTIC_OVERLAY_KEY
	// so this entry is replaced rather than appended.
	GEngine->AddOnScreenDebugMessage(
		static_cast<uint64>(YACS_DIAGNOSTIC_OVERLAY_KEY),
		CyclingPrototypePawnInternal::DiagnosticRefreshIntervalS * 1.5f + 0.1f,
		FColor::Yellow,
		OverlayText);
}

void ACyclingPrototypePawn::RegisterDefaultMappingContext()
{
	if (!DefaultMappingContext)
	{
		// The Pawn instance has no mapping context assigned. This is a
		// legitimate configuration (e.g. when input is driven from tests
		// without a Mapping Context asset) and not an error. Stay quiet
		// to keep test logs clean.
		return;
	}

	APlayerController* PC = GetController<APlayerController>();
	if (!PC)
	{
		return;
	}

	ULocalPlayer* LP = PC->GetLocalPlayer();
	if (!LP)
	{
		return;
	}

	UEnhancedInputLocalPlayerSubsystem* Subsystem =
		ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(LP);
	if (!Subsystem)
	{
		UE_LOG(LogCyclingPrototypePawn, Warning,
			TEXT("Pawn '%s' could not resolve UEnhancedInputLocalPlayerSubsystem on possess."),
			*GetName());
		return;
	}

	Subsystem->AddMappingContext(DefaultMappingContext, /*Priority=*/0);
}

void ACyclingPrototypePawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	// Step 1: register the mapping context with the local player. Done
	// here because SetupPlayerInputComponent is the canonical place
	// where possession guarantees a PlayerController, a LocalPlayer and
	// an Enhanced Input subsystem exist.
	RegisterDefaultMappingContext();

	// Step 2: bind actions to the existing one-shot handlers.
	UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!EIC)
	{
		UE_LOG(LogCyclingPrototypePawn, Warning,
			TEXT("Pawn '%s' PlayerInputComponent is not a UEnhancedInputComponent; no bindings registered."),
			*GetName());
		return;
	}

	// ETriggerEvent::Started fires once per key press, not per render
	// frame. Holding a key does not multiply mutations; binding to
	// Triggered would re-introduce frame-rate dependent power /
	// cadence increments and contradict the one-event-one-step
	// invariant.
	if (PowerIncreaseAction)
	{
		EIC->BindAction(PowerIncreaseAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandlePowerIncrease);
	}
	if (PowerDecreaseAction)
	{
		EIC->BindAction(PowerDecreaseAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandlePowerDecrease);
	}
	if (CadenceIncreaseAction)
	{
		EIC->BindAction(CadenceIncreaseAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandleCadenceIncrease);
	}
	if (CadenceDecreaseAction)
	{
		EIC->BindAction(CadenceDecreaseAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandleCadenceDecrease);
	}
	if (StartRideAction)
	{
		EIC->BindAction(StartRideAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandleStartRide);
	}
	if (StopRideAction)
	{
		EIC->BindAction(StopRideAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandleStopRide);
	}
	if (RestartRideAction)
	{
		EIC->BindAction(RestartRideAction, ETriggerEvent::Started, this, &ACyclingPrototypePawn::HandleRestartRide);
	}
}

namespace CyclingPrototypePawnInputInternal
{
	// Reserved for future input adapters that need a single-step
	// logging fallback. The current Stage 2 prototype routes every
	// command through ACyclingPrototypePawn::RecordCommandFeedback,
	// which logs rejections through the session itself.
}

void ACyclingPrototypePawn::HandlePowerIncrease(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::PowerIncrease,
		[this](FString& Err) { return Session.TryIncreasePower(Err); });
}

void ACyclingPrototypePawn::HandlePowerDecrease(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::PowerDecrease,
		[this](FString& Err) { return Session.TryDecreasePower(Err); });
}

void ACyclingPrototypePawn::HandleCadenceIncrease(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::CadenceIncrease,
		[this](FString& Err) { return Session.TryIncreaseCadence(Err); });
}

void ACyclingPrototypePawn::HandleCadenceDecrease(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::CadenceDecrease,
		[this](FString& Err) { return Session.TryDecreaseCadence(Err); });
}

void ACyclingPrototypePawn::HandleStartRide(const FInputActionValue& /*Value*/)
{
	// Stage 2 contract: StartRide is only valid from Ready or Stopped.
	// Ready/Stopped -> Running; Finished/Error/Uninitialized -> no-op.
	// The existing StartRide implementation enforces this with a
	// switch on Lifecycle. Calling it from Finished is intentionally a
	// no-op so the user must press Restart to recover from overshoot.
	//
	// The actual StartRide call is performed inside the
	// RecordCommandFeedback closure so the BEFORE/AFTER snapshot pair
	// is captured around it. The closure returns true iff the
	// lifecycle actually transitioned.
	RecordCommandFeedback(ECyclingInputCommand::StartOrResume,
		[this](FString& Err) -> bool
		{
			const ECyclingPrototypeLifecycle BeforeLifecycle = Lifecycle;
			StartRide();
			Err.Reset();
			if (BeforeLifecycle == ECyclingPrototypeLifecycle::Finished
				&& Lifecycle == ECyclingPrototypeLifecycle::Finished)
			{
				UE_LOG(LogCyclingPrototypePawn, Log,
					TEXT("Pawn '%s' StartRide ignored in Finished state; RestartRide is required."),
					*GetName());
			}
			return Lifecycle != BeforeLifecycle
				&& Lifecycle == ECyclingPrototypeLifecycle::Running;
		});
}

void ACyclingPrototypePawn::HandleStopRide(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::Stop,
		[this](FString& Err) -> bool
		{
			const ECyclingPrototypeLifecycle Before = Lifecycle;
			StopRide();
			Err.Reset();
			return Lifecycle != Before && Lifecycle == ECyclingPrototypeLifecycle::Stopped;
		});
}

void ACyclingPrototypePawn::HandleRestartRide(const FInputActionValue& /*Value*/)
{
	RecordCommandFeedback(ECyclingInputCommand::Restart,
		[this](FString& Err) -> bool
		{
			const ECyclingPrototypeLifecycle Before = Lifecycle;
			RestartRide();
			Err.Reset();
			return Lifecycle == ECyclingPrototypeLifecycle::Running;
		});
}
