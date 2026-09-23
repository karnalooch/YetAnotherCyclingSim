// Copyright YetAnotherCyclingSim. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "Cycling/CyclingSimulationSession.h"
#include "CyclingPrototypePawn.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class AActor;
class USplineComponent;

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
 * Stage 2 runtime Pawn.
 *
 * The Pawn is the single Unreal-runtime owner of one FCyclingSimulationSession.
 * It is responsible for:
 *
 *  - validating and caching the route spline reference (BeginPlay);
 *  - configuring the session with the prototype fixture values;
 *  - forwarding per-render-frame DeltaSeconds to Session.TryAdvance while
 *    Running (Tick is the only render-frame bridge to the deterministic
 *    fixed-step runner);
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
	// route validation and session configure. Slice A of Stage 2 keeps this
	// enabled on the L_CyclingTest instance to prove the runtime path.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cycling|Runtime")
	bool bAutoStart = false;

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

protected:
	// APawn / AActor overrides.
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

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
};
