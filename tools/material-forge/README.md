# YACS Material Forge

Material Forge is the deterministic offline surface-authoring pipeline for YACS Issue #387.

It deliberately does **not** own world semantics:

- **BOB** owns road/terrain geometry and earthworks.
- **PCG/PCGEx** owns classification, placement and authoritative spatial masks.
- **Material Forge** owns PBR surface appearance and material-local detail masks.

The implementation reuses the already-reviewed Material Maker/Godot path from the
Sa Calobra material foundation rather than introducing another renderer or service.

## Entrypoints

Windows:

```powershell
tools/material-forge/material-forge.ps1 --help
```

Portable:

```text
python scripts/assets/material_forge.py --help
```

The first spike authors exactly three material families with at least three
deterministic variants each:

- aged mountain asphalt;
- regional pale limestone;
- dry Mediterranean mineral soil.

Each rendered variant has this contract:

```text
BaseColor.png      sRGB
Normal_DX.png      DirectX tangent-space normal
ORM.png            R=AO, G=Roughness, B=Metallic (phase A requires B=0)
Height.exr         offline authoring/inspection only
DetailMasks.png    material-local R/G/B meanings recorded in provenance
```

`DetailMasks` never carries authoritative biome or placement classification.

## Author graphs

The Material Maker source tree is external and must match the pinned/reviewed
revision recorded in `worldgen/materials/material_forge/upstreams.json`.

```powershell
tools/material-forge/material-forge.ps1 author `
  --material-maker-source D:\tools\material-maker `
  --output D:\yacs\material-forge\run-001
```

The command is fail-closed and refuses an existing run directory. It emits a
`run-manifest.json`, editable `.ptex` graphs, per-variant provenance and the
retained Material Maker MIT notice.

## Render one variant

Rendering uses the reviewed Material Maker source plus Godot, not a YACS runtime
dependency:

```powershell
python scripts/assets/render_material_forge.py `
  --godot D:\tools\godot\godot.exe `
  --source D:\tools\material-maker `
  --variant D:\yacs\material-forge\run-001\aged_mountain_asphalt\base
```

The source runner exports five maps, verifies native decoding and then runs the
CPU gates.

## Validate a complete run

```powershell
tools/material-forge/material-forge.ps1 validate-run `
  D:\yacs\material-forge\run-001
```

Gates include:

- required outputs;
- exact resolution;
- tile-wrap continuity;
- non-empty colour/normal/detail signal;
- non-metallic phase-A contract;
- DirectX normal metadata and vector sanity;
- EXR identity;
- per-map SHA-256;
- semantic ownership guard.

## Determinism

Generate/render a second clean directory with the same source revisions and run:

```powershell
tools/material-forge/material-forge.ps1 compare `
  --left D:\yacs\material-forge\run-001\run-manifest.json `
  --right D:\yacs\material-forge\run-002\run-manifest.json
```

The compare command fails with exit code 2 on any graph/fingerprint/output hash drift.

## Authoritative world-mask packing

Material Forge may pack already-authoritative masks for UE delivery but may not
derive or reclassify them.

Example spec:

```json
{
  "semantic_owner": "PCG/PCGEx",
  "operation": "pack_only",
  "channels": {
    "R": {"name": "Rock", "path": "D:/proof/rock.png"},
    "G": {"name": "Soil", "path": "D:/proof/soil.png"},
    "B": {"name": "Grass", "path": "D:/proof/grass.png"},
    "A": {"name": "Road", "path": "D:/proof/road.png"}
  }
}
```

```powershell
tools/material-forge/material-forge.ps1 pack-world-masks `
  --spec D:\proof\control-0.json `
  --output D:\proof\YACS_Control_0.png `
  --manifest D:\proof\YACS_Control_0.manifest.json
```

The manifest preserves every source mask SHA and records
`classification_changed=false`.

## Unreal import and canary

After CPU validation, set:

```powershell
$env:YACS_MATERIAL_FORGE_VARIANT_DIR = "D:\yacs\material-forge\run-001\regional_limestone\base"
```

Inside the UE Python environment:

```python
import runpy
runpy.run_path(
    r"D:\yacs\project\scripts\ue\import_material_forge_variant.py",
    run_name="__main__",
)
```

By default the assets remain unsaved. Set `YACS_MATERIAL_FORGE_SAVE=1` only when
the exact variant has completed the required UE proof.

For the bounded Sa Calobra consumer proof, use
`scripts/ue/preview_material_forge_canary.py`. It toggles only
`LandscapeComponent_230`, does not save the level and verifies the frozen scene
snapshot before accepting the assignment.

## Tests

Lightweight CPU/unit coverage lives in
`scripts/assets/test_material_forge.py`.

Heavy work intentionally remains outside the authoring commit:

- Godot/Material Maker render replay on the reference host;
- UE material compile/import/canary proof;
- rider-close visual comparison;
- macro repetition inspection;
- performance acceptance.

Those proofs require an exact branch SHA and are planned as the next validation step.
