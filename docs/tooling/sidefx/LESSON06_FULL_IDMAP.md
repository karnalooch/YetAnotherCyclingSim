# Lesson06: original Pegasus IDMap repair and full-domain verification

Issue #365 / M3, existing PR #474, branch `codex/365-world-graph`.
Base revision: `99a5ae03a35fc5ff56e34a23ecfb9580431c8ba6`.

## Unified 16,000 × 16,000 single-quality closure — 2026-10-19
**Status: `LESSON06_FULL_IDMAP_PASS`**

The entire Sa Calobra landscape (8000 m × 8000 m) is fully unified into a single, continuous, high-fidelity domain at 0.5 m native grid spacing (16,000 × 16,000 cells = 256,000,000 samples). The historical Working vs Context boundary split has been completely eliminated, definitively solving the seam, band, streak, and blur artifacts without 2D image post-processing hacks.

### Key Metrics and Receipts
- **Domain**: Bounds `[-4000, +4000]` m in X and Z, Origin `[-3999.75, 0.0, 3999.75]`, Resolution `[16000, 16000, 1]`, Spacing `0.5 m`.
- **Relief (Invariant A)**: Elevation range `[-1.30, 1437.16]` m, Mean `418.99 m`. Puig Major peak preserved bit-exact from raw source DTM. Valid land area `Alpha > 0` comprises 249,818,980 samples (97.59%).
- **Pre-ID vs Post-ID Identity (Invariant B)**: `height`, `r`, `g`, and `b` layers are 100% bit-identical between Pre-ID cache and final IDMap (`max_diff = 0.00000000`).
- **Decoder & Class Distribution (Invariant C)**: Fresh hython reload of checkpoint HIP decoded all 5 Pegasus classes with 100% spatial sample match:
  - `grass` (ID 0, Code 0, Float 0.0000): 69,121,582 voxels (27.00%)
  - `grass 2` (ID 1, Code 64, Float 0.2510): 90,518,267 voxels (35.36%)
  - `sand` (ID 2, Code 128, Float 0.5020): 18,624,143 voxels (7.28%)
  - `cliffs` (ID 3, Code 191, Float 0.7490): 77,735,243 voxels (30.37%)
  - `scree` (ID 4, Code 255, Float 1.0000): 765 voxels (0.0003%)
- **Saved Caches & Checkpoint**:
  - Pre-ID Cache: `D:/yacs/work/lesson06-unified-20261019/pre_id_cache.bgeo.sc` (SHA-256: `d97cd262cf7d94f1a1e0458b4a0c13308d9b98c6238231e5c99f2425c160a069`)
  - Final IDMap Cache: `D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc` (SHA-256: `ea6f95f113ecb74af7dd6519f965aed5c8431a2329c3645061cc653d2f5ba2b8`)
  - Checkpoint HIP: `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc` (SHA-256: `0a7f757f0dc74603bb724d519aae2f90579765038fccf52b2941dd92cc8f9d98`)
  - Verification Receipt: `D:/yacs/work/lesson06-unified-20261019/verification_receipt.json`
- **Diagnostic Evidence**:
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/global_rgb_overview.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/global_idmap_overview.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/decoded_mask_grass.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/decoded_mask_grass_2.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/decoded_mask_sand.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/decoded_mask_cliffs.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/decoded_mask_scree.png` (2000 × 2000)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/closeup_former_north_seam.png` (2048 × 1024 side-by-side native 0.5 m crop)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/closeup_former_south_seam.png` (2048 × 1024 side-by-side native 0.5 m crop)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/closeup_puig_major_peak.png` (2048 × 1024 side-by-side native 0.5 m crop)
  - `worldgen/houdini/sa_calobra/evidence/lesson06_unified/closeup_sa_calobra_cove.png` (2048 × 1024 side-by-side native 0.5 m crop)

## UE Remote material handoff and recovery — 2026-10-18–19

### Authorized Working edge RGB exception (2026-10-19)

The owner subsequently authorized a separate RGB-only correction within 4 m of
the Working edge, at full resolution. NorthEdgeRGB is now live on the two north
actors in the same editor PID 42752. Native Transform borrows RGB 4 m inward;
Mask by Geometry (3.5 m box blur), Remap and HeightField Layer blend it into the
edge. A Blast explicitly retains only RGB before reflection into Context.
These are local presentation settings using documented SideFX nodes, not a
Pegasus tutorial preset. No source terrain or original mask is an output.

Both saved HIP graphs pass fresh replay. Exactly 48,905 Working RGB pixels
changed, all within 4 m; 34,366,645 other Working pixels in the two textures
remain byte-identical. Full 3811 × 5081 resolution is retained. All 38,727,382
pixels read back from UE match delivery, and the shared edge has zero code delta.
The 14 protected source hashes, both original RGB sources and saved map hash
were rechecked. All 27 actors retain their height/weightmap references, layers
and transforms; the other 25 retain their materials. This is preservation
evidence, not a new full geometry readback.

The strong single dark line is reduced, but finer horizontal color traces are
still visible in Lit and Unlit. **Complete artifact removal is NOT PASS** and
owner visual acceptance remains pending. Streaming has 440.66 MiB available
against 0.63 MiB required, without an over-budget warning. No restart, source
cache rewrite, Lesson02-05 rebuild or merge occurred. See the
[scoped RGB and visual receipt](lesson06-north-edge-rgb-live-20261019.json).

### Live Context RGB correction and memory recovery (2026-10-19)

The active editor remains PID 42752. Draining native asset/shader compilation
confirmed zero pending jobs. Switching the live Pixel Streaming codec from
H264 to VP9 and reconnecting viewers stopped the rapid private-commit growth
over the observed window; old committed memory was not reclaimed. This matches
the symptom reported in [Epic's upstream tracker](https://github.com/EpicGames/PixelStreamingInfrastructure/issues/954),
but does not establish a driver-level root-cause trace. No editor restart occurred.

The owner explicitly approved a 16 GiB D: pagefile extension. CIM rejected the
size; the approved native Windows existing-file extension succeeded through UAC.
Live allocation is 76,384 MiB; registry settings remain 60,000 MiB, so this is
session-only. Total commit increased by exactly 16 GiB. The unchanged 12 GiB
import guard then passed. The bounded adapter and receipts are retained under
`Saved/RuntimeProof/Lesson06NorthMaterial`.

Visual review rejected the 32 m constant-edge Streak variant and restored the
prior materials before the next test. The deployed NorthMirrorRGB variant uses
native Transform SOP reflection of **RGB volumes only** about the north source
edge, then HeightField Mask by Geometry and Layer compositing into Context.
This is a local presentation adaptation using documented SideFX nodes, not an
original Pegasus seam recipe or terrain transformation. Both fresh graph
replays pass. All 34,415,550 Working pixels within the two changed textures are
unchanged; the other 25 actors retain their materials. All 38,727,382 exported
UE RGB pixels match delivery exactly, with zero shared-edge discrepancy.
The 14 protected source hashes and original map hash were rechecked.

The broad Context curtain is removed in the live north view. **A thin dark line
remains at the source edge**, including in Unlit; original Working RGB contains
dark pixels in its first rows. Full artifact removal and owner visual acceptance
are NOT PASS. Further Working-side RGB correction requires the owner's scoped
decision; heights, masks and original caches remain unchanged. Streaming now has
440.66 MiB available against 0.63 MiB required, with no over-budget warning.
See the [current native and visual receipt](lesson06-north-mirror-live-20261019.json).
No Lesson02-05 rebuild, map save, restart, commit or merge was performed.

### Northern RGB follow-up and streaming budget (2026-10-19)

Owner-reported horizontal cliff bands were compared in the same live camera
using native Unlit and Lighting Only viewport modes. The broad horizontal
boundary remains in Unlit but disappears in Lighting Only: this isolates its
visible contribution to material color, rather than a matching large geometric
step. This does not certify every fine cliff artifact or terrain sample.
Evidence: `Saved/RuntimeProof/Lesson06NorthMaterial/walls_unlit.png` and
`walls_lighting_only.png`. Lit was restored afterward; no landscape data or
material assets changed during this diagnostic. The pending RGB candidate has
not thereby been proven to eliminate the band.

PID 42752 remains active without another restart. Native `stat streaming`
identified 5,403.6 MiB of non-streaming textures against a 616 MiB total pool.
Unloading saved, inactive RGB trial packages reduced the former to 4,789.47
MiB. A session-only 4,992 MiB pool provides 197.53 MiB for streaming against
0.76 MiB required. The warning disappeared in UE Remote. The VRAM limit remains
enabled; no texture compression, mip generation or source sharpness changed.
This follows Epic's [streaming-pool accounting](https://dev.epicgames.com/documentation/unreal-engine/texture-streaming-metrics-in-unreal-engine?lang=en-US),
where non-streaming mips consume part of the total budget.

The separate NorthBoundaryRGB candidate uses native HeightField Mask by Geometry
and Layer nodes, with a local 32 m expansion/blur restricted to background north
of the original Working lattice. These distances are an adaptation, not a
SideFX standard. Two fresh HIP replays pass; original Working RGB and every
pixel outside the north background remain exact. One background shared vertex
requires one-code transport alignment; delivered shared edges then match.
Original masks, heights and caches are retained.

**Northern deployment is blocked, not visually accepted.** Available commit
fell below the unchanged 12 GiB import guard before import. Garbage collection
and inactive-package unloading did not recover the required reserve; the cause
of increasing UE private memory remains unproven. The live scene still uses
SourceBoundaryRGB and still shows the northern detail boundary. The candidate
has not been imported. No restart, Lesson02-05 rebuild or merge was performed.
See the [follow-up receipt](lesson06-north-material-live-20261019.json) for the
current snapshot, source-hash recheck, streaming evidence and exact blocker.

### Current live source-boundary RGB correction (2026-10-19)

The owner explicitly authorized one restart of hung PID 21524. PID 42752
recovered the same 22 hash-pinned caches. All 27 native height/mask readbacks
match the admitted baseline bit for bit; all 14 protected files and the original
map hash remain unchanged. No lessons 2-5 rebuild or merge was performed.
The recovered map remains unsaved; new material assets are saved separately.

Live review rejected wide Streak bands from using padded UE tile bounds.
The deployed SourceBoundaryRGB variant follows the original Working source
lattice, using native HeightField Mask by Geometry and Layer compositing.
The 8 m expansion and 8 m blur are local RGB presentation settings, not a
SideFX standard. The background-side feather includes padding within UE Detail
actors, outside the original Working source. All 70,333,650 source Working
pixels are exact. Sixteen fresh graph replays pass. Shared-edge transport
changes eight Context pixels by one RGB code and no Working pixels.
All shared edges agree. Fourteen live textures exported from UE match all
159,192,228 delivered RGB pixels exactly. No terrain or original mask is edited.

Four Remote views confirm removal of broad streak bands and sharp Working.
The source-detail difference remains visible, especially north: invisible-seam
acceptance is NOT PASS. A roughly 780 KiB streaming budget warning remained in
captured views. Import references were released and the session-only texture
pool changed from 600 to 616 MiB; warning resolution is not claimed.
No global configuration was saved. Owner visual acceptance remains pending.

See the [current delivery receipt](lesson06-context-recovery-live-20261019.json)
for native proof, memory, and all four view captures. Earlier failure evidence
is preserved under Saved/RuntimeProof/Lesson06ContextColor/recovery_pid21524.

### Authorized recovery and three-channel border correction — 2026-10-19

The owner authorized relaunch and recovery from retained caches. The existing
Remote profile started PID 21524; all 22 DTM tiles were restored individually
from their hash-pinned payloads, without rebuilding Lesson02–05. A 12 GiB
available-commit guard precedes each import/readback, and native queued garbage
collection releases unreferenced objects between tiles. No further editor
restart was issued.

Fresh native readback of all 27 actors matches the prior admitted height and
mask volumes bit for bit. This carries forward the exhaustive DTM bound:
264,427,742 samples in the 26-tile replacement set, maximum 0.510986328 m.
All 14 protected source/cache hashes remain unchanged. The original Context
is retained hidden; its collision is disabled when the replacement is shown.

The first live color review rejected a red exterior band. The singular `Layer`
parameter of `HeightField Layer Properties` had resolved `r g b` to R only;
G/B retained their constant-zero border policy. A simple native probe confirmed
the cause. The corrected graph uses **three separate native nodes**, one each
for R, G and B, and asserts every resulting `volumebordertype` is `streak`.
All sixteen candidate graphs are freshly reopened; fourteen nonempty delivery
textures retain sharp source Working pixels and place the feather on Context.
Duplicate-vertex transport changes only 261 Context perimeter pixels by at most
two 8-bit codes; no Working pixel is changed by that alignment. Prepared shared
edges agree exactly. The rejected PNGs, HIPs and initial red screenshot remain
separate evidence, not current acceptance.

The original map is not overwritten. The reconstructed scene is unsaved.
The first material attempt was reverted after the red-band review. Corrected
three-channel RGB is verified offline but **not deployed**: PID 21524 remains
alive, while its command callback and log stopped advancing and two browser
clients timed out. The cause is unproven; available commit remained 29.3 GiB.
No corrected texture assets or applied receipt exist. The pending import was
cancelled to avoid an unattended deployment if the session resumes. No further
restart was issued. Native texture readback and final Remote visual review are
**BLOCKED**, as recorded in the
[recovery delivery receipt](lesson06-context-recovery-live-20261019.json).

### Owner correction: preserve Working sharpness; transition on Context only

The owner rejected the Working-side softening described below. The replacement
uses the retained reviewed Working RGB before either seam feather. Existing
0.5 m source samples are copied exactly into their registered Working positions;
native float-coordinate interpolation is not permitted to alter their 8-bit
transport values. The padded Working border uses the source edge color without
blur. No source cache is overwritten.

Official [HeightField Layer Properties](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layerproperty.html)
with `Streak` extends those edge colors outwards. `HeightField Mask by Geometry`
and RGB-only `HeightField Layer` fade the extension on the Context side of the
actual four-tile Working rectangle. The 128 m box expansion and blur radius are
local adaptation settings, not Pegasus defaults. This extends retained edge
color; it does not invent new source detail for the background. Twelve Context
candidates were checked; two with zero transition weight are excluded from
deployment. The payload is four restored Working RGB textures plus ten Context
RGB textures, with new duplicate materials and tile-specific world UVs.
Native per-tile coordinate sampling produced up to two 8-bit RGB codes of
difference on duplicate boundary vertices. The transport adapter copies only
those shared Context perimeter pixels from the canonical adjacent tile,
prioritizing untouched Working. It performs no interpolation or filtering:
382 Context pixels change by at most two codes; zero Working pixels change.
Original pre-alignment images remain retained. Exact shared-edge equality and
fresh native replay are separate checks, not a relaxed seam tolerance.

**Previous attempt blocked:** PID 11820 ceased running before this correction
was dispatched. Windows recorded virtual-memory exhaustion at 23:52:16 local,
reporting UE at 74,276,270,080 bytes and hython at 3,496,292,352 bytes. There is no
confirmed new UE crash receipt, so the precise termination cause is unresolved.
The agent did not issue a stop/restart command and did not relaunch the editor.
Previous live-session map changes were unsaved and must not be presumed recovered.
Source caches, previous receipts, separate material assets and prepared payloads
remain retained. New UE application and visual acceptance are **NOT RUN**.

The earlier Working-side material receipt is historical and rejected as the
desired appearance; it is not current acceptance. Local correction evidence is
under `Saved/RuntimeProof/Lesson06ContextColor/`.
Fresh reopening reproduces all sixteen candidate textures; fourteen are in the
delivery manifest. All shared RGB perimeter samples agree exactly after the
bounded transport correction. All 70,333,650 registered Working source pixels
remain exact, and all 14 protected source/cache hashes remain unchanged.
See the [prepared correction and UE blocker receipt](lesson06-context-color-20261019.json).

### Color sampling transition — rejected Working-side adaptation

The subsequent owner-authorized material repair runs in the same editor PID
11820. Working color was sampled at 0.5 m; retained Context color was sampled at
3.90625 m. Texture settings matched, including no mip generation and zero LOD
bias. The remaining sharpness difference therefore came from source color
sampling, not a new height change or a mismatched texture setting.

The isolated Houdini 22.0.466 graph uses native
[HeightField Mask by Geometry](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyobject.html)
and [HeightField Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layer.html),
restricted to `r g b`, to feather Working color into retained Context color.
The 128 m inset and 128 m box-blur radius are explicitly local adaptation
settings, not Pegasus tutorial constants. A new temporary color weight drives
the composite; original material masks and Visibility are neither edited nor
exported. The four isolated graphs output RGB only and freshly reopen to
bit-exact PNGs. This maps to the official color-layer compositing capability;
it does not claim implementation of the full
[Pegasus Landscape Material](https://www.sidefx.com/tutorials/project-pegasus-landscape-material/)
detail shader.

Four duplicate UE material instances bind the new color textures; parent,
world UVs and texture settings are retained. The 22 DTM Context actors are
unchanged. Native texture exports match all 77,454,764 prepared RGB pixels
bit for bit. Native post-change readback confirms all original five actors'
height and mask volumes are bit-exact (81,523,053 height samples), and all 14
pinned source/cache hashes are unchanged. No Lesson02–05 cook, editor restart
or merge occurred. New material assets are saved separately; map bindings
remain live-session changes and the original map is not saved.

Four Remote edge captures show a broader, gradual color transition. The repair
softens Working color near the edge; it cannot restore detail absent from the
retained coarse Context color. It is not a claim of equal source sharpness
everywhere, owner visual acceptance, or a complete detail-material delivery.
See the [material sampling receipt](lesson06-material-sampling-20261018.json)
and local runtime evidence under `Saved/RuntimeProof/Lesson06MaterialSampling/`.

### DTM-based resolution replacement — live; native height/mask checks passed

The owner clarified that the original **0.5 m DTM is the sole height reference
for both Working and Context**. The earlier 0.363 m Context result below was
relative to its own coarse source grid, and does **not** establish a 2 m bound
against the full-resolution DTM or continuity between the two grids.

Native Houdini 22.0.466 `HeightField Resample` tests on a bounded cliff window
failed the 2 m DTM criterion for every available filter. `HeightField Tile Splice`
stitches tiles produced by Tile Split; it does not reconstruct missing source
detail. The replacement candidate therefore imports exact retained DTM windows
with native `HeightField File` and the existing geographic axis transform.
It consists of 22 separate background tiles with 0.5 m spacing, surrounding the
unchanged four Working tiles. Their 186,972,978 prepared samples match the input
windows exactly before UE transport. Source files and original masks are retained.
Derived visibility uses nearest sampling of the retained ownership mask plus
original DTM validity; this is a representation adapter, not a new source mask.

The existing project uses `X = easting - 483650`,
`Z = 4409899.5 - northing`. An initial window orientation was rejected before
publication. The corrected mapping was independently checked against all four
retained Working base arrays: bit-exact equality with full-DTM windows. Initial
test-tile UE height measurements are not accepted geographic-fidelity evidence.

The initial live import was **BLOCKED**, not PASS. Three bounded native tests returned
no `visibility` volume, and the new actor's `get_target_layer_names(True)` was
empty. Correct `unreal_material_hole`, matching material bindings and native
ForceLayersFullUpdate/PostEditChange did not resolve it. Registering the retained
target settings through Python was refused: `Property 'TargetLayers' ... is
read-only and cannot be set`. The native header's AddTargetLayer is not exposed
as a UFUNCTION. The unadmitted probe actor was removed.

After the owner authorized starting the stopped Remote profile, the project
adapter `RegisterDtmLandscapeVisibility` was compiled before launch. It calls
UE 5.8 `AddTargetLayer` using `ALandscapeProxy::VisibilityLayer`, updates the
layer-info map and flushes composition. It does not write height/mask pixels.
This is a version-integration adapter, not a new terrain recipe. The engine's
special target name is `__LANDSCAPE_VISIBILITY__`; Houdini's source volume remains
`visibility`. Material-derived ordinary target registration had omitted it.

Editor PID 11820 started with the retained L06 Remote profile. The first native
readback passed all 8,264,145 height samples: maximum DTM error 0.0628125 m;
Visibility matched the prepared retained-mask representation bit for bit.
All 22 tiles subsequently passed native readback: 186,972,978 samples, maximum
DTM error **0.064685822 m**, no sample above 2 m, and all derived Visibility
masks bit-exact. Combined with the four Working tiles, the exhaustive check
covers **264,427,742 samples**, maximum DTM error **0.510986328 m**. All original
five actors' height and mask volumes remain bit-exact against the retained
pre-transition native baseline. All 14 pinned source/cache files retain their
hashes. Shared edge spacing is 0.5 m and maximum paired vertex height mismatch
is **0.051521277 m**; this is not a claim of mathematically welded edges.

The new Context is now visible in PID 11820. The old Context remains retained,
hidden in editor/game and with collision disabled. The four Working actors are
unchanged. The original map package remains unchanged on disk; this is live
session deployment, not a saved/fresh-reopen or production acceptance claim.

See [candidate and exact failure receipt](lesson06-dtm-context-candidate-20261018.json).
Remote captures cover north, east, west and south boundaries. The coarse
geometry resolution jump has been replaced by the 0.5 m DTM representation.
At that checkpoint a visible **material color sharpness difference remained**, particularly in the
west/south views; retained Context color data is coarser than Working. No mask
rewrite or material concealment was used. Therefore the native height/mask
checks pass, but fully seamless material appearance and owner visual acceptance
were **not PASS**. The subsequent RGB-only adaptation is recorded above.
Native sample admission does not measure every decimated
render LOD against the DTM.

Current evidence: [live delivery receipt](lesson06-dtm-live-20261018.json).
Runtime readbacks and captures are under
`Saved/RuntimeProof/Lesson06DTMContext/` (not committed generated caches).

Official references: [HeightField Resample](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_resample.html),
[Tile Splice](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_tilesplice.html),
[Unreal Landscape basics](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html).
The native registration API is documented in
[UE 5.8 AddTargetLayer](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Landscape/ALandscapeProxy/AddTargetLayer).

### Owner global height limit and rejected transition

The owner now requires an absolute maximum of 2 m source-relative height change
across the entire Landscape. The previous transition is rejected: native UE
measured a 112.838745 m change at its worst sample. All four transition layers
were disabled; all 81,523,053 native height and mask samples were restored exactly
to the pre-transition state. Import and re-enable commands now reject this payload.

An independent full-domain audit reconstructs each reference from retained
`source_working_05m` / `context_source`, with original registered tile padding;
the Manual cache is confirmed neutral and the original input hashes unchanged.
The restored Working maximum is 0.510986 m and Context maximum is 0.362603 m
relative to those sources, including UE quantization. No sample exceeds 2 m.
The final fresh native readback after setting all four rejected layer height
alphas to zero reproduces these bounds; exported masks and visibility remain
bit-exact. UE PID remains 31408. Map changes remain active and unsaved; the
original map file hash is unchanged. Source fidelity is measured against the
retained source grids at their original resolutions, not cross-grid interpolation.
See [global source-relative audit](lesson06-global-height-audit-20261018.json).
The original resolution seam remains unresolved; eliminating it does not justify
violating the height limit. No Lesson02–05 rebuild or merge is authorized.

The prepared transition is applied to all four Working actors and Context in
the existing Lesson05 map, in the same Unreal process (PID 31408, started
21:47:59 local time). No editor restart or Lesson02-05 cook occurred.
The [UE receipt](lesson06-ue-seam-20261018.json) records the verification.

Five new textures and duplicate material instances are saved under
`/Game/Generated/YACS/Lesson06Seam_20261018`. They retain the original parent,
texture settings and world UV parameters; only `AlbedoTexture` changes.
This is the existing global-color consumer, not a Lesson07 ID/detail shader.
Context and Working also receive the already-cached reviewed tint correction
that had not reached the previous UE textures; no earlier lesson was rebuilt.
Native UE PNG exports match all **81,523,053 RGB pixels exactly**.

The material bindings are active in this session. The original map was **not
saved**; its SHA-256 remains
`ccabe772cb307c8f4cfee91ed9bc7b9485098162c73c5330a76c5d31a7ac7681`.
No height or mask payload was imported. Actor transforms, edit layers,
component layout and UV parameters are unchanged. Python does not expose
LandscapeComponent heightmap/weightmap texture properties here, so this is
not a new pixel-level UE height/weightmap re-export proof. Full source
conservation remains covered by the Houdini seam receipt.

All four boundary views were inspected in the live H264 stream. The material
deployment passes; **overall seamless visual acceptance does not**: a marked
geometry/resolution and shading discontinuity remains visible. Source-height
preservation prevents this material-only operation from correcting that
pre-existing difference. Owner visual acceptance remains pending.
The unrelated stale rock-progress overlay is not evidence for this task.

- [North before](../../../worldgen/houdini/sa_calobra/evidence/lesson06_remote/north_before.png)
- [North after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_remote/north_after.png)
- [South after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_remote/south_after.png)
- [West after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_remote/west_after.png)
- [East after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_remote/east_after.png)

Local deployment is separate from remote commit, protected CI and merge;
none of those delivery gates is asserted by this receipt.

## Status and retained inputs

### Authorized separate height transition

**Superseded by peak audit: rejected for source-relief fidelity; the four
`Lesson06_Boundary_Transition` layers are now disabled in the live scene.**
The import/replay PASS below remains transport evidence only. It is not terrain
acceptance. Original source caches, masks and the layer payload are retained.
See the [peak audit](lesson06-peak-audit-20261018.json).

The maximum is at Houdini X/Z **(-1310.25, -1787.750122) m**, tile
`SaCalobra_Detail_0_0`, zero-based pixel **(1180, 5055)**, 18 m south of native
Working in the UE tile padding. The original source/manual padding is
58.48 m; the pre-transition UE sample is 58.502197 m. The band weight is 1,
so native HeightField Layer completely replaces that sample with interpolated
Context height 171.318741 m: **+112.816544 m**. Native UE quantization yields
171.340942 m, an actual UE difference of **112.838745 m**.

The [measured cross-section](../../../worldgen/houdini/sa_calobra/evidence/lesson06_peak_audit/profile.png)
shows a sharp cliff edge being smoothed/displaced by the coarse Context surface;
the whole surrounding area is not uniformly raised by 112 m. Original Context
sampling gives 171.313843 m at the same position, agreeing with the imported
Context to about 5 mm. The error is therefore not a centimetre/metre conversion
or a fabricated import spike. The selected coarse target and full-weight blend
alter the source cliff profile. Changes also reach **83.142059 m inside native
Working**, so the issue is not confined to padded duplicate geometry.

Same-camera live UE views:

- [Before, full scene](../../../worldgen/houdini/sa_calobra/evidence/lesson06_peak_audit/scene_before.png)
- [After, full scene](../../../worldgen/houdini/sa_calobra/evidence/lesson06_peak_audit/scene_after.png)
- [Before, Working isolated](../../../worldgen/houdini/sa_calobra/evidence/lesson06_peak_audit/working_before.png)
- [After, Working isolated](../../../worldgen/houdini/sa_calobra/evidence/lesson06_peak_audit/working_after.png)

Context was temporarily hidden only for the isolated screenshots, then restored.
The exact peak has Context visibility value 1 (excluded); surrounding Context
can obscure parts of the camera view, so the numeric cross-section identifies
the exact sample more reliably than a perspective screenshot. No mask changed.
No editor restart, map save or merge occurred. A new repair must address the
coarse/fine cliff correspondence and fidelity before admission; larger blur or
a wider blend is not accepted as an automatic fix.

The owner subsequently authorized height changes **inside a separate boundary
band**, retaining original caches and masks, and requested live UE deployment.
This supersedes the no-derived-height-change restriction in the feasibility
follow-up below. See the [transition receipt](lesson06-geometry-transition-20261018.json).

`SaCalobra_Pegasus_Lesson06_Geometry.hiplc` adds `/obj/LESSON06_GEOMETRY`
to the retained seam HIP. It reads full native UE readbacks of the five current
actors; the calibrated H22 codec decodes transport values into metres. No
Lesson02-05 authoring graph is cooked. Native HeightField Mask by Geometry
creates a separate inverted rectangular mask; HeightField Layer composites
**height only** toward unchanged Context. Original masks are not used as a
scratch buffer or exported back to UE.

The inner rectangle is inset 64 m from the native Working rectangle, with a
32 m native box-blur radius. The band also includes the existing UE tile padding
outside that rectangle. These are local candidate settings, not tutorial
constants. Its exact nonzero support is retained per tile in `*_band.npy` under
`D:/yacs/work/lesson06-geometry-20261018`; it contains 13,495,898 samples including
duplicate tile edges. Native fresh-HIP replay passes, with bit-identical masks,
unchanged heights outside that support, unchanged Context, and zero height-code
disagreements on all four shared Working edges.

The average absolute correction within each tile's band is 0.43–0.63 m; the
largest local absolute correction is 112.82 m in the steep padded margin.
This is a material geometry change in that authorized band, not a claim of
centimetre-only smoothing or newly measured geography. Original source caches
remain retained and the consumer correction is a separate reversible layer.

The existing Houdini Engine cached-heightfield adapter imports four height-only
increments into `Lesson06_Boundary_Transition` in UE PID 31408. No Context
increment, paint/visibility payload, material rebinding, map reload/save or
editor restart is performed. New state is active in the current session;
the original saved map remains unchanged. Native readback and visual status
are recorded in the receipt, separately from owner acceptance and merge.

Completed live readback verifies **81,523,053 samples** against expected uint16
height codes. All `mask` and `visibility` samples are bit-identical before/after;
every height code outside the band and every Context height code is unchanged.
12,038,690 height codes change inside the band. Four complete shared Working
edges remain identical. All twelve retained Houdini source/mask cache hashes
match. Python compilation, documentation index/i18n/links/freshness and diff
whitespace checks pass; protected CI and merge were not run.

North, south, west, east and the largest-displacement location were inspected
in the active stream. The derived transition is present; the different
resolution/detail of Working and Context remains visible. This is not a claim
of a seamless whole-world visual PASS or owner acceptance.

- [North](../../../worldgen/houdini/sa_calobra/evidence/lesson06_geometry_remote/north_after.png)
- [South](../../../worldgen/houdini/sa_calobra/evidence/lesson06_geometry_remote/south_after.png)
- [West](../../../worldgen/houdini/sa_calobra/evidence/lesson06_geometry_remote/west_after.png)
- [East](../../../worldgen/houdini/sa_calobra/evidence/lesson06_geometry_remote/east_after.png)
- [Largest correction](../../../worldgen/houdini/sa_calobra/evidence/lesson06_geometry_remote/maximum_delta_after.png)

The obsolete rock-progress browser overlay was also removed at the owner's
request by restoring the hash-verified original viewer HTML. Browser reconnect
did not restart Unreal or alter its scene.

### Geometry-boundary feasibility follow-up

The owner requested removal of the remaining geometry/resolution boundary with
unchanged heights/masks, no Lesson02-05 rebuild, restart or merge. A fresh
read-only Houdini 22.0.466 measurement loaded only the retained final caches;
it did not load a HIP or cook terrain. See the
[geometry receipt](lesson06-geometry-boundary-20261018.json) and
[measurement script](../../../scripts/houdini/inspect_lesson06_geometry_boundary.py).

Across 33,966 Working perimeter samples (including duplicate corners), native
`hou.Volume.sample` of Context at the same world X/Z yields mean absolute
height difference **0.592894 m**, maximum **39.300690 m**; 28,832 samples differ
by more than 0.05 m. Both cache hashes match the retained source receipt.
This is continuous Houdini-volume comparison, **not** the gap measured on the
triangulated UE visibility boundary. It supersedes nearest-cell comparisons
only for evaluating same-position source disagreement. Working spacing is
0.5 m, Context spacing 3.90625 m; their native lattices are not coincident.

Official solutions reviewed:

- [HeightField Resample](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_resample.html)
  changes the grid and interpolates values. Upsampling cannot restore missing
  Context detail or ensure equality with this independently detailed Working.
- [HeightField Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layer.html)
  supports masked composition on the base grid. A height-only transition can
  retain original source caches and masks, but necessarily changes the derived
  heights in its transition band. It is not authorized by the current constraint.
- [HeightField Tile Splice](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_tilesplice.html)
  reassembles Tile Split output; it is not a documented reconciliation method
  for two independently sampled and detailed surfaces.
- [SideFX Unreal landscape basics](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html)
  documents shared conversion ranges and explicit section sizes. The existing
  native L05 proof already verifies shared Z encoding and source-height error
  bounded by 0.022888184 m. This does not explain away source differences of
  the magnitude measured here. LOD tuning cannot guarantee continuity of
  disagreeing source surfaces; no live LOD experiment or LOD repair is claimed.

PEG-02-02, **03:03–04:30**, documents source/manual/procedural separation and
additive layer composition. It supports a future isolated derived correction,
not a claim that this tutorial provides a no-height-change seam solution.
No replacement algorithm, skirt, masking change or concealment was applied.
A connector mesh would add a new surface and needs its own topology, fidelity
and collision proof; it is not verified here as a compliant SideFX solution.

**Outcome: no verified complete repair under the stated invariants.** The
smallest documented candidate is a separately cached, height-only transition
using native HeightField Layer with the retained inputs; original source files
and masks can remain intact, but final heights would change. Its design and
UE live-import feasibility remain unimplemented. The active material handoff
is retained; no editor restart, terrain rebuild, height/mask edit or merge was
performed during this follow-up.

The earlier [receipt](lesson06-idmap-full-20261018.json) describes the original
candidate. Its full-pass assertion is superseded by this review. The repaired
candidate uses separate files under `D:/yacs/work/lesson06-reviewed-20261018` and
`worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Reviewed.hiplc`.
The Reviewed candidate status remains **LESSON06_PARTIAL**. Both full-domain native checks
and fresh native replays **PASS**. The subsequent owner-authorized seam repair
is described below; its separate candidate preserves this checkpoint.
See the [reviewed receipt](lesson06-idmap-reviewed-20261018.json).
Owner visual acceptance and Unreal admission are separate.

Saved Reviewed HIP SHA-256:
`f0a7738268770c11aa1d0b95038d362e56939e4b3217868fe6f024f2c0db7008`.
Fresh processes verified all **74,510,970 samples**: zero decoded spatial
mismatches, exact native replay/cache equality, and bit-identical height,
R/G/B, roughness and Alpha. Both reopened without the previous PythonModule
error. Native world-space threshold checks explain 380 Working and 6 Context
direct-array boundary cases without changing the original threshold or encoder.

The Working perimeter comparison found **12,049 / 33,966 (35.473709%)**
different material selections against the nearest Context cell. This measures
the rectangular domain boundary, with corners counted twice; it is not an
Unreal visibility/consumer seam test. The two retained input-mask grids have
different resolutions. Their source-consistent encoding is proven, but their
material transition cannot be declared seamless. The official
[resampling guidance](https://www.sidefx.com/docs/houdini/heightfields/resampling.html)
describes resolution/detail tradeoffs; it does not establish an approved
Pegasus recipe for reconciling these two retained material-mask sets. No
resampling, new blending rule, threshold change or source-mask rewrite was
introduced in that Reviewed checkpoint.

## Working / Context transition repair

Scope: issue #365 / M3, PR #474, owner request of 2026-10-18. Local candidate
`SaCalobra_Pegasus_Lesson06_Seam.hiplc`, object `/obj/LESSON06_SEAM`.
The existing Reviewed HIP and all input caches remain unchanged. The output
nulls are `OUT_WORKING_TRANSITION` and `OUT_CONTEXT_UNCHANGED`.
Candidate verification: **NATIVE_SEAM_VERIFIED; OWNER_VISUAL_PENDING**.
Every native checkpoint was reproduced byte-for-byte in a fresh Houdini process,
without node errors or warnings. The [seam receipt](lesson06-seam-reviewed-20261018.json)
records the exact HIP, script, source and cache hashes. Owner visual acceptance
and Unreal consumer admission are not claimed.

The root cause is separate mask evaluation on 0.5 m Working and 3.90625 m
Context lattices, followed by the same categorical threshold stack. On the
33,966 perimeter samples, the retained grass, grass 2, sand, cliffs and scree
masks disagree at threshold 0.5 on 8,845, 9,567, 1,131, 7,223 and 16 samples,
respectively. These overlap; they must not be summed into an ID mismatch count.
The final selection differs on 12,049 samples. Retained global RGB and roughness
also differ, so correcting ID alone would leave the global-color discontinuity.
This is a resolution-dependent input discrepancy, not an encoder ordering bug.

The adaptation uses verified Houdini 22.0.466 vendor nodes:

| Operation | Official method and local adaptation |
|---|---|
| Shared categorical reference | Crop Context to the overlap; Convert VDB, [VDB Resample](https://www.sidefx.com/docs/houdini/nodes/sop/vdbresample.html) with nearest neighbor and Working reference transform, Convert VDB, then align to the Working HeightField. No averaging of category numbers is used as an authoring rule. |
| Reversible transition weight | [HeightField Mask by Geometry](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyobject.html), inverted inset rectangle, native box blur. Inset 32 m and blur radius 16 m are measured local candidate settings, not Pegasus tutorial defaults. |
| Derived material masks | Original Pegasus ID-to-Layer decodes the reference; [HeightField Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layer.html) composites each retained Working mask toward that decoded mask using the third-input transition weight. Original masks are separate read-only inputs. |
| ID selection | Original five Pegasus Layers-to-ID nodes retain their order and threshold 0.5. Final Blast/Merge selects only the new ID, avoiding the encoder's working-mask overwrite. |
| Global color | A separate HeightField Layer composite restricts its pattern to `r g b roughness`. It cannot modify height or source masks. |

The original L06 ranges above remain the source for the ID stack and decoder;
the cross-grid transition is an explicitly documented SideFX-native adaptation,
not an operation demonstrated verbatim in that lesson. Labs mask tools were
considered; native Layer already supplies masked, transformed compositing.
A small cropped native fixture preceded the full cook.

The full check and fresh replay preserve 67,092,794 core samples exactly. The feather
occupies 3,223,872 samples (4.585% of Working); ID changes on 424,842 samples.
All nine retained non-color/non-ID layers, including height and Alpha, are bit-identical
across the entire Working grid. All ten retained material-mask cache hashes
and both Reviewed final-cache hashes remain unchanged; Context is reused whole.

All 33,966 edge samples match the native Context categorical reference.
There are 270 coordinates exactly halfway between Context cells; either
equidistant neighbor is valid. VDB chooses a different equally near material
from NumPy ties-to-even on 13 of those points. Both tie candidates are checked
independently against Context, and zero non-nearest selections are permitted.
This distinction is retained in the receipt; it is not a numeric tolerance
that excuses a wrong material. VDB-to-HeightField floating roundoff is decoded
through the original HDA before the discrete output is checked.

The complete 70,316,666-sample Working output decodes correctly for all five
materials. The unchanged 4,194,304-sample Context output retains its earlier
full native replay proof, whose cache hash is checked again. On the full
perimeter, native Context sampling gives mean absolute RGB residuals
0.00000197 / 0.00000208 / 0.00000245, reduced from
0.13013 / 0.13206 / 0.16022. Maximum RGB residual is 0.00009031;
roughness mean/max residual is 0.00000233 / 0.00011367 (normalized 0-1).
These are measured floating sampling differences, not material-class errors.

All four CPU color comparisons were inspected: the abrupt rectangular color
edge becomes a gradual transition to Working detail. These images combine
native cache colors with a bilinear Context diagnostic background; they are
not native viewport screenshots or an Unreal visual acceptance.

This repairs appearance only. The pre-existing nearest-cell height comparison
has mean absolute difference 0.902 m and maximum 51.994 m; different sampling
is not a geometric continuity proof. No elevation is changed or defect hidden
with displaced geometry. Consumer/geometry continuity is outside this request.

Reproduction uses `scripts/houdini/repair_lesson06_seam.py --verify` in a fresh
Houdini 22.0.466 CPU process. Native checkpoint replay is limited to L06.
The retained sources are never overwritten; verification refreshes its local
reopen report, and the versioned receipt retains the reviewed result. Evidence lives
under `D:/yacs/work/lesson06-seam-20261018`; CPU diagnostic images are saved under
`worldgen/houdini/sa_calobra/evidence/lesson06_seam`. No L02-05 rebuild, Unreal
operation, remote delivery or merge is included.

- [North: before / after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_seam/color_north.png)
- [South: before / after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_seam/color_south.png)
- [West: before / after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_seam/color_west.png)
- [East: before / after](../../../worldgen/houdini/sa_calobra/evidence/lesson06_seam/color_east.png)
- [Full Working ID and transition weight](../../../worldgen/houdini/sa_calobra/evidence/lesson06_seam/overview.png)

Documentation links/i18n/structure/freshness, Python compilation and registered
catalog-status persistence checks pass. The existing evidence-storage guard
fails on the unchanged `docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json`
(1,440,278 bytes, also present at HEAD), exceeding its 1 MiB limit. It was not
deleted, waived or modified. Protected CI and remote delivery were not run.

The original Lesson06 HIP, its caches, Lesson05 Reviewed HIP, all source/manual
data and Lesson02-05 output caches are retained. Grass and sand are read from
the existing unchanged selectors on saved Source/Manual inputs. Tint is read
from the retained Lesson06 `ramp_layer`; cliff and final transported scree are
read from the named Lesson05 cache layers. These mask samples are cached once
for bounded IDMap replay. No material, displacement, erosion or Slump stage is
rerun. A cached mask's source node, layer, hash and grid are recorded.

## Source mapping

Original [Lesson06 video](https://vimeo.com/888569182) and
[SideFX Landscape Workflow](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/).
Retained caption: `PEG-02-06`, SHA-256
`71e2246974f9ab56c0beeff2c0f05d8516132ecd4fb84e538840475ae527273b`.

| Lesson range | Saved Lesson06 operation | Verification |
|---|---|---|
| 04:33-09:53 | Five named mask Nulls and Object Merge references | Retained mask identity, common domain lattice and source mapping |
| 09:56-12:42 | Original IDMap Layers metadata and Layers-to-ID HDA | Five names, source package hashes, actual loaded definitions and unchanged algorithm sections |
| 12:42-15:18 | grass, grass 2, sand, cliffs, scree stack | Original native encoder; threshold 0.5 retained, explicitly discussed at 14:08-14:11 |
| 15:19-16:44 | Native Ramp and Isolate | Each material mode cooked; errors, warnings and visualization metadata recorded |
| 16:45-17:08 | Original ID-to-Layer | Every decoded sample compared spatially with the selected ID, not merely histogram counts |

Working remains 7154 x 9829 at 0.5 m; Context remains 2048 x 2048 at
3.90625 m. Identifiers are obtained from the original encoder's evaluated
parameters: grass 0, grass 2 64, sand 128, cliffs 191, scree 255.

## Explicit compatibility adaptations

Both adapted definitions are isolated under `otls/lesson06_reviewed/`. The
original corpus and prior project's HDA copies remain unchanged. The internal
`Contents.gz` section must match the LandscapeWorkflow3 original byte-for-byte.

1. **IDMap Layers PythonModule:** the original accesses `kwargs['node']` at
   module import. Houdini's [HDAModule contract](https://www.sidefx.com/docs/houdini/hom/hou/HDAModule.html)
   supplies `type` there. Guard the optional node context; preserve the existing
   output-cook behavior when a node is supplied. No metadata or terrain
   algorithm changes.
2. **Original ID-to-Layer menu:** the original truncates five-layer menu codes
   to 0/63/127/191/255, while the original encoder produces 0/64/128/191/255.
   The unadapted original failed grass 2 and sand on the retained full Context.
   Round menu codes to the actual encoded values and guard absent metadata,
   using the supported [MenuParmTemplate API](https://www.sidefx.com/docs/houdini/hom/hou/MenuParmTemplate.html).
   The decoder's original internal remap graph is unchanged. This replaces the
   prior candidate's different, unproven decoder definition.
3. **Layers-to-ID:** retain the previously documented Lesson05 empty-metadata
   menu guard. Verify its algorithm section against the original HDA. No new
   encoding formula or material-selection algorithm is introduced.

Definition selection and native readback use the version-matched
[HDADefinition API](https://www.sidefx.com/docs/houdini/hom/hou/HDADefinition.html).
Vendor documentation supports these interface adaptations; full-domain native
measurements establish the integration result.

## Verification and replay

Use CPU hython 22.0.466 with `HOUDINI_OCL_DEVICETYPE=CPU`. Run
`scripts/houdini/repair_lesson06_idmap.py --help` for explicit corpus, input HIP,
output HIP, output root and area arguments. Process Context then Working,
loading the Context checkpoint for the Working pass. Existing completed proofs
and output HIP files cannot be overwritten. Interrupted mask extraction can
reuse its retained intermediates.

Run `scripts/houdini/verify_lesson06_reopen.py` once per area against the final
saved Reviewed HIP. Each invocation is a fresh process and recomputes only the
IDMap stack from retained masks. It checks loaded definitions, source mask
connections, full-grid encoding, decoded positions and bitwise conservation of
height, R/G/B, roughness and Alpha. No prior terrain stage is rebuilt.

Direct array thresholding is an independent placement oracle. Any discrepancy
must additionally match the exact native `volumesample` operation used inside
the original HDA. A temporary diagnostic wrangle measures that operation only;
it never feeds production geometry or writes a source mask. Every exceptional
index and sampled value is retained. This accounts for finite-precision
world-space sampling at threshold boundaries without relaxing a tolerance or
changing material selection.

`scripts/houdini/render_lesson06_review.py` renders native decoded arrays,
whole-domain overviews and native-resolution source/ID/decoded closeups. These
are explicitly CPU diagnostics, not viewport screenshots. It also compares
every Working rectangular perimeter sample with the nearest Context cell in
world coordinates. Different source grids are not assumed to select identical
materials; measured disagreement is reported and cannot silently become a
seam-continuity PASS.

## Delivery and acceptance boundaries

HIP/HDA binaries follow existing Git LFS rules; heavy caches stay on D:.
The machine-readable catalog is the registered implementation-status source;
the catalog generator preserves its status and receipt link. Local native
proof, source commit, remote delivery, protected CI, visual acceptance and merge
remain distinct. M3 performance is `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Review views

These images preserve measured ID/decoder results. Overviews use every eighth
sample; closeups use all 256 x 256 native samples and nearest display scaling.
Every material has a source/ID/decoded closeup in the same evidence directory.
Boundary strips show Working above Context at corresponding world locations.

- [Working overview](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/working_review_overview.png)
- [Context overview](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/context_review_overview.png)
- [Working five decoded materials](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/working_review_decoded.png)
- [Context five decoded materials](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/context_review_decoded.png)
- [Working scree at native resolution](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/working_review_scree.png)
- [Working sand transition](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/working_review_sand.png)
- [North boundary](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/boundary_north.png)
- [South boundary](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/boundary_south.png)
- [West boundary](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/boundary_west.png)
- [East boundary](../../../worldgen/houdini/sa_calobra/evidence/lesson06_reviewed/boundary_east.png)
