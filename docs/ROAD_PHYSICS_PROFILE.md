# YACS — Road Physics Profile

**Status:** architectural contract  
**Scope:** Stage 3H, consumed by Stage 4 cornering and future advanced physics  
**Rule:** rendering, terrain and PCG are presentation/world-generation layers, not the authoritative source of road physics

## 1. Purpose

The Road Physics Profile is the canonical physics-facing representation of the rideable road.

Its purpose is to let World/Assets/PCG and Physics evolve independently while consuming the same route definition. Physics must not infer authoritative grade, curvature, banking or surface state from arbitrary mesh triangles, render transforms, terrain normals or PCG output.

The intended dependency flow is:

```text
Route authoring / procedural route definition
                 |
                 v
        Road Physics Profile
          /             \
         v               v
Physics/gameplay      UE geometry/world
                         |
                         v
                    PCG/presentation
```

## 2. Route-local coordinate system

Every rideable point must be addressable in route-local coordinates:

- `S` — longitudinal distance along the authoritative route;
- `D` — signed lateral displacement from the route reference line.

The sign convention for `D` must be defined once and used consistently across route queries, physics, guidance, replay and telemetry.

Physics must be able to query the rider's current `S` and `D`, not only world-space XYZ.

## 3. Minimum profile contract

For a relevant route position, the profile must be capable of exposing:

| Property | Purpose | MVP use |
|---|---|---|
| `S` / route progress | deterministic progress and queries | yes |
| elevation | route vertical profile | yes |
| longitudinal grade | gravity along the route | yes |
| signed horizontal curvature | corner direction and lateral demand | yes |
| effective radius | human-readable/debug corner context | yes |
| vertical curvature | crest/compression metadata | represented now, advanced effect post-MVP |
| road width | available riding envelope | yes |
| lateral position `D` | racing-line / path selection | yes |
| banking / cross-slope | banked and off-camber behaviour | yes |
| surface type | asphalt/paint/gravel/future types | simplified MVP grip |
| wetness | weather-dependent grip input | simplified MVP grip |
| roughness | future vibration/energy-loss input | represented now, post-MVP effect |

The profile may expose additional derived fields, but derived values must not replace the canonical route quantities.

## 4. Horizontal curvature

Corner physics must consume continuous curvature rather than only a discrete `radius` label.

A generated road must not transition directly from zero curvature to a tight radius in one simulation sample. Curvature must change through a transition region.

A clothoid-like implementation is allowed but not mandated. The contract requires continuity and bounded rates of change, not one specific mathematical primitive.

## 5. Vertical curvature

Longitudinal grade alone is insufficient to describe vertical road geometry.

The profile must retain vertical curvature so future physics can model normal-load changes over:

- crests;
- compressions;
- short rollers;
- fast transitions between climb and descent.

MVP is not required to apply these normal-load effects yet.

## 6. Banking and cross-slope

Banking is independent from longitudinal grade and is queried from the same route-local `S/D` coordinate system as the rest of the physical road.

Each canonical sample stores two half-road values:

- `left_cross_slope_angle_rad` for `D < 0`;
- `right_cross_slope_angle_rad` for `D > 0`.

Positive cross-slope rises toward `+D` (the rider's right). At `D = 0` the query returns the deterministic average of the left/right half-road values. Both half-road values interpolate continuously along `S`.

This representation supports without consulting rendered geometry:

- flat road: left = 0, right = 0;
- planar bank: left = right = the same signed angle;
- ordinary crown/crossfall: left/right may have different or opposite signed angles;
- off-camber corners: Stage 4 interprets local cross-slope together with signed horizontal curvature.

Both left and right cross-slope angles must remain finite, strictly inside `(-pi/2, pi/2)`, and must not appear or disappear discontinuously. Authoring/generation provides transition regions and validates their rate of change explicitly.

Stage 4B-C interprets bank support from the existing sign conventions without adding another road representation. Positive curvature turns toward `+D` (right), while positive cross-slope rises toward `+D`; therefore the signed support angle used by the pure-lateral corner model is:

```text
bank_support_angle = -sign(horizontal_curvature) * local_cross_slope
```

A positive support angle is banked in favour of the turn; a negative value is off-camber/adverse. The pure-lateral limit uses the resolved surface grip and effective racing-line radius. It deliberately does not consume braking demand yet; the shared longitudinal+lateral friction budget remains Stage 4C. No arbitrary recommended-speed margin is embedded in the physics limit.

The current Alpine Journey baseline is intentionally `0° / 0°`. Stage 3 route geometry does not yet carry authored banking/crown values, so Stage 3H does not invent them.

## 7. Racing line and lateral position

The rider is not constrained to an infinitely thin centerline.

Changing `D` can change:

- effective corner radius;
- travelled path length;
- experienced cross-slope/banking;
- local surface beneath the tyres;
- remaining road margin.

The MVP may use controlled/automatic line selection instead of free steering, but that line selection must operate in the same route-local coordinate system.

## 8. Grip budget

Braking and cornering must not receive independent full-grip budgets.

Stage 4C-A uses the simplest explicit MVP form: a **unit friction circle** operating on normalized absolute tyre-force usage:

```text
longitudinal_usage = |Fx demand| / longitudinal capacity
lateral_usage      = |Fy demand| / lateral capacity

combined_usage = sqrt(longitudinal_usage^2 + lateral_usage^2)
```

`combined_usage <= 1` is inside the shared budget; `combined_usage > 1` exceeds it. Inputs are not clamped, so over-demand remains observable.

The kernel also exposes how much normalized axis capacity remains while the other axis is consuming grip:

```text
remaining_lateral_capacity      = sqrt(max(0, 1 - longitudinal_usage^2))
remaining_longitudinal_capacity = sqrt(max(0, 1 - lateral_usage^2))
```

This makes the core invariant explicit: two demands that are each individually below 100% can still exceed the shared budget when combined.

Stage 4C-A deliberately does **not** invent braking controls, brake-force split, a tyre coefficient, a safety factor or consequence thresholds.

Stage 4C-B1 adds the explicit control-side contract `brake_ratio ∈ [0, 1]`: `0` means released and `1` means full requested braking. The default is `0` and, during B1, the value is validated/plumbed through rider input, controller and session but intentionally does not alter the equation of motion. This preserves exact pre-braking physics while the force model is reviewed separately.

Stage 4C-B2 is the deterministic demand bridge. The explicit normalized brake command is the longitudinal usage request, while lateral usage is derived from the actual fixed-step speed and Stage 4B-C corner limit:

```text
lateral_acceleration_demand = speed^2 / effective_radius
lateral_usage = lateral_acceleration_demand / lateral_acceleration_limit
longitudinal_usage = brake_ratio
```

These values feed the 4C-A shared circle. This makes shared-grip accounting available without inventing a brake-force constant.

Stage 4C-B3a resolves the no-slip braking force without a hardware-specific maximum-brake constant. The standalone longitudinal capacity is derived from the caller-owned effective tyre-road friction and the static gravity-normal component of the tilted road surface:

```text
normal_load_static = mass * g * cos(longitudinal_road_angle) * cos(cross_slope)
longitudinal_force_capacity = mu_effective * normal_load_static
applied_longitudinal_usage = min(brake_ratio, remaining_longitudinal_capacity)
applied_brake_force = applied_longitudinal_usage * longitudinal_force_capacity
```

The rider's requested shared budget remains visible even when the no-slip applied force is capped. Dynamic load transfer, front/rear brake split, ABS, wheel lock and tyre relaxation remain outside the MVP resolver.

Stage 4C-B3b applies the resolved braking force as an explicit non-negative opposing force in the fixed-step energy model. The force is included in both the deterministic predictor and the average-speed work estimate. The legacy simulation-step API delegates to the explicit-force integrator with exactly `0 N`, and zero-brake results must remain exact regression parity with the pre-braking simulation.

Stage 4C-B3c is the orchestration layer: for every authoritative fixed substep it resolves current Road Physics Profile state, corner context, lateral capacity, shared demand and tyre-limited braking force before calling the explicit-force integrator. This happens inside the fixed-step runner, so render-frame batching cannot change braking/cornering results.

A look-ahead corner is not the current tyre contact patch. During `Approach`, the corner context may intentionally describe future curvature/surface metadata for guidance, while longitudinal braking still uses the current `S/D` road state under the tyres. Actual lateral grip usage starts only in `Entry`, `Apex` and `Exit`. Current grade, cross-slope, surface and wetness therefore remain the source for longitudinal tyre capacity until the rider physically reaches the corner.

Aerodynamic drag, gravity and rolling resistance remain ordinary external/resistance forces and must not be misclassified as tyre-braking grip usage.

The kernel is stateless rather than one permanent global grip scalar. MVP may evaluate it for a simplified whole-bike model; later front/rear tyre state can evaluate the same contract independently with different capacities and demands.

## 9. Surface and wetness

Grip must not permanently be represented as one global coefficient for the whole route.

Stage 3H therefore carries deterministic road metadata rather than embedding one friction policy:

- `surface_id` identifies the physical surface state for the route interval;
- `wetness` is a normalized `[0, 1]` surface input;
- `roughness` remains a non-negative metadata input whose detailed physical effect is post-MVP.

The Alpine Journey static baseline is `surface_id = asphalt`, `wetness = 0`, `roughness = 0`. Dynamic weather is composed later and is not baked into the authoritative geometry builder.

Stage 4B owns a deterministic `SurfaceGripPolicy` that turns `surface_id + wetness` into a relative `grip_multiplier`. The policy is explicit configuration: every surface provides a dry and fully-wet multiplier, and normalized wetness linearly interpolates between them. Unknown surfaces fail closed. The tyre/base friction coefficient remains a separate caller-owned input, so this layer still does **not** invent absolute friction coefficients or a detailed tyre model.

For the Alpine Journey asphalt baseline, the existing scripted weather data already defines a consistent relationship: dry asphalt is `1.00`, fully-wet asphalt is `0.75`, and all intermediate weather keyframes lie exactly on the same linear interpolation. Stage 4B reuses that existing contract instead of introducing new numbers. Stage 4C later consumes the resolved multiplier in the shared braking/cornering grip budget.

Later versions may distinguish, for example:

- dry/wet asphalt;
- painted markings;
- gravel/shoulder;
- standing water;
- other hazards.

## 10. Front/rear tyre extensibility

MVP does not require a detailed two-tyre contact model.

The architecture must still allow future front/rear state to diverge, including:

- normal load;
- longitudinal force;
- lateral force;
- slip;
- camber response;
- tyre pressure influence;
- load sensitivity;
- self-aligning torque.

Detailed measured tyre models and Magic Formula/Pacejka are post-MVP.

## 11. Rider anticipation / look-ahead

Route context must be queryable ahead of the current `S`.

This enables technique scoring to evaluate preparation for a corner, not only state at the apex.

MVP technique evaluation should be able to consider:

- entry speed;
- power reduction timing;
- braking-equivalent grip demand where applicable;
- release timing;
- line choice;
- apex behaviour;
- power application on exit.

Look-ahead queries must be deterministic.

## 12. Crosswind extensibility

The environment model must remain extensible beyond headwind/tailwind drag.

Post-MVP physics may add:

- lateral aerodynamic force;
- yaw-dependent aero effects;
- roll/steering moments.

These are not Stage 3H implementation requirements.

## 13. Roughness extensibility

Road roughness must be representable as metadata.

No detailed vibration or roughness-energy-loss model is required for MVP.

Future uses may include:

- additional energy loss;
- rider/bike vibration;
- camera feedback;
- audio;
- handling modifiers.

## 14. MVP boundary

Before the physics side of MVP is considered complete, YACS should use:

- longitudinal grade;
- signed horizontal curvature;
- road width and lateral rider position;
- banking/cross-slope;
- continuous curvature/banking transitions;
- surface + wetness through a simplified grip model;
- shared braking/cornering grip budget;
- deterministic look-ahead sufficient for technique evaluation.

Explicitly post-MVP physical effects:

- detailed front/rear tyre dynamics;
- detailed load transfer;
- Magic Formula/Pacejka or equivalent advanced tyre model;
- vertical-curvature normal-load effects;
- roughness vibration/energy-loss physics;
- lateral crosswind force and steering/roll moments;
- weave/wobble simulation;
- crash/fall simulation.

The post-MVP list does not mean those inputs may be discarded from the route/environment contracts.

## 15. Validation invariants

Generated or authored profiles must reject or flag at least:

- NaN/infinite values;
- zero/negative or otherwise invalid road width;
- pathological grade spikes caused by sampling noise;
- discontinuous or unbounded curvature changes;
- discontinuous banking changes;
- route-local coordinate inconsistencies;
- invalid surface identifiers/state;
- out-of-range wetness values.

Thresholds belong to explicit configuration/specification, not hidden rendering code.

## 16. World/Physics separation

World and Physics are separate workstreams.

### World lane

Owns:

- terrain;
- road mesh presentation;
- PCG;
- vegetation;
- rocks;
- materials;
- atmosphere;
- visual polish.

### Physics lane

Owns:

- synthetic Road Physics Profile fixtures;
- grade;
- curvature;
- banking;
- racing line;
- grip budget;
- technique/consequences;
- deterministic route queries.

### Integration lane

Proves that the authoritative route definition feeds both world presentation and physics consistently.

A visual road may not silently disagree with the physical road profile.

## 17. CI expectations

A physics-only change should not require full asset checkout.

A regular asset-only change should not trigger unrelated C++/physics work unless its path classification requires it.

For trusted `ue_code=true` changes, PR #163 makes the code-only reusable Unreal build + Automation lane part of the fail-closed Aggregate CI gate.

Heavy map/asset/cook/package proof remains a separate explicit lane.

## 18. Evolution rule

Future physics features should consume or extend this contract.

If a new feature requires replacing the Road Physics Profile with an unrelated route representation instead of extending it, that should be treated as an architectural regression and reviewed explicitly.
