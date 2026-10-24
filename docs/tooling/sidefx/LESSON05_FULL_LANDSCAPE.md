# Lesson05: full Landscape scree and grading

Owner-directed full-grid execution, 2026-10-18, issue #365 / PR #474. No merge.
This supersedes the earlier small-patch-only execution scope in the
[plan](LESSON05_SCREE_PLAN.md). Original L03/L04 checkpoints and source data remain
inputs. Native authoring, Unreal admission and owner visual acceptance are
separate states; see the [measurement receipt](lesson05-full-landscape-20261018.json).

**Historical checkpoint:** full Working and Context authoring, saved HIP, fresh-process
full-grid tail rebuild and all-sample height/colour comparison. **Subsequently
completed:** Lesson05 UE import/reopen (see consumer evidence below). Final M3
owner visual acceptance remains pending.

## Local correction and audit, 2026-10-18

Owner-requested local work on `codex/365-world-graph`, HEAD
`99a5ae03a35fc5ff56e34a23ecfb9580431c8ba6`, issue #365 / open Draft PR #474.
GitHub has no milestone assigned to #365; the Roadmap places this work in M3.
No commit, push, merge, UE import, stream changes or Lesson06/07 work.
The [correction receipt](lesson05-tail-repair-20261018.json) records this pass.

Native inspection and hashes confirmed the original HIP and both final caches
match the preceding fresh-rebuild evidence. A real HDA binding error remained:
`PE_heightfield_tint::1.0` labels `srcname1` as **Ramp Layer**, and `ramp_mask`
as **Mask**. Empty `ramp_mask` made both constant cliff/scree tints global.
The correction uses `ramp_mask="mask"` for constant tints only; the broad
occlusion and curvature ramp bindings were already correct. Cliff tint now
reads the original L04 `WORKING_MASK_CLIFF` / `CONTEXT_MASK_CLIFF`, rather than
recomputing that slope selector on L04's displaced height.

Only the tint/output tail was rebuilt, under
`D:/yacs/work/lesson05-tail-repair-20261018`. Source, Manual, L04, Slump,
pockets, Layer Slump, remapped scree and material/displacement caches were
reused. The original broad-occlusion/curvature masks are also reusable through
`--reuse-root`; Context initially recomputed those two masks before the reuse
path was added. Final caches additionally retain named `cliff`, `pockets`,
`broad_occlusion`, `curvature`, and the actual material-placement `scree`.

Corrected checkpoint:
`worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson05_Reviewed.hiplc`.
The original Lesson05 HIP/cache remain unchanged rollback inputs. The older
receipt describes that earlier checkpoint, not the corrected global colour.

### Native checks and source mapping

Fresh processes reopened the corrected HIP and rebuilt the native final Tint
for both full domains: **zero differences** in height/R/G/B/roughness versus
the corrected caches, over **74,510,970 samples**. All height/scree/roughness
samples equal the earlier Lesson05 result. Constant cliff/scree tint changes
outside their respective masks are exactly zero in every RGB channel.
Native resolution/origin/axes are:

| Domain | Grid | First sample (Houdini metres) | Grid steps |
|---|---|---|---|
| Working | 7154 x 9829 | (-1771.25, 0, 3144.25) | +X 0.5 m; -Z 0.5 m |
| Context | 2048 x 2048 | (-3998.046875, 0, 3998.046875) | +X 3.90625 m; -Z 3.90625 m |

The retained original PEG-02-05 transcript was read. Direct Vimeo retrieval
failed; the timestamped retained caption was available. All three original
HDA hashes match the preceding receipt. Layer Slump resolves from retained
`ProjectFiles_LandscapeWorkflow3/.../Houdini/Packages/PegasusDemo/otls/`;
Material and Tint resolve from the project's `otls/` copies of those definitions.
`SIDEFXLABS` resolves to `D:/yacs/tools/sidefx_packages/SideFXLabs22.0`;
no new Labs node or generator was introduced.

| Lesson time | Actual node under each `LESSON05_<AREA>` | Effective settings/result |
|---|---|---|
| 00:00–00:20; 06:39–07:58 | `MATERIAL/FORGE_SCREE` | Original Material; size 4 m, Height Scale .1, Use Mask 1; reused cache |
| 00:20–02:07; 08:00–09:20 | `SLUMP/SCREE_SOURCE_SLOPE`, `SCREE_DOWNHILL` | Source 35–90 degrees; 20 iterations, repose 30 degrees; erosion/bedrock off, outflow on |
| 02:22–03:10 | `TRANSPORT/MEASURED_SLUMP_RANGE` | Measured maxima Working 44.15713119506836 / Context 25.54274559020996; mask to 0–1 |
| 03:10–06:38 | `POCKETS/LOCAL_POCKETS`, `TRANSPORT/POCKETS_LAYER`, `PEGASUS_POCKET_TRANSPORT` | Occlusion 5 m, inverted ramp; left mask/right pockets; direction 1, iterations 20, repose 0, spread 1 |
| 06:39–07:58 | `TRANSPORT/MEASURED_SPARSE_REMAP` | Measured maxima .6418575644493103 / .9552562236785889; output 0–1; original sparse ramp and dry/Alpha exclusion |
| 09:20–10:38 | `CLIFF_TINT/CLIFF_TINT`, `SCREE_TINT/SCREE_TINT` | Correct mask binding; strengths .15/.2; colours (.94,.96,1)/(1,.98,.95) |
| 10:38–14:10 | `OCCLUSION/EXPOSURE_TINT` | 25 m exposure; strength .2; white–(.93,.95,.92)–white ramp |
| 14:10–15:19 | `CURVATURE/CURVATURE_TINT` | Computed curvature range 2 / .25600001215934753; strength .1; 1–1.02–1.05 ramp |
| 15:19–17:19 | `FINAL_CACHE`, `GLOBAL_COLOR`, `NEUTRAL_GEOMETRY` | Complete saved HeightField; default colour display; independent named masks |

The [native direction control](../../../scripts/houdini/check_lesson05_transport.py)
used a 400 m diagnostic crop with a 50 m analysis margin. Pocket-weighted mask
accumulation was .137867 with zero iterations, .014172 in the opposite direction
and .185187 in the retained direction. All three preserved height exactly.
This supports the intended pocket attraction; it does not replace full-domain
processing or whole-area visual acceptance.

Material inputs remain Forge `run-a/mediterranean_soil/limestone_scree_v1/export/YACS_Material_BaseColor.png`
under `D:/yacs/work/lesson05-material-forge-20261018`, plus
`D:/yacs/work/lesson05-houdini-20261018/Height_Pegasus.exr` and
`Roughness_Pegasus.exr`. Height uses the existing Forge +.03 neutral adapter;
roughness is ORM green. These are Material Forge assets, not SideFX textures.
No additional texture generation or colour-space conversion occurred.

### Replay, views and remaining acceptance

For an incremental correction, pass `--reuse-root <original-full-root>` and
`--checkpoint-input <retained-L04-or-L05-HIP>` to `lesson05_full.py`, with a
fresh output root. Execute `cliff_tint`, `scree_tint`, `occlusion`, `curvature`,
`verify` serially for each area. Pass `--reuse-root` to the checkpoint assembler
and `--previous-root <original-full-root>` to the fresh measurement script.

The [review renderer](../../../scripts/houdini/render_lesson05_review.py), run
with the project Python and `--root <correction-root>`, writes images in its
`working/` and `context/` folders:
`whole_domain_review.png`, `review_scree.png`, `review_pocket.png`,
`review_transition.png`, `review_gentle.png`. Each compares the same registered
L04/L05 location in colour, mask and neutral geometry. Overviews sample every
eighth cell; closeups use native samples. Neutral images are CPU hillshade
diagnostics, not perspective renders or Unreal screenshots. Coordinates are
recorded in the correction receipt. Native hillshade shows existing fine
terrain patterns; the colour correction makes no claim to repair source or
L04 geometry. Scree remains sparse and the gentle-area centre remains unmasked.
For occlusion/curvature on/off views, run the same renderer with hython and
`--export-stages` first, then with project Python. `grading_review.png` compares
the retained stage colours without applying the tints twice. The direction
control figure uses one shared mask scale for zero/opposite/retained cases.

Native persistence and the bounded direction test pass. Owner visual
acceptance, perspective-camera review and final Working/Context consumer
transition acceptance remain open. The active saved UE map still shows the
earlier baked global colour, not this correction or a Lesson07 material.
The inherited ID-layer menu warning was subsequently repaired with explicit
owner authorization; see the bounded follow-up below.

### ID-layer menu follow-up, 2026-10-18

The owner authorized repairing the warning after the Lesson05 review.
Both overview `PE_Heightfield_Layers_to_ID::2.0/IN_MENU` geometries have no
detail attributes. The original menu calls `dictAttribValue("id")` without
checking that `id` exists. The adaptation adds only
`findGlobalAttrib("id") is not None` before that read, using the documented
[SideFX Geometry API](https://www.sidefx.com/docs/houdini/hom/hou/Geometry.html).
Missing metadata now returns an empty menu; it does not fabricate an IDMap.

The corrected definition is embedded in `SaCalobra_Pegasus_Lesson05_Reviewed.hiplc`
and serves the two overview instances. The external original HDA is unchanged.
The pre-fix HIP is retained as `SaCalobra_Pegasus_Lesson05_Reviewed_BeforeIdMenuRepair.hiplc`.
The [menu repair receipt](lesson05-id-menu-repair-20261018.json) supersedes the
earlier receipt's HIP hash only: current SHA-256 is
`c4720f00e1bdcab20a1a4639509bee8cb874eff01d7d18b4a7049b1d1cdcd539`.
No terrain nodes or cache files were edited or recooked.

Fresh-process reopen passed for both menus and real HOM fixtures with absent,
empty and two-entry ID dictionaries. Save emitted no ID-layer traceback;
Houdini did emit its informational notice that the embedded definition was
saved despite the general Save Definitions preference being disabled.
This repairs the menu only; Lesson06 IDMap generation is not implemented.
Reproduction: `scripts/houdini/repair_lesson05_id_menu.py --hip <HIP> --receipt <JSON>`;
use `--verify` for read-only HIP verification (updates the receipt).

Validation: Python compilation, `git diff --check`, documentation index
links/i18n/structure/freshness and targeted changed-document UTF-8/link checks
pass. The new compact receipt passes the raw-storage limit. The global
`check_evidence_storage.py` fails on the unchanged historical
`docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json`:
its 44,200 CRLF endings change the raw blob from the exact LF exception pin.
LF-normalized content matches HEAD and the exception; no historical evidence
was rewritten to bypass the guard. Native hython initially failed in the
sandbox with a system-DLL relocation error; execution outside that sandbox
succeeded. No application installation or shared host setting was changed.

## Source mapping and implementation

The [original Pegasus lesson](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/)
and retained PEG-02-05 transcript define the sequence. The material substitution
is the validated [Forge limestone scree](LESSON05_MATERIAL_PREPARATION.md).
This follows the original node workflow, not the fictional island's numerical
terrain settings. Numeric settings below are explicit Sa Calobra candidates.

| Lesson time | Executed operation / candidate settings |
|---|---|
| 00:00–00:20 | Original `PE_heightfield_material::1.0`; Forge BaseColor, ORM green roughness and adapted Height; 4 m texture size |
| 00:20–02:07 | Native HeightField Slump, 20 iterations, 30-degree repose; erosion and Add to Bedrock disabled |
| 02:22–03:10 | Native Remap with measured full-grid maximum |
| 03:10–06:38 | Native Mask by Feature occlusion, 5 m view distance, inverted ramp; Copy Layer to `pockets`; original `PE_heightfield_layerslump`, 20 iterations, inverted direction |
| 06:39–07:58 | Measured Remap, sparse ramp `(0,0),(.05,0),(.4,.45),(1,1)`; dry/valid support exclusion after transport |
| 08:00–09:20 | Separate 35–90 degree slope source with soft falloff; original cliff mask preserved |
| 09:20–10:38 | Independent original Pegasus cliff/scree tint nodes, strengths .15/.2; colours (.94,.96,1)/(1,.98,.95) |
| 10:38–14:10 | Original Pegasus tint driven by broad 25 m exposure; strength .2, restrained white–(.93,.95,.92)–white ramp |
| 14:10–15:19 | Curvature feature and original Pegasus tint, strength .1, ramp 1–1.02–1.05 |
| 15:19–17:19 | Separate global RGB, scree mask, final height, Lesson05 delta, neutral and colour display nodes |

All Working transport operates on the continuous 7154 × 9829 grid, not independent
UE tiles. Context uses its retained native grid and the same staged recipe.
Full-area evaluation removes artificial interior crop boundaries; the original
dataset border remains a real boundary. Source/Manual/Lesson04 remain distinct.

## Material calibration and precision

The original HDA maps Height to `scale * (2 * H - 1)`: neutral is .5. Native flat
controls 0, .47, .5, .75 and 1 measured -1, -.06, 0, .5 and 1 at scale 1.
The adapter adds .03 to Forge Height so the recipe's .47 reference becomes .5.
The full material uses a **candidate** height scale .1; measured terrain change,
not that slider alone, determines its physical effect.

Roughness is extracted from ORM green into a float EXR. The PNG colour control
(128,64,192) measured approximately (.501961,.250980,.752941) in native RGB:
the HDA retains encoded PNG values. Full authoring therefore uses Forge's PNG
in the same existing Lesson04 convention. The calibration also emits a linear
EXR for consumers that explicitly need it; mixing it with encoded Lesson04 RGB
would be incorrect. There is no claim of a completed UE colour-space/UV check.

The earlier zero-height material control found native blend roundoff of
0.00006103515625 m. Mask-only stages require exact unchanged height. Final
assembly preserves the HDA's result inside the scree support and copies exact
registered Lesson04 samples outside it, eliminating unsupported roundoff.
This is an explicit transfer precision adapter, not terrain generation.

## Reproduction and saved work

Run with Houdini 22.0.466. Set `HOUDINI_OCL_DEVICETYPE=CPU` to leave GPU resources
available to the owner stream; this uses SideFX's
[supported CPU OpenCL driver](https://www.sidefx.com/docs/houdini/ref/env.html).
The host verified Intel OpenCL on the i5-9600K. Run stages serially in separate
hython processes to release native caches between stages.

1. [Calibrate the material](../../../scripts/houdini/calibrate_lesson05_material.py)
   with `--source-root`, fresh `--output-root` and `--material-root`.
2. [Execute full native stages](../../../scripts/houdini/lesson05_full.py) with
   `--source-root`, fresh `--output-root`, `--corpus`, `--forge-root`,
   `--adapter-root`, `--checkpoint-input <retained-L04-HIP>`,
   `--area working|context`, and `--stage` in this order:
   source, slump, pockets, transport, material, cliff_tint, scree_tint,
   occlusion, curvature, verify.
3. [Assemble the checkpoint](../../../scripts/houdini/save_lesson05_full_checkpoint.py)
   using the same source/output/corpus roots and a new `--checkpoint` alongside
   Lesson04, preserving its HIP-relative source locators.

Retained host output root: `D:/yacs/work/lesson05-full-20261018`.
Large HIPs, caches, map images and Forge textures stay outside Git. Git contains
the replay code, configuration in code, source mapping and compact measurements.
The stage graphs and caches are individually retained for debugging and
incremental replay. Changes to a stage invalidate it and all downstream stages;
use a new output root rather than overwrite evidence.

## Full-grid measurements and persistence

| Measurement | Working | Context |
|---|---:|---:|
| Native samples | 70,316,666 | 4,194,304 |
| Resolution | 7154 x 9829 | 2048 x 2048 |
| Lesson05 signed increment | -0.000488281 to +0.016723633 m | -0.000457764 to +0.019287109 m |
| Nonzero scree coverage | 7.58682% | 4.44145% |
| Coverage above .1 | 1.33126% | .73361% |
| Changed height samples | 4,034,078 | 134,728 |
| Height change outside scree support | exactly 0 m | exactly 0 m |
| Total procedural versus Source+Manual | -0.347969085 to +0.509399414 m | -0.340454102 to +0.351074219 m |
| Fresh native tail differences: height/R/G/B/roughness | all 0 | all 0 |

All mask-only stages preserved every height sample exactly. All measured
height, mask and colour values are finite. Full native registration matches
Lesson04. This is 74,510,970 native samples, not the different padded/duplicated
UE tile sample count. No UE seam result is claimed here.

Checkpoint: `D:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson05.hiplc`.
Its SHA-256 and both final-cache hashes are in the receipt. Ten retained input
hashes match the Lesson04 repair manifest. The original Lesson04 HIP hash is
unchanged. [Fresh measurement code](../../../scripts/houdini/measure_lesson05_full.py)
reopens the HIP and actually rebuilds the full final native stage before
comparing all five channels, then measures Source+Manual-relative deltas.

The default curvature range initially yielded an empty mask. That diagnostic
output was retained, the native Compute Curvature Range action supplied the
correct ranges, and curvature/verification were rerun. Legacy overview nodes
originally emitted ID-layer menu errors during HIP save; the bounded follow-up
above records their subsequent repair.

## Unreal consumer import, 2026-10-18

The [consumer receipt](lesson05-ue-import-20261018.json) records a separate saved
map: `/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05`.
The original repaired Lesson04 map is byte-identical to its pre-import hash.
Houdini Engine output mode 1 adds `Lesson05_Increment` above retained L04 layers.
It encodes **q(L05) - q(L04)** around the calibrated neutral height code; it does
not import absolute height as an additive delta or clear the retained layers.
All five tiles retain Scale.Z 585.9375 and Z origin zero.

Full native readback before import, after save and after map reopen compares
81,523,053 samples (including duplicate tile edges). All expected uint16 hashes
match. The maximum source-height error is 0.022888184 m, the half-step of the
shared 0.0457763671875 m encoding. All four complete shared edges have exactly
0 m discrepancy. The reopen is a fresh map load within the same editor process,
not a claim of a separate-process reload of the final saved map.

Every Working/Context visibility sample is unchanged across those three reads;
the previously verified Context exclusion remains retained. Native readback
confirms the five new albedo textures, sRGB flags and north-first world UVs.
Three exported RGB tile edges match exactly. One green channel at row 167 of
the 0_1/1_1 boundary differs by one code (76 versus 75). Repeating native SideFX
resampling reproduced green values 0.296080112 and 0.296071589: the two tile
transforms represent X as 4.750122070 and 4.75 m at Z 3196.25 m, outside Working.
This straddles the 75.5 rounding boundary. Exact colour-seam equality is **false**,
not silently accepted by a relaxed test; the measured discrepancy is retained.
The consumer uses baked
Pegasus global colour containing the Forge scree; this is not a new multi-layer
PBR shader or a claim that every Forge channel was independently bound in UE.

The old offscreen stream reported CUDA 700 and could not expose a console.
The owner approved a controlled restart with the import at startup. A
corrective restart was needed after the texture setter returned false; the
existing Forge importer pattern (explicit override plus independent readback)
resolved the failure. Full measurements then found 1605 unchanged Context
samples while all four detail tile hashes matched. The transfer incorrectly
retained a visibility volume: in pinned SideFX `HoudiniLandscapeTranslator.cpp`
the clear path for both Height and Visibility clears the heightmap, keyed
separately per target name. Visibility therefore erased the preceding height
increment. Removing non-height primitives (as in the L04 adapter) fixes the
transport without changing source geography or retained visibility. One final
restart applied this correction only to Context, gated by a full readback of
the known mixed pre-correction state. All attempts and failures remain retained.
The initial successful stream retained H.264 NVENC and the CUDA workaround;
that configuration was later superseded by the recovery below. The receipt
records actual increasing decoded browser frames; this is a bounded reception
proof, not an overnight stability claim or a performance PASS.

### Replay and next startup

- [Prepare the transfer](../../../scripts/houdini/prepare_lesson05_ue.py) with
  `--lesson05-root`, `--lesson04-transfer`, `--tile-root`, and a fresh
  `--output-root` set to the retained work root's `transfer-height-only` folder.
  Use Houdini 22.0.466 with CPU OpenCL.
- On an idle host, [start the stream](../../../scripts/ue/Start-YacsLesson05Stream.ps1)
  **without switches** to open the saved Lesson05 map without importing again.
  `-ImportLesson05` explicitly runs the bounded first-import bootstrap from L04.
  `-ImportLesson05 -RecoverBaseline` is only for a failed first attempt with a
  retained saved baseline; its full pre-import readback must still match L04.
  `-ImportLesson05 -RepairContext` is restricted to the recorded Context-only
  mismatch; it replaces that new Edit Layer and never reimports the detail tiles.
- [Bootstrap](../../../scripts/ue/bootstrap_lesson05_import.py) pauses at baseline,
  after, and reopened. For each completed native export, run
  [height/seam verification](../../../scripts/houdini/verify_lesson04_ue_readback.py)
  using `--export-root` and `--transfer-root`; baseline uses the L04 transfer,
  the other two use L05. Context-only recovery uses `transfer-before-context`
  for its mixed-state baseline. Only MATCH advances the next stage.
- [Consumer verification](../../../scripts/houdini/verify_lesson05_consumer.py)
  takes `--root` and `--proof` and checks full visibility retention, UV/material
  readback, RGB seams and the source map hash.

Retained work: `D:/yacs/work/lesson05-ue-20261018`; successful proof:
`proof-context`. Large map packages, images and caches remain local under the
existing source-retention policy. Git preserves the scripts and compact proof.
Owner visual acceptance remains pending the final M3 audit; performance is
`DEFERRED_AFTER_M3`. PR #474 remains Draft and is not merged.

## Saved-map stream recovery — 2026-10-18

The CUDA profile froze shortly after a second viewer joined: NVENC 20 preceded
CUDA 700 and repeated external-memory import failures. This is a measured
sequence, not proof of the underlying NVIDIA driver defect. The owner approved
a restart without import. The saved Lesson05 map hash stayed identical.

The launcher now retains H.264 NVENC/D3D12 with
`-AVCodecs.NvEnc.D3D12UsesCUDA=false`, CBR, and fixed 12,000,000 bit/s encoder
and WebRTC min/start/max bitrates. This local/LAN candidate avoids the failing
CUDA interop path and limits bitrate reconfiguration; fixed bitrate is not a
recommendation for constrained Internet links. Epic's
[driver issue discussion](https://github.com/EpicGames/PixelStreamingInfrastructure/issues/900)
reports a D3D12 reconfiguration leak and caveats for the CUDA workaround.

[Runtime receipt](lesson05-stream-recovery-20261018.json) records a concurrent
isolated second client decoding 16 then 44 frames, cleanup of that client,
and zero CUDA 700/NVENC 20 matches in the sampled replacement log. UE remained
running. Process private memory increased from approximately 17.0 to 18.4 GB
across the observations, which include startup and camera movement. The leak
is **not proven resolved**, and long-duration stability is **not proven**.
`t.MaxFPS 30` caps the engine; the inherited `WebRTCMaxFps` argument was not
confirmed applied (the observed WebRTC property remained 60). Do not infer a
30 FPS receiver guarantee from the launch arguments.

For the next startup on an idle host, run
`scripts/ue/Start-YacsLesson05Stream.ps1` without import switches. Optional
`-ScreeCloseup` invokes the [camera-only script](../../../scripts/ue/show_lesson05_scree.py),
which rejects the wrong map and does not cook, import, or save packages. It
uses an explicit named pitch/yaw/roll and a native scree-mask sample. The first
camera attempt had incorrect positional Rotator arguments and was corrected;
the streamed framing still needed manual adjustment, accepted by the owner.
This optional preset is not proof of the final displayed camera position.
The saved consumer contains Forge-derived baked global colour, not independently
bound full Forge PBR channels. No terrain source, checkpoint or geometry was
changed during this recovery. No merge; leave the active stream running.
