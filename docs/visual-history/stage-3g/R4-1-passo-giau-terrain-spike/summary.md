# Stage 3G R4.1B — Passo Giau terrain source/preparation evidence

**Status:** source/preparation proof accepted; Unreal visual import pending  
**Date:** 2026-09-28  
**Parent plan:** [Stage 3G R4.1 Alpine Visual Recovery](../../../STAGE3G_R4_1_ALPINE_VISUAL_RECOVERY.md)  
**Next implementation issue:** #213 — R4.1B isolated Unreal Landscape spike

## Purpose

Record the reproducible remote evidence that the selected Passo Giau DEM can be
downloaded, validated and converted into an Unreal-friendly heightmap candidate.

This record is not a visual acceptance of the final world.

## Source

- dataset: TINITALY 1.1;
- provider: INGV;
- license: CC BY 4.0;
- AOI: approximately 8 x 8 km around Passo Giau;
- raster: 800 x 800;
- source resolution: 10 m;
- CRS: EPSG:32632;
- DEM SHA-256: `9a58a8aca8b1856507b4ca3e656f8c975518cbd89bd273036ef2483c148db610`.

## Remote execution

GitHub Actions run: **36357523138 — PASS**.

Artifact:

`passo-giau-r4-1-terrain-spike`

The artifact contains the preparation evidence and generated candidates; raw
external terrain is intentionally not committed into the repository.

## Observed terrain

| Metric | Value |
|---|---:|
| Minimum elevation | 1171.353 m |
| Maximum elevation | 2713.832 m |
| Relief | 1542.479 m |
| Mean elevation | 1993.256 m |

## Prepared outputs

- `passo_giau_height_native_u16.png`;
- `passo_giau_height_ue_landscape_1009_u16.png`;
- `passo_giau_height_ue_landscape_1009.r16`;
- `passo_giau_hillshade.png`;
- `terrain-report.json`.

Recommended candidate import parameters:

- Landscape vertices: **1009 x 1009**;
- XY scale: **793.651 cm/vertex**;
- Z Scale: **301.265**.

The 1009 raster is resampled for an Unreal-compatible topology. It does not add
terrain detail beyond the 10 m source.

## Repository provenance

- PR #211 merged DEM bootstrap as `7db3a63e11b83c3d33f86f80e1d6687c05b8ea78`;
- PR #212 merged terrain preparation pipeline as `a98162fd590c5d3dc597a5c625d70e9860bb46c7`;
- downloader: `scripts/assets/download_passo_giau_dem.py`;
- preparation: `scripts/assets/prepare_passo_giau_heightmap.py`;
- workflow: `.github/workflows/passo-giau-r4-1-terrain-spike.yml`.

## Acceptance boundary

Accepted here:

- official source can be fetched remotely;
- payload validates as GeoTIFF;
- provenance/checksum is recorded;
- UE-friendly 16-bit outputs can be produced reproducibly;
- terrain has substantial natural macro relief.

Not accepted yet:

- Unreal Landscape import;
- rendered visual quality;
- road/terrain integration;
- PCG composition;
- performance in UE;
- canonical 1200/4900/8000 Visual History captures.

## Next gate

Issue #213 must create an **isolated** Unreal Landscape spike. The canonical
`L_CyclingTest` map and authoritative `FRouteGeometryProfile` remain untouched.

A rendered proof must be reviewed before the real DEM path can replace or extend
the existing R4 presentation terrain.
