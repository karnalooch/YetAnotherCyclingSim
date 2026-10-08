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


### Local single-surface smoothing diagnostic

The opt-in `YACS_LOCAL_CLIFF_SMOOTHING=1` variant acts only on the owned native
Component 230 mesh export. It never mutates Landscape, source DTM or PCGEx data.
The 1,017 authoritative skin cells select 8,136 native half-metre triangles.
Every vertex incident to an unselected triangle and every component boundary
vertex stays fixed. Up to 84 normal-space relaxation passes use blend 0.10,
followed by three tangential redistribution passes at blend 0.20. All passes
share an owner-approved maximum total displacement of 100 cm from the refined source, with
per-vertex backtracking rejecting XY folds and collapsed triangles. The fixed interface and consistently oriented
XY triangles preserve the selected planar domain. Source topology and triangle
count stay unchanged. Normals are recomputed for the edited presentation.

This replaces the visible component for the diagnostic, so no overlapping cliff
skin or scree is spawned. It tests a single geometric owner, not a boolean merge
of PCGEx and Landscape. The existing PCGEx authority proof and A/B gates remain
binding and unchanged. No full-map rollout or visual acceptance is claimed.

The workflow emits `local-cliff-smoothing/` renders, rollback/constraint receipts
and `local-cliff-smoothing-mesh.json`, containing source/candidate vertex pairs,
movability flags and triangle indices for independent auditing. The evidence hash
is recorded in the receipt. Native export conversion error is measured before
smoothing and must not be interpreted as zero displacement of the candidate.
The first build passed at `5258e162`, but the solver rejected a later proposal at
its nonfolding constraint before rendering. It now stops at the last verified
iterate instead of treating constrained convergence as a fatal error; invalid
steps are still never applied. Completed pass count and constrained stopping are
recorded. Runtime, visual and whole-map preview proof remain pending.

#### Native selective geometry refinement

The first single-surface result at `c3b2447e` passed its independent geometry
audit: 2,997 changed vertices, 33.94 cm maximum displacement, 1,017 m2 retained,
zero folded triangles/nonmanifold edges and fixed interfaces. Render review
rejected it for remaining strong angular dark regions; there is no full-map
admission. This is distinct from the separate baseline-image equality failure.

Epic documents the mismatch between smooth shading normals and coarse geometry
as a potential [shadow terminator problem](https://dev.epicgames.com/documentation/unreal-engine/virtual-shadow-maps-in-unreal-engine).
The next experiment uses Epic `FSelectiveTessellate` red-green level 1 on only the
8,136 selected cliff triangles, including conforming boundary transitions. The
native `DynamicMesh` GeometryProcessing module is an editor-only dependency for
this existing engine operation. No external plugin or shipping dependency is added.
Linear refinement alone does not repair curved geometry: subsequent bounded
normal-space relaxation moves the refined interior while keeping interfaces fixed.
Per-vertex step reduction prevents one constrained location from stalling every
other patch. The original 50 cm displacement limit and fold/area guards remain.

The refined source must agree with the native exported triangular surface within
0.001 cm before relaxation. Expected selected triangles become 32,544; an offline
edge-count forecast gives 58,216 total including transitions, below the unchanged
60,000 per-mesh limit. Runtime verifies actual counts/budget and fails closed if
the engine pattern differs. Independent audit distinguishes native and refined
source contracts. Lighting, shadow bias, materials and canonical terrain remain
unchanged. Build/render proof is pending; the shadow-terminator explanation is
still a hypothesis, not a diagnosed engine defect.

The first selective-tessellation build (`133de462`, run `37707815058`) compiled
but the in-place operator asserted inside DynamicMesh: `Array index out of bounds:
0 from an array of size 0`, process exit 3. No refined candidate was rendered.
The next call uses the documented separate immutable input/output constructor,
with the pattern bound to the same immutable source. This tests an input-lifetime
hypothesis; it does not establish the engine root cause or waive any mesh gate.

The immutable-input selective operator passed at `f44539ed` (run
`37708266454`): 29,415 vertices, 58,216 triangles, 14,119 moved vertices,
maximum displacement 50 cm, source/candidate area 1,017 m2 and zero XY folds or
nonmanifold edges. The local audit and capture passed; render review still found
large angular dark regions. Whole-map rollout remains blocked. The full workflow
also retains its separate strict cross-session A/B baseline equality failure.

The next shading diagnostic keeps this exact geometry, material and lighting and
uses Epic GeometryScript `compute_split_normals` with a 60-degree crease angle
and area/angle weighting. It rebuilds normal sharing from the edited geometry
instead of inheriting native export overlay boundaries. This is not a shadow-bias
change or a material workaround. Render comparison must establish whether the
hypothesized smooth-normal mismatch actually contributes to the artifacts.

At `c21e9ea7` the 60-degree crease experiment retained identical geometry evidence
(`d13336c32350e65ff38ac7ca7e531725043e765d4d4a85b2b7175dac86d53711`)
but visual review rejected it: large wedges remained and additional hard facets
became visible. Ordinary CI passed; dedicated A/B remains failed. Restore the
prior normal policy. Two additional diagnostic-only frames use per-face normals
on the same mesh to distinguish interpolated-normal artifacts from geometric
shadow boundaries. These frames are recorded separately, cannot replace the four
admitted Lit/Lighting Only views and are not a proposed flat-shaded final terrain.
Geometry, materials, light settings, shadow bias and all admission gates stay fixed.
Light orientation is included in evidence to support reproducible diagnosis.

The face-normal diagnostic at `7dd3eca8` (run `37722735213`) retained the
large wedges; flat normals also expose triangulation and are rejected as a final
presentation. Directional light points along (0.819152, 0, -0.573576). A read-only
screen-ray/triangle probe at pixel (1400,700), using the harness camera and exported
candidate, hit receiver triangle 32017 and an occluder triangle 31436 about
190.68 cm toward the light. Both are inside the movable cliff region. This supports
a geometric cast shadow for that sampled wedge, not a missing-material explanation
or proof that every dark pixel has the same cause. Other sampled receivers can be
at fixed interfaces; the probe includes only the exported component.

The occluding ridge barely moves after additional normal-space passes because
lateral movement reaches the XY nonfolding guard. The next bounded solver keeps
normal-space motion as its first choice but applies the unfulfilled tangent-plane
residual vertically when XY step weights are reduced. Vertical fallback cannot
alter already-validated XY coordinates; its Z component is clamped to the remaining
50 cm displacement sphere. Fixed vertices, footprint, holes, source data and
triangle budgets are unchanged. A read-only 24-pass numerical probe reduced the
99th-percentile absolute normal Laplacian residual from 9.07 cm (previous solver)
to 6.26 cm; this is a geometry diagnostic, not visual acceptance. Unreal build,
independent geometry audit and rendered comparison must validate the new solver.

At `a76fe4dd` (run `37723714143`), the fallback built, passed the independent
geometry audit and rendered successfully. Ordinary CI, Gumball and orchestrator
passed. Geometry remained 58,216 triangles, 1,017 m2, zero nonmanifold edges/XY
folds, fixed interfaces and max displacement 50 cm. At luma <0.15 the candidate
had 13,741 dark pixels and largest region 1,167, versus 16,324 and 2,232 in the
preceding diagnostic. Large wedges still remain: no visual or whole-map admission.
The separate legacy A/B baseline-identity gate remains failed.

A scope defect was identified: full-overlay normal recomputation altered shading
at fixed vertices outside the editable footprint. The new darkest small region
around (1735,302) traces to fixed receiver/occluder geometry. Restrict native normal
recomputation to overlay elements whose parent vertex is movable. Retain and
exactly compare every fixed element before/after the operation, failing on any
change. This preserves native shading at unedited surfaces and component interfaces.
The presentation geometry and smoothing parameters stay identical for this test.

At `2efd5899` (run `37725196419`), scoped normal recomputation built and
rendered: 15,296 fixed normal elements were exactly preserved; 14,119 editable
elements were recomputed. Geometry evidence SHA remained unchanged from
`a76fe4dd`. Large cast-shadow wedges remain, so this is not visual admission.

The latest local baseline also changed substantially across sessions (5,338 pixels
below luma 0.05 versus 35 in the preceding baseline), despite the global LOD cvar
and priming frame. Do not count that unstable baseline as a quality improvement.
The next capture pins the actual Component 230 `ForcedLOD` editor property to zero,
records/read-checks it before each view, then restores and verifies the prior value
during cleanup. This tests the Landscape-specific LOD/readiness hypothesis, without
changing source heights, camera, lighting, materials or the strict A/B hash gate.


At `3eb8a03d` (run `37726230370`), Component 230 ForcedLOD readback and
rollback passed, but cross-process baseline PNG identity still failed. Lit images
had mean absolute RGBA difference 0.09978/255 (574,598 changed pixels; only 3,964
above 3/255). Lighting Only mean difference was 0.07283/255. This establishes
render variation despite fixed geometry/LOD; its exact GPU/history source remains
unproven. It is not evidence of a source-terrain change.

The A/B harness now acquires a single common baseline in one editor session,
then renders custom A, destroys its actors, verifies the original presentation
scene snapshot and renders PCGEx B with the same camera/light/material setup.
The two baseline frames are packaged in both evidence folders with an explicit
shared acquisition identifier and source path. They are not claimed as independent
pixel determinism runs. Both receipts are written only after final rollback;
failed actor removal, scene drift or cleanup fails the proof. Existing image-hash
identity and every dark-pixel/region threshold remain unchanged. The separate
two-run canonical topology determinism proof remains unchanged. This corrects the
experimental control; it does not fix the remaining geometric wedges or establish
visual acceptance. Unreal runtime validation is required.


The paired acquisition passed on `b90e9f2a`, run `37732509788`: topology,
all captures, unchanged A/B thresholds and non-persistence checkout gate passed.
The common reference contained 5,382 pixels below luma 0.05, versus only 35 in
some earlier independently captured references. Thus the green gate does not yet
prove baseline readiness or visual acceptance. The next controlled experiment
primes each exact scene/view mode immediately before its admitted frame, for both
baseline and candidates. Priming frames remain diagnostic-only. This tests history
readiness after Lit/Lighting Only transitions, with identical lighting, geometry,
64-frame screenshot warmup and admission thresholds. Paired capture timing is
reported as session timing, not invented per-candidate execution time.


At `0c94c64c`, run `37733227829`, per-view priming removed the large black
baseline region: luma <0.05 baseline count became 44 rather than 5,382. The shared
baseline/provenance still passed, but unchanged quality thresholds correctly
rejected PCGEx: 92 >44 pixels and largest region 25 >19 at 0.05; 1,852 >1,658
pixels at 0.10. The previous green result is therefore not accepted as visual
improvement. Retain priming; do not relax thresholds or return to a darker reference.

The next local solver experiment preserves integrated relaxation time 8.4 but
uses 84 steps of 0.10 instead of 24 of 0.35 to reduce explicit-step overshoot.
A read-only numerical probe reduced movable-edge dihedral angles >45 degrees
from 989 to 964, >90 degrees from 240 to 229, and the 99th-percentile normal
Laplacian residual from 6.26 to 6.02 cm. These are modest geometric improvements,
not a visual PASS. Fixed vertices/normals, 50 cm bound, exact footprint and budgets
are unchanged. Unreal build/audit/render remain required.

Two additional diagnostic-only local frames use Epic's documented
`r.Shadow.Virtual.Cache 0` control to redraw shadow pages. The normal admitted
frames retain caching; light, bias, shadow resolution, geometry and material do
not change. Readback and restoration are mandatory. This isolates stale VSM pages
from geometric cast shadows; diagnostic frames cannot replace admitted A/B evidence.
Reference: [Epic Virtual Shadow Maps caching](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-shadow-maps-in-unreal-engine).

At `e5e0bd6a`, run `37733933374`, the smaller-step solver built and rendered.
The local candidate retained visible wedges. Disabling the VSM cache did not
remove them: at luma <0.05 both cached and uncached local frames contained 81
pixels, and at <0.10 both contained 1,490 pixels with a largest region of 623.
At <0.15 counts were 14,747 and 14,730 respectively. This rejects cache reuse
as the dominant explanation for those wedges. The separate PCGEx overlay gate
also failed (93 versus 32 baseline pixels at <0.05; 1,885 versus 1,640 at <0.10).
Neither result grants visual or whole-map admission.

The exported local geometry identifies a sampling defect: normal-only flow
introduces 121 interior triangles with quality below 0.1, using
`4 * sqrt(3) * area / sum(edge_length_squared)` (equilateral = 1).
A read-only three-pass tangential redistribution probe eliminated these slivers
and reduced movable-edge dihedrals above 45 degrees from 964 to 624 and above
90 degrees from 229 to 65. A longer 30-pass probe increased the >45-degree count
to 1,528 and was rejected. The short probe passed the independent domain audit:
58,216 triangles, 1,017 m2, fixed interfaces, no XY folds, and the original 50 cm
source-displacement bound. These measurements are not rendered proof.

The next Unreal candidate applies only the short redistribution after the normal
flow. Its update is the one-ring mean offset projected into the current tangent
plane; the existing source-displacement projection and XY line search still apply.
Vertical fallback is disabled for tangential passes because it would reintroduce
normal motion. Fixed positions/normals and the original triangle budget remain
binding. The receipt reports normal and tangential completed pass counts separately.
Unreal build, independent audit and actual Lit/Lighting Only review are required
before this candidate can be accepted. Lighting, materials and gates are unchanged.

At `eef394cb`, run `37734971563`, the three-pass redistribution built and
matched the offline probe: zero interior triangles below quality 0.1, 624
movable edges above 45 degrees and 65 above 90 degrees. Fixed interfaces and
the 50 cm bound passed. Render review still found large wedges, so whole-map
rollout remains blocked.

That run's nominal A/B PASS is rejected as readiness evidence: the paired
baseline contained 5,068 near-black pixels with a largest region of 5,034,
whereas the same run's native-export and local-smoothing baseline frames had
28 near-black pixels and a largest region of 19. Even the paired prime was
still changing (5,337 near-black pixels). A single priming capture is insufficient.
The harness now takes three complete priming captures before every admitted
view. This is a readiness experiment, not a guarantee of convergence.

Metric analysis additionally rejects the observed cold-render defect for the
frozen Component 230 neutral-material fixture: its <0.05 reference mask must
contain no connected region of at least 250 pixels (an existing reported region
size). Clean references in the reviewed runs have a largest region of 19-20;
the faulty reference has a region over 5,000. The guard does not apply to other
material fixtures, does not choose a lighter reference, and does not alter any
candidate lighting threshold. Metrics are saved before the analyzer fails so
the rejected reference remains inspectable. Small isolated dark details remain
allowed. Missing receipt/provenance fails instead of guessing the fixture.

Owner approval, 2026-10-08: extend the local presentation-only displacement
envelope from 50 cm to 100 cm and select routine parameters autonomously within
that envelope. This applies to the copied mesh only: source DTM/Landscape,
roads, hard exclusions and fixed interfaces stay unchanged. Historical 50 cm
measurements above remain historical evidence, not the current limit.
The producer, capture receipt, independent audit and workflow all enforce the
same 100 cm total Euclidean displacement, not 100 cm separately on each axis.
The receipt declares the configured limit. This first 100 cm trial retains the
same 84 normal-flow and three tangential passes to isolate the envelope change.
Local rendered acceptance still precedes whole-map preview delivery.

The owner subsequently also authorized local Landscape/DTM edits for this
repair. Apply the same bounded 1 m envelope to admitted cliff regions, retain
the original checkpoint/source and use reversible terrain corrections. Preserve
road/hard-exclusion cells and outer interfaces. This supersedes the earlier
blanket frozen-terrain restriction only for the authorized local repair. The
current experiment still edits only an exported mesh and must keep its existing
no-mutation receipt truthful; a terrain-edit candidate needs its own explicit
height-change and rollback evidence. No terrain edit is claimed by this commit.

## Native Landscape thermal erosion trial

Owner request, 2026-10-08: test modified DTM/Landscape and erosion. The isolated
trial reads the native composite 127 by 127 height samples of Component 230,
retains the exact original, and performs bounded thermal/talus redistribution
on a derived heightfield. It imports the result into a transient native
Landscape at the original transform, rather than presenting an eroded mesh as
an edited Landscape. The accepted component is hidden only during capture.
No canonical source, map or asset is saved or overwritten.

Thermal erosion transfers equal integer height units from higher to lower
admitted neighbours above a talus slope of 1.2. Forty-eight alternating-order
passes use one eighth of the excess per transfer. This is a deterministic
thermal relaxation trial, not hydraulic erosion or a geological simulation.
Every transfer respects the total 100 cm envelope and uint16 range, conserves
the height sum, and excludes any vertex touching a non-admitted cell. Roads,
hard exclusions and footprint interfaces therefore remain fixed.

The native importer independently validates every changed sample against the
frozen 1,017-cell domain and original heights. It verifies imported integer
heights and world positions (within 0.01 cm); Python also compares a complete
readback. Evidence retains source/candidate/readback heightfields and erosion
metrics. Cleanup removes the trial and rechecks the complete original heightfield,
scene snapshot, map hash and visibility. Lit/Lighting Only use the same neutral
material, camera and lighting as the mesh comparison. Runtime and visual proof
are required; no visual PASS follows from bounded displacement alone.

API references: [Epic native heightfield access](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Landscape/FLandscapeComponentDataInterface)
and [Epic native Landscape import](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Landscape/ALandscapeProxy).

The first runtime trial at `c19b500a` built successfully and produced a bounded
2,333-sample correction (98.9837 cm maximum, conserved height sum, no fixed
samples changed). Native import was rejected by its immediate readback before
candidate capture. UE 5.8 registration automatically enables edit layers; the
import path now completes `ForceLayersFullUpdate`, as the existing terrain
import commandlet does, before validating the composite heights and world
positions. Failed readbacks log actual and expected values. The original
heightfield and scene were restored; this failed trial is not visual evidence.
