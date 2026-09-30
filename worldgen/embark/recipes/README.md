# Passo Giau Embark-mode terrain recipes

This directory is the repository contract for the external DCC recipe assets used by
issue #287.

The binary recipe files are intentionally **not fabricated by text tooling**. They
must be authored with the real licensed applications and committed through Git LFS:

- `passo_giau_landscape.hiplc` — Houdini Indie HIP containing the two required TOP
  networks and the Gaea2Houdini bridge network;
- `yacs_passo_giau_heightfield.hdalc` — YACS-owned Houdini heightfield utility HDA;
- `passo_giau_landscape.terrain` — Gaea terrain recipe consumed through Gaea2Houdini.

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

## Gaea2Houdini bridge contract

The Houdini HIP must contain the Gaea2Houdini processing/output network at:

- `/obj/yacs_passo_giau_gaea/OUT_GAEA`

The network must use the official Gaea2Houdini integration from SideFX Labs with a
regular activated Gaea Professional/Enterprise installation. A direct custom blur,
home-grown erosion substitute, or opaque Python replacement is not equivalent.

The bridge consumes the PDG-conditioned terrain and produces:

`ExternalAssets/Terrain/PassoGiau/EmbarkPipeline/20_gaea/passo_giau_gaea_shaped.tif`

## Gaea recipe contract

The recipe must follow the official Gaea2Houdini `In > Process > Out` contract:

- create a String variable named `inputHeightfield` with Type = `Input`;
- bind a Gaea File node's Filename property to `inputHeightfield`;
- place the approved shaping/simulation nodes between input and output;
- create a String variable named `outputHeightfield` with Type = `Output`;
- create an Export node with format = `GaeaRaw`, Location = `Explicit`, and bind
  Output Path to `outputHeightfield`;
- expose only the shaping controls that the YACS recipe actually needs.

The Gaea2Houdini SOP must consume that real `.terrain` recipe. The surrounding
Houdini network owns the conversion from the bridge output back to the 32-bit
metric YACS working heightfield written at the configured `gaea_heightfield`
handoff path.

The generated variable JSON is retained as reproducibility evidence; it is not a
replacement for the Gaea2Houdini node contract.

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
2. Houdini/SideFX Labs: install and validate Gaea2Houdini, wire the Gaea terrain
   processor into `/obj/yacs_passo_giau_gaea/OUT_GAEA`, and prove the bridge cooks.
3. Gaea: author the terrain graph, expose the two file variables, configure the
   production build profile, and verify the same recipe can build through Gaea2Houdini.
4. Author `yacs_passo_giau_heightfield.hdalc` with the reusable YACS heightfield
   validation/utility operations required by the final TOP.
5. Commit all binary recipes via Git LFS.
6. Run `scripts/worldgen/embark_terrain_pipeline.py preflight`.
7. Only after preflight passes run the full pipeline and compare rider-view evidence
   against the closed #256 direct-DTM baseline.

This is a fail-closed boundary. Missing recipe binaries are a real blocker, not an
invitation to substitute a NumPy smoothing shortcut.
