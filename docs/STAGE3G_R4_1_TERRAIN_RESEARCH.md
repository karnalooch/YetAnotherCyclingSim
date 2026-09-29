# Stage 3G R4.1 — Terrain / Landscape research playbook

**Status:** active working research for R4.1B  
**Scope:** Passo Giau DEM -> Unreal Engine 5.8 Landscape visual-quality diagnosis  
**Rule:** this document informs presentation only; route/physics truth remains independent.

## 1. Why this exists

R4.1B has now proven both the original bootstrap path and the higher-resolution
active Landscape path.

Historical merged baseline:

- TINITALY 1.1 / INGV, 800x800 at 10 m;
- deterministic 1009x1009 R16 candidate;
- licensed source/provenance and remote preparation proof on `main`.

Active PR #215 candidate:

- MASE PST, `LiDAR DTM grigliato 1x1`, CC BY 4.0;
- immutable GitHub prerelease source checkpoint, 853,162,557 bytes;
- SHA-256 `4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c`;
- 204 official Float32 GeoTIFF DTM tiles; every raster is `*_DTM.tiff`, with zero DSM tiles;
- source CRS EPSG:4326 with pinned observed pixel spacings of 0.00001 and 0.000005 degrees;
- explicit metric reprojection to EPSG:32632 before any UE resampling;
- 8000x8000 / 1 m metric working grid for the bounded 8 km AOI;
- deterministic 4033x4033 unsigned-16 / little-endian R16 presentation grid;
- 32x32 components / 1024 components remain the UE topology target;
- the isolated map remains protected from `L_CyclingTest` and route/physics truth;
- fresh MASE exact-SHA UE authoring/render proof is required; previous GREEN
  authoring runs are Veneto 5 m historical evidence, not acceptance of this source.

The remaining problem is **visual interpretation and level-design use**, not
"make CI green".

The earlier 1080p proof contained dense repetitive herringbone/striping. The
4K/FXAA diagnostic substantially reduces that pattern while the source and
prepared 4033 hillshades remain natural. Screen-space aliasing was therefore a
real contributor.

Visible stepping/ribbing remains on very steep cliff faces. That residual is
now treated primarily as a heightfield/spatial-resolution representation
constraint until disproven, not as evidence that the uint16 encoding is broken.

Do not hide unresolved geometry with broad blur, production vegetation,
post-processing or Nanite.


### P0 source gate — MASE PST LiDAR DTM 1x1 acquired (2026-09-28)

**Source correction:** package `1372707` / 89 tiles was an earlier partial
checkpoint and is now **superseded**. The canonical DTM-only package is
`1372858`: 204 GeoTIFFs, all `*_DTM.tiff`, zero DSM tiles.

The source-resolution gate is now **resolved for Passo Giau** by a pinned
official source-data checkpoint mirrored as a GitHub prerelease outside Git/LFS.

Canonical source checkpoint:

- provider: Ministero dell'Ambiente e della Sicurezza Energetica (**MASE**);
- program/product: PST / `LiDAR DTM grigliato 1x1`;
- release tag: `data-mase-pst-passo-giau-dtm-2026-09-28`;
- archive: `MASE_PST_8309f0171e3340c6aba45798c4812d54_1372858_DTM.zip`;
- archive size: **853,162,557 bytes**;
- archive SHA-256:
  `4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c`;
- contents: **204 GeoTIFF DTM tiles**, all `*_DTM.tiff`; zero DSM tiles;
- raster contract: Float32, source-defined tile dimensions, NoData `-9999`; the pinned package is heterogeneous, so fixed 1000 x 1000 dimensions are explicitly not required;
- raster CRS: **EPSG:4326**;
- observed pixel sizes: `0.00001 x 0.00001` and `0.000005 x 0.000005` degrees; the package is heterogeneous and each tile must match one of these pinned square-pixel variants, approximately
  **0.76 x 1.11 m near Passo Giau**;
- exact AOI/tile-union coverage is re-derived from the 204-tile package during
  the fresh preparation proof rather than inherited from superseded package
  `1372707`;
- license checkpoint: **CC BY 4.0**.

The raw release is immutable source evidence. It is not committed to Git/LFS and
must never be rewritten by the terrain-preparation pipeline.

**Critical coordinate rule:** `0.00001 degrees` is not `1 metre`. EPSG:4326
longitude/latitude samples must never be interpreted as a metric grid. The
active authoring path explicitly reprojects the source to a metric CRS before
any UE Landscape resampling.

Canonical active preparation path:

`pinned release asset -> byte-size/SHA-256 verification -> extract 204 GeoTIFFs -> mosaic -> explicit EPSG:4326 -> EPSG:32632 reprojection -> bounded 8 km AOI at a 1 m metric working grid -> controlled cubic resample to 4033 -> UInt16/R16 -> isolated L_PassoGiauTerrainSpike`.

The established 8 km Landscape extent is shifted only **40 m south** while
keeping the same 8 km size and therefore the same **198.412698 cm/vertex** UE XY
scale. This keeps the rotated UTM square inside the immutable source
tile-union north edge instead of filling an uncovered strip.

### Current decision

- **MASE PST DTM 1x1 is the canonical source path for PR #215.**
- Veneto LiDAR-derived **5 m** remains a reproducible fallback and A/B baseline.
- The Veneto Olympic **2 m** WebGIS investigation remains useful historical
  lineage evidence, but is no longer the blocker for obtaining higher-resolution
  raw elevation samples for Giau.
- Existing GREEN Veneto authoring/render runs remain historical proof only.
  A fresh exact-SHA MASE authoring run and human visual review are required
  before PR #215 can leave Draft.
- Route/physics authority remains unchanged; this is presentation-only terrain.

### Historical P0 source gate — Cortina 2021 LiDAR / 2 m WebGIS contract (resolved by MASE source checkpoint)

> Historical record only. The current source decision is the MASE PST section above.
> Statements below about the “next gate” or “until then” describe the state before
> the immutable MASE 1x1 package was acquired.

The source-resolution decision is upstream of further terrain art, but the
research now distinguishes **LiDAR acquisition density**, **DTM product
resolution**, and **WebGIS display/derivative resolution** instead of treating
the label `2m` as proof of native terrain samples.

Official Veneto evidence establishes the acquisition context:

- the Cortina + neighboring-municipalities project covers Cortina d'Ampezzo,
  Colle Santa Lucia, Borca di Cadore, Selva di Cadore and San Vito di Cadore;
- the commissioned airborne LiDAR density was **4 points/m²** with production
  of both DSM and DTM over about **39,010 ha**;
- Veneto's 2026 Olympic WebGIS portfolio describes the 2021 LiDAR-derived DTM,
  DSM and CHM as **"ricampionati a 2m"** — resampled to 2 m.

Primary references:

- Regione del Veneto DGR / BUR project:
  https://bur.regione.veneto.it/BurvServices/Pubblica/DettaglioDgr.aspx?id=426837
- Regione del Veneto Olympic 2026 WebGIS portfolio:
  https://idt2.regione.veneto.it/portfolio/webgis-olimpiadi-2026-in-veneto/
- Olympic viewer:
  https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=86

The Olympic viewer exposes the display label `DTM_2m_Cortina`. Live WMS
discovery identifies its raw-looking technical layer as **`rv:DTM_2m_clip`**.
Its advertised WGS84 extent is approximately:

`11.988525 .. 12.258246 E, 46.461630 .. 46.675067 N`

and therefore contains the Passo Giau reference point
`12.05321 E, 46.48284 N`.

The WMS layer advertises **EPSG:6876 / RDN2008 Zone 12 (N-E)** plus CRS:84.
EPSG:6876 uses Northing/Easting axis order; **EPSG:7795 is the corresponding
GIS-oriented Easting/Northing form**. YACS may prefer 7795 as a working GIS
CRS, but source-axis order must be handled explicitly and never inferred from
numeric similarity.

Live evidence is generated by:

- `scripts/assets/probe_passo_giau_cortina_2m.py`;
- `scripts/assets/test_probe_passo_giau_cortina_2m.py`;
- `.github/workflows/passo-giau-cortina-2m-probe.yml`.

The probe is fail-closed. Source-contract run
**36453219301 / probe #26** established the terminal WCS behavior across the
full alias/version matrix; the subsequent optimized probe preserves that
evidence while fast-failing a disabled endpoint.

The source contract proves:

- the official Olympic portfolio describes the 2021 DTM/DSM/CHM as
  **resampled to 2 m**;
- the official Olympic viewer is tracked separately as **WebGIS 86**; its
  initial anonymous HTML is only a client shell, so neither the dynamic layer
  list nor the portfolio-to-viewer navigation is inferred from that raw HTML;
- the WMS source identity and Passo Giau geographic coverage;
- the derivative family `DTM_2m_clip_hillshade`,
  `DTM_2m_slope_recl_clip` and `DTM_2m_aspect_recl_clip` exists over the
  same area;
- the raw-looking WMS layer exposes no WMS `MetadataURL` or `DataURL`;
- WMS `DescribeLayer` classifies `rv:DTM_2m_clip` as WCS-backed;
- both tested public WCS endpoints — global and `rv` workspace — return the
  terminal GeoServer error **`Service WCS is disabled`** for direct
  `DescribeCoverage` probes;
- run #26 exercised the known layer aliases against WCS 2.0.1, 1.1.1 and
  1.0.0 before the probe was optimized to short-circuit this terminal
  endpoint-level error;
- Veneto's anonymous generic download catalog is reachable and currently
  exposes 932 downloadable layers, but contains neither
  `DTM_2m_Cortina` nor `DTM_2m_clip`;
- the public CSW 2.0.2 catalog returns 0 exact records for both identifiers;
- Veneto's public downloader JavaScript exposes a first-party
  `getDtmLidar5ByProvincia` / `getDtmLidar5ByComune` /
  `downloadDtmLidar5` transport contract for the established **5 m** LiDAR
  DTM product, but no equivalent public 2 m DTM transport has been identified.

### Decision

The Cortina dataset is now classified as:

**high-density 2021 LiDAR acquisition -> official DTM/DSM products -> Olympic
WebGIS derivatives resampled to 2 m.**

It is **not** classified as a proven native 2 m elevation source.

The 2 m candidate is therefore **not approved for UE height authoring**. We
have proven its official viewer/WMS publication and geographic relevance, but
we have not proven an official lossless/raw DTM distribution preserving
elevation samples. Public WCS is explicitly disabled.

WMS `GetMap` output must not be treated as elevation data. A rendered map
interface does not prove preservation of raw DEM sample values, and a 2 m WMS
label does not create measurement detail absent from the source product.

The next gate is intentionally narrow: obtain a documented official raw DTM
distribution for the 2021 Cortina acquisition (GeoTIFF/ASC or equivalent), or
provider metadata that identifies such a distribution. Do not guess sibling
filenames, scrape styled WMS pixels, or infer a hidden DTM download merely from
other published derivatives.

If such a raw source is obtained, prove:

1. actual raster geotransform / cell spacing;
2. elevation datatype and NoData contract;
3. CRS, axis order and vertical datum;
4. license/provenance;
5. complete Passo Giau/SP638 AOI coverage;
6. immutable source hash;
7. whether the raster is native to the DTM production chain or itself a
   provider-side resample.

Only then may the deterministic A/B preparation path proceed:

`verified raw DTM -> one deliberate GIS crop/reproject/resample -> 4033 Float -> UInt16/R16 -> UE`.

Until then:

- the existing Veneto **5 m** pipeline remains the reproducible terrain
  baseline;
- the 2 m WebGIS path remains a **documented blocked source candidate**, not a
  hidden TODO to brute-force;
- no GIS work moves into PR #224 / the local-mesh path;
- road cut/fill, cliffs/scree and materials may be evaluated against the 5 m
  baseline, but any claim that 2 m has already solved the steep-face problem is
  prohibited by the source evidence.


## 2. Hard facts from Epic documentation

### Valid 4033 topology

Epic's Landscape Technical Guide supports the same 63-quad section /
2x2-subsection component pattern used by the current candidate.

For the active 4033x4033 Passo Giau Landscape:

- 63 quads per section;
- 4 sections per component (2x2);
- 126x126 quads per component;
- 1024 components (32x32);
- 4033 vertices per side = 32 * 126 + 1.

That matches the current R4.1B topology.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

### Height precision and Z scale

Epic documents the Landscape height domain as approximately -256..+255.992
local height units stored with 16-bit precision, with the imported height then
scaled by Landscape Z scale.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

For the active Veneto source proof:

- source min: 1168.833 m;
- source max: 2715.996 m;
- relief: 1547.163 m;
- encoded range: 65536 possible uint16 levels;
- prepared 4033 raster: 64756 unique uint16 values;
- exact-flat adjacent-sample share: about 0.026%.

The ideal full-range vertical quantization is therefore approximately:

`1547.163 m / 65535 ~= 0.02361 m`

or about **2.36 cm per encoded level**.

This is far smaller than the visually obvious large terraces in the current
proof. Therefore "16-bit is inherently too coarse" is **not** an acceptable
root-cause conclusion without additional evidence.

### Supported formats

Epic explicitly supports:

- 16-bit grayscale PNG;
- 8-bit r8;
- 16-bit r16.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/importing-and-exporting-landscape-heightmaps-in-unreal-engine

### Native import API

`ALandscapeProxy::Import` accepts imported height data as
`TMap<FGuid, TArray<uint16>>`.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Landscape/ALandscapeProxy/Import

The editor also exposes `FLandscapeImportHelper` and the Landscape file-format
interfaces. These are useful as an A/B oracle against our manual R16 reader.

References:

- https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/LandscapeEditor/FLandscapeImportHelper
- https://dev.epicgames.com/documentation/unreal-engine/creating-custom-landscape-importers-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/API/Editor/LandscapeEditor/ILandscapeFileFormat

## 3. Current observation: screen aliasing is separated from residual geometry

The commandlet still keeps production terrain materials out of the proof:

`Landscape->LandscapeMaterial = nullptr;`

The latest capture additionally enforces:

- Landscape LOD0;
- lighting-only view mode;
- proof sun shadows disabled;
- 3840x2160 spatial capture;
- deterministic high-quality FXAA.

Compared with the earlier 1920x1080 proof, the dense herringbone/striping is
substantially reduced. That is direct evidence that the old screenshot
overstated terrain defects because of screen-space/render aliasing.

What remains is concentrated on steep cliff faces: staircase/rib structures
that are plausible consequences of representing a steep 5 m DTM as a
single-valued Landscape heightfield. The 4033 grid is a presentation resample
to about 1.98 m/vertex; it does **not** create new measured detail beyond the
native 5 m source.

### Production trap: Landscape grid density is not source-data resolution

**Do not confuse the 4033x4033 Unreal Landscape grid with a 2 m measured DEM.**

For the current 8 km extent:

- 4033 Landscape vertices imply about **1.98 m/vertex** in Unreal;
- the authoritative Veneto DTM still contains measured terrain information at
  **5 m source spacing**;
- vertices introduced by resampling between native samples are interpolated;
- the denser Unreal grid improves editability, spline/patch shaping and
  representation of authored local changes, but it does **not** create new
  surveyed geological detail.

Consequences:

- never describe the active source as a "2 m DEM";
- never justify a full terrain restart solely because the UE grid is denser
  than the source;
- evaluate source sufficiency from visible macro-form errors that remain after
  the road-corridor and environment-art passes, not from vertex count alone;
- Nanite/LOD changes cannot manufacture source detail that was never measured.

This is a permanent production guardrail for R4.1 and later terrain work.

### Priority discovery — Cortina 2 m LiDAR DTM + QGIS/GDAL geospatial SSOT

Research on 2026-09-28 found a materially better source candidate than the
regional harmonized 5 m baseline.

The Regione del Veneto commissioned a dedicated aerophotogrammetric + airborne
LiDAR survey for:

- Cortina d'Ampezzo;
- Colle Santa Lucia;
- Borca di Cadore;
- Selva di Cadore;
- San Vito di Cadore.

The official procurement specifies **4 LiDAR points/m²** and production of both
DSM and **DTM** products over 39,010 ha. This is directly relevant to the
SP638 / Passo Giau AOI because the survey explicitly covers Cortina and the
neighboring municipalities around the pass.

Official source:
https://bur.regione.veneto.it/BurvServices/Pubblica/DettaglioDgr.aspx?id=426837

The current Veneto geoportal exposes a layer named **`DTM_2m_Cortina`**. This
is now the **priority higher-resolution terrain-source candidate** for YACS.
Before promotion to canonical input, the exact downloadable AOI must still be
verified for:

- complete SP638 / Passo Giau coverage;
- source metadata and acquisition date;
- CRS / vertical datum;
- license / reuse terms;
- NoData behavior and tile boundaries;
- actual raster cell size and datatype.

Geoportal viewer:
https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=246

The regional harmonized LiDAR-derived DTM remains a valid historical/baseline
source and is officially published at **5 m cells**:
https://idt2.regione.veneto.it/nuovo-dtm-derivato-da-dati-lidar/

#### Why this changes the current diagnosis

For the current approximately 8 km x 8 km AOI:

- 2017 vertices imply `8000 / 2016 ~= 3.968 m/vertex`;
- 4033 vertices imply `8000 / 4032 ~= 1.984 m/vertex`.

A 4033 Landscape generated from the existing 5 m DTM is still an interpolation
of 5 m measurements. It does **not** become a 2 m measured DEM.

If `DTM_2m_Cortina` verifies as a genuine ~2 m raster over the required AOI,
then a 4033 x 4033 Landscape at ~1.984 m/vertex becomes a near one-to-one match
between source sampling scale and UE Landscape vertex spacing. That makes the
2 m source a decisive A/B test for the remaining Minecraft-like faceting.

This does not invalidate the permanent grid-alignment guardrail. Road XY,
terrain raster cells and Unreal Landscape vertices remain independent data
domains and must never be snapped together merely because their nominal spacing
is similar.

#### QGIS/GDAL becomes the geospatial master pipeline

YACS should move terrain preprocessing out of ad-hoc Unreal runtime repair and
into a deterministic GIS stage.

Preferred responsibility split:

1. **QGIS/GDAL = geospatial SSOT and preprocessing**
   - DEM acquisition and provenance;
   - CRS normalization;
   - AOI crop;
   - NoData cleanup;
   - orthophoto / road / future biome masks in the same metric CRS;
   - one deliberate reprojection/resample;
   - Float32/Float64 terrain working products;
   - final UInt16 Landscape transport encoding.

2. **Unreal Landscape = rendered macro heightfield**
   - consumes the prepared heightmap;
   - does not repair source sampling defects;
   - does not redefine road XY.

3. **SP638 spline + road corridor geometry = road engineering**
   - road bench;
   - shoulders;
   - cut/fill;
   - retaining / drainage / local transition geometry.

4. **Meshes/PCG/materials = non-heightfield geology and dressing**
   - cliffs / overhangs;
   - rock faces / scree;
   - vegetation and surface breakup.

Use a metric east/north coordinate system throughout the working GIS pipeline.
**EPSG:7795 — RDN2008 / Zone 12 (E-N)** is the current preferred candidate
because its axes are Easting/Northing in metres. The downloaded source metadata
remains authoritative and must be checked before any reprojection.

Reference:
https://epsg.io/7795

#### Preserve floating-point elevation until the transport boundary

Do **not** render/export a QGIS visualization and treat that image as DEM data.

Keep the terrain raster in Float32/Float64 through acquisition, crop, reprojection
and source comparison. Convert to UInt16 only at the final Unreal transport
step.

GDAL explicitly supports target resolution and resampling algorithms including
`bilinear`, `cubic`, `cubicspline` and `lanczos`:
https://gdal.org/en/stable/programs/gdalwarp.html

The R4.1 source experiment must resample/reproject only once. For elevation,
test at least `cubic` and `cubicspline`; do not silently chain multiple
resize/reprojection stages.

A representative final encoding contract is:

```text
gdal_translate \
  -ot UInt16 \
  -scale MIN_ELEV MAX_ELEV 0 65535 \
  -exponent 1 \
  -of PNG \
  dem_final_float.tif \
  yacs_height_4033.png
```

`MIN_ELEV` and `MAX_ELEV` must be deliberate AOI bounds with documented
headroom where required, not accidental extrema from a NoData/outlier cell.

GDAL reference:
https://gdal.org/en/stable/programs/gdal_translate.html

Epic supports 16-bit Landscape height data and documents 4033 x 4033 as one of
the recommended Landscape sizes:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine
https://dev.epicgames.com/documentation/unreal-engine/importing-and-exporting-landscape-heightmaps-in-unreal-engine

For an 8 km extent:

`XY Scale ~= 800000 cm / 4032 ~= 198.412698 cm`

For a heightmap whose deliberately encoded vertical range is
`vertical_range_m`, use Epic's 512-unit Landscape height domain:

`Z Scale = vertical_range_m * 100 / 512`

and place the Landscape Z origin consistently with the chosen encoded min/max
range. Example: a 1600 m encoded vertical range gives `Z Scale = 312.5` and
an ideal UInt16 quantization step of about `1600 / 65535 ~= 2.44 cm`.

#### P0 next experiment — source-resolution A/B, no art camouflage

Do **not** spend another cycle smoothing the current 5 m source globally.

The next decisive experiment is:

`DTM_2m_Cortina -> QGIS/GDAL -> Float DEM -> 4033x4033 -> UInt16/R16 -> UE`

with the same AOI, camera, Landscape topology, forced LOD and lighting-only
capture used for the current baseline.

Compare directly:

- **A:** current Veneto 5 m source -> 4033 presentation resample;
- **B:** verified Cortina 2 m source -> 4033 (~1.984 m/vertex).

No production material, foliage, rocks, procedural noise, road cut/fill or
terrain-skin replacement is allowed in this source-resolution A/B. The purpose
is to isolate whether genuine horizontal source resolution removes or strongly
reduces the Minecraft-like faceting.

Acceptance interpretation:

- if B removes or materially reduces the defect, source horizontal resolution
  is confirmed as the dominant cause and the 2 m DTM becomes the macro-terrain
  candidate;
- if B retains the same defect, investigate Landscape triangulation / LOD /
  importer behavior before adding art;
- R16 vertical quantization remains a low-priority hypothesis because the
  measured current quantization is already centimetric.

#### QGIS feature-preserving smoothing is secondary, not the first test

QGIS provides **Feature preserving DEM smoothing**, which can reduce local DEM
roughness while limiting elevation changes and preserving break-in-slope
features better than indiscriminate Gaussian blur.

Use it only after the raw 2 m source A/B if the verified 2 m DTM itself still
contains high-frequency roughness. Any smoothing experiment must preserve a
raw immutable source and record parameters, before/after error metrics and
identical-camera visual evidence.

Do not use feature-preserving smoothing to disguise a 5 m -> 2 m upsample.

QGIS reference:
https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/rasteranalysis.html

### Adopted terrain-detail hierarchy

The production hierarchy is now source-aware:

1. **Verified highest-quality official DTM = macro terrain truth**
   - priority candidate: `DTM_2m_Cortina` if AOI/metadata/license verification passes;
   - fallback/baseline: harmonized Veneto 5 m LiDAR-derived DTM;
   - mountain massing, ridges, valleys, passes and broad slope shape.

2. **SP638 GIS spline + road-corridor tooling = road engineering**
   - road bench;
   - uphill cut;
   - downhill fill/embankment;
   - shoulders, drainage-scale shaping and hairpin cleanup.

3. **Static/Nanite meshes = non-heightfield geology**
   - vertical cliffs;
   - overhangs;
   - rock faces and retaining structures;
   - shapes that cannot be represented correctly by a single-valued Landscape
     heightfield.

4. **PCG/material dressing = near-field natural detail**
   - rocks and boulders;
   - scree;
   - grass, shrubs and trees;
   - slope/elevation/road-distance-driven distribution.

The base DEM is still not expected to be a finished cyclist-height scene.
However, YACS must not knowingly use a 5 m source as canonical macro terrain if
an official, licensed, correctly covering 2 m DTM is available and materially
improves the neutral geometry proof.

### Higher-resolution source escalation rule — revised 2026-09-28

The previous rule deferred higher-resolution DEM evaluation until after the
road/cliff/material art pass. The discovery of an official Cortina-area 2 m DTM
changes that order.

**Evaluate the verified 2 m DTM before further terrain art camouflage.**

Do not rebuild the production world yet. First perform the bounded, exact-camera
5 m vs 2 m A/B described above. Promote the 2 m source only if:

1. coverage includes the required SP638 / Passo Giau AOI;
2. metadata, CRS, datum, license and provenance are recorded;
3. the preprocessing path is deterministic and preserves Float elevation until
   final UInt16 encoding;
4. the neutral 4033 UE proof materially improves against the 5 m baseline;
5. road XY remains independent and unchanged.

This revised rule supersedes the earlier assumption that
`good 5 m macro DTM + authored corridor` should automatically be preferred
over testing a denser source. The old 5 m result remains valuable baseline
evidence, not the final source decision.

### P0 diagnostic trap: independent road and terrain grids

Do not confuse Landscape vertex spacing with either source accuracy or source
alignment.

The SP638 road geometry and the Veneto DTM were measured independently. The
selected road source is in an approximately 4 m positional-accuracy class while
the canonical DTM is a 5 m raster. On steep Alpine slopes, that combination is
large enough that a small XY displacement can select materially different
terrain heights. A road of similar width to one DTM cell can also lie largely
between measured terrain samples.

Therefore:

- do not snap SP638 XY to DTM cells or Unreal Landscape vertices;
- do not treat a 4033-grid vertex (~1.98 m spacing) as a new measured terrain
  point;
- keep canonical road XY independent, sample/interpolate DTM Z continuously,
  and solve the rider-close road bench/cut/fill with local geometry;
- if a visual mismatch disappears only after moving the canonical road onto the
  terrain grid, treat that as a failed diagnostic, not a valid fix;
- any deliberate correction of canonical road XY requires separate evidence
  that the road source itself is wrong;
- do not estimate road curvature, tangent frames or road-cut widths from a
  sampling window smaller than the source-position uncertainty. Densifying the
  centerline to 2 m stations does not create 2 m positional truth. For the
  current proof, source-scale road geometry analysis uses a 6 m half-window
  while preserving every canonical centerline station unchanged.

This trap is especially important at tight hairpins, where local curvature,
road width, independent XY uncertainty and the 5 m terrain grid can all be on
the same spatial scale.

### Required next diagnostic only if R4.1D cannot cover the residual cleanly

1. capture a representative steep-face crop with wireframe/component boundaries;
2. check whether any repeated defect aligns with 63/126-quad boundaries;
3. compare the same location against the prepared 4033 hillshade/source samples;
4. use Unreal-native import-reader parity only if the evidence suggests a data
   interpretation defect.

Do not save diagnostic-only overrides into the canonical map.

## 4. Diagnostic ladder — run in this order

### A. Prove the source and R16 numerically

Add deterministic report fields for both source float32 DEM and prepared R16:

- unique-value count;
- min/max;
- smallest non-zero elevation delta;
- p50/p95/p99 adjacent-sample delta;
- count/share of exact flat plateaus;
- decoded R16 -> meters round-trip RMSE and max error;
- horizontal/vertical scanline samples through the visible problem area;
- slope histogram before and after resampling.

Acceptance principle:

- R16 round-trip error should stay on the order implied by the ~2.35 cm
  quantization step;
- visible meter-scale terraces must have a measurable source/data cause if they
  are real geometry.

### B. Compare our R16 reader with Unreal's own file-import path

Use `FLandscapeImportHelper::GetHeightmapImportDescriptor` /
`GetHeightmapImportData` (or the registered R16 file-format implementation)
to load the same file.

Compare the resulting `TArray<uint16>` byte-for-byte with
`ReadR16LittleEndian`.

Outcomes:

- identical -> our endian/row reader is not the cause;
- different -> stop and fix the importer contract before any art pass.

### C. Test component/subsection continuity

Epic's Landscape architecture duplicates shared boundary vertices between
components. Component boundaries are therefore a high-value diagnostic area.

For the current topology:

- subsection size: 63 quads;
- component size: 126 quads;
- component grid: 32x32.

Instrument seam probes around X/Y multiples of 126 and, separately, subsection
multiples of 63. Compare the source samples on both sides of each boundary and
look for periodic error correlated with the visible pattern.

A defect aligned exactly to 63/126 intervals is much more suspicious than
ordinary DEM detail.

### D. Neutral geometry capture

Only after A-C:

- force Landscape LOD0;
- keep camera, resolution and seed fixed;
- use no-grid neutral material;
- disable production decoration;
- capture lit and unlit/debug variants.

The geometry proof should read like the source hillshade at macro scale.

### E. Only then consider controlled preprocessing

Do **not** apply a broad Gaussian blur simply because a screenshot looks
terraced.

Community experience repeatedly identifies true 8-bit/poor-gradient data as a
cause of terracing, but experienced Unreal users also warn that indiscriminate
blur destroys terrain data and recommend diagnosing the data/source first.

Useful discussion:
https://forums.unrealengine.com/t/landscape-heighmap-blocky-even-grayscale-16bit-blur/1706783

If smoothing is ultimately justified, prefer a bounded, measured,
slope-aware/feature-aware operation with BEFORE/AFTER numerical and visual
evidence.

## 5. External terrain-tool guidance worth keeping

### Gaea

Gaea's Unreal output path explicitly auto-levels its 32-bit height data before
conversion to Unreal's 16-bit Landscape range so that the available 16-bit
precision is not wasted on unused headroom.

Reference:
https://docs.gaea.app/reference/nodes/output/unreal

This supports the current YACS strategy of mapping the useful DEM range across
the available uint16 domain.

### World Machine

World Machine's Unreal workflow recommends RAW16 and Unreal-compatible
Landscape resolutions.

Reference:
https://help.world-machine.com/topic/export-to-unreal-engine/

This is useful as an independent terrain-authoring reference, not as a reason
to replace the deterministic Python pipeline.

## 6. Do not use Nanite as a geometry-quality band-aid

Epic states that Nanite Landscape uses the same source Landscape data and users
should not expect a visual-quality improvement or downgrade merely from enabling
Nanite. It primarily changes rendering/performance behavior.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine

Therefore:

- do not enable Nanite to "fix" terracing;
- first make the base Landscape geometry visually correct;
- evaluate Nanite later as an R5/R7 performance/rendering decision.

## 7. Material and level-design direction after geometry passes

Once the neutral proof is clean, switch from engineering diagnosis to level
design.

Epic Landscape Materials support layer-based blending and are appropriate for
the R4.1 material family.

References:

- https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/landscape-material-expressions-in-unreal-engine

R4.1 material order remains:

1. meadow / low vegetation base;
2. forest floor;
3. dirt / gravel;
4. exposed rock;
5. scree;
6. optional high-altitude snow.

Use slope/elevation/macroscale variation to support geological readability,
not to conceal broken terrain geometry.

## 8. Visual-debug acceptance gate

R4.1B Landscape path A is technically and visually acceptable only if:

- the neutral no-grid capture has no obvious periodic artificial terracing;
- no recurring defect correlates with 63/126-quad section/component intervals;
- Unreal-native R16 import data agrees with our deterministic reader, or any
  difference is understood and deliberately resolved;
- source -> prepared R16 round-trip error is measured and documented;
- the silhouette and major ridges agree with the source hillshade;
- the diagnostic proof remains 3840x2160 and deterministic;
- `L_CyclingTest` remains byte/hash protected;
- the owner/human review explicitly accepts the visual result.

Green CI remains necessary but is not visual acceptance.

## 9. Working hypothesis priority after the 4K/FXAA proof

Current evidence changes the priority order:

1. **steep-face heightfield / native 5 m spatial-resolution limit** — primary
   residual hypothesis; Landscape cannot represent overhangs and the 4033
   resample does not add measured terrain detail;
2. **component/subsection boundary correlation** — check only if the residual
   shows periodic alignment with 63/126-quad boundaries;
3. **native-import vs manual-reader parity** — keep as a fail-closed oracle if
   data interpretation becomes suspect;
4. **bounded meso cliff geometry** — use R4.1D Rock Face / cliff / scree assets
   for inspectable steep faces while keeping the DEM for macro massing;
5. **renderer aliasing** — proven to have contributed to the old 1080p
   herringbone, but no longer the main residual after 4K/FXAA;
6. **Nanite** remains a later performance/rendering decision, not a geometry
   repair.

Broad terrain smoothing is still rejected: it would destroy source structure
without addressing the core heightfield limitation.

### 9.1 R4.1B.3 result -> R4.1B.4 decision

PR #239 produced a successful exact-head technical proof at
`556e89600ee05ddeca6f3c9680da4769c6da530c` (Gumball run
`36563292917`), including zero non-local corridor overlap pairs and bounded
road-clearance diagnostics. Human review nevertheless rejected the 3840 x 2160
rider-close image because heightfield ribbing/staircase terrain and black
occlusion ribbons remained dominant.

That result promotes **bounded meso geometry** from hypothesis to the active
R4.1B.4 recovery path (#247). The implementation deliberately:

- keeps MASE Landscape as macro terrain;
- samples local Landscape height only as a source surface;
- builds a bounded irregular meso patch on a local working grid;
- pins the patch topology boundary exactly to source terrain;
- keeps the meso surface from falling below the still-visible macro Landscape,
  preventing depth/occlusion ribbons from exposing the raw heightfield;
- keeps the road/shoulder corridor excluded while B.4.1 permits a bounded
  road-facing transition overlap: the meso cutout starts from the actual
  earthwork outer extent plus 0.50 m clearance, then shrinks by 0.65 m so the
  meso patch may underlap the dedicated outer earthwork edge by at most 0.15 m
  instead of exposing macro Landscape between the two systems;
- validates deterministic mesh/hash, seam error, protected-distance clearance,
  non-degenerate triangles and bounded correction before the UE proof;
- retains human cyclist-camera acceptance as the final geometry decision.

A finer local mesh is **not** evidence of finer terrain measurement. It only
provides presentation topology for a local non-heightfield repair.

The first B.4 Gumball proof on PR #251 (run `36571406362`) technically passed
the bounded-meso contract at exact HEAD
`257f75d6baddeb42ea3a9489c9f09a310e8a640a`: one editor process/boot, zero seam
adjustment, at least 10.5 m protected earthwork clearance, no meso vertex below
the visible macro Landscape, and reduced high-frequency curvature. Human review
still rejected that Lit frame because checker/fallback proof materials obscured
whether the remaining dark ribbons were geometry or shading artifacts.

The next B.4 geometry proof therefore uses UE 5.8 `viewmode lightingonly`.
Lighting Only deliberately replaces scene materials with a neutral
lighting-only diagnostic and omits source normal maps. This makes the exact-SHA
human geometry gate material-independent; production materials remain a
separate later visual/dressing acceptance concern.

Human review of that Lighting Only path later isolated a narrower defect: long
dark seam wedges remained at the `earthwork -> exposed Landscape -> meso`
interface even though the macro/meso non-penetration and topology checks passed.
This is treated as an interface problem, not a reason to alter the MASE source,
SP638 XY, measured banking or broad terrain smoothing.

B.4.1 therefore adds a deterministic transition-underlap contract. The meso
boundary may move inward only through a named overlap allowance; with the current
proof values, 0.65 m overlap against 0.50 m nominal earthwork clearance yields a
maximum 0.15 m underlap beneath the outer earthwork edge. The meso topology
boundary remains pinned to sampled MASE height, and the existing interior lift
continues to keep active meso geometry from falling below the visible macro
Landscape.

### 9.2 SP638 banking/crossfall — real-data-first guardrail

PR #251 also establishes the presentation-side banking rule for real SP638:
**do not manufacture a constant `4° everywhere` bank**.

The active estimator is road-band-first rather than hillside-first: it samples a
cross-road LiDAR transect around the SP638 centerline, isolates/fits the
approximately carriageway-width band, and only then derives signed crossfall.
This is necessary because a naïve two-point transect can measure the adjacent
mountain slope, ditch or embankment instead of the road itself and produce
physically meaningless angles.

The presentation path may apply bounded regularization to reject that
contamination and keep the road surface continuous, but the result must remain
traceable to the measured samples. A synthetic constant is not an acceptable
production fallback when usable measured evidence exists.

This presentation crossfall does **not** automatically become simulation
banking. The `Road Physics Profile` remains physics authority. Promotion of
measured SP638 crossfall into physics is the separate post-#251
`R4.1C-PHYS — Road banking physics authority` gate defined in
`docs/ROAD_PHYSICS_PROFILE.md`.

The two representations may be smoothed differently for their responsibilities,
but a validation proof must catch a material visual-bank vs physics-bank
mismatch before physics promotion is accepted.

## 10. Source hierarchy

Prefer sources in this order:

1. Epic UE 5.8 documentation/API;
2. source code / reproducible engine behavior;
3. terrain-tool vendor documentation (Gaea / World Machine);
4. Epic Developer Community forum experience;
5. Reddit/community discussion only as symptom vocabulary or anecdotal hints.

Community advice is not an acceptance criterion unless reproduced in YACS.
