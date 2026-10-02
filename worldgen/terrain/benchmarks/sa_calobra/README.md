# Sa Calobra MDT50cm terrain benchmark

This directory contains the selected M3 terrain source for Sa Calobra and Coll
de Cal Reis, Mallorca. It replaces the retired Passo Giau Landscape map as the
active world input. Actual native import and diagnostic capture have passed;
human visual and performance acceptance remain pending. See the runtime
evidence below.

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

## Current working AOI (2026-10-02)

The source benchmark is 8 km × 8 km, but the active Unreal terrain import is a
2,016.5 m × 2,016.5 m native-resolution window around Coll dels Reis. This is
the square currently under review; it is not the final world extent.

| Point | EPSG:25831 (E, N) | WGS84 (lat, lon) |
|---|---:|---:|
| SW | 483000.0, 4407500.0 | 39.81731356, 2.80137117 |
| SE | 485016.5, 4407500.0 | 39.81735150, 2.82493195 |
| NE | 485016.5, 4409516.5 | 39.83552023, 2.82488583 |
| NW | 483000.0, 4409516.5 | 39.83548226, 2.80131885 |
| center | 484008.25, 4408508.25 | 39.82641749, 2.81312695 |

Inside that window, the current road work is the bounded 300 m Ma-2141
diagnostic around source part 3 / vertex 43. Its approximate WGS84 endpoints
are 39.82963155, 2.81454613 and 39.83101147, 2.81432764, with the focus vertex
at 39.83040946, 2.81367791. The alignment remains diagnostic-only: road
physics, final pavement geometry, BOB earthworks and collision/ride acceptance
are not admitted by these coordinates.

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

## Runtime evidence and remaining admission

- Run `36967539981`, commit `05a7e92eb6d27bc09c19bc68d0d66e78f08ce732`: full
  CI success, native-reader parity over 16,265,089 samples, 1024 Landscape
  components, native 0.5 m spacing and two edit layers. Its initial checker
  material capture is not the neutral visual acceptance record.
- Run `36968109437`, commit `6bdd8d38357777f7ca97063a3a3cf0fde64e4ef0`: Unreal
  build/Automation, native import, two neutral 3840 x 2160 captures and 300 m
  Ma-2141 native alignment all passed. Overall CI failed in Python dependency
  installation because Shapely 2.1.1 had no Python 3.14 wheel. The follow-up
  pins Shapely 2.1.2 and requires binary wheels.
- Bounded runner retirement in the first run removed 15 positively identified
  Italy payload files totaling 209,775,758 bytes. Its artifact contains the
  inventory and deletion receipt. Shared LFS object storage and Git history
  were not pruned. Repeating retirement produced a zero-file receipt.

No Spanish corridor mesh, BOB earthworks, collision/ride, environment placement
or performance acceptance is established by these artifacts. Human visual
review remains pending. Source width, asphalt-height profile, surface and
bicycle access remain unresolved; do not substitute native DTM heights for
those missing road facts or promote this diagnostic into BOB case memory.

## IGN IGR-RT height and surface candidate

`ma2141_igr_rt_source_2026-10-02.json` preserves the official four-feature OGC
API response, with license and limitations in `ma2141_igr_rt_source_review.json`.
Feature `VIAL_TR70190001272` coincides with the selected CartoCiudad XY within
numerical projection tolerance; this is not independent positional validation.
Its source attributes indicate two lanes and `paved`, but also `fictitious=true`.
Neither lane count nor paved class establishes road width or asphalt composition.

The diagnostic producer now emits a hash-verified IGR-RT comparison alongside
the native alignment. Initial comparison with the captured 300 m diagnostic
gave raw third-coordinate minus DTM values from -1.117 to +2.897, RMS 1.141,
and a maximum piecewise-linear source slope of 0.30044. These are numerical
checks, not measured road/terrain displacement: the third-coordinate datum and
feature-specific accuracy remain unverified. These values must not drive BOB
cut/fill or Road Physics Profile admission.

An accessible IDEIB endpoint exposing 3D road and asphalt-edge layers was
rejected for production inclusion because its service metadata explicitly calls
it preproduction/test-only. The production endpoint returned HTTP 503.
No IDEIB geometry was imported.
