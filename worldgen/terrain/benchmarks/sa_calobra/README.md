# Sa Calobra MDT50cm terrain benchmark

This directory contains the selected M3 terrain source for Sa Calobra and Coll
de Cal Reis, Mallorca. It replaces the retired Passo Giau Landscape map as the
active world input, but it does not yet represent Unreal import, visual or
performance acceptance.

## Included output

- `sa_calobra_8x8km_mdt50cm_epsg25831.tif` — Git LFS, 389,039,616 bytes,
  SHA-256 `6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a`;
- `sa_calobra_8x8km_mdt50cm_epsg25831.json` — complete source-file hashes,
  raster contract, statistics, benchmark points, tool versions and license.
- `sa_calobra_road_inventory_2026-10-01.json` — clipped OpenStreetMap road
  inventory totals and the first named-road authoring scope;
- `ROAD_DELIVERY_PRIORITY.md` — bounded P0-P4 authoring order, acceptance gates
  and the explicit local-only Strava evidence boundary.

Raster contract: 16,000 × 16,000 Float32 pixels, one band, 0.5 m spacing,
8,000 × 8,000 m bounds, EPSG:25831, NoData `-32767`, tiled ZSTD compression.

## Rebuild

Download the 17 CNIG files named and hashed by
`scripts/assets/prepare_sa_calobra_mdt50cm.py` into:

```text
ExternalAssets/Terrain/SaCalobra/CNIG_MDT50CM/source/
```

Then run:

```text
python scripts/assets/prepare_sa_calobra_mdt50cm.py --force
```

The tool verifies every source byte before rebuilding the tracked output pair.
The source tiles are intentionally not committed.

## Source and attribution

Source: CNIG/IGN, MDT50 cm — 3ª cobertura, v1 (2022–2025):
https://centrodedescargas.cnig.es/CentroDescargas/modelo-digital-terreno-mdt50cm

License: CNIG general-use license compatible with CC BY 4.0.

Required derived-work attribution:

> Obra derivada de MDT50cm-cob3 2022-2025 CC-BY 4.0 scne.es

Road inventory source: OpenStreetMap contributors, ODbL 1.0:
https://www.openstreetmap.org/copyright

The road summary contains no Strava data or derivative heatmap artifact.

## Official Ma-2141 geometry review

The immutable CartoCiudad REST Geocoder response is retained in
`ma2141_cartociudad_source_2026-10-02.json`; its hash and projected metrics are
recorded in `ma2141_source_review.json`. Service coordinates are EPSG:4326 and
metric review uses EPSG:25831. Attribution: CC BY 4.0
www.scne.es/productos.html#CartoCiudad.

The response has six line parts, including one closed loop that meets other
parts at the same XY. Preserve source vertices and investigate vertical
separation before road carving; never infer both road levels from a single DTM
height. This is a source-review candidate, not admitted canonical route or road
physics. Width, surface and bicycle access remain unknown.

The first bounded alignment diagnostic selects source part 3, vertex 43, with
150 m of source arc length on either side (300 m total). It lies inside the
native terrain window and avoids the unresolved closed-loop junction. The
producer preserves official vertices and linearly densifies only on source XY.
Its Z samples the native terrain and is explicitly not reconstructed asphalt
height. Width, surface and bicycle access remain unknown; no earthworks or
Road Physics Profile admission is granted by this diagnostic.
