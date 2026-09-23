# YetAnotherCyclingSim — Stage 2 runtime integration contract

**Status:** implementation contract for Stage 2  
**Scope:** first playable Unreal prototype only  
**Current engine target:** Unreal Engine 5.8

## 1. Purpose

Stage 1 already provides a deterministic, rendering-independent cycling domain.
Stage 2 must connect that domain to the Unreal runtime without moving physics,
timing truth, or rider-input truth into Actor transforms, Blueprint graphs, or
frame-dependent code.

The target dependency direction is:

```text
keyboard / diagnostic UI
          |
          v
Unreal input adapter
          |
          v
FCyclingSimulationSession
  |       |        |
  |       |        +--> FRiderInputController
  |       +-----------> FFixedStepSimulationRunner (0.05 s)
  +-------------------> FSimulationState
                          |
                          v
                presentation adapter
                          |
                          v
                    route spline
                          |
                          v
                visible rider placeholder
```

The central rule is:

> `FCyclingSimulationSession` owns simulation truth. Unreal presentation reads
> that truth; presentation never becomes an input to cycling physics.

## 2. Existing contracts that remain authoritative

Stage 2 must reuse the existing domain instead of reimplementing it in Unreal
gameplay classes.

### 2.1 Rider input

`FRiderInputController` remains the single source of current test power and
cadence.

Keyboard actions and diagnostic controls call the session API:

- `TrySetPowerW`;
- `TrySetCadenceRpm`;
- `TryIncreasePower`;
- `TryDecreasePower`;
- `TryIncreaseCadence`;
- `TryDecreaseCadence`.

No Pawn, Actor, widget, or Blueprint may maintain a second authoritative copy of
power or cadence.

Cadence is still part of the public input contract even where the current
longitudinal equation does not directly consume it.

### 2.2 Fixed-step simulation

`FFixedStepSimulationRunner` remains responsible for converting variable
render-frame time into deterministic 0.05 s simulation steps.

The Unreal runtime is allowed to tick once per rendered frame because it is the
single bridge that supplies frame delta to the already-tested fixed-step
runner. Physics itself must not be rewritten as Actor Tick logic.

### 2.3 Session orchestration

`FCyclingSimulationSession` is the Stage 2 domain boundary.

The Unreal runtime owner:

1. configures one session;
2. sends input commands to it;
3. calls `TryAdvance(FrameDeltaS, ...)` while the ride is running;
4. reads `FSimulationState`;
5. converts that state into presentation.

The runtime owner must not call `TryStepSimulation` directly.

### 2.4 Simulation state

`FSimulationState` remains the authoritative longitudinal ride state:

- `SpeedMps`;
- `DistanceM`;
- `ElapsedTimeS`.

Actor transform, spline distance in centimetres, animation state and UI are
derived values.

## 3. Minimal Unreal ownership model

Stage 2 should introduce one small Unreal-owned runtime adapter. The exact
choice between one Actor and one ActorComponent is an implementation detail,
provided there is only one clear owner for the prototype ride session.

That owner may depend on Unreal runtime concepts such as:

- frame delta;
- input events;
- a reference to the prototype route spline;
- the visible placeholder transform;
- diagnostic UI data.

It must not move these concepts into the domain classes.

The adapter owns exactly one `FCyclingSimulationSession` for the local ride.

Avoid:

- one simulation object per presentation subsystem;
- duplicated session state in a widget;
- Level Blueprint orchestration;
- physics calculations in Blueprint;
- independent power/cadence variables in multiple Unreal classes.

## 4. Runtime lifecycle

Use a small explicit runtime lifecycle.

Conceptually:

```text
Uninitialized
     |
     | valid configuration + valid route reference
     v
Ready
     |
     | Start
     v
Running
  |     |
  |     +--> Stop --> Stopped
  |
  +--> route end --> Finished

Stopped -- Restart --> Running from zero
Finished -- Restart --> Running from zero
```

The exact enum/type may differ, but behavior must be explicit.

### 4.1 Configure

Before a ride can run:

- session configuration must validate successfully;
- a route spline reference must exist;
- the spline length must be positive and finite.

Failure must leave the runtime non-running and surface a useful diagnostic
error.

Do not silently replace invalid data with arbitrary defaults.

### 4.2 Start

Starting a valid Ready session enables calls to `TryAdvance`.

Starting must not implicitly mutate rider parameters, environment, power,
cadence, or simulation state.

### 4.3 Stop

Stop means:

- stop calling `TryAdvance`;
- preserve current simulation state;
- preserve the fixed-step accumulator;
- preserve current rider input;
- preserve the current visible position.

It is therefore a runtime pause of progression, not a reset.

### 4.4 Restart

Restart means:

1. stop progression;
2. call `FCyclingSimulationSession::Reset()`;
3. clear presentation-only transient state;
4. place the visible placeholder at the route start;
5. start the ride again.

After Restart:

- speed = 0;
- distance = 0;
- elapsed simulation time = 0;
- fixed-step accumulator = 0;
- power/cadence return to configured initial values.

## 5. Frame update contract

While Running, one Unreal frame performs this sequence:

```text
read FrameDeltaS
      |
      v
Session.TryAdvance(FrameDeltaS)
      |
      +--> 0..N deterministic 0.05 s physics steps
      |
      v
authoritative FSimulationState
      |
      v
update presentation target
      |
      v
place visible placeholder on spline
      |
      v
update diagnostic readout
```

Input actions are event-driven and may occur between frame advances.

### 5.1 Variable render FPS

The adapter passes frame delta only to `FCyclingSimulationSession::TryAdvance`.

It must not:

- multiply power by frame delta;
- integrate distance itself;
- calculate speed from Actor displacement;
- use Actor velocity as physics truth;
- call a variable-delta physics equation.

### 5.2 Multiple fixed steps in one frame

A frame may execute more than one fixed simulation step after a hitch or at a
low render rate.

Presentation consumes the final authoritative state returned for that frame.
It does not need to render every internal fixed step.

### 5.3 Frames with zero fixed steps

A frame may execute zero fixed steps when the accumulated time is below 0.05 s.

The authoritative state remains unchanged.

This is valid behavior and must not trigger an error or an artificial physics
step.

## 6. Spline presentation contract

The Stage 2 prototype uses the existing straight route spline purely as a
presentation/spatial mapping of domain distance.

### 6.1 Unit boundary

The domain remains SI.

The conversion to Unreal centimetres happens only at the presentation boundary:

```text
DistanceAlongSplineCm = SimulationState.DistanceM * 100.0
```

Do not store centimetres back into `FSimulationState`.

### 6.2 Position and orientation

For the prototype:

- clamp the presentation query to the spline range;
- get world location at distance along the spline;
- get world orientation/tangent from the spline;
- set the visible placeholder transform from those presentation values.

The Actor transform is an output only.

### 6.3 Route end

The Stage 2 route is a 500 m presentation asset. The physics domain currently
has no route-length concept and must not gain Stage 3 route semantics merely to
finish this prototype.

When authoritative `DistanceM` reaches or exceeds the spline length:

- clamp visible presentation to the spline end;
- mark the runtime state Finished;
- stop further calls to `TryAdvance`;
- preserve the final authoritative state, including a possible small
  fixed-step overshoot beyond exactly 500 m.

Do not rewind or alter physics state to manufacture an exact finish crossing in
Stage 2. Exact route/sector timing belongs to later route/session work.

## 7. Presentation smoothing boundary

Correctness comes before smoothing.

The first Stage 2 implementation may present the newest authoritative spline
target directly. That is sufficient to prove the integration contract.

If visible 20 Hz stepping is unacceptable, smoothing may be added as a separate
presentation-only task.

Any smoothing must obey all of these rules:

- authoritative `FSimulationState` is never modified;
- smoothed Actor position is never read back into physics;
- HUD physics values come from authoritative state;
- Reset and major discontinuities may snap presentation immediately;
- presentation must not extrapolate a rider beyond known authoritative route
  distance unless a later explicit prediction design is approved.

No interpolation requirement should force a change to the physics step rate.

## 8. Input adapter contract

Keyboard and diagnostic UI are two presentation/input surfaces over the same
session input API.

Recommended prototype actions:

- increase power;
- decrease power;
- increase cadence;
- decrease cadence;
- start/stop;
- restart.

A diagnostic numeric control may additionally call the direct setters.

Do not implement a second keyboard-specific physics model.

A future trainer adapter should be able to replace the test input source by
producing the same domain input values without changing the cycling equations.

## 9. Diagnostic panel contract

The Stage 2 diagnostic panel is a development surface, not the final HUD.

At minimum it should expose authoritative:

- power (W);
- cadence (rpm);
- speed (m/s and optionally derived km/h for display only);
- distance (m);
- elapsed simulation time (s);
- runtime state.

Useful diagnostic-only values:

- fixed steps completed by the latest frame;
- remaining fixed-step accumulator time;
- latest runtime/session error.

The panel must not calculate alternate physics values.

Display-unit conversions are presentation only.

## 10. Failure behavior

### 10.1 Session advance failure

If `TryAdvance` fails:

- do not move the visible placeholder from the last valid presentation state;
- do not reset the session automatically;
- set the runtime to a non-progressing error/stopped condition;
- expose/log the returned error;
- preserve the transactional domain state.

### 10.2 Missing route reference

A missing route/spline reference prevents the ride from starting.

Do not fall back to arbitrary world-X movement.

### 10.3 Invalid frame delta

The session already rejects non-finite or negative frame delta.

The runtime must surface the failure rather than substituting a guessed value.

## 11. Hitch policy

Stage 2 must not silently discard simulation time.

The current fixed-step runner may execute multiple 0.05 s steps to catch up
after a render hitch. The Unreal adapter should preserve that existing behavior.

Do not introduce an arbitrary `DeltaSeconds` clamp merely to hide a hitch.

If later profiling shows that pathological stalls can create an unacceptable
catch-up burst, introduce an explicit, tested simulation-time policy as its own
change. Such a policy must define whether time is slowed, queued, or discarded
and must never be hidden inside presentation code.

For Stage 2, record/report notable hitches during validation rather than changing
physics semantics.

## 12. Environment boundary in Stage 2

Stage 2 may use one configured environment for the straight prototype.

Do not derive grade from the spline yet.

Spline-derived grade, route segments, changing weather and environment sampling
belong to later roadmap stages.

This keeps the Stage 2 goal narrow: prove input → fixed-step physics → visible
movement.

## 13. What belongs in C++ versus Blueprint

### C++

Use C++ for:

- ownership of `FCyclingSimulationSession`;
- runtime lifecycle/state;
- frame-to-session advance;
- session error handling;
- deterministic input commands;
- SI ↔ centimetre conversion boundary;
- reading authoritative state for presentation.

### Blueprint / assets

Blueprint may be used for:

- assigning the prototype spline reference;
- assigning the placeholder mesh/presentation;
- simple visual configuration;
- diagnostic widget composition/binding where practical.

Blueprint must not implement:

- cycling force equations;
- distance integration;
- fixed-step accumulation;
- duplicate authoritative power/cadence state;
- Level Blueprint ride orchestration.

## 14. Stage 2 implementation slices

Keep implementation incremental.

### Slice A — runtime movement bridge

Implement only:

- one runtime owner;
- session configuration;
- session advance;
- route spline reference;
- `DistanceM` → spline transform;
- start/stop/restart;
- minimal error reporting.

This produces the first moving placeholder.

### Slice B — keyboard input

Wire event-driven keyboard actions to the existing session input methods.

No new physics code.

### Slice C — diagnostic panel

Expose the authoritative state/input and basic runtime diagnostics.

### Slice D — integration validation and performance baseline

Validate frame-rate independence in PIE and record the first Game/Render/GPU
frame-time baseline for the intentionally minimal test map.

Presentation smoothing is optional after Slice A correctness is proven.

## 15. Home-PC validation matrix

Every implementation PR that changes Unreal C++ or assets still requires the
existing home-PC build and Automation validation.

For the completed Stage 2 integration, additionally prove:

### Functional

- map opens without Blueprint/runtime errors;
- Start causes forward movement from the spline start;
- increasing power changes subsequent authoritative speed as expected;
- cadence controls update authoritative rider input;
- Stop freezes progression without resetting state;
- Restart returns the session and visible rider to the initial state;
- reaching the spline end enters Finished and does not move beyond the visible
  route;
- no Level Blueprint gameplay logic is required.

### Frame-rate independence

Run an equivalent constant-input ride with representative render pacing such as:

- approximately 30 FPS;
- approximately 60 FPS;
- approximately 120 FPS;
- a controlled jitter/hitch sequence.

For equal total supplied frame time and identical commands, authoritative
simulation state must agree within the existing deterministic/floating-point
contract.

The visible Actor transform may differ transiently only if presentation
smoothing is later enabled; authoritative state may not.

### Build/tests

- build `YetAnotherCyclingSimEditor Win64 Development`;
- zero compiler errors;
- investigate compiler warnings;
- run the existing scoped Automation suites;
- add focused runtime integration tests where the new C++ boundary can be
  tested without brittle asset assumptions.

### Performance baseline

On the reference PC, capture at least:

- average/representative Game thread frame time;
- Render thread frame time;
- GPU frame time;
- obvious hitches during the straight prototype run.

This is a baseline, not Stage 7 visual optimization.

## 16. Explicit non-goals

This contract does not authorize:

- Stage 3 route/profile implementation;
- grade derived from spline geometry;
- sectors or exact finish interpolation;
- cornering;
- weather transitions;
- final HUD;
- final rider/bicycle assets;
- trainer/BLE/FTMS;
- multiplayer;
- network prediction;
- World Partition;
- traffic;
- final animation smoothing.

## 17. Stage 2 architectural completion condition

The runtime integration is architecturally correct when:

1. Unreal input changes only the session input contract.
2. Variable render delta reaches physics only through
   `FCyclingSimulationSession::TryAdvance`.
3. The fixed-step runner remains the only simulation-time accumulator.
4. `FSimulationState` remains authoritative for speed, distance and
   simulation time.
5. Visible world transform is derived from state and the spline.
6. World transform never feeds back into cycling physics.
7. Stop/Restart/Finished behavior is explicit.
8. Errors fail visibly rather than silently resetting or inventing values.
9. The same simulation command/time sequence remains frame-rate independent.
10. No Stage 3 or later subsystem is required to complete the first playable
    straight-line prototype.
