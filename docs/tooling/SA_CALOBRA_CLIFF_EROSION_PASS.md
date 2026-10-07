# Sa Calobra Cliff / Erosion Pass

**Issues:** #429 Phase 1, #440 Phase 2A; child track of #368  
**Parent integration:** PR #381  
**Status:** Phase 1 selector complete; Phase 2A placement-handoff implementation/proof  
**Authority:** World Building Bible remains authoritative

## Purpose

Material Forge diagnostics established that the dramatic near-black cliff
cavities are dominated by dynamic shadows cast by steep/terraced Landscape
geometry rather than BaseColor, projection, material normals or a simple
ShadowSlopeBias defect.

The accepted Sa Calobra Landscape therefore remains the geographic and physics
ground truth. This pass adds a non-destructive presentation authority above it
for places where a heightfield cannot convincingly represent steep limestone
faces.

It does **not** smooth, erode, displace or replace Base_DTM.

## Authority split

| Layer | Owns |
|---|---|
| CNIG / accepted Base_DTM | geographic ground truth |
| Landscape | canonical terrain and physics support |
| Road + BOB | pavement, shoulder, cut/fill and earthworks authority |
| Cliff/Erosion selectors | presentation eligibility only |
| Phase 2A handoff | deterministic patch/sample identity, orientation and clearance metadata |
| Later PCG/PCGEx + meshes | visual cliff/scree representation |
| Material Forge | material appearance only |

No selector or handoff record authorizes a final mesh footprint by itself.

## Phase 1 frozen-grid classifier

The classifier consumes the existing 4033x4033 / 0.5 m EPSG:25831 products:

- elevation.tif;
- slope.tif;
- roughness.tif;
- exclusion-reasons.tif.

Protected reasons are pavement, shoulder envelope, BOB affected domain,
buildings, mapped water holdback and infrastructure holdback.

The pinned presentation hypothesis is:

- cliff: slope >= 50 degrees and 3x3 roughness >= 0.75 m;
- scree: slope 24-42 degrees, roughness >= 0.35 m, local cardinal-step
  proxy >= 0.5 m and within 8 m of an admitted cliff candidate;
- invalid terrain neighborhoods remain unknown;
- protected cells can never become cliff or scree candidates.

These are versioned art-selection parameters, not a geology claim.

The successful whole-area selector contains:

- cliff: 1,472,939 cells = 368,234.75 m2;
- scree: 508,659 cells = 127,164.75 m2.

The earlier proximity+slope-only experiment selected about 1.325 km2 as scree
and was rejected before mesh placement. The local-step gate and bounded cliff
proximity were added before Phase 1 acceptance.

## Canonical review footprint

Read-only UE evidence from #432 pins LandscapeComponent_230 to:

- X 378.0..441.0 m;
- Y 441.0..504.0 m;
- columns 756..882 inclusive;
- rows 882..1008 inclusive;
- 127x127 = 16,129 source cells.

Against the accepted Phase 1 selector this window contains:

- 2,522 cliff cells = 630.50 m2 = 15.64%;
- 1,175 scree cells = 293.75 m2 = 7.29%;
- 1,236 protected cells = 309.00 m2;
- 0 invalid terrain neighborhoods.

Phase 2A proof treats those values as an exact checkpoint, not an inferred
component ordering.

## Phase 2A placement handoff

scripts/assets/prepare_sa_calobra_cliff_erosion_handoff.py converts the
accepted Phase 1 rasters into deterministic placement metadata without opening
or saving Unreal.

### Cliff clustering

Cliff cells are clustered with true **8-connectivity** using a deterministic
run-length / union-find implementation. No SciPy dependency or one-cell-one-rock
mapping is introduced.

Every patch receives:

- exact source-cell footprint through cliff-patch-labels.tif;
- stable patch_id;
- deterministic spatial patch_index for this exact handoff only;
- inclusive source-grid bbox;
- cell count and area;
- centroid in local world metres and EPSG:25831;
- mean slope and roughness;
- maximum Phase 1 local-step proxy;
- mean elevation-gradient orientation;
- surface-normal proxy in local X east / Y south / Z up;
- downslope azimuth;
- conservative lower-bound clearance to road, shoulder, BOB and the broader
  PCG exclusion authority;
- exact overlap count with LandscapeComponent_230.

patch_id is derived from the fixed Sa Calobra grid identity plus the
component's deterministic top-left anchor cell. Small shape changes away from
that anchor therefore do not churn the durable identity. patch_index is not a
durable ID.

The first handoff size buckets are metadata only:

- micro: <8 m2;
- small: 8..<40 m2;
- medium: 40..<200 m2;
- large: 200..<1000 m2;
- massif: >=1000 m2.

No patch is discarded merely because it is small. Later authoring can decide
whether a micro patch becomes a single outcrop, is suppressed, or is absorbed
visually by another treatment.

### Orientation

Orientation comes from the frozen elevation grid.

For valid cardinal neighborhoods Phase 2A computes:

- dz/dX in the east axis;
- dz/dY in the south axis.

The patch record stores the mean gradient and the corresponding normal proxy.
This is an initial placement/facing guide, not a surveyed rock-face plane and
not permission to rotate randomly through 360 degrees. Later authoring may add
small controlled jitter around this source-derived orientation.

### Scree handoff

Phase 2A does not claim a final Poisson distribution.

Instead it creates stable scree seed candidates by dividing the source raster
into fixed 4x4-cell blocks (2x2 m) and choosing one admitted scree cell per
occupied block using a deterministic coordinate-derived SplitMix64 priority.

Every selected seed records:

- stable sample_id;
- row/column and block coordinates;
- local/EPSG position and elevation;
- slope, roughness and local-step proxy;
- lower-bound distance to cliff;
- lower-bound clearances to road, shoulder, BOB and the broader PCG exclusion
  authority;
- LandscapeComponent_230 membership.

This is deliberately a handoff density, not final talus density. Phase 2B or a
PCGEx graph may thin or expand presentation points only inside
scree-candidate==1, while preserving the same exclusion/clearance contract and
deterministic seed logic.

## Clearance contract

Selector membership only proves that the source cell itself is outside the
Phase 1 protected domain.

A later mesh or generated patch must also know:

- its horizontal footprint radius;
- any extra art/gameplay clearance.

The consumer must reject placement unless the complete footprint fits within
the conservative lower-bound clearance. Road, shoulder and BOB may never be
crossed. Unknown footprint radius is fail-closed.

The handoff additionally carries the existing PCG exclusion-distance lower
bound, which is intentionally broader than the Phase 1 six-bit presentation
protection and can reject other/unknown LiDAR domains as well.

## Phase 2A outputs

The handoff package contains:

- cliff-patch-labels.tif — exact integer patch footprint on the frozen grid;
- cliff-patches.jsonl — stable patch metadata;
- scree-samples.jsonl — deterministic scree seed metadata;
- cliff-erosion-handoff-manifest.json — source fingerprints, parameters,
  counts, Component_230 checkpoint, output hashes and consumer contract.

The JSONL files are ordered deterministically. Durable consumers persist
patch_id / sample_id, never ordinal indices.

## Proof

.github/workflows/sa-calobra-cliff-erosion-proof.yml now proves both phases on
the self-hosted YACS runner.

The workflow:

1. checks out the exact SHA;
2. verifies the retained normalized/PCG inputs;
3. runs Phase 1 and Phase 2A focused unit tests;
4. rebuilds the whole-area Phase 1 selectors;
5. pins the accepted whole-area cliff/scree counts;
6. builds Phase 2A twice from the same inputs;
7. requires identical handoff fingerprint and logical output hashes;
8. requires the exact LandscapeComponent_230 2522/1175/1236/0 checkpoint;
9. publishes the selector and handoff evidence.

No Unreal map is opened or saved by this proof. Canonical terrain mutation flags
must remain false.

## Phase 2B direction

Only after Phase 2A handoff review:

1. use LandscapeComponent_230 as the first visual spike;
2. consume stable patch IDs, exact patch labels, normals and clearance metadata
   through PCG/PCGEx;
3. instantiate source-consistent limestone cliff meshes / generated surface
   patches session-only;
4. add talus/scree under the Phase 2A seed and clearance contract;
5. keep gameplay collision off or query-only until separately admitted;
6. blend Landscape -> cliff with underlap/overlap, material transition,
   small-rock dressing and vegetation suppression;
7. rerun Lit and Lighting Only A/B captures plus black-cavity metrics;
8. expand beyond Component_230 only after visual and regression acceptance.

Erosion/breakup remains presentation geometry work. It is never written back
into the canonical Landscape without a separate explicit architecture change.
