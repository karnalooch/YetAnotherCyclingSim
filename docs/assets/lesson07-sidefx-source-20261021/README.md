# Lesson07: original SideFX package and video reinspection

## Decision and implementation boundary

The owner requested the original Landscape Workflow3 archive and another close
review of Lesson07, followed by reproduction of that material workflow. This
supersedes the unexecuted custom normal candidate and further substitute-rock
experiments. Issue #365 / M3 continues in the existing Draft PR #474.

The owner's preceding clarification narrowed the immediate request to extracting
the textures from that supplied ZIP. **This extraction and file delivery is
complete.** External Fab/Quixel acquisition, purchase and substitute searches
are no longer the active task; no existing local export is requested from the
owner. This delivery made no Unreal import or material change.

The subsequent owner request is to implement the author's solution 1:1.
Native reproduction is now active again. The next bounded step retains the
installed `edit_level` contract during the existing authenticated discovery;
this adds no native call or binding mutation. An original-MI copy is being
prepared so layer associations are preserved instead of guessed through
name-only setters. The current Sa Calobra geography, visibility and registered
texture coordinates remain required inputs. The source global-colour coverage
defect and missing final video surface sets remain explicit dependencies.

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
mask over a base without RGB. This is a concrete source-stage hypothesis,
**not a verified cause**. The supplied Overview HIP does not contain that
first-grass instance, so its exact authored value cannot be inferred from it.

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
have not been added. No external acquisition or substitute search is active.
The later reproduction request resumes material work using the original source
system; its native candidate and application are not yet verified.

Actual application, corrected global-colour generation, matching PBR sources,
whole-area native evidence and final visual acceptance remain separate work.
`LESSON07_TECHNICAL_PASS: false`; `performance_pass: false`;
`performance_note: DEFERRED_AFTER_M3`. Preserve the current Editor and Draft PR.
