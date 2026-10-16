# PEG-04: Project Pegasus | Landscape Technical Deep Dive

[Official series](https://www.sidefx.com/tutorials/project-pegasus-landscape-technical-deep-dive/) · [Catalog](README.md) · [Workflow](../README.md)

Stage: **RGB HeightFields and point advection**. Corpus folder: `P1_04_Landscape_Technical_Deep_Dive`.

## Lesson concordance

All listed TXT/VTT files were read and the original VTT hashes checked. `INDEXED` means source availability and integrity, not semantic study or a successful Houdini cook. Paths below resolve relative to `YACS_SIDEFX_CORPUS`.

### PEG-04-00: 1  | RGB Heightfields

[Original video](https://player.vimeo.com/video/888566872) · [Caption resource](https://captions.vimeo.com/captions/120806387.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.340` → `00:29:15.335`; 548 nonempty cues; original timestamps retained.
- TXT: `P1_04_Landscape_Technical_Deep_Dive/Czesci/00_1_RGB_Heightfields/Transkrypcja.en.txt`
- VTT: `P1_04_Landscape_Technical_Deep_Dive/Czesci/00_1_RGB_Heightfields/Transkrypcja.en.vtt`
- Original VTT SHA-256: `ace306bb4fecf02dd5e2a496d3ef85598d46ce8ffd96b40a7c968786e903ec70`
- Source lesson objective: Take a closer look at how you can use the Heightfield tools to build detailed color maps in Unreal.
- Materials: shared `PEG-04` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-04-01: 2 | Heightfield Advect Points

[Original video](https://player.vimeo.com/video/888566369) · [Caption resource](https://captions.vimeo.com/captions/120806282.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.305` → `00:29:53.845`; 685 nonempty cues; original timestamps retained.
- TXT: `P1_04_Landscape_Technical_Deep_Dive/Czesci/01_2_Heightfield_Advect_Points/Transkrypcja.en.txt`
- VTT: `P1_04_Landscape_Technical_Deep_Dive/Czesci/01_2_Heightfield_Advect_Points/Transkrypcja.en.vtt`
- Original VTT SHA-256: `170e99af32c48da7df900bf5762eb12efbd0d2c51c118c661d38e20138c7ad75`
- Source lesson objective: Learn an advanced technique for moving points along a heightfield, taking a basic scatter and moving the points across the landscape to create more interesting placement, such as biasing points to move along valleys or peaks.
- Materials: shared `PEG-04` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

## Original material bundle

The filenames and HDA type names below are evidence of supplied files. They are not a claim that every dependency is present, licensed for redistribution, version-compatible or successfully cooked.

- [ProjectFiles_TechnicalDeepdives2.zip](https://media.sidefx.com/files/tutorials/project-pegasus-landscape-technical-deep-dive/ProjectFiles_TechnicalDeepdives2.zip) — original archive SHA-256 `675a8f7ad82af59c8818aa4de48c2334b4c5c8ee479a6958552def86338368dd`.

| Corpus-relative material path | Kind / inspected HDA definitions | Bytes | CRC32 |
|---|---|---:|---|
| `P1_04_Landscape_Technical_Deep_Dive/Materialy/ProjectFiles_TechnicalDeepdives2/ProjectFiles_TechnicalDeepdives/HeightfieldAdvectPoints/sop_PE_Heightfield_Advect_Points.hda` | PE_Heightfield_Advect_Points | 27153 | `fd1680b8` |
| `P1_04_Landscape_Technical_Deep_Dive/Materialy/ProjectFiles_TechnicalDeepdives2/ProjectFiles_TechnicalDeepdives/RGBHeightfields/hda/sop_PE_Heightfield_Colour.hda` | PE_Heightfield_Colour | 23823 | `9b774a99` |
| `P1_04_Landscape_Technical_Deep_Dive/Materialy/ProjectFiles_TechnicalDeepdives2/ProjectFiles_TechnicalDeepdives/RGBHeightfields/Heightfield_RGB.hip` | .hip | 281712 | `710ac7fe` |

Exact SHA-256 for every material and inspected HDA parameter schemas are in [catalog.json](catalog.json).
