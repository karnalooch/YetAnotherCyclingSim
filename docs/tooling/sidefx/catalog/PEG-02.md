# PEG-02: Project Pegasus | Landscape Workflow

[Official series](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/) · [Catalog](README.md) · [Workflow](../README.md)

Stage: **Layered terrain workflow, masks, trails and vegetation handoff**. Corpus folder: `P1_02_Landscape_Workflow`.

## Lesson concordance

All listed TXT/VTT files were read and the original VTT hashes checked. `INDEXED` means source availability and integrity, not semantic study or a successful Houdini cook. Paths below resolve relative to `YACS_SIDEFX_CORPUS`.

### PEG-02-00: Introduction [1:16]

[Original video](https://player.vimeo.com/video/888567542) · [Caption resource](https://captions.vimeo.com/captions/134174289.vtt)

- Language: `en`; source track: `en`; automatic: `false`.
- Text coverage: `00:00:00.366` → `00:01:16.099`; 36 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/00_Introduction/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/00_Introduction/Transkrypcja.en.vtt`
- Original VTT SHA-256: `d179378bb6502b56ac8546e3e02032a581b39a45b6880254794e5396a2b50733`
- Source lesson objective: A quick overview of each lesson and what you’ll be learning along the way.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-01: 1 | Preamble [1:19]

[Original video](https://player.vimeo.com/video/888567602) · [Caption resource](https://captions.vimeo.com/captions/120806445.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.485` → `00:01:19.185`; 41 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/01_1_Preamble/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/01_1_Preamble/Transkrypcja.en.vtt`
- Original VTT SHA-256: `295980e35dea4132b8b2b0bcd11b23286191f9dc30393e2b1c81220ae6f78907`
- Source lesson objective: Before getting underway, familiarise yourself with some other useful Project Pegasus learning content relevant to the landscape workflow.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-02: 2 | Pipeline Overview [19:02]

[Original video](https://player.vimeo.com/video/888567622) · [Caption resource](https://captions.vimeo.com/captions/120806871.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:03.515` → `00:19:01.445`; 397 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/02_2_Pipeline_Overview/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/02_2_Pipeline_Overview/Transkrypcja.en.vtt`
- Original VTT SHA-256: `7f55f991af4cc25989c179d13a9ef2407260a67bcf0700bb65b3eeaf69d982c3`
- Source lesson objective: Get an overview of the landscape pipeline and how the Pegasus team collaborated on building the landscape, layering procedural detail and manual edits.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `IMPLEMENTED_LOCAL_STAGE_CHECKPOINT`. Full landscape pipeline verification: `SaCalobra_Pegasus_Lesson02.hiplc` under `D:/yacs/work/sa-calobra-houdini-unreal-20261016`. Receipts: [sa-calobra-pegasus-lesson02-pipeline-verification.json](sa-calobra-pegasus-lesson02-pipeline-verification.json), [sa-calobra-pegasus-first-detail-verification.json](sa-calobra-pegasus-first-detail-verification.json) and [sa-calobra-pegasus-first-detail-readback.json](sa-calobra-pegasus-first-detail-readback.json). Full landscape (7,154 × 9,829 cells at 0.5 m spacing) three-layer pipeline established with original `PE_Load_Landscape::2` and `PE_Cache_Landscape`: Layer 1 `Source` (100% bit-exact DTM base) -> Layer 2 `Manual` (Unreal Edit Layer delta, neutral zero baseline, reversible sculpt verified) -> Layer 3 `Procedural` (detail delta). Bidirectional roundtrip verified in Houdini and mapped to Unreal native Landscape Edit Layers.
 
### PEG-02-03: 3 | Pegasus Heightfield Materials [9:47]
 
[Original video](https://player.vimeo.com/video/888568015) · [Caption resource](https://captions.vimeo.com/captions/120806878.vtt)
 
- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.555` → `00:09:26.225`; 186 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/03_3_Pegasus_Heightfield_Materials/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/03_3_Pegasus_Heightfield_Materials/Transkrypcja.en.vtt`
- Original VTT SHA-256: `2500bef6f0ba343b177ba8bd4fa66acf01ea20b81c53d095f6f20dd17d2bf99c`
- Source lesson objective: Learn how heightmaps from the Quixel Megascans were used to add a fine level of detail to the landscape.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `IMPLEMENTED_LOCAL_STAGE_CHECKPOINT`. HDA: `sop_PE_heightfield_material.1.0.hda`. Material 1 (Rock slope): 4K float displacement EXR `inputs/textures/wepoeaw_4K_Displacement.exr`, physical size 20.0 m, height scale 0.35 m, mask by slope 28° to 90°.
 
### PEG-02-04: 4 | Heightfield Materials Workflow [16:27]
 
[Original video](https://player.vimeo.com/video/888568278) · [Caption resource](https://captions.vimeo.com/captions/120807236.vtt)
 
- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.615` → `00:16:26.255`; 311 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/04_4_Heightfield_Materials_Workflow/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/04_4_Heightfield_Materials_Workflow/Transkrypcja.en.vtt`
- Original VTT SHA-256: `0a1b906617532bc3b9dc9daefca9cc6a12bf9632e515474de4684730a38c9ed6`
- Source lesson objective: Now that you have an understanding of the Heightfield Material workflow take a closer look at how you can build a detailed landscape by layering multiple Megascan textures using masks.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `IMPLEMENTED_LOCAL_STAGE_CHECKPOINT`. Material 2 (Ground transition): 4K float displacement EXR `inputs/textures/tlonbisya_4K_Displacement.exr`, physical size 12.0 m, height scale 0.15 m, mask by slope 0° to 32°, `use_heightblend = 1`. Subregion 300m x 300m verified with max delta 0.4833 m, mean delta 0.0473 m, 0.0 m outside boundary.

### PEG-02-05: 5 | Scree Slopes [17:19]

[Original video](https://player.vimeo.com/video/888568753) · [Caption resource](https://captions.vimeo.com/captions/120807320.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.630` → `00:17:18.825`; 314 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/05_5_Scree_Slopes/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/05_5_Scree_Slopes/Transkrypcja.en.vtt`
- Original VTT SHA-256: `d72a5b91f2d7b5a10600cb18d2650fdbe145d59db53c5a804a61dc09443062d7`
- Source lesson objective: Building on the previous lesson, learn how you can use some of the heightfield tools to build more complex and natural-looking masks to place detailed textures.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: [full Working/Context native execution, saved HIP and fresh rebuild](../LESSON05_FULL_LANDSCAPE.md); Earlier UE import is separately recorded there; the corrected masked-tint HIP is local only and owner visual acceptance remains pending.

### PEG-02-06: 6 | IDmap Workflow [17:30]

[Original video](https://player.vimeo.com/video/888569182) · [Caption resource](https://captions.vimeo.com/captions/120807536.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:02.755` → `00:17:28.475`; 373 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/06_6_IDmap_Workflow/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/06_6_IDmap_Workflow/Transkrypcja.en.vtt`
- Original VTT SHA-256: `71e2246974f9ab56c0beeff2c0f05d8516132ecd4fb84e538840475ae527273b`
- Source lesson objective: Learn how you can use Houdini to create an IDmap that can be used in Unreal to drive the material placements on the landscape.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `IMPLEMENTED_LOCAL_STAGE_CHECKPOINT; LESSON06_FULL_IDMAP_PASS`. Full unified 16,000 × 16,000 domain (0.5 m spacing, 8000 m × 8000 m, 256M voxels) covering 100% of historical Working and 100% of Context in a single continuous grid. Working/Context boundary seams, bands, streaks, and smudges fully eradicated without 2D post-processing. Bit-exact Pre-ID vs Post-ID identity verified across all 256M samples (`max_diff = 0.00000000`). All 5 Pegasus semantic classes decoded via original `PE_Heightfield_id_to_layer` in fresh hython session with 100% spatial sample match. Saved checkpoint: `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc`. Receipt: [Lesson06 full-domain repair and verification](../LESSON06_FULL_IDMAP.md).

### PEG-02-07: 7 | Material Setup [26:24]

[Original video](https://player.vimeo.com/video/888569514) · [Caption resource](https://captions.vimeo.com/captions/120810096.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:03.125` → `00:26:22.445`; 595 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/07_7_Material_Setup/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/07_7_Material_Setup/Transkrypcja.en.vtt`
- Original VTT SHA-256: `2f0c5e8292219b145ab59ecb173f706bcced71bec15622cb0e926c500a32fa80`
- Source lesson objective: With the IDMap created, learn how to import the IDmap into Unreal and use it within the Unreal material. For a more in-depth look at the material setup, please check out the Material Deepdive lessons.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-08: 8 | Procedural Trails [31:28]

[Original video](https://player.vimeo.com/video/888730964) · [Caption resource](https://captions.vimeo.com/captions/120902004.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:03.455` → `00:31:27.605`; 723 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/08_8_Procedural_Trails/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/08_8_Procedural_Trails/Transkrypcja.en.vtt`
- Original VTT SHA-256: `a2bd626f356a3c0ad3f9e55750523c69e6a08386050c4e905f1911e4b33daef3`
- Source lesson objective: Continuing on to adding detail to the landscape by building procedural paths using custom digital assets built for Project Pegasus. You’ll find the digital assets in the project files.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-09: 9 | Custom Paths [14:43]

[Original video](https://player.vimeo.com/video/888732627) · [Caption resource](https://captions.vimeo.com/captions/120901616.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.745` → `00:14:42.535`; 329 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/09_9_Custom_Paths/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/09_9_Custom_Paths/Transkrypcja.en.vtt`
- Original VTT SHA-256: `2e361071afd70535aee485e3dc2a73da934341d598ae00376482b9ae1011a860`
- Source lesson objective: Building on the previous lesson, learn how to add manually placed paths to the landscape.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-10: 10 | Paths Material Layer [10:31]

[Original video](https://player.vimeo.com/video/888733445) · [Caption resource](https://captions.vimeo.com/captions/120902263.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.925` → `00:10:31.285`; 281 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/10_10_Paths_Material_Layer/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/10_10_Paths_Material_Layer/Transkrypcja.en.vtt`
- Original VTT SHA-256: `7c3509e1fd7b8d41eb91bac9451273ef70d87cb6e2ffe9ad32e997d18cfe2944`
- Source lesson objective: Now, update the IDmap and Unreal material with the paths to add textures.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-11: 11 | Woodland Scatter [34:08]

[Original video](https://player.vimeo.com/video/888734336) · [Caption resource](https://captions.vimeo.com/captions/120904089.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.635` → `00:34:07.325`; 885 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/11_11_Woodland_Scatter/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/11_11_Woodland_Scatter/Transkrypcja.en.vtt`
- Original VTT SHA-256: `fa1fbf6c33a310586e65c834d6e50da526046f4a0db8993df5fcd51067d9bfbb`
- Source lesson objective: Taking the landscape workflow even further, next, you’ll learn how to scatter trees on the environment, considering where to place foliage based on their biome.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-12: 12 | Woodland Material Layer [9:21]

[Original video](https://player.vimeo.com/video/888736712) · [Caption resource](https://captions.vimeo.com/captions/120904252.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.795` → `00:09:20.125`; 205 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/12_12_Woodland_Material_Layer/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/12_12_Woodland_Material_Layer/Transkrypcja.en.vtt`
- Original VTT SHA-256: `6cffebea2b0a7c85fd604f16d498f62eacca5597350f87546f74e64cf549317e`
- Source lesson objective: Learn how to update the IDmap based on the woodland scatter, tying the trees to the landscape with woodland ground textures.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-13: 13 | Grass and Groundcover [17:39]

[Original video](https://player.vimeo.com/video/888737205) · [Caption resource](https://captions.vimeo.com/captions/120905097.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.505` → `00:17:38.305`; 391 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/13_13_Grass_and_Groundcover/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/13_13_Grass_and_Groundcover/Transkrypcja.en.vtt`
- Original VTT SHA-256: `517b6b82e8433e86b8e7195a68e33e8fafb5cea797e563d955557f8bfdcfd39c`
- Source lesson objective: Learn how to add grass and ground cover to the landscape in Unreal using landscape grass in Unreal.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-02-14: 14 | Final Touches [9:19]

[Original video](https://player.vimeo.com/video/888738700) · [Caption resource](https://captions.vimeo.com/captions/120905988.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.520` → `00:09:18.365`; 241 nonempty cues; original timestamps retained.
- TXT: `P1_02_Landscape_Workflow/Czesci/14_14_Final_Touches/Transkrypcja.en.txt`
- VTT: `P1_02_Landscape_Workflow/Czesci/14_14_Final_Touches/Transkrypcja.en.vtt`
- Original VTT SHA-256: `617899ba0de573b5ee1fd600348a40ea67450fe3afeb62e6445d1e67fb0d91c8`
- Source lesson objective: In the final lesson you’ll add the final touches to the landscape material.
- Materials: shared `PEG-02` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

## Original material bundle

The filenames and HDA type names below are evidence of supplied files. They are not a claim that every dependency is present, licensed for redistribution, version-compatible or successfully cooked.

- [ProjectFiles_LandscapeWorkflow3.zip](https://media.sidefx.com/files/tutorials/project-pegasus-landscape-workflow/ProjectFiles_LandscapeWorkflow3.zip) — original archive SHA-256 `8c4e9f7ebacedc914f9ab55e82ac378aa18d3366207d859f393758a0f9dade10`.

| Corpus-relative material path | Kind / inspected HDA definitions | Bytes | CRC32 |
|---|---|---:|---|
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Landscape_Workflow_01_Overview.hip` | .hip | 739064 | `63c48a87` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Add_Points.1.0.hda` | pe_add_points::1.0 | 24439 | `ffb04d7a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Anisotropic_Connect_Points.hda` | PE_Anisotropic_Connect_Points | 21227 | `cbad42e4` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Auto_Remap.hda` | PE_Auto_Remap | 12061 | `8bb97185` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Cache_Landscape.hda` | PE_Cache_Landscape | 30294 | `d1daa4f9` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_CarveByAttribute.1.0.hda` | PE_CarveByAttribute::1.0 | 17430 | `f21daffb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_Advect_Points.hda` | PE_Heightfield_Advect_Points | 27153 | `fd1680b8` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_Colour.hda` | PE_Heightfield_Colour | 23838 | `60359194` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_colour_blur.hda` | PE_heightfield_colour_blur | 26445 | `96da73cb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_HeightField_Convert.1.0.hda` | PE_HeightField_Convert::1.0 | 7029 | `c4b7ea55` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_id_to_layer (1).hda` | PE_Heightfield_id_to_layer | 23846 | `dbe505e2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_id_to_layer.hda` | PE_Heightfield_id_to_layer | 16947 | `63eeb955` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_layerflow.hda` | PE_heightfield_layerflow | 16553 | `cd1ff216` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_Layers_to_ID.2.0.hda` | PE_Heightfield_Layers_to_ID::2.0 | 41241 | `c071640a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_layerslump.hda` | PE_heightfield_layerslump | 17961 | `f0f74078` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_mask_by_layer.hda` | PE_heightfield_mask_by_layer | 24047 | `7364374a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_Mask_By_Points.hda` | PE_Heightfield_Mask_By_Points | 20811 | `b10a724c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_mask_to_attribute.1.0.hda` | PE_heightfield_mask_to_attribute::1.0 | 7796 | `e60e0d9e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_material.1.0.hda` | PE_heightfield_material::1.0 | 45649 | `f8c4e316` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_paths.2.0.hda` | PE_heightfield_paths::2.0 | 62799 | `d6e87029` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_RGB_ColorSpace.1.0.hda` | heightfield_rgb_colorspace::1.0 | 17556 | `c12a65bf` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_RGB_Power.1.0.hda` | heightfield_rgb_power::1.0 | 17259 | `ff70bbb2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_RGB_Remap.1.0.hda` | heightfield_rgb_remap::1.0 | 20823 | `355c9f2b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_texture.1.0.hda` | PE_heightfield_texture::1.0 | 1096 | `26dab1d9` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_tint.1.0.hda` | PE_heightfield_tint::1.0 | 28878 | `e26d8892` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightfield_to_points.hda` | PE_Heightfield_To_Points | 26117 | `565dd5ab` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_heightield_idmap_layers.hda` | PE_heightield_idmap_layers | 18610 | `1453dc52` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_import_bgeo.hda` | PE_import_bgeo | 18759 | `0a0d5138` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Load_Landscape.2.hda` | PE_Load_Landscape::2 | 64166 | `7bc58b91` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Unreal_Instances.2.0.hda` | PE_Unreal_Instances::2.0 | 26721 | `8fb20098` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/PegasusDemo.json` | .json | 221 | `1f121bc4` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Later_1_Source.bgeo.sc` | .sc | 54102955 | `bad58a24` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc` | .sc | 20497769 | `42472c06` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_3_Procedural_Detail.bgeo.sc` | .sc | 11542615 | `996fa08e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layers.bgeo.sc` | .sc | 30924325 | `d663aa77` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Metadata$OS.bgeo.sc` | .sc | 2196 | `ef00714c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Textures/T_Pegasus_Landscape_AO.png` | .png | 6331767 | `06ac6159` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Textures/T_Pegasus_Landscape_Colour.png` | .png | 5889075 | `9277c6b6` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Textures/T_Terrain_IDMAP.png` | .png | 767017 | `2340622b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Landscape/Textures/T_Terrain_wetness.png` | .png | 7692217 | `d12caf36` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Textures/tlonbisya_4K_Displacement.exr` | .exr | 49398483 | `b19d783e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/SourceContent/Pegasus/Textures/wepoeaw_4K_Displacement.exr` | .exr | 49909184 | `552e3e3b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Config/DefaultEditor.ini` | .ini | 49 | `b6431874` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Config/DefaultEngine.ini` | .ini | 2814 | `fabe5e9d` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Config/DefaultGame.ini` | .ini | 97 | `9220fdc9` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Config/DefaultInput.ini` | .ini | 9046 | `7e317517` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/__ExternalActors__/PegasusDemo/Workshops/Landscape_Workflow/Landscape_Workflow/B/CM/9NY0Z55VO3H7W6L8YAYOBH.uasset` | .uasset | 91441 | `ef42c73a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Houdini/hda/sop_PE_Cache_Landscape.uasset` | .uasset | 33057 | `93f78dcb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Houdini/hda/sop_PE_import_bgeo.uasset` | .uasset | 9625 | `39cbbfb5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Houdini/hda/sop_PE_Load_Landscape.uasset` | .uasset | 66761 | `88fc8604` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_BilinearBlend.uasset` | .uasset | 13914 | `65de1dae` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Bitpack.uasset` | .uasset | 49072 | `c0aa9aa5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_BitUnpack.uasset` | .uasset | 24620 | `e51298d2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_BlendLayers.uasset` | .uasset | 15602 | `9850053b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Encode_IDS.uasset` | .uasset | 13448 | `24394a83` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Extract_Parmsets.uasset` | .uasset | 21828 | `cee139fa` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_ID_Unpack.uasset` | .uasset | 18867 | `ef8dcfd5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Layer_Unpack.uasset` | .uasset | 11387 | `3e70134a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Layerblend_IDMAP.uasset` | .uasset | 29034 | `d79686ff` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Material.uasset` | .uasset | 13312 | `4682c5b5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_TextureAtlas_Sample.uasset` | .uasset | 20824 | `12e2a62c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_TextureAtlas_SampleMasks.uasset` | .uasset | 22310 | `b19e46eb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_TextureAtlas_SampleNormal.uasset` | .uasset | 20948 | `ef626723` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Unpack_Parmset_A.uasset` | .uasset | 27490 | `7a0ad31b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Functions/MF_PE_Unpack_Parmset_B.uasset` | .uasset | 28843 | `f179d03a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Grasstypes/LGT_PE_Grass.uasset` | .uasset | 7020 | `3bbe7d77` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Grasstypes/LGT_PE_Heather.uasset` | .uasset | 4236 | `02b045d5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Grasstypes/LGT_PE_Highland.uasset` | .uasset | 7247 | `726849ba` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Grasstypes/LGT_PE_Wetland.uasset` | .uasset | 5695 | `8f494890` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Layers/ML_PE_Landscape_Base.uasset` | .uasset | 19634 | `964cda2d` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Layers/ML_PE_Landscape_Layer.uasset` | .uasset | 20936 | `6037f40c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Layers/MLB_PE_Landscape.uasset` | .uasset | 52771 | `689582c7` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Layers/MLB_PE_Landscape_Backup.uasset` | .uasset | 29897 | `a906a3a0` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/M_Pegasus_Landscape_Master.uasset` | .uasset | 211283 | `bd05472a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/MI_Landscape_Instance.uasset` | .uasset | 38181 | `aa7ba371` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_B.uasset` | .uasset | 8245 | `b4500892` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_G.uasset` | .uasset | 8243 | `a06947fc` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_Null.uasset` | .uasset | 8647 | `9a389499` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_O.uasset` | .uasset | 8246 | `9920e0d4` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_P.uasset` | .uasset | 8244 | `526b2384` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_R.uasset` | .uasset | 8208 | `63e69e3d` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_V.uasset` | .uasset | 8244 | `6e7942ed` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_W.uasset` | .uasset | 8763 | `81025d7a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/Debug/T_Y.uasset` | .uasset | 8247 | `a06079c3` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/TA_Colour.uasset` | .uasset | 5798 | `81620458` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/TA_Masks.uasset` | .uasset | 6102 | `05aa2076` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Materials/Landscape/Textures/TA_Normal.uasset` | .uasset | 3763 | `e9bf6749` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Common/M_Bark_Master.uasset` | .uasset | 24885 | `dcdda05f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Common/M_Foliage_Master.uasset` | .uasset | 32540 | `6acc539e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Common/M_Grass_Master.uasset` | .uasset | 94635 | `ecc578d8` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Calluna_Vulgaris/Calluna_Vulgaris_01_Medium_Clump.uasset` | .uasset | 1385307 | `66f07f21` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Calluna_Vulgaris/Callune_twig1_diffuse.uasset` | .uasset | 466013 | `2668a011` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Calluna_Vulgaris/Callune_twig1_normal.uasset` | .uasset | 1670100 | `e9119334` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Calluna_Vulgaris/Callune_twig1_opacity.uasset` | .uasset | 407988 | `fcd11c25` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Calluna_Vulgaris/MI_Calluna_Vulgaris.uasset` | .uasset | 17860 | `749ac034` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Cottongrass/cottongrass_01.uasset` | .uasset | 161696 | `d287e166` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Cottongrass/MI_CottonGrass.uasset` | .uasset | 26665 | `fd7e75fd` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Cottongrass/PE_Flora_Card5_diffuse.uasset` | .uasset | 540040 | `24667ff2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Cottongrass/PE_Flora_Card5_normal.uasset` | .uasset | 2098729 | `e5f1a351` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Cottongrass/PE_Flora_Card5_opacity.uasset` | .uasset | 399576 | `5e6715fa` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/fringe_moss_bake_2_diffuse.uasset` | .uasset | 773747 | `ebd9e45e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/fringe_moss_bake_2_normal.uasset` | .uasset | 1751692 | `56958fe7` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/fringe_moss_bake_2_opacity.uasset` | .uasset | 294739 | `a0ce574a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/Fringe_Moss_Patch_01.uasset` | .uasset | 290621 | `eda64456` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/Fringe_Moss_Patch_02.uasset` | .uasset | 283724 | `5b16c525` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/Fringe_Moss_Patch_03.uasset` | .uasset | 199750 | `9a46c5d2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/MI_Fringe_Moss.uasset` | .uasset | 22495 | `e042a6ff` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Fringe_Moss/MI_Fringe_Moss_Billboard.uasset` | .uasset | 19866 | `9fdbb37e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/atlas_colour.uasset` | .uasset | 1357 | `299cc770` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/atlas_height.uasset` | .uasset | 29056 | `b5455a37` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/atlas_opacity.uasset` | .uasset | 1362 | `0fdf565c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/Grass_Patch_01.uasset` | .uasset | 582871 | `823ffea5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/Grass_Patch_02.uasset` | .uasset | 231273 | `3a43e453` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/MI_Grass_Long.uasset` | .uasset | 22451 | `4bedaea4` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/MI_Grass_Short.uasset` | .uasset | 24882 | `1ea71d23` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/PE_Flora_Bake5_diffuse.uasset` | .uasset | 299677 | `ea82ea2f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/PE_Flora_Bake5_normal.uasset` | .uasset | 1067794 | `5d0c144b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Groundcover/Grass/PE_Flora_Bake5_opacity.uasset` | .uasset | 328280 | `d3d767a2` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Betula_Pendula_01.uasset` | .uasset | 8685071 | `45d0786f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/C_Birch_Colour.uasset` | .uasset | 5306 | `d1ece805` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/card_diffuse.uasset` | .uasset | 1088991 | `cf439104` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/card_opacity.uasset` | .uasset | 260378 | `6cc6e3b6` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/CAT_Birch.uasset` | .uasset | 3991 | `e48a5516` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/MI_Betula_Pendula.uasset` | .uasset | 14588 | `82ba76a6` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/MI_Birch.uasset` | .uasset | 12672 | `ba32fbc1` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/tdnifdqt_2K_Albedo.uasset` | .uasset | 2255951 | `f9772a85` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/tdnifdqt_2K_Normal.uasset` | .uasset | 3827369 | `1ae89873` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/Twigs.uasset` | .uasset | 12634 | `5ce85d4f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Betula_Pendula/Materials/uktkebycw_2K_Albedo.uasset` | .uasset | 718001 | `d34ce9fb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/Material_1.uasset` | .uasset | 14471 | `ab4813aa` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/MI_Corylus_Avellana.uasset` | .uasset | 17588 | `b2e342b5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/principledshader.uasset` | .uasset | 9029 | `c6b0cabe` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/qgumD_4K_Albedo.uasset` | .uasset | 1269483 | `761d680d` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/qgumD_4K_Normal.uasset` | .uasset | 2790875 | `3a00a7c7` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/qgumD_4K_Opacity.uasset` | .uasset | 593724 | `9ca1e837` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/wkljdbis_4K_Albedo.uasset` | .uasset | 4513202 | `d5c4a9d1` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/wkljdbis_4K_Normal.uasset` | .uasset | 5880465 | `e59de5ab` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/Materials/wkljdbis_4K_Roughness.uasset` | .uasset | 2758454 | `addf1194` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/SM_Hazel_01_HP.uasset` | .uasset | 13118224 | `032d2315` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/SM_Hazel_02_HP.uasset` | .uasset | 13115431 | `9d820c4b` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Corylus_Avellana/SM_Hazel_03_HP.uasset` | .uasset | 15403613 | `f3fdf0c1` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/M_Bark.uasset` | .uasset | 19362 | `e1423b59` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/MI_Pinus_Bark.uasset` | .uasset | 15779 | `b8ac3d5d` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/MI_Pinus_Sylvestris.uasset` | .uasset | 22583 | `e156f323` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/rfei7_4K_Albedo.uasset` | .uasset | 969797 | `8fa63c1a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/rfei7_4K_Normal.uasset` | .uasset | 2212874 | `752fd62f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/rfei7_4K_Opacity.uasset` | .uasset | 1662964 | `8f38fa93` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/T_PineBark_Top_PG_C.uasset` | .uasset | 7557450 | `dbdc0522` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/T_PineBark_Top_PG_H.uasset` | .uasset | 1169776 | `430147b0` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/T_PineBark_Top_PG_N.uasset` | .uasset | 9784664 | `4da33503` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/T_PineBark_Top_PG_O.uasset` | .uasset | 1721047 | `771cf21a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/Materials/T_PineBark_Top_PG_R.uasset` | .uasset | 2916296 | `375b75cb` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/SM_Pine_01_HP.uasset` | .uasset | 34767842 | `95f5ce91` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/SM_Pine_02_HP.uasset` | .uasset | 49237572 | `8cf4e4aa` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Pinus_Sylvestris/SM_Pine_03_HP.uasset` | .uasset | 50449735 | `73a40fd8` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/MI_Sorbus_aucuparia_bark.uasset` | .uasset | 13873 | `d2d08b06` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/MI_Sorbus_aucuparia_foliage.uasset` | .uasset | 22798 | `dc64bf66` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/T_Atlas_Mountain_Ash_diffuse.uasset` | .uasset | 12989088 | `f2e4a7ec` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/T_Atlas_Mountain_Ash_normal.uasset` | .uasset | 14641219 | `4b988924` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/T_Atlas_Mountain_Ash_opacity.uasset` | .uasset | 3009949 | `24b8e313` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/T_Atlas_Mountain_Ash_roughness.uasset` | .uasset | 3999707 | `23e273de` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/uktkciscw_4K_Albedo.uasset` | .uasset | 2057707 | `723ed610` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/uktkciscw_4K_Normal.uasset` | .uasset | 3201385 | `06531c69` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/Materials/uktkciscw_4K_Roughness.uasset` | .uasset | 901788 | `83c2554f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_01_HP.uasset` | .uasset | 15694158 | `6f7cf358` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_01_LP.uasset` | .uasset | 107859 | `950364de` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_02_HP.uasset` | .uasset | 15526253 | `31a7d17a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_03_HP.uasset` | .uasset | 10829400 | `be98beea` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_03_LP.uasset` | .uasset | 150969 | `24a4e32c` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_04_HP.uasset` | .uasset | 49586174 | `f58bc17e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Content/PegasusDemo/Meshes/Foliage/Trees/Sorbus_aucuparia/SM_Mountain_Ash_04_LP.uasset` | .uasset | 705994 | `59ffa9ca` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/AssetRegistryCache/c90e3f55.bin` | .bin | 23509732 | `a5787d4f` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/CachedAssetRegistry_0.bin` | .bin | 25945313 | `cd20a46a` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/Crypto.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/GameUserSettings.ini` | .ini | 63 | `df7425a3` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/HoudiniEngine.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/InternationalizationExport.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/LocalizationServiceSettings.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/ObjectMixer.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/ObjectMixerSerializedData.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/OpenColorIO.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/TranslationPickerSettings.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/Config/CoalescedSourceConfigs/UnrealInsightsSettings.ini` | .ini | 0 | `00000000` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/ReimportCache/3688439234.bin` | .bin | 238 | `f863fcc5` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/ShaderAutogen/PCD3D_SM5/AutogenShaderHeaders.ush` | .ush | 15288 | `73b2d47e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Intermediate/ShaderAutogen/PCD3D_SM6/AutogenShaderHeaders.ush` | .ush | 15288 | `73b2d47e` |
| `P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Unreal/Pegasus_Demo.uproject` | .uproject | 405 | `210ebffd` |

Exact SHA-256 for every material and inspected HDA parameter schemas are in [catalog.json](catalog.json).
