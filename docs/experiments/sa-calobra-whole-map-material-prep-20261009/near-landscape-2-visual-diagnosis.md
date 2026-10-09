# Sa Calobra — near-landscape-2 prepared-only black region (2026-10-09)

## Diagnosis from original native output

Evidence: [native run 37892732453](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37892732453), artifact [11599281622](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37892732453/artifacts/11599281622), exact SHA \`7e37eec2a2190ef89cb448addec8fb8d7f9e61d7\`. Independent 1920x1080 PNGs, identical camera/target/FOV within each baseline/prepared/checker triplet. Diagnostic threshold: pixel counts as dark when all RGB channels are below 16, and a view is flagged if at least 20% are prepared-only dark while each control has <=3% dark pixels.

| Source-bound near frame | Baseline dark | Prepared dark | Checker dark | Prepared-only dark |
| --- | ---: | ---: | ---: | ---: |
| near-landscape-1 | 0.0000% | 0.0255% | 0.0000% | 0.0255% |
| **near-landscape-2** | **0.0000%** | **51.3312%** | **0.0000%** | **51.3312%** |
| near-landscape-3 | 0.0000% | 0.0000% | 0.0000% | 0.0000% |

The entire black region is introduced by the Prepared mode at the same pose. The earlier speculative claim that *camera placement alone* causes the black region is therefore unsupported. Camera sampling still cannot certify actual owner pixels; \`rendered_pixel_depth_verified=false\`. Checker emits diagnostic color via emissive and a neutral normal, so it isolates a very different shader path. Neither this comparison nor collision raycasts identify the exact cause of the black area. Suspects include real shadowing amplified by the prepared material's normal chain, mistaken tangent/world normal interpretation, or other material-light interaction. **No geometry hole, mask defect or normal bug is proven yet.**

## Code safeguard and next constrained native experiment

New \`scripts/ci/sa_calobra_whole_map_visual_review.py\` assesses immutable triplets, verifies paired camera identity and includes full PNG provenance in a new \`whole-map-visual-anomaly-review.json\`. It reports \`VISUAL_REVIEW_REQUIRED\` rather than treating green technical CI as visual acceptance. The existing 43 primary frames and proof contract stay intact. A normal-debug native experiment must be separate: same camera and exposure, A/B prepared normal intensity (default 0.75 vs 0), shadow-on/off if feasible, plus an occlusion/depth witness. Keep those images outside the admitted 43-frame set. Only change the material graph if this experiment proves the source. No v8 geometry, roads, BOB, mask or saved map changes.

**Acceptance:** sample must no longer have newly darkened large regions in Prepared versus baseline and checker; repeat across all near probes, confirm root/source/camera identity and restore the scene; full 43/43 technical proof and exact-head CI remain required. Visual/performance/production acceptance remain PENDING_OWNER/NOT_MEASURED/UNAUTHORIZED.
