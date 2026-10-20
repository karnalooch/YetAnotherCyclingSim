# Lesson 07: Material Setup â€” Full Unified Domain Verification & Remediation

- **Task**: SideFX Project Pegasus Landscape Workflow â€” Lesson 7 "Material Setup" (PEG-02-07)
- **Domain**: Sa Calobra Unified $16\,000 \times 16\,000$ single-quality domain ($8000 \times 8000\text{ m}$, $0.5\text{ m}$ spacing, $256\,000\,000$ samples)
- **Branch**: `codex/365-world-graph`, Draft PR #474
- **Accepted Base**: `2e1c209995b100fe01af08c39542605cffee9305`
- **Receipt**: [lesson07-material-setup-verification-receipt.json](lesson07-material-setup-verification-receipt.json)
- **Technical Status**: `LESSON07_TECHNICAL_PASS: false` (local consumer repair and sampled native/runtime checks complete; whole-area collision, exact interpolation, protected CI and owner visual acceptance remain unverified)
- **Visual Review**: `PENDING_FINAL_M3_AUDIT`
- **Performance Acceptance**: `DEFERRED_AFTER_M3` (`performance_pass: false`, `performance_note: "DEFERRED_AFTER_M3"`)

---

## Close-up squares correction (2026-10-20)

**Current checkpoint:** this supersedes the scale-only tiling assessment at
`7e3b0001d1d325553f0fbf09c7aee71b33a57935`. The owner supplied a close-up showing
clear squares. The previous panorama was insufficient evidence; that earlier
checkpoint is not accepted as a tiling fix.

The grid remained after isolating normal influence. Source Grass0 edge
measurements did not show a large wrap discontinuity. The retained texture
pattern repeats under plain UV tiling; reducing the repeat scale alone cannot
remove it. The bounded correction reuses the installed Epic function
`/Engine/Functions/Engine_MaterialFunctions03/Texturing/TextureVariation`.
No replacement sampling algorithm, generated terrain or new surface textures
are introduced. The saved UE material/function graphs are the authoring source.

The same `M_Landscape_YACS` now shares each detail/macro `Shifted UVs` output
between Colour, Normal and Masks sampling. Three bounded copies under
`Materials/Functions/MF_YACS_ArrayVariation{Colour,Normal,Masks}` retain the
original four corner indices/outputs and add explicit `UV_DDX` / `UV_DDY`.
Each array sample uses Derivative mode. Append a zero layer-index derivative
to each float2 gradient before the float3 array sampler; the first float2-only
trial was rejected by the compiler and restored before retrying. IDMap/global
UVs, class codes, array contents and geometry stay untouched.

Variation uses scale 1, 13 levels, Random Offset Variation 7.173, temporal dither
on, rotation/scale randomization off and Heightmap Influence 0. These are local
artistic settings, not SideFX/Epic standards. The neutral default Heightmap
is not used as world geography or as a class-dependent displacement map.
Current anti-aliasing is TSR (method 4); temporal stability and cost still
require separate review.

The inherited Normal sampler function contained three Color interpretations
and one Normal interpretation. In the bounded copy, all four now decode as
Normal. The master passes signed DirectX XYZ, removing its encoded `1-G`
operation. Refreshing the existing instance after function changes is necessary
to avoid stale bindings/glare. Rejected intermediate images were not accepted
as proof. Shared original Pegasus and Engine functions are unchanged.

Native readback and post-save images:
[receipt](../../assets/lesson07-squares-20261020/receipt.json),
[close-up before](../../assets/lesson07-squares-20261020/close-before.jpg),
[close-up after](../../assets/lesson07-squares-20261020/close-after.jpg),
[panorama after](../../assets/lesson07-squares-20261020/panorama-after.jpg).
The close pair uses the same explicit camera/FOV. Compilation returned no errors
and drained to zero jobs. The read-only verifier is
`scripts/ue/readback_lesson07_texture_variation.py`; it never loads/saves a map
or changes an asset. Native statistics: 610 pixel shader instructions, 41 pixel
texture samples, 9 samplers. These are counts, not a measured performance PASS.

Only five material assets were saved: the existing master/MI and three bounded
function copies. Four actors, 4096 components, transforms, material bindings and
all other previously audited assets remain unchanged. Map SHA remains
`d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75`;
the owner's dirty scene was not saved. UE PID10872 remains open; no Computer
Use, terrain cook or base rebuild occurred. Resume from these saved graphs,
not the scale-only checkpoint. Do not blindly replay first-import/tuning
scripts over this later graph. Fresh reopen, whole-area/temporal review,
owner visual acceptance and protected exact-commit proof remain pending.

## Current appearance checkpoint and next session (2026-10-20)

This section supersedes the earlier import-stage/render-pending appearance
notes below. Same #365/M3 candidate, branch `codex/365-world-graph`, Draft
PR #474. Delivery targets that existing PR; its head identifies the remote
checkpoint. GitHub #365 currently has no milestone assigned; ROADMAP still owns M3.

**Saved locally:** existing material instance and three existing texture arrays,
plus the preceding three Grass2 textures. The global colour black-patch repair
is retained. Existing Pegasus parameters now remove the defective global hue /
saturation influence (`Global Colour Strength=0`, `Global Saturation=0`,
`Global Brightness=0`), use `Detail Brightness=1`, `Macro Tiling=0.25` and
`Global Normal Flatten=0.2`. Detail Tiling remains 0.25. The former distant
20 m repetition is reduced to the 4 m texture period rather than enlarged into
a visible grid. This reduces visible distant repetition; it is not a stochastic
non-repeating shader or a finished near-field surface.

The existing Colour array uses native non-destructive Hue +25 degrees,
Saturation 0.7 and Brightness 1.1. This intentionally grades **all five slices**,
not only Grass0. Original Grass0 is ochre (mean encoded RGB 113.76/97.08/36.13);
Cliffs is almost neutral grey (181.15/181.40/181.66), so the broad grade shifts
the ground towards subdued green while retaining near-neutral limestone.
Original source pixels, all class codes and slice order remain intact. Normal
and Masks arrays now use `TMGS_FROM_TEXTURE_GROUP` to suppress distant aliasing;
IDMap filtering/mips are unchanged. These are measured artistic adaptations,
not tutorial defaults or geographic classifications.

[Retained native before/after captures and receipt](../../assets/lesson07-appearance-20261020/receipt.json):
[panorama before](../../assets/lesson07-appearance-20261020/panorama-before.jpg),
[panorama after](../../assets/lesson07-appearance-20261020/panorama-after.jpg),
[black patches before](../../assets/lesson07-appearance-20261020/black-before.jpg),
[black patches after](../../assets/lesson07-appearance-20261020/black-after.jpg).
The current pair uses the same explicit camera/FOV and completed native shader
compilation. The after image contains an owner selection outline/gizmo; that
is not a material artifact. This is a limited 956x431 panorama, not whole-world
visual acceptance. Native arrays remain 2048x2048x5, DXT1/BC5/DXT5, with sRGB
only on Colour. No actor transform, Landscape geometry, IDMap, global-colour
source, original slice texture or shader graph changed. Only four material
assets changed after the preceding Grass2 import. Original array/MI backups
remain under `Saved/RuntimeProof/Lesson07Appearance-20261020-1/before-assets`.

**Resume here:** open the existing `L_SaCalobra_Lesson07` map and inspect the
saved material assets; do not rerun terrain generation or the first-import
Grass2 script. The latter refuses an existing destination deliberately.
The bounded tuning source is `scripts/ue/tune_lesson07_landscape_appearance.py`;
its pre-change backup check also prevents blind replay over a later checkpoint.
The source recipe/package adapters for Grass2 are committed for reproducibility;
rendered intermediary PBR maps stay in local proof storage, and the saved UE
textures retain their source art. No Material Maker installation is needed to
open the saved consumer.

**Important session boundary:** the owner's map remains dirty and unsaved.
The saved map SHA is still
`d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75`.
Remote material delivery does not include arbitrary unsaved map edits. Current
read-only lighting is 6 lux, temperature disabled (6500 K stored), sun rotation
pitch/yaw/roll -35/0/-38, exposure min/max 1/1, bias 1. Earlier 80000 lux / EV15
trials are historical, not the current appearance producer. Do not replay those
old trials or save over the owner's scene. Streaming pool remains a local
session configuration; performance is not accepted.

Validation: 40 unique selected CPU tests passed, including optimized-Python
cross-project rejection of all three editor scripts; Ruff passed. Review fixes
add explicit (non-assert) save/guard checks, reject wrong editor checkouts and
pre-existing dirty import arrays, and roll back only touched arrays including
sRGB. They do not require reimporting the completed consumer. Fresh reopen,
protected exact-commit CI, whole-domain comparison to the reference, finer
limestone/grass detail and owner visual acceptance remain open. Next work is
visual review of this saved checkpoint, then bounded surface refinement only;
never restart the base terrain. No merge or overall Lesson07 PASS is claimed.

## Black global-colour patches: bounded live repair (2026-10-20)

Issue #365 / M3, local candidate on base
`c4d2a44aa2b79579507cda2babd448eab45e1144`. Status:
`GLOBAL_BRIGHTNESS_REPAIRED_SAVED_NATIVE_AB_VERIFIED`.

Native inspection found `Use Terrain Colour=true`, `Global Brightness=0.5`,
`Global Colour Strength=0.5` and `Global Saturation=0.5`. The existing Pegasus
HSV graph feeds both hue branches from the same Value expression: detail V,
2*detail V*global V, and global V through `Lerp_3Color`. Black pixels already
exist inside valid Grass2 regions of the source global colour. The new local
Grass2 colour and AO do not contain corresponding black pixels. Reducing
Global Colour Strength alone would not isolate the shared Value expression.

The bounded repair sets only **Global Brightness to 0.0**, selecting detail
Value while retaining the existing hue/saturation mix, classes, textures and
shader graph. This is an artistic consumer adaptation to defective source
colour modulation, not a SideFX default. The exact earlier Houdini stage
that produced the black RGB remains unisolated; original source RGB is retained.

Native API screenshots at the same explicit camera and FOV, after zero pending
asset/shader jobs, confirm the surface black patches disappear while terrain
shadows remain. The capture service reported near-black fraction 0.005 before
and 0.000 after (rounded service statistics, not an acceptance threshold).
One earlier fallback-shader image was rejected. Evidence is retained locally:
`Saved/RuntimeProof/Lesson07BlackPatches-20261020-1/summary.json`,
`fixed-camera-before.jpg`, `fixed-camera-after.jpg`, `compile-drain-0.0.json`.

`scripts/ue/repair_lesson07_global_colour.py` saved only the existing
`MI_Landscape_Instance_YACS`, with an original disk backup. All other live
parameters and four Landscape transforms/bindings are preserved; previously
unsaved MI settings are included in that scoped MI save. Disk conservation
against the preceding Grass2 receipt confirms every other audited asset is
unchanged. The map still hashes to
`d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75`.
The active editor remained PID 10872; the map was not saved, no terrain was
rebuilt and no Computer Use was involved. Fresh reopen, whole-area visual
acceptance and protected delivery remain separate and unverified. This repair
is included in the current appearance checkpoint described above.

## Grass2 appearance replacement candidate (2026-10-20)

Status: `APPLIED_SAVED_NATIVE_READBACK_PASS_RENDER_PENDING`. Owner-authorized scope is
muted green and grey limestone in the existing Grass2 class, evaluated across
the full Landscape from a distance. It does not authorize terrain regeneration,
mask reclassification or detailed world dressing.

The previous Grass2 source contains brown block-like rocks. The new selected
Forge variant `mediterranean_soil/limestone_grass2_v1` reuses the existing periodic
fragment recipe with smaller material-local fragments, muted olive/grey colours,
roughness 0.88 and normal strength 0.3. These are artistic candidate settings,
not geographic measurements or a SideFX standard. All 17 historical Forge
graphs remain byte-identical. Two native Material Maker/Godot runs exited 0 and
produced identical hashes for all five PBR maps. CPU validation ran 39 tests
without failures; Ruff and diff checks passed. Native source mean encoded RGB
is approximately (97.4,105.2,80.2), versus (102.0,80.0,44.9) for the old Grass2
slice. Pixel statistics describe the files, not visual acceptance.

The package is retained under
`Saved/RuntimeProof/Lesson07Grass2-20261020-1/package/grass2-package.json`.
Colour and DirectX Normal preserve the rendered bytes; Masks is packed as
AO/Roughness/Height/AO from the matching Forge outputs. Metallic is not Height.
The original EXR remains retained; there is no height rescaling or Landscape
height operation. The original texture sources and accepted terrain caches
remain intact.

The bounded importer is `scripts/ue/apply_lesson07_grass2.py`. It verifies the
active L07 world and four Landscape bindings, imports three new candidate
textures, and replaces only index 1 in the existing Colour/Normal/Masks arrays.
Indices 0,2,3,4 and the material-instance binding remain unchanged. It backs up
the array files and saves only the six scoped texture/array assets. It never
loads or saves a level, starts/closes UE, enables a listener, or cooks Houdini.
The original Grass2 textures remain available for rollback.

The existing authenticated Wingman/Loco channel executed the importer once in
editor PID 10872 without Computer Use, a new listener or an editor restart.
`live-import.json` confirms successful saving; `native-verification.json`
confirms the same four actors, transforms, material bindings, camera and
pre-existing dirty map/material-instance packages. All three arrays report
2048x2048x5 with the new source at index 1; other indices are unchanged.
Colour uses DXT1/sRGB, Normal BC5 and Masks DXT5 without sRGB.

Disk comparison confirms exactly six scoped asset changes. The map retains
SHA-256 `d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75`;
the other protected source files are unchanged. Original array backups remain
under the proof directory. Do not rerun the first-import command against the
already-created destination assets.

At the Grass2 import stage, rendered appearance was unverified. The later
black-patch repair above adds scoped native A/B images; fresh reopen and owner
visual acceptance remain unverified.
The native screenshot task did not complete; any late output is not a valid
before-image. No second capture was stacked and no camera or focus was changed.
The candidate is included in the current appearance checkpoint described
above. The existing whole-world admission gates remain in force.

## Local consumer repair and sampled verification (2026-10-20)

The local repair preserves the same four Landscape actors and existing
`L_SaCalobra_Lesson07` package in
`D:/yacs/work/lesson07-readback-39436127684-1`, based on
`5d4475af5fe04eade56ce87b2d62f257cd7095ef`. This is a working-tree candidate,
not a protected-CI or visual acceptance claim. The repaired map, existing material
instance and bounded derivative master are now promoted to the main local project
`D:/yacs/project`, with original map/instance backups retained. No source HIP or
terrain cache was regenerated.

Native measurements cover 65,032 boundary vertices and 1,040 collision queries.
All four retained source seams match exactly. The saved UE seams differ by
3.117â€“5.800 cm; every measured uint16 height matches the installed Houdini
Engine conversion using the corresponding actor's different Z scale. This
identifies a consumer quantization defect, not a reason to rebuild the source.
The boundary read found no allocated visibility weights. Measurements and
source comparisons are retained under local
`Saved/RuntimeProof/Lesson07Seams-20261020-1`.

The existing material instance now uses a bounded derivative of the original
Pegasus master in the isolated candidate. Its surface graph and texture bindings
are preserved. The derivative removes the out-of-scope grass output and uses
Epic's `MatLayerBlend_OverrideOpacityMask` with `LandscapeVisibilityMask` on
the main masked material. A separate hole material is not required by this
recipe. Native fresh material inspection confirms the actual graph connections.

The same map was backed up and saved after native refresh removed 16,384 cached
grass references from 4,096 components. Full source-mip hashes, texture bindings
and component transforms match before and after; no height data changed.
The refreshed candidate map is 1,841,267,493 bytes, SHA-256
`6e41be524255492e5b025f96ee218294275f41aa0fa34bca166fdeb11a1a8ad5`.
The local receipt is
`Saved/RuntimeProof/Lesson07Materials-20261020-refresh1/refresh.json`.
Fresh reopening of that cache-only repair completed with no reported native
dependency problems. The subsequent mask-only canary preserved every mip of
both composite and existing edit-layer heightmaps, including bindings and
transforms. The first completed canary exited with `0xC0000005` after log close;
its faulting module remains unknown. Explicit official `StopSession` followed
by invalid-session verification produced clean exit code 0 in the next canary
and the full update.

The full update used the same retained four BGEO tiles, existing transfer HDA,
actors and edit-layer GUIDs. It assigned common Scale.Z
`561.389892578125`, inverted source validity into UE hole weights, waited for
native layer composition and saved the existing map once. Only that map
changed: 1,838,638,056 bytes, SHA-256
`d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75`.
The receipt is
`Saved/RuntimeProof/Lesson07ConsumerUpdate-20261020-1/update.json`.
Fresh post-update readback measured a maximum seam Z difference of
`0.013910478999605402 cm` (about 0.139 mm), down from 5.800 cm.
The preserved original actor transforms still produce a maximum XY difference
of `0.03643035907043668 cm`; these are measured floating-point registration
residuals, not a newly invented acceptance tolerance.
Three source-selected interior NoData samples have four native weights of 255
each. Their editor Visibility traces still hit; the separate actual Simulate In
Editor world correctly returns MISS for all three holes and HIT for all twelve
valid controls (15/15 sampled results), as recommended by
[Epic's visibility documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-visibility-tool-in-unreal-engine).
The runtime session stopped cleanly (exit 0), with the map unchanged. This proves
the sampled hole/valid behavior, not whole-area collision or exact source-height
interpolation. Runtime versus rendered-triangle differences reached 4.247 mm;
Chaos has a separate height quantization whose exact triangle values were not
read back, so this is not an accepted tolerance or interpolation PASS.
Unallocated weights on other components remain explicitly unknown, not
reported as measured zeros.

Fresh native captures are retained without image editing:
[full material panorama](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/ue_panorama_material.png),
[full neutral panorama](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/ue_panorama_neutral.png),
[Scree-location material view](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/ue_closeup_scree.png),
[matching neutral view](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/ue_closeup_scree_neutral.png)
and [central seam view](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/ue_tile_seam_check.png).
The [capture review](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/consumer_repair_20261020/capture-review.json)
records limits: the Scree location contains mixed classes, sharp cliff ribs are
also present in the neutral/source views, and image appearance is not collision
proof. Main-material tessellation and all four Landscape Nanite flags were
observed disabled. Owner visual acceptance remains pending.

The latest local native build and 50 Automation tests passed in
`Saved/RuntimeProof/Lesson07NativeAPIBridge-20261020-retry1`. An earlier test
fixture crash is retained in the first run: UE 5.8 requires a texture owner
when initializing `FTextureSource`; the fixture was corrected and rerun.
These local dirty-tree results do not substitute for exact-commit protected CI.

Final local adapter tests ran 109 cases with no failures and two environment
skips; Ruff and diff checks passed. Documentation index i18n, structure, links
and freshness guards passed. The evidence-storage guard still rejects the
unchanged, pre-existing oversized
`docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json`;
that guard was not weakened. Fresh current-pin admission (readback 3) exited 0,
with four actors, 4,096 components, no structural reasons and unchanged map bytes.
Readback 2 retains the independently authenticated full repair chain.

Final SHA-256 conservation checks confirm the original Lesson07 HIP, base cache,
final cache and IDMap PNG are unchanged. Before publication, the remote branch was rechecked at
`5d4475af5fe04eade56ce87b2d62f257cd7095ef`. The owner subsequently authorized
publishing this same repair on the existing branch, without rebuilding terrain.
These native results remain dirty-tree evidence from before the delivery commit;
exact-commit CI is a separate gate.
Disk exhaustion interrupted a report write; verified backup relocation is recorded
in the promotion proof. Active assets and source data were preserved.

Source / Manual Edits / Procedural Detail describe the authoring workflow.
They do not mandate three UE edit layers. The existing base cache, final cache
and procedural-difference branch are retained; adding that difference again
to the already-final consumer would double the detail.

The actual material graph subtracts Offset:
`GridCoordinates = WorldXY_cm / TerrainScale - OffsetXY`.
With scale 50 and Offset (-8000,-8000), the authenticated Scree witness maps
to (2981.5,4311.49951172), the expected source texel center. The later noise
perturbation and four-neighbour shader sampling still require their actual
parameter values and rendered verification.

## Earlier Unreal startup repair and native inspection (2026-10-20)

The startup failure recorded below is resolved in a local owned diagnostic.
UE 5.8.2 editor session analytics called
`FShaderCompilerStats::GetTotalShadersCompiled` with null
`GShaderCompilerStats`: the L07 launcher had disabled its initialization with
`-NoShaderCompile`. The installed Engine DLL export/unwind mapping identifies
the crash return address at RVA `0x1f2cc44`, reached from the statistics call
at `0x531a2d`. Removing that flag, retaining `-NullRHI`, let the same staged
project load the canonical L07 and exit normally (code 0).
The launcher now reports process failure before attempting to read a missing
JSON report, preserving the primary error.

The diagnostic reused `D:/yacs/work/lesson07-readback-39436127684-1`;
reader and staging provenance remain `c98a89dc35b481c75a37ada06b92ae8194757975`,
with diagnostic work based on `52fb27e597608a290e72dec6cbd6d96dd6b77dc8`.
It did not recopy assets, cook Houdini, import or save the map.
The current receipt links the raw report, log and conservation hashes.
This local diagnostic is separate from protected CI.

That earlier native inspection observed all four actors and 4096 components. It does **not**
establish technical acceptance:

- Seven referenced Pegasus groundcover mesh packages are absent from the
  staged asset set and canonical `Content/PegasusDemo/Meshes` tree. Missing
  dependencies remain failures; no substitute vegetation is generated.
- All actors have the single edit layer `Houdini_Unified_Final`, target layer
  `__LANDSCAPE_VISIBILITY__`, and no separate hole material. These observations
  do not prove source/manual/detail separation or working NoData holes.
- The strict scale assertion rejects the measured XY scale
  `49.99999701976776` versus nominal `50`. Raw measurements and the assertion
  are retained; this small numerical difference is not evidence of a changed
  source terrain, and no tolerance or geometry was adjusted to obtain PASS.
- Four diagnostic collision hits reproduce earlier values; full source-height,
  tile-edge, visibility/collision and rendered-material acceptance remain open.
  Historical rounded landmarks are not exact source witnesses.

Therefore the crash repair passes its native startup check, while L07 retains
`LESSON07_TECHNICAL_PASS: false`. The original failure and all historical
receipts below remain evidence of their own executions.

## Current Houdini preview correction (2026-10-20)

This section and the current receipt supersede the earlier preview claims below.
The reviewed HIP `2ea5eafb0e5b2965ef718243a81aa83919255d0cb2af56444d0e7d6bf99fd8d1`
was resumed and backed up, not rebuilt from L06. The corrected
[L07 HIP](../../../worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc)
is SHA-256 `340c7f8aa20e0d3e34b7a8416981eaa115eae4e4de025337c5e229e00d5ae775`.
Only display branches, a native diagnostic crop and the Scree camera changed.
L06 HIP/cache, exported IDMap/colour, terrain layers and Unreal assets were
preserved.

Deleting `volvis` did not produce the claimed RGB preview. Native
[HeightField Visualize](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_visualize.html)
now uses custom tint, `cdvolume="r g b"` and no colour ramp.
The palette and isolation modes explicitly select `id` and `mask`.
The cooked native `volvis` fields are checked: merely setting parameters is
insufficient when a node conversion retains its former internal network.
The repair restores the native HDA definition; it does not author a replacement
shader or terrain algorithm.

The historical Scree centroid was not an authenticated class witness.
The replacement is PNG texel `(2981, 4311)`, native voxel `(2981, 11688, 0)`,
at Houdini `(-2509.25, 44.6479721, -1844.2502441) m`. A 128 m native crop retains
0.5 m sampling and 34 Scree samples. The original Pegasus decoder has zero
classification mismatches in that crop. A 32 m neighbourhood is used only to
choose a diagnostic camera target, not to change the material mask.
The camera sits above the crop's maximum height to avoid the surrounding cliff.

Ten frames were rendered in fresh Houdini 22.0.466 processes from the saved HIP
and SHA-authenticated small preview caches. The global frame has 21.30%
chromatic pixels; neutral has 0.00068%; the Scree closeup has 170 red-mask pixels.
All three display signal checks passed. These checks **are not visual
acceptance**. Earlier failed camera/render attempts remain in local
`D:/yacs/work/lesson07-unified-20261019/render_history`.

The full-resolution closeup exposes very steep, jagged source walls. Nine
nearby samples already range from 39.24 to 152.14 m in retained Stage 1; their
final-minus-base deltas range from -0.016 to +0.133 m. This limited observation
shows that those large height differences predate the preview correction; it
does not establish terrain quality or full-domain correctness. No smoothing or
material concealment was applied. The old cove/transition camera labels and UE
images remain unaccepted landmark evidence.

The L07 source map remains PEG-02-07 ID encoding at 05:03â€“05:28 / 08:01â€“08:06
and colour export at 06:24â€“07:26 / 10:36â€“11:54. Diagnostic cameras, crop and
display controls are documented YACS adaptations using native SideFX nodes.
The source export recipe was not regenerated by this correction.

## 1. Executive Summary & Review Remediation

The numbered items below retain the earlier remediation report following commit `b84ff443`; sections 1â€“7 are historical measurements and claims, not acceptance of the current UE consumer. The current verification receipt records `LESSON07_REQUIRES_NATIVE_GEOMETRY_RECHECK` and `LESSON07_TECHNICAL_PASS: false`. The later geometry warnings and the acceptance status in section 8 supersede the earlier all-points-resolved conclusion. Preserve the accepted L06 cache while checking the affected transfer and UE consumer.

1. **Houdini 3 Preview Modes Remediated (Krok 1)**:
   - Root cause resolved: upstream `volvis` detail dictionary attribute was overriding the viewport primitive rendering, forcing identical color ramps regardless of display flag.
   - Stripped `volvis` via `attribdelete` in `PREVIEW_GLOBAL_COLOR` to allow native OpenGL volume primitives (`r, g, b`) to render authentic macro terrain coloring.
   - Configured `PREVIEW_NEUTRAL_SHADING` with `heightfield_isolatelayer` and stripped color/volvis attributes for pure clay geometry evaluation.
   - Configured `PREVIEW_IDMAP` with discrete 5-class Pegasus color ramp (`hou.rampBasis.Constant`) bound to `cdvolume="id"`.
   - Verified that all modes render completely distinct pixel distributions and hashes.
2. **Scree Isolation Remediated (Krok 2)**:
   - Explicitly configured `ID_TO_LAYER.parm("id_layer").set("255")` on the decoder node.
   - Verified full-resolution cache contains exactly $781$ scree voxels (`id == 1.0` / code 255), exactly matching the accepted Lesson 06 receipt.
   - Set `filter="point"` on `PREVIEW_RESAMPLE` to preserve categorical class IDs $(0, 64, 128, 191, 255)$ without continuous linear interpolation.
   - Identified densest scree cluster at Centroid $(X=-2502.78\text{ m}, Y=460.95\text{ m}, Z=1845.95\text{ m})$ and framed camera `cam_scree_site` directly onto the gravel slope surface.
3. **Texture Array Scree Slice & UE Assets Confirmed (Krok 3)**:
   - Verified `slice_4_scree_masks.png` channel values: $R=255$ (AO 1.0), $G=223.46$ (Roughness $0.85\text{--}0.90$), $B=186.79$ (Height/Displacement $0.73$).
   - Executed [verify_ta_scree.py](../../../scripts/ue/verify_ta_scree.py) inside Unreal Editor: confirmed `TA_Masks_Unified` slice 4 references `/Game/Generated/YACS/Lesson07_Unified/Textures/Slices/T_Scree_Masks`.
   - Re-saved and verified on-disk packages for `TA_Masks_Unified.uasset`, `TA_Colour_Unified.uasset`, and `TA_Normal_Unified.uasset`.
   - Deleted temporary scratch file `scree_height_test.png` and obsolete fallback level script `setup_lesson07_level.py`.
4. **UE Landscape Geometry Read Back & Quantization Quantified (Krok 4)**:
   - Read back actual geometry directly from `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07`:
     - 4 Landscape actors (`SaCalobra_Unified_0_0`, `0_1`, `1_0`, `1_1`), each with 1024 components ($32 \times 32$) = **4096 total components**.
     - Section size: 127 quads, $2 \times 2$ subsections per component ($254 \times 254$ quads per component), $8128 \times 8128$ quads per tile ($8129 \times 8129$ vertices).
     - Material assigned: `MI_Landscape_Instance_YACS`.
     - Quantization unit: $2.2965\text{ cm/step}$ across $[-5\text{ m}, 1500\text{ m}]$ (65535 levels).
     - Verified vertical elevations against Houdini source cache via line trace raycasts:
       - Puig Major Summit: UE $1437.114\text{ m}$ vs source $1437.160\text{ m}$ ($\Delta = -4.58\text{ cm}$, $-1.996$ quantization steps).
       - Sa Calobra Cove Beach: UE $10.291\text{ m}$ vs source $10.340\text{ m}$ ($\Delta = -4.93\text{ cm}$, $-2.145$ quantization steps).
       - Scree Cluster 1: UE $460.917\text{ m}$ vs source $460.950\text{ m}$ ($\Delta = -3.29\text{ cm}$, $-1.434$ quantization steps).
       - Inland Center $(0, 0)$: UE $473.117\text{ m}$ vs source $473.508\text{ m}$ ($\Delta = -39.26\text{ cm}$).
5. **UE Cameras Aligned & Material/Neutral Pairs Captured (Krok 5)**:
   - Corrected Sa Calobra Cove framing: positioned camera at $(350, 80, -950)\text{ m}$ aiming at $(470, 10, -1060)\text{ m}$, framing the beach, cove inlet, and coastal cliff walls.
   - Corrected Scree framing: positioned camera at $(-2550, 520, 1780)\text{ m}$ aiming at $(-2503, 461, 1846)\text{ m}$, looking down onto the actual scree slope surface with zero void or black wall artifacts.
   - Captured 8 offscreen shots including identical-camera material and neutral clay pairs for panorama and scree closeup, plus summit, cove, boundary transition, and domain center tile seam.
6. **Verification Receipt & Reporting Corrected (Krok 6)**:
   - Updated [lesson07-material-setup-verification-receipt.json](lesson07-material-setup-verification-receipt.json) strictly with measured readback data.
   - Removed unmeasured "60 FPS" claims, recording `performance_pass: false` and `performance_note: "DEFERRED_AFTER_M3"`.

---

## 2. Geometry Transfer & Unreal Engine Landscape Structure

### Transport Envelope & Padding
To satisfy Unreal Engine's native section sizing ($127 \times 127$ quads per section, $2 \times 2$ subsections per component $\implies 254 \times 254$ quads per component $\implies 8128 \times 8128$ quads per $32 \times 32$ component tile):
- **Source Domain**: $8000 \times 8000\text{ m}$ ($16\,000 \times 16\,000$ cells at $0.5\text{ m}$ spacing).
- **Transport Envelope**: $8128 \times 8128\text{ m}$ ($16\,257 \times 16\,257$ vertices total), divided into 4 identical tiles:
  - `SaCalobra_Unified_0_0`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_0_1`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
  - `SaCalobra_Unified_1_0`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_1_1`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
- **Padding Handling**: Each tile contains $64\text{ m}$ ($128$ quads) of outer padding beyond the $4000\text{ m}$ quadrant span. The outer boundary vertices contain `Alpha=0 / NoData`, cleanly separating border geometry from the active domain and preventing classification as legal Grass (ID=0).
- **Seam Elevation Continuity**: Maximum elevation difference at interior tile boundaries is strictly $0.000000\text{ m}$.

### Unreal Engine Read-Back Metrics ([readback_lesson07_geometry.py](../../../scripts/ue/readback_lesson07_geometry.py))
- **Level Package**: `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07` ([L_SaCalobra_Lesson07.umap](../../../Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap), $1\,842\,190\,204\text{ B}$, SHA-256 `61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7`)
- **Landscape Actors**: 4 actors (`SaCalobra_Unified_0_0`, `0_1`, `1_0`, `1_1`)
- **Total Components**: $4 \times 1024 = 4096$ components (`components_pass = true`)
- **Component Grid**: $32 \times 32$ components per landscape
- **Section Size**: 127 quads, $2 \times 2$ subsections per component ($254 \times 254$ quads per component)
- **Tile Geometry**: $8128 \times 8128$ quads ($8129 \times 8129$ vertices)
- **Spacing / Scale**: $50.0\text{ cm}$ ($0.5\text{ m/px}$), horizontal scale = `(50.0, 50.0)`
- **Assigned Material**: `/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS`

### 16-Bit Quantization & Raycast Elevation Verification
- **Quantization Parameters**:
  - Height span: $[-5.0, +1500.0]\text{ m}$ ($150\,500\text{ cm}$) over $65\,535$ levels.
  - Step size: $2.2964674\text{ cm/step} = 0.022964674\text{ m/step}$.
  - Expected quantization tolerance: $\pm 1\text{--}2$ discrete steps ($\sim 2.3\text{--}4.6\text{ cm}$) on sampled vertex peaks.
- **Line Trace Elevation Sampling Results**:
  | Target Point | UE Coords $(X, Y)\text{ cm}$ | Houdini Coords $(X, Z)\text{ m}$ | Source Height | UE Hit Height | Delta $\Delta z$ | Quantization Steps | Hit Actor |
  |---|---|---|---|---|---|---|---|
  | **Puig Major Summit** | $(-128375, 349525)$ | $(-1283.75, 3495.25)$ | $1437.160\text{ m}$ | $1437.114\text{ m}$ | $-4.58\text{ cm}$ | $-1.996$ | `SaCalobra_Unified_0_1` |
  | **Sa Calobra Cove Beach** | $(47000, -106000)$ | $(470.0, -1060.0)$ | $10.340\text{ m}$ | $10.291\text{ m}$ | $-4.93\text{ cm}$ | $-2.145$ | `SaCalobra_Unified_1_0` |
  | **Scree Cluster 1** | $(-250278, 184595)$ | $(-2502.78, 1845.95)$ | $460.950\text{ m}$ | $460.917\text{ m}$ | $-3.29\text{ cm}$ | $-1.434$ | `SaCalobra_Unified_0_1` |
  | **Inland Center $(0, 0)$** | $(0, 0)$ | $(0.0, 0.0)$ | $473.508\text{ m}$ | $473.117\text{ m}$ | $-39.26\text{ cm}$ | $-17.095$ | `SaCalobra_Unified_1_1` |

---

## 3. Global Material Mapping Derivation & Alignment

### Mathematical Closed-Form Parameter Derivation
In Unreal Engine, coordinates are in centimeters ($1\text{ m} = 100\text{ cm}$).
The domain spans $X \in [-4000, +4000]\text{ m}$ and $Z \in [-4000, +4000]\text{ m}$, transforming to:
$$X_{UE} \in [-400\,000, +400\,000]\text{ cm}, \quad Y_{UE} \in [-400\,000, +400\,000]\text{ cm}$$

With texture resolution $N = 16\,000$ and sample spacing $\Delta = 50\text{ cm}$:
1. **Terrain Scale**: $\Delta = 50.0\text{ cm/px}$
2. **Terrain Resolution**: $N = 16\,000.0$
3. **UV Rotate**: $0.0^\circ$ (Houdini $X \to$ UE $X$, Houdini $Z \to$ UE $Y$; raster coordinate system aligns with world axes).
4. **Offset â€” documented equation requires graph verification**: The previous report used the following additive expression. It has not been authenticated against the current `M_Pegasus_Landscape_Master` graph:
   $$\text{UV} = \frac{(X_{UE}, Y_{UE}) + \text{Offset}_{xy} \times \text{Scale}}{\text{Resolution} \times \text{Scale}}$$
   For the southwest corner $(X=-400\,000, Y=-400\,000)$ to map to UV $(0.0, 0.0)$:
   $$-400\,000 + \text{Offset}_x \times 50.0 = 0 \implies \text{Offset}_x = \frac{+400\,000}{50.0} = +8000.0$$
   $$\text{Offset}_{\mathrm{additive}} = (+8000.0, +8000.0, 0.0, 0.0)$$
   Under that additive convention, the domain corners map to UV (0, 0) and (1, 1). The historical parameter readback below instead contains -8000, which would map those corners to (-1, -1) and (0, 0) under this formula. The actual master may apply a different convention; inspect its graph, texel centers and landmark registration before changing any asset. This arithmetic correction does not certify the saved material mapping.
5. **Num IDmap Layers**: $5.0$

### Historical Material Instance Parameter Readback ([MI_Landscape_Instance_YACS.uasset](../../../Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset))
- `Terrain Resolution`: $16000.0$
- `Terrain Scale`: $50.0$
- `UV Rotate`: $0.0$
- `Offset`: `(-8000.0, -8000.0, 0.0, 0.0)`
- `Num IDmap Layers`: $5.0$
- `Global Colour Strength`: $0.5$
- `Global Specular Scale`: $1.0$
- `Detail Brightness`: $1.5$
- `Terrain IDmap`: `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap`
- `Terrain Colour`: `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color`
- `Colour Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified`
- `Normal Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified`
- `Masks Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified`

---

## 4. Scree Remediation & Texture Arrays

### Master Material Masks Contract Compliance
- **Contract**: **R = AO, G = Roughness, B = Displacement**
- **Slice Assignment**:
  - Slice 0: Grass (ID 0)
  - Slice 1: Grass2 (ID 64)
  - Slice 2: Sand (ID 128)
  - Slice 3: Cliffs (ID 191)
  - Slice 4: Scree (ID 255)
- **Scree Source**: Lesson 05 Material Forge (`limestone_scree_v1/export/`)
- **Verified Mask Channels ([slice_4_scree_masks.png](file:///d:/yacs/work/lesson07-unified-20261019/slice_4_scree_masks.png))**:
  - Red (R): Ambient Occlusion, mean $1.00$ ($255$)
  - Green (G): Roughness, mean $0.88$ ($223.46$, within range $0.85\text{--}0.90$)
  - Blue (B): Displacement / Height, mean $0.73$ ($186.79$)

### Saved & Verified Texture2DArray Packages
- `TA_Colour_Unified.uasset`: $27\,552\,324\text{ B}$, SHA-256 `682d7c3a0bd80f58d7cfe0f924b08a537d3f28dd4301f9810770b0d34b571e33`, `srgb=true`, `TC_Default`
- `TA_Normal_Unified.uasset`: $45\,545\,946\text{ B}$, SHA-256 `15e531bfa888fe7c8b87a8d9b8a94a860029c3944b48a109ec179c00af28d76b`, `srgb=false`, `TC_Normalmap`
- `TA_Masks_Unified.uasset`: $12\,087\,571\text{ B}$, SHA-256 `0de2cd408ae436d5b8d96e5e5ea666eb3a9e0dc0c936b3a8d21beb8e0914476b`, `srgb=false`, `TC_Masks`

---

## 5. Houdini Daily Preview & Checkpoint Verification

### Look-At Camera Rigging & Resolution
In [SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc](../../../worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc) ($570\,182\text{ B}$, SHA-256 `2ea5eafb0e5b2965ef718243a81aa83919255d0cb2af56444d0e7d6bf99fd8d1`):
- All cameras use native null targets wired to `lookatpath`. Camera local -Z alignment dot product with target aim vector is strictly **$1.00000000$** across all 5 cameras.
- `PREVIEW_RESAMPLE` creates an interactive $2000 \times 2000$ ($4.0\text{ m}$) proxy with `filter="point"`, preserving discrete categorical ID codes $(0, 64, 128, 191, 255)$ without continuous blending. Full $16000 \times 16000$ ($0.5\text{ m}$) feeds export nodes directly from `FINAL_CACHE`.

### 4 Authentic Viewport Preview Modes (1920x1080)
1. [3d_preview_global_color.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_global_color.png): $949\,800\text{ B}$, SHA-256 `2a80d3b31045...`, mean $91.83$, non-black $58.5\%$. Native RGB volumes rendered directly after stripping overriding `volvis`.
2. [3d_preview_neutral_shading.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_neutral_shading.png): $1\,044\,646\text{ B}$, SHA-256 `880012514859...`, mean $90.15$, non-black $58.6\%$. Pure neutral grey clay geometry shading.
3. [3d_preview_idmap_palette.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_idmap_palette.png): $1\,853\,941\text{ B}$, SHA-256 `122e5ed8078f...`, mean $52.24$, non-black $50.1\%$. 5-class discrete Pegasus color palette.
4. [3d_preview_scree_isolation.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_scree_isolation.png): $1\,017\,936\text{ B}$, SHA-256 `8dc590953849...`, mean $70.03$, non-black $56.7\%$. Decoded scree layer 255 visualized in vivid red.

### Landmark Camera Renders
- [3d_cam_panorama.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_panorama.png): $949\,800\text{ B}$, SHA-256 `2a80d3b31045...`, mean $91.83$
- [3d_cam_puig_major.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_puig_major.png): $382\,413\text{ B}$, SHA-256 `6b5baea368b2...`, mean $72.29$
- [3d_cam_sa_calobra_cove.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_sa_calobra_cove.png): $340\,135\text{ B}$, SHA-256 `76d9eae1be6a...`, mean $51.81$
- [3d_cam_scree_site.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_scree_site.png): $183\,609\text{ B}$, SHA-256 `7ede8aec9224...`, mean $143.14$, non-black $100.0\%$
- [3d_cam_scree_site_isolation.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_scree_site_isolation.png): $193\,216\text{ B}$, SHA-256 `40a87e60b9ac...`, mean $142.13$, non-black $100.0\%$
- [3d_cam_transition.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_transition.png): $82\,926\text{ B}$, SHA-256 `623e698401ef...`, mean $165.42$, non-black $100.0\%$

---

## 6. Historical Unreal captures â€” not current acceptance

The following images and descriptions are the earlier submission. Their
claims of seamless geometry, authentic scree framing, cove location and a
class-boundary transition were not established by native measurements.
The later audit found actual seam differences and corrected the scree camera.
Retain these files as historical evidence; use the remediation receipts and
new captures for the repaired candidate.

Eight high-resolution offscreen renders were captured using native `AutomationLibrary.take_high_res_screenshot` under direct PBR sunlight:

1. [ue_panorama_material.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_panorama_material.png) ($2\,650\,872\text{ B}$, SHA-256 `c74bd5b84bef...`, mean $134.10$, non-black $100.0\%$): Full $8 \times 8\text{ km}$ landscape shaded with `MI_Landscape_Instance_YACS`.
2. [ue_panorama_neutral.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_panorama_neutral.png) ($1\,901\,267\text{ B}$, SHA-256 `2cfea8063cfc...`, mean $173.59$, non-black $100.0\%$): Identical camera on neutral clay `M_TerrainReview` verifying pure relief and seamless geometry.
3. [ue_closeup_scree.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_scree.png) ($3\,217\,612\text{ B}$, SHA-256 `a64f9ea56193...`, mean $95.66$, non-black $75.4\%$): Direct framing on Scree Cluster 1 gravel surface; verified Mediterranean limestone response with zero dark voids.
4. [ue_closeup_scree_neutral.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_scree_neutral.png) ($2\,155\,082\text{ B}$, SHA-256 `b187162d78ba...`, mean $100.17$, non-black $100.0\%$): Identical scree camera on neutral clay confirming slope surface continuity.
5. [ue_closeup_puig_major.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_puig_major.png) ($2\,577\,999\text{ B}$, SHA-256 `c812c2f5e02b...`, mean $166.02$, non-black $100.0\%$): Summit crags showing pale limestone cliff normal map relief.
6. [ue_closeup_sa_calobra_cove.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_sa_calobra_cove.png) ($2\,449\,739\text{ B}$, SHA-256 `f12a07b1c7cf...`, mean $96.30$, non-black $94.8\%$): Framed beach, cove inlet, and coastal cliff walls.
7. [ue_closeup_transition.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_transition.png) ($2\,852\,572\text{ B}$, SHA-256 `da25ec9c99fa...`, mean $84.86$, non-black $75.8\%$): Two-class boundary transition zone demonstrating crisp classification without blending artifacts.
8. [ue_tile_seam_check.png](../../../worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_tile_seam_check.png) ($3\,668\,402\text{ B}$, SHA-256 `213260e4fa95...`, mean $171.47$, non-black $98.7\%$): Domain center tile seam boundary looking along $X=0$ and $Y=0$ axes; zero visible elevation step or texture misalignment.

---

## 7. Historical submission inventory & checksums

This table records the earlier submission, including the superseded L07 HIP
identity. Current source and repaired-package identities are recorded in the
verification receipt; this table is not a current synchronization manifest.

| Asset / File Description | Location | File Size | SHA-256 Checksum |
|---|---|---:|---|
| **L06 Input Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc` | $391\,364\text{ B}$ | `7701a844bd82d1496995866676a20ee069e9cac6e873889aca02a64be3ae2abb` |
| **L07 Output Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc` | $570\,182\text{ B}$ | `2ea5eafb0e5b2965ef718243a81aa83919255d0cb2af56444d0e7d6bf99fd8d1` |
| **Stage 1 Base Height Cache** | `D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc` | $519\,575\,557\text{ B}$ | `08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952` |
| **Stage 5 Final IDMap Cache** | `D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc` | $4\,808\,520\,505\text{ B}$ | `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24` |
| **Pegasus IDMap PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png` | $12\,392\,456\text{ B}$ | `cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3` |
| **Pegasus Global Color PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png` | $398\,192\,590\text{ B}$ | `90bd39006ed5f56888ef9a3de887c7840bc8ff9782c11d68062755b516afbb7b` |
| **UE Durable Map** | `Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` | $1\,842\,190\,204\text{ B}$ | `61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7` |
| **UE Material Instance** | `Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset` | $40\,261\text{ B}$ | `2e2256df25fee01d9975c67570e8f7839836a707374ee7440c624ac5a64c428c` |
| **Colour Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified.uasset` | $27\,552\,324\text{ B}$ | `682d7c3a0bd80f58d7cfe0f924b08a537d3f28dd4301f9810770b0d34b571e33` |
| **Normal Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified.uasset` | $45\,545\,946\text{ B}$ | `15e531bfa888fe7c8b87a8d9b8a94a860029c3944b48a109ec179c00af28d76b` |
| **Masks Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified.uasset` | $12\,087\,571\text{ B}$ | `0de2cd408ae436d5b8d96e5e5ea666eb3a9e0dc0c936b3a8d21beb8e0914476b` |
| **Verification Receipt** | `docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json` | $14\,500\text{ B}$ | *(tracked in repo)* |

---

## 8. Conclusion & Acceptance Status

Current acceptance follows the [verification receipt](lesson07-material-setup-verification-receipt.json), not the earlier all-six-points-resolved claim:

- `status: LESSON07_REQUIRES_NATIVE_GEOMETRY_RECHECK`
- `LESSON07_TECHNICAL_PASS: false`
- `native_recheck_required: true`
- `visual_review: PENDING_FINAL_M3_AUDIT`
- `performance_pass: false` (`performance_note: "DEFERRED_AFTER_M3"`)

Successful source/cache or export checks retain their own scope. They do not establish correct UE actor transforms, source-coordinate height agreement, visibility, collision, material registration or fresh reopen. The 39.26 cm historical landmark residual is not by itself a measured tile-to-tile step: the reported interior tile edges are at -0.25 m, while that landmark is at (0, 0). Measure both sides of the actual seams and compare against the properly interpolated source before diagnosing a vertical gap.


## Current geometry acceptance warning (2026-10-20)

The previous transfer discarded `Alpha`. New code preserves it as a `visibility` volume and zeroes validity outside the unified source footprint. This is not yet proof of visible holes: the native UE material must use `LandscapeVisibilityMask`. Existing saved UE content is unchanged, and destructive rebake now requires deliberate `YACS_LESSON07_ALLOW_REBAKE=YES`. The raycast report had deviations up to 39.26 cm and a false shared quantization assumption despite differing actor Scale.Z. Native UE geometry, visibility and collision need a new verified run before claiming `LESSON07_TECHNICAL_PASS`.

### Local/remote identity audit (2026-10-20)

At `c6cd4c0982cf0ee5fa1575cc0cd496d8d17b708b`, independent read-only
inspection authenticated the L07 map, MI, Pegasus master, IDMap, global colour
and three texture arrays against their Git LFS objects. The map remains
`61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7`.
The L06 source and all four saved native transport tiles also match the
successful run `39390349735`; its manifest SHA-256 is
`66847b4a614e748a0012dcefabbbc6f2be9b0326f0a863714e690cb71c068a8f6`.
This proves the retained bytes, not that Unreal loaded or accepted them.

The intended L07 consumer is exclusively
`/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07`.
The dedicated readback launcher copies those saved assets into an isolated
project and checks the loaded package. Run `39413841851` stopped before copying
or starting Unreal because of the disk reserve; run `39420689675` skipped
Unreal after its upstream CI failed. Neither produced a native L07 readback.
The 28 ordinary Automation tests in run `39413855349` validate general project
regressions and DLLs, not L07 terrain, materials or appearance.

The installed Live Host is a different consumer. Its `latest_verified` registry
and resolver pin `/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface`
on installed source `5a3517ee74b7477832af66f1727c4e4510c8f80b`.
The observed state was `STALE_OR_DEAD_NOT_LIVE`, last heartbeat
`2026-10-18T05:48:11Z`. Restarting that profile would still open the road
checkpoint, not L07. Workspace/default editor startup separately names
`L_SaCalobraAccepted_20261004`. Do not substitute either default for the explicit
L07 package or relabel L07 as `latest_verified` without its required evidence.

Two automatically triggered workflows also have different purposes:
`blender-material-forge-reference.yml` checks retained
`material-forge-v2-final/run-a` materials, not L07's
`limestone_scree_v1` inputs; run `39420697663` failed before Blender on missing
`validation.json`. The Embark workflow and broker `m3-terrain` still concern
Passo Giau/SP638; run `39420689680` had `execute_proof=false` and did not generate
terrain. Preserve applicable regression gates, but never present these jobs as
L07 delivery. L07 remote evidence must identify its exact package, source SHA,
asset hashes and actual native consumer.

The related remote repair conversation also reports this same PR #474, branch,
`c6cd4c0` source and native/CI run identities. No active second L07 writer was
observed. The other recent changes were owner-requested skills; the older
separate worktree was performing a read-only storage audit. The inactive Live
Host is therefore not evidence that the remote coding task generated another
world. A declared hourly cloud follow-up could not be independently checked for
schedule state; an idle chat does not guarantee that it will stay idle.

Continue with one writer on the affected paths. Before any subsequent write,
recheck the remote head and the same L07 map/source identities above. A required
isolated proof copy must retain their hashes. Report old Material Forge and
Passo Giau regression jobs separately from L07 acceptance, and timestamp free
disk observations instead of presenting an old failure log as current capacity.


## 2026-10-20 L07 UE consumer repair gate (non-destructive)

The accepted full-domain L06 cache remains frozen and SHA pinned. Earlier rounded-height, 4-actor and 4096-component records cannot establish a seam-free driveable UE landscape. The read-only Windows source audit authenticated the unchanged source but the older four-tile transport manifest has not established an Unreal `visibility` layer. Fresh UE readback failed during module load before any geometry could be verified. A separate module inventory confirmed both project DLLs exist, but did not prove ABI/build compatibility. Remediation must be carried out in isolated, bounded staging before any opt-in bake, and validate `LandscapeVisibilityMask`, source-coordinate seam alignment, collision, materials and frame time independently. Do not set a technical PASS on a static inventory, successful source hash or successful DLL compile alone.


### Native repair test: 2026-10-20 (first runner attempt)

A native 4-tile Houdini test (Actions 39389560761) authenticated the unchanged L06 SHA-256, then failed on the first tile at the former [0,1] Alpha-range assertion. The accepted L06 Stage 1 explicitly imports a binary validity raster with heightscale 255; accepting any positive Alpha as valid is its already-verified convention. The L07 transfer now converts the *copy* to exact 0/1 while preserving all other valid source data and forcing outer padding to 0. This is a versioned transport repair, not a terrain rebuild. Native replay must still verify all four saved tiles and actual Unreal hole-material/collision behavior. Old run status stays FAILED; source SHA and original map are untouched.


### Native source transport retry 39390052167

Hython successfully wrote all four binary Alpha-normalized native .bgeo.sc tiles (about 0.50 GiB total, D:/yacs/work/lesson07-native-proof-39390052167-1). Acceptance stopped at a 0.000244 m discrepancy between nominally co-located world coordinates stored as float32. This is the expected representational quantization scale of km-scale float32 volume transforms, not a measured vertical surface gap. The world coordinate comparison now allows <=0.0005 m (0.5 mm), while the independent height seam threshold remains <=0.0001 m (0.1 mm). The old run remains FAILED; a fresh native run must establish both the true height and visibility seams.


### Native source transport success 39390349735

[Run 39390349735, job 118520101615](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39390349735/job/118520101615) completed successfully on `c575cf21c884455595650a173fa6863254527dc0`. Its status is `NATIVE_TRANSFER_VERIFIED_NOT_UE_ACCEPTED`. The accepted L06 source SHA256 remained `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24`; four saved native tiles totalled 0.50 GiB in `D:/yacs/work/lesson07-native-proof-39390349735-1`.

All four height edges and all four normalized validity edges were compared across 8129 samples each: sample error was **zero**. World-position error was `0.000244140625 m`, within the separate 0.5 mm coordinate tolerance. The accepted source's bilinearly interpolated height at `(0, 0)` was `473.5955810546875 m`. Preserve these source and export results; the earlier failed run statuses remain unchanged.

The receipt explicitly keeps `masked_hole_material_ue_verified=false`, `center_0_0_ue_collision_verified=false` and `saved_map_mutated_by_this_job=false`. Validity continuity does not prove the installed Houdini Engine translator's hole polarity. Before a full UE transfer, verify known valid land, known NoData and padding in a bounded native canary, including rendered holes and collision. Do not infer the result from the layer name or mask seam test alone.

### Ordinary Editor build blocker and module isolation

At source HEAD `5a33c31a43e4933547a64bcb12e78552ce06e83a`, the ordinary Editor
build in [run 39397896686, job 118545978608](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39397896686/job/118545978608)
failed in Unreal Header Tool before Automation or L07 consumer readback. The
first compiler diagnostic is:

```text
YacsPcgWitnessToolset.h(21): Error: Unable to find parent class type for 'UYacsPcgWitnessToolset' named 'UToolsetDefinition'
Result: Failed (OtherCompilationError)
```

The build exited with code 6. Conditional `ToolsetRegistry` dependency selection
in `YetAnotherCyclingSimEditor.Build.cs` does not isolate the reflected witness
classes or their registration code from the common Editor module. A supported
module/target boundary must isolate those opt-in dependencies and be validated
with the ordinary and PCG365 Editor targets. Do not re-enable experimental
plugins in the byte-pinned common `.uproject` merely to bypass the failure.
This run provides no new L07 geometry, collision, visibility or visual PASS.

The same UHT error recurred in [run 39401819414, job 118559693068](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39401819414/job/118559693068), whose PR source was `0c94f388b0551ec0e3bfed57d758b3c35c356565`. The repair moves the reflected witness and registration into the disabled-by-default `Plugins/YacsPcgWitness` Editor plugin, enabled only by the separate PCG365 target. The ordinary target and pinned `.uproject` are unchanged.

**Initial ordinary Editor build and Automation PASS:** [run 39411137356, job 118589885665](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39411137356/job/118589885665), exact source `10e182ca9ab12894ba73787c9d9b6042cbef33fa`. The build reported `Result: Succeeded`; Automation discovered 28 tests, passed all 28, with zero failed/skipped/errors and two warnings. Protected CyclingSim CI also succeeded. [Native artifact 12259896881](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39411137356/artifacts/12259896881) has SHA256 `031aa65ecee7afd7214380ec5fb597fadb6a644db0099c8b5a18d8b0cd7a29eb`. This confirms the ordinary UHT/build blocker is repaired; it predates the L07 native getter and did not read or accept the saved L07 map.

**Fresh ordinary Editor build and Automation PASS, including the L07 getter:** [run 39413855349, job 118599568420](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413855349/job/118599568420), exact source `e2aed213870a7151106049a7b56953eaba919d6f`, built successfully and passed 28/28 tests, with zero failed/skipped/errors and two warnings, including the missing-route diagnostic from `CyclingInput.ErrorSafety`. [Native artifact 12261661100](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413855349/artifacts/12261661100) has SHA256 `efcd65f69bbfdbec6d66d1fa05e3441c3bf696945a4cb92ab7e1ef57abf2a064`. The getter now has compilation evidence. Its execution against the actual L07 map, the separate PCG365 target and optional plugin load remain unverified.

### Isolated consumer readback and remaining transfer contract

The existing [L07 readback workflow](../../../.github/workflows/yacs-lesson07-unreal-readonly.yml) now uses [Invoke-YacsLesson07Readback.ps1](../../../scripts/ue/Invoke-YacsLesson07Readback.ps1) to prepare a new physical copy of the pinned saved map and bounded known material dependencies. It first requires successful protected CI for the exact source SHA, then authenticates the existing ordinary CI cache's original Automation receipt, compile/proof fingerprints, engine/toolchain identity and module BuildIds. It preserves the actual compile/proof SHAs and never upgrades their meaning to a later reader SHA.

The new consumer runs only while the host is idle, using separate copies of the project and RoadForge modules. It preserves at least 30 GiB after the planned copies and verifies original and copied inputs after success, failure or timeout. The ordinary cache, canonical source packages and accepted Houdini cache are not deployment destinations. The known asset roots are an initial bounded inventory; native missing-package or missing-class diagnostics prevent a complete result.

The reader records actual actor transforms, per-component layout, assigned materials, hole material, Landscape layer queries and four diagnostic traces. Three layout fields are public in the [native LandscapeComponent API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Landscape/ULandscapeComponent) but are not published as Python editor properties. The small `ReadLesson07ComponentLayout` function in the existing [Landscape diagnostic library](../../../Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsLandscapeMeshDiagnosticLibrary.h) reads those native fields directly, on the game thread and only in the exact L07 world. It neither computes substitute terrain nor changes components. Missing native observations remain unknown.

The highest result for this stage is `STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING`. It does not establish full height samples, the true tile seams at `-0.25 m`, Visibility polarity, continuous collision, material rendering or a reopen after repair. Those still require native measurements against the accepted Houdini source and an isolated candidate update. No current result authorizes the destructive bake helper as an ordinary `PE_Load_Landscape` update.

**Audit follow-up at `9ddebf5a8a7387313a8751e1fb0c960785af4b2a`:**
[ordinary CI 39434128373](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39434128373)
passed, including 28/28 native Automation tests, zero failed/skipped/errors and
two warnings. Physical compile fingerprint `d590157323ba1dee7a999cba34718cd204df0ea8f53dacd6bba7836b4ab66ac7`
matched the retained build; the cache preserved actual compile head `e2aed213`
and recorded fresh proof head `9ddebf5a`.
[L07 readback 39434119045](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39434119045)
authenticated the canonical map and CI cache, then stopped before candidate
creation or Editor launch: `Measure-Object size_bytes` did not resolve the
ordered-dictionary keys under strict mode. Its receipt measured the original
map unchanged; it provides no structural or geometry result. The wrapper now
uses the supported calculated-property form of `Measure-Object` for the same
three size sums. A real PowerShell regression reproduces the old failure and
verifies asset/module/config accounting above 2 GiB, including empty config.
The 30 GiB reserve and identity protections are unchanged.

**Actual Editor attempt at `c98a89dc35b481c75a37ada06b92ae8194757975`:**
[ordinary CI 39436179335](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39436179335)
passed. [L07 attempt 39436127684](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39436127684)
then staged all 59 intended assets and verified module/config copies, totalling
2,453,803,817 bytes. The owned Editor (PID 8420) started, but crashed at engine
initialization with `Null assigned to TNotNull` (`NotNull.cpp:12`), before a
native L07 report was written. Its recorded exit code is `-1073741571`.
The isolated session also logged missing Stage3F/Stage3G constructor references
from the common project module; their relationship to the fatal error is not
established. These startup references do not establish that another world was
opened or generated.

The result remains `INCOMPLETE`, with structural and geometry acceptance false.
After the crash, the original map, copied map and every protected input were
verified unchanged. Host receipt SHA-256:
`7f2921b958b88d54d04c0fdb5cc5d073402782a20babda3d2cd2ccdafe7264db`.
[Diagnostic artifact 12273361465](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39436127684/artifacts/12273361465)
has archive SHA-256 `af3c187885ee03f923905f05ba172b3a52fe495a1f268d199059ae1a00c16a83`.
The exact remaining gap is Editor startup and native map execution, followed by
the geometry/visibility/collision gates already listed. Do not infer a repair
from ordinary Automation success or bypass native errors.

An additional independent byte audit at the same commit compared **all 59
canonical assets (2,451,237,244 bytes)** against their committed Git LFS objects:
zero differences. This closes local/remote asset identity for the complete
staged asset set; it does not close the failed native execution gate.

**First isolated readback attempt: blocked before map measurement.** [Run 39413841851, job 118603360623](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413841851/job/118603360623) used `e2aed213870a7151106049a7b56953eaba919d6f` after that protected CI succeeded. Its `host-receipt.json` reports `INCOMPLETE`: the first `Assert-L07Reserve` rejected insufficient free space for the unchanged 30 GiB reserve, before candidate creation, map hashing or Editor launch. `candidate_root`, `owned_editor_pid` and all source/candidate map measurements are null. There is no new unchanged-map hash measurement, structural result or collision proof. The [1038-byte artifact 12261980942](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413841851/artifacts/12261980942) contains only that receipt; archive SHA256 is `d428d16cd8304442111be7c2c6a5704c370a496ce412d28c1cd71b0ed42725c9`.

A later read-only host diagnostic measured **22.04 GiB free on D:** at `2026-10-20 11:59:27 UTC`: [run 39386777997, attempt 2, job 118614584666](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39386777997/job/118614584666), [716-byte artifact 12262321889](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39386777997/artifacts/12262321889), SHA256 `0d9e3d75ee9b83382f711ac4e5040e0552ac83090cad4120718ab2f1955d7819`. The diagnostic ran historical workflow code `113021b84f3316868ffad164cd88e5ef4c141ec8`; it did not build, check out or launch UE. Its canonical-project module BuildId `55116800` and present DLLs are inventory only, not admission of the ordinary CI cache. Preserve the accepted Houdini caches and the reserve while following the [bounded retention policy](../../ci/RUNNER_WORKSPACE_RETENTION.md).

Prepared integration corrections keep the raw-byte and fingerprint checks intact: the L07 workflow's private Git configuration explicitly sets `core.autocrlf=false` and `core.eol=lf`, and the [cache-input verifier](../../../scripts/ci/materialize_unreal_cache_inputs.py) raises only its complete fingerprint-input inventory limit from 512 to 1024 to cover the observed 670 inputs. Its 256 repair-target and 2 MiB per-file bounds remain unchanged. The LF checkout fixture is local evidence; the failed L07 run never reached its raw-byte guard. Fresh native runs of these corrections and the restricted inactive-cache cleanup remain `NOT_RUN`. Houdini remains the primary authoring executor; restoring this consumer must preserve the accepted L06 source and complete L06/L07 without replacing their terrain recipe.

The [bake preflight](../../../scripts/ue/bake_lesson07_landscape.py) also now reads the hole material from the producer's actual nested field, `tiles[].visibility.requested_hole_material`, and requires it to match the top-level request. Missing or malformed metadata is rejected before any map setup. This schema repair does not alter `Alpha`, hole polarity, source heights or saved assets; producer-shaped synthetic tests are not native material/geometry evidence.
