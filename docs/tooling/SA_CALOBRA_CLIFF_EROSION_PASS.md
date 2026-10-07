# Sa Calobra Cliff / Erosion Pass

**Issue:** #429, child of #368  
**Status:** Phase 1 selector foundation in progress  
**Authority:** World Building Bible remains authoritative

## Purpose

The accepted Sa Calobra Landscape is a source-faithful heightfield. Material
Forge diagnostics established that the dramatic near-black cliff cavities are
dominated by dynamic shadows cast by steep/terraced Landscape geometry rather
than by BaseColor projection or material normals.

This pass does **not** rewrite the DTM to make it prettier. It creates a
non-destructive presentation layer for places where a heightfield cannot
convincingly represent steep limestone faces.

## Authority split

| Layer | Owns |
|---|---|
| CNIG/accepted Base_DTM | geographic ground truth |
| Landscape | canonical terrain/physics support |
| Road + BOB | pavement, cut/fill and earthworks authority |
| Cliff/Erosion selectors | presentation eligibility only |
| Later PCG/PCGEx + meshes | visual cliff/scree representation |
| Material Forge | material appearance only |

The selector output is never a new DEM and never authorizes terrain smoothing.

## Phase 1 frozen-grid classifier

The classifier consumes the existing 4033×4033 / 0.5 m EPSG:25831 products:

- `elevation.tif` — native accepted terrain elevation;
- `slope.tif` — centered finite-difference slope in degrees;
- `roughness.tif` — 3×3 max-minus-min local relief;
- `exclusion-reasons.tif` — conservative presentation holdbacks.

Protected reasons are pavement, shoulder envelope, BOB affected domain,
buildings, mapped water holdback and infrastructure holdback.

The first explicit presentation hypothesis is:

- cliff candidate: slope >= 50° and 3×3 roughness >= 0.75 m;
- scree candidate: slope 24–42°, roughness >= 0.35 m, local cardinal-step
  proxy >= 0.5 m and within 8 m of an admitted cliff candidate;
- invalid terrain neighborhoods remain unknown;
- protected cells can never become cliff or scree candidates.

These thresholds are versioned art-selection parameters, not a geology claim.
The first whole-area proof showed that proximity+slope alone selected about
1.325 km² as scree, which was too broad for a conservative presentation
selector. The 0.5 m local-step gate and 8 m proximity bound were therefore added
before any mesh placement. They are intentionally reviewable and remain
candidate thresholds.

Two additional diagnostics are retained but do not themselves grant selection:

- local curvature proxy: absolute centre elevation minus mean cardinal-neighbour
  elevation;
- local step proxy: maximum cardinal elevation delta.

They help identify abrupt heightfield response and likely terracing without
claiming whether the source shape is natural or artificial.

## Outputs

`prepare_sa_calobra_cliff_erosion.py` produces:

- `cliff-candidate.tif`;
- `scree-candidate.tif`;
- `curvature-step-proxy.tif`;
- `cliff-distance-lower-bound.tif`;
- `cliff-erosion-selectors.png`;
- `cliff-erosion-manifest.json`.

All raster outputs retain the frozen native grid. The manifest records source
hashes, parameters, counts, semantics and a deterministic fingerprint.

## Proof

The self-hosted workflow
`.github/workflows/sa-calobra-cliff-erosion-proof.yml` runs against the
retained frozen-grid cache under the YACS runner workspace, executes focused
unit tests and publishes the whole-area selector package.

Phase 1 proof does not save/open-modify the accepted map. Exact
`LandscapeComponent_230` bounds are a separate UE read-only evidence step;
until that is added, the manifest explicitly marks component-local statistics
as pending instead of guessing row/column ownership.

## Phase 2 direction

After selector review, later implementation may:

1. consume selector==1 cells through PCG/PCGEx;
2. place source-consistent cliff-face meshes or generated surface patches;
3. place talus/scree only in the bounded scree domain;
4. apply erosion/breakup to generated presentation geometry only;
5. blend the representation into the Landscape while preserving road/BOB
   clearances;
6. prove reload, visual quality and performance before #368 acceptance.

The canonical Landscape remains available underneath as ground/physics truth.
No Phase 2 consumer may move roads, change route physics or persist an eroded
replacement DTM without a separate explicit architecture decision.
