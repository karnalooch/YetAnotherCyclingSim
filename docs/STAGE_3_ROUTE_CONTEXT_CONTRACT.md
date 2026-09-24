# Stage 3 route-context contract

## Status

Stage 3A contract for route-dependent simulation context.

This document defines the boundary between authoritative fixed-step simulation
and later Stage 3 route/profile/presentation work. Stage 3B/3C may provide real
route data and spline-derived grade, but they must preserve these rules.

## Authoritative source

Route/environment physics is resolved from the authoritative
`FSimulationState` at the **start of each 0.05 s fixed simulation step**.

The minimum authoritative route-progress input is:

`FSimulationState::DistanceM`

The following are explicitly not authoritative physics inputs:

- Actor transform;
- Pawn transform;
- rendered spline position sampled once per render frame;
- viewport/frame rate;
- wall-clock time.

## Per-step resolution

`ISimulationStepContextProvider::TryResolveEnvironment(...)` is called once for
every fixed substep that actually runs.

Therefore a catch-up render frame that executes multiple fixed steps may use
more than one route environment in the same render-frame batch.

Example:

1. fixed step starts on flat road;
2. it crosses the route distance at which the climb starts;
3. the next fixed step in the same catch-up batch resolves the climb grade;
4. no render-frame boundary is required for the environment to change.

This rule applies to grade and any other route-local `FEnvironment` field,
including wetness and rolling-resistance multiplier.

## Environment-section boundary semantics

`FDistanceBasedSimulationStepContextProvider` selects the environment section
with the greatest `StartDistanceM` that is less than or equal to the
authoritative pre-step `DistanceM`.

Therefore an authoritative distance exactly equal to a section start uses the
new section.

Environment sections must:

- start with one section at exactly 0 m;
- have finite, non-negative, strictly increasing start distances;
- contain valid `FEnvironment` values.

## Route-boundary crossing semantics

Boundary events are observed after a successful fixed simulation step.

For Sector and Finish boundaries a crossing is emitted when:

`PreStep.DistanceM < Boundary.DistanceM <= PostStep.DistanceM`

A boundary is therefore emitted once for a monotonically-forward ride and is
not emitted again when a later step begins exactly on or beyond that boundary.

### Start

A Start boundary is defined only at exactly 0 m.

It is emitted on the first fixed step for which:

- pre-step distance is exactly 0 m; and
- post-step distance is greater than 0 m.

A stationary rider does not cross Start merely because simulation time passes.

### Terminal finish

A Finish boundary may request `bStopAfterCrossing`.

When such a finish is crossed:

- the crossing fixed step is committed;
- later fixed steps from that same render-frame batch are not executed;
- remaining accumulated frame time is preserved and reported;
- accumulated time is not silently discarded or clamped.

The runtime lifecycle integration that latches the final `Finished` state is a
later Stage 3 integration responsibility. Stage 3A only provides deterministic
fixed-step crossing/early-stop semantics.

## Transactional behavior

If environment resolution, physics stepping, or completed-step observation
fails during a batch:

- runner simulation state is unchanged;
- runner accumulator is unchanged;
- no partial boundary-crossing list is published;
- completed-step output is zero.

Context-provider implementations must be logically const and must not keep
externally visible partial mutations that would violate this transaction model.

## Frame-pacing invariant

For identical:

- initial simulation state;
- rider parameters;
- rider input sequence;
- route-context data;
- total supplied simulation time;

authoritative state and route-crossing observations must not depend on whether
fixed steps were supplied through regular render frames, jitter, or a catch-up
hitch.

## Stage 3B / 3C integration rule

Stage 3B may construct the real Alpine route profile and Stage 3C may derive
grade from the route geometry/spline.

They must feed that data through the fixed-step context contract.

They must **not**:

- sample route grade once in `Pawn::Tick()` and reuse it for all fixed steps;
- make the Actor transform authoritative route progress;
- introduce a second physics-time accumulator;
- move route-dependent physics into a Level Blueprint.
