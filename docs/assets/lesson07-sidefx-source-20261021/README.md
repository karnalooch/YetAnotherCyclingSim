# Lesson07: original SideFX package and video reinspection

## Exact owner requirement and open source gaps (2026-10-22)

The owner explicitly requires **1:1 Pegasus reproduction, including all
configuration and assets**. The final tutorial state is the target. The
original ZIP, its defaults and the existing adapted candidate are separate
observations; none alone establishes that target. This dated instruction
supersedes the earlier extraction-only acquisition pause recorded below.
Official exact-source verification and permitted retrieval are active again.
No purchase or substitute selection is authorized.

| Area | Verified observation | Remaining requirement |
|---|---|---|
| Original Unreal graph | The 257 shared expressions have matching resolved connections; YACS adds visibility support and removes an unused grass output | Verify and explicitly retain any geographic integration differences; do not call the whole current graph byte-identical |
| Final PBR arrays | The five exact legacy IDs and their slot order are visible in Lesson07; the supplied ZIP has diagnostic arrays | Obtain the exact five families with matching D/N/ORDp maps and verify their source identity and settings |
| Final MI configuration | The prepared candidate retains ZIP defaults: Detail Brightness 1, UV Distort 4, Falloff 0.5 | Reproduce the verified final-video values 5, 1 and 1, plus the complete original parameter identities |
| Fresh native MI read | Recovery 39747236327 read both instances successfully; they still bind the existing YACS arrays | Name/order-only rows do not prove association/index or original SourceTextures |
| Houdini source textures | Direct Lesson03–05 inspection identifies five separate original families; current grass/cliff, sand and scree still use substitutions | Obtain those exact original files and verify their bytes and settings; the five Unreal IDs do not identify these Houdini inputs |
| Houdini instance values | Direct Lesson04 review now proves final grass use_mask=1 after a temporary unmasked preview; original HDA default is 0 | Restore the author's preceding rocky material with its exact inputs; complete the remaining material/tint/distortion parameter comparison |
| Geographic registration | Current maps use the real 16000-square, 8-km Sa Calobra domain | Preserve the accepted geography and verify its required coordinate mapping separately from tutorial material fidelity |

The five required Unreal families are `tkekcgfn`, `vjulbjjr`, `wenocdss`,
`ultncbnlw` and `ullmagidy`, in that order. Their official indexed legacy
ID/title mappings are retained in [the public-source receipt](video-source-public-id-mapping.json).
An exact current Fab listing, available source files and account entitlement
have not been established. A matching title is insufficient to select an asset.

The proposed new source-crop/canary using the current substitutions was stopped
before edits or native execution. The existing canary remains a mechanism test,
not 1:1 completion evidence. No material was changed by the successful
[Editor/camera recovery](recovery-39747236327-evidence.json). Read-only source
inspection can continue while the original-input gaps are resolved.

The earlier [direct grass-mask source correction](grass-mask-source-correction-20261022.json)
withdraws the earlier unmasked-base proposal. Lesson04's 04:46-04:54 narration
and 04:55 frame confirm the final enabled mask and an upstream rocky material.
At published source `fbe2eb7`, only `stage4a_grass.use_mask` was restored from
0 to 1; the rest of that recipe AST was unchanged. Exact recipe pins and the
strict existing comparison test were updated, with all ten CPU tests passing.
The subsequent graph correction below is a separate change. No native canary or cook ran,
and the existing substitute texture families remain unaccepted for 1:1.

The independent [native header observation](source-headers-39749604030-evidence.json)
confirms three 16000-square base volumes (`height`, `mask`, `Alpha`) and four
matching-size source masks. This is header/source-identity evidence only;
there was no full geometry load, material replay or UE change.

## Author's Houdini materials: Lessons03–05 source observations

The [timestamped author-instance receipt](houdini-author-material-observations-20261022.json)
retains five material families, their visible configuration, twelve ordered
source/material/tint operations (with the cliff-tint insertion still unverified
in that initial observation) and hashes for 42 inspected frames. The separate
[official ID/title mapping](houdini-material-public-id-mapping-20261022.json)
corroborates their legacy Quixel identities. These five Houdini families are
distinct from the five Lesson07 Unreal array families listed above.

| Author material | Original legacy ID | Publisher title | Observed Height Scale / Size | Evidence and precision |
|---|---|---|---|---|
| Rocky predecessor | `tjmledzr` | Hawaiian Lava Stone | 10 / 1000 | L03 09:24, final visible lesson state |
| Grass | `ulgmbhwn` | Rocky Steppe | 0 / 100 | L04 03:55–04:58, last directly readable fields; mask restored ON |
| Sand | `td1hcimn` | Thai Rippled Sand | 10 / 500 | L04 06:20–06:32, last directly readable fields |
| Cliff | `tdwlcc1l` | Icelandic Cliff | −10 / 100 | L05 00:03, continuation of the completed L04 setup |
| Scree | `vjdqcba` | Rocky Ground | 1 / 100 | L05 00:12–02:20, last directly readable HDA fields; mask network continues changing |

All five observed instances leave Roughness at the literal `default.pic`;
its resolved bytes and numeric output are not established. Grass has Distort
enabled with the observed Curl controls, while the other four displayed
instances have it disabled. The unmasked `(2,2,2)` tint is after grass and
before sand. The graph also contains separate grass, cliff, scree, exposure
and curvature tint observations. The initial cliff-tint frame shows a branch
with no output connection; the later follow-up below closes this connection.
Complete final mask/ramp tuples and saved-HIP parameters still have explicit
gaps. Temporary previews are separately recorded and
must not replace the last directly observed settings.

The [additional official-archive search](additional-author-hip-search-20261022.json)
inspected five HIPs from three further official archives without finding the
author's `Landscape_Workflow_03_Detailing.hip` or its material/tint instances.
This negative finding applies to the inspected files only. The selected
video filenames and some resolutions are readable, but original texture
bytes/hashes, exact Fab mappings and the remaining configuration are still
open. No source texture acquisition, native material replay, cache recook or
terrain change follows from these observations. Demo displacement values
are evidence of the author's setup, not authorization to alter the accepted
Sa Calobra heights.

## Graph correction and blocked material replay (2026-10-22)

The [later graph and parameter inspection](houdini-author-graph-followup-20261022.json)
retains 69 cited frame identities and distinguishes directly observed values,
temporal inference and unread fields. At Lesson05 09:41.5-09:42 the author
connects the cliff tint before the scree material. Later frames also expose
the final readable cliff and scree tint components. This supersedes the
earlier connection gap without changing the historical receipt.

The [reviewed source correction](graph-source-correction-20261022.json) in the
existing `lesson06_unified_pipeline.py` contains these changes:

| Area | Corrected source recipe | Evidence limit |
|---|---|---|
| Grass/sand order | Grass material -> gradient tint -> unmasked `(2,2,2)` tint -> sand material | The supporting mask branch and original materials remain incomplete |
| Grass gradient | Strength `0.95`; point 1 at `0`, RGB `(0.34,0.55,0.12705)`; point 2 at `0.996694`, RGB `(1,0.822741,0.538)`; Linear | Each point is directly read at a different time; their assembled final state is a temporal inference, not saved-HIP readback |
| Cliff/scree order | Cliff material -> cliff tint -> scree material -> scree tint | The original material and mask inputs are still dependencies |
| Cliff tint | Strength `1`, RGB `(0.597,0.597,0.597)`, Mask `mask` | Last readable 09:56 setting; earlier `0.437` and `0.487` are tuning states |
| Scree tint | Strength `1`, RGB `(0.874,0.822347,0.701822)`, Mask `mask` | All three fields are directly readable at 10:34 |

The same inspection also resolves more of the author mask graph. Grass
occlusion uses **Subtract with Invert Mask OFF**; the author inverts the ramp
itself. Exposure comes from the post-scree branch with the visualization helper,
and curvature continues the exposure-mask output. The last observed exposure
View Distance is `145` and Max Curvature is `0.18`. These observations are
retained for the next source correction; the still incomplete final ramp tuples
are not filled from presets or guessed numeric positions.

Material-dependent execution is now blocked at all seven direct stage entries
and before CLI dispatch for `all`, `materials`, `4a`, `4b`, `4c`, `scree`, `4d`
and `idmap`. The check precedes cache reuse and stops `all --force` before it
can reach base or masks. It has no bypass switch. The independent historical
substitute canary is also blocked at both `main` and `cook_canary`; its
diagnostic functions and strict source checks are retained. These changes
prevent the old substitutions or old cache presence from being reported as a
new reproduction. They do not admit a cook or change accepted terrain.
All **14 CPU tests pass**, including 32 pipeline entrypoint calls with and
without `force`. Independent source/code review accepts this partial,
blocked recipe. The base and mask function ASTs are unchanged. These tests
stub native modules for pipeline import; they do not claim a native replay.

The [static original-HDA inspection](houdini-original-hda-file-branches-20261022.json)
shows why the Roughness field needs more care: the HDA's Python SOP tests
`os.path.exists` on the evaluated `filename2`. Its false branch bypasses the
roughness-file node. Merely locating Houdini's stock `default.pic` does not
prove which branch the author used or the resulting numeric roughness.

The [native resource read](material-resources-39761109220-evidence.json), run
`39761109220` at source `7b43d13`, confirms that both installed material/tint
HDAs match the original byte hashes. It enumerates all ten entries of the
fixed project texture root, finds no exact-family Albedo/Displacement matches,
and records the five named immediate family folders as absent in that scope.
It does not search other libraries or establish whole-host absence. The stock
`default.pic` is present; the project/work CWD candidate files are absent.

The installed host recipe has hash `6e8c8b70...`, different from the published
source recipe checked by this audit. The read-only run does not deploy the
new source corrections. No original map acquisition, material cook, cache
overwrite, HIP save, Unreal import or visual acceptance is established.

## Decision and implementation boundary

The owner requested the original Landscape Workflow3 archive and another close
review of Lesson07, followed by reproduction of that material workflow. This
supersedes the unexecuted custom normal candidate and further substitute-rock
experiments. Issue #365 / M3 continues in the existing Draft PR #474.

The owner's preceding clarification narrowed the immediate request to extracting
the textures from that supplied ZIP. **This extraction and file delivery is
complete.** External Fab/Quixel acquisition and substitute searches were
paused for that extraction-only request. The latest instruction above resumes
exact original-source verification and permitted retrieval. This earlier
delivery made no Unreal import or material change.

The subsequent owner request is to implement the author's solution 1:1.
Native reproduction is now active again. The authenticated
[metadata discovery](discovery-39668607144-evidence.json) retained the complete
installed `edit_level` contract with **zero native calls** and the same owner
Editor PID 11284. Its discovery step succeeded; the overall workflow failed
later because the separate historical error reader refused the current owner
with `FAILURE_LOG_OWNER`. That reader and the denied observer remain unchanged.
The typed level tool supports `modify` with reflected properties and explicit
`save:false`; the preparation below obtained a fresh four-Landscape inventory,
but exact material-binding proof is still needed before a binding preview.
An original-MI copy is now saved, preserving the source layer parameters. The
current Sa Calobra geography, visibility and registered texture coordinates
remain required inputs. Source global-colour coverage and the missing final
video surface sets remain explicit dependencies.

The [decoded material contract](one-to-one-material-contract.json) compares the
original and saved YACS masters. Their 257 shared expressions have matching
classes and all resolved input links/output indices/channel masks. Of those,
256 match every compared decoded property; the remaining material-layer node
differs only in its cross-version EditorOnly representation, with matching
runtime layers and blends. YACS adds visibility masking and removes an unused
grass output. This supports retaining `M_Landscape_YACS` as parent for a copy
of the original instance. It is static evidence, not a native compiler or
render acceptance. The first candidate uses the ZIP's saved instance defaults;
the final video's distinct brightness/distortion/falloff values are now part
of the required target, not an optional comparison profile.

The [persisted MI tuple comparison](one-to-one-mi-parameter-evidence.json)
also resolves the repeated-name ambiguity. The saved YACS instance already has
the original five runtime layers, four blends, all eight layer/blend index
overrides and their expression GUIDs. Its 61-row native read includes inherited
values; the package contains 30 explicit scalar overrides. There is only one
explicit `Global Colour Strength`, associated with `GlobalParameter/-1`.
Keeping the YACS registration and texture bindings leaves five scalar changes
for the ZIP profile: Global Brightness 0 to 0.5, Global Colour Strength 0 to
0.5, Global Normal Flatten 1 to 0, Global Saturation 0 to 0.5 and Global
Specular Scale 0 to 1. The final video additionally uses Detail Brightness 5,
UV Distort 1 and Specular Falloff Exponent 1. The offline reader roundtrips
both selected current-MI export payloads exactly but cannot decode the
editor-only layer-name/GUID cache; it does not prove a native compile.

The reviewed candidate-preparation operation has eleven fixed typed calls and
22 fresh owner checks. It inventories Landscape actors, checks current and
source instances and the existing parent, requires nine clean input packages,
then saves only a new current-MI backup and an adapted original-MI copy. It
reads both copies and the active instance back, checks the input files remain
unchanged, and retains exactly the two new packages for indexed offline review.
It does not apply the candidate to the Landscape. The active material,
geometry, IDMap and map save state remain outside this preparation operation.
Optional host memory and fixed small-crop file metadata support a separate
future source-colour canary; this operation does not launch Houdini.

That preparation now completed in [run 39672674724](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39672674724)
at source `1479d2ddd424d47ddc35b179c5599eba9cfb6cbe`: eleven calls and 22
fresh checks retained the same PID 11284. The
[native preparation receipt](preparation-39672674724-evidence.json) records
the two saved packages, unchanged nine inputs and complete ordered readbacks.
The backup's decoded persisted tuple contract matches the actual current MI.
The new source copy is saved at
`/Game/Generated/YACS/Lesson07_Unified/Materials/SideFX_OneToOne_20261021/MI_Pegasus_Source_YACS`.
It has not been assigned to the Landscape. Its offline reader encounters an
unsupported legacy `TextureStreamingData` payload, so a complete candidate
export comparison remains unverified despite the successful native reads.
The separate [partial-prefix receipt](preparation-39672674724-candidate-prefix-evidence.json)
does decode all parameter and runtime-layer properties before that unsupported
section: eleven complete properties roundtrip to an identical 16,184-byte
prefix. All 29 source scalar GUIDs, eight layer/blend tuples and five ZIP global
values are preserved. The added Terrain Scale 50 has a zero ExpressionGUID,
unlike the previously saved YACS override; that is an explicit metadata
difference, not proof of a bad runtime value. This supplementary result does
not change the [frozen full-validator result](preparation-39672674724-offline-validation.json)
from `OFFLINE_PARAMETER_CONTRACT_UNVERIFIED` to PASS.
The host reported about 16.8 GiB free physical memory, but the pinned 257-square
source crop was missing. The small Houdini canary was consequently not launched;
no alternate or full-size cache was substituted.

The historical [base-coverage proposal](base-material-coverage-recipe.json)
changed `MAT_GRASS.use_mask` from 1 to the HDA default 0. Its source-graph
interpretation remains a mechanism observation, not a native A/B or proof of
the author's instance. Direct Lesson04 review supersedes that proposal and
restores the verified final mask value 1, as recorded above. The separate
mask input and `heightscale=0` remain unchanged. Existing caches are skipped
and were not invalidated or rebuilt by either source edit. No geometry or
IDMap write was performed.

A separate [input-inspection operation](input-inspection-scope.json) is prepared
to read metadata for eight fixed historical cache paths and make one installed
plugin-source search, with two fresh owner checks. It will establish available
inputs and inspect scalar-setter semantics before the final-video comparison.
Its publication does not itself establish either result or alter a material.

The archive and video establish an important dependency: **the downloaded
project contains the material system and diagnostic arrays, not the five
finished Megascans surface sets shown at the end of the lesson.** Replacing the
current arrays with those archive defaults would remove the actual surfaces.
After the owner's manual Windows reset, the reopened canonical Editor was
verified and both read-only inventories completed. The standard Megascans
surface folder is empty. The subsequent five-ID search across `/Game` found
no registered Texture2D names containing any of the exact video identifiers;
each query reported 0 shown / 0 total and `raw_from_registry=457`, without
truncation. Renamed assets, unregistered files, external download caches and
license entitlement remain unverified. No completed 1:1 native application or
Lesson07 acceptance is claimed by this source review.

## Original texture files extracted and delivered

`SideFX_Textures_From_Original_Zip.zip` was delivered to the owner. It contains
**57 original files**, preserving their source archive paths and uncompressed
bytes. Its size is **217,202,273 bytes**, SHA256
`672310b3b66072db2c1cfe73d958c69cb7b0a4e0c195a7a361c52b8e008ccdee`.
The selected files total 224,958,528 uncompressed bytes.

| Original file type | Count | Contents |
|---|---:|---|
| Texture2D | 48 | 9 Landscape diagnostic colours and 39 foliage textures |
| Texture2DArray | 3 | `TA_Colour`, `TA_Normal`, `TA_Masks` |
| SourceContent PNG | 4 | Terrain Colour, AO, IDMAP and wetness |
| SourceContent OpenEXR | 2 | The original `tlonbisya` and `wepoeaw` displacement images |

The [unchanged extraction manifest](original-textures-extraction-manifest.json)
records every selected path, class, size and SHA256, plus coverage of all
125 `.uasset` files. Their metadata was inspected with the pinned UAssetAPI
reader; the 51 selected assets have matching top-level export and AssetRegistry
classes. One unrelated ExternalActor has no top-level asset class and is
correctly excluded through its registry class. Asset names alone were not used
for selection. Every new ZIP member was read back and checked against the
original size, CRC32 and SHA256. No image conversion or `.uasset`
reserialization occurred, and the source archive remained unchanged.

The [six-image inspection](source-six-image-inspection.json) independently
records the four PNG dimensions/formats and two 4096x4096 single-channel
FLOAT32 EXR headers. The extraction includes only files actually present in
the supplied archive; it does not supply the five final landscape PBR families
shown in the video. It also does not import the archive's diagnostic arrays
over the current surfaces.

## Original archive, downloaded again

- [Official ZIP](https://media.sidefx.com/files/tutorials/project-pegasus-landscape-workflow/ProjectFiles_LandscapeWorkflow3.zip).
- Actual size: **605,943,562 bytes**.
- SHA256: `8c4e9f7ebacedc914f9ab55e82ac378aa18d3366207d859f393758a0f9dade10`.
- The new download exactly matches the historical catalog's size and SHA256.
- **394 entries, 187 files, 674,890,049 uncompressed bytes**; all paths and CRCs
  checked before use. No downloaded project code was executed.

The [download receipt](download-receipt.json) and
[complete archive inventory](zip-inventory.json) retain the observations.
The [compact archive/HDA inspection](source-archive-hda-summary.json) retains
the exact array sources and HDA findings. Source assets were parsed without
writing any `.uasset`. The original master,
instance and three arrays passed complete in-memory byte equality with the
pinned UAssetAPI reader. This is file inspection, not an Unreal compilation.

| Original package asset | Actual contents |
|---|---|
| `TA_Colour` | Eight 64x64 diagnostic slices: Engine WhiteSquareTexture, then T_R, T_O, T_Y, T_G, T_B, T_P and T_V |
| `TA_Masks` | One 128x128 Engine DefaultDiffuse_TC_Masks slice; Masks compression, sRGB off |
| `TA_Normal` | One 1x1 Engine BaseFlattenNormalMap slice; Normalmap compression, sRGB off |
| `MI_Landscape_Instance` | References those arrays; Terrain Colour initially points to Engine WhiteSquareTexture and Terrain IDmap to Debug/T_Null |

The archive also contains separately exported terrain maps. Their presence
does not make the instance's placeholder bindings final. Exact original
parameters, associations, indices and texture references are retained in
[original-material-settings.json](original-material-settings.json).

A separate [remote-tree comparison](current-landscape-archive-comparison.json)
shows that all **37 original Landscape source packages** under
`Content/PegasusDemo/Materials/Landscape` are already referenced by exactly
matching canonical Git LFS pointers at commit
`5869953cc0924b5078e2067e55336d720f3e6ea7`. The comparison uses each extracted
original's SHA256 and size and the untruncated remote Git tree. It establishes
committed source-pointer identity, not LFS server availability, current Windows
workspace bytes or the state of the derived active YACS material. No native
operation or new import was performed by that comparison.

## What was reviewed in the video

Source: [Lesson07, Vimeo 888569514](https://vimeo.com/888569514), duration 26:24.
The complete 595-cue transcript was read, 120 timeline thumbnails were reviewed,
and 36 full-resolution frames were inspected at the material, texture and
export operations. The [observations](video-observations.json) list the exact
reviewed times; [frame receipts](video-frame-receipts.json) identify captured
images. This does not claim uninterrupted playback, inspection of every video
frame or an independent audio listen. Full captions/video are not republished.

| Lesson time | Original operation |
|---|---|
| 01:43-03:58 | Subtract pre-procedural height from the result; cache the separate procedural layer |
| 04:59-08:08 | Export raw ID as single-channel 8-bit data; export r/g/b separately as RGB colour |
| 10:36-11:56 | Convert the Houdini RGB output from linear to sRGB before colour export |
| 12:38-12:58 | Reload the procedural layer through the original Landscape HDA in Update Existing mode |
| 13:07-17:36 | Apply the supplied instance, bind both terrain maps, and set IDMap to Grayscale, sRGB off and Nearest |
| 17:45-21:43 | Populate Colour-array slots with independently acquired matching Megascans surfaces |
| 22:03-22:18 | Restore Colour-array sRGB after the array changes |
| 22:41-24:23 | Balance global colour and local detail; final Detail Brightness is 5 |
| 24:43-25:18 | Fill matching Normal and ORDp/Masks slots in the same order |
| 25:17-25:42 | Review under changing light and restore Global Specular Scale to 1 |

## Exact final surface order

The readable Colour list at 21:42, Normal list at 25:02 and Masks list at 25:18
agree. Identifiers were read from the video's actual asset labels/tooltips.
They identify the video sources; no entitlement or present-day Fab availability
is implied by a name or identifier.

| Slot | Surface | Megascans identifier | Three corresponding maps |
|---:|---|---|---|
| 0 | Mossy Ground | `tkekcgfn` | `_D`, `_N`, `_ORDp` |
| 1 | Tundra Mossy Ground | `vjulbjjr` | `_D`, `_N`, `_ORDp` |
| 2 | Gravel Ground | `wenocdss` | `_D`, `_N`, `_ORDp` |
| 3 | Layered Rock Cliff | `ultncbnlw` | `_D`, `_N`, `_ORDp` |
| 4 | Shoreline Beach Rocks | `ullmagidy` | `_D`, `_N`, `_ORDp` |

The demonstration keeps eight array entries, with three unused diagnostic
entries. Only five classes are selected. Its final Normal array displays BC5,
with imported 4096x4096x8 and displayed/max in-game 2048x2048x8. The existing
five-entry YACS arrays are an explicit adaptation, not proof of absent layers.

## Final video values versus the updated archive

| Parameter | Final video | Downloaded original MI |
|---|---:|---:|
| Detail Brightness | 5 | 1 |
| Detail Tiling | 0.25 | 0.25 |
| Macro Tiling | 0.05 | 0.05 |
| Macro Texture Distance | 10000 | 10000 |
| Global Colour Strength | 0.5 | 0.5 |
| Global Normal Flatten | 0 | 0 |
| Global Specular Scale | 1 | 1 |
| Specular Falloff Exponent | 1 | 0.5 |
| Num IDmap Layers | 5 | 5 |
| Terrain Resolution | 2016 | 2016 |
| UV Distort | 1 | 4 |
| UV Rotate | -90 | -90 |

The original MI also serializes Global Brightness and Global Saturation at
0.5; these values are from the archive, not a claimed frame read. Global
parameters and identically named layer parameters have different associations.
The original MI has no per-layer Global Colour Strength overrides. Do not infer
that an absent layer override inherits the global parameter's numeric value.

The author's [official corrections](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/)
require the encoded layer count, blend Bit, layer atlas index and appropriate
Masks/Normal compression. The comment refers to terrain resolution 2017, while
the video and original MI show 2016. These distinct observations are retained;
the comments do not justify copying either demo size onto the 16000-pixel,
8-km Sa Calobra data. Project coordinates, scale, source extent and NoData
handling require their existing geographic adaptation. `UV Rotate` feeds the
shared GridCoordinates used by Terrain Colour and all five IDMap samples.
Direct detail/macro atlas UV inputs are independent of this rotation; the
selected slice indices depend on it through IDMap. The [connection trace](uv-rotation-trace.json)
is identical in the inspected original and current masters. Copying -90 onto
the current map would rotate geographically registered reads; the current 0
must be retained unless a separately verified map-coordinate adaptation proves
otherwise.

## Differences that matter in the current project

The retained native checkpoint uses Macro 0.05, but Global Normal Flatten is 1,
Detail Brightness is 1 and the global colour mixing controls have been disabled.
Those are earlier YACS adaptations, not final Lesson07 settings. The last
surface import replaced Cliffs Colour/Normal/Masks and Grass Normal/Masks only;
it retained Grass Colour and slots 1, 2 and 4. It never imported the five source
families listed above.

The original decoder is not a reason to rebuild the class map. With five
classes it uses spacing 255/(5-1); the blend compares rounded class codes
64, 128, 191 and 255. `Bit` selects the class and `Material_Selection` selects
the array slice. The current [0,64,128,191,255] codes are consistent with this
source. The decoder and layer packages were decoded from the official archive;
the separate 37-package comparison above establishes their committed source
pointer identity without claiming a current Windows byte readback.

Restoring global mixing requires resolving the known source-colour defect:
the retained 20 October native evidence contains black RGB inside valid Grass2
regions. Earlier disabling of Global Brightness hid this symptom; it did not
repair the Houdini source. The original material HDA's unmasked default fills
its material mask, while the current first grass operation explicitly uses a
mask over a base without RGB. Direct Lesson04 inspection shows that the author
instead layers masked grass over an earlier rocky material. The current
pipeline lacks that predecessor. This is a demonstrated recipe difference;
its contribution to the retained black RGB still requires a faithful native
replay. The supplied Overview HIP does not contain the relevant instances.

The freshly downloaded normal function has the same SHA256 as the earlier
offline inspection: `bb556279f30c6d116a4c24ae18a5234af28cf27cd9f2f59e43e6f85f71d5032a`.
The proposed private normal rewrite is consequently a separate adaptation,
not an original Lesson07 instruction. It remains paused and unexecuted.

## Earlier standard-folder inventory after the owner's reset

[Run 39654531355, attempt 2](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39654531355)
completed the three fixed read-only calls from source `1f6828d5`. The first
attempt was canceled before a runner or any job step was assigned; no native
operation occurred in that attempt. The second attached to the manually
reopened canonical Editor, PID 11284, start FILETIME `134370817710799968`,
interactive session 1. All six owner/process/listener checks agreed. No Editor
start/stop, import, parameter change or material save was performed.

The registry returned **0 shown / 0 total**, not truncated, for Texture2D and
subclasses under `/Game/Megascans/Surfaces`. This is complete for that scope,
not proof that the five sources are absent from every other project directory
or from an external owned download cache. The [original receipts and review](source-inventory-39654531355-2-evidence.json)
retain exact arguments and response bytes.

The MI read confirms Detail Brightness 1, Macro Tiling 0.05, Global Normal
Flatten 1, Global Specular Scale 0, UV Distort 4 and UV Rotate 0. The five
returned Global Colour Strength rows are all zero; Global Brightness and
Saturation are zero. Repeated scalar names retain their returned order, without
claiming a verified association/index for each row. The MI explicitly reports
`saved=false`.

All three arrays report 2048x2048. Colour uses TC_Default/sRGB on, Normal uses
TC_Normalmap/sRGB off, and Masks uses TC_Masks/sRGB off. The API returns
`pixel_format=<n/a>`: settings are verified, but actual GPU BC5 is not. Its
`required_sampler` field is a requirement derived from texture settings,
not a readback of material-function sampler nodes. SourceTextures lists are
not exposed by this read mode.

Historical protected CI `39654542444`, for source `1f6828d5`, passed its
executed hosted checks, including the saved-MI reader's 60 tests. Its Windows
lane refused `LOCAL_BUSY`
before checkout/build to preserve the open owner Editor. Later proof-log
staging also lacked its working directory because the checkout had not run.
That run concluded failure; it provides no native build or Automation PASS,
and its hosted results are not transferred to a later source commit.

## Completed project-wide ID inventory

[Run 39658443621, attempt 1](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39658443621),
from source `5869953cc0924b5078e2067e55336d720f3e6ea7`, completed **seven fixed
read-only calls and fourteen owner/process/listener checks**. All checks
retained PID 11284, start FILETIME `134370817710799968`, and listener 19315;
the harness retained interactive session 1 and reported no Editor start/stop.
The [new evidence summary](source-inventory-39658443621-1-evidence.json) links
the four byte-identical raw receipts and records their hashes.

The first five calls used `/Game`, recursive search, the full Texture2D class
filter including subclasses, `limit=200` and `offset=0`. The installed tool
defines `query` as a case-insensitive substring of the **asset name**.

| Exact query | Shown / total | Raw registry count | Truncated |
|---|---:|---:|---|
| `tkekcgfn` | 0 / 0 | 457 | false |
| `vjulbjjr` | 0 / 0 | 457 | false |
| `wenocdss` | 0 / 0 | 457 | false |
| `ultncbnlw` | 0 / 0 | 457 | false |
| `ullmagidy` | 0 / 0 | 457 | false |

All five filters were verified in order and all pages were complete; no
pagination was attempted. The 457 value is the registry count reported before
each name filter, not a count of matching surfaces. These results establish
no matches for the expected names in the registered project textures. They
do not exclude renamed assets, unregistered files or external caches, and do
not establish source provenance or license entitlement.

Call 6 read the current MI; call 7 read the three array settings. Their **full
response text and ordered JSON are identical** to the earlier three-call
inventory: 61 scalar rows, one vector, five texture bindings and three static
switches in the MI, plus the same three array-setting rows. The MI again reports
`saved=false`. The parameter, SourceTextures, GPU-format and actual sampler
limitations above still apply. This run performed no import or save and did
not repair the normals or Houdini global colour.

Protected [CI 39658455912](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39658455912)
for this exact source concluded **failure**. Hosted Python job `119425014052`
succeeded: the saved-MI reader passed 60 tests and the Wingman client passed
110 tests. The FULL plan selected 285/285 modules; that is selection coverage,
not a claim that deferred or skipped modules executed. Windows job
`119426772514` refused `LOCAL_BUSY` at 19:10:54 UTC before checkout/build,
preserving the owner's Editor. Proof-log staging then lacked its working
directory, and final cleanup again refused the busy owner. No native build or
Automation PASS is claimed.

## Remaining application and acceptance

The requested original-ZIP extraction and delivery are complete. The 57 files
have not been imported by this delivery, and the five final video PBR families
have not been added. Exact official-source verification and permitted retrieval
are active under the 22 October instruction; substitute selection is not.
The native candidate was saved and read back, but it uses the ZIP profile and
current YACS textures, has never been assigned to the Landscape and does not
meet the final-video 1:1 requirement.

Actual application, corrected global-colour generation, matching PBR sources,
whole-area native evidence and final visual acceptance remain separate work.
`LESSON07_TECHNICAL_PASS: false`; `performance_pass: false`;
`performance_note: DEFERRED_AFTER_M3`. Preserve the current Editor and Draft PR.
