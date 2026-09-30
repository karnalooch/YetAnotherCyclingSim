# Passo Giau Embark-mode terrain recipes

This directory is the repository contract for the external DCC recipe assets used by
issue #287.

The binary recipe files are intentionally **not fabricated by text tooling**. They
must be authored with the real licensed applications and committed through Git LFS:

- `passo_giau_landscape.hiplc` — Houdini Indie HIP containing the two required TOP
  networks;
- `passo_giau_landscape.terrain` — Gaea terrain recipe used by Build Swarm.

YACS does not claim to reproduce Embark's proprietary internal graph. The recipe
must implement the **publicly documented stages** using official Houdini/Gaea
capabilities and YACS-owned data contracts.

## Houdini HIP contract

The HIP must contain both TOP networks:

- `/tasks/yacs_passo_giau_preprocess`
- `/tasks/yacs_passo_giau_finalize`

### Preprocess TOP

Inputs:

- original MASE PST DTM tiles and download report;
- original Veneto 5 m fallback tiles and download report;
- fixed Passo Giau AOI and EPSG:32632 spatial contract;
- SP638 protected corridor data when required for terrain-shaping masks.

Required output:

`ExternalAssets/Terrain/PassoGiau/EmbarkPipeline/10_pdg/passo_giau_pdg_conditioned.tif`

Output contract:

- single-band 32-bit float GeoTIFF;
- EPSG:32632;
- exact 8 km x 8 km Passo Giau bounds from the JSON pipeline contract;
- finite values across the AOI;
- native cell size <= 2 m;
- source masks/reconciliation evidence preserved in the pipeline work area;
- no mutation of canonical SP638 XY or physics data.

The exact source-reconciliation algorithm is YACS-owned and must be justified by
measured source-boundary diagnostics. Do not invent or attribute proprietary
Embark parameters.

### Finalize TOP

Input:

`ExternalAssets/Terrain/PassoGiau/EmbarkPipeline/20_gaea/passo_giau_gaea_shaped.tif`

Required output:

`ExternalAssets/Terrain/PassoGiau/EmbarkPipeline/30_houdini/passo_giau_final_heightfield.tif`

The final TOP validates/normalizes the Gaea result for Unreal Landscape handoff. It
must not silently reposition the route, change CRS, or replace source provenance.

## Gaea recipe contract

The recipe must expose exactly these pipeline variables:

- `inputHeightfield`
- `outputHeightfield`

Build Swarm receives them through a generated JSON variable file.

The recipe is allowed to shape presentation terrain, but it must preserve the route
corridor mask/constraints supplied by the Houdini preprocessing stage. It must not
become route or physics authority.

Required output:

- 32-bit terrain format that Houdini can read without reducing vertical precision;
- deterministic build for seed `0`;
- same metric AOI and elevation meaning as the input;
- no baked road centerline displacement.

## Creation rule

Create and validate the recipes once in their native UIs before automation:

1. Houdini: author the HIP/TOP networks and prove both networks cook successfully.
2. Gaea: author the terrain graph, expose the two file variables, configure the
   production build profile, and use **Copy Command Line** to verify the Build Swarm
   invocation.
3. Commit the binary recipes via Git LFS.
4. Run `scripts/worldgen/embark_terrain_pipeline.py preflight`.
5. Only after preflight passes run the full pipeline and compare rider-view evidence
   against the closed #256 direct-DTM baseline.

This is a fail-closed boundary. Missing recipe binaries are a real blocker, not an
invitation to substitute a NumPy smoothing shortcut.
