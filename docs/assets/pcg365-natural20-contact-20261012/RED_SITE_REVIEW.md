# #365 — Red diagnostic sites for joint Unreal review

**Status:** Implementation candidate; native red-overlay proof **NOT RUN** until
a new exact-SHA [owner-triggered workflow](../../../.github/workflows/pcg365-red-site-review.yml)
produces a clean exit-0 receipt and the real images are inspected. This
checkpoint does not claim an interactive UE Remote/PixelStreaming connection.

## Decision and scope

Owner requested marking the five problematic positions red in an Unreal review,
then deciding together what to preserve or alter. No geometry should be
automatically fixed. This is a transient presentation layer applied to the
**accepted, saved Sa Calobra Landscape** consumed at the successful
[three-session #365 native proof](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278235093).

The five P0–P4 XY centres are historical diagnostic vegetation-selector cells,
**not admitted rock-scatter domains**. Display red = reject/inspect; not
permission to flatten slopes, relocate a rock into NoData, amend a road, mask
an air gap with material or auto-place foliage.

| Label | Source XY (cm) | Sampled max slope range | Historical V1 |
|---|---|---|---|
| P0 | (16800, 70400) | 38.20–45.64° | REJECTED 20/20 |
| P1 | (4800, 96800) | 52.81–53.87° | REJECTED 20/20 |
| P2 | (184800, 180800) | 35.17–43.69° | REJECTED 20/20 |
| P3 | (181600, 189600) | 5.88–18.77° | REJECTED 20/20 |
| P4 | (91200, 200800) | 26.46–29.92° | REJECTED 20/20 |

The group minima/maxima are per-mesh sampled footprint values, not a
uniform GIS slope at the point. Every case also exceeded at least one
embedding/exposure gate. This does not establish that the full area is too
steep for any rock.

## Implemented bounded reviewer

- Machine-readable authority: [immutable red review manifest](../../../worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json) pins five coordinates, native producer SHA, contact receipt digest, accepted map hash and all-false production flags.
- [Runtime diagnostic script](../../../scripts/ue/pcg365_red_marker_preview.py) loads only the original, completed **d361e765** contact stage in its separate owned UE project, authenticates all 100 retained decisions, queries actual Landscape collision for marker height and creates five transient red TextRender Actors.
- The one-process offscreen reviewer requests two native 1920×1080 frames plus two warmups per site, verifies PNG bytes and unchanged map. It destroys its temporary labels. One real process exit zero is required for the launcher marker.
- [Offline tests](../../../scripts/ue/test_pcg365_red_marker_preview.py) enforce site count/identity, case completeness, unchanged rejection and no production admission. CI is required before any Editor/GPU work.
- User-visible UE Remote is a **separate browser client/stream admission gate**. This workflow captures actual UE PNGs on the remote Windows runner; it does not create or claim PixelStreaming, an active Editor browser session or an exposed LAN URL. Existing #364 Stream Level Editor launcher is scoped to its road snapshot; it must not be silently repointed to this distinct world stage.

## What we decide after viewing

For each P0–P4: **leave as steep terrain**, **keep excluded from rocks**, or
**request separately scoped source/mask geometry investigation**. The default
remains excluded; neither a red label nor a pleasing screenshot promotes it
to an approved World Authority rock location.

Separately, the World Authority owner must establish mask-valid candidates
with known/exclusion/NoData provenance; Blender can prepare source-preserving
support and baked-quarter-turn variants with new hashes. None of those should
be described as completed by this presentation review.

All existing #365 requirements retain `qualified_assets: []`,
`placement: false`, `full_qualification: false`,
`PENDING_FINAL_M3`, `DEFERRED_AFTER_M3`, `performance_pass: false`.
Frozen Landscape, `Base_DTM`, roads, georeferencing and physics remain intact.
PR #474 Draft; #365 remains open. Paused #475 runner cleanup is untouched.
