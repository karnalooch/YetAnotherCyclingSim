# Lesson05 plan: Sa Calobra scree with Material Forge

**Status:** PLAN with execution progress tracked below. Prepared 2026-10-18.

**Owner scope update, 2026-10-18:** The owner explicitly requested the complete lesson on the full Landscape, superseding the small-patch-only execution scope. [Full native execution and fresh-rebuild measurements](LESSON05_FULL_LANDSCAPE.md) are now recorded; UE import and visual acceptance remain separate.

**Earlier execution update, 2026-10-18:** [Precheck and Material Forge preparation](LESSON05_MATERIAL_PREPARATION.md) completed with two matching native map renders. Houdini adapter calibration, scree placement, Lesson05 checkpoint and UE import remain NOT RUN.

**Delivery:** [PR #474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474), `codex/365-world-graph`; no merge.

**Inspected baseline:** `3c6897aaa31c093d9e4b2fa8ca5125344c98b5f7`, including the saved CUDA/NVENC stream workaround. Recheck HEAD and host state before execution.

The next authoring pass adds scree below cliffs and in terrain pockets, with restrained limestone/soil colour variation. Preserve Sa Calobra's real macro relief. Houdini/Pegasus owns spatial masks and measured procedural detail; Material Forge supplies surface appearance, as requested by the owner. This plan does not execute Lesson05 or grant production acceptance.

Authority: the [Sa Calobra build guide](SA_CALOBRA_BUILD_GUIDE.md), [SideFX workflow](README.md), [World Building Bible](../../WORLD_BUILDING_BIBLE.md), [Material Forge contract](../MATERIAL_FORGE.md) and [host policy](../../ai/policies/M3_WORLD_OPERATIONS.md). Historical PCG-first ownership wording in Forge's tool README/agent contract is superseded by the current Houdini-first authority; retain Forge's validation contracts.

## 1. Resume inputs and source provenance

Start from the saved [Lesson04 repair](LESSON04_UNREAL_REPAIR.md), not an older review map or a rebuilt DTM. Its measurement receipt is a Lesson04 baseline, not evidence for Lesson05.

| Input | Verified baseline / locator |
|---|---|
| Houdini / Unreal | Houdini and Houdini Engine 22.0.466; UE 5.8.2 CL56702186 |
| Working HIP | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson04.hiplc` |
| HIP SHA-256 | `6d5419191083ed32a79e4fb1668a1476cdf49b38bdc27d3b869424959793d098` |
| Houdini working grid | 7,154 x 9,829 samples, 0.5 m spacing; 70,316,666 samples |
| Saved repaired UE map | `/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test` |
| UE detail / Context | Four 3,811 x 5,081 detail tiles; 2,017 x 2,017 Context; distinct from the Houdini source grid |
| Shared UE height transform | `Scale.Z=585.9375`, actor Z origin 0; verify suitability for the new output |
| Controlled visual baseline | Saved test-map sun intensity 3.9; retain camera, exposure and light for A/B comparisons |

The Lesson04 HIP was inspected in manual-update mode without cooking or saving. Existing nodes under `/obj/SA_CALOBRA/` include:

- `WORKING_MASK_CLIFF`: native `heightfield_maskbyfeature`, input `COMPOSE_SOURCE_AND_MANUAL`, current slope range 28-90 degrees. Preserve it; it is not automatically the correct scree-source mask.
- `WORKING_CLIFF_MATERIAL`: `PE_heightfield_material::1.0`, inputs `WORKING_HEIGHTFIELD_TINT` and `WORKING_MASK_CLIFF`; current material size 20 and height scale 0.35. These are inspected Lesson04 settings, not Lesson05 defaults.
- `WORKING_HEIGHTFIELD_TINT`: existing colour treatments after `WORKING_SAND_MATERIAL`. Inspect their effective ramps before adding another tint to avoid applying the same correction twice.

Official lesson: **PEG-02-05, 5 | Scree Slopes, 17:19**, in [Project Pegasus Landscape Workflow](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/); [video](https://player.vimeo.com/video/888568753). The complete retained transcript was read for this plan. Resolve originals through `YACS_SIDEFX_CORPUS`, following the [corpus locator contract](README.md#source-corpus-and-portable-references); this environment variable must be configured on the execution host.

- Transcript: `P1_02_Landscape_Workflow/Czesci/05_5_Scree_Slopes/Transkrypcja.en.txt`; VTT in the same directory.
- VTT SHA-256: `d72a5b91f2d7b5a10600cb18d2650fdbe145d59db53c5a804a61dc09443062d7`.
- Original project root: `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini`.
- Original `Landscape_Workflow_01_Overview.hip` SHA-256: `149878bf5e4895ed76f2ec5b84af0c00d03065398f551176154603282189de6b`. It is an overview input, not a verified completed Lesson05 graph.

Original definitions, inspected without cooking, reside under that project root's `Packages/PegasusDemo/otls`:

| File | Resolved type | SHA-256 |
|---|---|---|
| `sop_PE_heightfield_layerslump.hda` | `PE_heightfield_layerslump` | `7d6fdfa34a3794ad320cf7593966b68caeb64d243309d8d422babcb7cfe057b4` |
| `sop_PE_heightfield_material.1.0.hda` | `PE_heightfield_material::1.0` | `e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023` |
| `sop_PE_heightfield_tint.1.0.hda` | `PE_heightfield_tint::1.0` | `93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed` |

Revalidate actual loaded definitions and dependencies. Keep original HIP/HDA files and full transcripts outside Git. Consult the [reviewed Labs package](SIDEFX_LABS_22_0_466.md) before introducing any additional operation.

## 2. Lesson-to-execution sequence

Tutorial numbers below describe the demonstration. They are starting experiments only where explicitly identified, never accepted Sa Calobra parameters.

| Lesson time | Original operation | Planned Sa Calobra execution |
|---|---|---|
| 00:00-00:20 | Gravel textures and a new HeightField material | Adapt the surface input to one versioned Material Forge limestone-scree candidate |
| 00:20-02:07 | Cliff-source mask through HeightField Slump | Transport a separate scree mask downhill; tune iterations/repose while preserving height |
| 02:22-03:10 | HeightField Remap | Measure actual mask range, then remap to 0-1; demonstration 0-8 is not a fixed input range |
| 03:10-04:57 | Layer slump and local occlusion | Generate pocket influence with Mask by Feature / Occlusion and an inspected ramp |
| 04:57-06:38 | Copy to `pockets`, connect layer slump, correct direction | Left input: scree mask; right: pocket field. Layer to slump: `mask`; influence: `pockets`. Verify downhill/pocket direction; author inverts at 05:58 |
| 06:39-07:58 | Remap and tune sparse distribution | Record final ramp, iterations, repose and coverage; retain irregularity |
| 08:00-09:20 | Optional dedicated slope source with falloff | Use a new source mask if needed; do not retune the accepted cliff material mask |
| 09:20-10:38 | Separate cliff and gravel tint | Preserve independent strength/bypass and avoid duplicating Lesson04 tint |
| 10:38-14:10 | Broad occlusion grading | Subtle, inspectable colour modulation; no strong baked shadow in albedo |
| 14:10-15:19 | Curvature brightness | Tune independently; demonstration ramp 1-2 is not a production default |
| 15:19-17:19 | Global colour/masks and neutral inspection | Compare geometry without tint, final colour, masks and separate height deltas |

Native references: [HeightField Slump](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_slump.html), [HeightField Mask by Feature](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyfeature.html), [HeightField Remap](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_remap.html). Verify bindings and parameter names in installed 22.0.466. IDMap and the full Unreal material workflow belong to later lessons 6-7; roads, vegetation and separate rock meshes are outside this pass.

## 3. Preflight and checkpoint

1. Recheck branch/HEAD, local changes, tool versions, source hashes and host ownership. Verify real received H.264 frames, UE process commit/private memory and system commit headroom before adding work.
2. Reuse the active owner session. Serialize GPU/native operations through existing host arbitration. Do not launch a second editor or stop the stream to obtain access.
3. Preserve original DTM, L03/L04 HIPs, Source/Manual/Procedural caches, prior maps and configuration. Save As a new `SaCalobra_Pegasus_Lesson05.hiplc` with a distinct versioned cache directory; do not overwrite accepted outputs.
4. Load verified Lesson04 caches. Confirm origin, spacing, orientation, CRS, validity/NoData and allowed working area. Record actual dependencies and output paths using the existing [recipe template](RECIPE_TEMPLATE.md).

Checkpoint A: reproducible Lesson04 input with hashes, plus a separate Lesson05 working copy. No full base rebuild.

## 4. One Material Forge scree candidate

Inspect `regional_limestone` and `mediterranean_soil/stony` from the [family catalog](../../../worldgen/materials/material_forge/families.json) at their physical scale. `stony` is an available candidate input, not an already accepted scree material. Create one versioned limestone-scree variant within the existing pipeline: irregular angular fragments, mineral fines, matte grey/beige. Preserve prior accepted variants and seeds. Asphalt is out of scope.

Use the existing [Forge instructions](../../../tools/material-forge/README.md) and [SSOT](../MATERIAL_FORGE.md):

1. Author into a fresh run directory with `tools/material-forge/material-forge.ps1 author --material-maker <reviewed-install> --output <fresh-run>`. Record the catalog variant, seed, resolution and physical tile size explicitly; current catalog baseline is 2,048 px and 4 m.
2. Verify Material Maker source commit `4d29a815489866aae483281cf44b2cfe48d3cc3e` and Godot 4.7.2. The inspected host source locator was `D:/yacs/research/material-maker-20261005`; reverify its revision before use. The Material Maker 1.7 install supplies reviewed authoring inputs, not the render runtime.
3. Prime source caches with `Godot --headless --path <source> --import`; require `.godot/global_script_class_cache.cfg` and imported resources. Use `scripts/assets/render_material_forge.py --godot <godot> --source <source> --variant <variant-directory>` for native rendering.
4. Run existing `validate-run <run-directory>` and `compare --left <run-a/run-manifest.json> --right <run-b/run-manifest.json>` commands through `material-forge.ps1`. Require two runs, exact graph/output hashes and native Godot decode receipts. Do not use the rejected Material Maker release `--export-material` path, which previously failed with `0xC0000005`.

| Output | Pegasus/UE handling |
|---|---|
| BaseColor | sRGB source; verify the HDA's colour-space conversion before grading |
| Normal_DX | Preserve DirectX convention for later UE microdetail; do not convert it into terrain height |
| ORM | R=AO, G=Roughness, B=Metallic; use G for the HDA roughness input; metallic must remain zero |
| Height EXR | Authoring/inspection data; measure range and neutral value, then calibrate original HDA height scale on a small patch; never import raw EXR as Landscape height |
| DetailMasks | Material-local semantics only; do not use Forge to classify or place scree in the world |

Validate dimensions, tiling continuity, nonblank signals, normal vectors, metallic and exact-byte decode evidence with existing gates. Set physical texture size explicitly. A 0.5 m terrain grid cannot represent centimetre stones as geometry; retain those signals for normal/material detail. No accepted Height-to-metres conversion exists yet for this new candidate.

Checkpoint B: one validated surface variant, provenance and adapter settings; owner visual review remains separate from numerical validation.

## 5. Small Houdini prototype before full Working

Use an approximately 300 x 300 m representative patch plus a halo. Expand the halo until the central result converges; edge accumulation in a crop is not a valid terrain result.

1. Derive a separate rock-source/slope mask. Feed native HeightField Slump, starting with low iterations and tuning repose. Inspect bindings and disable unintended bedrock erosion or sediment addition to `height`. **At the mask-only stage, height difference from the input must be exactly zero.**
2. Measure the resulting mask range and remap to 0-1. Record min/max, coverage and effective parameters; do not copy the tutorial's 0-8 range blindly.
3. Generate local pockets via Mask by Feature / Occlusion. Copy/rename the influence to `pockets` and use original `PE_heightfield_layerslump` with the input/layer bindings in section 2. Confirm accumulation in depressions rather than on peaks. Tutorial View Distance 5 at approximately 06:33 is an experiment, not an approved world-scale setting.
4. Remap again, then apply hard exclusions after transport/remapping: NoData, water and areas outside the allowed Working support. Verify Working/Context registration and zero contribution outside the allowed mask.
5. Apply `PE_heightfield_material::1.0` with the validated Forge adapter. First run a zero-additional-height control. Then tune a separate reversible Lesson05 contribution while preserving macro relief. Record `delta_L05 = final_L05 - final_L04` and total procedural delta relative to `Source + Manual`; the historical proposed 0.5 m bound is not a permanent specification.
6. Apply independent cliff/scree tint, occlusion and curvature controls using `PE_heightfield_tint::1.0`. Give every added treatment a strength/bypass. Inspect existing Lesson04 grading; verify sRGB/linear handling and UV orientation before compensating with darker colours. Keep global colour and masks separate.

Review three sites: a steep cliff/base, a soil pocket and a Working/Context or coast boundary. For each, retain mask, neutral geometry without tint, final colour and delta A/B at identical camera/light/exposure (sun 3.9 baseline). Street View is a visual reference, not height ground truth or a texture source.

Checkpoint C: small-patch mask and height/colour behaviour accepted for scaling, with effective ramps/parameters recorded. Do not hide a failed geometry or registration check with material changes.

## 6. Full Working and fresh Houdini reopen

Recompute only the changed dependency branch on the continuous Working grid. Do not compute each UE tile's transport mask independently without converged padding. Retain Context as a baseline; any colour transition adjustment is a separately checked change. Do not recook all background at 0.5 m on every iteration.

Save masks, raw Lesson05 delta, final heights/colour, effective parameters, seed and cache hashes. Record:

- Dimensions, origin, spacing, orientation, CRS and source-validity identity.
- Signed min/max/mean and p95 of absolute height change, changed-sample count and outside-mask maximum/count for both the Lesson05 increment and total procedural result.
- Zero unexpected changes outside the permitted support, no NaN/Inf, valid mask ranges and preserved macro relief.
- Invalidation inputs and exact identities of reused versus newly generated caches.

Save the separate Lesson05 checkpoint. Reopen it in a fresh Houdini process, read caches and rebuild a selected small graph patch to detect stale caches and missing dependencies. Record hashes and differences; a successful file-open alone is insufficient.

Checkpoint D: reproducible full-area Houdini result and fresh-process evidence, still separate from Unreal verification.

## 7. Isolated Unreal consumer and encoding

Create a separate Lesson05 derivative map, retaining the repaired Lesson04 map as the fallback. Current [apply](../../../scripts/ue/apply_lesson04_ue_repair.py) and [readback](../../../scripts/ue/export_lesson04_ue_readback.py) scripts intentionally guard the Lesson04 target. Add an explicit narrow Lesson05 target/manifest before reuse; do not disable allowlists or accept arbitrary maps.

Use original Houdini Engine `output_mode=1` to modify the intended Edit Layer on an existing derivative Landscape; use `output_mode=0` only when creating a new Landscape. Keep absolute `Source + Manual`, total procedural contribution and the incremental Lesson05 contribution distinct.

Reuse the measured [height encoding](../../../scripts/houdini/lesson04_height_encoding.py) after checking the new range. Do not add absolute `final_L05` as a delta, or independently round multiple deltas and assume they reproduce the quantized final target. For unchanged transform, the existing composition uses `q_base = round(base_m * 12800 / Scale.Z) + 32768` and `q_detail = 32768 + q_final - q_base`, plus the verified H22 transport-centre handling. If keeping a separate L05 layer, derive its encoded increment from final quantized codes and verify native composition, rather than assuming float-delta import is equivalent.

Check that both absolute heights and signed encoded deltas fit before retaining `Scale.Z=585.9375`. If the range changes, recompute the shared transform and dependent base/detail encodings consistently across all tiles. Do not silently clamp or normalize per tile.

| Check | Required evidence for Lesson05 |
|---|---|
| Full height readback | Every native code versus the expected final code; current layout totals 81,523,053 samples including duplicate tile edges, distinct from 70,316,666 source samples |
| Height error | At unchanged range, encoding half-step bound approximately 0.022888184 m; report actual maximum/mean and mismatches, including any adapter bias calibration |
| Shared edges | All four full shared detail edges; target 0 m difference |
| Working / Context | Native visibility mask plus runtime traces identifying hit actors; no Context overlap/Z-fighting in the detail interior |
| Colour | Correct UV V, sRGB/linear handling, registration and matched-light A/B; do not claim exact colourimetric equivalence from a screenshot |
| Persistence | Save and freshly reopen the derivative map; remeasure heights/seams/visibility and inspect colour |
| UE Remote | Real decoded H.264 frames and camera input on the saved candidate; three A/B sites plus panorama; process/system memory trend |

Checkpoint E: measured native import and persistence, then owner visual review. Existing Lesson04 PASS results cannot substitute for any Lesson05 row.

## 8. Stream continuity and next-session entry point

The [saved stream repair receipt](lesson04-stream-stability-20261018.json) records the bounded stability observation. It is not an overnight guarantee. Preserve `-AVCodecs.NvEnc.D3D12UsesCUDA=true` and H.264/NVENC in the running session and any later authorized startup; verify frames as well as memory.

If the host is idle and the saved Lesson04 map is needed as the starting point, the committed launcher is [Start-YacsLesson04RepairStream.ps1](../../../scripts/ue/Start-YacsLesson04RepairStream.ps1). From the repository root, in PowerShell 7.4 or later:

```powershell
./scripts/ue/Start-YacsLesson04RepairStream.ps1 -WhatIf
# Only when a new startup is needed and the host is idle:
./scripts/ue/Start-YacsLesson04RepairStream.ps1
```

The launcher refuses an occupied host/stream ports and starts the saved **Lesson04** map; it does not generate or select Lesson05. Viewer: `http://127.0.0.1/?AutoConnect=true&AutoPlayVideo=true`. Reuse an already running stream. Coordinate an eventual map switch or fresh-process verification with its owner; do not restart automatically for test convenience or run a competing GPU job.

## 9. Stop conditions and completion

Stop the dependent stage for a missing original HDA/input, unverified Forge height scale, wrong mask registration/gamma/UV, unintended macro-height change, out-of-area detail, failed small-patch test, nonzero seams, Context overlap, native readback mismatch or failed fresh reopen. Host memory growth, insufficient commit headroom or conflicting GPU ownership also blocks further heavy work. Record the exact failure and preserve evidence; do not generate replacement terrain to conceal it.

Completion requires a reproducible Lesson05 checkpoint, scree mask, one Forge variant with all maps/hashes, separated measured height contribution, full native measurements, fresh Houdini/UE reopen and an operating viewer with explicit owner review. Record actual implementation status and remaining gaps using the existing recipe/proof system; do not introduce another proof framework.

Deliver scoped code/adapters, parameters, documentation and compact receipts on existing PR #474. Heavy HIPs, caches, source distributions and rendered images remain outside Git at recorded workspace locations. Update the build guide and lesson concordance only to the evidence level actually achieved. **No merge. The original planning revision performed no Lesson05 authoring/render/import; consult the execution update above for subsequent bounded progress.**
