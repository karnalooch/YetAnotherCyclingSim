# Sa Calobra World Data Stack v1

Issue #335 prepares bounded real-world inputs for Landscape materials and PCGEx
without changing accepted terrain, road or physics authority.

## Current acquisition boundary

The source-acquisition boundary is now the **entire active Unreal working square**,
not only the Golden Hairpin:

- CRS: EPSG:25831;
- bounds: E 483000.0..485016.5, N 4407500.0..4409516.5;
- size: 2,016.5 m × 2,016.5 m;
- area: ~4.0665 km²;
- center: E 484008.25, N 4408508.25;
- WGS84 center: lon 2.8131269468, lat 39.8264174916.

This square intersects nine 1 km PNOA LiDAR grid cells:

`483-4407, 484-4407, 485-4407, 483-4408, 484-4408, 485-4408,
483-4409, 484-4409, 485-4409`.

These are locator hints only, not guessed CNIG filenames. Exact source identities
must be verified before they are marked acquired.

## Source set requested now

- existing admitted MDT50cm ground source: reuse, do not duplicate;
- PNOA LiDAR 3rd coverage **NPC03** for all intersecting working-space cells;
- MDS50cm 3rd coverage V1 as surface-height cross-check only;
- PNOA Máxima Actualidad 2024 orthophoto/service extract;
- BTN vector context for the same bbox;
- SIOSE 2014 WFS land-cover cross-check;
- DG Catastro INSPIRE Buildings WFS extract.

Large raw payloads persist on the self-hosted runner under the YACS world-data
cache and are not committed wholesale. The repository stores manifests, hashes,
receipts and explicitly admitted bounded derived products.

Run the planner locally or in CI:

```powershell
python scripts/assets/plan_sa_calobra_world_data.py
python scripts/assets/plan_sa_calobra_world_data.py --json
```

The planner fails closed if AOI geometry drifts, 1 km LiDAR cell hints no longer
match the bbox, raw-cache policy becomes unsafe, duplicate source IDs appear, or
an acquired/included/derived source lacks exact file identity/hash evidence.

## Exact CNIG source inventory acquired and verified 2026-10-03

The CNIG public product-page coordinate search was executed in headless Chromium
without attempting download authorization. The current working square resolves to:

- **9 LiDAR NPC03 LAZ files**, 2024 Baleares, ~448.66 MB as displayed by CNIG;
- **4 MDS50cm COB3 V1 COG files**, ~446.92 MB displayed total;
- **4 PNOA Máxima Actualidad 2024 source COG files**, ~2,289.31 MB displayed total.

Exact provider records, delivered filenames, byte sizes, SHA-256 values, `sec`
identifiers and detail URLs are pinned in `working_space_sources.json`. The 17
source binaries were downloaded manually through CNIG's provider-authorized bulk
download flow and verified read-only in the persistent runner cache:

- 17 files, 3,339,596,438 bytes total;
- 9 LAZ files with the expected `LASF` signature;
- 8 TIFF files with the expected little-endian BigTIFF container signature;
- no missing catalogue records and no unexpected files.

CNIG delivered the nine LAZ and four orthophoto filenames with underscore
separators (and lowercase `h25` / `.tif` for orthophotos), while the catalogue
uses hyphens and uppercase tokens. The receipt preserves both names and records
the one-to-one reviewed match; raw files are not renamed. See
[`manual_cnig_receipt_2026-10-03.json`](manual_cnig_receipt_2026-10-03.json) for
the complete 17-file inventory.

The repository is public, so these raw files are not published through a normal
release by default. Issue #335 maintains a private-to-writers **draft release**
named `data-cnig-sa-calobra-working-v1-2026-10-03` with the verified 17-file
raw snapshot, receipt, working manifest and asset inventory.
The cross-project reconciliation and publication boundary are recorded in
[`docs/legal/USED_ASSET_INVENTORY_2026-10-03.md`](../../../../../docs/legal/USED_ASSET_INVENTORY_2026-10-03.md).
Publishing that draft requires a separate explicit owner decision.

On a clean trusted Windows host, restore and verify only the 17 raw files with:

```powershell
# Preview authenticated remote/local state.
pwsh -NoProfile -File .\scripts\assets\Restore-YacsSaCalobraWorldData.ps1

# Download missing files and require 17/17 matching SHA-256 values.
pwsh -NoProfile -File .\scripts\assets\Restore-YacsSaCalobraWorldData.ps1 -Apply
```

The script is idempotent, never overwrites an existing file and fails closed on
unexpected files, size drift, hash drift or a non-draft release.

For immediate world-authoring work, the acquisition runner separately downloads
the same-AOI **PNOA WMS orthophoto extract**, BTN vector context, SIOSE cross-check
and Catastro Buildings WFS data, which are available through official services
without that binary-download authorization flow.

## Expansion order

1. acquire and validate the current 2.0165 km working square;
2. generate first World Data Stack derivatives and feed bounded PCGEx/Landscape consumers;
3. only after that proof, expand the exact same contract to the existing 8 km × 8 km benchmark.

## Authority boundary

- accepted `Base_DTM` remains ground authority;
- canonical road XY / Road Physics Profile remain unchanged;
- BOB remains Road & Earthworks authority;
- PCGEx and Landscape materials consume normalized World Data Stack outputs;
- MDS/orthophoto/canopy products never replace ground-Z truth;
- unknown or conflicting evidence remains unknown until reviewed.
