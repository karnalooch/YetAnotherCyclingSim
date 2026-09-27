# VH-3G-R3-001 — Stage 3G / R3 — Valley + High-Alpine PCG

## Goal

Complete the valley and high-Alpine presentation using deterministic route-aware worldgen, remove obvious Engine Cone biome massing, preserve the accepted R2 forest sector and prove the result visually at stable route cameras.

## Roadmap

- Stage: **Stage 3G**
- Version: **R3**
- Issue: **#187**
- PR: **#192 — draft**

## Baseline — BEFORE

- Accepted baseline: Stage 3G R2
- Merge commit: `fd77094ffe0c8f29c3bd9949ba22079fc73fc1c5`
- Visual status: `VISUAL_ACCEPTED`

## Current — NOW

- Branch: `feat/stage3g-pcg-biomes-r3`
- Current visual-integration SHA: `58c89674656ddec1bce9473547d366f6798dcfb5`
- Technical status: `CI_GREEN`
- Visual status: `VISUAL_ACCEPTED`

## Important rejected checkpoint

Commit `0148f894e9036dfe6b7c1d7176922e65e7024a65` passed CyclingSim CI **#408 / 36302003337** including the full Stage 3G proof.

It was **not visually accepted**.

Reason: `PCG_Valley` and `PCG_HighAlpine` were persisted and technically correct, but the rendered reference map did not visibly consume them. The 1200 m and 8000 m captures remained effectively the R2 scene.

This checkpoint is intentionally preserved in Visual History because it demonstrates why technical and visual acceptance are separate gates.

## Current visual-integration change

The active R3 revision replaces the remaining valley/high-Alpine Engine Cone massing with bounds-aware instances of the validated `SM_Stage3G_Boulder` while keeping deterministic instance counts and the R2 forest baseline intact.

## Technical proof

- Unreal build + scoped Automation: **PASS**
- Stage 3G full validation: **PASS**
- Fresh Load: **PASS**
- Map Check: **0 errors / 0 warnings**
- LFS fsck: **PASS**
- Visual Capture: **PASS**
- Aggregate CI gate: **PASS**
- CI run: **#417 / 36305204327**
- Proof artifact: `stage3g-full-validation-36305204327-1`
- Ground-support contract: **PASS**

## Visual iteration history

- **#408 / 0148f894** — technical PASS, visual reject: PCG graph output was not visibly consumed.
- **#412 / 07e0803b** — technical PASS, visual reject: real massing visible but oversized/floating.
- **#415 / 7de2cc46** — technical PASS, visual reject: scale bounded, but distant massing still lacked terrain support.
- **#417 / 58c89674** — technical PASS, **visual accepted NOW**: massing is grounded on supported presentation terrain.

## World-generation inputs

- Seed: `42017`
- Route clearance: `4.0 m`
- Graphs: `PCG_Valley`, `PCG_RouteExclusion`, `PCG_Forest`, `PCG_HighAlpine`
- Valley: `0–3700 m`, rock density `0.10`
- Forest: `3700–6200 m`, density `0.72`
- High Alpine: `6200–10000 m`, rock density `0.65`
- Route truth: `FRouteGeometryProfile`

## Asset delta

- `SM_Stage3G_Boulder` — validated real mesh for valley/high-Alpine massing and rock dressing.
- `SM_Stage3G_FirSaplingMedium` — retained accepted forest asset.
- Targeted placeholders removed from visible biome massing: Engine Cone valley ridge / near-Alpine / distant mountain presentation.

## Visual acceptance criteria

### 1200 m — Valley

**VISUAL_ACCEPTED for R3 baseline.** Real boulder massing is grounded, kept away from the road and reads as valley-side landform dressing rather than floating geometry.

### 4900 m — Forest

**VISUAL_ACCEPTED / preserved baseline.** The R2 conifer forest and road-clearance readability remain intact.

### 8000 m — High Alpine

**VISUAL_ACCEPTED for R3 baseline.** Real rocks are grounded on widened high-Alpine presentation terrain, remain outside the road corridor and no longer float above the horizon.

This is still a Stage 3G reference baseline, not final Stage 7 environment art: the road, broad terrain forms, atmosphere and overall scene composition remain intentionally open for later polish.

## AFTER

`PENDING — awaiting visual acceptance`

No current NOW capture may be promoted to AFTER until the committed-SHA proof and human visual review both pass.

## Decision

- Technical acceptance: **YES**
- Visual acceptance: **YES — NOW accepted**
- Visual change detected: **YES**
- Rejection reason: **none for 58c89674**
- Next step: sync #192 with current `main`, run one final exact-SHA proof, merge, then capture merged `main` as AFTER and close VH-3G-R3-001.
