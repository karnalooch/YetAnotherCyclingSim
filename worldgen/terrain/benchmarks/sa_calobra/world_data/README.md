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
