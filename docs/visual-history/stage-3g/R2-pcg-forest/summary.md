# VH-3G-R2-001 — Stage 3G / R2 — PCG Forest

## Goal

Replace the forest placeholder silhouette with a validated real conifer and establish deterministic, route-aware PCG forest authoring without letting presentation own route or physics truth.

## Roadmap

- Stage: **Stage 3G**
- Version: **R2**
- PR: **#162**
- Result: **merged**

## Baseline — BEFORE

- Accepted baseline: Stage 3G R1
- Main commit: `91c1150fa63488028054b17b36ce6aee1bb2e8d7`
- Visual status: `VISUAL_ACCEPTED`

## Current / accepted R2

- Branch: `feat/stage3g-pcg-forest-r2`
- Accepted source SHA: `fb5f900c86066aef475dcc3a8fd1a4365793433c`
- Merge SHA: `fd77094ffe0c8f29c3bd9949ba22079fc73fc1c5`
- Technical status: `MERGED`
- Visual status: `VISUAL_ACCEPTED`

## Technical proof

- CyclingSim CI run: **#398 / 36299298530**
- Stage 3G full validation: **PASS**
- Automation/build: **PASS**
- Fresh Load: **PASS**
- Map Check: **0 errors / 0 warnings**
- LFS fsck: **PASS**
- Visual Capture: **PASS**
- Proof artifact: `stage3g-full-validation-36299298530-1`

## World-generation inputs

- Seed: `42017`
- Route clearance: `4.0 m`
- Graphs: `PCG_RouteExclusion`, `PCG_Forest`
- Forest range: `3700–6200 m`
- Forest density: `0.72`
- Route truth: `FRouteGeometryProfile`

## Asset delta

- Validated conifer: `SM_Stage3G_FirSaplingMedium`
- Forest presentation no longer relies on Engine Cone/Cylinder placeholders for the accepted 4900 m proof.

## Visual review

The 4900 m capture visibly contains the validated conifer and retains a clear road corridor. This state is the accepted BEFORE baseline for R3.

R2 predates the repository Visual History convention. Its genuine R1/R2 source captures were recovered from the original CI proof artifacts and are now retained as repository triptychs under `captures/`, with SHA-256 values recorded in the manifest. The AFTER panel explicitly reuses the accepted R2 render because the merge introduced no visual delta.

## Decision

- Technical acceptance: **YES**
- Visual acceptance: **YES**
- Visual change detected: **YES**
- Next step: Stage 3G R3 valley/high-Alpine completion.
