# Julka — asset management and local workspace

**Status:** active, isolated supporting tool for Issue #345
**Owner-facing summary:** one inventory for large assets, safe restore plans,
exact integrity checks and cleanup visibility. No existing Unreal/world code is
changed or invoked.

## Architecture decision

The public Embark pattern establishes a producer → prepared data → Unreal
consumer → bounded proof boundary for terrain/world content. Public evidence
does not disclose the internal ARC Raiders recipe, node graph or settings.
Julka adopts only the public boundary. Existing YACS scripts remain the
producers/preparers; Unreal project assets stay with the current Git LFS
consumer. Julka is an acquisition/catalog/proof utility, not a new terrain
generator, runtime service or replacement for the World Building Bible.

| Stage | YACS owner | Julka responsibility | Proof boundary |
|---|---|---|---|
| Producer/input | CNIG receipt, reviewed local sources, pinned repository commit | Inventory IDs, filenames, provenance, SHA-256, size, backend and GIS metadata state | Receipt maps 17 delivered names; a separate catalog pins the different 17 MDT mosaic inputs |
| Prepared data | Existing YACS prep scripts and authored outputs | Preserve separate output identity/parent hashes when registered; don't mutate producer files | Input/output identity can be compared without assuming a generator ran |
| Consumer | Existing UE project and Unreal asset pipeline | Restore Git LFS files on exact commit; local external sources remain outside UE project | SHA-256/OID and size; Unreal build/import remains a separate proof |
| Evidence | Existing YACS validation tiers and human visual acceptance | Report inventory/restore receipt and local integrity | Integrity PASS is not a build, terrain render, performance PASS or visual acceptance |

This keeps the tool behind existing producer/consumer boundaries. No new Unreal
plugin, runtime dependency, DCC license, cloud service or world architecture was
introduced. The existing project remains the source of truth for all authored
UE content.

## Storage matrix

| Asset class | Authority and storage | Clean-PC restore | Important limit |
|---|---|---|---|
| Unreal `.uasset` / `.umap`, checked-in GeoTIFF | Git commit + Git LFS OID | `julka hydrate-lfs --apply` | Free Git LFS monthly bandwidth/storage quota applies; usage and budget stay with GitHub account |
| 17 raw CNIG source tiles | Receipt SHA-256 + repository Draft Release | `julka hydrate --profile sa-calobra-working-v1 --apply` | Repository access required; no paid service assumed; Release bytes do not change receipt authority |
| 17 original MDT50 cm terrain-mosaic inputs | Existing YACS preparation manifest pins size/SHA-256; no copy found in the known runner `manual-cnig` root or the two checked source roots | `julka adopt-mdt --source-dir <folder> --apply` after manual/free CNIG acquisition | Not present in the Draft Release; a full cold-start 8×8 restore remains incomplete until a verified local source set or authorized free remote copy exists |
| Prepared/native derived outputs | Existing local workspaces until separately catalogued | Explicit local restore/provider plan | Nothing is called available unless exact identity and storage are known |
| Unreal DDC / generated directories | Engine-generated disposable data | Regenerate through Unreal | Not a backup and never a source-asset cleanup target |

Each current Release asset is below GitHub's documented 2 GiB per-file limit;
GitHub currently documents no total Release asset or bandwidth cap. Private
repository access remains necessary. Git LFS has separate free quotas (10 GiB
storage and 10 GiB monthly bandwidth on Free/Pro); excess without billing setup
can block LFS retrieval, so Julka reports pointer-only files and never turns on
paid billing. See [GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
and [Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)
for the current provider terms.

Julka intentionally adds no DVC dependency or second local content store. DVC
remains a candidate from the separate experiment in Issue #340 and needs its
own accepted evidence and compatible-license review before adoption. If a
source has no authorized free remote copy, it stays in the selected local asset
root or is reacquired from the official provider; Julka does not claim that this
is a second-device backup.

## Integrity and destructive-action contract

- Catalog paths are relative and rejected if absolute or traversing upward.
- A Release restore checks private-draft state, exact tag, asset name, remote
  size/digest, pinned 8,194-byte receipt, receipt row mapping, downloaded
  size/SHA-256 and file signature.
- Downloads stage on the destination volume; all files pass identity checks
  before promotion. Existing valid files are retained; corrupt files are never
  overwritten. Per-file atomic promotion can resume after interruption. A
  per-root operating-system lock rejects a second simultaneous mutating Julka
  operation instead of racing over staging or restore state.
- Git LFS hydration selects files already tracked by the selected commit and
  limited to Unreal/raster extensions, then checks SHA-256 OID and byte count.
- `doctor`, `inventory`, `status`, `plan`, and `cleanup` are read-only.
- `cleanup` is an inventory/space report only. Julka does not delete files,
  run remote garbage collection, remove Git LFS objects, or clear Unreal
  generated folders. It scans only explicitly known Julka cache locations.
- SHA/provenance proof is intentionally distinct from Unreal import/build,
  exact-SHA visual review, performance evidence, or human acceptance.
- `audit-root` requires a specific user-selected subdirectory, skips credentials
  and reparse points, and reports logical sizes; it never claims exact physical
  disk reclaim, deduplicates only where file IDs allow, and does not upload its
  filename inventory.
- Windows file identity is read through `os.stat(..., follow_symlinks=False)`;
  `DirEntry.stat()` returns zero volume/file IDs on Windows and must not be
  used for deduplicating audit sizes. Logical file-ID totals still do not
  measure physical allocation or justify deletion.
- GIS registry fields preserve unverified CRS, vertical reference, footprint,
  density/resolution, classification and NoData as explicitly uninspected.

## Delivery boundary — Issue #345

PR #346 closes the bounded CLI checkpoint #347 and delivers working-profile
integrity checks.
It references, but does not close, the full Julka workstream in Issue #345.
That issue retains the missing 17 raw MDT inputs, independent-host/clean-OS
restore, GRID/ROADS/LANDCOVER admission, producer/consumer and Unreal proof,
and independent backup decisions. Issue #339 is consolidated into #345;
PR #340 remains a historical isolated DVC experiment, not a Julka dependency.
Issue #341 tracks the existing Windows host scripts in PR #336, rather than
a second asset manager.

Incomplete layer declarations produce a nonzero result from `status`, `plan`
and `verify`, even when every file currently in the catalog verifies correctly.
The working profile is a byte-integrity checkpoint, not completion of #345.
Asset-root arguments may be absolute or relative to the current directory;
reporting normalizes the root before displaying receipt-relative paths.

## Usage and SSOT

### Working-space P1 context checkpoint — 2026-10-04

The separate `tools/julka/data/p1_context.json` supplements the original 34-item
catalog with 45 local source/evidence identities. `load_catalog_file` merges
these identities without changing the 17-file Release or MDT profiles.
Source IDs `btn_vector_context`, `siose_2014_wfs` and `catastro_buildings_wfs`
are accepted by `explain` and report counts, provenance receipt, errors and
restore limitations. Local backend `layout=world-data-cache` resolves paths
directly under the explicitly selected cache root, without copying source bytes.

`sa-calobra-btn-context` verifies 30 BTN tiles (250,386 B, 21 layers).
`sa-calobra-p1-context` inventories all 45 files but remains incomplete:
SIOSE's 244 returned objects fail the requested 2014 edition identity, and
all 12 Catastro GML payloads are provider exceptions. Evidence-byte PASS does
not admit those geographic sources. `status`, `verify` and `plan` stay nonzero
for the incomplete profile. Missing local-only files also make `plan` nonzero;
`hydrate` verifies local bytes and does not fabricate a remote restore source.

Select the parent `sa-calobra-working-v1` cache with `--root`; P1 raw payloads
are under `p1-2026-10-04`. Restore by copying the retained relative paths and
verifying pinned size/SHA-256. No independent or remote P1 backup is registered.
Exact results, official provider evidence and usage are in the
[P1 acquisition report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ACQUISITION_2026-10-04.md).

Install/use commands and the 34-item identity catalog (the 17 Release files plus
the separate 17 MDT mosaic inputs) are in
[`tools/julka/README.md`](../../tools/julka/README.md) and
[`tools/julka/data/catalog.json`](../../tools/julka/data/catalog.json).
The tool's focused tests are discovered by `scripts/ci/run_script_tests.py`.

The current authority list in [`../README.md`](../README.md) identifies
[`ASSET_PLAN.md`](../ASSET_PLAN.md) as the asset/provenance SSOT and
[`WORLD_BUILDING_BIBLE.md`](../WORLD_BUILDING_BIBLE.md) as the world-methodology
SSOT. Julka changes asset acquisition/management only, so this page and the
asset ledger are updated while the Bible and production code remain unchanged.
