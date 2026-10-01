# Sa Calobra road delivery priority

This note defines a bounded engineering order for the road network inside the
Sa Calobra 8 km x 8 km terrain benchmark. It is a planning input, not route,
physics, surface, access or gameplay authority.

## Area and inventory

- WGS84 bounds: `2.76258,39.80384,2.85626,39.87588`;
- OpenStreetMap snapshot timestamp: `2026-10-01T20:46:35Z`;
- inventory is clipped to the benchmark polygon before length aggregation;
- motor-road classes: 31.294 km;
- `highway=track`: 20.790 km;
- path-class features: 82.421 km;
- all inventoried `highway=*` geometry: 134.506 km.

The first authoring scope is the 52.084 km motor-road plus track network. The
82.421 km path inventory stays visible for completeness, but a path is not
automatically a rideable gravel road. Surface, width, access, obstacles and
topology must be verified before authoring or gameplay admission.

Machine-readable totals and named-road lengths are recorded in
`sa_calobra_road_inventory_2026-10-01.json`.

## Delivery order

### P0 — first complete road slice

Author and validate these connected motor-road corridors first:

1. `Ma-2141` / Coll dels Reis to Sa Calobra — 12.876 km;
2. `Ma-10` connection inside the benchmark — 7.040 km;
3. `carretera de Cala Tuent` spur — 3.694 km.

Together they form the first useful continuous road skeleton for terrain,
road-carving, earthworks, junction and rider-camera validation. This priority
comes from benchmark coverage, named-road continuity and the need to prove one
connected slice before expanding the network.

### P1 — verified mixed-surface connectors

Add named and topologically useful `highway=track` segments only after field or
authoritative-source checks confirm bicycle access, surface class, usable width
and connection to the P0 skeleton. A track tag alone is insufficient evidence
for a rideable gravel road.

### P2 — remaining motor access and service roads

Add unnamed residential, service and unclassified motor roads after the main
skeleton. Preserve their real junctions and elevation separation; do not merge
them into nearby terrain or infer access from geometry alone.

### P3 — remaining tracks

Author the remaining verified tracks after P0-P2 topology and terrain ownership
are stable. Unknown access or surface remains explicitly unknown.

### P4 — paths and optional detail

Keep path-class features for inventory and later inspection. Do not promote
footways, steps, difficult MTB paths or uncertain features into gravel gameplay
without separate evidence and acceptance.

## Strava evidence boundary

The Strava Global Heatmap was inspected locally as a non-authoritative planning
reference. No Strava tiles, screenshots, sampled intensity values, ranked
geometry, CSV, GeoJSON or derivative heatmap artifact is included in YACS.

Strava's current Terms prohibit automated collection from the service and
restrict copying, modification and derivative works. Therefore local heatmap
observations cannot become a committed dataset, deterministic build input,
route authority or acceptance proof. Future use requires a separately approved
Strava data agreement or another redistribution-safe source.

Official terms reviewed on 2026-10-01:

- https://www.strava.com/legal/terms
- https://www.strava.com/legal/api_policy

## Acceptance gates per road

Before a road moves from inventory into the authored world, verify:

1. geometry and topology against a redistributable authoritative source;
2. surface, width, bicycle access and obstacle semantics;
3. vertical placement against the benchmark DTM and separation at crossings;
4. deterministic regeneration and provenance metadata;
5. rider-camera geometry, junction and earthwork proof;
6. Road Physics Profile admission as a separate decision;
7. performance against the World Building Bible budget and proof cadence.

The World Building Bible remains the methodology authority. This note only
orders the bounded Sa Calobra benchmark work.
