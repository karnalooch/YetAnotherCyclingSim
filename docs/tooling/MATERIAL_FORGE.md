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

## Why this is not a Godot or PCG fork

The current implementation intentionally keeps the dependency boundary small:

- Material Maker remains an external authoring source/application;
- Godot remains an external headless renderer;
- no Godot fork is introduced;
- no Material Maker source tree is vendored;
- MaterialPilot and Tool-MaterialMaker-MCP are reference-only evidence;
- the YACS-owned surface contract is implemented in repository Python/JSON;
- PCG/PCGEx continues to own world semantics.

A fork is justified only if a concrete upstream limitation blocks an accepted
Material Forge contract and a smaller adapter cannot solve it.

## Phase-A families

The catalog is
`worldgen/materials/material_forge/families.json`.

It defines three families and three deterministic variants per family:

1. **Aged mountain asphalt**
   - base aged;
   - worn cracked;
   - patched repaired.
2. **Regional pale limestone**
   - weathered pale;
   - fractured;
   - karst weathered.
3. **Dry Mediterranean mineral soil**
   - fine mineral;
   - stony mineral;
   - dry crusted.

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

Phase A requires metallic to remain zero.

`DetailMasks` meanings are family-local and recorded in provenance. Examples:

- asphalt: cracks / patches / binder micro-variation;
- limestone: fractures / pores-pits / mineral variation;
- soil: pebbles / dry crust / fine-grain variation.

These channels are not world-classification masks.

## Material Maker inputs

Material Forge deliberately distinguishes two external inputs:

- **Material Maker 1.7 install directory** — used by `author` to read the shipped `nodes/material.mmg` definition and hash the reviewed executable;
- **Material Maker source checkout** — used only by the Godot headless render runner.

The author CLI accepts `--material-maker` (with the earlier
`--material-maker-source` spelling retained as an alias). Provenance records
the reviewed release/source revisions separately.

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
scripts/assets/render_material_forge.py
              |
        Material Maker source
              +
         Godot headless
              |
              v
PBR + DetailMasks + native decode receipt
              |
              v
CPU validation + hashes + run manifest
              |
              v
UE importer / bounded canary
```

The author command refuses an existing output directory. Accepted or reviewed
material output is never silently overwritten.

## Fingerprint-driven rebuild planning

`plan-rebuild` hashes the YACS Material Forge implementation, the existing
Material Maker graph builder, family catalog and upstream pins. A run is rebuilt
only when that source fingerprint changes. Existing reviewed output is never
silently overwritten.

## Reproducibility and fingerprinting

Every run records:

- catalog SHA-256;
- upstream-pin SHA-256;
- graph SHA-256;
- family/variant seed;
- canonical variant fingerprint;
- output SHA-256 after rendering;
- validation receipt.

Two clean runs can be compared with:

```text
python scripts/assets/material_forge.py compare --left <run-a> --right <run-b>
```

Any graph or output hash drift fails the comparison.

## Validation gates

The CPU validator rejects:

- missing outputs;
- wrong dimensions;
- discontinuous tile boundaries;
- blank colour/normal/detail signal;
- non-zero metallic in phase A;
- invalid normal-vector lengths;
- non-DirectX normal metadata;
- missing EXR height;
- missing or invalid native Godot decode receipts (all five outputs, including
  Height, must have a successful decode at the requested resolution and the
  receipt SHA-256 must match the exact rendered bytes);
- semantic ownership that is not PCG/PCGEx.

Visual quality still requires exact-SHA human proof. A numeric pass is not a
claim that repetition, scale or regional appearance is accepted.

## Authoritative world-mask packing

Material Forge contains one intentionally narrow world-mask operation:
**pack-only**.

Input masks must already be authoritative PCG/PCGEx products. The packer:

- requires `semantic_owner=PCG/PCGEx`;
- requires `operation=pack_only`;
- does not threshold, classify, grow, shrink or invent a mask;
- copies channels into RGBA;
- records every input SHA;
- records `classification_changed=false`.

This allows efficient UE control textures without creating a second semantic
pipeline.

## Controlled world-mask steering

Material Forge supports one derived-mask operation in addition to RGBA packing:
`modulate_detail_only`.

It multiplies a material-local RGB detail mask by an authoritative grayscale
PCG/PCGEx world mask. This permits, for example, an authoritative Road mask to
limit asphalt crack/patch detail to the road domain without Material Forge
deciding where the road is.

The transform:

- requires `semantic_owner=PCG/PCGEx`;
- preserves the world-mask SHA;
- preserves the source detail-mask SHA;
- requires identical dimensions;
- does not threshold, blur, grow, erode or classify;
- records `classification_changed=false`.

The machine-readable operation schema and replay examples live under
`worldgen/materials/material_forge/`.

## UE importer

`scripts/ue/import_material_forge_variant.py`:

- accepts only a CPU-validated variant;
- verifies map hashes again;
- imports BaseColor/Normal/ORM/DetailMasks;
- applies sRGB/compression/wrap settings;
- keeps DirectX normal green unchanged;
- creates a parameterized master material;
- creates a Material Instance;
- exposes tile size and texture parameters;
- keeps Height offline;
- does not mutate Landscape/world placement;
- defaults to unsaved assets.

Persistent save requires explicit `YACS_MATERIAL_FORGE_SAVE=1` and is not an
acceptance shortcut.

## Bounded Sa Calobra canary

`scripts/ue/preview_material_forge_canary.py` is the first controlled consumer.

It:

- requires the frozen accepted Sa Calobra map identity;
- verifies map SHA;
- verifies one Landscape and the expected topology;
- targets only `LandscapeComponent_230`;
- imports a validated variant unsaved;
- changes only that component override;
- verifies global material, all other components and the frozen scene snapshot;
- writes a proof receipt;
- never saves the map;
- restores the original material when run again.

This is a presentation canary only. It does not admit whole-Landscape placement,
PCG masks, performance or final visual quality.

## Agent/MCP surface

The high-level operation registry is
`tools/material-forge/agent-contract.json`.

YACS intentionally exposes domain operations such as author, render, validate,
pack, import and canary. It does not expose arbitrary Godot/UE calls or introduce
another long-running backend.

This contract is ready to be wrapped by an approved MCP transport later without
changing the world/material ownership model.

## Upstream pins and licences

`worldgen/materials/material_forge/upstreams.json` records exact evidence.

Current pins:

- Material Maker 1.7 release commit
  `4c6cea67b659e1eb472f91590e06b2b1c5245916`, MIT;
- previously validated Material Maker source commit
  `4d29a815489866aae483281cf44b2cfe48d3cc3e`;
- Godot 4.7.2-stable commit
  `ed1daf0bf001b61586d9930840f2f1394092c079`, MIT;
- MaterialPilot commit
  `e3721eadd042e077f3aa7d472ad83c5594c7ea5b`, Apache-2.0, reference only;
- Tool-MaterialMaker-MCP commit
  `1488b94c02f85e88ef6563e33d753c3bfdfaac5a`, MIT, reference only.

No MaterialPilot or Tool-MaterialMaker-MCP source is copied into YACS.

## Validation state for this implementation

Completed before opening the draft:

- Python syntax compilation for the new Python files: PASS;
- Material Forge CPU unit tests: **8/8 PASS**.

Not claimed yet:

- Ruff: unavailable in the current execution environment;
- fresh Material Maker/Godot 3x3 family render;
- two-run byte determinism on the reference host;
- UE 5.8 importer execution;
- UE material compilation;
- canary assignment/rollback;
- rider-close and wide anti-repetition visual proof;
- performance acceptance;
- whole-Landscape/PCG integration.

These are exact-SHA proof tasks for the next validation session, not missing
implementation scope.
