# Natural20 contact contract audit — #365 / M3

Historical preflight audit; subsequent execution is recorded in [README](README.md).

Read-only design audit. No native contact run, placement, terrain edit or
qualification is asserted. Authority: agent router, procedural-world owner,
World Building Bible and M3 world operations policy. Landscape and road truth
remain frozen; diagnostics consume the authenticated terrain package.

## Existing frozen gates

`scripts/assets/pcg_rock_contact_policy.py` owns the executable V1 contract:
native uniform scale 1, yaw 0, tilt 0; maximum measured local ground slope 10°;
required embedding at most 20% of transformed AABB height; maximum exposed
height at least 80% of height and exposed intervals at least 80% of sampled
mesh intervals. Positive sampled bottom gap must be zero. Every sampled mesh
interval needs authenticated ground of class
`LandscapeHeightfieldCollisionComponent`. Incomplete coverage rejects.

V1 requires 33×33 and 65×65 measurements, with root and embedding differences
at most 0.1 cm. Explicit V2 uses 65×65 and 129×129 with identical physical
limits. Numerical convergence is not terrain accuracy or continuous proof.
`solve_support` fits root Z to `min(ground-bottom)`; the nonpenetrating root is
`max(ground-bottom)`. Their difference is required embedding. All-submerged
fits reject. Paired mesh misses are outside the sampled silhouette; unpaired
hits and missing ground must remain failures, not successful support samples.

## Existing input boundary

`sa_calobra_pcg_rock_qualification.py` currently requires
`rock-qualification-request.json` with integer `schema_version: 1`,
`scope: ISOLATED_ROCK_QUALIFICATION_ONLY`, `placement: false`,
`qualified_assets: []` and exactly two unique `assets`. Source paths must match
`rock-source/[A-Za-z0-9_-]+.fbx` and exact source hashes/sizes. Native import
witnesses include expected LOD0 triangles and source/native bounds.
Optional `policy` must equal the frozen policy exactly.

`points` defaults to `contact-request.json.points`; it must equal those points
exactly and contain five records, each with finite two-element `world_xy_cm`.
Keep candidate IDs, source cells, seeds and source/selector identities from
the authenticated producer; matching arbitrary XY JSON alone does not create
geographic authority. `qualification-sources.json` binds the consumed terrain
map. The native consumer requires exactly one Landscape, XY scale 50 cm and
zero rotation. Package/source hashes, before/after transforms and no map save
must be retained for any new run.

The natural20-forge01 stage's existing rock-qualification request still names
the earlier two prepared Namaqualand02/06 sources. It does not describe or
qualify the twenty natural20 assets. Natural20's verified import/reload and
studio render record terrain contact `NOT_RUN`.

## Smallest bounded adaptation

Prefer a separately scoped collection contact consumer that loads the twenty
already saved, hash-verified mesh packages and reuses `measure_grid`,
`solve_support` and the unchanged policy evaluator. Bind the collection catalog,
all twenty package/source identities, actual material binding and five
authenticated contact sites. Record a complete 20×5 case matrix, including
failures, rather than quietly selecting successful rocks or sites. Identity
actor rotation/scale must remain explicit; baked source poses retain their
source recipe and unit evidence. Re-importing meshes is unnecessary.

Alternatively, ten independent two-asset requests can preserve the existing
reader boundary, but each needs distinct output/package handling and authentic
collection source identities. Neither approach permits an implicit two-to-twenty
schema change or relaxing thresholds to obtain a pass.

Old planar-cap declarations for prepared02/06 cannot be reused as proof for
eight families and twenty new derivatives. The separate source-cap diagnostic
requires a source-hash-bound, topology-verified cap and valid loops, cap Z=0,
cap tolerance 0.01 cm and declared planting fraction 0 or 0.05. It retains full
footprint ground coverage and full-geometry embedding/exposure limits; convex
sample-hull COM containment is not physical stability proof. Its result cannot
replace V1/V2 failure or admit continuous contact. New cap preparation, if
needed, requires its own declared derived-source evidence.

Even a successful matrix yields only sampled contact. Source rights, units,
topology/collision, material deformation limits, actual terrain render and owner
visual review remain separate. No regional geology or scatter admission follows
from this audit.

## Local implementation candidate

`scripts/ue/sa_calobra_pcg_collection_contact.py` now implements the separate
saved-package consumer. Ten batches select two sorted catalog IDs each and
retain five cases per mesh, 33/65 grids and optional convergence-only 129
refinement. Aggregate reload authenticates ten exact-head launcher receipts,
source/catalog/package identities, all raw grid hashes and the complete
100-case key matrix. The capture subclass requests two real views of every
mesh at a measured root and labels rejected cases. If any mesh has no usable
measured fit, rendering rejects rather than inventing a placement.

Five CPU tests passed at the initial consumer checkpoint: batch coverage, marker
identity, terrain conservation, incomplete-ground/unpaired-hit rejection and numeric gates. Ruff passes.
No UE import, launcher execution, terrain-contact result or GPU capture has
been performed by this implementation task; native API behavior remains to
be verified by the serialized parent-owned consumer run.
