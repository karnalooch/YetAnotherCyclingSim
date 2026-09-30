# Stage 3G — Environment Performance Proof

Status: **PASS**  
Date: **2026-09-27**  
Parent scope: **#80 — Stage 3G Reference Environment Pass**  
Implementation PR: **#197**  
Exact performance implementation SHA: `a59d1f3def60a7099c25ff15747f91c512fb71db`  
Workflow: **Stage 3G environment performance #13**  
Run ID: **36319841165**  
Evidence artifact: `stage3g-environment-performance-36319841165-1`

## Purpose

This proof closes the explicit Stage 3G environment-performance sanity gate for the accepted
R3 valley / forest / high-Alpine baseline. It is not a final Stage 7 optimization pass and it
does not replace later full-route RAM/VRAM, streaming, hitch, foliage-WPO or packaged-build
profiling.

The gate runs on the trusted `yacs-ue58` self-hosted reference runner and verifies the
documented MVP target at a real rendered **1920×1080** viewport.

## Acceptance contract

The threshold was fixed before measurement and was not reduced after failures.

Each canonical Stage 3G sector must independently satisfy:

- target: **60 FPS**;
- frame-time p95: **<= 16.6667 ms**;
- GPU-time p95: **<= 16.6667 ms**;
- sampled frames above 16.6667 ms: **<= 5%**;
- minimum frame and positive GPU sample counts;
- reference GPU identity: **RTX 2070 Super**;
- exact-SHA checkout and Git LFS verification;
- non-zero UnrealEditor exit is a hard failure;
- missing GPU timing is a hard failure.

GPU timing is collected through UE 5.8 `FRHIGPUFrameTimeHistory` from `GPUProfiler.h`.
The older `GetAverageUnitTimes()` value is retained only as supplementary/fallback evidence.

## Result

| Sector | Distance | Frame p95 | GPU p95 | Average FPS | Frames over 16.67 ms |
|---|---:|---:|---:|---:|---:|
| Valley | 1200 m | **9.032 ms** | **8.063 ms** | **124.06 FPS** | **0.00%** |
| Forest | 4900 m | **11.443 ms** | **10.641 ms** | **94.52 FPS** | **0.00%** |
| High Alpine | 8000 m | **9.476 ms** | **7.281 ms** | **128.54 FPS** | **0.00%** |

All three sectors passed the unchanged 60 FPS budget. The current worst frame-time p95 is
the forest sector at **11.443 ms**, leaving approximately **5.224 ms** below the 16.667 ms
budget.

## Provenance and failure history

The gate intentionally failed closed while instrumentation was being established:

- run #1 measured acceptable frame timing but rejected the proof because GPU samples were
  missing;
- intermediate runs exposed source-format/include problems and were not accepted as
  performance evidence;
- no threshold was relaxed to obtain a green result;
- run #13 is the first accepted proof using the UE 5.8 RHI GPU frame-time history.

The ordinary `CyclingSim CI` for the same implementation SHA also completed successfully
(run **#434 / 36319843770**).

## Scope of validation

This proof is sufficient to close the **aggregate Stage 3G environment-performance sanity**
required by the Technical UE Asset Ledger for `PCG_Valley` and `PCG_HighAlpine`, because
their deterministic persistence/reload, route-clearance integration and visual acceptance
were already proven by R3 / PR #192 / Visual History `VH-3G-R3-001`.

It does **not** by itself mark individual source assets such as `Sparse Grass`,
`Rocky Terrain`, `Forest Ground 03` or `Boulder 01` as fully `validated`. Their source
asset lifecycle still requires the explicit per-asset LOD/Nanite/instancing checks defined
in `ASSET_PLAN.md`.

## Performance Framework handoff

This document remains the historical Stage 3G environment proof. Cross-stage performance policy now lives in:
- [`performance/PERFORMANCE_FRAMEWORK.md`](performance/PERFORMANCE_FRAMEWORK.md);
- [`performance/BUDGETS.md`](performance/BUDGETS.md).

The current CSV already records Frame, Game, Draw, RHI and GPU timing. Performance Framework **v1.0** must expose percentile summaries for all five domains and use the forest 4900 m sector as the first controlled A/B diagnostic client without invalidating this accepted historical proof.

## Next performance work

Stage 3G revision **R5 — Smooth Frame / Rendering Tech** now pulls forward a bounded, evidence-driven performance pass using this accepted proof plus the final R4 closeout as baselines. R5 is defined in [`performance/STAGE3G_R5_RENDERING_TECH.md`](performance/STAGE3G_R5_RENDERING_TECH.md) and records durable evidence through [`performance-history/README.md`](performance-history/README.md).

This historical R3 proof remains immutable evidence: R5 must compare against it or the accepted R4 closeout rather than rewriting these results.

Later Stage 7 / MVP gates still include:

- full-route Game / Render / GPU baselines;
- RAM and VRAM;
- hitch percentiles and streaming stalls;
- foliage wind / Animation LOD;
- HLOD / pop-in / skyline streaming proof;
- packaged-build PSO / first-use stutter;
- final comparison against the 1080p/60 reference baseline recorded here.
