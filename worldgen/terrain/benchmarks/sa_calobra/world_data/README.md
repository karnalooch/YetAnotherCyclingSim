# Sa Calobra World Data Stack v1

Issue #335 prepares bounded real-world inputs for Landscape materials and PCGEx
without changing accepted terrain, road or physics authority.

## Golden Hairpin AOI

The first planning AOI is a 1 km × 1 km square in EPSG:25831 centered on the
current Ma-2141 source part 3 / vertex 43 diagnostic focus:

- center: E 484056.322036, N 4408951.208023;
- WGS84: lon 2.81367791300534, lat 39.830409456831;
- bounds: E 483556.322036..484556.322036,
  N 4408451.208023..4409451.208023.

The current road diagnostic is 300 m of source arc length. The 500 m square
half-extent gives bounded context around it without expanding acquisition to the
whole active Landscape or island.

## Source state

`golden_hairpin_sources.json` is the committed acquisition contract. At this
checkpoint it contains **no claimed exact CNIG files**. Four 1 km LiDAR grid-cell
locator hints are derived from the AOI, but they are not provider filenames or
section IDs.

Run:

```powershell
python scripts/assets/plan_sa_calobra_world_data.py
python scripts/assets/plan_sa_calobra_world_data.py --json
```

The planner fails closed if AOI geometry drifts, locator hints no longer match the
1 km grid, raw cache leaves `ExternalAssets/`, duplicate source IDs appear, or a
source is marked acquired/included/derived without exact file name, byte size,
SHA-256 and provider detail URL.

## Authority boundary

- accepted `Base_DTM` remains ground authority;
- canonical road XY / Road Physics Profile remain unchanged;
- BOB remains Road & Earthworks authority;
- PCGEx and Landscape materials consume normalized World Data Stack outputs;
- raw provider payloads are not committed wholesale;
- unknown or conflicting evidence remains unknown until reviewed.
