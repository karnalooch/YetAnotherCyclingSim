# PEG-01: Project Pegasus | Landscape Creation

[Official series](https://www.sidefx.com/tutorials/project-pegasus-landscape-creation/) · [Catalog](README.md) · [Workflow](../README.md)

Stage: **HeightField creation, shaping, erosion and HDA packaging**. Corpus folder: `P1_01_Landscape_Creation`.

## Lesson concordance

All listed TXT/VTT files were read and the original VTT hashes checked. `INDEXED` means source availability and integrity, not semantic study or a successful Houdini cook. Paths below resolve relative to `YACS_SIDEFX_CORPUS`.

### PEG-01-00: Overview [1:29]

[Original video](https://player.vimeo.com/video/888565712) · [Caption resource](https://captions.vimeo.com/captions/134120967.vtt)

- Language: `en`; source track: `en`; automatic: `false`.
- Text coverage: `00:00:00.400` → `00:01:25.800`; 29 nonempty cues; original timestamps retained.
- TXT: `P1_01_Landscape_Creation/Czesci/00_Overview/Transkrypcja.en.txt`
- VTT: `P1_01_Landscape_Creation/Czesci/00_Overview/Transkrypcja.en.vtt`
- Original VTT SHA-256: `0b348f967c78d64f9b4764e1e13fc24a35385cdedf5dd1ba4bd440ca6890758a`
- Source lesson objective: A quick overview of each lesson and what you’ll be learning along the way.
- Materials: shared `PEG-01` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-01-01: 1 | Introduction to Heightfield Erode [39:56]

[Original video](https://player.vimeo.com/video/888565731) · [Caption resource](https://captions.vimeo.com/captions/120805559.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.525` → `00:39:54.495`; 714 nonempty cues; original timestamps retained.
- TXT: `P1_01_Landscape_Creation/Czesci/01_1_Introduction_to_Heightfield_Erode/Transkrypcja.en.txt`
- VTT: `P1_01_Landscape_Creation/Czesci/01_1_Introduction_to_Heightfield_Erode/Transkrypcja.en.vtt`
- Original VTT SHA-256: `e566c6d5199d12c576aa859c42aa21ccaa628eab98cef68dde0d548f7bfc11b7`
- Source lesson objective: Take a tour of the Heightfield Erode tool, breaking down each parameter's purpose and how it affects the erosion simulation.
- Materials: shared `PEG-01` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-01-02: 2 | Building the Landscape [32:51]

[Original video](https://player.vimeo.com/video/888565929) · [Caption resource](https://captions.vimeo.com/captions/120805561.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:01.115` → `00:32:49.635`; 608 nonempty cues; original timestamps retained.
- TXT: `P1_01_Landscape_Creation/Czesci/02_2_Building_the_Landscape/Transkrypcja.en.txt`
- VTT: `P1_01_Landscape_Creation/Czesci/02_2_Building_the_Landscape/Transkrypcja.en.vtt`
- Original VTT SHA-256: `110a5b8939659a7ad42dc466f168a76762d6c77d9bf234ec97d415fd66a265a9`
- Source lesson objective: Learn to build the landscape for Project Pegasus, creating the basic shape using geometry, projecting it into a heightfield and layer noises, distortion and erode nodes to create the final landscape.
- Materials: shared `PEG-01` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

### PEG-01-03: 3 | Landscape Digital Asset [18:53]

[Original video](https://player.vimeo.com/video/888566094) · [Caption resource](https://captions.vimeo.com/captions/120805649.vtt)

- Language: `en`; source track: `en-x-autogen`; automatic: `true`.
- Text coverage: `00:00:00.090` → `00:18:51.355`; 335 nonempty cues; original timestamps retained.
- TXT: `P1_01_Landscape_Creation/Czesci/03_3_Landscape_Digital_Asset/Transkrypcja.en.txt`
- VTT: `P1_01_Landscape_Creation/Czesci/03_3_Landscape_Digital_Asset/Transkrypcja.en.vtt`
- Original VTT SHA-256: `baa46891d8c5414e7ca3288fd7f30459a364d887f0598ef3dedfa1bf56310009`
- Source lesson objective: Learn how to save the landscape as a Digital Asset and import it into Unreal. You’ll see how to create a basic landscape material and how to use Session Sync to make changes to the Digital Asset.
- Materials: shared `PEG-01` bundle listed below. Per-lesson dependency mapping has not been established.
- Verification: `INDEXED`; implementation: `NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED`.

## Original material bundle

The filenames and HDA type names below are evidence of supplied files. They are not a claim that every dependency is present, licensed for redistribution, version-compatible or successfully cooked.

- [ProjectFiles_LandscapeCreation2.zip](https://media.sidefx.com/files/tutorials/project-pegasus-landscape-creation/ProjectFiles_LandscapeCreation2.zip) — original archive SHA-256 `0792e36b2a990da33bffe2657c4379315ed5ff34e926b7c712ae975ad4e5f4db`.

| Corpus-relative material path | Kind / inspected HDA definitions | Bytes | CRC32 |
|---|---|---:|---|
| `P1_01_Landscape_Creation/Materialy/ProjectFiles_LandscapeCreation2/ProjectFiles_LandscapeCreation/hdas/sop_pe_landscape.1.0.hda` | pe_landscape::1.0 | 89701 | `df30998d` |
| `P1_01_Landscape_Creation/Materialy/ProjectFiles_LandscapeCreation2/ProjectFiles_LandscapeCreation/ProjectFiles_LandscapeCreation_DigitalAsset.hip` | .hip | 609530 | `a3cd6aea` |
| `P1_01_Landscape_Creation/Materialy/ProjectFiles_LandscapeCreation2/ProjectFiles_LandscapeCreation/ProjectFiles_LandscapeCreation_HFErodeExamples.hip` | .hip | 2110048 | `5f680a06` |

Exact SHA-256 for every material and inspected HDA parameter schemas are in [catalog.json](catalog.json).
