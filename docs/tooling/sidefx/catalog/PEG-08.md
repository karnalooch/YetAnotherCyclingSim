# PEG-08: Project Pegasus | Architecture

[Official series](https://www.sidefx.com/tutorials/project-pegasus-architecture/) · [Catalog](README.md) · [Workflow](../README.md)

Stage: **Architecture slicing, placement and terrain sampling**. Corpus folder: `P1_08_Architecture`.

## Lesson concordance

All listed TXT/VTT files were read and the original VTT hashes checked. `INDEXED` means source availability and integrity, not semantic study or a successful Houdini cook. Paths below resolve relative to `YACS_SIDEFX_CORPUS`.

### PEG-08-00: Introduction [6:59]

[Original video](https://player.vimeo.com/video/896225847) · [Caption resource](https://captions.vimeo.com/captions/125438551.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.130` → `00:06:58.015`; 113 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/00_Introduction/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/00_Introduction/Transkrypcja.en.vtt`
- Original VTT SHA-256: `b1920e10e5dea7877c88c0c5b8098683ec777e2aef1296600c7f2c082dd665dd`
- Source lesson objective: Discover the topics you’ll be learning in the upcoming lessons and begin to set up the basic starting blocks of the Houdini setup.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-08-01: 1 | HDA Setup [8:13]

[Original video](https://player.vimeo.com/video/896226122) · [Caption resource](https://captions.vimeo.com/captions/125438913.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.325` → `00:08:12.105`; 124 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/01_1_HDA_Setup/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/01_1_HDA_Setup/Transkrypcja.en.vtt`
- Original VTT SHA-256: `2423f6fc04cf6b6c47c227ee6146635798a8b8bfd98d87e486713f73c7223726`
- Source lesson objective: Learn how to save subnets as Digital Assets and how to import them into Unreal so that you can begin developing the tools. The lesson uses the Unreal Procedural Content Generation (PCG) graph (see bonus below) to sample the landscape in Unreal.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-08-02: 2 | Boolean Preparation [9:37]

[Original video](https://player.vimeo.com/video/896226401) · [Caption resource](https://captions.vimeo.com/captions/125439081.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.515` → `00:09:36.645`; 132 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/02_2_Boolean_Preparation/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/02_2_Boolean_Preparation/Transkrypcja.en.vtt`
- Original VTT SHA-256: `ab4c1ebdcdce9b88f50c3a249cb7ea87c869a5d72802d4b3c133445e312b1e9f`
- Source lesson objective: Learn how to reference the result of the PCG network from Unreal into Houdini. We'll generate input geometry for the tool and execute boolean operations involving both the terrain and the input shapes.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-08-03: 3 | Slicing [24:52]

[Original video](https://player.vimeo.com/video/896226671) · [Caption resource](https://captions.vimeo.com/captions/125439377.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:02.775` → `00:24:52.325`; 409 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/03_3_Slicing/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/03_3_Slicing/Transkrypcja.en.vtt`
- Original VTT SHA-256: `daa0993cecef9c4c5bebba5c9a87a45d5be5cf3d21e204898f3ddfa4cc4b2c0f`
- Source lesson objective: See how to slice the input geometry into segments and begin to have a framework which later can be used for all sorts of detail placement.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-08-04: 4 | Placement [21:24]

[Original video](https://player.vimeo.com/video/896227112) · [Caption resource](https://captions.vimeo.com/captions/125439678.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:02.095` → `00:21:23.235`; 312 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/04_4_Placement/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/04_4_Placement/Transkrypcja.en.vtt`
- Original VTT SHA-256: `99bdf60491c38d8812222cc092d596cf7717a6eb383ce6856d39e0875fe7e57e`
- Source lesson objective: Discover how to quickly setup modules using the previously created framework. We will use orientation attributes native to Houdini like the up vector and normals.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-08-05: BONUS | PCG Terrain Sampler [14:11]

[Original video](https://player.vimeo.com/video/896228801) · [Caption resource](https://captions.vimeo.com/captions/125440681.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.845` → `00:14:10.225`; 188 nonempty cues; original timestamps retained.
- TXT: `P1_08_Architecture/Czesci/05_BONUS_PCG_Terrain_Sampler/Transkrypcja.en.txt`
- VTT: `P1_08_Architecture/Czesci/05_BONUS_PCG_Terrain_Sampler/Transkrypcja.en.vtt`
- Original VTT SHA-256: `fe4d4729f40bd32796d81b818498cfa0e4efe3af5cb74cc1a0102ce27ab35b0b`
- Source lesson objective: Learn how to create a PCG tool that can be used to sample an area of Unreal landscape and referenced into Houdini. This allows you to only reference the area that you need rather than the whole landscape, vastly speeding up your workflow.
- Materials: shared `PEG-08` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

## Original material bundle

The filenames and HDA type names below are evidence of supplied files. They are not a claim that every dependency is present, licensed for redistribution, version-compatible or successfully cooked.

- [ProjectFiles_Architecture.zip](https://media.sidefx.com/files/tutorials/project-pegasus-architecture/ProjectFiles_Architecture.zip) — original archive SHA-256 `de24983417c1bd26c16cb687110103b5bfa8e4b3bba903285915dcbf5094c6f0`.
- [ProjectFiles_TerrainSampler.zip](https://media.sidefx.com/files/tutorials/project-pegasus-architecture/ProjectFiles_TerrainSampler.zip) — original archive SHA-256 `fa11ed2fe1a72f223eb4fa565e70fbdd3bfe1fe939341708daf47ddf9e6b3b6a`.

| Corpus-relative material path | Kind / inspected HDA definitions | Bytes | CRC32 |
|---|---|---:|---|
| `P1_08_Architecture/Materialy/ProjectFiles_Architecture/ProjectFiles_Architecture/assembler.hda` | pegasus::assembler::1.0 | 46148 | `18140546` |
| `P1_08_Architecture/Materialy/ProjectFiles_TerrainSampler/ProjectFiles_TerrainSampler/terrainsample_scatter.hda` | pegasus::scatter::1.0 | 20100 | `76cc805a` |

Exact SHA-256 for every material and inspected HDA parameter schemas are in [catalog.json](catalog.json).
