# Sa Calobra — near-landscape-2 prepared-only black region (2026-10-09)

## Diagnosis from original native output

Evidence: [native run 37892732453](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37892732453), artifact [11599281622](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37892732453/artifacts/11599281622), exact SHA `7e37eec2a2190ef89cb448addec8fb8d7f9e61d7`. Independent 1920x1080 PNGs, identical camera/target/FOV within each baseline/prepared/checker triplet. Diagnostic threshold: pixel counts as dark when all RGB channels are below 16, and a view is flagged if at least 20% are prepared-only dark while each control has <=3% dark pixels.

| Source-bound near frame | Baseline dark | Prepared dark | Checker dark | Prepared-only dark |
| --- | ---: | ---: | ---: | ---: |
| near-landscape-1 | 0.0000% | 0.0255% | 0.0000% | 0.0255% |
| **near-landscape-2** | **0.0000%** | **51.3312%** | **0.0000%** | **51.3312%** |
| near-landscape-3 | 0.0000% | 0.0000% | 0.0000% | 0.0000% |

The entire black region is introduced by the Prepared mode at the same pose. The earlier speculative claim that *camera placement alone* causes the black region is therefore unsupported. Camera sampling still cannot certify actual owner pixels; `rendered_pixel_depth_verified=false`. Checker emits diagnostic color via emissive and a neutral normal, so it isolates a very different shader path. Neither this comparison nor collision raycasts identify the exact cause of the black area. Suspects include real shadowing amplified by the prepared material's normal chain, mistaken tangent/world normal interpretation, or other material-light interaction. **No geometry hole, mask defect or normal bug is proven yet.**

## Code safeguard and next constrained native experiment

New `scripts/ci/sa_calobra_whole_map_visual_review.py` assesses immutable triplets, verifies paired camera identity and includes full PNG provenance in a new `whole-map-visual-anomaly-review.json`. It reports `VISUAL_REVIEW_REQUIRED` rather than treating green technical CI as visual acceptance. The existing 43 primary frames and proof contract stay intact. A normal-debug native experiment must be separate: same camera and exposure, A/B prepared normal intensity (default 0.75 vs 0), shadow-on/off if feasible, plus an occlusion/depth witness. Keep those images outside the admitted 43-frame set. Only change the material graph if this experiment proves the source. No v8 geometry, roads, BOB, mask or saved map changes.

**Acceptance:** sample must no longer have newly darkened large regions in Prepared versus baseline and checker; repeat across all near probes, confirm root/source/camera identity and restore the scene; full 43/43 technical proof and exact-head CI remain required. Visual/performance/production acceptance remain PENDING_OWNER/NOT_MEASURED/UNAUTHORIZED.

## Native 43+8 witness result — 2026-10-09

[Run 37903867604](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37903867604), exact `9830926a7f497cc7b63f698b5a5fe1ad605b48ee`: Unreal captured **43 primary images plus 8 additional diagnostic images**, with `WHOLE_MAP_PREPARATION_PASS`, `diagnostic_complete=true`, `native_modes=51` and `cleanup.status=RESTORED`. The independent native verifier correctly **FAILED** because it still required exactly 43 v8 guard records and did not account for the 8 additional diagnostic records. This is a *verifier contract mismatch*, not a demonstrated source/map regression. Original preserved [artifact 11603537594](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37903867604/artifacts/11603537594): 185,433,158 ZIP bytes.

The strict fix requires the full original 43-frame guard sequence **followed by** all 8 exact expected diagnostic guard records, rejecting missing/reordered/duplicated entries. The original sequence is unchanged. Previous failed workflow status remains FAILED; this note does not relabel it green.

Measured almost-black pixels (all RGB components under 16) from the **same run**:

| Frame | Prepared | Flat micro-normal (0) | Dynamic shadows off |
| --- | ---: | ---: | ---: |
| near-landscape-2 | 41.0646% | 32.7528% | **4.1332%** |
| seam-close | 28.0525% | 29.8538% | **9.9161%** |
| ground-1-2 | 26.0698% | 27.6656% | **0.5620%** |
| window-0021-forward-00005 | 12.2949% | 12.5396% | **6.1462%** |

Shadows-off has a stronger effect than flattening normals across all four. These are percentage shares of *rendered image pixels*, not square metres of defects. No normal/shadow root cause or geometry defect is proven yet. The next work is an owner/occluder/depth witness and physically plausible shadow fix, without disabling game shadows. Do not edit production assets or merge the Draft PR before new exact-head proof and visual sign-off.
