# Sa Calobra surface coverage — measurement appendix

Read-only evidence for [the audit report](sa-calobra-surface-coverage-2026-10-04.md). All coordinates are EPSG:25831 metres; no source imagery is embedded.

## Input identity

| Role | Candidate manifest | SHA-256 |
|---|---|---|
| surface | `surface-cover-v1a-2026-10-04/surface-cover-manifest.json` | `ac787853dbd25bb3a4599fdea8dcecb5ec7efe415f86c2a5940be1cae072549d` |
| lidar | `lidar-masks-v1b-2026-10-04/lidar-manifest.json` | `fd14d0725f867759438727f9f7275f15427220ea185b01783c9d616432523e00` |
| road | `road-masks-v1a-2026-10-04/road-mask-manifest.json` | `b9a1891ffe35243dbdf2b3ca9c4e6c67a210cceb4c35123a1a64befb4dff38a9` |
| review | `mask-transition-review-v1a-2026-10-04/review-manifest.json` | `aed7f8324102750fd898224a3951e10507b27e6878a7c093def723b4c0a5bf14` |

## Full-area sector inventory

Sectors cover the entire 4033-square grid with rounded `linspace(0, 4033, 9)` edges. R1 is north; C1 is west. Shares are percentages of each sector, not classification accuracy. Bounds are half-open pixel indices.

| Sector | Row start:end | Column start:end | Cells | Unresolved % | Display no-LiDAR % | Raw no-LiDAR % |
|---|---|---|---:|---:|---:|---:|
| R1C1 | 0:504 | 0:504 | 254016 | 17.002472 | 33.812437 | 34.880086 |
| R1C2 | 0:504 | 504:1008 | 254016 | 12.664950 | 25.531069 | 26.513291 |
| R1C3 | 0:504 | 1008:1512 | 254016 | 19.334609 | 27.086483 | 27.086483 |
| R1C4 | 0:504 | 1512:2016 | 254016 | 21.705326 | 28.928886 | 29.287132 |
| R1C5 | 0:504 | 2016:2521 | 254520 | 18.783200 | 25.763005 | 25.765755 |
| R1C6 | 0:504 | 2521:3025 | 254016 | 10.502882 | 23.155628 | 23.155628 |
| R1C7 | 0:504 | 3025:3529 | 254016 | 12.808642 | 24.668131 | 24.668131 |
| R1C8 | 0:504 | 3529:4033 | 254016 | 17.605978 | 24.766944 | 24.766944 |
| R2C1 | 504:1008 | 0:504 | 254016 | 21.801383 | 21.768314 | 22.106481 |
| R2C2 | 504:1008 | 504:1008 | 254016 | 20.349112 | 17.082389 | 17.213089 |
| R2C3 | 504:1008 | 1008:1512 | 254016 | 18.126811 | 18.801965 | 18.802359 |
| R2C4 | 504:1008 | 1512:2016 | 254016 | 19.531841 | 17.070972 | 17.955956 |
| R2C5 | 504:1008 | 2016:2521 | 254520 | 21.382603 | 13.960789 | 15.033003 |
| R2C6 | 504:1008 | 2521:3025 | 254016 | 18.155549 | 13.657407 | 13.928650 |
| R2C7 | 504:1008 | 3025:3529 | 254016 | 19.347206 | 15.763968 | 15.763968 |
| R2C8 | 504:1008 | 3529:4033 | 254016 | 15.499417 | 14.521526 | 14.521526 |
| R3C1 | 1008:1512 | 0:504 | 254016 | 13.801099 | 10.085191 | 10.289509 |
| R3C2 | 1008:1512 | 504:1008 | 254016 | 33.205782 | 7.029478 | 7.477875 |
| R3C3 | 1008:1512 | 1008:1512 | 254016 | 31.077176 | 8.052642 | 8.604576 |
| R3C4 | 1008:1512 | 1512:2016 | 254016 | 24.868906 | 8.567177 | 8.571507 |
| R3C5 | 1008:1512 | 2016:2521 | 254520 | 25.563021 | 5.475798 | 5.874980 |
| R3C6 | 1008:1512 | 2521:3025 | 254016 | 26.951058 | 4.971340 | 5.127236 |
| R3C7 | 1008:1512 | 3025:3529 | 254016 | 24.029982 | 6.196066 | 6.196066 |
| R3C8 | 1008:1512 | 3529:4033 | 254016 | 20.628228 | 5.470128 | 5.470128 |
| R4C1 | 1512:2016 | 0:504 | 254016 | 19.916068 | 4.971734 | 4.971734 |
| R4C2 | 1512:2016 | 504:1008 | 254016 | 38.223183 | 3.722994 | 3.722994 |
| R4C3 | 1512:2016 | 1008:1512 | 254016 | 38.503480 | 4.389881 | 4.389881 |
| R4C4 | 1512:2016 | 1512:2016 | 254016 | 20.147943 | 5.275652 | 5.275652 |
| R4C5 | 1512:2016 | 2016:2521 | 254520 | 25.927628 | 3.681832 | 3.681832 |
| R4C6 | 1512:2016 | 2521:3025 | 254016 | 25.268881 | 4.480820 | 4.611914 |
| R4C7 | 1512:2016 | 3025:3529 | 254016 | 29.292643 | 5.476820 | 5.476820 |
| R4C8 | 1512:2016 | 3529:4033 | 254016 | 19.305870 | 4.430036 | 4.430036 |
| R5C1 | 2016:2521 | 0:504 | 254520 | 18.945466 | 8.749804 | 8.749804 |
| R5C2 | 2016:2521 | 504:1008 | 254520 | 25.624705 | 10.631777 | 10.631777 |
| R5C3 | 2016:2521 | 1008:1512 | 254520 | 26.112290 | 10.963382 | 10.963382 |
| R5C4 | 2016:2521 | 1512:2016 | 254520 | 16.419142 | 11.973519 | 11.973519 |
| R5C5 | 2016:2521 | 2016:2521 | 255025 | 18.691893 | 11.167925 | 11.411038 |
| R5C6 | 2016:2521 | 2521:3025 | 254520 | 17.443423 | 13.431165 | 13.624470 |
| R5C7 | 2016:2521 | 3025:3529 | 254520 | 21.143722 | 14.136021 | 14.136021 |
| R5C8 | 2016:2521 | 3529:4033 | 254520 | 14.211064 | 13.453167 | 13.453167 |
| R6C1 | 2521:3025 | 0:504 | 254016 | 20.976238 | 17.113883 | 17.113883 |
| R6C2 | 2521:3025 | 504:1008 | 254016 | 18.799603 | 22.858009 | 22.858009 |
| R6C3 | 2521:3025 | 1008:1512 | 254016 | 20.467215 | 23.163502 | 23.163502 |
| R6C4 | 2521:3025 | 1512:2016 | 254016 | 18.311051 | 22.668651 | 22.668651 |
| R6C5 | 2521:3025 | 2016:2521 | 254520 | 15.937451 | 22.985227 | 23.558856 |
| R6C6 | 2521:3025 | 2521:3025 | 254016 | 14.097537 | 25.461782 | 25.461782 |
| R6C7 | 2521:3025 | 3025:3529 | 254016 | 17.546139 | 24.848041 | 24.848041 |
| R6C8 | 2521:3025 | 3529:4033 | 254016 | 15.659643 | 24.643723 | 24.643723 |
| R7C1 | 3025:3529 | 0:504 | 254016 | 30.385094 | 27.302611 | 27.302611 |
| R7C2 | 3025:3529 | 504:1008 | 254016 | 24.211861 | 29.822925 | 29.822925 |
| R7C3 | 3025:3529 | 1008:1512 | 254016 | 18.080357 | 26.518015 | 26.518015 |
| R7C4 | 3025:3529 | 1512:2016 | 254016 | 16.406053 | 26.095994 | 26.095994 |
| R7C5 | 3025:3529 | 2016:2521 | 254520 | 14.107339 | 24.427157 | 25.795222 |
| R7C6 | 3025:3529 | 2521:3025 | 254016 | 24.366575 | 28.145471 | 28.180508 |
| R7C7 | 3025:3529 | 3025:3529 | 254016 | 22.810374 | 23.024928 | 23.024928 |
| R7C8 | 3025:3529 | 3529:4033 | 254016 | 20.671533 | 26.130244 | 26.130244 |
| R8C1 | 3529:4033 | 0:504 | 254016 | 32.142463 | 15.945059 | 15.945059 |
| R8C2 | 3529:4033 | 504:1008 | 254016 | 26.701074 | 16.855237 | 16.855237 |
| R8C3 | 3529:4033 | 1008:1512 | 254016 | 16.208428 | 16.366292 | 16.366292 |
| R8C4 | 3529:4033 | 1512:2016 | 254016 | 22.265920 | 15.471860 | 15.471860 |
| R8C5 | 3529:4033 | 2016:2521 | 254520 | 14.219315 | 16.738567 | 17.097674 |
| R8C6 | 3529:4033 | 2521:3025 | 254016 | 23.105631 | 17.249307 | 17.951231 |
| R8C7 | 3529:4033 | 3025:3529 | 254016 | 17.765416 | 14.252252 | 14.371142 |
| R8C8 | 3529:4033 | 3529:4033 | 254016 | 17.680776 | 16.076940 | 16.076940 |

## Reviewed crop centers

Systematic crops: 128 m square with a central 64 m detail. Targeted crops use the same display sizes. A displayed center may be clipped inward to keep the crop inside the AOI.

| ID | Easting (m) | Northing (m) | Selection |
|---|---:|---:|---|
| S11 | 483252.25 | 4409264.25 | Center of a 4 × 4 macro-sector |
| S12 | 483756.25 | 4409264.25 | Center of a 4 × 4 macro-sector |
| S21 | 483252.25 | 4408760.25 | Center of a 4 × 4 macro-sector |
| S22 | 483756.25 | 4408760.25 | Center of a 4 × 4 macro-sector |
| S13 | 484260.25 | 4409264.25 | Center of a 4 × 4 macro-sector |
| S14 | 484764.25 | 4409264.25 | Center of a 4 × 4 macro-sector |
| S23 | 484260.25 | 4408760.25 | Center of a 4 × 4 macro-sector |
| S24 | 484764.25 | 4408760.25 | Center of a 4 × 4 macro-sector |
| S31 | 483252.25 | 4408256.25 | Center of a 4 × 4 macro-sector |
| S32 | 483756.25 | 4408256.25 | Center of a 4 × 4 macro-sector |
| S41 | 483252.25 | 4407752.25 | Center of a 4 × 4 macro-sector |
| S42 | 483756.25 | 4407752.25 | Center of a 4 × 4 macro-sector |
| S33 | 484260.25 | 4408256.25 | Center of a 4 × 4 macro-sector |
| S34 | 484764.25 | 4408256.25 | Center of a 4 × 4 macro-sector |
| S43 | 484260.25 | 4407752.25 | Center of a 4 × 4 macro-sector |
| S44 | 484764.25 | 4407752.25 | Center of a 4 × 4 macro-sector |
| class4-1 | 484072.25 | 4408508.25 | highest 32m block count; centers at least 250m apart within class |
| class4-2 | 484360.25 | 4409340.25 | highest 32m block count; centers at least 250m apart within class |
| class4-3 | 484712.25 | 4408668.25 | highest 32m block count; centers at least 250m apart within class |
| class4-4 | 484936.25 | 4408860.25 | highest 32m block count; centers at least 250m apart within class |
| class5-1 | 484360.25 | 4407740.25 | highest 32m block count; centers at least 250m apart within class |
| class5-2 | 483064.25 | 4407740.25 | highest 32m block count; centers at least 250m apart within class |
| class5-3 | 484872.25 | 4407612.25 | highest 32m block count; centers at least 250m apart within class |
| class5-4 | 483368.25 | 4407580.25 | highest 32m block count; centers at least 250m apart within class |
| unresolved-component-1 | 483493.75 | 4408682.75 | center of bounding box of largest connected unresolved components |
| unresolved-component-2 | 483319.25 | 4408712.25 | center of bounding box of largest connected unresolved components |
| deepest-empty-cell | 484952.75 | 4408179.75 | maximum distance to an observed cell center |

The actual deepest empty-cell center is row 2673, column 3977: E 484988.75, N 4408179.75. Its displayed crop center is shifted west to remain inside the raster. Bounding-box centers need not fall inside their named connected component.

## Local reproducibility receipts

The full JSON measurements and source-image comparisons remain under the workspace `work/surface-coverage-audit-2026-10-04` directory. This location is a local receipt, not a remote backup of source imagery. The replay document and committed aggregate measurements provide remote reproducibility context.

| Output | SHA-256 after two byte-identical runs |
|---|---|
| `audit.json` | `b5fdb682f9d4d001d8985d98e88f326c59b2b34d4fa1112f18089ee5f2254fd9` |
| `targeted-audit.json` | `f0119ec96fe866739d4b21825becba5605d8ad864cfba4071d48712758b688c9` |
| `whole-area.png` | `7f57644545d2aaf75c098b3e3c9d35671f7a4a2e0583382d33c58de113d6ed16` |
| `crops-1-1.png` | `14c912bd082982a2190f8a5795647c8f02c35fd8587b2b287cad980dcb03111b` |
| `crops-1-2.png` | `a2bad890b5ae5d46d6cf2bb880f5e9a0f3171b359ea7e05bbbddc99c95457e84` |
| `crops-2-1.png` | `540769e6b49ed45c7c5ecb8a44c1dc5a6e41c210c53da0a6e38532af94238c89` |
| `crops-2-2.png` | `b3edff39d8fb836ddd9c7ae57945cb0cd9cdc41ba06da6cff397c9b60c94b22d` |
| `targeted-1.png` | `bcccc10f8635a958ad5262f5fa323010b8bef171072c0c822b2753afd4f43c33` |
| `targeted-2.png` | `b21473781c94de208fabca5118f4ef987cc72e8ce71cb698e3b1aa60e2a0f1e2` |
| `targeted-3.png` | `1d3bb26a0e3ee593ec86fb26070ba018586b279b90fdb9f2145b6d3f886f4a6a` |

## Independent arithmetic checks

```json
{
  "status": "PASS",
  "independent_block_reshape_checks": 5,
  "sector_partition": "PASS",
  "road_band_partition": "PASS",
  "brute_force_distance_checks": 201,
  "distance_random_seed": 379
}
```

## Interpretation constraints

The reference input is a candidate, not independent ground truth. No confusion matrix or calibrated accuracy follows from these totals. Raw occupancy and displayed no-LiDAR labels have different counts because other mapped evidence can label empty LiDAR cells. No unknown cell was relabeled in this audit.
