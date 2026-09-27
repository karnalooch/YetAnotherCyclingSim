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
- Current visual-integration SHA: `07e0803bad809e87473ed3a461fdecf55e75ec76`
- Technical status: `CI_GREEN`
- Visual status: `VISUAL_REJECTED`

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
- CI run: **#412 / 36302963634**
- Proof artifact: `stage3g-full-validation-36302963634-1`

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

**VISUAL_REJECTED.** The scene visibly changes, but the boulder-derived valley masses are oversized and read as giant rock walls rather than believable valley landforms.

### 4900 m — Forest

The accepted R2 conifer forest remains recognizable and the road corridor remains readable. This capture is not the reason for rejection.

### 8000 m — High Alpine

**VISUAL_REJECTED.** Real rock geometry is visible, but the current massing is far too large and includes floating/overhanging formations around the road. The technical replacement succeeded; the composition and grounding did not.

## AFTER

`PENDING — awaiting visual acceptance`

No current NOW capture may be promoted to AFTER until the committed-SHA proof and human visual review both pass.

## Decision

- Technical acceptance: **YES**
- Visual acceptance: **NO**
- Visual change detected: **YES**
- Rejection reason: oversized / floating valley and high-Alpine boulder massing.
- Next step: reduce target massing scale, improve grounding and road sightline, rerun exact-SHA captures, then update the same Visual History entry. Automation of the durable triptych evidence pack is tracked in **#193**.
