// Copyright YetAnotherCyclingSim. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "Engine/EngineTypes.h"
#include "Cycling/CyclingSimulationSession.h"
#include "Cycling/AlpineJourneyRuntimeContext.h"
#include "Cycling/CyclingDiagnostics.h"
#include "CyclingPrototypePawn.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class AActor;
class USplineComponent;
class UCameraComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

// Authoritative runtime lifecycle of the prototype Pawn.
//
// The runtime lifecycle is explicit and is the sole authority over whether
// the Pawn's Tick is enabled, whether TryAdvance is being called, and whether
// the visible transform is being updated from the authoritative state.
//
// Transitions:
//
//   Uninitialized -> Ready   (valid route spline + valid session configure)
//   Ready         -> Running (StartRide)
//   Running       -> Stopped (StopRide)
//   Running       -> Finished (authoritative DistanceM reaches route end)
//   Running       -> Error   (TryAdvance or runtime validation failure)
//   Stopped       -> Running (StartRide resumes the same session)
//   Finished      -> Running (RestartRide)
//   Error         -> Running (RestartRide revalidates route/configuration)
//   *             -> Error   (route/spline validation failure on construction)
UENUM(BlueprintType)
enum class ECyclingPrototypeLifecycle : uint8
{
	Uninitialized UMETA(DisplayName = "Uninitialized"),
	Ready         UMETA(DisplayName = "Ready"),
	Running       UMETA(DisplayName = "Running"),
	Stopped       UMETA(DisplayName = "Stopped"),
	Finished      UMETA(DisplayName = "Finished"),
	Error         UMETA(DisplayName = "Error"),
};

/**
 * Stage 3 runtime Pawn.
 *
 * The Pawn is the single Unreal-runtime owner of one FCyclingSimulationSession.
 * It is responsible for:
 *
 *  - validating and caching the route spline reference (BeginPlay);
 *  - configuring the session with the prototype fixture values;
 *  - forwarding per-render-frame DeltaSeconds to Session.TryAdvanceWithContext
 *    while Running (Tick is the only render-frame bridge to the deterministic
 *    fixed-step runner and route context);
 *  - reading the authoritative FSimulationState and converting it to a
 *    spline transform in Unreal centimetres for presentation only;
 *  - enforcing the explicit lifecycle (Ready / Running / Stopped /
 *    Finished / Error).
 *
 * Architectural invariants:
 *
 *  1. The session is the sole owner of simulation truth. The Pawn never
 *     computes physics, never integrates distance, never reads its own Actor
 *     velocity to derive movement.
 *  2. The Actor transform is an output only. It is recomputed every Tick
 *     from authoritative Session.GetSimulationState().DistanceM.
 *  3. The only unit conversion performed by the Pawn is
 *        DistanceM * 100.0  (metres -> Unreal centimetres)
 *     which is used solely for the spline query. The authoritative state is
 *     never modified in centimetres.
 *  4. Tick is enabled only in Running; in any other lifecycle state Tick is
 *     disabled and TryAdvance is not called.
 *  5. There is no second fixed-step accumulator. The Pawn forwards
 *     DeltaSeconds directly to the existing FFixedStepSimulationRunner.
 *
 * The Pawn intentionally exposes StartRide / StopRide / RestartRide per the
 * Stage 2 runtime contract. Keyboard binding and diagnostic HUD wiring are
 * out of scope for this issue and are added by follow-up work.
 */
UCLASS()
class YETANOTHERCYCLINGSIM_API ACyclingPrototypePawn : public APawn
{
	GENERATED_BODY()

public:
	ACyclingPrototypePawn();

	// --- Editor-assigned configuration ---

	// Route Actor that owns exactly one USplineComponent. The spline is used
	// exclusively for presentation; the spline length in centimetres defines
	// the visual route end. The Pawn does not derive grade from the spline.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cycling|Route")
	TObjectPtr<AActor> RouteActor;

	// Static mesh component used as the temporary visual representation of
	// the bicycle. The mesh asset itself is assigned on the instance (Basic
	// Cube from /Engine/BasicShapes/Cube) and is intentionally not
	// hard-coded in C++.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cycling|Components")
	TObjectPtr<UStaticMeshComponent> BicycleMesh;

	// When true, BeginPlay calls StartRide automatically after a successful
	// route validation and session configure. Slice B of Stage 2 (interactive
	// keyboard input) keeps this disabled on L_CyclingTest; the placed Pawn
	// is possessed by Player 0 and waits for an explicit Start input.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cycling|Runtime")
	bool bAutoStart = false;

	// --- Stage 2 Enhanced Input (issue #47) ---

	// Single default mapping context applied to Player 0 on possession.
	// Contains the keyboard bindings: Up/Down (power), Left/Right (cadence),
	// Space (Start), S (Stop), R (Restart). All step actions use the
	// ETriggerEvent::Started trigger so that one key press performs exactly
	// one session mutation, regardless of render-frame cadence.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> PowerIncreaseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> PowerDecreaseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> CadenceIncreaseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> CadenceDecreaseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> StartRideAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> StopRideAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Input")
	TObjectPtr<UInputAction> RestartRideAction;

	// --- Stage 2 validation camera (temporary) ---

	// TEMPORARY Stage 2 validation camera. Plain UCameraComponent with a
	// fixed offset behind and above the root, used only to give PIE a
	// usable view of the moving prototype. To be replaced by the Stage 6
	// camera architecture; do not extend this component with smoothing,
	// spring arms, or chase logic.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Cycling|Components")
	TObjectPtr<UCameraComponent> ValidationCamera;

	// --- Stage 2 diagnostic overlay (issue #48) ---

	// When true, a 4 Hz presentation-only timer refreshes one stable
	// keyed GEngine->AddOnScreenDebugMessage entry showing authoritative
	// runtime/input diagnostics, the controls legend, the last input
	// feedback and the guided manual-acceptance prompt. The overlay is
	// intentionally a development/test harness and is not the final
	// Stage 5 HUD. Setting this to false stops the timer and clears
	// the on-screen message without affecting the simulation.
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Diagnostics")
	bool bEnableDiagnosticOverlay = true;

	// When true, the overlay additionally drives a presentation-only
	// 7-step guided manual-acceptance flow. The flow OBSERVES normal
	// user input and never issues gameplay commands on behalf of the
	// tester (issue #48 rule #9).
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Cycling|Diagnostics")
	bool bEnableGuidedAcceptance = true;

	// --- Lifecycle API ---

	// Validates the route spline and configures the session with the
	// prototype fixture values. Called automatically from BeginPlay.
	// On success the Pawn is in Ready and the visible transform is set to
	// the spline-distance-0 pose. On failure the Pawn is in Error and Tick
	// is disabled.
	UFUNCTION(BlueprintCallable, Category = "Cycling|Runtime")
	void InitializeRide();

	// Transitions Ready or Stopped -> Running. No-op in other states.
	// If the Pawn is in Stopped, this resumes the existing session without
	// resetting state.
	UFUNCTION(BlueprintCallable, Category = "Cycling|Runtime")
	void StartRide();

	// Transitions Running -> Stopped. Tick is disabled. Session state,
	// accumulator, rider input and visible transform are preserved.
	UFUNCTION(BlueprintCallable, Category = "Cycling|Runtime")
	void StopRide();

	// Transitions Stopped, Finished or Error -> Running after a full
	// session Reset() and a presentation re-snap to spline distance 0.
	// From Error, route validation and session configuration are retried
	// before Running can be entered.
	UFUNCTION(BlueprintCallable, Category = "Cycling|Runtime")
	void RestartRide();

	// --- Queries ---

	UFUNCTION(BlueprintPure, Category = "Cycling|Runtime")
	ECyclingPrototypeLifecycle GetLifecycle() const { return Lifecycle; }

	// Last useful diagnostic error (empty when the runtime is healthy).
	UFUNCTION(BlueprintPure, Category = "Cycling|Runtime")
	const FString& GetLastError() const { return LastError; }

	// Read-only view of the authoritative simulation state. Actor transform
	// is derived from this struct; never the other way around.
	const FSimulationState& GetAuthoritativeState() const
	{
		return Session.GetSimulationState();
	}

	// Read-only view of the deterministic cycling session owned by this Pawn.
	const CyclingSimulation::FCyclingSimulationSession& GetSession() const
	{
		return Session;
	}

	// Ordered fixed-step route boundary events emitted during the current ride.
	// This is event history for diagnostics/presentation only; authoritative
	// route progress remains Session.GetSimulationState().DistanceM.
	const TArray<CyclingSimulation::FSimulationBoundaryCrossing>& GetBoundaryHistory() const
	{
		return BoundaryHistory;
	}

	// Mutable view of the deterministic cycling session owned by this Pawn.
	// Exposed so tests and follow-up input adapters can call input-mutation
	// operations (e.g. TrySetPowerW). Runtime presentation code does not
	// need this accessor; it reads authoritative state via the const
	// overload above.
	CyclingSimulation::FCyclingSimulationSession& GetMutableSession()
	{
		return Session;
	}

	// Cached spline length in Unreal centimetres. Returned by this method
	// only for tests/diagnostics. Returns 0.0 when no spline is cached.
	double GetCachedSplineLengthCm() const { return CachedSplineLengthCm; }

	// --- Stage 2 diagnostic overlay (issue #48) ---

	// Read-only access to the latest authoritative input snapshot
	// (presentation-only mirror). Tests use this to assert the
	// before/after behaviour without driving the timer.
	const FCyclingInputSnapshot& GetLastInputSnapshot() const { return LastInputSnapshot; }

	// Read-only access to the latest presentation-only feedback record.
	const FCyclingLastInputFeedback& GetLastInputFeedback() const { return LastInputFeedback; }

	// Read-only access to the current guided-acceptance observer
	// state.
	const FCyclingGuidedAcceptanceState& GetGuidedAcceptanceState() const { return GuidedAcceptance; }

	// Enables or disables the diagnostic overlay at runtime. When
	// disabled, the timer is stopped and the on-screen message is
	// cleared; the simulation is unaffected.
	void SetDiagnosticOverlayEnabled(bool bEnabled);

	// Enables or disables the guided-acceptance observer at runtime.
	// When disabled, the overlay continues to refresh but the
	// "manual acceptance" block is omitted.
	void SetGuidedAcceptanceEnabled(bool bEnabled);

	// --- Stage 3E visual environment proof fixture ---

	// Stage 3E Visual Environment Proof-only helper.
	//
	// Sets the Pawn's visible Actor transform to the spline pose at
	// DistanceM WITHOUT mutating the authoritative Session state or the
	// route event history. Clamps DistanceM to [0, CachedSplineLengthCm /
	// 100.0]. This is a presentation-only fixture used exclusively by the
	// CyclingRuntime.Stage3VisualEnvironmentProof automation test to take
	// route-attributable screenshots; the next Tick (if enabled) will
	// overwrite the visible transform with the authoritative pose.
	//
	// Returns true and emits a "TeleportForProofCapture" log line when a
	// finite spline pose was sampled and the Actor transform was updated.
	// Returns false (and leaves state untouched) when no spline is cached,
	// the spline length is non-positive, or DistanceM is non-finite.
	bool TeleportForProofCapture(double DistanceM);

protected:
	// APawn / AActor overrides.
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	// Stage 2 Enhanced Input binding (issue #47). One key press ->
	// one session mutation. Bindings use ETriggerEvent::Started so that
	// frame-rate independent input is preserved (a pressed key fires once).
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

public:

	// --- Stage 2 Enhanced Input handlers (issue #47) ---
	//
	// Each handler delegates directly to the existing FCyclingSimulationSession
	// API. They never compute their own power/cadence accumulator or
	// duplicate input state. On error (e.g. unconfigured session, controller
	// refused) they emit one useful log line and leave the session state
	// untouched. The handlers are public so that focused automation tests
	// can invoke them directly without an Enhanced Input subsystem.

	// One-shot event handlers (bound with ETriggerEvent::Started).
	void HandlePowerIncrease(const FInputActionValue& Value);
	void HandlePowerDecrease(const FInputActionValue& Value);
	void HandleCadenceIncrease(const FInputActionValue& Value);
	void HandleCadenceDecrease(const FInputActionValue& Value);
	void HandleStartRide(const FInputActionValue& Value);
	void HandleStopRide(const FInputActionValue& Value);
	void HandleRestartRide(const FInputActionValue& Value);

	// Registers the default mapping context with the local player
	// subsystem. Called once on possess. Logs and returns early when the
	// LocalPlayer or subsystem cannot be resolved.
	void RegisterDefaultMappingContext();

public:
	// Runtime Tick is intentionally public so that tests and any future
	// automation harness can drive frames deterministically. Runtime Tick
	// policy still applies: Tick is enabled only while Lifecycle == Running.
	virtual void Tick(float DeltaSeconds) override;

	// --- Internal helpers ---

	// Validates RouteActor and caches the spline + length. Returns true and
	// fills OutSpline / OutLengthCm on success. On failure returns false and
	// fills OutError with a useful message.
	bool TryCacheRouteSpline(USplineComponent*& OutSpline, double& OutLengthCm, FString& OutError) const;

	// Configures the deterministic session with the documented prototype
	// fixture. Returns true on success.
	bool TryConfigurePrototypeSession(FString& OutError);

	// Configures the Stage 3 Alpine geometry + marker context consumed by the
	// fixed-step runner. The context is deterministic and rendering-independent.
	bool TryConfigurePrototypeRouteContext(FString& OutError);

	// Recomputes the visible Actor transform from authoritative
	// Session.GetSimulationState().DistanceM. The presentation query clamps
	// the spline distance to [0, CachedSplineLengthCm]; the authoritative
	// distance is never rewritten.
	void UpdatePresentationFromSession();

	// Centralised error reporter. Sets Lifecycle to Error, disables Tick,
	// stores the message in LastError and emits one UE_LOG warning.
	void EnterErrorState(const FString& Message);

	// Builds the prototype rider / environment / rider-input fixture used by
	// the Stage 2 straight prototype. Exposed via static methods so tests can
	// exercise the same values without instantiating a Pawn.
	static CyclingSimulation::FCyclingSimulationSessionConfig MakePrototypeSessionConfig();

private:
	// Deterministic cycling session owned by this Pawn. The Pawn forwards
	// frame deltas and presentation queries to this object.
	CyclingSimulation::FCyclingSimulationSession Session;

	// Stage 3 route-aware fixed-step context. It derives grade from the
	// deterministic Alpine geometry and emits start/sector/finish crossings.
	CyclingSimulation::FAlpineJourneySimulationStepContextProvider RouteContext;

	// Per-ride event history. Cleared by successful initialization/restart;
	// pause/resume preserves it so already-crossed markers are not replayed.
	TArray<CyclingSimulation::FSimulationBoundaryCrossing> BoundaryHistory;

	// Cached spline reference. Set on a successful BeginPlay validation and
	// never re-queried in Tick.
	UPROPERTY(Transient)
	TObjectPtr<USplineComponent> CachedSpline;

	// Cached spline length in Unreal centimetres. > 0 and finite after a
	// successful validation. 0 otherwise.
	double CachedSplineLengthCm = 0.0;

	// Authoritative lifecycle state.
	ECyclingPrototypeLifecycle Lifecycle = ECyclingPrototypeLifecycle::Uninitialized;

	// Last useful diagnostic error (empty when healthy).
	UPROPERTY(Transient)
	FString LastError;

	// --- Stage 2 diagnostic overlay state (issue #48) ---

	// 4 Hz presentation-only timer that refreshes the on-screen
	// overlay message. Timer is started in BeginPlay and cleared in
	// EndPlay. It does NOT call TryAdvance; it only reads
	// already-computed state.
	FTimerHandle DiagnosticTimerHandle;

	// Latest fixed-step counter (set by Tick). Used by the overlay
	// to display "FIXED STEPS N". -1 before the first Tick.
	int32 LastCompletedSteps = -1;

	// Latest presentation-only snapshot of authoritative
	// simulation/input state. Used by the overlay to format the LAST
	// INPUT block; never fed back into the simulation.
	FCyclingInputSnapshot LastInputSnapshot;

	// Latest presentation-only feedback record. Updated in the input
	// handlers around the existing FCyclingSimulationSession calls.
	FCyclingLastInputFeedback LastInputFeedback;

	// Latest guided-acceptance observer state.
	FCyclingGuidedAcceptanceState GuidedAcceptance;

	// Captures the current authoritative input snapshot into a
	// pure-data struct.
	FCyclingInputSnapshot CaptureCurrentInputSnapshot() const;

	// Captures BEFORE state, runs the existing command, captures
	// AFTER state and stores the resulting feedback record in
	// LastInputFeedback. Also advances GuidedAcceptance. The command
	// closure must not mutate state outside Session.*.
	template <typename CommandOpT>
	void RecordCommandFeedback(ECyclingInputCommand Command, CommandOpT&& CommandOp)
	{
		const FCyclingInputSnapshot Before = CaptureCurrentInputSnapshot();
		FString Error;
		(void)CommandOp(Error); // execute the actual command; result is captured in Before/After deltas
		const FCyclingInputSnapshot After = CaptureCurrentInputSnapshot();

		// Build the presentation-only feedback record from the
		// authoritative BEFORE/AFTER pair.
		const double PowerStep = Session.IsConfigured()
			? Session.GetConfig().RiderInput.PowerStepW
			: 10.0;
		const double CadenceStep = Session.IsConfigured()
			? Session.GetConfig().RiderInput.CadenceStepRpm
			: 5.0;

		FCyclingLastInputFeedback Built = CyclingDiagnostics::BuildLastInputFeedback(
			Command, Before, After, PowerStep, CadenceStep);
		LastInputFeedback = Built;
		// Keep the public LastInputSnapshot in sync with After so
		// external observers can read the current authoritative
		// mirror without driving the timer.
		LastInputSnapshot = After;

		// Whenever the runtime enters Stopped (or already is
		// Stopped), capture the StopEntrySnapshot so the stability
		// observer has a stable reference. Capturing inside the
		// RecordCommandFeedback pipeline guarantees the snapshot
		// represents the authoritative state at the moment of
		// transition, even when the guided-acceptance observer
		// state machine is disabled or the Pawn was already
		// Stopped.
		if (After.Lifecycle == ECyclingDiagnosticsLifecycle::Stopped
			&& Before.Lifecycle == ECyclingDiagnosticsLifecycle::Running)
		{
			GuidedAcceptance.StopEntrySnapshot = After;
			GuidedAcceptance.StopStabilityObservedTicks = 0;
			GuidedAcceptance.bStopStable = false;
			GuidedAcceptance.StopStabilityStatus.Reset();
		}

		// Advance the guided-acceptance observer (presentation-only).
		if (bEnableGuidedAcceptance)
		{
			GuidedAcceptance = CyclingDiagnostics::AdvanceGuidedAcceptance(
				GuidedAcceptance, Built, After, /*bEnableGuidedAcceptance=*/true);
		}
	}

	// Timer callback. Reads authoritative state, formats the overlay
	// and updates the stable keyed GEngine debug message. Never
	// mutates the simulation.
	void RefreshDiagnosticOverlay();

	// Starts the diagnostic timer (no-op when bEnableDiagnosticOverlay
	// is false).
	void StartDiagnosticTimer();

	// Stops the diagnostic timer and removes the stable keyed message.
	void StopDiagnosticTimerAndClearMessage();

	// Removes the keyed debug message from GEngine (no-op when
	// GEngine is unavailable).
	static void ClearOverlayMessage();
};
