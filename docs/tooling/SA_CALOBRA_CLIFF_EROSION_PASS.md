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

## Phase 2A observed proof result

Exact-head Phase 2A proof on the implementation produced the following
deterministic handoff identity:

- handoff fingerprint:
  `400353b34a2e5310e9acce984efb95863d95dfe0286afdb8b6b64de9331428ef`;
- 52,262 cliff patches over the 1,472,939 admitted cliff cells;
- patch classes:
  - micro: 48,516;
  - small: 2,962;
  - medium: 623;
  - large: 126;
  - massif: 35;
- 269,250 deterministic Phase 2A scree seed candidates over 508,659 admitted
  scree cells;
- `LandscapeComponent_230`: 97 intersecting cliff patches and 521 scree seed
  candidates, while retaining the exact 2,522 cliff / 1,175 scree / 1,236
  protected / 0 invalid source-cell checkpoint;
- replay A/B produced the same handoff fingerprint and logical output hashes.

The distribution is intentionally treated as evidence, not an asset count.
48,516 of 52,262 cliff patches (about 92.8%) are micro patches. A Phase 2B
consumer must therefore classify, thin, merge visually or treat micro patches
as small outcrops/material-breakup hints. It must **not** instantiate one
full-size cliff mesh per patch. Likewise, 269,250 scree seeds are an
authoring/sampling handoff, not a request for 269,250 rendered rocks.

The exact proof artifact was about 79 MiB compressed and includes the Phase 1
selector package plus Phase 2A label/JSONL evidence. This is acceptable for the
bounded engineering proof, but later production handoff formats should avoid
shipping the proof archive as runtime content.

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

## Phase 2C bounded topology experiment — Issue #445 / PR #446

The active Component 230 experiment preserves the accepted Landscape,
classifier and 0.5 m pavement/shoulder/water exclusions. Its frozen plan has
2,611 cliff cells, 1,237 scree cells and 1,017 admitted 1 m skin cells.
Fourteen semantic 8-connected clusters form 19 physical polygon islands.

The graph passes exact cell squares directly to PCGEx Clipper2 Triangulate,
using consolidated inputs and EvenOdd fill. It does not use Path Subdivide or
Decompose / Cluster Surface. GeometryScript tessellates each physical triangle
component independently with ceil(maxEdge / 150 cm) - 1.

PCGEx remains authoring-only at revision
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`. The bounded compatibility experiment
uses Union into oriented flat contours followed by standard Triangulate, and
fixes HorizontalBetween to inspect every fixed horizontal boundary, including
ones not yet activated on the current scanline. Checking active edges alone
allows a diagonal to cross a later boundary. The flat-union change alone did
not fix the real input: it still returned 1,088 m2 instead of 1,017 m2.
The fill rule, Z callback and Delaunay setting remain unchanged.
The failed reversed-winding experiment is retired. Bootstrap verifies the
patch SHA-256 and complete normalized patched-source SHA-256, allowing only
that source file to differ from the pinned revision.

Standalone C++ probes pass for two holes, a nested island and a cell union with
holes, using the pinned Clipper implementation with minimal Unreal macro stubs.
The reduced 14-cell concave regression returned 175,000 cm2 instead of
140,000 cm2 before the horizontal-boundary fix. The corrected real 1,017-cell
probe produces 622 triangles and 19 islands, exactly 1,017 m2, zero missing or
outside area and zero overlapping triangle area (independent polygon audit).
The commandlet tests the reduced regression with Delaunay both enabled and
disabled before executing the graph. These are not visual acceptance proofs.
The dedicated exact-head workflow must prove correct components, zero outside
vertices/centroids, zero degenerate/nonmanifold triangles, retention 0.90..1.001,
edge length <=157.5 cm, <=60,000 triangles per mesh and <=120,000 total, plus
identical canonical mesh receipts from two executions.

Topology acceptance precedes matched custom A / PCGEx B Lit and Lighting Only
captures, existing dark-region gates and human visual acceptance. No map,
graph or asset save and no canonical Landscape mutation are permitted.
PR #446 remains Draft pending proof; merge requires explicit owner approval.

The first native topology proof passed at `f3bb3ea33a90bf18267274ca06fd31fa4299244e`
(Actions run `37688447292`): 28,640 triangles, 19 physical components,
1,017 m2 retained, 150 cm maximum edge and zero outside vertices/centroids,
degenerate triangles or nonmanifold edges. Two commandlet runs produced the
same canonical SHA-256, `77372ed6a4a71508ef90606568892b17e4144483624b0546363e1a51544af367`.
The overall workflow failed baseline image equality; visual acceptance is not
claimed. Its logs also exposed omitted accepted-scene LFS dependencies:
CheckpointMaterials, 185 CheckpointEarthworks textures and the Landscape's
M_MaskReview_1 / T_MaskReview_1 pair. The capture workflow now materializes
these existing packages and rejects their load errors before image admission.
This does not re-author or save the accepted map or its assets.

Owner approval on 2026-10-07 permits a temporary neutral Default Lit material
override on Component 230 in the isolated A/B sessions. The workflow enables
`YACS_CLIFF_NEUTRAL_LANDSCAPE=1` for both generators. The capture uses the existing
`/Engine/BasicShapes/BasicShapeMaterial`, retains the original component override
before applying it, restores it during cleanup (also after a partial failure),
and verifies identity on readback. The receipt records this presentation-only
exception and the workflow requires successful restoration. The accepted
checkpoint's Unlit review mask is unsuitable for evaluating physical shadows.
No heightfield, classifier, footprint, exclusion or saved asset is changed.

The PCGEx renderer uses a fixed plane-gradient UV frame per physical island,
matching the custom generator's projection policy. A vertex-varying frame
created large UV discontinuities despite unchanged geometry. Capture warm-up
uses the proof camera in the viewport before screenshots, LOD 0, fully loaded
used textures and 64 high-resolution warm-up frames for both generators.
Image equality and dark-region gates are unchanged.

The isolated renderer verifies `r.Test.FreezeTemporalSequences=1` at runtime
and records it. Screenshot delay is zero seconds: the 64-frame high-resolution
warm-up supplies the settling period without a hardware-dependent number of
extra frames. Presentation offsets preserve source XY exactly; normal clearance
is converted to a bounded vertical lift. Interior smoothing cannot lower a
vertex below its traced source height, while boundary underlap remains active.
The final presentation receipt measures XY displacement and requires zero.

The next diagnostic measures signed vertical clearance against the accepted
Landscape at every front-face centroid and edge midpoint, before spawning the
candidate. `component230-cliff-contact-samples.json` retains front vertices,
triangles and all four clearances per triangle for reproducible diagnosis.
Interior triangles and triangles incident to boundary vertices are reported
separately because the latter include intentional underlap. Negative values
mean penetration; the count below -1 cm is diagnostic, not a new admission
tolerance. Sampling does not prove continuous contact and changes no geometry.
Both A/B editor sessions use UE 5.8 `-Deterministic` (the documented shortcut
for `-UseFixedTimeStep -FixedSeed`). Strict baseline-image equality remains
binding; this setting is an experiment, not a claim of reproducible rendering.

### Same-material contact diagnostic

Owner request, 2026-10-08: capture an additional PCGEx presentation using the
exact material currently assigned to the isolated Component 230 Landscape.
`YACS_CLIFF_MATCH_LANDSCAPE_MATERIAL=1` requires the neutral Landscape override
and reads that same material object for the cliff mesh. The workflow retains
ordinary custom/PCGEx A/B captures and adds `same-material/` Lit and Lighting Only
captures with unchanged geometry, camera, lighting and scree. Material identity
and diagnostic-only scope are recorded and checked. Original A/B image and
lighting gates remain binding. This test is not limestone material acceptance,
a geometry fix, or permission to save the map/assets. Runtime proof is pending.

### Native Landscape mesh replacement diagnostic

Owner approval, 2026-10-08: temporarily replace only Component 230's visible
surface with its native LOD0 mesh, without cliff overlays or scree. This narrowly
permits hiding that component during an isolated capture; it does not authorize
Landscape height/visibility-mask edits or persistence. Baseline frames retain
the original Landscape. Candidate frames use the exported mesh and hide only
the original component, including hidden-shadow participation. Cleanup restores
the component visibility, shadow flag and material and destroys the transient
mesh actor. The accepted map hash and existing scene snapshot remain checked.

UE 5.8 API evidence:
[Landscape export parameters](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Landscape/ALandscapeProxy/FRawMeshExportParams)
support an explicit component list, LOD0 and absolute coordinates;
[mesh conversion](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/MeshConversion/FMeshDescriptionToDynamicMesh)
preserves native attributes and exposes vertex correspondence. The editor-only
adapter uses these native operations without resampling, smoothing or skirts.
It checks triangle counts and conversion position error <= 0.001 cm. This checks
conversion fidelity, not equality of lighting between different render paths.
Nanite Landscape proxies are rejected because they require separate visibility
handling. The ordinary cliff authority and A/B gates are unchanged.

Enable with `YACS_LANDSCAPE_MESH_DIAGNOSTIC=1`; the dedicated workflow writes
four frames and a rollback/export receipt under `landscape-mesh/`.
The receipt marks `NON_PRODUCTION_NATIVE_LANDSCAPE_MESH_DIAGNOSTIC`.
Native export/build/capture passed at `1ce1cb293e687694ab20211ba325e176cd79014f`
(run `37703226554`): 16,129 vertices, 31,752 triangles and zero vertex
conversion error. Visibility/material rollback passed. Large dark regions remain
without PCGEx overlays. This is not a world representation migration, a cliff fix,
a performance admission or a merge approval. The full A/B gate remains failed.

The first native-test baseline Lit frame visibly used coarser Landscape geometry
than the following frames. Captures now retain a separate `00-streaming-prime.png`
full-camera render before the four admitted views. This is a readiness experiment;
strict cross-session baseline equality and lighting thresholds remain unchanged.

Owner direction, 2026-10-08: repair local cliff presentation/contact, allowing
bounded horizontal adjustment on steep walls and vertical adjustment on shallow
transitions, plus local presentation smoothing where geometry artifacts persist.
Preserve canonical source DTM, roads, hard exclusions and rollback. Do not assume
all dark regions are intersections: they also occur in native Landscape mesh
captures. Expand to the current whole Landscape and provide an owner preview only
after the local candidate is visually and technically verified. This authorizes
presentation work and preview packaging, not PR #446 merge or false acceptance.

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

