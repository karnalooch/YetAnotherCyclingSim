# Natural20 source support audit — #365 / M3, 2026-10-12

Status: read-only source/contract audit. No source, UE, Blender, GPU, terrain, road or scatter mutation. No terrain-contact measurement or qualification is claimed for these twenty assets. The coordinator owns subsequent native operations and proof admission.

## Pinned source evidence

Producer receipt: `D:/yacs/work/pcg365/natural-rock-collection03/derived/natural-rock-collection.json`, SHA256 `3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc`. It contains twenty variants/eight licensed source families, explicit component/cut/ART recipes, closed connected consistently wound positive-volume topology, cap loops and uniform-density closed-volume COM. Producer LF SHA `1290715fa7692a5e5c8d19926ef3dca61d71e6b09124c9c6d16eafbff2b960ca`. This local producer proof does not replace native source/package/triangle/bounds authentication.

Existing calculators reviewed: `scripts/assets/pcg_boulder_support.py`, `pcg_rock_contact_policy.py`, `pcg_rock_patch_diagnostic.py`; existing native consumer `scripts/ue/sa_calobra_pcg_rock_qualification.py`. The latter currently accepts exactly two meshes/five authenticated diagnostic points; it cannot silently consume 20. A bounded new coordinator-owned integration must preserve its existing ground-owner/complex-ray/negative-control/save guards.

## Limits already frozen

V1: native actor uniform_scale 1, yaw 0, tilt 0; maximum full-footprint local slope 10 degrees; embedding no more than 20% of native transformed height H; maximum exposed height at least 80%H; at least 80% exposed rays; complete authenticated ground coverage 100%; positive sampled bottom gap 0 cm; root and embedding refinement deltas at most 0.1 cm (33-to-65; explicit V2 is65-to-129 with the same limits). Refinement is numerical stability, not DTM accuracy or continuous proof.

Source-cap diagnostic: cap identity/plane tolerance 0.01 cm, source/derived hash binding, actual LandscapeHeightfieldCollisionComponent ground, full and cap expected ray counts independent of successful hits, COM inside sampled cap hull, the same slope/burial/exposure/refinement limits. Optional planting is exactly 0 or 5%H, frozen before measurement; planting consumes the same 20% total full-geometry burial budget. A cap diagnostic PASS is DIAGNOSTIC_SUPPORT_PATCH_ONLY, not unchanged full-footprint V1 PASS or physical stability.

No per-asset threshold is invented here. The table merely converts the existing height fractions into centimetres using producer bounds. Native readback must supply the final H; recompute these products from that authenticated value. Rounded values are explanatory, never comparison tolerances. No extra sink margin, air epsilon, slope allowance or scale-dependent convergence gate is authorized.

## Per-asset source geometry and derived budgets

X/Y/H use native-axis dimension magnitudes in cm. Cap area/bbox is a source diagnostic only: the denominator is the rectangular XY envelope, not actual projected mesh area or supported/contact area. COM-cap means inside the actual declared source-loop parity region, not stability. Q means a source-only baked quarter-turn candidate if authenticated terrain steepest direction is X; it is not an approved native actor yaw.

| Asset | X / Y / H cm | Max burial 20%H cm | Optional plant 5%H cm | Min exposed 80%H cm | Cap area/bbox | Loops | COM-cap | X-slope pose candidate |
|---|---:|---:|---:|---:|---:|---:|---|---|
| boulder_01_01 | 127.214 / 179.963 / 90.345 | 18.069 | 4.517 | 72.276 | 29.6% | outer1 | OUTSIDE | identity first |
| boulder_01_02 | 136.795 / 169.779 / 81.310 | 16.262 | 4.066 | 65.048 | 29.6% | outer1 | OUTSIDE | identity first |
| boulder_01_03 | 118.798 / 187.938 / 99.379 | 19.876 | 4.969 | 79.503 | 29.6% | outer1 | OUTSIDE | identity first |
| namaqualand_boulder_02_01 | 249.569 / 123.086 / 77.672 | 15.534 | 3.884 | 62.138 | 47.4% | union2 | inside | Q90 candidate |
| namaqualand_boulder_02_02 | 269.218 / 115.888 / 69.905 | 13.981 | 3.495 | 55.924 | 47.4% | union2 | inside | Q90 candidate |
| namaqualand_boulder_03_01 | 240.710 / 306.541 / 132.587 | 26.517 | 6.629 | 106.070 | 45.5% | outer1 | inside | identity first |
| namaqualand_boulder_03_02 | 259.338 / 286.832 / 119.329 | 23.866 | 5.966 | 95.463 | 45.8% | outer1 | inside | identity first |
| namaqualand_boulder_03_03 | 224.420 / 324.062 / 145.846 | 29.169 | 7.292 | 116.677 | 45.0% | outer1 | inside | identity first |
| namaqualand_boulder_04_01 | 252.215 / 249.642 / 171.042 | 34.208 | 8.552 | 136.833 | 55.5% | outer1 | inside | identity first |
| namaqualand_boulder_04_02 | 274.543 / 235.295 / 153.937 | 30.787 | 7.697 | 123.150 | 54.9% | outer1 | inside | Q90 candidate |
| namaqualand_boulder_04_03 | 234.400 / 261.072 / 188.146 | 37.629 | 9.407 | 150.517 | 55.8% | outer1 | inside | identity first |
| namaqualand_boulder_05_01 | 136.403 / 74.798 / 48.449 | 9.690 | 2.422 | 38.759 | 17.8% | outer1 | inside | Q90 candidate |
| namaqualand_boulder_05_02 | 147.235 / 70.418 / 43.604 | 8.721 | 2.180 | 34.883 | 17.7% | outer1 | inside | Q90 candidate |
| namaqualand_boulder_05_03 | 126.919 / 78.358 / 53.294 | 10.659 | 2.665 | 42.635 | 17.8% | outer1 | inside | Q90 candidate |
| namaqualand_boulder_06_01 | 67.498 / 121.188 / 58.647 | 11.729 | 2.932 | 46.917 | 32.4% | outer1 | inside | identity first |
| namaqualand_boulder_06_02 | 72.783 / 113.691 / 52.782 | 10.556 | 2.639 | 42.226 | 32.6% | outer1 | inside | identity first |
| rock_07_01 | 16.861 / 32.014 / 12.935 | 2.587 | 0.647 | 10.348 | 61.1% | outer1 | inside | identity first |
| rock_07_02 | 18.036 / 29.940 / 11.641 | 2.328 | 0.582 | 9.313 | 62.0% | outer1 | inside | identity first |
| rock_09_01 | 7.401 / 14.462 / 2.958 | 0.592 | 0.148 | 2.367 | 44.4% | union2 | inside | identity first |
| rock_09_02 | 8.031 / 13.587 / 2.662 | 0.532 | 0.133 | 2.130 | 44.2% | union2 | inside | identity first |

All 20 COM projections lie within the source cap convex hull, but all three Boulder01 COM projections lie outside the actual concave source cap (nearest boundary approximately 13.030/12.847/13.277 cm). This does not automatically fail the existing hull rule: a distributed concave support can have a hull covering the COM. It does make hull PASS insufficient evidence of actual ground support/stability. Rotation about Z, recentering and vertical sinking do not make the source COM enter the source cap region; changing that relation requires separately declared source geometry/pose work or actual terrain support evidence. Do not reinterpret the empty concavity as a solid base.

N02 has two disjoint depth 0 outer loops (1653 and 20 vertices). Rock09 also has two disjoint depth 0 outer loops (401 and 12 vertices). They require explicit DISJOINT_OUTER_UNION_V1 in the existing diagnostic, with every loop preserved; treating the second as a hole or silently omitting the small region is incorrect. Every other source has one outer loop. No current 20 source has a declared hole or nested loop. Convert all XY/COM from Blender metres to UE centimetres with (x,y)->(100x,-100y); this reverses winding but preserves the region. Authenticate native bounds and cap-bottom complex rays independently.

Producer cap_validation area is the pre-ART source cap witness; cap_xy_loops_m areas are transformed per variant. For nonidentity ART recipes do not use the pre-ART area as native cap area. COM is already transformed by the declared source-to-variant affine; do not transform it twice. cap_z remains 0. Source cutting and closedness do not prove that all peripheral lower geometry is on this cap.

## Prior actual contact evidence and its limits

Historical [larger-rock evidence](../pcg365-large-rocks-20261012/README.md) reports both unchanged full-footprint V1 decisions REJECTED. The separate source-cap point3 diagnostics passed, while remaining peripheral positive gaps were 20.693365 cm for half-scale quarter-turned N02 and 50.458336 cm for N06. N06 required65-to-129 refinement; earlier33-to-65 did not converge. Both max slopes were 9.937148 degrees. Neither cap diagnostic or render was production placement acceptance.

The historical N02 full-size/half-unrotated footprint sampled 18.7739 degrees at point3; half-scale quarter-turn reduced the sampled footprint to a different region. Current natural20 N02 is full-size/unrotated, roughly 2.50 x 1.23 m, not that historical 1.25 m accepted diagnostic source pose. Its file/hash/transform and footprint changed: the old favourable numbers cannot be copied. Natural20 N06 baseline shares the broad source preparation lineage but is a distinct exported FBX and requires new native authentication/measurement.

Historical Rock07 planar support still had a peripheral undercut of roughly 11.64 cm over 12.93 cm height; the new source family retaining natural upper shape does not remove that failure by renaming/export. Rock09 is only 2.66-2.96 cm tall: its total burial budget is 0.532-0.592 cm and 5% planting only 0.133-0.148 cm. Do not turn native sample convergence or old source/native residuals into a fabricated DTM accuracy guarantee.

## Smallest native continuation without weaker gates

1. Authenticate every exact 20 FBX/package, actor scale 1/yaw 0/tilt 0, native triangle count/bounds/material binding, source-cap declaration and actual ground owner. Keep accepted Landscape/road/map/source package hashes unchanged; no Landscape/save-map operations. A studio plane is not real Terrain Authority evidence.
2. Start identity orientation at already authorized, mask/source-valid diagnostic XY; do not assume a common centre suits every footprint. Full footprint must be within source coverage/exclusions and authenticated Landscape. Terrain steepness must be measured across each actual mesh footprint, not only at its pivot or cap. Missing masks/NoData/owner hits reject; do not search arbitrary flat terrain to force 20 passes.
3. Measure paired complex bottom/top mesh intervals and bounded Landscape-only ground at 33 and 65. Evaluate original full-footprint V1 independently. If it fails only numerical convergence, explicit65-to-129 refinement retains all physical gates. Unpaired rays, missing ground, invalid controls or process failure reject.
4. Freeze the separate source-cap planting alternative at 0 and/or 5%H before native measurements. The cap root is min(ground-bottom) over cap rays minus declared planting; the full nonpenetrating root is max(ground-bottom) over all rays. Burial is their difference, not planting alone. Recompute full exposure/peripheral gaps and the existing cap diagnostic. Do not repeatedly lower until it looks grounded.
5. Source orientation candidates are geometry-driven: align the narrower footprint with measured terrain-gradient direction while retaining the planar base horizontal. For the historically X-directed steep variation, identity is the first candidate for Boulder01/N03/N06/Rock07/Rock09; source-baked Q90 is worth a separate bounded test for N02/N05 (and N04_02 if needed). N04 is broadly square, so quarter-turn benefits are limited. This is an ordering heuristic, not a claim of fit or licence to alter the masks.
6. Existing V1 rejects nonzero actor yaw and tilt. Any Q90 diagnostic must remain explicitly unsupported under unchanged V1, or be a separately produced/baked rigid source derivative with new hash/matrix/cap/COM/bounds and native actor yaw 0. Do not change yaw_deg in the policy or relabel the measurement. No tilt/alternate support-face recut is proposed for this20 batch; those would require a separate bounded source-preparation proof.
7. Source-only support risks prioritize low-angle real UE views: Boulder01 concave cap/COM region; N05 small cap relative to broad bbox (about18%); N06 previously large peripheral gap; Rock07/09 small-height and peripheral undercut. N03/N04 provide new broad morphology but need genuinely sufficiently level authorized ground across their 2.4-3.2 m footprints. Materials/shadows cannot repair an actual positive peripheral gap.
8. Preserve every rejection and exact process exit status. Render real Landscape seating from multiple low angles for all technical candidates. A visually pleasing render, cap diagnostic or local successful process cannot self-admit regional scatter, continuous support, physical stability, performance or whole-M3 acceptance. If fewer than 20 meet unchanged gates, deliver the measured split and remaining blockers rather than claim 20 qualified.

## Audit result

Source receipt/hash binding, loop classification, absolute fraction calculations and COM source-region/hull checks were performed with standard Python only. No new contact sample, UE process, Blender process, GPU capture, source geometry edit, policy edit or terrain/road/scatter mutation was executed. This document is the sole new authored path for the audit. Placement remains false; qualified_assets remains empty.
