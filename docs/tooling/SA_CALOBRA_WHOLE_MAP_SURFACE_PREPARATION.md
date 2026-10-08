# Sa Calobra whole-map surface preparation

**Owner direction:** 2026-10-08

**Work item:** [#445](https://github.com/karnalooch/YetAnotherCyclingSim/issues/445), continued in [draft PR #446](https://github.com/karnalooch/YetAnotherCyclingSim/pull/446)

**Starting revision:** `e74a2fabe292626cb49b7c69827a60e234878cd6`

**Status:** full-grid package, fresh native material and all 1024 render-instance roots verified; the first actual baseline/prepared pair is retained, with the 43-frame capture still incomplete

**Methodology:** [World Building Bible](../WORLD_BUILDING_BIBLE.md), selected through the [documentation index](../README.md)

## Goal and area

Prepare the entire current Sa Calobra Landscape for coherent surface materials,
with readable close detail and restrained distant detail. The owner explicitly
expanded the previous Component 230 experiment to this complete working area.
The work remains in the existing material/terrain preparation stack; it does not
start later foliage, road-material, building or official MCP workstreams.

The authoritative area is the existing 2,016.5 m square, approximately 4.07 km2:

| Property | Contract |
|---|---|
| CRS | EPSG:25831 |
| Source raster bounds, metres | E 483000..485016.5; N 4407500..4409516.5 |
| Grid | 4033 x 4033 samples, 0.5 m spacing |
| Samples | 16,265,089 |
| Landscape components | 1024 |
| First sample centre | E 483000.25; N 4409516.25 |
| Unreal axes and units | X east, Y south, centimetres |
| Material UV | `(UE_XY_cm / 50 + 0.5) / 4033` |
| Raster footprint in Unreal | -25..201625 cm on both horizontal axes |
| Landscape vertex span | 0..201600 cm; distinct from the raster footprint |
| Saved source world | `/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004` |

The larger 8 km x 8 km source benchmark is not the working map. Neither a road
strip nor the Golden Kilometer replaces this full-area preparation and review.

### Authorized local Landscape and seam corrections

At 23:42 Europe/Warsaw on 2026-10-08, the owner explicitly authorized local
Landscape and seam changes while preserving visual coherence. A demonstrated
geometry defect may therefore receive a bounded correction in this same work.
The original source/checkpoint remains retained; each derived/Edit Layer change
must record its physical extent, changed heights/vertices and displacement,
fixed interfaces, neighbouring continuity and rollback. Existing operation
envelopes remain binding. Canonical road XY/physics, source scale, macro
geography and exclusion semantics remain unchanged.

This permission does not require speculative edits before a defect is observed.
The initial material-only preparation retains its no-geometry-mutation proof.
If a later correction is needed, its distinct before/after and close/distant
evidence must identify that mutation instead of reusing the material-only claim.

## Findings that determine the implementation

The source masks already cover the whole working grid. The existing fixed
Material Forge Landscape master, however, uses the blue rock amplitude and
its soil complement. It does not consume the separate low-vegetation,
forest-floor and dry-channel contributions. Repeating that two-role master
across 1024 components would not complete the current surface contract.

The existing fixed-master bootstrap, isolated editor process, native material
instance audit, memory guards and capture/rollback facilities are reusable.
This work extends those facilities with a YACS-specific five-role consumer.
It adds no new rendering framework, DCC dependency or PCGEx graph.

The [surface detail atlas](SA_CALOBRA_SURFACE_DETAIL_ATLAS.md) owns the new
physical-surface review model. A/B/C/D are viewer-demand bands, not numerical
distance rings or Unreal LOD values. Only the Component 230 pilot has an
executed physical registration and native witness. The remaining survey
observations do not establish whole-map A/B/C/D footprints.

The full-grid appearance inputs are presentation candidates, not admitted
current land cover. A visually coherent fallback never becomes planting or
geographic authority. The original sample availability, inference categories
and placement exclusions remain independent, inspectable inputs.

## Responsibilities and protected data

| Layer | Responsibility in this work |
|---|---|
| `Base_DTM` / native Landscape | Preserve source identity and macro continuity; named local corrections use the explicit allowance above |
| Road and `Road_Earthworks` | Preserve road position, cut/fill geometry, collision and separate road/BOB materials; Landscape earthwork appearance participates in the new full-area material |
| Accepted Component 230 v8 | Retained local comparison mesh with its existing UVs, normals and limestone material |
| Surface preparation package | Verify and expose full-grid appearance roles, availability, inference and exclusions |
| New fixed Landscape material | Consume every appearance role with metric projection and diagnostic modes |
| Camera-distance detail controls | Vary micro-normal strength smoothly while keeping macro colour and shape |
| Native Landscape LOD / texture mips | Retain automatic distance-dependent presentation; do not globally force LOD0 |
| A/B/C/D and five review tags | Preserve separate physical-surface evidence; unregistered coverage remains U |
| Proof workflow | Bind exact inputs and execution revision to actual native consumption, frames and rollback |

No whole-Landscape conversion into Dynamic Mesh is planned. Dedicated geometry
remains appropriate where an identified surface and owning geometry problem
justify it. Source scale, road interfaces, protected areas and the accepted v8
comparison reference remain binding. Local Landscape/seam corrections must
resolve an identified geometry defect under the explicit allowance above,
independently of material tuning.

## Execution plan

### 1. Freeze and verify inputs

Read the exact branch/PR state and current documentation before editing. Use the
tracked `worldgen/materials/visual_fill` manifest and its three original PNGs,
plus the retained PCG manifest and exclusion raster. Verify identities, sizes,
grid, modes, bit meanings and canonical manifest fingerprints before generating
anything or opening Unreal. Resolve external data and proof paths through the
existing workspace configuration; preserve the live authoring project.

The appearance package has 30,239,452 bytes across its three source PNGs. The
raw six-band LiDAR stack is not needed for this continuation. A missing or stale
retained input is a failure, not permission to regenerate geography or silently
omit an exclusion.

### 2. Produce the complete surface preparation package

Implement `scripts/assets/prepare_sa_calobra_whole_map_surface_prep.py` and
focused tests. Keep the original RGBA, availability and inference images intact.
Retain the original exclusion raster and provide a native-importable image with
the same reason bits. Emit a versioned manifest, exact output hashes and a
256-sector coverage report covering every raster sample exactly once.

For normalized source channels R, G, B and A, use:

| Appearance role | Weight |
|---|---|
| Dry low vegetation | `R * (1 - A)` |
| Forest floor | `G * (1 - A)` |
| Exposed rock | `B * (1 - A)` |
| Mineral residual | `(1 - R - G - B) * (1 - A)` |
| Existing dry-channel appearance | `A` |

Reject invalid channel sums. Do not square weights, introduce a slope-driven
class replacement or interpret alpha as availability. The final weights sum to
one; an all-zero RGB source has a mineral remainder, not a hole. The dry-channel
appearance is not a surveyed waterbed, water presence or new scree classification.

Coverage reports retain observed, inferred, neutral-fallback, protected and
unknown counts separately. Link the existing Component 230 detail evidence as a
scoped reference; do not paint that face registration across the Landscape.
Process bounded strips and record the actual preparation cost and peak memory
where available. The same inputs and recipe must reproduce the same outputs.

### 3. Build the fixed native preparation material

Use one isolated bootstrap process to create the whole-map master, followed by
a fresh process that consumes it. Bind all five roles from the existing retained
surface library. Keep physical tile scales and all appearance parameters explicit.
The preparation material may use scalar roughness to keep the diagnostic graph
bounded; this is not acceptance of a final production PBR set.

The initial five-role recipe uses the retained texture library
`3d53743e48394f31beb35e4030dc8a87`. Dry low vegetation, forest floor and exposed
rock use a 2 m tile; mineral ground and the existing dry-channel appearance use
3 m. The exposed-rock scale remains an explicit artistic trial because its
provider dimensions are unknown. Five colour inputs, five normal inputs and
one full-grid weight input make eleven texture parameters. Triplanar sampling
can perform more than eleven texture fetches; this parameter count is not a
shader-cost measurement.

Provide ordinary lit appearance, role-domain and metric-checker modes. Keep
availability and exclusion diagnostics distinguishable from surface appearance.
Use the installed native projection/normal functions and verify new expressions
against UE 5.8.2 source/API evidence before execution. Missing assets, failed
shader compilation or Default Material fallback fail the proof.

### 4. Separate detail demand from rendering distance

Expose independent near/far controls for a smooth micro-normal transition.
These are rendering parameters, never a way to derive A/B/C/D geography.
Keep a distant B wall's major forms and a C skyline intact. An A observation
elsewhere must not be downgraded because the same surface is distant in one view.

Record the initial and active global LOD settings and all component overrides.
The full-map capture must use adaptive Landscape LOD rather than inheriting the
Component 230 diagnostic's global LOD0 override. Restore all settings afterwards.
Normal fading changes visible detail; a lerp alone does not prove fewer shader
samples or faster GPU execution. Native LOD and mip behaviour, shader cost and
measured performance are separate evidence.

Initial controls retain full micro-normal contribution through 25 m, fade it
continuously to zero at 250 m and use a 0.75 normal-strength multiplier. The
same-camera forced-factor 1/0 pair isolates its visible shading response. The
4033-pixel weight texture's actual mip and residency information must be read
from Unreal; setting a streaming flag alone does not prove that this
non-power-of-two data texture streams.

### 5. Apply and inspect the whole native consumer

Run within the existing accepted-v8 scene lifecycle. Bind only Landscape
materials, preserving road materials, mesh attributes and source geometry.
Verify the generated material-instance parent chains for all 1024 components
using the existing native audit. Assignment or `GetMaterial(0)` alone is
insufficient evidence of actual render-instance consumption.

Capture a distributed 3 x 3 ground grid, opposing whole-area overviews and
selected close-road/dominant-wall views. Add same-camera baseline/domain/checker
comparisons and a controlled micro-normal comparison. Keep camera, FOV, lighting,
resolution and readiness evidence with every original PNG. Add close and distant
views aimed at the same retained v8 boundary vertex to inspect its contact with
the adaptive Landscape. The original set contains 30 full-HD frames from 16
primary views. The implemented coverage extension adds three source-verified Landscape
targets at approximately 2.7 m and the existing SC-P04 / SC-P06 survey poses:
baseline, prepared and checker views for each close target, plus baseline and
prepared views for the two survey poses. The resulting planned inventory is
43 frames from 21 views; the final native receipt owns the executed inventory.
A collision-target distance does not establish per-pixel depth or a new
physical A/B/C/D registration.

The full-grid binding and coverage checks are exhaustive for their specified
properties. The images are selected visual observations, not proof that every
surface or every possible approach is visually accepted.

### 6. Review images and correct evidenced defects

Review macro continuity, visible grid structure, road-ground contact, component
seams, projection scale, steep-face stretching, role transitions and detail
changes. Classify each problem by its owning layer. Correct implementation
defects within this scope and repeat only the affected checks and captures.
Keep actual failures and unresolved geometry visible in the report rather than
using colour, lighting or materials to conceal them.

### 7. Retain results and close the preparation step

Retain the source-bound package, native receipts, original PNGs, memory and
timing observations, API evidence and clean rollback/source checks. Publish
code and documentation in the same draft PR with exact-revision CI results.
The final report distinguishes implementation, real native execution, visual
observations, owner acceptance, saved production assets and performance.

Retain the three generated candidate packages at their original Content paths:
`M_SaCalobraWholeMapPreparation`, `MI_SaCalobraWholeMapPreparation` and
`T_WholeMapWeights`, beneath `/Game/Generated/YACS/SaCalobra/WholeMapPreparation`.
Their ten source textures remain exact, existing Git LFS dependencies. The
reversible `preview('apply', bundle=..., master_receipt=...)` and
`preview('restore')` entrypoints in `scripts/ue/sa_calobra_whole_map_prep.py`
provide an owner replay in the already-open accepted map without a map save.

The existing combined-lighting and PCGEx admission failures remain historical
open gates. This preparation does not close #363, unblock #384/#364 or admit
later world dressing. Whole-map owner visual acceptance, a production saved
consumer and the applicable reference-PC performance gates retain their own
requirements. PR #446 remains unmerged pending the existing approval boundary.

## Parallel implementation ownership

| Owner | Files / responsibility |
|---|---|
| Surface producer | New asset preparation producer and its meaningful input/normalization/coverage tests |
| Native consumer | New fixed master, preparation binder, full-map capture and bounded integration into the existing v8 lifecycle |
| Proof workflow | Owner-only whole-map workflow lane, preflight, verified compile reuse and focused workflow tests |
| Integration / review | This plan, current documentation links, issue/PR scope, independent review, final evidence and report |

All work shares the existing branch. Contributors own disjoint files, do not
commit or dispatch independently, and report cross-file interface changes before
integration. Heavy native operations remain serial on the reference runner.

## Validation and acceptance ledger

| Check | Required evidence | Current state |
|---|---|---|
| Scope / source contracts | Exact AOI, immutable input identities and current SSOT | Read-only audit complete |
| Full-grid package | Every sample accounted for; unchanged source and exclusion bytes; reproducible outputs | Windows full-grid execution and independent pixel/sector audit passed at `a0f12793`; source bytes and logical outputs reproduced; encoder-version byte differences are retained explicitly below |
| Role composition | Unit sum, valid channels, explicit residual/unknown/alpha meanings | Passed over all 16,265,089 source cells |
| Native material | All five roles, expected assets and metric projection, successful compile | Fixed master saved and all three package byte identities verified at `ddeb01b5`, attempt 2; all eleven fresh-process texture bindings verified after native compilation completed at `35e81dc5` |
| Actual full-map bindings | 1024 generated instance parent chains | All 1024 native render-instance roots matched at `35e81dc5`, including hidden Component 230; verified again after the ten actual captures |
| Adaptive detail | Recorded LOD state, independent near/far parameters and matched view evidence | Pending |
| Preservation | Original map, roads, v8 source/UV/normals/material and final rollback checks | Checkout, map and retained sources unchanged after the stopped `a0f12793` pass; complete scene rollback still awaits actual capture |
| Selected visual review | Original distributed/rider/overview PNGs and location-specific findings | Partial: nine baseline and one prepared PNG at `35e81dc5`; the same-camera ground pair shows the material change, while the full 43-frame inventory and near/far acceptance remain pending |
| Source / workflow tests | Focused executed checks plus exact-head CI | CI passed at `a0f12793`: 1,147 script tests, 391 reference tests, 26 fresh Unreal Automation tests; native Windows preflight ran 104 focused tests with one platform skip |
| Documentation | Links, i18n, structure and freshness guards; semantic reconciliation | All four local guards passed; final evidence reconciliation pending |
| Owner visual acceptance | Explicit owner decision on the presented result | Pending |
| Reference-PC performance | Applicable full-area exact-SHA Frame/GPU measurement | Not measured by preparation alone |

The final evidence report will replace pending execution entries with measured
outcomes and links. A successful preparation package is not a declaration that
the entire finished world is already visually or performance-admitted.

## Executed full-grid checkpoint and native startup diagnosis

[Run 37860882304](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37860882304)
at `35e81dc5eda6c710f1ce208b1d84b7f53afa8bf4` passed fresh-process texture
verification, bound all 1024 native Landscape render-instance roots and produced
ten original 1920-by-1080 PNGs: nine baseline views and the first prepared ground
view. The native asset queue drained from fifteen entries to zero, with zero
shader jobs after completion. The same-camera pair shows the large diagnostic
checker replaced by the new continuous warm ground appearance. It is one view,
not whole-map visual acceptance or a measurement of the physical tile scale.

The next prepared view stopped at an additional compilation barrier after the
capture reapplied identical scalar values and updated the material instance.
The failed barrier did not retain its native counters, so its exact remaining
queue is unknown. The correction first reads the actual scalar values, changes
only differing parameters and skips material updates and the extra full drain
when moving between views with unchanged parameters. Actual mode changes still
require readback and native completion. Every frame retains its independent
screenshot-loading and Landscape height-mip readiness checks. Any future failed
drain now includes the complete native queue, worker and memory observations.

Review also found that the lifecycle's completion check still expected the old
thirty-frame plan. It now requires both the actual inventory and full plan to
contain 43 frames. Regression tests invoke the real stop lifecycle: 43/43 may
advance to scene cleanup, while 30/43, 30/30 and 43/42 all fail. The partial
`35e81dc5` receipt remains `FAILED`; its original exception is retained even
though native state restoration, environment restoration and final source/map/
checkout conservation were separately verified. A process exit code of zero
does not admit that incomplete proof.

The subsequent [43-frame run 37859234820](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37859234820)
at `06f823346f4c8b7bab1b794b9088e5dbdd3e02f0` passed the repaired Python
bootstrap and saved the master again. Capture then stopped before material
binding or frames because the installed engine reports the legacy
`r.PostProcessAAQuality` console variable as absent. The whole-map lane now
preserves the existing engine AA configuration and neither queries nor issues
that unsupported legacy setting. All six settings actually changed by this
lane still require a successful snapshot and exact restoration; missing any
required setting fails before mutation. Two regressions cover both boundaries.
The stopped run retained unchanged map/source/checkout evidence and **0/43**
frames; this is not a visual result.

[Run 37859986710](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37859986710)
at `c1c454e88d569fb31ff16180210c9f8d18505abe` passed both bootstrap repairs and
again retained the saved master. Its fresh consumer then read `WeightTex`
before an explicit completion barrier and rejected the native fallback state.
The capture receipt is `FAILED`, with **0/43** frames, even though the orderly
editor shutdown returned process code zero. The independent verifier correctly
rejected it. Verification now resolves all eleven actual texture bindings,
finishes existing native asset/shader work, and audits every binding again;
fallback, compiling or changed bindings remain failures. The compilation
receipt is retained with the fresh-process readback. Failed completion logs
also include the actual receipt status, frame count and native exception.

[Native run 37855085872](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37855085872)
at `a0f12793fba5ef8b425688cd22808e45df26a105` produced and verified the complete
package, with fingerprint
`d955bc5653a586d32e24615305c96dd72b8fa97532ac41344117017f9009622e`.
All 256 sector windows cover exactly 16,265,089 cells. The exclusion raster has
4,603,235 cells carrying at least one reason and 11,661,854 cells without an
exclusion; individual reason counts overlap. Original missing LiDAR samples
remain 2,713,728. Independent replay verified every source byte, every decoded
exclusion pixel, the role sums and every sector total. The local replay used
Pillow 12.3.0 / zlib 1.3.2 rather than the recorded Windows Pillow 12.0.0 /
zlib 1.3.1: eight package files were byte-identical, while the encoded exclusion
PNG and its manifest differed. Their decoded values remained identical. This is
logical reproducibility across encoders, not a claim of identical encoding.

The same run booted the actual empty `/Engine/Maps/Entry` world and stopped
before loading the ten role textures, importing the weight texture or building
the material. Its existing memory gate required 8 GiB physical / 12 GiB commit
headroom; observed free memory was 7,278,485,504 physical bytes and
56,487,071,744 commit bytes. No new material package or rendered frame was
created in that pass. The next bounded correction uses the project's existing
asset/shader compilation drain and full garbage collection before that same
gate, recording before/after memory even if admission still fails. It does not
lower the threshold or alter rendering quality.

[Standard CI 37855093904](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37855093904)
passed on the same revision. UBT performed a warm up-to-date check with zero
build actions; the subsequent 26 Unreal Automation tests were fresh. This is
independent of the pending whole-map material and visual result.

### Fixed native master after the owner freed RAM

The first `ddeb01b5` attempt retained a truthful failed startup receipt:
the compilation queues and active workers were already empty, and a single
drain/GC did not increase system headroom. No allocator change or threshold
reduction was made. The owner freed RAM at approximately 01:05 Europe/Warsaw
on 2026-10-09, and the failed job was retried on the same commit.

[Attempt 2 of run 37856751521](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37856751521/attempts/2)
passed the unchanged memory gate with 10,579,374,080 available physical bytes
and 63,428,063,232 commit bytes. It successfully built the 146-node master,
verified eleven texture and eighteen scalar parameter names and saved all
three self-contained `.uasset` packages: 111,106 bytes for the master,
8,122 for the instance and 28,166,244 for the whole-grid weight texture.
Independent size and SHA-256 checks passed for each retained package.

Native texture readback confirms the 4033-by-4033 linear B8G8R8A8 weight texture
has one mip and one resident mip. The ten role textures are 1024-by-1024,
with eleven mips and seven resident at empty-Entry bootstrap: DXT1 for colour,
BC5 for normals. None is a default texture or still compiling. Bootstrap
residency is not a statement about later close-view residency, aliasing or GPU
cost; those remain native scene observations.

The separate scene process loaded the accepted map and found all 1024 components,
but stopped before material binding because its early helper import could not
resolve the repository `scripts` package. The correction establishes the
repository path at the capture entrypoint, with a regression that runs that
actual bootstrap in an isolated Python process outside the repository. No PNG
was produced by this failed scene pass. Source and checkout conservation passed.

[CI 37856759105](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37856759105)
passed for `ddeb01b5`: 135 script modules / 1,150 reported tests,
391 reference-model tests and 26 fresh Unreal Automation tests. The hosted
script summary identifies the PR merge-test commit `768da0d5daa9a5ecf86d73781ae1942e779f6ad5`;
the independent native material proof remains bound to the exact `ddeb01b5` head.
