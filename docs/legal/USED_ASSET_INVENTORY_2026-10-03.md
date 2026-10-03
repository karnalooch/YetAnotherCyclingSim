# YACS used asset inventory — 2026-10-03

**Issue:** #335

**Snapshot commit before this inventory:** `e6173323beba7267b6d475b7178fde47cb5bf5af`

**Scope:** source assets, external data, included third-party code and technical Unreal assets that have been acquired, imported, included or used as evidence by YACS so far.

This inventory is a point-in-time reconciliation. The authoritative lifecycle and
license records remain [`ASSET_PLAN.md`](../ASSET_PLAN.md),
[`DEPENDENCY_PROVENANCE.md`](DEPENDENCY_PROVENANCE.md),
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) and the referenced
machine-readable manifests.

## Storage summary

| Storage class | Files/objects | Bytes | Remote state | Decision |
|---|---:|---:|---|---|
| Git LFS at the branch snapshot | 58 | 562,918,293 | already remote | keep in Git LFS; do not duplicate in a data release |
| Persistent runner `manual-cnig` cache | 17 | 3,339,596,438 | remote copy pending at inventory time | upload unchanged to the private draft release `data-cnig-sa-calobra-working-v1-2026-10-03` |
| Runner PNOA WMS working extract | 27 | 17,602,749 | local cache only | inventory only; not an admitted raw-source snapshot |
| Runner Catastro Buildings probe | 14 | 30,911 | local cache only | inventory only; returned 300-byte feature responses require review |
| Runner SIOSE probe | 1 | 35,101 | local cache only | capabilities-only evidence; not an admitted payload |

The complete runner cache therefore contains 59 files / 3,357,265,199 bytes.
Only the 17-file `manual-cnig` set has a complete provider-to-delivery mapping,
byte sizes, SHA-256 hashes, container-signature proof and an approved remote
snapshot decision.

## Repository and Git LFS assets

The 58 LFS objects comprise:

- 57 Unreal assets (`.uasset` / `.umap`), including Stage 3F materials,
  Stage 3G imported Poly Haven meshes/textures, YACS materials, prototype input,
  the prototype map/route and four validated PCG assets;
- one 389,039,616-byte derived CNIG MDT50cm GeoTIFF:
  `worldgen/terrain/benchmarks/sa_calobra/sa_calobra_8x8km_mdt50cm_epsg25831.tif`.

The exact current object inventory is reproducible with:

```powershell
git lfs ls-files --json --long
```

These objects are already stored by GitHub LFS and are not copied into the
World Data Stack release.

## External source assets and data used

| Source / family | Current YACS state | License / authority | Stored evidence | Remote disposition |
|---|---|---|---|---|
| Poly Haven `sparse_grass`, `forrest_ground_03`, `rocky_terrain`, `boulder_01`, `fir_sapling_medium` | imported; fir sapling medium and four PCG consumers validated as recorded in the asset ledger | CC0-1.0 | curated source manifest plus imported Unreal LFS assets | imported derivatives already remote; raw provider packages are reproducible and are not mirrored |
| TINITALY 1.1 | acquired historical Passo Giau derived input | CC BY 4.0 | downloader, DOI, local source receipt when acquired | raw GeoTIFF not mirrored by this snapshot |
| MASE PST Passo Giau LiDAR DTM 1x1 | acquired historical Passo Giau source | CC BY 4.0 | published prerelease `data-mase-pst-passo-giau-dtm-2026-09-28` | already remote; no duplicate upload |
| Regione Veneto LiDAR-derived DTM | used as bounded Passo Giau gap-fill evidence | provider terms recorded by the Passo Giau pipeline | pinned scripts and generated reports | no new upload; historical pipeline only |
| CNIG/IGN MDT50cm 3rd coverage | acquired source for the current 8 km terrain benchmark | CNIG general-use terms compatible with CC BY 4.0 | 17 source identities pinned by preparation tooling; derived GeoTIFF and report in Git/LFS | derived product already remote; original source tiles are not present in the current runner cache |
| PNOA LiDAR NPC03, MDS50cm COB3 V1 and PNOA Máxima Actualidad 2024 | 17 acquired World Data Stack v1 sources | CNIG/IGN general-use terms compatible with CC BY 4.0 | `working_space_sources.json` and `manual_cnig_receipt_2026-10-03.json`; 17/17 live SHA-256 verification PASS | upload unchanged to the private draft release |
| CartoCiudad Ma-2141 response | acquired source-review dataset | CC BY 4.0 | immutable response and review JSON in the repository | already remote in Git |
| IGN IGR-RT Ma-2141 response | acquired source-review dataset | CC BY 4.0 | immutable response and review JSON in the repository | already remote in Git |
| OpenStreetMap Sa Calobra road inventory | derived aggregate summary | ODbL 1.0 | aggregate inventory with snapshot/bounds/attribution | already remote in Git; raw geometry intentionally excluded |
| PNOA Ma-2141 review image | admitted bounded visual review input | CC BY 4.0 | image, profile and attribution in the repository | already remote in Git |

## Included tools and third-party code

| Dependency | State | License | Remote disposition |
|---|---|---|---|
| RoadForge minimal editor donor | included, editor-only | MIT | vendored subset and license already remote in Git |
| `db-lyon/ue-mcp` 1.3.9 | pinned development dependency | MIT | lockfile/reference already remote; installed payload is not mirrored |
| PCGEx `5.8` at `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66` | pinned authoring dependency used by the Passo Giau proof | MIT | fetched from upstream exact SHA; not duplicated in the data release |

## Explicit exclusions

- Strava Global Heatmap remains reference-only; copying and derived-data
  inclusion are blocked.
- GeoTerrain and Embark UnrealClaudeFileHelper remain copying-blocked because
  the reviewed source lacks a sufficiently strong root license artifact.
- SideFX Houdini, SideFX Labs/Gaea2Houdini and QuadSpinner Gaea are reference or
  optional escalation paths, not acquired production assets in this snapshot.
- Candidate-only Poly Haven assets are not represented as imported or used.
- PNOA WMS, Catastro and SIOSE service-cache files are not promoted to admitted
  source assets by this inventory.

## Remote snapshot contract

The GitHub repository is public. Publishing a normal release would make the raw
CNIG files public. The first remote copy is therefore a **draft release**, which
GitHub exposes only to users with push access. The draft must not be published
until the owner explicitly approves public redistribution and the release asset
list, attribution and hashes have been reviewed.

The release must contain exactly:

- the 17 unmodified `manual-cnig` source files;
- `manual_cnig_receipt_2026-10-03.json`;
- `working_space_sources.json`;
- this inventory document.

Upload success is not sufficient. Closeout requires the remote asset count,
total bytes and GitHub-provided SHA-256 digests to match the local receipt.
