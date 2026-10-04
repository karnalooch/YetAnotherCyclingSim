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

## Verified P1 alternatives — 2026-10-04

Owner-authorized alternative acquisition adds 8 local identities to the P1
supplement: Catastro ATOM Escorca (2 feeds + ZIP) and regional IDEIB SIOSE 2014
(service/layer/license metadata, AOI IDs and 15-feature geometry). The
`sa-calobra-p1-inputs` profile verifies 38 files (30 BTN + 8 alternative files)
and passes. The historical failed-WFS profile remains nonzero and unchanged.
`explain` accepts `catastro_buildings_atom` / `siose_2014_ideib`; failed source
explanations point to those explicit alternatives. Restore stays local-only.
See the [alternative report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ALTERNATIVES_2026-10-04.md)
for exact counts, license, coverage limits and remaining 2A work.

## Working-space normalized candidate — 2026-10-04

The supplemental catalog now registers 18 additional municipal/Base_DTM/derived
identities. `sa-calobra-2a-context-candidate` verifies 56 local files; source-level
`explain normalized_context_v1` records grid, coverage, fingerprint, clean
regeneration and candidate status. `explain ideib_municipal_coverage` records
source/license and exact coverage evidence. `sa-calobra-2a-world-authority`
remains nonzero for missing current-land-cover, LiDAR/canopy, water/infrastructure
and road/BOB layers. GIS read/hash PASS is not Unreal or human visual acceptance.
Restore is local-only copying plus hash verification, or pinned regeneration;
no remote backup is registered. See the [normalized report](../../worldgen/terrain/benchmarks/sa_calobra/world_data/NORMALIZED_CONTEXT_2026-10-04.md).

## Frozen Landscape mask review candidate — 2026-10-04

`sa-calobra-mask-review-candidate` adds five pinned identities to the existing
candidate closure: three native-grid context/review PNGs, one diagnostic class
raster and their manifest (61 total files). `explain mask_review_v1` describes
colors, pixel-center registration, frozen map identity and remaining blocked
layers. Restore remains local-only copying and hash verification, or pinned
producer regeneration; an Unreal render is a separate receipt, never inferred
from byte PASS. No new terrain, road or current-biome authority is admitted.

## Placement evidence handoff candidate — 2026-10-04

`sa-calobra-placement-evidence-candidate` verifies 59 source/context/placement
identities, including two native-grid rasters and `placement-manifest.json`.
`sa-calobra-placement-readiness` extends it but retains the ten incomplete
World Authority layer groups and must return nonzero. `explain
placement_handoff_v1` reports prohibited/unknown counts, provenance, fingerprint,
restore and `BLOCKED_FOR_PLANTING`; byte PASS cannot grant planting permission.
Restore is local copying plus hashes or pinned producer regeneration. No remote
backup or PCGEx execution is claimed. Source amber relief remains review evidence.

## Native LiDAR evidence candidate — 2026-10-04

`sa-calobra-lidar-evidence-candidate` adds ten pinned prepared/evidence identities
and their nine raw LAZ dependencies to the existing review closure.
`sa-calobra-lidar-review-candidate` adds three context PNGs and a review manifest.
`explain lidar_masks_v1` reports complete decode counts, source-class/height/fraction
limits, versions, fingerprint, clean regeneration and local restore. A native
render receipt is separate from these hash checks; the preview sky is transient.

Raw source bytes remain read-only. Derived payloads stay outside Git; a small
[receipt](../../worldgen/terrain/benchmarks/sa_calobra/world_data/lidar_masks_receipt_2026-10-04.json)
records hashes/provenance in the repository. Restore is local copying plus
hashes or pinned regeneration with approved isolated decoder tools; no remote
derivative backup is registered. Whole-2A/planting readiness stays nonzero:
candidate data existence is not admission of current cover, canopy, exclusions
or road/BOB authority. See the [Bible](../WORLD_BUILDING_BIBLE.md#native-lidar-evidence-candidate-issue-335).

## Vegetation domains and owner review — 2026-10-04

`sa-calobra-vegetation-domains-candidate` adds two rasters and a manifest to the
84-file LiDAR review closure. `explain vegetation_domains_v1` records overlapping
low/medium/high presence, unknown samples, separate review flags, the pink-cell
audit and scoped owner acceptance of the green preview. Local restore uses
verified copies or the pinned producer and retained derived LiDAR inputs; no new
decoder installation, raw download or remote backup is needed. The
[receipt](../../worldgen/terrain/benchmarks/sa_calobra/world_data/vegetation_domains_receipt_2026-10-04.json)
records byte/logical hashes and clean regeneration. Neither visual acceptance
nor this candidate profile admits production planting or complete road safety.

## Bounded PCGEx mask candidate — 2026-10-04

Profile `sa-calobra-pcg-masks-candidate` extends the 87-file vegetation closure
with 402 retained source/derived/review files (489 total). Its byte PASS is
separate from native integration, human acceptance or full World Authority.
Use `verify --profile sa-calobra-pcg-masks-candidate --root <world-data-cache>
--repo <checkout>`; `explain pcg_masks`, `explain regional_hydrology`,
`explain frozen_road`, `explain road_masks` and `explain context_exclusions`
report identity, sizes, source limits and local-only restore. No remote backup
or automatic road rebuild is registered.

The official GOIB provisional hydrography snapshot has 106 AOI features and
dataset-specific Creative Commons Attribution evidence; source years remain
2010 / 95 as delivered. Mask water/infrastructure holdbacks are decorative 5m
fallbacks, not measured channel widths or regulated distances. Road inputs are
owner-authorized frozen c5573b3 output artifacts; original PARTIAL_IMPORTED and
engineering/collision limits remain unchanged. Raw/rasters/PNGs stay outside Git.

The bounded consumer receipt records `PASS_MASK_READ_ONLY`; it does not run a
PCGEx graph. Radius/clearance are explicit, unknowns reject placement, high
selectors reject invalid height. Earlier green visual acceptance covers character;
new holdbacks still need review. Historical blocked profiles keep their original
scope and point to the successor candidate rather than rewriting old evidence.
Full-authority readiness continues to fail closed while its admissions are missing.
