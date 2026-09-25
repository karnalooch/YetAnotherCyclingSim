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
