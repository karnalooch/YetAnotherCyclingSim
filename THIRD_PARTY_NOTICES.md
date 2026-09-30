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
