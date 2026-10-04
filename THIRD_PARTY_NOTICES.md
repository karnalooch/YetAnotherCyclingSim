# Third-Party Notices

This file records third-party material that is included in, or used as a
reproducible source input for, YetAnotherCyclingSim (YACS).

It is **not** a license for YACS as a whole. The repository currently has no
project-wide open-source license. Do not infer permission to reuse YACS source
code or assets from the licenses listed below.

For the provenance process and reference-only candidates, see
[`docs/legal/DEPENDENCY_PROVENANCE.md`](docs/legal/DEPENDENCY_PROVENANCE.md).

## Poly Haven source assets

Provider: Poly Haven  
License: CC0 1.0  
Source manifest: `scripts/assets/stage3g_polyhaven.json`  
Provider license page: https://polyhaven.com/license

YACS imports only selected source material rather than mirroring complete asset
packs. The repository currently contains Unreal-derived/imported assets from
the following Poly Haven source families:

- `sparse_grass` — Sparse Grass;
- `forrest_ground_03` — Forest Ground 03;
- `rocky_terrain` — Rocky Terrain;
- `boulder_01` — Boulder 01;
- `fir_sapling_medium` — Fir Sapling Medium.

The manifest is the canonical source list. Download tooling writes local source
URLs and checksums into an ignored `download-index.json` before import.

CC0 does not require attribution, but YACS keeps this notice and source metadata
for provenance and reproducibility.

## TINITALY 1.1 terrain data

Dataset: TINITALY 1.1  
Provider: Istituto Nazionale di Geofisica e Vulcanologia (INGV)  
License: CC BY 4.0  
DOI: https://doi.org/10.13127/tinitaly/1.1  
Source tooling: `scripts/assets/download_passo_giau_dem.py`

The raw GeoTIFF is downloaded into gitignored `ExternalAssets/`. The
downloader records the exact WCS request, checksum, license and citation in
local provenance files. Any derived YACS terrain committed from this dataset
must retain the attribution and provenance chain required by CC BY 4.0.

Citation recorded by the YACS downloader:

> Tarquini S., I. Isola, M. Favalli, A. Battistini, G. Dotta (2023).
> TINITALY, a digital elevation model of Italy with a 10 meters cell size
> (Version 1.1). Istituto Nazionale di Geofisica e Vulcanologia (INGV).
> https://doi.org/10.13127/tinitaly/1.1

## CNIG/IGN MDT50cm Sa Calobra terrain benchmark

- Dataset: MDT50 cm — 3ª cobertura, v1 (2022–2025)
- Provider: Centro Nacional de Información Geográfica / Instituto Geográfico Nacional (CNIG/IGN)
- Product page: https://centrodedescargas.cnig.es/CentroDescargas/modelo-digital-terreno-mdt50cm
- License: CNIG general-use license compatible with CC BY 4.0
- License and attribution reference: https://www.scne.es/
- Preparation tooling: `scripts/assets/prepare_sa_calobra_mdt50cm.py`

YACS includes a derived 8 km × 8 km, 0.5 m GeoTIFF benchmark covering Sa
Calobra and Coll de Cal Reis. The 17 original CNIG COG tiles remain outside
Git; their exact filenames, sizes and SHA-256 values are pinned by the
preparation tool. The derived GeoTIFF is stored through Git LFS with its
machine-readable provenance report.

Required attribution retained in the GeoTIFF metadata and report:

> Obra derivada de MDT50cm-cob3 2022-2025 CC-BY 4.0 scne.es

This data is a terrain-research benchmark. Its inclusion is not visual,
performance or production-world acceptance.

## CNIG/IGN Sa Calobra World Data Stack v1 sources

- PNOA LiDAR 3rd coverage, Illes Balears NPC03: 9 LAZ files;
- MDS50cm 3rd coverage COB3 V1: 4 GeoTIFF files;
- PNOA Máxima Actualidad 2024, Illes Balears: 4 source COG files.

Provider: Centro Nacional de Información Geográfica / Instituto Geográfico
Nacional (CNIG/IGN).

License: CNIG/IGN general-use terms compatible with CC BY 4.0.
Exact file identities, provider records, byte sizes and SHA-256 values:
`worldgen/terrain/benchmarks/sa_calobra/world_data/working_space_sources.json`
and `manual_cnig_receipt_2026-10-03.json`.

The raw files remain outside Git. Their verified remote backup is stored in the
unpublished draft release `data-cnig-sa-calobra-working-v1-2026-10-03`; the
public repository does not make that draft an approved public distribution.

Required derivative attribution for LiDAR products:

> Obra derivada de LiDAR-PNOA-cob3 2022-2025 CC-BY 4.0 scne.es

PNOA/MDS/orthophoto derivatives must retain source attribution under the
applicable IGN geographic-data license. These products provide bounded
surface, canopy, object-height and imagery evidence. They do not replace the
accepted ground DTM, canonical road geometry or Road Physics Profile.

## OpenStreetMap Sa Calobra road inventory

- Provider: OpenStreetMap contributors
- Copyright and license: https://www.openstreetmap.org/copyright
- License: Open Data Commons Open Database License 1.0
- Snapshot timestamp: `2026-10-01T20:46:35Z`
- Bounds: WGS84 `2.76258,39.80384,2.85626,39.87588`
- Included summary:
  `worldgen/terrain/benchmarks/sa_calobra/sa_calobra_road_inventory_2026-10-01.json`

YACS includes aggregate road-class lengths and named-road planning totals. Raw
OpenStreetMap geometry is not committed by this benchmark. The summary is a
planning inventory and is not route, physics, surface, access or gameplay
authority.

## Strava Global Heatmap reference not included

The Strava Global Heatmap was inspected locally as a planning reference. YACS
does not include Strava tiles, screenshots, sampled intensity values, ranked
geometry, CSV, GeoJSON or derivative heatmap imagery. The source remains
blocked from copying or derived-data inclusion under the current Strava Terms
of Service and API Policy:

- https://www.strava.com/legal/terms
- https://www.strava.com/legal/api_policy

## Unreal Engine

YACS is built with Unreal Engine. Unreal Engine itself is not vendored in this
repository and remains subject to Epic Games' applicable license terms.

## RoadForge minimal editor donor

Upstream: `YuuhenR/roadforge-osm-ue5-procedural-city`  \
Pinned revision: `781cb046483cc1887e80085aacf0fb2951f4746d`  \
License: MIT  \
Upstream copyright: Copyright (c) 2026 RoadForge Contributors  \
Preserved license: `Plugins/RoadForge/LICENSE`  \
Vendoring note: `Plugins/RoadForge/README.YACS.md`

YACS includes only the editor-target module bootstrap and
`RoadForgeMeshUtils.{h,cpp}` geometry donor surface plus the minimum plugin
build/descriptor files needed to compile it. The donor is not part of the
shipping runtime surface. OSM ingestion, procedural-city
generation, PCG/editor tooling, sample data, screenshots, textures and other
content payloads are not included.

YACS adaptations are limited to the UE 5.8 plugin descriptor/build boundary and
a unity-build-safe module log category. The retained upstream source headers and
MIT permission notice are preserved.

## Reference projects not included

GeoTerrain remains reference-only because the checked revision has unresolved
license-artifact ambiguity. Its current provenance status is tracked in
`docs/legal/DEPENDENCY_PROVENANCE.md`.

## CartoCiudad Ma-2141 source geometry

Source: https://www.cartociudad.es/geocoder/api/geocoder/find?q=Ma-2141

CC BY 4.0 www.scne.es/productos.html#CartoCiudad

The immutable response is included for source/topology review. Metric lengths
and coordinates are derived by projection from service EPSG:4326 to EPSG:25831.
No road width, access, surface or vertical crossing interpretation is added.
License/service coordinate evidence: https://www.cartociudad.es/web/portal/faq

## IGN IGR Redes de Transporte Ma-2141 source review

Source: https://api-features.idee.es/collections/roadlink

Obra derivada de IGR Redes de Transporte, consulta 2026-10-02, CC BY 4.0 scne.es

License: https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf

The pinned OGC API response retains four original features. The bounded
comparison selects `VIAL_TR70190001272`, projects horizontal coordinates into
EPSG:25831 and compares raw third-coordinate numbers with the native DTM.
It does not establish a common vertical datum or asphalt-height authority.
Source `paved`, lane count and `fictitious` attributes remain source claims.


## PNOA Ma-2141 bounded pavement review image

- Provider/product: IGN/CNIG PNOA most-recent orthophoto WMS.
- Source: https://www.ign.es/wms-inspire/pnoa-ma
- License: CC BY 4.0; https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf
- Attribution: Obra derivada de PNOA, consulta 2026-10-02, CC BY 4.0 scne.es.
- Included image: `worldgen/terrain/benchmarks/sa_calobra/ma2141_pnoa_review_2026-10-02.jpg`.
- SHA-256: `4c896f9e64f9e86aa4005d59bd33d46f6b7619dac84cf0201180f4b79b1f20f9`.
- Exact request, CRS/bounds, pixel size and inferred edge observations are recorded
  in the adjacent `ma2141_pavement_preview_profile.json`.
- Status: admitted for bounded visual source review and an inferred contact trial;
  not admitted as survey, height, road-width, access or physics authority.
- Acquisition date and native GSD remain unknown; request date is not flight date.
  Approximate AI-interpreted edge positions have an explicit review allowance,
  not measured statistical accuracy. The generated preview is not road acceptance.

## Bounded BTN / SIOSE / Catastro service evidence

Acquired 2026-10-04 for Issue #335. IGN/CNIG BTN context consists of 30 z16
vector tiles; attribution: Instituto Geográfico Nacional. IGN/CNIG data terms
compatible with CC BY 4.0 apply. SIOSE's current endpoint did not establish the
requested 2014 identity; its diagnostic payload is not admitted geography.

Catastro returned only exception payloads. Its
[INSPIRE access/use license](https://www.catastro.hacienda.gob.es/webinspire/documentos/Licencia.pdf)
permits own use and transformed value-added products, including commercial
use, while disallowing redistribution of the original supplied information.
Raw service responses remain outside Git. This checkpoint includes provenance,
receipts and hashes only, not source-geometry redistribution or derived masks.
