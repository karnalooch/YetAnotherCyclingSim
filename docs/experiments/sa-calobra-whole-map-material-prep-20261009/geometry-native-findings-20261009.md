# Geometry verification — native evidence 2026-10-09

## Provenance

- PR #446 exact native HEAD: `9972803b67812ea8584473d076e588d4452a2628`.
- Native run: https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37911204919
- Artifact 11606693801: https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37911204919/artifacts/11606693801
- Independent CyclingSim CI at same SHA: https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37911213609

## Verified results

- Native capture receipt `WHOLE_MAP_PREPARATION_PASS`, 43 primary frames, 8 normal/shadow diagnostic frames, `diagnostic_complete=true`, `cleanup.status=RESTORED`.
- Native receipt `WHOLE_MAP_EVIDENCE_VERIFIED` and independent `whole-map-geometry-collision-review.json` = `COLLISION_GEOMETRY_EVIDENCE_VERIFIED`.
- Four source-bound views (near-landscape-2, seam-close, ground-1-2, window-0021-forward-00005), each 9 vertical rays from +150000 to -150000 cm; total **36 sites / 72 traces**.
- All 36 world-first and Landscape-only collision measurements returned exactly the **same vertical height** (`height_delta_cm = 0.0`); no extra collision surface above the owning Landscape was observed **at those XY locations**.
- All 36 labels = `WORLD_HIT_OWNER_UNKNOWN` because native Unreal 5.8 did not expose hit actor/component names through this Python reflection route. This must not be converted to `LANDSCAPE_FIRST_HIT` without independent owner identity proof.

## Limitations and decision

These traces are valuable negative evidence against a *collidable, higher surface at the sample sites*, not against a bad rendered mesh or hidden shadow caster somewhere else. The camera can see a different part of the scene from its source target. Collision-disabled surfaces and geometry affecting shadows remain unmeasured; displayed normals/shadow maps are not collision.

Thus **there is no confirmed geometry error to patch at any sampled point**. Do not deform accepted v8, Landscape, BOB or roads speculatively; source map remains unchanged and visual acceptance is PENDING_OWNER. The current observation supports additional *screen-space dark-pixel scene-depth/occluder* proof, prioritized in Issue #456 before a bounded geometry modification.

## Geometry correction acceptance contract

New proof must bind actual selected black pixels to same-frame camera FOV and pose, raycast to both visible primitive and Landscape, and identify the shadow caster including collision-disabled meshes. Record source triangle/vertex set, winding/normal errors, exact localized spatial delta, pre/post image and preserved geometry outside patch. If verified, repair only this bounded geometry and rerun exact-head native proof with shadows ON.
