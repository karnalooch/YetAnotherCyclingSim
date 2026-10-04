# Julka — YACS Asset Manager

Julka is an opt-in, isolated command-line tool for inventorying, planning,
restoring and verifying YACS assets. It does not change Unreal C++/Blueprints,
project configuration, route authority or terrain methodology. Its commands are
read-only unless an explicit `--apply` flag is supplied.

## Clean Windows setup

Install Git for Windows with Git LFS, Python 3.12+, `uv`, and GitHub CLI. Clone
the repository with Git LFS available, then in PowerShell:

```powershell
uv run --project tools/julka python tools/julka/julka.py doctor
uv run --project tools/julka python tools/julka/julka.py profiles
uv run --project tools/julka python tools/julka/julka.py inventory
uv run --project tools/julka python tools/julka/julka.py plan --profile sa-calobra-working
```

The Git LFS command inventories tracked production Unreal/raster files and is
plan-only until `--apply` is supplied. Sign into GitHub CLI (`gh auth login`)
with an account that can read the private draft Release to retrieve the raw
Sa Calobra source package. Choose a destination volume with several GiB free;
the manager estimates exact bytes before writing:

```powershell
$env:YACS_ASSET_ROOT = 'D:\YACS-Assets'
uv run --project tools/julka python tools/julka/julka.py hydrate-lfs --profile sa-calobra-working --apply
uv run --project tools/julka python tools/julka/julka.py hydrate --profile sa-calobra-working --apply
uv run --project tools/julka python tools/julka/julka.py verify --profile sa-calobra-working
```

The Release profile restores 17 inputs (4 MDS surface-model GeoTIFFs, 9 LiDAR LAZs,
4 orthophotos): exactly **3,339,596,438 bytes**. SHA-256, byte count, BigTIFF or
LASF signature, Release asset digest, draft state and the downloaded provider
receipt are checked in staging before any file is promoted. Each file is
atomically moved only when its destination is absent; existing verified files
are retained, corrupt existing files are never overwritten, and an interrupted
promotion can be resumed. The receipt preserves both CNIG's catalog names and
the delivered filenames. Original provider files are never renamed or edited.

`inventory --verify` hashes every materialized Git LFS payload. `hydrate-lfs
--profile sa-calobra-working --apply` retrieves only the Unreal `.uasset`/
`.umap` files and the pinned 8×8 km GeoTIFF in that profile, then verifies
Git LFS SHA-256 OIDs. Git LFS
doesn't cover local ignored files or arbitrary datasets; use an explicit
profile/provider receipt for those instead.

The terrain mosaic's 17 original MDT50 cm inputs are a distinct set from the 17
MDS/LiDAR/orthophoto Release assets. Their byte identities are pinned to the
existing `scripts/assets/prepare_sa_calobra_mdt50cm.py` input manifest, but the
files are not in the known runner source folder and are not currently in the
Draft Release. Obtain these from CNIG using the existing approved/manual
acquisition route, then `adopt-mdt --source-dir <folder> --apply` verifies and
copies them while leaving the originals unchanged. Julka fails closed instead
of calling those bytes cloud-backed. GRID, ROADS and LANDCOVER are explicitly
incomplete and are not part of an “8×8 ready” claim.

## Data flow and ownership

```text
Provider receipts + immutable identities
       ├── tracked Unreal/raster assets ──> Git LFS ──> UE project checkout
       └── 17 raw CNIG tiles ─────────────> private draft Release ──> local asset root
                                                                    │
                                 existing YACS prep tools (separate) ─┤
                                                                    ▼
                                         derived assets / proof manifests
```

This adopts the publicly documented producer → prepared data → Unreal consumer
→ bounded proof boundary used for production terrain authoring. Embark's
internal recipes and parameters are not public, so Julka does not invent or
claim them. The DCC/processing implementation remains the existing YACS tools;
Julka manages bytes, identities and acquisition only. It does not run world
generation or change existing consumer code.

The Draft Release is an already configured, private-to-repository-readers
transport copy. The checked-in manifest pins its expected metadata; the CNIG
receipt remains the source identity/provenance authority. A GitHub Release is
free for release asset storage and bandwidth under current GitHub documentation,
with a 2 GiB maximum per file; each present source asset is below that limit.
Access still requires repository permission. Git LFS has separate plan quotas;
usage is checked in GitHub billing and may be blocked after free quota. Julka
never selects a paid upgrade.

The local asset root is deliberately outside Git and Unreal's generated
directories. Use `YACS_ASSET_ROOT` to choose a drive. `status`, `plan`, `doctor`,
`inventory`, and `cleanup` do not remove or download source data. `cleanup` only
reports only the explicitly known `derived-cache` and interrupted Julka staging
directories. Source files, Git LFS objects, prepared outputs, evidence and
Unreal project data are not cleanup targets. Data without an authorized remote
copy remains on the configured local disk; Julka does not manufacture a backup
or silently duplicate multi-gigabyte source files.

## Commands

```text
julka doctor [--project <uproject>]              read-only tool check
julka profiles                                    list profile closure/size
julka inventory [--verify]                        inspect Git LFS objects
julka hydrate-lfs [--profile NAME] [--apply]        Git LFS exact-path restore
julka audit-root --root PATH [--hash] [--output FILE] scoped local inventory
julka adopt-mdt --source-dir PATH [--apply]          verify/copy the 17 raw MDT tiles
julka status [--profile NAME] [--verify]          inspect local profile files
julka plan [--profile NAME]                       calculate missing bytes/free space
julka hydrate [--profile NAME] [--apply]            verified Release restoration
julka explain <asset-id>                           show source and GIS metadata status
julka verify [--profile NAME]                     full size/SHA/signature check
julka cleanup                                     cache-only size report, no deletion
```

The `code` profile has no external data. `sa-calobra-working` includes all 17
verified Release assets plus the pinned terrain raster and tracked Unreal LFS
consumer assets. `sa-calobra-8x8` additionally requires the separate 17 MDT
source tiles and reports GRID/ROADS/LANDCOVER gaps; it cannot pass while those
inputs are missing. GIS metadata states which values are uninspected rather
than inventing CRS/vertical datum/footprints from filenames alone.

Even after all catalog files are present, the incomplete GRID/ROADS/LANDCOVER
declarations keep `status`, `plan` and `verify` nonzero for `sa-calobra-8x8`.
MDS describes the surface including objects and vegetation; it is not MDT ground
authority. The working profile verifies stored bytes, not a clean Windows UE
setup, independent-host recovery, world regeneration or playable-world acceptance.

For a deliberately scoped read-only audit of an existing local asset root:

```powershell
uv run --project tools/julka python tools/julka/julka.py audit-root --root 'D:\actions-runner-yacs\_work\YetAnotherCyclingSim'
```

The audit skips Git metadata, credentials/config roots and reparse points. Its
default report contains logical sizes and paths only; `--hash` can read many
gigabytes and should be used only when a full byte-integrity audit is desired.
The report is local; it is never committed or uploaded automatically.

More architecture, limitations, and SSOT links: [`../../docs/tooling/JULKA.md`](../../docs/tooling/JULKA.md).

## P1 context and provider failures

The original 34-item catalog is supplemented by `data/p1_context.json`.
Use `explain btn_vector_context`, `explain siose_2014_wfs`, or
`explain catastro_buildings_wfs` for source-level state and provenance.
`sa-calobra-btn-context` verifies 30 local BTN tiles;
`sa-calobra-p1-context` verifies all 45 source/evidence files but remains nonzero
because SIOSE 2014 and Catastro are unadmitted. Select the parent world-data
`sa-calobra-working-v1` cache via `--root`. This backend uses the existing
`p1-2026-10-04` relative paths, without duplicating bytes into `sources/`.
No remote P1 snapshot is registered. `plan` reports local restore requirements;
`hydrate` verifies local-only files and never downloads an invented backup.
Copy the retained relative cache paths to the selected root, then verify hashes.
Provider reacquisition is a new snapshot if mutable responses differ.

See the [P1 report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ACQUISITION_2026-10-04.md)
for exact file/layer counts, rejected payloads and provider references.

## Verified P1 input alternatives

`sa-calobra-p1-inputs` selects the 30 BTN tiles plus 8 verified alternative
payloads: Catastro Buildings ATOM for Escorca and IDEIB SIOSE 2014 AOI geometry.
Use `explain catastro_buildings_atom` and `explain siose_2014_ideib` for counts,
provenance and local restore status. Select the same parent world-data root;
the alternative files live under `p1-alternatives-2026-10-04`.
The historical WFS failure profile remains available as diagnostic evidence.
See the [alternative acquisition report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ALTERNATIVES_2026-10-04.md)
for coverage limitations and the remaining 2A normalization work.

`sa-calobra-2a-context-candidate` verifies the pinned normalized GIS candidate,
its municipal coverage inputs and accepted Base_DTM local copy. It is a selected
byte-integrity checkpoint. `sa-calobra-2a-world-authority` remains incomplete;
`explain normalized_context_v1` reports exact remaining layers and restore.
See the [normalized report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/NORMALIZED_CONTEXT_2026-10-04.md).
