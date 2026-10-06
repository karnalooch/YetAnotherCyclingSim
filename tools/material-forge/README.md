# YACS Material Forge

Material Forge is the deterministic offline surface-authoring pipeline for YACS Issue #387.

It deliberately does **not** own world semantics:

- **BOB** owns road/terrain geometry and earthworks.
- **PCG/PCGEx** owns classification, placement and authoritative spatial masks.
- **Material Forge** owns PBR surface appearance and material-local detail masks.

## Entrypoints

Windows:

```powershell
tools/material-forge/material-forge.ps1 --help
```

Portable:

```text
python scripts/assets/material_forge.py --help
```

Phase A authors three families with three deterministic variants each: aged
mountain asphalt, regional pale limestone and dry Mediterranean mineral soil.

Each rendered variant contains:

```text
BaseColor.png      sRGB
Normal_DX.png      DirectX tangent-space normal
ORM.png            R=AO, G=Roughness, B=Metallic (phase A requires B=0)
Height.exr         offline authoring/inspection only
DetailMasks.png    material-local R/G/B meanings recorded in provenance
```

`DetailMasks` never carries authoritative biome or placement classification.

## Author graphs

Graph authoring uses the pinned Material Maker 1.7 install directory containing
`nodes/material.mmg` and `material_maker.exe`.

```powershell
tools/material-forge/material-forge.ps1 author `
  --material-maker D:\tools\material-maker-1.7 `
  --output D:\yacs\material-forge\run-001
```

The command refuses an existing run directory and emits editable `.ptex`
graphs, provenance and a run manifest.

## Render one variant

Rendering uses the official Material Maker 1.7 `--export-material` CLI. Godot
4.7.2 is used separately only to natively decode the five outputs and bind its
receipt to their exact SHA-256 values.

```powershell
python scripts/assets/render_material_forge.py `
  --material-maker D:\tools\material-maker-1.7\material_maker.console.exe `
  --godot D:\tools\godot\Godot_v4.7.2-stable_win64.exe `
  --variant D:\yacs\material-forge\run-001\aged_mountain_asphalt\base
```

If the release has no console wrapper, `material_maker.exe` is accepted
directly. Material Maker 1.7's CLI proof is pinned to 2048 output because its
current exporter does not actually honor another parsed `--size` value.

## Validate a complete run

```powershell
tools/material-forge/material-forge.ps1 validate-run `
  D:\yacs\material-forge\run-001
```

Gates include required outputs, exact dimensions, tile-wrap continuity,
non-empty signal, non-metallic contract, DirectX normal sanity, EXR identity,
Godot native decode + exact output hashes, and semantic ownership.

## Determinism

Generate/render a second clean directory and compare:

```powershell
tools/material-forge/material-forge.ps1 compare `
  --left D:\yacs\material-forge\run-001\run-manifest.json `
  --right D:\yacs\material-forge\run-002\run-manifest.json
```

Any graph/fingerprint/output hash drift fails the comparison.

## World-mask boundary

Material Forge may pack already-authoritative PCG/PCGEx masks and may use them
to gate material-local detail. It may not reclassify the world. Receipts preserve
input hashes and record `classification_changed=false`.

## Unreal import and canary

After CPU validation, set `YACS_MATERIAL_FORGE_VARIANT_DIR` to one variant and
run `scripts/ue/import_material_forge_variant.py` inside UE Python. Assets are
unsaved by default.

`scripts/ue/preview_material_forge_canary.py` toggles only
`LandscapeComponent_230`, never saves the accepted map and verifies the frozen
scene snapshot before admitting the assignment.

## Tests and heavy proof

Lightweight CPU/unit coverage lives in
`scripts/assets/test_material_forge.py`. Heavy exact-SHA proof consists of:

- Material Maker release rendering of all 3x3 variants;
- Godot decoder-only native read and hash receipts;
- second clean render + byte determinism comparison;
- UE material compile/import/canary;
- rider-close, grazing, 3x3 repetition and wide visual review;
- later whole-Landscape performance acceptance.
