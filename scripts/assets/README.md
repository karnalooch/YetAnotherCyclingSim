# Stage 3G source-asset bootstrap

This folder contains the **manifest and downloader**, not the downloaded binary assets.

The Stage 3G bootstrap uses a small curated set of Poly Haven assets for the reference-environment pass:

- valley meadow ground;
- forest floor;
- high-Alpine rocky ground;
- rock face and boulder dressing;
- a mid-ground mountainside candidate;
- a fir-tree baseline;
- a grass-clump baseline.

All selected Poly Haven assets are CC0. The live Poly Haven API resolves current download URLs, sizes and MD5 hashes. Its API terms require a unique User-Agent and clear credit to Poly Haven; the downloader provides both.

## Usage

From the repository root on the home PC:

```powershell
py scripts/assets/download_stage3g_assets.py --list-only
py scripts/assets/download_stage3g_assets.py
```

The default is **2K** source textures and FBX model geometry. Downloads go to:

```text
ExternalAssets/Stage3G/PolyHaven/
```

`ExternalAssets/` is intentionally gitignored. Source downloads must not be committed wholesale. Only assets actually imported and validated for Stage 3G should later become Unreal project assets under `Content/` and be tracked by the existing Git LFS rules.

Useful options:

```powershell
# One asset only
py scripts/assets/download_stage3g_assets.py --asset rock_face_01

# Smaller source textures for a quick experiment
py scripts/assets/download_stage3g_assets.py --resolution 1k

# Re-download even when the cached file matches Poly Haven's MD5
py scripts/assets/download_stage3g_assets.py --force

# Raise the safety cap deliberately if provider metadata exceeds 1.5 GiB
py scripts/assets/download_stage3g_assets.py --max-total-mib 2500
```

## Independent Texture Material Prep foundation

`texture_material_prep.py` analyzes immutable opaque 8-bit sRGB PNG BaseColor
inputs, writes bounded 2x2/4x4 tiling evidence and seam/luminance metrics, and
prepares validated draft Texture Graph recipes. It never processes production
pixels, connects to Unreal or changes existing assets. Recipes explicitly remain
blocked in this offline CLI until a live UE connection binds the execution.
The opt-in `YacsTexturePrep` plugin implements the separate editor adapter.
`texture_material_prep_bundle.py` measures its five-map export;
`texture_material_prep_ue_smoke.py` and `texture_material_prep_ue_reopen.py` run
only in a marked disposable proof project. `restore_texture_prep_checkpoint.py`
verifies the dedicated #382 single-archive recovery manifest (safe member names,
exact member set, per-file size/SHA-256 and archive identity) and restores only
to an empty isolated directory; it does not consume the separate workspace-data
manifest format.

See the [commands and supported subset](../../docs/tooling/TEXTURE_MATERIAL_PREP_EXAMPLES.md)
and [architecture / limestone proof plan](../../docs/tooling/TEXTURE_MATERIAL_PREP.md).
Evidence goes to a fresh ignored `Saved/RuntimeProof/TextureMaterialPrep/` run.
Run `python scripts/assets/test_texture_material_prep.py` for synthetic checks.

## Safety / validation boundary

The downloader does **not** import anything into Unreal Engine, create `.uasset` files, choose Nanite/LOD settings, modify the Stage 3 map, scatter foliage, or change gameplay/route logic.

Before a downloaded model becomes part of Stage 3G, validate on the home PC:

1. scale, pivot and orientation;
2. material/texture wiring (DirectX normal map for UE);
3. collision requirements;
4. available LODs and practical triangle cost;
5. instancing behavior for repeated props/foliage;
6. RAM/VRAM and 1080p performance impact;
7. visual fit with the Stage 3G reference target.

The manifest is the reproducible source list. The downloader writes a local `download-index.json` with exact source URLs, MD5 values and local paths for each resolved run.


## Passo Giau terrain bootstrap — Stage 3G R4.1

R4.1 can evaluate a real Alpine macro-terrain source without making external
terrain authoritative for route physics. The bootstrap uses the official
**TINITALY 1.1** bare-earth DTM from INGV:

- native grid: 10 m;
- format: GeoTIFF via WCS;
- CRS: EPSG:32632 (WGS84 / UTM zone 32N);
- license: CC BY 4.0;
- default AOI: 8 x 8 km centred on Passo Giau.

From the repository root:

```powershell
# Inspect the exact WCS request without writing files
py scripts/assets/download_passo_giau_dem.py --dry-run

# Download/cache the default 8 x 8 km / 10 m source GeoTIFF
py scripts/assets/download_passo_giau_dem.py

# Replace an existing cached source
py scripts/assets/download_passo_giau_dem.py --force
```

Downloads go to:

```text
ExternalAssets/Terrain/PassoGiau/TINITALY_1_1/
```

The downloader writes:

- the GeoTIFF source;
- `download-index.json` with the exact WCS request, AOI, checksum and provenance;
- `SOURCE_AND_LICENSE.txt` with attribution/citation requirements.

`ExternalAssets/` is already gitignored. Do not commit the raw DEM wholesale.
A later R4.1 authoring task may derive a bounded Unreal-friendly heightfield or
terrain mesh and validate that result independently.

The downloader deliberately rejects requests below the native 10 m resolution:
asking the WCS for a denser output grid would only upsample the source data.

TINITALY citation:

> Tarquini S., I. Isola, M. Favalli, A. Battistini, G. Dotta (2023).
> TINITALY, a digital elevation model of Italy with a 10 meters cell size
> (Version 1.1). Istituto Nazionale di Geofisica e Vulcanologia (INGV).
> https://doi.org/10.13127/tinitaly/1.1

This downloader does **not** modify the Stage 3 map, route geometry, road physics,
PCG graphs or Unreal assets.


### Preparing the Passo Giau heightmap

After the source GeoTIFF exists, prepare the R4.1 Unreal import candidates:

```powershell
py -m pip install numpy==2.2.6 Pillow==11.3.0 rasterio==1.4.3
py scripts/assets/prepare_passo_giau_heightmap.py
```

The default prepared output is written to the ignored directory:

```text
ExternalAssets/Terrain/PassoGiau/Prepared/
```

Outputs include:

- native-resolution unsigned 16-bit PNG;
- 1009x1009 Unreal Landscape candidate PNG;
- matching little-endian `.r16`;
- grayscale hillshade preview;
- `terrain-report.json` with source bounds, elevation distribution and
  recommended Unreal XY/Z transform values.

The 1009x1009 candidate is intentionally **resampled** to a standard Landscape
vertex resolution. It does not create terrain detail beyond the original 10 m
TINITALY source.

The GitHub Actions workflow
`.github/workflows/passo-giau-r4-1-terrain-spike.yml` is intentionally treated as a manual-merge governance change and performs the full remote
download + preparation and publishes the prepared files as the
`passo-giau-r4-1-terrain-spike` artifact.


## YACS World Authoring Library

Issue #230 adds a semantic layer above the existing curated downloader. It does
not replace the Stage 3G manifest/downloader; it reuses the same Poly Haven
file-resolution, size/MD5 verification and ignored-source-cache rules.

The first preset can be resolved with:

```powershell
python scripts/assets/yacs_asset_library.py `
  --preset worldgen/presets/alpine_roadside_grove_v1.json `
  --live-discovery `
  --output Saved/RuntimeProof/world_asset_selection_plan.json
```

To prove the acquisition/cache path as well:

```powershell
python scripts/assets/yacs_asset_library.py `
  --preset worldgen/presets/alpine_roadside_grove_v1.json `
  --live-discovery `
  --download `
  --output Saved/RuntimeProof/world_asset_selection_plan.json
```

The semantic catalog is `worldgen/assets/catalog.json`. Automatic acquisition
is currently fail-closed to the declared Poly Haven provider and CC0 policy.
Provider discovery does not automatically qualify an asset for Unreal use: a
new candidate still requires import, scale/pivot/material, visual and
performance validation before it may receive an approved catalog entry.

See `docs/YACS_WORLD_AUTHORING_LIBRARY.md`.
