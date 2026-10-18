# Lesson05: full Landscape scree and grading

Owner-directed full-grid execution, 2026-10-18, issue #365 / PR #474. No merge.
This supersedes the earlier small-patch-only execution scope in the
[plan](LESSON05_SCREE_PLAN.md). Original L03/L04 checkpoints and source data remain
inputs. Native authoring, Unreal admission and owner visual acceptance are
separate states; see the [measurement receipt](lesson05-full-landscape-20261018.json).

**Completed:** full Working and Context authoring, saved HIP, fresh-process
full-grid tail rebuild and all-sample height/colour comparison. **Not run:**
Lesson05 UE import/reopen and owner visual acceptance.

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
   `--adapter-root`, `--area working|context`, and `--stage` in this order:
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
| Resolution | 7154 � 9829 | 2048 � 2048 |
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
emit ID-layer menu errors during HIP save; those retained later-lesson menus
are not the Lesson05 output and are not claimed as repaired.

## Consumer and acceptance boundaries

The running UE session is the repaired Lesson04 map, preserved with H.264 NVENC
and the CUDA workaround. No restart, map replacement, source asset edit or merge
is implied by native Houdini completion. Full Lesson05 UE import, native seam
readback, fresh UE reopen, matched-camera review and owner acceptance must be
reported separately. They cannot inherit Lesson04 PASS results.
