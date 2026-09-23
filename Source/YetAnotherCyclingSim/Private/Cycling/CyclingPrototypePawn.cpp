// Copyright YetAnotherCyclingSim. All Rights Reserved.

#include "Cycling/CyclingPrototypePawn.h"

#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingPrototypePawn, Log, All);

namespace CyclingPrototypePawnInternal
{
	// Meters -> Unreal centimetres. Used only at the presentation boundary.
	constexpr double MetresToCentimetres = 100.0;
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
	FString Error;

	if (!Session.TryAdvance(static_cast<double>(DeltaSeconds), NewState, RemainingTimeS, CompletedSteps, Error))
	{
		// Session refused the frame: keep last valid authoritative state,
		// keep last valid visible transform, transition to Error, disable
		// Tick. Do NOT auto-reset.
		EnterErrorState(FString::Printf(TEXT("TryAdvance failed: %s"), *Error));
		return;
	}

	// Successful advance. Update presentation only from authoritative
	// NewState.DistanceM. Check Finished condition (route end reached or
	// exceeded).
	if (CachedSplineLengthCm > 0.0 &&
		NewState.DistanceM * CyclingPrototypePawnInternal::MetresToCentimetres >= CachedSplineLengthCm)
	{
		// Clamp the visible presentation to the spline end without
		// rewriting the authoritative DistanceM (Stage 2 deliberately
		// preserves a small fixed-step overshoot).
		UpdatePresentationFromSession();
		Lifecycle = ECyclingPrototypeLifecycle::Finished;
		SetActorTickEnabled(false);
		UE_LOG(LogCyclingPrototypePawn, Log,
			TEXT("Pawn '%s' reached Finished at authoritative distance %.6f m (route end %.2f m)."),
			*GetName(), NewState.DistanceM, CachedSplineLengthCm / 100.0);
		return;
	}

	UpdatePresentationFromSession();
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
	// Common delegate helper: try to apply a step operation on the
	// session. Logs a single useful warning on failure and never mutates
	// any state on failure (the session / controller is transactional).
	template <typename StepOp>
	void DispatchStep(
		ACyclingPrototypePawn* Pawn,
		const TCHAR* OpName,
		StepOp Op)
	{
		if (!Pawn)
		{
			return;
		}
		FString Error;
		if (!Op(Error))
		{
			UE_LOG(LogCyclingPrototypePawn, Warning,
				TEXT("Pawn '%s' input '%s' rejected: %s"),
				*Pawn->GetName(), OpName, *Error);
		}
	}
}

void ACyclingPrototypePawn::HandlePowerIncrease(const FInputActionValue& /*Value*/)
{
	CyclingPrototypePawnInputInternal::DispatchStep(this, TEXT("PowerIncrease"),
		[this](FString& Err) { return Session.TryIncreasePower(Err); });
}

void ACyclingPrototypePawn::HandlePowerDecrease(const FInputActionValue& /*Value*/)
{
	CyclingPrototypePawnInputInternal::DispatchStep(this, TEXT("PowerDecrease"),
		[this](FString& Err) { return Session.TryDecreasePower(Err); });
}

void ACyclingPrototypePawn::HandleCadenceIncrease(const FInputActionValue& /*Value*/)
{
	CyclingPrototypePawnInputInternal::DispatchStep(this, TEXT("CadenceIncrease"),
		[this](FString& Err) { return Session.TryIncreaseCadence(Err); });
}

void ACyclingPrototypePawn::HandleCadenceDecrease(const FInputActionValue& /*Value*/)
{
	CyclingPrototypePawnInputInternal::DispatchStep(this, TEXT("CadenceDecrease"),
		[this](FString& Err) { return Session.TryDecreaseCadence(Err); });
}

void ACyclingPrototypePawn::HandleStartRide(const FInputActionValue& /*Value*/)
{
	// Stage 2 contract: StartRide is only valid from Ready or Stopped.
	// Ready/Stopped -> Running; Finished/Error/Uninitialized -> no-op.
	// The existing StartRide implementation enforces this with a
	// switch on Lifecycle. Calling it from Finished is intentionally a
	// no-op so the user must press Restart to recover from overshoot.
	const ECyclingPrototypeLifecycle Before = Lifecycle;
	StartRide();
	if (Before == ECyclingPrototypeLifecycle::Finished &&
		Lifecycle == ECyclingPrototypeLifecycle::Finished)
	{
		UE_LOG(LogCyclingPrototypePawn, Log,
			TEXT("Pawn '%s' StartRide ignored in Finished state; RestartRide is required."),
			*GetName());
	}
}

void ACyclingPrototypePawn::HandleStopRide(const FInputActionValue& /*Value*/)
{
	StopRide();
}

void ACyclingPrototypePawn::HandleRestartRide(const FInputActionValue& /*Value*/)
{
	RestartRide();
}
