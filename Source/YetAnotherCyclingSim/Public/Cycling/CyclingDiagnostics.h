// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Stage 2 prototype diagnostic overlay - presentation-only.
//
// This header defines the pure-data and pure-formatting pieces of the
// development diagnostic panel. It contains:
//   - the snapshot of authoritative runtime/input fields that the
//     overlay reads (power, cadence, speed, distance, elapsed time,
//     lifecycle, fixed-step accumulator, last fixed-step count, last
//     runtime error);
//   - the small presentation-only feedback record describing the most
//     recent accepted/ignored prototype input command and its observed
//     domain effect;
//   - the guided-manual-acceptance observer state machine that drives
//     the in-viewport "what to press next" hint without ever
//     mutating authoritative state;
//   - a pure formatter that turns one snapshot into one multi-line
//     FString ready for a stable keyed on-screen debug entry.
//
// No Actor, Pawn, SceneComponent, GEngine or renderer dependency
// lives in this header. The intent is to keep the formatter/observer
// logic testable in isolation (issue #48 acceptance #15) and to keep
// the runtime Pawn free of string-builder bloat (issue #48 rule #14).
//
// Architectural rule:
//   Authoritative simulation state lives in FCyclingSimulationSession
//   and FRiderInputController. This file owns presentation-only
//   mirrors that NEVER feed back into the simulation.

#pragma once

#include "CoreMinimal.h"
#include "Containers/UnrealString.h"

#include "Cycling/SimulationState.h"
#include "Cycling/RiderInput.h"

// Stable integer key used by the runtime Pawn to register a single
// on-screen debug entry that is replaced/refreshed rather than
// accumulated. Picked as the four-byte ASCII tag "YCSD" ('Y'=0x59,
// 'C'=0x43, 'S'=0x53, 'D'=0x44) which is guaranteed not to collide
// with INDEX_NONE (-1) and is unlikely to clash with the engine's
// transient engine warnings (which mostly use negative keys).
#define YACS_DIAGNOSTIC_OVERLAY_KEY ((uint64)0x59435344)

// =====================================================================
// Lifecycle enumeration (must match the Pawn-side enum order).
// =====================================================================

// Stage 2 lifecycle as seen by the Pawn. Duplicated here (instead of
// being a dependency on CyclingPrototypePawn.h) so the formatter and
// the guided-acceptance observer can be unit-tested in isolation.
// Order matches ACyclingPrototypePawn::ECyclingPrototypeLifecycle so
// the values stay in sync.
UENUM()
enum class ECyclingDiagnosticsLifecycle : uint8
{
	Uninitialized = 0,
	Ready         = 1,
	Running       = 2,
	Stopped       = 3,
	Finished      = 4,
	Error         = 5,
};

// =====================================================================
// Input feedback types (declared first; used by FCyclingDiagnosticsSnapshot).
// =====================================================================

// Identifies the most recently observed prototype command. Used by
// the overlay to render a single line describing what was pressed and
// what happened as a consequence. Presentation-only; not authoritative.
UENUM()
enum class ECyclingInputCommand : uint8
{
	None              = 0,
	PowerIncrease     = 1,
	PowerDecrease     = 2,
	CadenceIncrease   = 3,
	CadenceDecrease   = 4,
	StartOrResume     = 5,
	Stop              = 6,
	Restart           = 7,
};

// Snapshot of one moment in authoritative simulation/input state.
// Captured before and after each prototype command to derive a
// before/after presentation-only feedback record. Never persisted
// into the simulation.
struct FCyclingInputSnapshot
{
	double PowerW = 0.0;
	double CadenceRpm = 0.0;
	double SpeedMps = 0.0;
	double DistanceM = 0.0;
	double ElapsedTimeS = 0.0;
	ECyclingDiagnosticsLifecycle Lifecycle = ECyclingDiagnosticsLifecycle::Uninitialized;
};

// One observed command and its derived before/after effect.
// Presentation-only; the authoritative simulation is unaffected by
// the existence of this struct.
struct FCyclingLastInputFeedback
{
	ECyclingInputCommand Command = ECyclingInputCommand::None;
	bool bAccepted = false;
	FCyclingInputSnapshot Before;
	FCyclingInputSnapshot After;
};

// =====================================================================
// Authoritative snapshot (presentation-side, read-only).
// =====================================================================

// Pure-data snapshot that the formatter consumes. The Pawn assembles
// it on every refresh tick from existing read-only diagnostics; the
// formatter does not read anything beyond what is in this struct.
//
// All numeric fields use SI units (W, rpm, m/s, m, s).
struct FCyclingDiagnosticsSnapshot
{
	// Stage 2 lifecycle at the moment of capture.
	ECyclingDiagnosticsLifecycle Lifecycle = ECyclingDiagnosticsLifecycle::Uninitialized;

	// Current rider power (W).
	double PowerW = 0.0;

	// Current rider cadence (rpm).
	double CadenceRpm = 0.0;

	// Authoritative forward speed (m/s).
	double SpeedMps = 0.0;

	// Authoritative distance along the route (m).
	double DistanceM = 0.0;

	// Authoritative elapsed simulation time (s).
	double ElapsedTimeS = 0.0;

	// Number of fixed-step simulation steps executed by the latest
	// rendered frame. Zero on frames with no fixed step.
	int32 LastCompletedSteps = 0;

	// Remaining unprocessed fixed-step accumulator time (s).
	double AccumulatorS = 0.0;

	// Cached spline length in metres. Used to format
	// "DISTANCE 126.7 / 500.0 m".
	double CachedRouteLengthM = 0.0;

	// Latest useful runtime/session error. Empty when healthy.
	FString LastError;

	// Configured power step (W) for the controls legend.
	double ConfiguredPowerStepW = 10.0;

	// Configured cadence step (rpm) for the controls legend.
	double ConfiguredCadenceStepRpm = 5.0;

	// Latest presentation-only last-input feedback (see below). The
	// formatter renders this block directly from
	// FCyclingLastInputFeedback.
	FCyclingLastInputFeedback LastInputFeedback;
};

// =====================================================================
// Guided manual acceptance (presentation-only observer).
// =====================================================================

// Ordered list of guided acceptance steps. The overlay shows the
// current step's "press X" instruction and the PASS/FAIL/pending
// status of the previous step. The state machine is forward-only and
// advances only when the observer detects that the natural runtime
// outcome of the user's keyboard activity matches the expected
// outcome. The observer never issues commands on behalf of the
// tester.
UENUM()
enum class ECyclingGuidedAcceptanceStep : uint8
{
	// 1. Ready -> press SPACE -> Running.
	Ready_WaitStart         = 0,
	// 2. Running -> press UP -> power + one configured step.
	Running_WaitPowerUp     = 1,
	// 3. Running -> press RIGHT -> cadence + one configured step.
	Running_WaitCadenceUp   = 2,
	// 4. Running -> press S -> Stopped, freeze distance/time.
	Running_WaitStop        = 3,
	// 5. Stopped -> press SPACE -> Running without reset.
	Stopped_WaitStart       = 4,
	// 6. Running -> press R -> state reset, lifecycle Running.
	Running_WaitRestart     = 5,
	// 7. Finished state reached; show Restart-required hint.
	Finished                = 6,
};

// Pure observer state. The Pawn updates this struct in response to
// normal user input; the formatter reads it. The struct contains
// only presentation-only fields: a step index, a status, a snapshot
// for stability checks, and a string of the last comparison result.
//
// Invariant: this struct CANNOT mutate the authoritative
// FCyclingSimulationSession. The Pawn never reads from it to decide
// whether to call Session API.
struct FCyclingGuidedAcceptanceState
{
	ECyclingGuidedAcceptanceStep CurrentStep =
		ECyclingGuidedAcceptanceStep::Ready_WaitStart;

	// "PENDING" | "PASS" | "FAIL".
	FString StepStatus;

	// Optional human-readable note attached to StepStatus (e.g.
	// "expected power +10 W"). Empty when not relevant.
	FString StepNote;

	// Snapshot captured at Stop entry for the stability check in
	// step 4. Compared against current authoritative distance /
	// elapsed time on each refresh tick while in Stopped.
	FCyclingInputSnapshot StopEntrySnapshot;

	// Number of refresh ticks the Pawn has been in Stopped since
	// the snapshot was captured. The overlay only emits
	// "Distance stable: PASS" once the snapshot has been observed
	// for at least one full refresh interval (> 0).
	int32 StopStabilityObservedTicks = 0;

	// Set to true while Stop stability is confirmed: distance and
	// elapsed time equal StopEntrySnapshot.
	bool bStopStable = false;

	// "PASS" once stop stability has been observed for the required
	// duration.
	FString StopStabilityStatus;
};

// =====================================================================
// Public API (pure, no Unreal Actor/Pawn dependency).
// =====================================================================

namespace CyclingDiagnostics
{
	// Maps the Pawn's lifecycle enum to the diagnostics lifecycle
	// enum. Exposed so tests can build a snapshot directly.
	ECyclingDiagnosticsLifecycle MapLifecycle(int32 PawnLifecycleValue);

	// Captures a snapshot from authoritative simulation/input
	// values. Pure function: takes the values that the Pawn reads
	// from existing read-only diagnostics and packages them into
	// the formatter's snapshot.
	FCyclingDiagnosticsSnapshot MakeSnapshot(
		ECyclingDiagnosticsLifecycle Lifecycle,
		double PowerW,
		double CadenceRpm,
		const FSimulationState& State,
		int32 LastCompletedSteps,
		double AccumulatorS,
		double CachedRouteLengthM,
		const FString& LastError,
		double ConfiguredPowerStepW,
		double ConfiguredCadenceStepRpm,
		const FCyclingLastInputFeedback& LastInputFeedback = FCyclingLastInputFeedback());

	// Returns a short uppercase tag for an input command. Examples:
	// "UP", "DOWN", "LEFT", "RIGHT", "SPACE", "S", "R", "-".
	const TCHAR* GetInputCommandKeyTag(ECyclingInputCommand Command);

	// Returns a human-readable command label. Examples:
	// "POWER +10 W", "CADENCE -5 rpm", "START", "STOP", "RESUME",
	// "RESTART".
	FString GetInputCommandLabel(ECyclingInputCommand Command,
		double ConfiguredPowerStepW, double ConfiguredCadenceStepRpm);

	// Captures an authoritative input/simulation snapshot at one
	// moment of time.
	FCyclingInputSnapshot CaptureInputSnapshot(
		ECyclingDiagnosticsLifecycle Lifecycle,
		double PowerW,
		double CadenceRpm,
		const FSimulationState& State);

	// Builds a presentation-only last-input feedback record from
	// authoritative BEFORE and AFTER snapshots and the command that
	// was issued. The command itself never mutates the snapshots;
	// the formatter only inspects the before/after deltas. Pure
	// function.
	FCyclingLastInputFeedback BuildLastInputFeedback(
		ECyclingInputCommand Command,
		const FCyclingInputSnapshot& Before,
		const FCyclingInputSnapshot& After,
		double ConfiguredPowerStepW,
		double ConfiguredCadenceStepRpm);

	// Formats one snapshot into the multi-line overlay string.
	// The string is sized to be replaced (not appended) into a
	// stable keyed GEngine->AddOnScreenDebugMessage(...) entry.
	FString FormatOverlay(const FCyclingDiagnosticsSnapshot& Snapshot,
		const FCyclingGuidedAcceptanceState& Guided,
		bool bEnableGuidedAcceptance);

	// Pure observer: evaluates whether the latest command feedback
	// transitions the guided acceptance state machine forward.
	// Returns the new state (the input state is copied and
	// advanced if appropriate). The function NEVER mutates the
	// authoritative session. Callers MUST ignore this function's
	// output when bEnableGuidedAcceptance is false.
	FCyclingGuidedAcceptanceState AdvanceGuidedAcceptance(
		const FCyclingGuidedAcceptanceState& Current,
		const FCyclingLastInputFeedback& LastFeedback,
		const FCyclingInputSnapshot& CurrentSnapshot,
		bool bEnableGuidedAcceptance);

	// Pure observer: evaluates Stopped-state stability against the
	// StopEntrySnapshot already stored on the guided state. Updates
	// bStopStable / StopStabilityStatus / StopStabilityObservedTicks
	// in a copy and returns it. NEVER re-enables the simulation Tick
	// or modifies the authoritative session. The Pawn is expected
	// to call this every refresh tick.
	FCyclingGuidedAcceptanceState ObserveStopStability(
		const FCyclingGuidedAcceptanceState& Current,
		const FCyclingInputSnapshot& CurrentSnapshot);
}