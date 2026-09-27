# VH-3G-R4-001 — Stage 3G R4 — route-aware terrain coherence

## Goal

Make the road, terrain support and biome dressing read as one coherent landscape rather than a road ribbon laid over a flat slab with independent rocks/trees.

## Current engineering state

- Issue: #199
- PR: #200 (Draft)
- implementation authoring SHA: `10268c9f…`
- persisted map commit: `f5e4c823…`
- trusted authoring workflow: #1 / `36326068660` — **PASS**
- persisted map: `Content/Prototype/Maps/L_CyclingTest.umap`
- map LFS object changed from `0ceef3d7…` / 3,321,104 bytes to `b3305bcf…` / 3,491,033 bytes

R4 replaces one flat terrain support slab per 50 m slice with seven deterministic route-aware bands: one flat road corridor plus three rising shoulder bands on each side.

## Surface profile

- protected presentation corridor: ±8 m, flat beside the road;
- valley support: 110 m half-width, up to +10 m rise;
- forest support: 60 m half-width, up to +8 m rise;
- high-Alpine support: 220 m half-width, up to +28 m rise;
- smooth cubic interpolation between corridor and outer support;
- simulation truth remains `FRouteGeometryProfile`; terrain/PCG transforms remain presentation-only.

## Dependency ordering

The research-driven representative forest is intentionally being accepted first in #201 / PR #202.

R4 final visual acceptance must therefore **rebase onto the accepted target-density forest baseline before NOW captures are accepted**. This prevents a technically correct terrain pass from being visually accepted against the old sparse forest proxy.

## BEFORE

Current accepted baseline: `VH-3G-R3-001` / merged `02ff23f0…`.

## NOW

**PENDING.** The map is persisted, but the final R4 NOW must be captured after #202 is accepted and R4 is synced to that baseline.

## AFTER

**PENDING — awaiting visual acceptance.**

## Remaining gates

- normal PR / Aggregate CI on a human-authored head;
- sync with accepted #202 forest baseline;
- exact-SHA Stage 3G full proof / Fresh Load / Map Check / LFS;
- 1920×1080 captures at 1200 / 4900 / 8000 m;
- unchanged 60 FPS environment performance gate;
- forest sector must also remain compatible with the stricter representative-forest budget established by #201.
