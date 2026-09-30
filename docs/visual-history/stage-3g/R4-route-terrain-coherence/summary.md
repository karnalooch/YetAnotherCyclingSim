# VH-3G-R4-001 — Stage 3G R4 — route-aware terrain coherence

## Goal

Make the road, terrain support and biome dressing read as one coherent landscape rather than a road ribbon laid over a flat slab with independent rocks/trees.

## Current engineering state

- Issue: #199
- PR: #200 — **MERGED**
- accepted target-density forest dependency: PR #202 — **MERGED** as `88e417e6ab828a290c335cb7bbaa684f3027a4ce`
- post-#202 R4 integration commit: `55f222ff96a286f15f0259dfc74e50deba646036`
- self-hosted workspace hardening: `bd2d5e58f141e3084edaaf07eb0fb9ed1f5edd53`
- lock-safe authoring contract HEAD: `9928491e7b13a9d32d3c0d05e63dc46ef1dcf49a`
- lightweight PR CI: #527 / `36348293024` — **PASS**
- trusted R4 authoring: run #5 / `36348289844` — **PASS**
- persisted route-aware map commit: `fc0f22a2588c9ccb97ec5e469bbe911748e2e413`
- persisted map: `Content/Prototype/Maps/L_CyclingTest.umap`
- map LFS object changed from `017766cf088477f0d810bee4a3c320b05c18c931aff1901e0443fbaa1d40798b` / 3,716,048 bytes to `c4794f4dc182c3151dad0beb6193bc208339474a61fbdf337a139b529d81c095` / 3,879,249 bytes

R4 replaces one flat terrain support slab per 50 m slice with seven deterministic route-aware bands: one flat road corridor plus three rising shoulder bands on each side.

The post-#202 integration is implemented in both presentation paths:
- persisted target-density forest HISM transforms consume the same route-relative `SurfaceRiseM`;
- `Stage3GForestCandidatesSettings` applies the same `SurfaceRiseM` before emitting PCG transforms;
- the canonical 4 m route exclusion remains fail-closed;
- the road-adjacent presentation corridor remains flat at ±8 m;
- simulation/physics truth remains `FRouteGeometryProfile`.

## Surface profile

- protected presentation corridor: ±8 m, flat beside the road;
- valley support: 110 m half-width, up to +10 m rise;
- forest support: 60 m half-width, up to +8 m rise;
- high-Alpine support: 220 m half-width, up to +28 m rise;
- smooth cubic interpolation between corridor and outer support;
- terrain, PCG and dressing transforms are presentation-only.

## Dependency ordering

The #202 dependency is resolved: the representative `target_density_v2` forest is on `main` in merge commit `88e417e6…`, and #200 is based on that merge. The R4 branch then integrated the shared presentation surface and re-authored the canonical map on the synced forest baseline.

The historical R3.1 Visual History record still needs a small backfill so its metadata reflects the already-completed #202 merge. That documentation debt does not change the actual R4 branch ancestry or the persisted forest/map state.

## BEFORE

Current accepted pre-R4 world baseline: `VH-3G-R3-001` / merged `02ff23f0…`.

Representative forest dependency merged through #202 / `88e417e6…`.

## NOW

**TECHNICALLY MERGED — POST-MERGE VISUAL REVIEW REJECTED AS STAGE 3G CLOSEOUT.**

PR #200 merged as `e1653227ff33005be70c979e3c6f038efbf57c0e`. The route-aware support and PCG grounding remain valid technical work. Human review of the resulting current world found that the scene still reads as a greybox/flat support world rather than a convincing Alpine reference environment: insufficient macro terrain, weak skyline/mountain mass, sparse local dressing, prototype road/shoulder treatment and insufficient atmospheric depth.

This is not a request to revert R4. It creates a bounded **R4.1 Alpine Visual Recovery** follow-up.

Canonical review points remain:
- 1200 m — valley / road-ground coherence;
- 4900 m — critical target-density forest / shoulder coherence;
- 8000 m — high-Alpine massing / road-ground coherence.

## AFTER

**NOT ACCEPTED.** R4 has no accepted `AFTER` visual baseline. The next accepted `AFTER` must come from R4.1, not from copying the technically merged R4 state.

## Follow-up / R4.1 gate

- preserve PR #200 as the technical route-grounding milestone;
- execute [`../../../STAGE3G_R4_1_ALPINE_VISUAL_RECOVERY.md`](../../../STAGE3G_R4_1_ALPINE_VISUAL_RECOVERY.md);
- first accept a 300–500 m / 1200 m golden terrain vertical slice;
- then propagate the accepted language to 1200 / 4900 / 8000 m and the full corridor;
- freeze the human-accepted exact SHA and produce Visual History `AFTER`;
- rerun unchanged performance and final Stage 3G closeout proof on that tree;
- only the accepted R4.1 tree may become the immutable pre-optimization baseline for R5.
