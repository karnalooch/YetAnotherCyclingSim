# Stage 3G R5 — Smooth Frame / Rendering Tech

**Status:** planned; starts only after Stage 3G R4 visual/world closeout  
**Owner:** YACS rendering/performance workstream  
**Reference target:** 1920×1080 / stable 60 FPS on RTX 2070 SUPER reference PC  
**Hard frame interval:** 16.667 ms  
**Development headroom target:** approximately 13–14 ms p95 where practical  
**Framework:** YACS Performance Framework v1.0, extended by the R5 evidence rules below

## Intent

R5 is a dedicated performance-and-rendering-tech pass. It is intentionally separated from R4 so that world/forest/terrain/road changes can be accepted visually before renderer tuning starts.

R5 must improve **frame pacing and hitch behavior**, not merely average FPS. Vendor technologies are optional backends over a healthy baseline; they must not hide an underlying CPU, GPU, streaming or shader-stutter regression.

R5 does not reopen R4 art direction unless a measured optimization causes a visual regression that must be fixed or rejected.

## Entry gate: R4 closeout

Do not start R5 implementation until the R4 agent publishes a closeout report containing:

- exact branch and HEAD/commit SHA;
- summary of visible changes;
- forest status;
- terrain status;
- road / route-fit status;
- canonical screenshots at **1200 m / 4900 m / 8000 m**;
- average FPS;
- 1% low FPS;
- Frame / Game / Draw / GPU timing;
- VRAM high-water mark where available;
- hitch count and/or hitch percentile evidence;
- CI / proof status;
- known problems and regressions.

The R4 numbers are a **measurement baseline, not a target to game**. Do not optimize R4 before capturing the accepted closeout state.

## R5 principles

1. Measure first; change one major variable at a time.
2. Keep Native/TSR as vendor-neutral reference paths.
3. Do not judge success by average FPS alone.
4. Super Resolution and Frame Generation are separate systems.
5. Frame Generation never makes a failed base-render performance gate pass.
6. Low-latency integration is paired with the appropriate vendor backend when supported.
7. Motion vectors, depth, WPO and UI composition are acceptance-critical for temporal tech.
8. Do not enable every plugin at once. Integrate one backend per reviewed change and keep a working fallback.
9. Auto settings are capability-based and benchmark-informed, never a simple GPU-vendor switch.
10. Visual acceptance remains human-owned and is cross-linked with Visual History.

## Work packages

### R5.1 — Performance History + deterministic benchmark

Create a repeatable 60–90 second route benchmark with:

- exact route/camera path;
- deterministic WorldSpec / PCG seed;
- fixed weather and time-of-day;
- fixed resolution and preset;
- warm-up period before capture;
- exact SHA and hardware/driver identity;
- machine-readable CSV/JSON output;
- Unreal Insights trace when deeper diagnosis is required.

Required R5 benchmark metrics:

- FPS average;
- FPS 1% low;
- Frame p50/p95/p99/max;
- Game p50/p95/p99/max;
- Draw p50/p95/p99/max;
- RHI p50/p95/p99/max when available;
- GPU p50/p95/p99/max;
- frames over 16.667 ms;
- hitch count and hitch duration distribution;
- RAM and VRAM high-water marks where available;
- limiting timing domain;
- visible/relevant tree instance count when diagnostic instrumentation exists;
- loaded/generated PCG cell/component counts when relevant.

The benchmark must remain comparable across renderer experiments.

### R5.2 — Fixed-step presentation interpolation

The cycling simulation remains authoritative and fixed-step. Rendering must not be visually locked to the physics step.

Add a presentation interpolation layer between adjacent simulation snapshots for render-facing state such as:

- rider/bike transform;
- orientation and lean;
- wheel rotation;
- other presentation-only values proven to need interpolation.

The interpolation must not feed back into authoritative physics, route truth, save state or networking assumptions.

Acceptance:
- simulation determinism unchanged;
- smooth 60/90/120 Hz presentation is possible over the current fixed-step simulation;
- no visible extrapolation spikes during frame-time jitter.

### R5.3 — Forest and world render-cost pass

Evaluate, one controlled variable at a time:

- foliage **WPO disable distance**;
- wind complexity by distance;
- foliage/shadow distance policy;
- Virtual Shadow Map invalidation pressure from animated foliage;
- Nanite programmable-raster distance controls where appropriate;
- Nanite foliage features only as a measured R&D path when still experimental;
- LOD/Nanite/instancing policy of repeated trees/rocks;
- masked-material and overdraw pressure;
- section/material count on mass-repeated assets;
- Lumen **Medium** quality as a measured quality/performance option.

No visual downgrade is accepted solely because it is faster. Each material change must have Visual History evidence at the canonical capture points.

### R5.4 — PCG, streaming and world continuity

The long-term world may use PCG to create content, but runtime generation must have a bounded frame cost.

Evaluate:

- hierarchical PCG generation by content scale;
- large-grid static world elements vs small-grid local detail;
- runtime generation component limits / per-frame work budgets;
- editor-time persistence for content that does not need runtime generation;
- World Partition cell sizing and streaming radius;
- HLOD policy for distant terrain/forest/rocks;
- directional preload bias ahead of the rider where practical;
- unload policy behind the rider;
- traversal hitches and cell-transition spikes.

R5 may introduce measured prototypes. Stage 7 remains the full production world-scale/streaming acceptance stage.

### R5.5 — PSO and first-use stutter

Add a plan and proof for PSO/shader first-use behavior.

Measure:
- first appearance of new foliage/material/shadow/weather permutations;
- shader compilation or PSO stalls;
- warm vs cold run differences.

Adopt PSO precaching where it measurably reduces shipping-relevant stutter. The final packaged first-use gate remains part of the later release framework.

### R5.6 — Upscaler abstraction

Provide one project-facing selection layer:

```text
YACS Upscaler
  Native
  TSR
  DLSS
  FSR
  XeSS
```

Requirements:

- query actual runtime capability;
- expose only supported modes;
- preserve TSR as the universal fallback;
- support user override;
- keep quality mode mapping explicit;
- log selected backend and mode into Performance History;
- do not scatter vendor-specific conditions through gameplay/world code.

Initial rollout order:
1. Native + TSR baseline;
2. DLSS Super Resolution;
3. FSR Super Resolution;
4. XeSS Super Resolution.

Each backend receives the same deterministic benchmark and visual-artifact review.

### R5.7 — Temporal image-quality validation

For every temporal upscaler validate at minimum:

- foliage leaves and thin branches;
- grass;
- spokes and wheels;
- rider limbs and bike frame;
- road markings and thin geometry;
- rain/particles when introduced;
- translucency;
- disocclusion around moving rider/bike;
- WPO vegetation velocity;
- ghosting/trailing;
- shimmer;
- reactive-mask or equivalent integration requirements where relevant.

A backend that is faster but materially damages ride-time image stability may be rejected or restricted to a lower preset.

### R5.8 — Low-latency technologies

Integrate only when the relevant backend/hardware supports it:

- NVIDIA Reflex;
- AMD Anti-Lag 2;
- Intel XeLL.

Measure end-to-end behavior where practical and ensure these systems do not alter authoritative simulation timing.

### R5.9 — Dynamic resolution

Evaluate dynamic resolution only after the static Native/TSR/SR baselines are understood.

Rules:
- target the same 60 FPS product contract;
- use bounded screen-percentage ranges;
- record actual screen percentage over time;
- verify Nanite/LOD/streaming behavior under resolution changes;
- validate visual stability in forest and high-Alpine sectors.

Dynamic resolution is a stabilizer for transient GPU pressure, not permission to ignore expensive content.

### R5.10 — Frame Generation spike

Frame Generation is a separate, later R5 spike after real rendered performance is healthy.

Potential backends:
- DLSS Frame Generation;
- FSR Frame Generation;
- XeSS Frame Generation.

Rules:
- keep SR and FG backend selection logically separate;
- allow only combinations explicitly validated in the compatibility matrix;
- treat swapchain/presentation ownership conflicts as a first-class constraint;
- backend changes that require restart must say so in UI/settings;
- disable or safely handle FG in loading screens, pause/static screens and other unsupported presentation states;
- validate HUD/UI composition separately from world rendering;
- pair FG with the appropriate low-latency path when supported;
- report both **base rendered FPS** and **displayed/generated FPS**;
- never use generated FPS as the R5 hard acceptance metric.

On the RTX 2070 SUPER reference PC, DLSS Frame Generation is not a required capability. The reference machine remains valid because R5 acceptance is based on real rendered frames.

### R5.11 — Auto graphics policy

`Auto` must:

1. detect GPU/driver/runtime capabilities;
2. run or load a stable hardware benchmark;
3. select a base scalability preset;
4. choose an available upscaler;
5. choose an appropriate quality mode;
6. enable only validated low-latency technology;
7. leave unsupported options hidden/disabled;
8. allow user override;
9. never auto-enable an unvalidated FG/SR combination.

Do not implement:
`if NVIDIA => DLSS Performance`.

## Compatibility matrix

Maintain an explicit matrix for supported shipping combinations.

Example columns:

| SR backend | FG backend | Low-latency path | Runtime support query | Restart needed | Visual QA | Perf QA | Shipping status |
|---|---|---|---|---|---|---|---|
| TSR | Off | vendor/default | yes | no | pending | pending | baseline |
| DLSS SR | Off | Reflex | yes | no | pending | pending | candidate |
| FSR SR | Off | Anti-Lag 2 when supported | yes | no | pending | pending | candidate |
| XeSS SR | Off | XeLL when supported | yes | no | pending | pending | candidate |

Add FG rows only after the isolated FG spike begins.

## Performance History

R5 introduces **Performance History** as the durable companion to Visual History.

Preferred layout:

```text
docs/performance-history/
  README.md
  stage-3g/
    R4-closeout/
    R5-baseline/
    R5-dlss/
    R5-fsr/
    R5-xess/
```

Each record should contain, where available:

- Performance History ID;
- roadmap stage / slice;
- commit SHA;
- branch and PR;
- date;
- engine version;
- GPU/CPU/RAM;
- driver version;
- output resolution;
- internal resolution / screen percentage;
- preset;
- route/scenario ID;
- weather/time-of-day;
- PCG seed;
- upscaler backend/mode;
- FG backend/mode;
- low-latency backend;
- FPS average;
- FPS 1% low;
- Frame/Game/Draw/RHI/GPU percentile summary;
- VRAM/RAM;
- hitch summary;
- visible tree/foliage counts when instrumented;
- loaded/generated PCG cells/components when relevant;
- CI/workflow/run identifiers;
- paths/hashes for CSV, JSON, trace and screenshots;
- baseline delta;
- limiting-domain classification;
- known artifacts/regressions;
- acceptance decision.

## R5 acceptance

R5 is complete when:

- the accepted R4 baseline is preserved and reproducible;
- deterministic benchmark + Performance History exist;
- fixed-step simulation has a render interpolation strategy/proof;
- the dominant forest/world cost has been diagnosed and tuned without unacceptable visual regression;
- Native/TSR baseline remains healthy;
- supported DLSS/FSR/XeSS SR paths are capability-gated and benchmarked, or explicitly rejected with evidence;
- motion-vector/foliage/rider temporal-artifact checks are documented;
- low-latency paths are integrated where justified;
- dynamic resolution has a measured accept/reject decision;
- PSO/first-use work has a concrete measured path;
- FG has either a bounded spike result or an explicit defer decision;
- Auto settings are based on capabilities + benchmark evidence;
- all accepted changes keep the 1080p/60 hard product target on the reference PC.

## Non-goals

R5 does not:
- rewrite authoritative physics;
- replace the route model;
- turn runtime PCG into an MVP requirement;
- move full Stage 7 world-scale streaming acceptance earlier;
- require FG on the reference RTX 2070 SUPER;
- allow vendor tech to redefine the 60 FPS target;
- accept quality loss without visual evidence.
