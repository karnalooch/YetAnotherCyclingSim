# Sa Calobra MDT50cm terrain benchmark

This directory contains a bounded terrain-research input for Sa Calobra and
Coll de Cal Reis, Mallorca. It is independent from the canonical Passo Giau
world and does not represent Unreal, visual or performance acceptance.

## Included output

- `sa_calobra_8x8km_mdt50cm_epsg25831.tif` — Git LFS, 389,039,616 bytes,
  SHA-256 `6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a`;
- `sa_calobra_8x8km_mdt50cm_epsg25831.json` — complete source-file hashes,
  raster contract, statistics, benchmark points, tool versions and license.

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
