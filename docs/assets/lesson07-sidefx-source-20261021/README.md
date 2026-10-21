# Lesson07: original SideFX package and video reinspection

## Decision and implementation boundary

The owner requested the original Landscape Workflow3 archive and another close
review of Lesson07, followed by reproduction of that material workflow. This
supersedes the unexecuted custom normal candidate and further substitute-rock
experiments. Issue #365 / M3 continues in the existing Draft PR #474.

The archive and video establish an important dependency: **the downloaded
project contains the material system and diagnostic arrays, not the five
finished Megascans surface sets shown at the end of the lesson.** Replacing the
current arrays with those archive defaults would remove the actual surfaces.
After re-establishing the Editor session following the owner's manual Windows
reset, the next material operation is a fixed read-only inventory of the
existing project's Megascans surfaces and current material/array settings. No completed
1:1 native application or Lesson07 acceptance is claimed by this source review.

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
They identify required sources; no entitlement or present-day Fab availability
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
source. The inspected decoder and layer packages match the official bytes.

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

## Next native scope and acceptance

The owner reported a Windows reset, then clarified that it was manually
triggered. The former Editor process identity is historical. Re-establish a
fresh verified session through the existing startup path before attempting
the source inventory; no operation may reuse the pre-reset owner identity.

The fixed source inventory reads `/Game/Megascans/Surfaces`, the existing
material instance and the three current array settings through their existing
typed tools. It requires the same live owner process/listener and admits no
Python execution, import, save, geometry change or editor startup. A complete
registry result proves only presence/class/path; it does not prove licensing,
source-map consistency or successful rendering. Missing or truncated inventory
must remain explicit.

Actual application, corrected global-colour generation, matching PBR sources,
whole-area native evidence and final visual acceptance remain separate work.
`LESSON07_TECHNICAL_PASS: false`; `performance_pass: false`;
`performance_note: DEFERRED_AFTER_M3`. Preserve the current Editor and Draft PR.
