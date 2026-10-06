# YACS Material Forge

**Status:** implementation ready for exact-SHA render/UE proof  
**Issue:** #387  
**Scope:** offline procedural PBR authoring, material-local masks, deterministic validation and bounded UE import

Material Forge exists to answer one question:

> How should a surface look, once YACS already knows what that surface is and where it belongs?

It is deliberately not another world generator.

## Ownership boundary

| Subsystem | Owns |
|---|---|
| BOB | road/terrain geometry, cut/fill and earthworks |
| PCG/PCGEx | world semantics, classification, placement and authoritative spatial masks |
| Material Forge | surface appearance, procedural PBR and material-local detail masks |

The non-negotiable rule is:

> **PCG/PCGEx owns WHO / WHAT / WHERE. Material Forge owns HOW IT LOOKS.**

Material Forge may consume an authoritative Road/Rock/Soil/Wetness mask and derive
surface-detail breakup from it. It may not independently decide that a location
is road, rock, forest, soil, snow or any other world class.

## Runtime/tool boundary

The proof path deliberately keeps the dependency boundary small:

- the pinned **Material Maker 1.7 release executable** is the only map producer;
- the reviewed Material Maker source commit remains provenance/reference evidence,
  but the clean source tree is not launched as an application;
- the pinned **Godot 4.7.2** executable is decoder-only: it natively opens the
  produced PNG/EXR files and emits a hash-bound receipt;
- no Godot or Material Maker fork is introduced;
- MaterialPilot and Tool-MaterialMaker-MCP are reference-only evidence;
- the YACS-owned surface contract is implemented in repository Python/JSON;
- PCG/PCGEx continues to own world semantics.

The source-tree renderer was rejected during exact-SHA proof because a clean
checkout lacked the generated Godot class/import cache required by the
application. Increasing timeouts did not fix that defect.

## Phase-A families

The catalog is
`worldgen/materials/material_forge/families.json`.

It defines three families and three deterministic variants per family:

1. **Aged mountain asphalt** — base aged, worn cracked, patched repaired.
2. **Regional pale limestone** — weathered pale, fractured, karst weathered.
3. **Dry Mediterranean mineral soil** — fine mineral, stony mineral, dry crusted.

Every variant records its seed, tile size and surface parameters.

## Output contract

A rendered variant contains:

| Output | Contract |
|---|---|
| BaseColor | sRGB colour |
| Normal_DX | DirectX tangent-space normal |
| ORM | R=AO, G=Roughness, B=Metallic |
| Height | EXR authoring/inspection height; not Landscape displacement |
| DetailMasks | material-local RGB detail semantics |

Phase A requires metallic to remain zero. `DetailMasks` remains material-local
appearance data and never carries authoritative world classification.

## Material Maker inputs

Graph authoring reads the pinned Material Maker 1.7 install directory containing
`nodes/material.mmg` and `material_maker.exe`. Rendering then invokes that
same pinned release through its official `--export-material` CLI with the
YACS-owned `YACS/Textures` export profile embedded in the generated `.ptex`.

Material Maker 1.7 parses `--size`, but its current CLI exporter still passes
a hard-coded 2048 image size to `export_material`. Material Forge therefore
fails closed for non-2048 render requests rather than claiming a resolution the
upstream CLI did not honor.

The reviewed source commit in `upstreams.json` documents the inspected CLI and
node behavior. It is not a runtime dependency of the proof.

## Authoring pipeline

```text
families.json + upstreams.json
              |
              v
scripts/assets/material_forge.py author
              |
              v
editable Material Maker .ptex graphs
              |
              v
Material Maker 1.7 release --export-material
              |
              v
5-map YACS/Textures contract
              |
              v
Godot 4.7.2 decoder-only native read + exact byte hashes
              |
              v
CPU validation + hashes + run manifest
              |
              v
UE importer / bounded canary
```

Accepted or reviewed output directories are never silently overwritten.

## Reproducibility and fingerprinting

Every run records catalog/upstream hashes, graph hashes, family/variant seeds,
canonical variant fingerprints and output hashes. Two clean runs are compared
with:

```text
python scripts/assets/material_forge.py compare --left <run-a> --right <run-b>
```

Any graph or output hash drift fails determinism.

## Validation gates

The CPU validator rejects missing/wrong-size outputs, discontinuous tile
boundaries, blank signals, non-zero metallic, invalid normal vectors,
non-DirectX metadata, missing EXR Height, semantic-ownership violations, and
missing/invalid native Godot receipts. All five receipt entries must match the
requested 2048 dimensions and SHA-256 of the exact produced bytes.

Visual quality still requires exact-SHA human proof. A numeric PASS is not a
claim that repetition, scale or regional appearance is accepted.

## Authoritative world-mask operations

Material Forge may pack already-authoritative PCG/PCGEx masks into RGBA and may
modulate material-local detail by an authoritative world mask. Both operations
preserve source hashes, keep `semantic_owner=PCG/PCGEx`, record
`classification_changed=false`, and may not threshold, grow, erode or invent
world classes.

## UE importer and bounded canary

`scripts/ue/import_material_forge_variant.py` accepts only a CPU-validated
variant, verifies map hashes again, imports BaseColor/Normal/ORM/DetailMasks with
the required UE settings, creates a parameterized master + instance, keeps
Height offline, and defaults to unsaved assets.

`scripts/ue/preview_material_forge_canary.py` targets only
`LandscapeComponent_230` on the frozen accepted Sa Calobra map, verifies the
scene snapshot, never saves the level, and restores the original override on the
second invocation. It is a presentation canary, not whole-Landscape admission.

## Upstream pins and licences

`worldgen/materials/material_forge/upstreams.json` records exact evidence:

- Material Maker 1.7 release commit
  `4c6cea67b659e1eb472f91590e06b2b1c5245916`, MIT;
- reviewed Material Maker source commit
  `4d29a815489866aae483281cf44b2cfe48d3cc3e`, reference/provenance only;
- Godot 4.7.2-stable commit
  `ed1daf0bf001b61586d9930840f2f1394092c079`, MIT, decoder-only;
- MaterialPilot and Tool-MaterialMaker-MCP remain reference-only.

No upstream source tree is vendored into YACS.

## Admission state

The implementation has lightweight contract coverage and exact-SHA CI support.
Still required before PR admission: fresh 3x3 render, two-run byte determinism,
UE 5.8 import/compile, canary assignment + rollback, rider-close/grazing/3x3/wide
visual review, then whole-Landscape/performance acceptance.
