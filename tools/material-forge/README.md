# YACS Material Forge

Material Forge is the deterministic offline surface-authoring pipeline for YACS Issue #387.

- **BOB** owns geometry and earthworks.
- **PCG/PCGEx** owns classification, placement and authoritative spatial masks.
- **Material Forge** owns PBR surface appearance and material-local detail masks.

## Author

```powershell
tools/material-forge/material-forge.ps1 author `
  --material-maker D:\tools\material-maker-1.7 `
  --output D:\yacs\material-forge\run-001
```

The Material Maker 1.7 install provides the reviewed PBR node definition and
executable identity. Accepted run directories are never silently overwritten.

## Prime the render source

The render runtime is the reviewed Material Maker source commit under pinned
Godot 4.7.2. A clean checkout must first build its Godot import/script-class
cache:

```powershell
Godot_v4.7.2-stable_win64.exe --headless `
  --path D:\tools\material-maker-source `
  --import
```

A valid runtime must contain
`.godot/global_script_class_cache.cfg` and `.godot/imported`.

## Render one variant

```powershell
python scripts/assets/render_material_forge.py `
  --godot D:\tools\godot\Godot_v4.7.2-stable_win64.exe `
  --source D:\tools\material-maker-source `
  --variant D:\yacs\material-forge\run-001\aged_mountain_asphalt\base
```

The renderer exports BaseColor, DirectX Normal, ORM, Height EXR and DetailMasks,
emits a native Godot decode receipt bound to exact SHA-256 values, then runs CPU
validation.

The standalone Material Maker 1.7 `--export-material` binary path is not used
for automation: A/B/C proof showed `0xC0000005` even for an upstream example,
so that crash is independent of Forge graph generation.

## Validate and compare

```powershell
tools/material-forge/material-forge.ps1 validate-run D:\yacs\material-forge\run-001

tools/material-forge/material-forge.ps1 compare `
  --left D:\yacs\material-forge\run-001\run-manifest.json `
  --right D:\yacs\material-forge\run-002\run-manifest.json
```

Any graph or output hash drift fails determinism.

## UE canary

After CPU validation, set `YACS_MATERIAL_FORGE_VARIANT_DIR` and run
`scripts/ue/import_material_forge_variant.py` inside UE Python.
`preview_material_forge_canary.py` is bounded to one Landscape component,
does not save the accepted map and restores its previous override on replay.
