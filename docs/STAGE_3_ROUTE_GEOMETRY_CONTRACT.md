# Stage 3 route geometry contract

## Purpose

Stage 3C turns the Stage 3B Alpine Journey domain profile into deterministic
3D route geometry and a persisted Unreal spline while preserving the Stage 3A
fixed-step architecture.

## Sources of truth

Different layers own different facts:

- `FRouteProfile` owns ordered route segments, nominal segment grade targets
  and authoritative route-distance boundaries.
- `FRouteGeometryProfile` owns the deterministic 3D embedding of route
  distance in metres.
- `FSimulationState::DistanceM` remains authoritative runtime route progress.
- the persisted `USplineComponent` is a presentation/editor asset generated
  from `FRouteGeometryProfile`; it is not authoritative physics state.

Actor or Pawn transforms must never become route-progress inputs.

## Geometry construction

The Stage 3C Alpine geometry is sampled every 10 m of route-surface distance.

For each integration interval:

1. resolve the nominal Stage 3B grade target;
2. blend grade with smoothstep inside a 50 m half-window around each interior
   segment boundary;
3. compute horizontal run from surface distance and rise/run grade;
4. integrate XY heading through a smooth sinusoidal curvature envelope whose peak curvature is `1 / RadiusM`;
5. integrate Z from grade;
6. emit a geometry sample whose 3D interval length matches the route-distance
   interval.

The generated route therefore has exactly 10,000 m of route-surface distance
within floating-point tolerance.

## Grade derivation

Runtime grade is not read from the Actor rotation and is not sampled once per
render frame.

`FRouteGeometryProfile::TryCalculateGrade(...)` derives rise/run directly from
the route geometry polyline inside a configurable distance window.

Horizontal run is accumulated along the polyline rather than measured as one
straight chord. Curved road therefore does not artificially increase derived
grade.

`FRouteGeometrySimulationStepContextProvider` plugs this derived grade into
the Stage 3A `ISimulationStepContextProvider` contract so grade is resolved
from authoritative pre-step `DistanceM` for each fixed simulation substep.

Weather, wetness and other dynamic environment systems remain outside Stage 3C.

## Grade continuity

Stage 3B nominal grades are intentionally not converted into hard vertical
tangent discontinuities.

Each interior segment boundary uses a 100 m total smooth transition window
(50 m before + 50 m after). Stage 3C automated validation checks the derived
grade on a 10 m grid and rejects unplanned adjacent changes larger than
1.25 percentage points per 10 m.

This tolerance is a Stage 3 prototype continuity contract, not a final road
engineering standard.

## Corner geometry

The Stage 3C prototype includes eight deterministic curvature zones aligned
with the existing Alpine Journey corner reference:

| Corner | Center (m) | Length (m) | Radius (m) |
|---|---:|---:|---:|
| Village Bend | 650 | 80 | 55 |
| River Left | 1550 | 110 | 40 |
| Forest Entrance | 4050 | 90 | 32 |
| Climb Hairpin | 5350 | 70 | 18 |
| Shelf Right | 6650 | 100 | 30 |
| Valley Hairpin | 7550 | 80 | 22 |
| High Valley Sweep | 8150 | 140 | 48 |
| Lakeside Final Bend | 9250 | 100 | 35 |

Signed curvature alternates to produce left/right geometry. Curvature is zero at each zone entry/exit and reaches the listed radius only at the zone centre. Automated validation rejects unplanned XY centerline self-crossings.

These are geometry inputs only. Stage 4 owns corner-technique scoring, grip,
penalties, guidance and gameplay consequences.

## Persisted Unreal spline

`CyclingStage3RouteSetupCommandlet` is the only Stage 3C writer for the
prototype route asset.

It:

1. loads `/Game/Prototype/Maps/L_CyclingTest`;
2. finds the single route actor with exactly one `USplineComponent`;
3. rebuilds deterministic Alpine geometry;
4. replaces the spline points with geometry samples converted m -> cm;
5. uses Linear spline-point type so persisted geometry exactly matches the
   deterministic polyline;
6. saves the map.

Linear points are an intentional Stage 3 correctness choice. Final visual road
smoothing/material/mesh treatment belongs to later world/presentation work.

`CyclingStage3RouteVerifyCommandlet` must then run in a fresh editor process.
That proves save/reopen persistence and validates route actor identity, spline
point count, total length, representative positions and finite tangent samples.

## Local dirty-worktree safety

The owner's main home-PC checkout may contain unrelated local edits to
`Config/DefaultGame.ini` and `Content/Prototype/Maps/L_CyclingTest.umap`.

Stage 3C route generation must therefore run from a clean dedicated Git
worktree. Do not stash, reset, overwrite or commit those unrelated changes.

## Non-goals

Stage 3C does not:

- wire the production Pawn/session to the new route context (Stage 3D);
- implement final sector/finish lifecycle (Stage 3D);
- build production terrain or environment art (Stage 3E/Stage 7);
- implement corner technique (Stage 4);
- implement weather (Stage 8).
