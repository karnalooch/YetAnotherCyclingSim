# SideFX Labs 22.0.466: source review and adoption boundary

**Status:** user-supplied source package inspected as data; runtime installation and node-definition/cook admission **NOT RUN**.
**Reviewed:** 2026-10-17 for the [Sa Calobra build guide](SA_CALOBRA_BUILD_GUIDE.md), under the [SideFX workflow](README.md).
**Purpose:** retain a small, reproducible source reference and useful tool selection, not vendor the distribution or duplicate the Pegasus catalog.

## Supplied source identity

- Archive: `sidefx_packages.7z`, **222,002,321 bytes**.
- Archive SHA-256: `2b9bf7864ee874065be506a0cfcd1cd96fe6351f28a212bab5c3f91c12afab29`.
- Inventory: **2,728 regular files**, **532 directories**, **431,181,635 uncompressed file bytes**; 25 regular files are empty. Inventory and extraction were checked without executing supplied Python, plugins, HIP files or HDAs.
- Roots: `SideFXLabs22.0.json` and `SideFXLabs22.0/`. The descriptor declares version **22.0.466**, enables Houdini `>= 22.0` and `< 22.1`, and uses `load_package_once: true`.
- `SIDEFXLABS` is defined relative to the package descriptor directory as `$HOUDINI_PACKAGE_PATH/SideFXLabs22.0`; `hpath` includes the common root and the relevant platform-specific directory. `OPlibraries` points at `otls/SideFX_Labs.hda`.

This is a user-supplied snapshot declaring that version, not an independently authenticated upstream release/tag. The archive was fully inventoried and its regular files hashed; selected help summaries, descriptor, installation, lifecycle and Unreal package files were read. There is no claim of semantic review of every script, HDA section or binary. The main HDA was hashed, not loaded or enumerated through Houdini.

The archive is **not** the Pegasus lesson/project corpus and contains no completed YACS terrain. Keep its locator separate from `YACS_SIDEFX_CORPUS` and `YACS_SIDEFX_TALKS`. The actual persistent host location is **not verified** in this review. Resolve the retained original by its name/hash and record the host path before reuse; a chat sandbox path is not a durable project dependency.

## Minimal source pins

Paths below are relative to the extracted archive root. These pins identify the reviewed snapshot, not a permission to execute it.

| Path | Bytes | SHA-256 |
|---|---:|---|
| `SideFXLabs22.0.json` | 594 | `7f6fa2f49f92c8fd95830d1f9fc136a2f15c0fe36e7cf08df87e651d7c4968a9` |
| `SideFXLabs22.0/otls/SideFX_Labs.hda` | 69102251 | `0519d64e0872af422a6d97717e3efc7ba4b96268694f6325becdd48f7a606610` |
| `SideFXLabs22.0/OPlibraries` | 21 | `07eab822dc2ccb3d07440b1bd12c174eb8e6c3d79c82edcf081ab34c032b7332` |
| `SideFXLabs22.0/OPcustomize` | 17050 | `4a6293f076d7c8e81ad52dad6b14d6a2ba5a0b79d85dff5dacfba955716594b5` |
| `SideFXLabs22.0/LICENSE.md` | 1280 | `c5f125b234c006c9be44f7bb6add262ce8a806d38e788beb6a7064c915778f5c` |
| `SideFXLabs22.0/docs/installation.md` | 9489 | `01f8c7dd326ada629c39018fea8d241b0cd992a006f136bf68210734f8762b1d` |
| `SideFXLabs22.0/unreal/5.8/README.md` | 3322 | `3e3ee2f98a4ea46d4adcdac30a4250b1d16d38d8e85192fca52301088f251550` |
| `SideFXLabs22.0/unreal/5.8/SideFX_Labs/SideFX_Labs.uplugin` | 742 | `aa971b12cfab8ffc7befc5e635d52a1efeb7187b169411d373bc787b4ff3470f` |

## Read the appropriate bundled help before using a tool

Paths in this table are relative to `SideFXLabs22.0/help/nodes/sop/`. The exact installed type/version must still be resolved from the actual HDA; a help filename or header may be historical or inconsistent.

| Bundled help | Intended consultation | Boundary |
|---|---|---|
| `labs--hf_combine_masks.txt` | Blend named HeightField layers | Current mask work; check grid registration and clamp/exclusion semantics |
| `labs--hf_insert_mask.txt` | Insert a layer from a second HeightField | Current mask work; copying is not proof of coordinate equality |
| `labs--terrain_analysis-1.0.txt` | Slope/cost/avoidance diagnostics | Optional analysis, not road routing authority |
| `labs--terrain_segment-1.0.txt` | Terrain Mesh ROP, tiled/adaptive mesh output | Optional representation; not a substitute cliff generator |
| `labs--terrain_texture-1.0.txt` | Terrain Texture ROP and matching tiled images | Explicit output need only; preserve spatial/normal conventions |
| `labs--terrain_layer_import.txt`, `labs--terrain_layer_export.txt` | File-based Unreal terrain/layer interchange | Optional alternative; verify orientation and remapping, not automatic extra conversion |
| `labs--road_generator.txt` | Road geometry from curves and intersections | Later road stage; prove suitability for real hairpins/profile/earthworks |
| `labs--unreal_spline-1.0.txt` | Spline JSON exchange including transforms/tangents/roll/tags | Later integration; requires relevant Unreal content utilities |
| `labs--biome_region_assign-1.2.txt` | Region definitions from layers, curves, images or attributes | Later vegetation stage; source-led domains, not arbitrary biome invention |
| `labs--biome_attributes_to_terrain-1.1.txt` | Assign biome attributes to terrain | Later; default climate/soil values are not measured Sa Calobra data |
| `labs--biome_plant_define-1.3.txt`, `labs--biome_plant_scatter-1.3.txt` | Plant definitions and condition-driven scatter | Later; explicit exclusions, source-appropriate plants and deterministic settings |
| `labs--autouv-1.0.txt`, `labs--lod_create-2.0.txt` | UV and LOD preparation | Later scoped assets; inspect internal dependencies and output quality |
| `labs--maps_baker-5.0.txt` | Understand retained older bake recipes | Deprecated reference, not the default for new baking work |

## Specific traps found in this snapshot

**Historical biome nodes.** `OPcustomize` hides `labs::biome_initialize::1.0`, `labs::biome_profile::1.0` and `labs::biome_curve_setup::1.0`, identifying replacement families Region Assign, Define/Definitions File and Curve Label. Their help files still exist. Do not make the old Biome Initialize chain mandatory simply because it is in the archive. The old initialize help also has an inconsistent internal-type spelling; inspect actual node definitions rather than copying that spelling into automation.

**Deprecated baker.** The bundled Maps Baker 5.0 help and [current official documentation](https://www.sidefx.com/docs/houdini/nodes/sop/labs--maps_baker-5.0.html) identify Bake Geometry Textures COP and Karma Texture Baker LOP as replacements and state planned removal in Houdini 23.0. Prefer investigating those supported alternatives for new baking work; preserve old reproducible recipes and record any migration. This does not authorize replacing Material Forge wholesale.

**Mixed engine/platform payloads.** The archive contains UE 5.7 Labs DLLs and an old inline-C++ cache DLL; these are not evidence of UE 5.8 compatibility. Its UE 5.8 README describes main and Legacy content packages sharing `/SideFX_Labs`, which must not be installed together. The main UE 5.8 descriptor has built-in PCG/Python/editor-utility dependencies and no custom module list. This is distinct from the Houdini Engine plugin. Inspect the selected descriptor and dependency closure before any installation; never copy all bundled plugins or binary caches into YACS.

**Source remnants and missing optional payloads.** Several platform-specific external-remesher ZIP entries are empty. Empty files, old binaries and optional integrations do not become complete dependencies merely because extraction succeeded. No Gaea, RizomUV, QuadRemesher, ML, VAT or similar integration is approved as a new mandatory dependency by this review.

**Sample plants are not local evidence.** Bundled sample geometry includes many unrelated plant families. Use tool methods, not the entire sample library as the Sa Calobra vegetation palette. Source-appropriate species/domain decisions remain separate.

## Package verification for a future authorized host session

Use the existing package mechanism and a pinned retained snapshot, not an automatic latest/daily upgrade. Keep the descriptor and its relative content root consistent when locating or moving the package. Prefer the established D: tool/workspace roots and avoid installing another copy just because the current process has not been inspected.

[SideFX package documentation](https://www.sidefx.com/docs/houdini/ref/plugins.html) defines search order, version expressions, `hpath` and load-once behavior. `load_package_once` concerns the first matching package filename; it does not guarantee that the intended version wins over every differently named or manually loaded definition. The bundled installation guide still contains 21.0 example commands, so those examples must not override the actual 22.0.466 descriptor.

For the actual launch environment, record the resolved package path, Houdini/Labs versions, `SIDEFXLABS` value, load warnings and the selected node type/definition file. SideFX's Package Browser or `HOUDINI_PACKAGE_VERBOSE=1` with `hconfig -xa` can help inspect resolution; this review did not execute them. GUI, hython and service launches must not be assumed to share package resolution. Keep source hashes and verify a minimal cook plus fresh reopen before claiming YACS compatibility.

Do not modify shared `DefaultEngine.ini` to prove package availability. Follow the existing [Unreal configuration boundary](UNREAL_CONFIGURATION.md); applying a Houdini package and applying an Unreal/HAPI launch profile are different operations.

## Retention and adoption

Preserve the archive, original notices and dependencies outside Git. `LICENSE.md` and nested third-party notices are part of the source record; this review does not certify all bundled content for unrestricted redistribution. The product repository receives only authored guidance and these compact pins. Do not copy all help text, source assets, compiled modules, build caches or installation output into the PR.

At adoption: **inventory/hash review complete; selected documentation reviewed; host package resolution, HDA definition inspection, cooking, Unreal plugin installation and native runtime acceptance NOT RUN**. No world data or active scene changed. This source inventory complements the existing [recipe template](RECIPE_TEMPLATE.md) and [JSON storage contract](../../evidence/JSON_STORAGE.md), not a new proof framework.
