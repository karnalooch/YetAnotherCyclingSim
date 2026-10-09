# Sa Calobra — geometry collision triage (2026-10-09)

## Why inspect geometry now?

The four original camera poses in Issue #455 show strong changes when dynamic shadows are disabled. This **does not establish a shading engine bug**: intersecting road/cliff/BOB geometry and incorrect shadow casters remain plausible. Native evidence proved only that material preparation did not mutate accepted v8 geometry, not that the earlier geometry was intrinsically correct.

## Read-only native examination

On the fixed original camera target for near-landscape-2, seam-close, ground-1-2, and window-0021-forward-00005, sample nine points (centre, axial and diagonal offsets of +/-200 cm). From each world XY position trace vertically from +150000 to -150000 cm via UE complex visibility collision, comparing two queries:

1. **Landscape-only**: ignore every other actor.
2. **All-actors**: ignore none, record first hit and the owning actor/component.

Store 36 paired samples / 72 traces in the native report. Record owner, impact, collision normal, face index when reported, component cast-shadow flag when available, and the height difference. A non-Landscape-first hit >2 cm above terrain becomes NON_LANDSCAPE_SURFACE_ABOVE, **not** a declaration of a geometry defect: roads, rocks and overhangs can be valid. Missing traces and unknown owners remain explicit.

Collision-disabled objects may still cast shadows; this witness does not establish per-pixel rendering ownership, virtual shadow map correctness, occluder identity in the final rendered frame, or a repair. The host verifier recomputes all 36 ray positions from independently admitted frame poses, checks hit ranges, actor inventory, classes and categories, and rejects fabricated claims of geometry repair.

## Actual geometry repair gate

Before changing accepted Landscape / DynamicMesh / roads / BOB, correlate candidate contact defects with a rendered depth and shadow-caster witness. If a specific, bounded defect is confirmed, use a separate, rollbackable local repair with exact per-triangle before/after normals, cut/fill delta, area and restored source snapshot. Re-run the 43+8 native image proof and verify an improvement without globally disabling shadows. Owner acceptance stays pending; PR #446 remains Draft.

Source native report: capture/whole-map-prep/whole-map-prep-receipt.json, key geometry_collision_witness. Independently verified sidecar: whole-map-geometry-collision-review.json. Original 43 primary PNGs and 8 normal/shadow witnesses remain unaffected.
