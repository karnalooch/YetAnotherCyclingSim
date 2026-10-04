# Working-space normalized context candidate — 2026-10-04

Refs Issue #335. This bounded checkpoint normalizes terrain and provider context;
it does not complete 2A, integrate Unreal consumers or change route/BOB authority.
Methodology SSOT: World Building Bible; source SSOT: Asset Plan; Julka and CI
Validation Tiers define lifecycle and validation.

## Verified coverage and products

AOI: EPSG:25831, `483000,4407500 → 485016.5,4409516.5`.
Grid: native 0.5 m, 4033 × 4033; accepted Base_DTM hash
`6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a`.
Existing retained LFS bytes were read and copied into local cache; no download,
rewrite or modification of the protected 17 CNIG payloads occurred.

| Product | Result |
|---|---|
| Elevation, slope, aspect, 3×3 local relief | 4 native-grid Float32 GeoTIFFs; -32767 NoData; flat aspect unknown |
| Catastro mapped footprint | UInt8 conservative all-touched candidates; 0 no mapped provider footprint, 1 mapped, 255 unknown |
| SIOSE 2014 feature index | UInt16 historical object identity; 0 unknown, 65535 conflict; no inferred current biome |
| Clipped vector context | 3 metric geometry JSON collections: SIOSE, Catastro, municipal coverage |

Nine products total **167,471,514 B**, plus manifest and external visual QA.
Inputs and outputs carry exact sizes/hashes; geometry JSON explicitly declares
metric EPSG:25831 and is not RFC7946 GeoJSON.

The official [IDEIB municipal service](https://ideib.caib.es/geoserveis/rest/services/public/GOIB_UnitAdm_IB/MapServer)
selected named layer `Municipis` (1) and returned all AOI IDs: one Escorca polygon,
`ID=07019`. Exact polygon coverage has **0 m² uncovered**. Five source/metadata
JSON payloads total 756,371 B and are pinned in the recipe. Service boundaries
come from IGN's registry with MTIB 1:5000 coastline modifications, not a new
cadastral/legal-boundary determination.

The 15 SIOSE polygons cover the AOI without geometric gaps or overlaps; raster
unknown/conflict counts are both zero for this snapshot. Clipped Catastro has
2 Building, 8 BuildingPart, 0 OtherConstruction. Municipal coverage admits the
package footprint, not the real-world freshness/completeness of mapped buildings.

## Identity, restore and reproduction

Cache parent:
`D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1`.

- Raw municipal evidence: `coverage-2026-10-04/` (five pinned payloads).
- Existing accepted DTM local copy: `accepted-base-dtm/`.
- Candidate outputs/manifest/QA: `normalized-context-v1a-2026-10-04/`.
- Independent clean-output regeneration: `normalized-context-v1a-regenerated-2026-10-04/`.
- Initial failure retained: `normalized-context-v1-2026-10-04/failure_receipt.json`.

Only the small recipe, receipt, catalog identities, tooling/tests and docs enter
Git. Raw/GeoTIFF/geometry/PNG remain outside Git. No remote backup was created.
Restore the retained relative cache paths and verify hashes, or regenerate from
pinned inputs, recipe and versions. Provider reacquisition can be a new snapshot;
normalization performs no network requests and rejects stale/missing bytes.

```powershell
python scripts/assets/normalize_sa_calobra_context.py --cache-root '<cache parent>' --base-dtm '<cache parent>\accepted-base-dtm\sa_calobra_8x8km_mdt50cm_epsg25831.tif' --output '<empty output directory>'
python scripts/assets/verify_normalized_context.py '<output directory>\manifest.json'
python tools/julka/julka.py verify --profile sa-calobra-2a-context-candidate --root '<cache parent>'
python tools/julka/julka.py explain normalized_context_v1
```

Recipe: `scripts/assets/sa_calobra_context_recipe_v1.json`.
Receipt: [normalized_context_receipt_2026-10-04.json](normalized_context_receipt_2026-10-04.json).
Fingerprint: `73a797481e6d404ee999a211ac0fe224a9cfbf3baf7f3215479b6256dbbccf98`.
The owned recipe has Git `text eol=lf` to preserve its exact hash across
Windows/Linux checkouts; source payload bytes remain unchanged.
Versions: NumPy 2.3.5, Rasterio 1.5.2, Shapely 2.1.2; exact GDAL version is recorded.

Clean regeneration gives equal manifests and all **9/9 byte/logical hashes**.
A separately restored 14-input cache also reproduces the same complete manifest
and all nine outputs. The GIS reader verifies file identities and native grid/NoData/dtype. Julka's
candidate profile verifies **56/56 files** (38 P1 files plus 18 new input/output
identities); full `sa-calobra-2a-world-authority` remains nonzero for 10 missing
layer groups. Candidate byte PASS does not grant whole-2A or visual acceptance.

## QA, source errors and limitations

`visual_qa.png` juxtaposes orthophoto, elevation, slope, local relief, historical
SIOSE object index and Catastro markers in the same metric AOI. The four retained
orthophoto source hashes were verified read-only before the 2 m QA thumbnail.
Source images are 0.25 m; no thumbnail is a new terrain/classification authority.
The plotting tool was isolated outside the repository; no UE/project dependency
was added. Agent inspection found consistent gross orientation/extent and source
context; human visual and UE consumer acceptance are pending.

Native 3×3 relief has p99 4.98999 m, maximum 80.96997 m; 34,996 cells exceed 10 m.
These high-relief samples require source/geometry review; they are not corrected
or concealed by smoothing, and they are not new building/canopy evidence.

The first GML parser stopped with `ValueError: Catastro feature without supported
polygons`. Actual provider data uses `Surface/PolygonPatch`; explicit support
was added against retained XML and covered by a regression test. The initial
failed receipt remains separate; no failed output was promoted.

The municipal service's [exact license evidence](https://ideib.caib.es/geoserveis/rest/services/public/GOIB_UnitAdm_IB/MapServer/info/iteminfo)
states CC BY 4.0 with attribution `SITIBSA-scne.es`, and separate original-data
distribution request conditions. Raw geometry stays local. Derived source terms
and IGN/SIOSE/Catastro notices continue to apply.

## Remaining 2A

Current land-cover/confidence from stronger dated evidence; LiDAR classes and
canopy height/density; supported water/infrastructure exclusions; accepted road,
shoulder, distance/safety and BOB cut/fill/edge domains; human visual QA and bounded
Landscape/PCG ingestion proof. Existing road/BOB acceptance is a dependency; no
road domain is reverse-engineered from imagery here. Do not close Issue #335.
