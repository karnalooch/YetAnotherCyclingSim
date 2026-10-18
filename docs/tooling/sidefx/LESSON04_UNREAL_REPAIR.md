# Lesson04 isolated Unreal consumer repair

Recipe `SA-CALOBRA-L04-UE-REPAIR-20261018`, issue #365 / Draft PR #474,
M3. Base revision: `aee7a3dfdc6e6082139a75bdf94bc0544a12d8f7`.
This is a consumer repair of retained caches, not another terrain generator.
See the [build guide](SA_CALOBRA_BUILD_GUIDE.md),
[source concordance](catalog/PEG-02.md), and
[measured receipt](lesson04-unreal-repair-20261018.json).

The only admitted destination for these scripts is
`/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test`.
It was created with Unreal's `new_level_from_template` from
`/Game/Generated/YACS/Review/L_SaCalobra_Lesson04_Review` in an owned editor.
Original review/base maps, Lesson03/Lesson04 HIP files, retained caches and
`DefaultEngine.ini` were preserved. No Lesson05, roads, source DTM changes,
production-map replacement, merge, or visual/performance admission is included.

## Findings and measurements

The previous review preparation copied the old LandscapeOnly map and assigned
Lesson04 colour textures. That did not apply the retained Lesson04 heights.
The retained source caches contain 70,316,666 working samples (7154 x 9829),
with zero Manual Edits. `final - Source - Manual - Lesson04_delta` is exactly
zero at every working sample. The actual delta is -0.347969085 to +0.509399414 m;
39,223,702 samples are nonzero. These values describe this checkpoint, not a
new permanent bound on procedural detail.

The four imported tiles each contain 3811 x 5081 samples in Houdini orientation,
with 300 components of two 127-quad subsections. Unreal local X/Y is transposed
by the retained -90-degree yaw. Context contains 2017 x 2017 samples with
256 components of two 63-quad subsections. Counting component vertices with
shared borders repeatedly is not the unique sample count. The complete native
comparison covers 81,523,053 samples including duplicate tile edges; the
four-tile unique grid contains 77,436,981 samples, including retained padding.

| Native measurement | Before | Repaired, including fresh reopen |
|---|---:|---:|
| Maximum height difference from retained Lesson04 target | 0.657205 m | 0.022888184 m |
| Maximum shared-edge height difference | 0.0749714 m | 0 m |
| Every native uint16 code equals the expected final code | No | Yes, all five Landscapes |
| Four complete edge lengths | 5081, 5081, 3811, 3811 | Same |

The height error after repair is precisely the unavoidable half-step bound of
the selected uint16 range. No smoothing was used to make the seams agree.
Full before/after tables and array hashes are in the receipt. Raw Houdini input
floats have an exporter offset: they must be decoded before being described as
actual Unreal elevations. Earlier raw-export diagnostics are superseded by
these calibrated measurements.

Context already had a visibility mask and a masked hole material. Its mask
remains unchanged. Editor visibility traces alone were misleading: they hit
the editor's terrain beneath holes. A separate Simulate In Editor check found
all 484 sampled detail targets, no Context first hits at those locations, and
no Context collision at any of 35 sampled working-interior context positions.
This is bounded collision evidence, not an exhaustive runtime collision proof.

## Exact source mapping and adaptations

| Step | Original implementation retained | Bounded adaptation |
|---|---|---|
| Absolute base | Native `heightfield_layer`, `mode=add`, `layer=height`, Source plus retained Manual | No HIP writes; transient `/obj/LESSON04_TRANSFER_ONLY/SOURCE_PLUS_MANUAL` |
| Detail | Existing PEG-02 Lesson04 material-heightfield cache and its retained delta | No material-heightmap recook, random seed change or new detail algorithm |
| Tile registration | Existing cached grid origins, spacing, orientation and DTM padding | Copy coincident integer-grid samples; a native Layer replacement trial introduced up to 1.98 mm edge interpolation differences, so it was rejected |
| UE consumer | Houdini Engine cached-heightfield HDA and native Landscape Edit Layers | `output_mode=1` targets each copied actor by `unreal_output_name`; explicit base and delta layers, isolated bake folder |
| Readback | Native UE Landscape input through Houdini Engine WorldInput and SOP cache | A tiny native subnet caches its input and discards its output; no generated terrain. The local PE_Cache HDA had modified callbacks writing a fixed debug path, so it was not used for isolated evidence |

The original PEG-02 lesson mapping is unchanged. No video timestamp is claimed
for these version-specific transport adaptations. Their exact references are
the official [Landscape output modes](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html),
[Landscape outputs](https://www.sidefx.com/docs/houdini/unreal/landscape/outputs.html),
and [HeightField Layer](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_layer.html),
plus the installed H22.0.466 plugin implementations named below.

`output_mode=0` creates a new Landscape and derives its transform. Mode 1 writes
an existing Landscape/Edit Layer; it must not receive an absolute heightfield
as though it were an additive delta. The repaired test copy uses native height
clearing, then a shared `Scale.Z=585.9375`, Z origin zero, and two separate
imports: `Source_Manual_Lesson04` and `Lesson04_Procedural_Delta`. Original layer
names remain; their obsolete height contribution is cleared only in the copy.
Visibility is independent and retained. Merely changing Scale.Z would distort
the terrain and is not this procedure.

The chosen shared range is approximately +/-1500 m, with a 0.0457763671875 m
step. All samples fit without clipping. Original transfer min/max attributes
were present as floats; the report's claim that they were absent was incorrect.
`HoudiniLandscapeUtils::AdjustLandscapeTransformToLayerHeight` in the installed
plugin derives per-field scale in its normal non-default-scaling path. Attribute
presence alone therefore does not prove shared scale.

The pinned `ConvertHeightFieldData` normalizes floats and truncates `*65535`,
whereas Unreal's neutral sample is 32768. The adapter packs bin centres for
that converter. It quantizes absolute base and final heights first, then uses
`delta_code = 32768 + final_code - base_code`. This preserves the composite and
shared edges exactly. Conversely, `UnrealLandscapeTranslator` exports
`(code - 32767) * 512/65535 * Scale.Z/100`; the verifier recovers integer codes
and decodes Unreal units `(code - 32768) * Scale.Z/12800`. Exhaustive tests cover
all 65,536 codes at three scales. Revalidate this adapter for another plugin
version; do not apply its encoded floats directly as source metres.

## Colour and view checks

The retained PNG rows run north to south. The old material's positive V scale
mapped them in reverse. The isolated material copies use the north pixel edge
as the Y origin and a negative inverse Y extent, with pixel-centre registration.
Unreal's high-level vector setter did not reliably change this very small
inverse parameter; explicit reflected overrides are independently read back.
Original materials/textures are unchanged. Existing sRGB interpretation and
lighting are retained: these checks establish UV registration and viewability,
not colourimetric equivalence to Houdini or owner approval of appearance.
The native Landscape Visibility Mask connection and masked blend mode were
also read back. Full-area and near views are retained with the local evidence.

## Reproduction and evidence boundaries

Use an owned, idle native host following existing runner arbitration. Never
terminate an owner's editor or replace the active stream to run these scripts.
The tested versions are Unreal 5.8.2 CL 56702186 and Houdini/Engine 22.0.466.
The repository scripts are:

- `scripts/houdini/prepare_lesson04_ue_repair.py`: run with hython and explicit
  `--source-root`, `--transfer-root`, `--output-root`. Output must be a new
  directory outside both retained roots. The local accepted output is
  `D:/yacs/work/lesson04-ue-repair-20261018/transfer2`.
- `scripts/ue/apply_lesson04_ue_repair.py`: execute only after opening the exact
  derivative map. Set `YACS_LESSON04_TRANSFER` to the prepared directory and
  `YACS_LESSON04_PROOF` to a task evidence directory. Import files are hash
  checked before mutation. Only the derivative map/materials are saved.
- `scripts/houdini/create_lesson04_readback_hda.py --output <new.hda>`: create
  the native read-only cache adapter using hython.
- `scripts/ue/export_lesson04_ue_readback.py`: set
  `YACS_LESSON04_READBACK_HDA` and a new `YACS_LESSON04_READBACK_OUT`; execute
  in the derivative map. Wait for `complete.json`, not only a successful setter.
- `scripts/houdini/verify_lesson04_ue_readback.py --export-root <readback>
  --transfer-root <prepared>`: verify every sample, full shared edges, masks
  and expected integer-code hashes with hython.
- `scripts/ue/Test-YacsLevelEditorStreamClient.ps1`: use the existing receiving
  client check for stream proof. A reachable HTTP page alone is insufficient.

Houdini callbacks may pump Slate recursively. Both import and readback guard
against reentry and use post-processing/post-bake events. The initial synchronous
API attempt completed before its queued cook; it is not used as proof. Native
render-target height exports returned zero pixels despite success, so those
were also rejected. One diagnostic in-process world reload failed on retained
Python world references; fresh-process reopen is the accepted evidence.

The repaired map was reopened in a fresh editor and all native codes rechecked.
The existing browser proof observed increasing live frames, and NVIDIA's encoder
session inventory identified H.264 on that editor PID. Actual received video was
1912 x 910; 1920 x 1080 screenshots are separate evidence. The editor/stream is
left running on the derivative map. The old Live Host status was stale, not a
live session. No production promotion or PR merge is authorized by this result.

Heavy caches, map binaries, textures and raw logs remain local. The compact
receipt records source and code identities without publishing WebRTC session
credentials from logs. Owner visual acceptance remains pending, and performance
is `DEFERRED_AFTER_M3`, `performance_pass: false`.
