# Lesson05 material preparation — 2026-10-18

**Status:** native Forge maps validated; Houdini material adapter calibration, scree placement and UE import NOT RUN. This is the first bounded execution step of the [Lesson05 plan](LESSON05_SCREE_PLAN.md), on PR #474. It does not complete Lesson05 or claim owner visual acceptance.

## Precheck and stream

The starting local and remote revision was `7401f69019c796abc493349d410735fe71d45cec` on `codex/365-world-graph`. Tracked files were clean; unrelated untracked scripts and generated UE content were retained. Unreal was absent at precheck; the owner confirmed a computer reboot and explicitly requested startup. The committed Lesson04 launcher started PID 24432 at 08:17:54 Europe/Warsaw with H.264 and `-AVCodecs.NvEnc.D3D12UsesCUDA=true`. The browser showed the repaired map, and the owner confirmed it worked. Computer Use stopped at the owner's request; subsequent verification used process/log/port observations only.

UE remained running throughout the serial material renders. At 08:29:08, the same PID owned ports 80/8888, private memory was 15,507,234,816 bytes, available physical memory was 7,150 MiB, and system committed bytes were 40,547,188,736 against a 107,675,762,688 limit. This is a bounded continuity observation, not overnight or performance admission.

Read-only Houdini 22.0.466 inspection confirmed:

- Lesson04 HIP SHA-256 remains `6d5419191083ed32a79e4fb1668a1476cdf49b38bdc27d3b869424959793d098`.
- All ten retained source/manual/final/context/transfer input hashes match the Lesson04 repair manifest.
- Native source `height`, `mask` and `Alpha` volumes remain registered at 7,154 x 9,829 x 1, origin sample `[-1771.25, 0, 3144.25]`, X step `[0.5, 0, 0]`, second grid-axis step `[0, 0, -0.5]`.
- No HIP was opened/saved, graph cooked, Landscape changed or Lesson05 checkpoint created. Save As and the small Houdini prototype remain the next terrain-authoring step.

## Material candidate and reuse

The new catalog entry is `mediterranean_soil/limestone_scree_v1`: seed 547, physical tile 4 m, five 2,048 x 2,048 maps. It reuses Forge's existing periodic polygon-grain helpers, native Material Maker graph/PBR output and pinned render adapter. The existing soil field produces rounded pebbles; the new variant uses two angular fragment populations with 148 mm and 48 mm mean cell pitch, bevels/facets, mineral variation and fine surface grain. These are artistic candidate parameters, not a geological measurement or SideFX defaults. Surface fields do not classify or place scree on the Landscape.

The first flat-topped probe remains in the local `candidate-a` directory. The retained `run-a`/`run-b` candidate adds facet relief and material grain and treats both fragment populations as mineral surfaces. No previous accepted variant or seed was edited. Reauthoring all 16 historical variants produced identical graph bytes before and after this change.

Material Maker source revision: `4d29a815489866aae483281cf44b2cfe48d3cc3e`; native Godot: 4.7.2 `ed1daf0bf001b61586d9930840f2f1394092c079`. The retained source's tracked differences were import metadata (`.import` files), not source code. Its primed script-class cache and tool hashes are recorded in the receipt. No release CLI fallback was used.

| Measurement | Native candidate result |
|---|---|
| Graph SHA-256 | `36c05727c7f7013ee7d70097705fe65fa2f4ef14244fce6fbc63549d9a465e2f` |
| Two-run graph/fingerprint/map comparison | Deterministic, zero mismatches |
| Five maps | Native Godot decode and exact-byte receipt PASS for BaseColor, Normal_DX, ORM, Height EXR and DetailMasks |
| Existing map QA | Dimensions, wrap continuity, nonblank signals, DirectX normal vectors, zero metallic PASS |
| Roughness range | 0.8509804-0.9019608 |
| Metallic maximum | 0 |
| Coarse / fine coverage above 0.5 | 32.6133% / 15.5426%, material-local masks only |
| Height EXR range | 0.464599609375-0.61376953125, all finite; authoring scalar, **not metres** |
| Height EXR mean / recipe neutral reference | 0.5048879675 / 0.47; the reference is not an accepted Houdini displacement zero |

DetailMasks are R=coarse fragment coverage, G=fine fragment coverage, B=mineral variation. BaseColor is sRGB; normals remain DirectX. Roughness must come from ORM G as non-colour data. The Forge Height EXR has no accepted Landscape-height conversion: test a zero-height material control and calibrate the original Pegasus HDA on a small patch before enabling any height contribution.

Native exports exited 0 and passed validation. Retained upstream logs still report Steam initialization diagnostics and six ObjectDB instances/one resource at shutdown. They are recorded, not described as a clean diagnostic log; neither render produced shader/export/decode failure. Albedo/normal maps were inspected directly. A neutral-lit reference, Houdini colour-space/height adapter proof and owner appearance acceptance remain pending. No claim of final photorealism follows from numerical map QA.

## Reproduction and next step

Host outputs remain under `D:/yacs/work/lesson05-material-forge-20261018`. Inputs are the reviewed Material Maker 1.7 installation, pinned source checkout and Godot executable described in the [Forge SSOT](../MATERIAL_FORGE.md). Use a fresh output directory:

```powershell
python scripts/assets/material_forge.py author `
  --material-maker D:/yacs/tool-cache/material-forge/material-maker-1.7/material_maker_1_7_windows `
  --output D:/yacs/work/lesson05-material-forge-20261018/new-run `
  --family mediterranean_soil --variant limestone_scree_v1

python scripts/assets/render_material_forge.py `
  --godot D:/yacs/tools/godot-4.7.2/Godot_v4.7.2-stable_win64.exe `
  --source D:/yacs/research/material-maker-20261005 `
  --variant D:/yacs/work/lesson05-material-forge-20261018/new-run/mediterranean_soil/limestone_scree_v1

python scripts/assets/material_forge.py validate-run D:/yacs/work/lesson05-material-forge-20261018/new-run
```

Repeat author/render/validate into another fresh directory, then use `material_forge.py compare --left <run-a/run-manifest.json> --right <run-b/run-manifest.json>`. The new paired `--family`/`--variant` selector narrows generation and the run manifest to exactly one catalog entry; invalid or incomplete selection fails before creating output. Omitting both keeps full-catalog behaviour.

The [compact receipt](lesson05-material-preparation-20261018.json) records source hashes, output identities, native precheck, validation, determinism and remaining gates. Raw logs, maps, generated graphs and caches stay outside Git. The next step is the separate Lesson05 HIP, original Pegasus material adapter calibration and a bounded scree-mask prototype; keep the active stream and repaired L04 map intact.

Validation: 43 CPU contract tests passed across Forge, Blender-reference admission and transfer admission. Native map proofs are separate from those CPU tests. No Unreal import, terrain alteration, Lesson05 fresh reopen, performance admission or merge occurred.
