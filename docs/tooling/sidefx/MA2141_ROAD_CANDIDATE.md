# Ma-2141 source-aligned Houdini road candidate

Owner continuation, 2026-10-24, M3/#365: cliffs and real Ma-2141 roads are now
authorized. The owner's subsequent correction explicitly excludes the old road
as the implementation baseline. This candidate reads the original full-route
CartoCiudad source and current retained DTM; it does not reuse the old 300 m road.
The [World Building Bible](../../WORLD_BUILDING_BIBLE.md) and
[Road Physics Profile](../../ROAD_PHYSICS_PROFILE.md) retain their authority.

## Implemented bounded path

[`ma2141_road_candidate.py`](../../../scripts/houdini/ma2141_road_candidate.py)
has two separate products:

- `inspect`, `build`, `verify`: all six source parts / 522 vertices as planar
  diagnostic polylines. Houdini Y=0 is an explicitly labelled diagram plane,
  never elevation. No fusion, pathfinding or connection between parts occurs.
- `prepare-preview`, `preview`, `preview-verify`: a new 100 m visual road
  candidate, part 0, source chainage 0–100 m. Shapely retains original corners
  and adds 1 m samples along the source polyline. Rasterio samples retained
  0.5 m DTM cells without changing them. Native Houdini `sweep::2.0`, Ribbon,
  creates the mesh. Width is an explicit CLI visual assumption, not survey.

`mesh` deliberately refuses final full-route generation. Missing physical
profile, width/banking and integration of the resolved part-4 crossing do not prevent
the reversible source-aligned preview; they prevent final road admission.
The preview does not modify DTM, route physics, canonical XY or the active UE
consumer. It does not implement banking, shoulders or collision. The separate
terrain trial below applies reversible earthworks to a source-window copy only.

## Source mapping and adaptations

| Operation | Official source | Adaptation / boundary |
|---|---|---|
| Import existing polyline vertices | [HOM Geometry](https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html), `createPolygon`, `createPoint` | Input adapter only; native source order retained |
| Cache/read geometry | [File SOP](https://www.sidefx.com/docs/houdini/nodes/sop/file.html), Geometry File | New small BGEO/HIP; no whole-terrain cook |
| Road ribbon | [Sweep 2.0](https://www.sidefx.com/docs/houdini/nodes/sop/sweep.html), Surface Shape=Ribbon, Width | Existing native geometry operator; explicit provisional width |
| Later UE spline interchange | [Pegasus Roads, Tracks and Rivers](https://www.sidefx.com/tutorials/project-pegasus-roads-tracks-and-rivers/), [PEG-13](catalog/PEG-13.md), part 2.1 00:00:04.425–00:20:28.925 | Reference only; Unreal spline implementation NOT RUN |
| Alternative considered | [Labs Road Generator](https://www.sidefx.com/docs/houdini/nodes/sop/labs--road_generator.html) | Intersection generation unnecessary for bounded single spine; crossing/hairpin suitability unproved |

Pegasus pathfinding is deliberately omitted: it cannot relocate real Ma-2141.
The tutorial references establish reusable workflows, not proof of this
candidate. Installed bindings and output must be checked with Houdini 22.0.466.
No Blender replacement generator is introduced. Existing Forge
`aged_mountain_asphalt/dry_varied` remains the later appearance source; material
binding and Unreal proof are NOT RUN for this new road.

## Current real data and remaining acquisition

Pinned CartoCiudad source:
`worldgen/terrain/benchmarks/sa_calobra/ma2141_cartociudad_source_2026-10-02.json`,
SHA-256 `6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36`.
It contains six parts and approximately 12,643.476 m in EPSG:25831. Original
source coordinates are EPSG:4326; pyproj performs the established conversion.
The source review remains `NOT_ADMITTED` for canonical/physics purposes.

Existing host inputs were inspected on 2026-10-24:

- `D:/yacs/data/world-data/sa-calobra-working-v1/accepted-base-dtm/sa_calobra_8x8km_mdt50cm_epsg25831.tif`:
  EPSG:25831, 0.5 m, bounds `(479650,4405899.5,487650,4413899.5)`,
  NoData -32767. This bounds the complete route; individual sample validity
  still needs checking. Ground samples are not an asphalt elevation survey.
- `manual-cnig/PNOA_MA_OF_ETRS89_HU31_h25_{0643_4,0644_3,0670_2,0671_1}.tif`
  under the same working-data root: EPSG:25831, native 0.25 m pixels;
  their combined bounds cover the route. Reuse these for pavement edge
  interpretation, retaining shadow/vegetation uncertainty and acquisition date.
- `manual-cnig/PNOA_2024_BAL_*.laz`: existing NPC03 tiles, filenames span
  483–485 / 4408–4410. Full-route coverage is not established. Obtain only
  uncovered corridor tiles after checking actual LAS header footprints.
- Nearby MDS50CM rasters are DSM in EPSG:3043, not bare-ground replacements.
  They may support crossing investigation alongside classified LiDAR and
  orthophotography; canopy/structure returns must remain distinct from DTM.

The initial ortho crop at the part-0 start shows a paved road with vegetation
and shadow occlusion. The 5 m trial width is an explicit visual approximation,
not an edge measurement. Full width work requires station-indexed left/right
pavement observations from the existing orthophotos. Crossing integration requires
separate upper/lower structure elevation evidence; never drape both source
levels onto one heightfield. Preserve unknowns where imagery/LiDAR cannot
resolve them. [CNIG's current publication record](https://centrodedescargas.cnig.es/CentroDescargas/novedades?codSerie=LIDA3)
confirms Balearic NPC03 availability; availability is not local coverage proof.

## Reproduce and interpret proof

Use repository Python for `inspect`/`prepare-preview`, and installed hython for
native operations. Pass the SHA-256 printed by preparation with
`--record-sha256`; only a freshly produced inspected record is trusted, not an
externally supplied JSON with self-claimed provenance. Output locations must
be new. Serialize CPU work with the other Houdini authoring task; reserve GPU
and Unreal for the owner session.

```powershell
python scripts/houdini/ma2141_road_candidate.py inspect --output Saved/ma2141-source.json
python scripts/houdini/ma2141_road_candidate.py prepare-preview --dtm D:/yacs/data/world-data/sa-calobra-working-v1/accepted-base-dtm/sa_calobra_8x8km_mdt50cm_epsg25831.tif --width-m 5 --output Saved/ma2141-preview.json
# Use a new output directory and the actual preparation hash:
hython scripts/houdini/ma2141_road_candidate.py preview --record Saved/ma2141-preview.json --record-sha256 HASH --output Saved/ma2141-preview
hython scripts/houdini/ma2141_road_candidate.py preview-verify --record Saved/ma2141-preview.json --record-sha256 HASH --output Saved/ma2141-preview
```

The native full-source diagnostic was built and freshly reopened in Houdini
22.0.466: six parts, 522 vertices, maximum local float-storage error
0.000120805576 m. This establishes source import/cache preservation only.
Receipts are local execution evidence, not a parallel admission framework;
delivery still uses the existing CI and Gumball Proof Broker gates. Candidate
rendering, edge/contact checks, saved Unreal consumer, owner final-M3 audit
and performance remain separate. Performance stays `DEFERRED_AFTER_M3` /
`performance_pass: false`.

### Actual 2026-10-24 bounded proof

Producer SHA-256:
`6270bfb97f58615f1b724a683707a19daaeccc309a78f4c94c729a0d03b9ab39`.
The new source-aligned 100 m candidate was built and freshly reopened with
Houdini 22.0.466, native `sweep::2.0`. Actual controls: `surfaceshape=3`
(Ribbon), `width=5.0`. Its 104 backbone points retain the source corners;
the surface has 936 points / 824 polygon primitives, nine transverse columns.
Cross-section centres match the input to 0.000003657 m. Measured cross-section
width spans 4.999996–5.006754 m, including native corner expansion.

The origin is EPSG:25831 `(482406.81495792227,4410548.609070472)`;
Houdini X=easting minus origin, Y=DTM elevation, Z=northing minus origin.
Mapping this diagnostic origin to the L07 consumer remains **UNVERIFIED**.
Do not import it by assuming the consumer has the same origin or axis signs.

Nearest-cell DTM sampling of all 936 surface vertices produced 936 valid
samples and residual `surface_z - dtm_z` **-0.714676 to +0.470367 m**, RMS
0.147379 m. **CONTACT NOT PASS:** the provisional road has terrain tie-in
debt. This is a diagnostic against the source raster, not native triangle or
collision verification. Neither material nor a blanket vertical offset is a
valid resolution. Separately, all 522 full-route source vertices sample valid
DTM cells, spanning terrain elevations 14.9300003–721.8499756 m; this does not
resolve road deck elevation at crossings.

Local output directory:
`D:/yacs/project/Saved/road-source-diagnostic-20261024/new_source_verified/`.
It contains `source_100m_preview.hip`, the BGEO, exact build/fresh-reopen
receipts, source-space `surface_points.csv`, and
`terrain_residual_diagnostic.json`. Full-source import/reopen receipts are in
the sibling `full_source_verified/` directory. These local generated files
remain outside Git; the paths are recovery pointers, not portable proof URLs.
Ruff and documentation index/i18n/structure/links/freshness checks passed.

## Bounded native triangle-contact and earthworks trial

`prepare-terrain` reads only a 114 × 226-cell window from the retained DTM.
Its georeferenced bounds are `(482396.5,4410538.5,482509.5,4410595.5)`.
It writes an unchanged north-up source window plus a south-up storage adapter:
row order and GeoTIFF affine change together, preserving every georeferenced
sample. [HeightField File](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_file.html)
uses 0.5 m grid spacing, height scale 1, unclamped values, native rotation 90°.
All 25,764 imported positions/heights are checked against the source raster;
maximum float-storage difference was 0.000015259 m. This avoids an unverified
negative-volume transform and does not change the original DTM.

`terrain` and `terrain-verify` use native
[Convert HeightField](https://www.sidefx.com/docs/houdini/nodes/sop/convertheightfield.html)
with full-density triangles, and documented `hou.Geometry.intersect` against
those actual triangles. All 936 road vertices hit the identified source/candidate
terrain, with zero misses. This is a Houdini geometry test, not Unreal collision.
An earlier Ray SOP attempt failed direction readback and was replaced by the
documented native HOM intersection API, not a custom triangle sampler.

Confirmed contact defects authorize the isolated native chain:
[HeightField Project](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_project.html)
(`Replace`, closest hit, documented default max ray distance 1000, no jitter)
→ [Mask by Geometry](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyobject.html)
(road footprint, either side, no blur)
→ [HeightField Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layer.html)
(height only, masked blend 1). A tested 5 m project ray limit produced no
changes; the default distance resolved projection on this elevation range.
The geographic execution footprint is still only the small source window.

The saved HIP includes `ROLLBACK_SOURCE_DEFAULT`, input 0 selected. Input 1
shows the separate candidate. The source and road are not overwritten.
The operation changed 1,989 cells, with source-relative delta
**-0.379539 to +0.365326 m** and **zero change outside the projected footprint**.

| Native vertex contact | Before | After |
|---|---:|---:|
| Valid triangle hits | 936 / 936 | 936 / 936 |
| Minimum road minus terrain | -0.598422 m | -0.546463 m |
| Maximum road minus terrain | +0.401100 m | +0.370735 m |
| RMS | 0.144551 m | 0.065384 m |

**CONTACT NOT PASS remains.** Native projection improves the interior but does
not resolve boundary/grid tie-in. Next inspect station/edge-specific residuals
and source profile before extending an explicitly designed support footprint;
do not lower thresholds, globally move the road, or disguise penetration.
Fresh reopening reproduced the metrics at producer
`a805e5445e068aef6fb1b3771ff3852f033f7762e4be3fa2b23b6ad80bfbe9f6`.
Local evidence: `Saved/road-source-diagnostic-20261024/terrain_final/`.
Later source wording that records newly resolved crossing evidence does not
retroactively change that producer hash.

This is an official native-node adaptation, not a claim that Pegasus supplied
a Sa Calobra earthworks graph. The original PEG-13-09 transcript covers edit
layers/reserved splines at **07:30.045–08:40.385** and lower/raise terrain
attributes from **15:12.905**. The
[official spline-output documentation](https://www.sidefx.com/docs/houdini/unreal/landscape/splineoutput.html)
warns that Unreal spline segments need not exactly match Houdini input curves;
using those splines cannot silently replace canonical alignment.

## Existing-source crossing resolution

The source-data audit on 2026-10-24 resolved the shared XY crossing at
EPSG:25831 **(484251.663468,4409131.131841)** using the existing
`manual-cnig/PNOA_2024_BAL_484-4410_H31_NPC03.laz`, SHA-256
`af3b790313846225bde04f48b95609963e652d696c0a2edca0d1722eec8ec6d8`,
and retained orthophotography. Class 17 identifies bridge points under the
[official NPC03 class specification](https://pnoa.ign.es/resources/archivos/EspTec/Definicion_Clases_241004-LID3-SPC-LID-00122-IGN_Ed_2.0_NP.pdf).

- Upper NW–SE branch: **part 5 → START of part 4**, bridge median 673.455 m
  within 1 m of the shared location.
- Lower SW–NE branch: **END of part 4 → part 3**, ground median 666.295 m
  within 5 m. The approximately 7.16 m difference is level separation, not
  underside clearance or a structural specification.
- Independent nearby probes support this assignment: part 3 station 10 m
  ground median 666.145 m; part 4 station 10 m bridge median 673.076 m;
  part 4 station 129.893817 m ground median 666.315 m; part 5 station
  3191.995816 m bridge median 673.705 m.

**Part 4 is closed in XY but must remain open in XYZ:** its start and end have
different levels. DTM/DSM at the crossing represent roughly 666.3 m and cannot
recover the upper deck. Missing crossing evidence is no longer the blocker;
integration of these point-supported branch profiles, bridge construction and
native proof remains pending. Full-route width observation is still required.

## Numerical grid support comparison

The pavement-only projection residual is predominantly at the outer columns:
column 0 RMS 0.13039 m, column 8 RMS 0.14360 m; inner rows and columns RMS
0.00824 m. A bounded comparison therefore uses the same retained backbone
and native Sweep Ribbon at **7 m**, while retaining the actual candidate
pavement at **5 m**. The extra 1 m on each side is two raster cells of
numerical support, **not an observed shoulder or approved earthworks width**.
`--support-margin-m 1` projects and masks this support plane using the same
native chain; the separate pavement mask records changes outside pavement.
No blur or road-height offset is applied.

Actual `terrain_support_1m/terrain_trial.json` and fresh reopen, producer
`6254ab6c5f0f6e6182b8894dfffefc4fe9b3b68c1d31e5b4210b2dc48bfcc9d2`:

- 936/936 native triangle hits, zero misses, RMS 0.011364 m;
  residual range **−0.071399 to +0.107041 m**. Contact remains unaccepted.
- 2,787 changed raster samples, including 798 outside the pavement footprint;
  zero change outside the numerical support footprint.
- Source-relative terrain delta **−0.892395 to +1.109116 m**. These measured
  changes are candidate results, not an accepted terrain deformation bound.
- Source and pavement files unchanged; rollback switch defaults to source.

The first comparison deliberately retained the identical 104-point input. Inspection
also found duplicate endpoint stations 100 and 100.00000000004 caused by
floating-point line projection. The preparer now clamps projected stations to
[0,100]. The corrected `preview_clamped` candidate and fresh reopen prove
103 backbone points, 927 surface points and 816 primitives. Its same-margin
`terrain_clamped` trial/reopen has RMS 0.009972 m, with unchanged extrema and
terrain delta. The largest residuals occur at chainage 0/100 m: the widened
support plane still ends at those longitudinal boundaries. The largest
interior residual is about −0.0322 m at source corner station 17.231864 m.
Native intersections against the support ribbon itself are within 0.000008 m
at 924/927 vertices (three endpoint-boundary misses), isolating the remaining
error to terrain rasterization rather than a different road support surface.
[Official SideFX projection documentation](https://www.sidefx.com/docs/houdini/heightfields/projection.html)
explains grid-spacing aliasing. The proper next trial is source-backed overlap
at segment ends and explicit resolution assessment, not further widening.
The support comparison does not establish full triangle-interior contact,
smooth road grades, surveyed pavement width, or an Unreal/L07 import transform.

## Full-route observed-height diagnostic and native visual Sweep

`prepare-profile --dtm <retained DTM> --laz <audited LAZ> --output <record>`
uses the existing repository `.venv/Scripts/python.exe` with laspy/rasterio,
streams the LAZ in 250,000-point chunks, and retains all six source parts and
original corner stations plus a 2 m diagnostic station grid. The bridge AOI
is 100 m square; observations use class 17 within 1.5 m on the audited upper
branches only. A 50 m endpoint search is a diagnostic window, not a measured
bridge extent. Class 17 includes bridge accessories: its medians are source
observations, not admitted pavement levels. DTM samples remain explicitly
ground observations. No grade smoothing or unsupported transition interpolation
is performed.

`profile` / `profile-verify` require the record's SHA-256 and run with hython.
Missing observations and changes of source kind split open polylines. The
native Sweep Ribbon produces a separate **assumed 5 m** visual surface for
these segments; it cannot establish road contact, banking or surveyed width.
The original planar diagnostic remains available separately.

Actual `full_profile_native` build and fresh reopen:

- 6,839 source observations across six parts; 21 unsupported upper-branch
  observations excluded, leaving 6,818 points in eight open primitives.
- Part 4 starts at observed 673.455 m and ends at DTM 666.289978 m;
  the XY loop is never closed in XYZ.
- Native Sweep: 61,362 points, 54,480 primitives; source-backbone float storage
  error at most 0.000122 m. This is geometry evidence, not road acceptance.
- The explicit L06-compatible frame is `X=E−483650`, `Y=height`,
  `Z=4409899.5−N` (south-positive). This differs from the earlier isolated
  100 m preview's north-positive local frame. No UE import is claimed.

The full-route preview does not alter terrain. Unsupported bridge transitions,
accessory-versus-pavement classification, real widths, grade/crossfall quality,
terrain contact, bridge construction and consumer proof remain separate work.

Final guarded source `7f847a64f74d435a50e0baef221744799d58cb8f2a93fddf44e03b4149f504ac`
was built/reopened in `full_profile_checked` and `terrain_rollback_checked`.
The latter reads the actual rollback switch and compares every resulting height
with source; both passed. Full-route validation checks finite geometry,
positions, open topology, artifact hashes and native Sweep controls. Independent
semantic comparison of every primitive's connectivity/attributes and detection
of near-coincident full-route station pairs remain additional quality checks.

## Native FBX consumer probes

The separate retained `Saved/road-source-diagnostic-20261024/export_fbx_candidate.py`
uses the original native `filmboxfbx` ROP, following
[official FBX documentation](https://www.sidefx.com/docs/houdini/nodes/out/filmboxfbx.html).
Actual controls: `axissystem=0` (Y Up, Right-handed), `convertaxis=0`,
`convertunits=1` (Houdini meters to FBX centimeters), binary export. The
`startnode` selects only the retained candidate object. No mesh coordinates or
geographic source are edited. `fbx_candidate/export.hip` retains both exporters.

- `bounded100m.fbx`, SHA-256
  `09c0d8b29bcc62f569064da0544658949283872e636a3dfe6662bd840f18419c`:
  asymmetric native bounds provide a consumer axis/scale probe. Its local
  north-positive frame must not be mistaken for L06 global placement.
- `fullroute.fbx`, SHA-256
  `04be6f0fd62c640505e6ad9eeb0b19949ef29752793fd4f03a2dddc3c430f496`:
  L06 south-positive global geometry from `full_profile_native`, not the later
  guarded artifact bytes. Geometry counts and source-coordinate method match.
  Houdini bounds in meters are approximately
  `[-1273.311157,14.823858,-1271.475708]` to
  `[1306.154785,722.001404,2645.966309]`.

FBX export is proved; Unreal axis conversion, import, placement, collision and
visual acceptance require their own consumer measurements. Do not infer these
from the file extension or exporter controls.

The root agent subsequently imported the bounded canary through native UE
tools into a new unsaved asset. Actual receipts
`Saved/ue-road-canary-import-20261024.json` and
`Saved/ue-road-canary-readback-20261024.json` report 927 vertices and 1,632
triangles. UE centimeter bounds are
`[-75.838829,-237.210205,7338.475098]` to
`[9386.410156,3913.985352,8051.904297]`, matching the scoped mapping
`UE=(Houdini X,Houdini Z,Houdini Y)*100` without a sign flip. This proves
the canary import scale/axis bounds, not full per-vertex identity, terrain
contact, saved persistence or final visual acceptance.

The full-route FBX was also imported into the new
`/Game/Generated/YACS/RoadCliffCandidate_20261024/SM_Ma2141_SourceCandidate`
asset. `Saved/ue-road-fullroute-import-20261024.json` and
`Saved/ue-road-fullroute-readback-20261024.json` record 61,362 vertices,
108,960 triangles and maximum bounds discrepancy **0.005859375 cm** against
the expected axis/unit conversion. The new preview actor in current
`L_SaCalobra_Lesson07` has identity location/rotation/scale and matching bounds,
as recorded in `Saved/ue-road-actor-20261024.json` and
`Saved/ue-road-actor-readback-20261024.json`. The active map was not saved.
The whole-area view did not establish clear road visibility; close-view
inspection, surface appearance, contact and persistence remain unaccepted.

## Corrected native orientation — current candidate

The earlier full-route candidate above is **superseded**. Native inspection
found 38,142 downward-facing polygons: default Sweep Curve Normal transported
an unsuitable frame along the road. The initial sampling also combined global
2 m stations with original corners, creating artificial intervals as short as
0.001902 m. This was a geometry defect, not a material problem. The root agent
removed the old preview actor; `Saved/ue-road-actor-rollback-20261024.json`
records that rollback.

The current adapter uses [Shapely segmentize](https://shapely.readthedocs.io/en/stable/reference/shapely.segmentize.html)
to evenly subdivide each original source edge at maximum 2 m, preserving all
original corners and the exact XY polyline. The native
[Sweep up-vector contract](https://www.sidefx.com/docs/houdini/nodes/sop/sweep.html)
supplies `up=(0,1,0)` per backbone point with Transform Using Curve Point
Attributes, and explicit Target Up Vector Y Axis (`upvectortype=2`). No route
smoothing, height offset, selective face flipping or geometry exclusion was
used to fix orientation. World-aligned asphalt does not require a UV repair.

Current producer **`b9369ba4ecc88be669422f7b88e73c21c7c10edea78b0e30101e79bc4ed1cb79`**:

- `profile_up_final`: 6,566 supported source points, eight open runs, 18
  unsupported bridge observations excluded. Exact run connectivity, source
  part/kind/station/up attributes and producer identity pass fresh reopen.
- 59,094 surface points and 52,464 quads; **zero downward or vertical faces**,
  minimum native face-normal Y 0.026755346. Very steep source-ground sections
  still require road-profile construction; upward winding is not grade proof.
- `export-profile --preview-root <verified profile> --output <new export dir>`
  reproduces the native FBX export with pinned build/reopen producer and bytes.
- Current `fbx_up_final/ma2141_source_up.fbx` SHA-256:
  `b75c17fd86afc7e7e0a3f18828aeda8e16f6cb87bd7ee639c710f0dec84648fc`.
  Native bounds in meters: `[-1273.311279,14.930000,-1271.478394]` to
  `[1306.158813,721.857666,2645.966797]`. The corrected UE readback is recorded below.

## Retained asphalt material reuse

The current UE project initially lacked Forge asphalt. Six retained material
assets from `D:/yacs/work/level-editor-review/b9fddea3f602-y473save01` matched
their original saved manifest hashes and were copied by the root agent to
the same package paths in the live project. Receipts
`Saved/ue-road-material-copy-20261024.json` and
`Saved/ue-road-material-native-20261024.json` record the copy/native loading
and four texture dependencies plus world-aligned functions.

Binding candidate:
`/Game/Generated/YACS/RoadAsphaltConsumer/aged_mountain_asphalt/dry_varied/9c0a41f6e2ae/MI_MaterialForge`.
Only the instance, master and four textures were reused; no historical road
geometry/map/crack layer is part of this operation. The retained recipe is
`scripts/ue/road_asphalt_slot_canary.py` using Forge `import_variant`; that
historical canary's scene-loading steps must not run against the active world.
Material Maker's MIT upstream provenance and required notice are recorded in
[dependency provenance](../../legal/DEPENDENCY_PROVENANCE.md) and
`docs/legal/notices/material-maker-MIT.txt`; procedural surface appearance
does not establish surveyed Ma-2141 material or geography.

## Corrected UE visual proof and remaining contact failure

The corrected FBX import and material binding succeeded. Receipts
`Saved/ue-road-up-import-20261024.json`, `ue-road-up-material-20261024.json`
and `ue-road-up-readback-20261024.json` record **59,094 vertices / 104,928
triangles**, with maximum source-to-UE bounds difference **0.0078125 cm**.
The identity-transform preview actor was `PersistentLevel.StaticMeshActor_1`.
`Saved/ue-ma2141-asphalt-up-preview-20261024.png` visibly shows asphalt and
substantial scattered Landscape intrusion across it. Thus orientation/import
and surface visibility are proved; **terrain contact visibly FAILS**. The
terrain support layer has not been applied to the active Landscape.

The collision-profile setter changed the label to `NoCollision`, but actual
`collisionEnabled` remained `QueryAndPhysics`, as recorded in
`Saved/ue-road-up-collision-observed-20261024.json`. Collision disablement is
not proved. No map save or qualified runtime road is claimed.

The corrected mesh asset was subsequently saved separately:
`Saved/ue-road-up-saved-20261024.json` records 744,520 bytes and SHA-256
`e4b8a86971bc6aa107bc82b468966eac19093e87760c8b5246228d14207d0e2e` for
`SM_Ma2141_SourceUp.uasset`. Its fresh-process reopen is **NOT RUN**.
The new preview actor was removed successfully according to
`Saved/ue-road-up-actor-rollback-20261024.json`; the active map was not saved.
Saved asset evidence does not supersede the visible full-road contact failure.

## Read-only native edit-layer integration findings

The live project enables the existing UE `LandscapePatch` Editor plugin.
Installed UE 5.8 headers expose native BlueprintCallable
`ULandscapeTexturePatch::SetHeightTextureAsset`, source/encoding/alpha modes,
texture transforms, and inherited `SetLandscape`, `SetIsEnabled` and
`RequestLandscapeUpdate`. Patch managers are deprecated in those headers;
patches target edit-layer GUIDs and priority. This is a possible existing
consumer for a bounded Houdini-authored height/alpha patch, not implementation
proof or permission to change the active terrain without validating its layer.

The alternate [official Houdini Engine landscape route](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html)
supports `unreal_landscape_output_mode=1`, `unreal_output_name` targeting,
named edit layers and separate additive height data. The deprecated
`unreal_landscape_editlayer_target` must not be used. Houdini Engine availability
in the live project has not been established. Neither route was invoked by
this road adapter.

Before integration, regenerate the bounded terrain trial against the **current
segmentized, upward-facing global road** and current Landscape grid. The older
100 m north-positive local support trial is not an interchangeable patch.
Verify texture registration/height encoding, masked delta footprint, source
layer preservation, toggled rollback and actual post-update contact. Do not
offset the road or use material opacity to conceal the defect.

## Fresh current-FINAL bounded terrain candidate

`current-terrain` / `current-terrain-verify` now implement that independent
native trial. Inputs are the corrected `profile_up_final` mesh/record and
verified current `SaCalobra_Unified_0_0.bgeo.sc`, SHA-256
`fb4c5a7691f4af15cad405cfe87e4f5378d058c231710df36827e37ec0a7c7fb`.
The pinned transport manifest is
`760425da4a8fa46c4e201a74f0a70ced802f14dc992d1569885167fe73a8978e`.
The road interval requests chainage 10–110 m; actual retained source support
runs 0–118.072882 m, so the evaluated interval avoids support end boundaries.
Support width remains the explicit numerical 7 m, pavement 5 m assumption.

Native HeightField Crop retains all source samples exactly. Current FINAL has
height and visibility only, so [HeightField Copy Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_copylayer.html)
creates an empty mask with `copysrc1=0`; native Mask by Geometry fills it before
Project/Layer blending. This is a separate branch with source-default rollback.

Actual build and fresh reopen in `current_final_patch_v2`, producer
`0a26087d6079f86d674b4e8152ebb68970f50d46c8a44071caca0b0cf7473820`:

- 263 × 124 crop, **32,612 source samples identical**, no source visibility holes.
- 459 road-vertex native triangle hits. Before: RMS 0.083388 m, range
  −0.361206 to +0.468826 m. After: **RMS 0.003990 m**, range
  **−0.013107 to +0.011230 m**. `contact_pass=false`; no triangle-interior,
  consumer quantization or visual contact acceptance is inferred.
- 62 DTM nearest-cell backbone observations minus current-FINAL interpolated
  triangle heights: RMS 0.015603 m, range −0.042343 to +0.044571 m. This compares
  different sampling methods, not every cell of two raster baselines.
- 3,302 changed terrain samples; delta **−1.188896 to +1.543236 m**;
  zero change outside support. Rollback output reproduces source exactly.
- `current_patch.bgeo.sc` SHA-256
  `eacbb56325a8a9061a0d32ba8e50fdd16664579307a086f8a94b3bb313a96d49`.

No Unreal terrain mutation occurred. Consumer integration remains blocked on
an exposed, verified way to create/assign the required Landscape Patch Edit
Layer, followed by explicit texture encoding/registration and rollback proof.
The native patch is not a reason to promote the visible full-route road.

## Producer newline provenance

Historical native receipts hash the exact Windows CRLF producer bytes. The
road checkpoint `b9369ba4ecc88be669422f7b88e73c21c7c10edea78b0e30101e79bc4ed1cb79`
corresponds to LF-normalized source
`7838f689c7d6206f4156a3cd26dc9d6628d171e7e55cd48c66eb5d2439d34657`;
these are distinct byte identities, not interchangeable proof hashes.
The later CRLF current-patch producer `0a26087d6079f86d674b4e8152ebb68970f50d46c8a44071caca0b0cf7473820`
has now been normalized to repository-required LF before final native checks.
Its LF SHA-256 is
`87b52353a3e98097c90f959bffe8086971d8e730939c9879b19af37fabc1215f`.
New final native receipts must explicitly name that LF producer; previous
receipts retain their original identities and are not relabeled.

Final LF-native execution completed successfully: `profile_up_lf` build and
fresh reopen, `fbx_up_lf` export, and `current_final_patch_lf` build and fresh
reopen all record producer `87b52353a3e98097c90f959bffe8086971d8e730939c9879b19af37fabc1215f`.
Counts, bounds, upward-face checks and bounded contact metrics remain as
reported above. New FBX SHA-256 is
`e9e943c9a270961e235eb6c4e9d4de6cff1d2e61e919281bd09083960443b14c`.
That regenerated file was not reimported into UE; the earlier UE proof remains
bound to `b75c17fd86afc7e7e0a3f18828aeda8e16f6cb87bd7ee639c710f0dec84648fc`.

## Opt-in finite pavement / underside grading hypothesis

The zero-thickness road initially projected its top onto terrain, leaving
millimeter-scale raster disagreement at the visible surface. The independent
`slab` / `slab-verify` branch tests a **0.10 m vertical thickness assumption**,
supplied explicitly through `--thickness-m`. This number is neither observed
Ma-2141 construction nor a SideFX or engineering thickness standard.

[Official Poly Extrude 2.0](https://www.sidefx.com/docs/houdini/nodes/sop/polyextrude.html)
supports a global transform of the extruded front while retaining the back
and connecting side faces. Native Divide triangulates the retained road top;
Reverse prepares the whole open surface orientation, then connected-component
Poly Extrude translates the new underside downward with distance zero and a
global Y transform. The original top point set is unchanged. The separate
7 m support ribbon is translated to the underside only; native Project/Mask/
Layer grades the copied current terrain to that construction surface.

This follows the Bible's separation of road and presentation terrain; the
[Road Physics Profile](../../ROAD_PHYSICS_PROFILE.md) remains untouched.
Rendered slab thickness does not become authoritative grade, width, banking
or collision. No road lift or material-opacity workaround is used.

The [native Boolean surface/solid operation](https://www.sidefx.com/docs/houdini/nodes/sop/boolean.html)
clips the complete terrain triangles against an outward closed volume above
the unchanged native road top. This checks triangle interiors rather than
only vertex probes. The unmodified terrain is the positive control. Boolean
errors/warnings, open slab edges or incorrect top/bottom normals fail the run.

Actual `slab_010_trial` build and fresh reopen, LF producer
`6340e808d8772c713751a88830e0a9acc12387d5deb97f8b629de327ea9aa2a5`:

- **459 top points exactly unchanged**, zero top lift. Closed edge-incidence slab:
  918 points, 800 top triangles, 800 underside triangles and 116 side faces.
  Every edge is incident to two faces and top/bottom normals are checked;
  this does not independently prove vertex-manifoldness or no self-intersection.
- Before grading, native Boolean finds 4,297 terrain polygons above the road
  top; after underside grading it returns **zero points and zero polygons**.
  This proves the bounded native triangle intrusion test, not UE rendering or
  all-route contact.
- Underside-minus-terrain at 459 native probes still ranges
  **−0.013109 to +0.011229 m**, RMS 0.003991 m. Underside contact is therefore
  not admitted; the new volume separates that remaining raster discrepancy
  from the visible top surface.
- 3,302 modified terrain samples, delta **−1.288895 to +1.443237 m**;
  zero change outside support, exact source rollback. No physics/UE mutation.
- `pavement_slab.bgeo.sc` SHA-256
  `bf7ec94bb629c6aec92f042bec7a1cdb24edc5e21a14cb61d8385cdf4a6a5b0b`;
  `underside_terrain.bgeo.sc` SHA-256
  `7db03aeb9688fe912065c66d614bfc8d16825efbfd035edee4ddcb91190b136b`.

The earlier LF `87b52353...` checkpoint and its evidence remain separately
retained. This opt-in branch does not replace the saved full-route UE asset,
apply a Landscape Patch, or claim structural/physics acceptance.

### Future LandscapeTexturePatch handoff — not executed

The source layer is `REVERSIBLE_CANDIDATE` in `slab_010_trial/slab_trial.hip`;
the separate native `SUPPORT_MASK` supplies alpha. Export them together without
resampling, preserving the exact 263 × 124 grid. Candidate heights are absolute
Houdini meters. For an explicit UE float-height encoding, convert them to
centimeters and use `WorldUnits`, `ZeroInEncoding=0`,
`WorldSpaceEncodingScale=1`, `ZeroHeightMeaning=WorldZero`, and `AlphaBlend`.
Alpha is the same support mask, zero outside support. These are proposed
bindings from installed UE headers, not successful texture import settings.

Native voxel-center mapping is:

```text
Houdini X = -1253.2501220703125 + 0.5 * column
Houdini Z = -638.75 - 0.5 * row
UE X,Y   = 100 * (Houdini X,Houdini Z)
```

With texture V increasing toward UE +Y, reverse the native row order for both
height and alpha. The intended center is UE XY
`(-118775.01220703125,-66950)` cm; pixel-center coverage is
`(13100,6150)` cm. Installed `GetUnscaledCoverage` explicitly measures between
outer pixel centers, not outer pixel edges. Verify all four corner sample
positions and asymmetric interior control points after native import before
enabling a patch; do not silently infer raster orientation from image display.

`AssignToLandscape` requires an existing **Landscape Patch Edit Layer**.
The currently exposed toolsets do not provide a verified way to create/assign
that layer or call arbitrary reflected functions. Thus integration remains
blocked at that specific consumer operation. Once available: create a separate
named layer, assign the disabled patch, validate registration/encoding, enable
only for the bounded comparison, measure native Landscape contact and confirm
that disabling the patch exactly restores source samples. Do not save the
active map or promote this experimental thickness without those proofs.
