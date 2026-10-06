# YACS Material Forge

**Status:** exact-SHA render proof in progress  
**Issue:** #387  
**Scope:** offline procedural PBR authoring, material-local masks, deterministic validation and bounded UE import

Material Forge answers one question:

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

## Runtime/tool boundary

Material Forge uses:

- the pinned Material Maker 1.7 install directory only as reviewed authoring input
  (`nodes/material.mmg`, executable identity and licence evidence);
- the reviewed Material Maker source commit
  `4d29a815489866aae483281cf44b2cfe48d3cc3e` as the render runtime;
- pinned Godot 4.7.2 to first prime that source project's import/script-class
  cache and then execute the bounded YACS render adapter;
- no Godot fork and no Material Maker fork.

A clean Material Maker source checkout is **not render-ready by itself**. Exact-SHA
proof established that it must first be opened through
`Godot --headless --path <source> --import`, which creates
`.godot/global_script_class_cache.cfg` and imported resource cache. Rendering
before that priming produced unresolved Material Maker classes and timed out.

The alternative Material Maker 1.7 release CLI path was also tested and rejected
for this automation path: upstream `dry_earth.ptex`, the earlier YACS limestone
graph and the new Forge asphalt graph all exited with Windows access violation
`0xC0000005` both from the runner service and from the logged-on desktop
session. That A/B/C result isolates the crash from Forge graph generation.

## Phase-A families

The catalog `worldgen/materials/material_forge/families.json` defines three
families with three deterministic variants each:

1. aged mountain asphalt — base, worn cracked, patched/repaired;
2. regional pale limestone — weathered, fractured, karst-weathered;
3. dry Mediterranean mineral soil — fine, stony, dry-crusted.

Each variant records its seed, physical tile size and surface parameters.

## Output contract

Each rendered variant contains:

| Output | Contract |
|---|---|
| BaseColor | sRGB colour |
| Normal_DX | DirectX tangent-space normal |
| ORM | R=AO, G=Roughness, B=Metallic |
| Height | EXR authoring/inspection height; not Landscape displacement |
| DetailMasks | material-local RGB detail semantics |

Phase A requires metallic to remain zero. Detail masks never own world
classification.

## Authoring and render pipeline

```text
families.json + upstreams.json
              |
              v
material_forge.py author
              |
              v
editable Material Maker .ptex graphs
              |
              v
pinned Material Maker source checkout
              |
      Godot 4.7.2 --import
              |
      script/import cache receipt
              |
              v
render_material_forge.py + render_material_forge.gd
              |
              v
5 maps + native Godot decode/hash receipt
              |
              v
CPU validation + run manifest
              |
              v
second clean run -> byte determinism compare
              |
              v
UE importer / bounded canary
```

The renderer refuses to run if the source class/import cache is absent.

## Reproducibility and validation

Every run records graph/output SHA-256 values, upstream/catalog fingerprints,
seeds and validation receipts. Native Godot decode evidence for all five maps is
bound to the exact output bytes and requested dimensions.

Two complete runs are compared with:

```text
python scripts/assets/material_forge.py compare --left <run-a> --right <run-b>
```

Any graph/fingerprint/output drift fails determinism.

CPU gates reject missing outputs, wrong dimensions, wrap discontinuities, blank
signals, non-zero metallic, invalid normal vectors, non-DirectX metadata, missing
Height EXR, stale decode receipts or semantic-ownership violations.

Visual quality remains a separate exact-SHA human gate.

## World-mask boundary

Material Forge may pack already-authoritative PCG/PCGEx masks and may gate local
surface detail with them. It may not threshold, grow, erode or invent world
classes. Receipts preserve input hashes and record
`classification_changed=false`.

## UE importer and bounded canary

`scripts/ue/import_material_forge_variant.py` accepts only CPU-validated
variants, verifies hashes again, imports BaseColor/Normal/ORM/DetailMasks with
the required UE settings and defaults to unsaved assets.

`scripts/ue/preview_material_forge_canary.py` targets only
`LandscapeComponent_230`, verifies the frozen accepted Sa Calobra map, never
saves the level and restores the original component override on replay.

## Current proof evidence

The source-cache-prime proof on commit
`0ac2afe2d6f929a3f9911e1f4fc8c0f4378b326b` passed:

- pinned source checkout: PASS;
- Godot import/script-class cache creation: PASS;
- Forge authoring: PASS;
- first `aged_mountain_asphalt/base` render: PASS;
- CPU validation of that rendered variant: PASS.

The same commit also removes the reserved GLSL identifier `patch` from the
asphalt shader (`patch_mask` is used instead).

Still required for admission: all nine variants twice, byte determinism, UE
import/compile, canary assignment/rollback, visual review and later whole-area
performance.
