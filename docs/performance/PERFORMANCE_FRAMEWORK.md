# YACS Performance Framework

**Status:** active cross-stage engineering contract  
**Version:** roadmap defined; v1.0 implementation starts in Stage 3G  
**Reference target:** 1920×1080 / 60 FPS on the project reference PC

## Purpose

YACS treats performance as a continuously measured engineering contract, not as a final optimization pass.

The framework provides one reusable path for:
- exact-SHA performance capture;
- Frame / Game / Draw / RHI / GPU timing;
- percentile summaries and baseline comparison;
- bottleneck-domain classification;
- stage-specific diagnostics;
- warning and hard acceptance budgets;
- durable evidence that can be compared with Visual History.

The framework does not replace visual acceptance. A change can be faster and visually rejected, or visually better and performance-rejected.

## Measurement cadence

Performance is continuous as a contract, but **heavy measurement is milestone-driven rather than commit-driven** for world-art iteration.

During a Draft world-stage PR, vegetation/water/material/lighting/terrain-dressing changes use lightweight validation. The expensive performance benchmark is run when a visual candidate has been accepted by the owner and its exact SHA is frozen as a performance checkpoint.

After that checkpoint:

- optimization must preserve the accepted visual intent unless a new visual decision is recorded;
- any material visual/runtime change invalidates the checkpoint;
- Stage closeout runs the full Unreal/asset/world proof;
- if the closeout tree is unchanged from the accepted performance tree, performance is not rerun solely because the full proof ran.

This cadence is defined operationally in [`../CI_VALIDATION_TIERS.md`](../CI_VALIDATION_TIERS.md).

## Version roadmap

| Version | Roadmap integration | Primary scope | New evidence |
|---|---|---|---|
| **v1.0 — Frame Budget Core** | **Stage 3G / now, including 3G-R5** | Generalize the existing environment sampler and analyzer. Forest is the first client; R5 adds deterministic rendering-tech comparisons without inventing a new framework version. | p50/p95/p99/max for Frame, Game, Draw, RHI, GPU; exact-SHA JSON/CSV; limiting-domain classification; baseline delta; forest A/B diagnostics; R5 Performance History. |
| **v1.1 — Scenario + Visual Delta** | **Stage 5** | Add reusable named scenarios around session/HUD flow without turning UI into a performance subsystem. | Scenario manifests, BEFORE/NOW timing deltas, Visual History performance summary, regression warning annotations. |
| **v2.0 — Rider / Animation Budget** | **Stage 6** | Measure rider mesh, animation, Control Rig, IK and cameras. | animation/game-thread timing, rider significance inputs, skeletal LOD/update-rate evidence, near/medium/far rider scenarios. |
| **v2.1 — World Scale + Streaming** | **Stage 7** | Measure production environment density and traversal rather than only fixed viewpoints. | RAM/VRAM, streaming/HLOD transition evidence, hitch percentiles, visible-instance/LOD distribution, long corridor traversal. |
| **v3.0 — Weather / Effects** | **Stage 8** | Add worst-case rain, wet road, fog, wind, shadows, Niagara/audio-relevant presentation scenarios. | weather delta reports, shader/material pressure, shadow/WPO diagnostics, representative worst-case scene gate. |
| **v4.0 — MVP Release Gate** | **Stage 10** | Final packaged-build, full-route acceptance on reference hardware. | start-to-finish run, packaged build, RAM/VRAM peaks, hitch/streaming evidence, PSO/first-use stutter proof, final regression baseline. |

Versions are capability milestones, not independent product stages. They are implemented only when the corresponding roadmap stage creates a real measurement need.

**Naming note:** `3G-R5` is a revision inside product Stage 3G. It is not the same thing as product **Stage 5**, which remains the trigger for Performance Framework v1.1.

## Stage 3G R5 specialization

The concrete Stage 3G R5 plan lives in [`STAGE3G_R5_RENDERING_TECH.md`](STAGE3G_R5_RENDERING_TECH.md).

R5 uses v1.0 rather than creating a speculative new framework version. It adds these concrete clients of the existing framework:

- deterministic 60–90 second route benchmark;
- durable **Performance History** records;
- average FPS + 1% low alongside percentile timing;
- RAM/VRAM and hitch evidence where available;
- exact-SHA Native/TSR/DLSS/FSR/XeSS comparisons;
- temporal artifact review tied to the same exact SHA;
- capability-gated low-latency backend evidence;
- dynamic-resolution experiment records;
- Frame Generation records that always keep base-rendered FPS separate from generated/displayed FPS.

Performance History format is defined in [`../performance-history/README.md`](../performance-history/README.md).

R5 may pull forward limited measurement capability that later becomes mandatory in v2.1/v4.0 (for example VRAM, hitches or first-use stutter), but doing so does not move the full Stage 7 or Stage 10 acceptance gates earlier.

## v1.0 contract

The existing Stage 3G sampler already captures:
- frame time;
- game-thread time;
- render/draw-thread time;
- RHI-thread time;
- GPU frame time.

v1.0 must expose these values in the generated summary instead of reducing acceptance evidence to Frame + GPU only.

Required aggregate statistics per scenario:
- sample count;
- p50;
- p95;
- p99;
- maximum;
- average where useful;
- frames above the 60 FPS budget;
- exact branch / commit SHA;
- resolution and hardware identity.

A simple limiting-domain classification may identify the largest p95 timing domain. It is diagnostic only; it must not pretend to explain root cause automatically.

## Stage 3G forest diagnostics

The forest at the canonical 4900 m capture point is the first v1.0 diagnostic client.

The diagnostic path should support controlled A/B runs for:
- density;
- shadow casting;
- selected LOD policy / forced LOD experiments;
- masked foliage contribution where technically practical;
- other single-variable experiments justified by a measured bottleneck.

When accessible without invasive runtime changes, evidence should also include:
- visible or relevant instance count;
- LOD0/LOD1/LOD2/LOD3 distribution;
- primitive/section counts;
- shadow-casting instance count.

These diagnostics are not permanent runtime telemetry requirements.

## Asset performance gate

Mass-repeated assets require context-aware validation rather than a triangle-count-only rule.

Recommended lifecycle:

```text
SOURCE_FOUND
  -> LICENSE_OK
  -> STATIC_AUDIT_OK
  -> LOD_PROFILED
  -> MICROBENCH_OK
  -> WORLD_ACCEPTED
```

A high-poly asset may be acceptable if its measured world cost satisfies the project budget. A low-poly asset may still be rejected because of materials, masked overdraw, shadow cost, sections, component count or other measured costs.

The source-asset ledger remains owned by `docs/ASSET_PLAN.md`. This framework defines only the performance evidence attached to that lifecycle.

## Performance History integration

Performance History is the durable machine- and human-readable record of exact-SHA performance evidence. It complements, rather than replaces, Visual History.

For each accepted R5 experiment, prefer a record containing:
- scenario identity and deterministic seed;
- hardware/driver/engine identity;
- resolution, preset, screen percentage and backend selection;
- FPS average and 1% low;
- Frame/Game/Draw/RHI/GPU percentile summary;
- hitch and RAM/VRAM evidence when available;
- baseline deltas;
- known visual artifacts;
- accept/reject/defer decision.

Frame Generation results must report base-rendered FPS separately from displayed/generated FPS. Hard acceptance is based on the real rendered path.

## Visual History integration

For material visual changes, Visual History remains the visual source of truth.

Where a performance proof exists for the same exact SHA, the evidence pack should include a compact delta such as:

```text
BEFORE              NOW
Frame p95  13.2 ms  12.1 ms
Draw  p95  11.8 ms  10.4 ms
GPU   p95  10.9 ms  11.2 ms

delta:
Frame -1.1 ms
Draw  -1.4 ms
GPU   +0.3 ms
```

Visual acceptance remains human-owned. Performance automation must not decide whether the scene looks better.

## Ownership and repository placement

The framework is YACS-specific and remains in this repository.

Preferred layout as capabilities are introduced:

```text
docs/performance/
  PERFORMANCE_FRAMEWORK.md
  BUDGETS.md
  STAGE3G_R5_RENDERING_TECH.md

docs/performance-history/
  README.md
  ... exact-SHA stage/slice records ...

Source/YetAnotherCyclingSim/Private/Tests/
  ... reusable sampler + scenario proofs ...

scripts/
  perf/
    ... analysis / comparison / reporting ...
  ue/
    ... Unreal proof launchers ...

.github/workflows/
  ... performance regression workflows ...
```

Do not extract this to `engineering-platform` until another real consumer proves that the implementation is generic.

Do not introduce a dedicated Unreal plugin merely to host the first versions of this framework. Prefer small reusable test/runtime-proof helpers first.

## Definition of Done by version

### v1.0
- all five timing domains summarized;
- baseline comparison is machine-readable;
- forest 4900 m can run controlled A/B diagnostics;
- warning/hard budgets are read from the documented contract;
- current Stage 3G proof remains reproducible.

### v1.1
- named scenarios are reusable outside Stage 3G;
- Visual History can reference compact performance deltas;
- Stage 5 changes can be measured without bespoke one-off scripts.

### v2.0
- rider + animation + camera costs have representative scenarios;
- skeletal/animation scalability decisions are supported by measurements;
- no permanent per-frame diagnostic instrumentation is required in shipping gameplay.

### v2.1
- representative route traversal reports streaming and hitch behavior;
- RAM/VRAM are recorded;
- world/HLOD/foliage decisions can be compared against a stable baseline.

### v3.0
- dry and representative worst-weather scenarios are compared;
- shadow/WPO/material/VFX regressions are visible in evidence;
- weather cannot silently consume the remaining MVP frame headroom.

### v4.0
- packaged full-route proof passes final locked budgets;
- first-use/PSO and streaming hitches are covered;
- the final reference baseline is durable and reproducible.
